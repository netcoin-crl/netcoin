import base64
from pathlib import Path

import pytest

from netcoin.apps import AppError, AppStore

TINY_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="
)
TINY_PNG_DATA_URI = "data:image/png;base64," + base64.b64encode(TINY_PNG).decode()


def test_post_with_valid_image_round_trips_through_feed(tmp_path: Path):
    store = AppStore(tmp_path / "chain")
    post = store.create_community_post({"name": "alice", "message": "hello", "image": TINY_PNG_DATA_URI})
    assert post["image"] == TINY_PNG_DATA_URI
    feed = store.community_feed()
    found = next(p for p in feed["posts"] if p["post_id"] == post["post_id"])
    assert found["image"] == TINY_PNG_DATA_URI


def test_comment_with_valid_image_round_trips_through_list(tmp_path: Path):
    store = AppStore(tmp_path / "chain")
    post = store.create_community_post({"name": "alice", "message": "hello"})
    comment = store.create_community_comment(
        post["post_id"], {"name": "bob", "message": "nice", "image": TINY_PNG_DATA_URI}
    )
    assert comment["image"] == TINY_PNG_DATA_URI
    listed = store.list_community_comments(post["post_id"])
    found = next(c for c in listed["comments"] if c["comment_id"] == comment["comment_id"])
    assert found["image"] == TINY_PNG_DATA_URI


def test_post_without_image_has_empty_image_field(tmp_path: Path):
    store = AppStore(tmp_path / "chain")
    post = store.create_community_post({"name": "alice", "message": "hello"})
    assert post["image"] == ""


def test_oversized_image_is_rejected(tmp_path: Path):
    store = AppStore(tmp_path / "chain")
    big_payload = base64.b64encode(b"0" * (301 * 1024)).decode()
    big_uri = "data:image/jpeg;base64," + big_payload
    with pytest.raises(AppError, match="exceeds"):
        store.create_community_post({"name": "alice", "message": "hello", "image": big_uri})


def test_oversized_comment_image_is_rejected(tmp_path: Path):
    store = AppStore(tmp_path / "chain")
    post = store.create_community_post({"name": "alice", "message": "hello"})
    big_payload = base64.b64encode(b"0" * (301 * 1024)).decode()
    big_uri = "data:image/jpeg;base64," + big_payload
    with pytest.raises(AppError, match="exceeds"):
        store.create_community_comment(post["post_id"], {"name": "bob", "message": "nice", "image": big_uri})


def test_non_image_data_uri_is_rejected(tmp_path: Path):
    store = AppStore(tmp_path / "chain")
    bad_uri = "data:text/plain;base64," + base64.b64encode(b"hello").decode()
    with pytest.raises(AppError, match="data URI image"):
        store.create_community_post({"name": "alice", "message": "hello", "image": bad_uri})


def test_garbage_image_string_is_rejected(tmp_path: Path):
    store = AppStore(tmp_path / "chain")
    with pytest.raises(AppError, match="data URI image"):
        store.create_community_post({"name": "alice", "message": "hello", "image": "not-an-image-at-all"})


def test_invalid_base64_payload_is_rejected(tmp_path: Path):
    store = AppStore(tmp_path / "chain")
    with pytest.raises(AppError, match="not valid base64"):
        store.create_community_post(
            {"name": "alice", "message": "hello", "image": "data:image/png;base64,not-valid-base64!!!"}
        )
