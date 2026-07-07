# NetCoin Labs Market Integrity Policy

NetCoin prediction markets are demo, testnet, play-money, and private-development tools only. They must not be marketed as real-money event contracts without legal review.

## Controls

- Markets are restricted to `testnet_demo`, `play_money`, or `private_dev` modes.
- Restricted topic terms require operator override and legal acknowledgement.
- Orders use demo wallets and collateral reservations.
- Resolution requests are separated from final operator approval.
- Disputes can be recorded before final resolution.
- Surveillance reports flag wash-trade patterns, concentration, rapid price moves, stale pending resolution, and ledger anomalies.

## Operator Workflow

1. Review market question, source, close time, and warning labels.
2. Review surveillance report before allowing resolution.
3. Record evidence URL and resolution note.
4. Allow a dispute window when appropriate.
5. Resolve only after operator approval.
6. Preserve the audit trail.

## API Endpoints

- `GET /api/markets/surveillance`
- `GET /api/markets/<market_id>/surveillance`
- `POST /api/markets/<market_id>/dispute`
- `POST /api/markets/<market_id>/resolution-request`
- `POST /api/markets/<market_id>/resolve`
