# M4 · Mainnet-ready source package

M4 is the point where NetCoin can be evaluated for a real mainnet launch. This
file is intentionally conservative: it separates source readiness from
operational evidence.

## Safe claim

`M4 source-complete release candidate` means the repo contains the public docs,
checks, manifests, and runbooks needed to prepare for mainnet review.

## Unsafe claim

Do **not** claim `mainnet ready`, `audit complete`, `legal complete`, `genesis
approved`, or `safe to launch` until the strict evidence gate passes.

## Non-negotiable blockers

- External audit report complete and critical/high findings closed or explicitly waived.
- Formal protocol specification frozen and reviewed.
- Consensus/version-bits/checkpoint/genesis changes approved through a NIP and explicit same-session signoff.
- Genesis distribution approved publicly before launch.
- Legal posture reviewed by crypto-literate counsel.
- Cold-storage custody ceremony completed with multisig signers.
- Performance benchmark evidence meets targets.
- M1, M2, and M3 strict evidence gates are complete.

## Current source package behavior

This package adds M4 readiness gates and documentation. It does not modify
consensus code, emission schedule, address format, genesis economics, or live
seed deployment. Those changes are intentionally blocked until governance and
signoff evidence exists.
