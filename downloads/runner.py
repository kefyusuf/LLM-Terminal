"""Subprocess runners for download jobs.

Extracted from downloads/download_service.py during the architecture
review (candidate #5). Two runners, both consume a ``DownloadStore``
+ the shared ``STATE`` singleton (imported from ``download_service``):

- :func:`run_hf_download`: ``hf_api_download`` sentinel command →
  HuggingFace snapshot_download via subprocess.
- :func:`run_streamed_command`: every other command (e.g. ``ollama
  pull``) → stdout-streamed subprocess.

Both write status to ``STATE.store.update_job()`` and respect
``STATE.store.mark_cancel_requested()`` by escalating from
``terminate()`` to ``kill()`` after 1.5 seconds.
"""

from __future__ import annotations

import os
import subprocess
import sys
import time
from typing import Any

from loguru import logger

from core.utils import extract_download_progress


def _service_popen_kwargs() -> dict[str, Any]:
    import config

    kwargs: dict[str, Any] = {}
    if sys.platform.startswith("win"):
        kwargs["creationflags"] = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    env = os.environ.copy()
    hf_token = getattr(config.settings, "hf_token", None)
    if hf_token:
        env["HF_TOKEN"] = hf_token
    kwargs["env"] = env
    return kwargs


def _can_terminate_process(process) -> bool:
    return hasattr(process, "terminate") and callable(getattr(process, "terminate", None))


def _extract_progress(line: str) -> str | None:
    """Wrap :func:`utils.extract_download_progress` returning a ``"N%"`` string."""
    value = extract_download_progress(line)
    return f"{value}%" if value is not None else None


def is_hf_api_command(command) -> bool:
    """Return True when *command* is an internal HF API download payload."""
    return isinstance(command, list) and len(command) > 0 and command[0] == "hf_api_download"


def _repo_id_from_hf_command(command) -> str:
    """Extract repository id from an internal HF API command payload."""
    if not is_hf_api_command(command):
        return ""
    return command[1] if len(command) > 1 else ""


def _cancel_requested(state, target_id: str) -> bool:
    latest = state.store.get_job_by_target(target_id)
    return bool(latest and latest.get("cancel_requested"))


def _finalize_terminal(state, target_id: str, return_code, cancelled: bool, *, last_line: str = "") -> None:
    """Write the terminal state of a job (completed / failed / cancelled)."""
    if cancelled:
        state.store.update_job(
            target_id,
            status="cancelled",
            detail="Canceled",
            progress="",
            return_code=return_code,
        )
    elif return_code == 0:
        state.store.update_job(
            target_id,
            status="completed",
            detail="Completed",
            progress="",
            return_code=0,
        )
    else:
        failure_detail = "download command exited with non-zero status"
        if last_line:
            failure_detail = last_line[:180]
        state.store.update_job(
            target_id,
            status="failed",
            detail=failure_detail,
            progress="",
            return_code=return_code,
        )


