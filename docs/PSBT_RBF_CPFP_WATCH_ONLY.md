# PSBT, RBF, CPFP, xpub, and Watch-Only Wallets

## PSBT flow

NetCoin's `netpsbt:` container supports the M2 workflow:

1. Create unsigned PSBT from selected UTXOs and outputs.
2. Export it for offline/hardware review.
3. Sign one or more inputs.
4. Combine partial signatures.
5. Finalize/extract a fully signed transaction.
6. Broadcast through the node/API after policy checks.

## RBF

RBF fee bumping is opt-in: a transaction signals replaceability through input
sequence values. `netcoin.fee_bump.create_rbf_replacement` preserves the same
inputs and recipient outputs, reduces the change output, signs again, and lets
mempool policy enforce replacement and incremental relay-fee rules.

## CPFP

CPFP creates a high-fee child transaction spending an unconfirmed parent output.
The existing mempool package path validates the parent+child package together.

## xpub and descriptors

HD xpub derivation and watch-only descriptors are supported for public-branch
monitoring. Hardened derivation from xpub is rejected. Descriptors do not carry
private-key material.
