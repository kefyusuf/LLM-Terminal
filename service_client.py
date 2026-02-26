import json
import subprocess
import sys
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


SERVICE_HOST = "127.0.0.1"
SERVICE_PORT = 8765
SERVICE_BASE_URL = f"http://{SERVICE_HOST}:{SERVICE_PORT}"


def _request(method, path, payload=None, timeout=2.0):
    url = f"{SERVICE_BASE_URL}{path}"
    data = None
    headers = {"Content-Type": "application/json"}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")

    req = Request(url=url, data=data, method=method, headers=headers)
    with urlopen(req, timeout=timeout) as response:
        body = response.read().decode("utf-8")
        if not body:
            return {}
        return json.loads(body)


def is_service_running():
    try:
        data = _request("GET", "/health", timeout=1.0)
        return bool(data.get("ok"))
    except (URLError, HTTPError, TimeoutError, ValueError):
        return False


def ensure_service_running():
    if is_service_running():
        return True

    script_path = Path(__file__).resolve().with_name("download_service.py")
    creationflags = 0
    popen_kwargs = {
        "stdout": subprocess.DEVNULL,
        "stderr": subprocess.DEVNULL,
        "stdin": subprocess.DEVNULL,
    }

    if sys.platform.startswith("win"):
        detached = getattr(subprocess, "DETACHED_PROCESS", 0)
        new_group = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
        creationflags = detached | new_group
        popen_kwargs["creationflags"] = creationflags
    else:
        popen_kwargs["start_new_session"] = True

    subprocess.Popen([sys.executable, str(script_path)], **popen_kwargs)

    deadline = time.time() + 6.0
    while time.time() < deadline:
        if is_service_running():
            return True
        time.sleep(0.2)
    return False


def list_jobs(limit=50):
    data = _request("GET", f"/jobs?limit={int(limit)}", timeout=2.0)
    return data.get("jobs", [])


def create_job(model):
    return _request("POST", "/jobs", payload={"model": model}, timeout=3.0)


def cancel_job(target_id):
    return _request(
        "POST", "/jobs/cancel", payload={"target_id": target_id}, timeout=2.0
    )
