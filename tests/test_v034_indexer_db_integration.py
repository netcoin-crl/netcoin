from netcoin.indexer_db import IndexerDB, run_indexer_db_smoke, sample_indexer_blocks


def test_v034_indexer_db_smoke_passes():
    result = run_indexer_db_smoke()
    assert result["ok"] is True
    assert result["before_reorg"]["balance_sats"] == 4500
    assert result["after_reorg"]["balance_sats"] == 3800
    assert result["integrity"]["tip_height"] == 2


def test_v034_indexer_db_persists_address_and_market_events():
    db = IndexerDB()
    try:
        db.apply_blocks(sample_indexer_blocks()[:2])
        assert db.address_summary("net1alice") == {
            "received_sats": 5000,
            "sent_sats": 1200,
            "balance_sats": 3800,
            "event_count": 2,
        }
        assert db.market_summary("m1") == {
            "trade_volume_sats": 2000,
            "disputes": 0,
            "settlements": 1,
            "event_count": 2,
        }
    finally:
        db.close()


def test_v034_indexer_apply_block_is_idempotent_for_market_events():
    db = IndexerDB()
    try:
        block = {
            "height": 1,
            "hash": "h1",
            "prev_hash": "genesis",
            "txs": [],
            "market_events": [{"market_id": "m1", "type": "trade", "notional_sats": 100}],
        }
        db.apply_block(block)
        db.apply_block(block)
        assert db.market_summary("m1") == {
            "trade_volume_sats": 100,
            "disputes": 0,
            "settlements": 0,
            "event_count": 1,
        }
    finally:
        db.close()


def test_v034_indexer_same_height_fork_uses_only_active_block():
    db = IndexerDB()
    try:
        db.apply_block(
            {
                "height": 1,
                "hash": "h1",
                "prev_hash": "genesis",
                "txs": [
                    {
                        "txid": "tx1",
                        "address_events": [{"address": "net1alice", "direction": "receive", "amount_sats": 500}],
                    }
                ],
                "market_events": [{"market_id": "m1", "type": "trade", "notional_sats": 100}],
            }
        )
        db.apply_block(
            {
                "height": 1,
                "hash": "h1b",
                "prev_hash": "genesis",
                "txs": [
                    {
                        "txid": "tx1b",
                        "address_events": [{"address": "net1alice", "direction": "receive", "amount_sats": 600}],
                    }
                ],
                "market_events": [{"market_id": "m1", "type": "trade", "notional_sats": 300}],
            }
        )
        active = db.conn.execute("SELECT hash FROM blocks WHERE active = 1 ORDER BY height").fetchall()
        assert [row["hash"] for row in active] == ["h1b"]
        assert db.address_summary("net1alice") == {
            "received_sats": 600,
            "sent_sats": 0,
            "balance_sats": 600,
            "event_count": 1,
        }
        assert db.market_summary("m1") == {
            "trade_volume_sats": 300,
            "disputes": 0,
            "settlements": 0,
            "event_count": 1,
        }
    finally:
        db.close()
