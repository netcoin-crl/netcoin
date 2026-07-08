from pathlib import Path
import subprocess
import sys

from netcoin.apps import AppStore
from netcoin.feature_catalog import feature_catalog, top_impact_fixes


def test_feature_catalog_is_comprehensive_and_has_top_fixes():
    catalog = feature_catalog()
    assert catalog["schema"] == "netcoin-feature-catalog-v1"
    assert catalog["summary"]["feature_count"] >= 50
    assert catalog["summary"]["average_rating"] >= 6
    groups = catalog["groups"]
    for required in ["Core chain", "Wallet", "Sites", "Markets", "Exchange", "Node/API"]:
        assert required in groups
        assert groups[required]
    fixes = top_impact_fixes()
    assert len(fixes) == 10
    assert fixes[0]["area"] == "Community"


def test_community_votes_comments_feed_and_moderation(tmp_path):
    store = AppStore(tmp_path)
    post = store.create_community_post({"name": "Ada", "category": "wallet", "message": "How do I recover a wallet?"})
    pid = post["post_id"]
    voted = store.vote_community_post(pid, {"direction": "up", "voter": "alice"})
    assert voted["score"] == 1
    voted_again = store.vote_community_post(pid, {"direction": "up", "voter": "alice"})
    assert voted_again["score"] == 1
    flipped = store.vote_community_post(pid, {"direction": "down", "voter": "alice"})
    assert flipped["score"] == -1
    comment = store.create_community_comment(pid, {"name": "Bob", "message": "Use the recovery tab."})
    assert comment["post_id"] == pid
    comments = store.list_community_comments(pid)
    assert comments["count"] == 1
    hot = store.list_community_posts(sort="hot")
    assert hot["posts"][0]["comment_count"] == 1
    report = store.create_community_report({"post_id": pid, "reason": "test report"})
    queue = store.community_moderation_queue()
    assert queue["open_count"] == 1
    action = store.moderate_community_item({"target": pid, "action": "hide"})
    assert action["action"] == "hide"
    assert report["report_id"].startswith("report_")


def test_leaderboards_return_readable_summary(tmp_path):
    store = AppStore(tmp_path)
    data = store.load()
    data["leaderboard_events"].append({"type": "community_reward", "address": "nctest1", "amount_sats": 5000})
    store.save(data)

    class TxOut:
        address = "miner-address"
        amount = 10000

    class Tx:
        outputs = [TxOut()]

    class Block:
        transactions = [Tx()]

    class Chain:
        chain = [Block()]

    result = store.leaderboards(Chain())
    assert result["summary"]["miner_count"] == 1
    assert result["top_miners"][0]["rank"] == 1
    assert result["top_earners"][0]["short_id"]


def test_site_feature_assets_and_audit_pass():
    root = Path(__file__).resolve().parents[1]
    assert (root / "sites" / "features" / "index.html").exists()
    assert "Feature map" in (root / "sites" / "features" / "index.html").read_text()
    shell = (root / "sites" / "shared" / "site-shell.js").read_text()
    assert "features.netcoin.online" in shell
    result = subprocess.run(
        [sys.executable, "tools/audit_site_ui.py"], cwd=root, text=True, capture_output=True, check=True
    )
    assert '"ok": true' in result.stdout
