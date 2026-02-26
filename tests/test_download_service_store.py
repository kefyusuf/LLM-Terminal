from download_service import DownloadStore


def test_upsert_job_rejects_duplicate_active_target(tmp_path):
    store = DownloadStore(tmp_path / "jobs.db")
    model = {"source": "Ollama", "name": "Qwen3-Coder-Next", "publisher": "ollama"}

    first_job, first_created = store.upsert_job(model)
    second_job, second_created = store.upsert_job(model)

    assert first_created is True
    assert second_created is False
    assert (
        first_job["target_id"] == second_job["target_id"] == "ollama:qwen3-coder-next"
    )
