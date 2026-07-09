# NetCoin v0.34 Real Indexer Database Integration

v0.34 adds a real SQLite-backed indexer integration boundary in `netcoin/indexer_db.py`.

The integration layer covers:

- active block persistence
- transaction persistence
- address event indexing
- market event indexing
- address summaries
- market summaries
- rollback on reorg
- deterministic integrity snapshots

Run:

```bash
python tools/check_indexer_db_integration.py
make v034-check
```

This does not replace the live Python indexer yet. It creates a concrete database contract that the future Rust indexer can match.
