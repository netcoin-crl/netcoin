from pathlib import Path

import pytest

from netcoin.apps import AppError, AppStore, route_app_get, route_app_post
from netcoin.chain import Blockchain


def test_idempotency_replays_same_response_and_rejects_body_change(tmp_path: Path):
    store = AppStore(tmp_path)
    chain = Blockchain(tmp_path)
    body = {"author": "alice", "message": "hello", "idempotency_key": "idem-1"}
    status, first = route_app_post(store, chain, "/api/community/posts", dict(body))
    assert status == 200
    status, second = route_app_post(store, chain, "/api/community/posts", dict(body))
    assert status == 200
    assert second["idempotent_replay"] is True
    assert second["post_id"] == first["post_id"]
    with pytest.raises(AppError, match="different request body"):
        route_app_post(
            store, chain, "/api/community/posts", {"author": "alice", "message": "changed", "idempotency_key": "idem-1"}
        )


def test_app_nonce_replay_protection_and_security_status(tmp_path: Path):
    store = AppStore(tmp_path)
    chain = Blockchain(tmp_path)
    body = {"author": "alice", "message": "n1", "signer": "alice", "require_nonce": True, "app_nonce": 1}
    route_app_post(store, chain, "/api/community/posts", dict(body))
    with pytest.raises(AppError, match="nonce"):
        route_app_post(store, chain, "/api/community/posts", dict(body))
    status, security, _ = route_app_get(store, chain, "/api/security/status", {})
    assert status == 200
    assert security["app_nonce_scopes"] == 1
