# Phase 0.4 — Trust Layer and Interaction Standards

NetCoin already has enough product breadth. Phase 0.4 makes existing workflows feel safer, clearer, and more professional by defining one trust and interaction contract for wallet, explorer, markets, faucet, exchange, operator, and release verification surfaces.

This phase does not add a new product surface. It defines the rules every existing surface must follow.

## North star

Every screen should answer four questions:

1. What is happening?
2. Can I trust this state?
3. What happens next?
4. How do I recover if something fails?

## Canonical trust contract

Every trust-critical surface should expose these signals when relevant:

- freshness
- source
- verification
- risk
- next action

Examples:

- Wallet: updated 4 seconds ago, connected to node, wallet unlocked, backup verified.
- Explorer: active chain, confirmation count, data freshness, source node.
- Markets: market state, max loss, fee, settlement source, dispute state.
- Exchange: custody tier, approval status, daily limit usage, broadcast state.
- Release verification: version, signature, manifest, provenance, SBOM status.

## Canonical status language

Use only these global status terms:

- Healthy
- Warning
- Offline
- Maintenance

Other words such as online, live, ready, running, synced, okay, and operational may appear in descriptive copy, but they should not become competing badge states.

## Action lifecycle

Every workflow should fit this sequence:

```text
start -> input -> review -> confirm -> execute -> success -> verify -> recover
```

Not every workflow needs every visible step, but irreversible workflows must include review before execution.

## Irreversible actions

The following actions require review before execution:

- sending funds
- submitting a market order
- withdrawing custody funds
- signing offline/hardware transactions
- exporting sensitive wallet material
- changing faucet/operator/custody safety limits
- marking a release as trusted

## Error language

Every error must include:

- what happened
- why it matters
- reassurance, when true
- primary recovery action
- secondary recovery action

Example:

```text
Unable to reach node.
Balances and confirmations may be stale until the node reconnects.
Your wallet keys are local and were not changed.
Retry connection · View network status
```

## Confirmation language

Confirmations should be specific:

- Transaction sent.
- Contact saved.
- Backup created.
- Order placed.
- Faucet claim sent.
- Release verified.

Avoid vague confirmations such as "Done" or "Success" without context.

## Workflow reassurance

Every workflow should end by reassuring the user about what happened and what did not happen.

Wallet send success:

```text
Transaction sent. Explorer updated. Balance refreshed.
```

Wallet send failure:

```text
Nothing was broadcast. Your wallet keys are safe.
```

Market order failure:

```text
No order was placed and no funds were committed.
```

Release verification failure:

```text
Do not run this artifact. Download again or inspect verification details.
```

## Local-only user data

Contact labels, transaction notes, and local address labels must be described as local-only. The UI should never imply that labels are on-chain or public unless the user explicitly publishes something.

## Validation command

```bash
python tools/check_trust_interaction.py
```

This check is part of the v0.38.3 Phase 0 gate.
