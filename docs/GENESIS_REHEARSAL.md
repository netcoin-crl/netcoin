# Regtest/Testnet Genesis Rehearsal

P4 adds an offline genesis generator for rehearsal networks only. It is not a
mainnet launch tool and it does not modify `netcoin/params.py`, the current
testnet genesis constants, chain validation, or any committed consensus vector.

Run a regtest rehearsal:

```bash
python tools/generate_genesis.py --network regtest \
  --manifest config/genesis_rehearsal_manifest.example.json \
  --out reports/genesis_rehearsal_report.json
```

Run a testnet-rehearsal ceremony dry run by providing a manifest whose `network`
field is `testnet-rehearsal`:

```bash
python tools/generate_genesis.py --network testnet-rehearsal \
  --manifest path/to/testnet-rehearsal-manifest.json \
  --out reports/genesis_rehearsal_report.json
```

Safety boundaries:

- `mainnet`, `main`, and `mainnet-dry-run` are hard-refused.
- Only `regtest` and `testnet-rehearsal` are accepted.
- The manifest must commit to height 0, the zero previous hash, explicit compact
  difficulty bits, timestamp, coinbase message, and deterministic outputs.
- The report includes the manifest hash, mined block hash, raw header/block hex,
  and flags showing the result is not consensus-integrated.
- A real public launch still requires a NIP, final allocation review, independent
  operator reproduction, and explicit same-session signoff.

Ceremony rehearsal checklist:

1. Freeze the manifest and publish its SHA256 before mining.
2. Have at least two operators run the command from clean source archives.
3. Compare `manifest_hash`, `block_hash`, `merkle_root`, `timestamp`, `bits`, and
   `nonce` byte-for-byte.
4. Store the JSON reports as evidence.
5. Halt if any operator sees a different hash; do not patch around a mismatch.
