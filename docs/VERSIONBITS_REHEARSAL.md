# Versionbits Rehearsal

P3 adds testnet/regtest-only versionbits rehearsal tooling. It does not wire
versionbits into mainnet consensus.

Example config:

```bash
config/versionbits_rehearsal.example.json
```

Run the localnet rehearsal:

```bash
NETCOIN_TESTNET_DEPLOYMENTS=1 python tools/run_versionbits_rehearsal.py \
  --out reports/versionbits_rehearsal_report.json
```

The tool starts a three-node localhost network, fetches real block templates,
sets the configured signaling bit in the template version, mines and submits
those blocks through the node API, waits for convergence, then evaluates the
accepted block header versions with `netcoin.versionbits`.

The report schemas are:

- `netcoin-versionbits-rehearsal-v1` for pure chain-version evaluation.
- `netcoin-versionbits-localnet-rehearsal-v1` for localnet evidence.

Safety boundaries:

- `mainnet` and `main` hard-fail in `VersionBitsRehearsalConfig`.
- Activation remains model-only and requires a future NIP before consensus use.
- The trivial rehearsal rule only applies inside the rehearsal evaluator: once
  ACTIVE, candidate block versions must keep signaling the rehearsal bit.
- The package does not modify `netcoin/params.py`, genesis, consensus vectors,
  or block validation.
