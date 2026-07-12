# NetCoin M1 Live Smoke Check

This is the operator-run live verification layer for the M1 strict testnet package.
It is deliberately separate from source readiness because it touches live public
endpoints and depends on seed/network state.

## What this check proves

The live smoke check verifies that the main public M1 surfaces are reachable
through the seed1 Host-header path that works around local ISP blocking:

- `wallet.netcoin.online` loads the public wallet surface.
- `faucet.netcoin.online` loads the faucet surface.
- `explorer.netcoin.online/mempool.html` loads the live mempool/fee page.
- `status.netcoin.online` loads the M1 network snapshot and incident card.
- `docs.netcoin.online/testnet-user-journey.html` loads the tester path.
- `api.netcoin.online/api/health` responds.

## What this check does not claim

This check does not claim seed deployment, systemd restart, real CAPTCHA
credentials, external audit completion, independent-node decentralization,
hardware wallet support, or mainnet readiness.

## Dry-run plan

Use the dry-run first. It writes the exact Host-header curl commands without
making a live request:

```bash
python3 tools/check_m1_live_smoke.py --out reports/m1_live_smoke_plan.json
```

## Live run

Run this only after you intentionally want to check the public seed1 path:

```bash
python3 tools/check_m1_live_smoke.py --run --out reports/m1_live_smoke_report.json
```

Equivalent one-off curl pattern:

```bash
curl -sk -H 'Host: status.netcoin.online' https://18.220.89.128/ | head -20
```

## Failure handling

If a page fails the live smoke check:

1. Do not deploy or restart services automatically.
2. Save `reports/m1_live_smoke_report.json`.
3. Capture the failing curl command from the report.
4. Compare against the source readiness gate:
   `make m1-rc-check`.
5. If the source gate passes but live smoke fails, treat it as an operator or
   deployment issue and follow `docs/INCIDENT_RESPONSE.md`.
