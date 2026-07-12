# NetCoin M1 Testnet User Journey

This is the public M1 path for a first-time tester. It is written for a stranger who has not read the codebase or prior handoff notes.

NetCoin is public testnet software. Testnet NET has no real-money value; testnet NET has no real-money value, the system has not completed an external audit, and no one should paste a seed phrase or private key into chat, email, support forms, or issue trackers.

## Goal

A tester should be able to complete this loop without a manual step from the operator:

1. Open the wallet.
2. Create a new browser wallet.
3. Back up the recovery phrase offline.
4. Copy a receive address.
5. Claim faucet NET.
6. Confirm the incoming transaction in the wallet or explorer.
7. Send a small test payment back to another address.
8. Lock the wallet and verify it can be unlocked again.
9. Check the status page if anything looks stuck.
10. Report friction with exact page, action, expected result, and actual result.

## Start here

| Step | Site | What to do | Success signal |
| --- | --- | --- | --- |
| 1 | `https://wallet.netcoin.online` | Create a wallet and write down the recovery phrase offline. | Wallet opens to the dashboard with a visible testnet pill. |
| 2 | `https://wallet.netcoin.online` | Open Receive and copy a receive address. | The copied address is visible in truncated form with a copy action. |
| 3 | `https://faucet.netcoin.online` | Paste the receive address and complete the faucet challenge. | Faucet response says the request was accepted or explains the cooldown. |
| 4 | `https://explorer.netcoin.online` | Search the address or transaction ID. | Explorer shows the pending or confirmed transaction. |
| 5 | `https://wallet.netcoin.online` | Send a tiny amount to another test address. | Review screen appears before broadcast. |
| 6 | `https://status.netcoin.online` | Check height, mempool depth, peer count, and uptime if stuck. | Status page shows the public testnet snapshot. |

## Safety rules for testers

- Do not use a real Bitcoin seed phrase.
- Do not reuse a seed phrase from another wallet.
- Do not share screenshots containing a full seed phrase or private key.
- Treat all balances as play-money testnet balances.
- Use a fresh browser profile if you are testing restore, lock, and unlock flows repeatedly.
- If the faucet asks for a CAPTCHA, complete it in the browser; never send the CAPTCHA secret to anyone.

## What to record during the two-week M1 tester loop

For every issue, record:

- device and browser,
- URL,
- action taken,
- expected result,
- actual result,
- screenshot or console error if safe,
- whether retrying fixed it,
- whether the status page showed stale height, high mempool depth, low peers, or degraded uptime.


## Feedback intake

Use `docs/TESTNET_FEEDBACK_LOG.md` or `https://docs.netcoin.online/testnet-feedback.html` for every tester issue. Capture one friction point per row, redact secrets, assign severity, and re-test before closing. The feedback loop is part of the M1 exit gate: the project should not claim a stranger can complete the loop until P0/P1 reports are either fixed or explicitly documented.

Before expanding beyond the first small group, follow `docs/TESTNET_PILOT_PLAN.md` or `https://docs.netcoin.online/testnet-pilot.html` so the two-week tester loop has entry criteria, stop conditions, and a closeout report.

## Operator verification before inviting testers

Run the local source gate first:

```bash
make m1-rc-check
```

Then run the strict gate before public tester invites:

```bash
make m1-rc-strict
```

If the user's network blocks `netcoin.online`, verify the production host through seed1 with explicit Host headers:

```bash
curl -sk -H 'Host: wallet.netcoin.online' https://18.220.89.128/ | head -6
curl -sk -H 'Host: faucet.netcoin.online' https://18.220.89.128/ | head -6
curl -sk -H 'Host: explorer.netcoin.online' https://18.220.89.128/ | head -6
curl -sk -H 'Host: status.netcoin.online' https://18.220.89.128/ | head -6
```

Do not deploy to seed1, seed2, or seed3 from this document. Deployment remains an explicit operator action.

## What this does not claim

This journey does not claim mainnet readiness, real-money safety, independent-node decentralization, hardware wallet support, an external audit, or real CAPTCHA credentials in source control. Those remain later roadmap gates.
