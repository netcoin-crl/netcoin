from pathlib import Path

import pytest

from netcoin.apps import AppError, AppStore


def test_circle_stores_rules_and_starts_unpinned(tmp_path: Path):
    store = AppStore(tmp_path)
    circle = store.propose_circle({"name": "Mining Ops", "creator": "alice", "rules": "Be kind. No spam."})
    assert circle["rules"] == "Be kind. No spam."
    assert circle["pinned_post_id"] == ""


def test_creator_can_pin_a_post_belonging_to_the_circle(tmp_path: Path):
    store = AppStore(tmp_path)
    circle = store.propose_circle({"name": "Mining Ops", "creator": "alice"})
    post = store.create_community_post({"name": "alice", "message": "Welcome!", "circle_id": circle["circle_id"]})

    updated = store.set_circle_pin(circle["circle_id"], {"creator": "alice", "post_id": post["post_id"]})
    assert updated["pinned_post_id"] == post["post_id"]

    unpinned = store.set_circle_pin(circle["circle_id"], {"creator": "alice", "post_id": ""})
    assert unpinned["pinned_post_id"] == ""


def test_non_creator_cannot_pin(tmp_path: Path):
    store = AppStore(tmp_path)
    circle = store.propose_circle({"name": "Mining Ops", "creator": "alice"})
    post = store.create_community_post({"name": "bob", "message": "hi", "circle_id": circle["circle_id"]})
    with pytest.raises(AppError, match="only the circle creator"):
        store.set_circle_pin(circle["circle_id"], {"creator": "bob", "post_id": post["post_id"]})


def test_cannot_pin_a_post_from_a_different_circle(tmp_path: Path):
    store = AppStore(tmp_path)
    circle_a = store.propose_circle({"name": "Circle A", "creator": "alice"})
    circle_b = store.propose_circle({"name": "Circle B", "creator": "alice"})
    post_in_b = store.create_community_post({"name": "alice", "message": "hi", "circle_id": circle_b["circle_id"]})
    with pytest.raises(AppError, match="does not belong to this circle"):
        store.set_circle_pin(circle_a["circle_id"], {"creator": "alice", "post_id": post_in_b["post_id"]})
