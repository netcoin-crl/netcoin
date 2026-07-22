import pytest

from netcoin.apps import AppError, AppStore


def test_reply_nests_under_parent_comment(tmp_path):
    store = AppStore(tmp_path)
    post = store.create_community_post({"name": "Alice", "message": "How do I claim a username?"})
    top = store.create_community_comment(post["post_id"], {"name": "Bob", "message": "Use the Wallet tab."})
    assert top["parent_comment_id"] == ""

    reply = store.create_community_comment(
        post["post_id"], {"name": "Alice", "message": "Thanks!", "parent_comment_id": top["comment_id"]}
    )
    assert reply["parent_comment_id"] == top["comment_id"]

    listed = store.list_community_comments(post["post_id"])
    assert listed["count"] == 2
    ids = {c["comment_id"] for c in listed["comments"]}
    assert top["comment_id"] in ids and reply["comment_id"] in ids


def test_reply_to_nonexistent_or_mismatched_comment_is_rejected(tmp_path):
    store = AppStore(tmp_path)
    post_a = store.create_community_post({"name": "Alice", "message": "Post A"})
    post_b = store.create_community_post({"name": "Alice", "message": "Post B"})
    comment_on_a = store.create_community_comment(post_a["post_id"], {"name": "Bob", "message": "On A"})

    with pytest.raises(AppError, match="parent comment not found"):
        store.create_community_comment(post_a["post_id"], {"name": "Bob", "message": "fake parent", "parent_comment_id": "nope"})

    # A parent_comment_id from a DIFFERENT post must not be accepted either.
    with pytest.raises(AppError, match="parent comment not found"):
        store.create_community_comment(
            post_b["post_id"], {"name": "Bob", "message": "cross-post reply", "parent_comment_id": comment_on_a["comment_id"]}
        )
