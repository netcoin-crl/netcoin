from pathlib import Path

import pytest

from netcoin.apps import AppError, AppStore
from netcoin.wallet import Wallet


def test_poll_vote_weight_is_always_one(tmp_path: Path):
    store = AppStore(tmp_path / "chain")
    poll = store.create_poll({"title": "Ship it?", "options": ["Yes", "No"]})
    option = poll["options"][0]["option_id"]
    voter = Wallet.create().segwit_address
    result = store.cast_poll_vote(
        poll["poll_id"],
        {"voter_address": voter, "option_id": option, "weight": 999, "allow_unverified_demo": True},
    )
    assert result["results"][option]["weight"] == 1


def test_poll_rejects_votes_before_start_time(tmp_path: Path):
    store = AppStore(tmp_path / "chain")
    poll = store.create_poll(
        {"title": "Future poll", "options": ["Yes", "No"], "start_time": 9999999999}
    )
    option = poll["options"][0]["option_id"]
    voter = Wallet.create().segwit_address
    with pytest.raises(AppError, match="has not started"):
        store.cast_poll_vote(
            poll["poll_id"],
            {"voter_address": voter, "option_id": option, "allow_unverified_demo": True},
        )


def test_poll_id_collision_is_rejected(tmp_path: Path):
    store = AppStore(tmp_path / "chain")
    store.create_poll({"title": "First", "options": ["Yes", "No"], "poll_id": "fixed-poll"})
    with pytest.raises(AppError, match="already exists"):
        store.create_poll({"title": "Second", "options": ["Yes", "No"], "poll_id": "fixed-poll"})


def test_close_poll_cannot_be_reopened_via_arbitrary_status(tmp_path: Path):
    store = AppStore(tmp_path / "chain")
    poll = store.create_poll({"title": "Ship it?", "options": ["Yes", "No"]})
    closed = store.close_poll(poll["poll_id"], {"status": "open"})
    assert closed["status"] == "closed"
    assert closed["closed_at"]


def test_bounty_id_collision_is_rejected(tmp_path: Path):
    store = AppStore(tmp_path / "chain")
    store.create_bounty({"title": "Fix a bug", "bounty_id": "fixed-bounty"})
    with pytest.raises(AppError, match="already exists"):
        store.create_bounty({"title": "Another bug", "bounty_id": "fixed-bounty"})


def test_improvement_vote_requires_voter_and_blocks_double_voting(tmp_path: Path):
    store = AppStore(tmp_path / "chain")
    idea = store.create_improvement({"title": "Add dark mode"})
    with pytest.raises(AppError, match="voter is required"):
        store.vote_improvement(idea["idea_id"], {})
    voted = store.vote_improvement(idea["idea_id"], {"voter": "alice"})
    assert voted["votes"] == 1
    with pytest.raises(AppError, match="already voted"):
        store.vote_improvement(idea["idea_id"], {"voter": "alice"})
    voted_again = store.vote_improvement(idea["idea_id"], {"voter": "bob"})
    assert voted_again["votes"] == 2


def test_switching_post_vote_decrements_old_bucket(tmp_path: Path):
    store = AppStore(tmp_path / "chain")
    post = store.create_community_post({"name": "alice", "message": "hello world"})
    post_id = post["post_id"]
    up = store.vote_community_post(post_id, {"voter": "alice", "direction": "up"})
    assert up["upvotes"] == 1 and up.get("downvotes", 0) == 0 and up["score"] == 1
    down = store.vote_community_post(post_id, {"voter": "alice", "direction": "down"})
    assert down["upvotes"] == 0
    assert down["downvotes"] == 1
    assert down["score"] == -1
