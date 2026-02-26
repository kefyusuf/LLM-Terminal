from download_service import DownloadStore


def test_upsert_job_rejects_duplicate_active_target(tmp_path):
    store = DownloadStore(tmp_path / "jobs.db")
    model = {"source": "Ollama", "name": "Qwen3-Coder-Next", "publisher": "ollama"}

    first_job, first_created = store.upsert_job(model)
    second_job, second_created = store.upsert_job(model)

    assert first_job is not None
    assert second_job is not None
    assert first_created is True
    assert second_created is False
    assert (
        first_job["target_id"] == second_job["target_id"] == "ollama:qwen3-coder-next"
    )


def test_normalize_target_ids_merges_legacy_casing_duplicates(tmp_path):
    store = DownloadStore(tmp_path / "jobs.db")
    with store._connect() as conn:
        conn.execute(
            """
            INSERT INTO jobs (
                target_id, source, publisher, name, command_json, status,
                detail, progress, created_at, updated_at, cancel_requested, return_code
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, NULL)
            """,
            (
                "Ollama:Qwen3-Coder-Next",
                "Ollama",
                "ollama",
                "qwen3-coder-next",
                "[]",
                "completed",
                "done",
                "",
                1.0,
                1.0,
            ),
        )
        conn.execute(
            """
            INSERT INTO jobs (
                target_id, source, publisher, name, command_json, status,
                detail, progress, created_at, updated_at, cancel_requested, return_code
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, NULL)
            """,
            (
                "ollama:qwen3-coder-next",
                "ollama",
                "ollama",
                "qwen3-coder-next",
                "[]",
                "running",
                "Downloading",
                "40%",
                2.0,
                2.0,
            ),
        )

    store.normalize_target_ids()
    jobs = store.list_jobs(limit=10)
    assert len(jobs) == 1
    assert jobs[0] is not None
    assert jobs[0]["target_id"] == "ollama:qwen3-coder-next"


def test_recover_orphaned_running_jobs_marks_failed(tmp_path):
    store = DownloadStore(tmp_path / "jobs.db")
    with store._connect() as conn:
        conn.execute(
            """
            INSERT INTO jobs (
                target_id, source, publisher, name, command_json, status,
                detail, progress, created_at, updated_at, cancel_requested, return_code
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, NULL)
            """,
            (
                "ollama:qwen3",
                "ollama",
                "ollama",
                "qwen3",
                "[]",
                "running",
                "Downloading",
                "50%",
                3.0,
                3.0,
            ),
        )

    store.recover_orphaned_running_jobs()
    jobs = store.list_jobs(limit=10)
    assert jobs[0] is not None
    assert jobs[0]["status"] == "failed"
    assert "service restarted" in jobs[0]["detail"]
