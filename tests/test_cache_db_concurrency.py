"""Regression coverage for shared SQLite cache connection serialization."""

from __future__ import annotations

import threading
import time
from concurrent.futures import ThreadPoolExecutor

from core import cache_db


def test_execute_serializes_shared_connection_access(monkeypatch):
    """Concurrent callers must never execute on the shared connection simultaneously."""
    state_lock = threading.Lock()
    active = 0
    max_active = 0
    calls = 0

    class _ConnectionStub:
        """Record overlapping execute calls on a shared fake connection."""

        def execute(self, sql, params=()):
            """Track active execution count while simulating a short SQLite call."""
            nonlocal active, max_active, calls
            _ = (sql, params)
            with state_lock:
                active += 1
                calls += 1
                max_active = max(max_active, active)
            time.sleep(0.01)
            with state_lock:
                active -= 1
            return self

        def commit(self):
            """Provide the commit surface expected by the cache helper."""
            return None

    connection = _ConnectionStub()
    monkeypatch.setattr(cache_db, "_get_conn", lambda: connection)

    start = threading.Barrier(8)

    def worker():
        """Start all callers together and execute one cache statement."""
        start.wait()
        cache_db._execute("SELECT 1")

    with ThreadPoolExecutor(max_workers=8) as pool:
        futures = [pool.submit(worker) for _ in range(8)]
        for future in futures:
            future.result(timeout=3)

    assert calls == 8
    assert max_active == 1


def test_concurrent_cache_writes_round_trip(tmp_path, monkeypatch):
    """Concurrent cache writes must all persist and remain readable."""
    cache_db._close_conn()
    monkeypatch.setattr(cache_db, "_cache_db_path", tmp_path / "cache.db")
    cache_db.init_db()

    def write(index: int) -> None:
        """Write one unique model-cache record."""
        cache_db.set_model_cache("test", f"model-{index}", {"index": index})

    try:
        with ThreadPoolExecutor(max_workers=8) as pool:
            futures = [pool.submit(write, index) for index in range(40)]
            for future in futures:
                future.result(timeout=3)

        assert [
            cache_db.get_model_cache("test", f"model-{index}") for index in range(40)
        ] == [{"index": index} for index in range(40)]
    finally:
        cache_db._close_conn()
