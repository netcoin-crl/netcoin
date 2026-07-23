import threading
from pathlib import Path

from netcoin.webwallet import LocalNodeController


def test_concurrent_start_calls_only_spawn_one_subprocess(tmp_path: Path, monkeypatch):
    """Regression: the web wallet's ThreadingHTTPServer can dispatch two
    overlapping /api/local-node/start requests (an impatient double click, a
    retried request while the first node is still binding its port). Without
    a lock, both can see "not running yet" and each call subprocess.Popen —
    the second one hits a real OS-level "Address already in use" and
    overwrites the handle to the first (successful) process, so the request
    that actually started a working node gets reported back as a failure.
    """
    controller = LocalNodeController(enabled=True, port=59999, data_dir=tmp_path)
    popen_calls: list[list[str]] = []

    class FakeProcess:
        pid = 12345

        def poll(self):
            return None  # never exits on its own

    def fake_popen(cmd, **kwargs):
        popen_calls.append(cmd)
        return FakeProcess()

    def fake_external_info():
        # Only "comes online" once a (the) subprocess has actually been spawned.
        return {"height": 1, "peers": [], "version": "test"} if popen_calls else None

    monkeypatch.setattr("netcoin.webwallet.subprocess.Popen", fake_popen)
    monkeypatch.setattr(controller, "_external_info", fake_external_info)

    results: list[dict] = []
    errors: list[Exception] = []

    def run():
        try:
            results.append(controller.start())
        except Exception as exc:
            errors.append(exc)

    threads = [threading.Thread(target=run) for _ in range(5)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=5)

    assert not errors, f"start() raised under concurrent calls: {errors}"
    assert len(popen_calls) == 1, f"expected exactly one subprocess spawn, got {len(popen_calls)}"
    assert all(r.get("message") for r in results)


def test_start_returns_already_running_message_without_spawning_twice(tmp_path: Path, monkeypatch):
    controller = LocalNodeController(enabled=True, port=59998, data_dir=tmp_path)
    monkeypatch.setattr(controller, "_external_info", lambda: {"height": 5, "peers": [], "version": "test"})
    popen_calls: list[list[str]] = []
    monkeypatch.setattr("netcoin.webwallet.subprocess.Popen", lambda cmd, **kwargs: popen_calls.append(cmd) or object())

    result = controller.start()

    assert result["message"] == "node already running on this port"
    assert popen_calls == []


def test_start_and_stop_require_enabled():
    controller = LocalNodeController(enabled=False, port=59997)
    try:
        controller.start()
        assert False, "expected ValueError"
    except ValueError as exc:
        assert "127.0.0.1" in str(exc)
    try:
        controller.stop()
        assert False, "expected ValueError"
    except ValueError as exc:
        assert "127.0.0.1" in str(exc)