def run_hf_download(state, target_id: str, command) -> None:
    """Run a HuggingFace snapshot_download for *target_id*.

    The HF runner is unique: it inlines a Python ``-c`` script that
    calls :func:`huggingface_hub.snapshot_download` with
    ``allow_patterns=['*.gguf']`` and a fixed ``local_dir='models'``.
    The script receives the repo id as ``argv[1]``.

    The subprocess inherits ``HF_TOKEN`` via
    :func:`_service_popen_kwargs` so authenticated downloads work
    when ``AIMODEL_HF_TOKEN`` is configured.
    """
    repo_id = _repo_id_from_hf_command(command)
    if not repo_id:
        state.store.update_job(
            target_id,
            status="failed",
            detail="missing Hugging Face repository id",
            return_code=1,
        )
        return

    state.store.update_job(
        target_id,
        status="running",
        detail="Downloading",
        progress="",
    )
    hf_script = (
        "from huggingface_hub import snapshot_download; "
        "import sys; "
        "snapshot_download("
        "repo_id=sys.argv[1], "
        "allow_patterns=['*.gguf'], "
        "local_dir='models', "
        "local_dir_use_symlinks=False"
        ")"
    )
    process = subprocess.Popen(
        [sys.executable, "-c", hf_script, repo_id],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
        **_service_popen_kwargs(),
    )
    state.set_process(target_id, process)
    cancel_sent_at = None

    try:
        while True:
            if _cancel_requested(state, target_id):
                if cancel_sent_at is None:
                    cancel_sent_at = time.monotonic()
                    try:
                        process.terminate()
                    except OSError:
                        pass
                elif process.poll() is None and (time.monotonic() - cancel_sent_at) > 1.5:
                    try:
                        process.kill()
                    except OSError:
                        pass

            return_code = process.poll()
            if return_code is not None:
                break
            time.sleep(0.25)

        cancelled = _cancel_requested(state, target_id)
        if cancelled:
            _finalize_terminal(state, target_id, return_code, cancelled=True)
        elif return_code == 0:
            _finalize_terminal(state, target_id, 0, cancelled=False)
        else:
            failure_detail = "hugging face download failed"
            if process.stderr is not None:
                err_text = process.stderr.read().strip()
                if err_text:
                    failure_detail = err_text.splitlines()[-1][:180]
            state.store.update_job(
                target_id,
                status="failed",
                detail=failure_detail,
                progress="",
                return_code=return_code,
            )
    except Exception as exc:
        logger.warning("HF download failed for {}: {}", target_id, exc)
        detail = str(exc).strip() or "hugging face download failed"
        state.store.update_job(
            target_id,
            status="failed",
            detail=detail[:180],
            progress="",
            return_code=1,
        )
    finally:
        state.clear_process(target_id)


def run_streamed_command(state, target_id: str, command) -> None:
    """Run a generic subprocess that streams progress on stdout.

    Used for ``ollama pull`` and any non-HF command. Progress is
    parsed from stdout lines via :func:`extract_download_progress`;
    a 1-second idle heartbeat keeps ``updated_at`` fresh even when
    no progress lines arrive.
    """
    process = subprocess.Popen(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        bufsize=1,
        **_service_popen_kwargs(),
    )
    state.set_process(target_id, process)
    start = time.monotonic()
    last_update = start
    last_line = ""

    try:
        if process.stdout is not None:
            for raw_line in process.stdout:
                line = raw_line.strip()
                if line:
                    last_line = line

                if _cancel_requested(state, target_id):
                    try:
                        process.terminate()
                    except OSError:
                        pass

                progress = _extract_progress(line)
                now = time.monotonic()
                if progress is not None:
                    state.store.update_job(
                        target_id,
                        status="running",
                        detail="Downloading",
                        progress=progress,
                    )
                    last_update = now
                    continue

                if now - last_update >= 1.0:
                    elapsed = int(now - start)
                    state.store.update_job(
                        target_id,
                        status="running",
                        detail="Downloading",
                        progress=f"{elapsed}s",
                    )
                    last_update = now

        return_code = process.wait()
        cancelled = _cancel_requested(state, target_id)
        _finalize_terminal(state, target_id, return_code, cancelled, last_line=last_line)
    finally:
        state.clear_process(target_id)


def process_job(state, target_id: str) -> None:
    """Process a single download job (called in thread pool).

    Dispatches to the HF runner or the streamed runner based on the
    command payload stored in the job row.
    """
    try:
        cmd = state.store.get_command(target_id)
        if not cmd:
            state.store.update_job(
                target_id, status="failed", detail="missing command", return_code=1
            )
            return

        if is_hf_api_command(cmd):
            run_hf_download(state, target_id, cmd)
            return

        run_streamed_command(state, target_id, cmd)
    except FileNotFoundError:
        state.store.update_job(
            target_id,
            status="failed",
            detail="required command not found",
            return_code=127,
        )
    except OSError as exc:
        state.store.update_job(target_id, status="failed", detail=str(exc)[:180], return_code=1)
    finally:
        state.clear_process(target_id)
