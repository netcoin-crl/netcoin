# Phase 0.2: Design System and Workflow Architecture

Phase 0.2 continues the anti-sprawl work from Phase 0. It does not add a broad new product feature. It creates the rules every future NetCoin UI and workflow must follow so Wallet, Explorer, Markets, Faucet, Exchange, Operator, Docs and Release tools feel like one product.

## Purpose

NetCoin already has enough breadth. The next improvement is coherence:

```text
Wallet -> Explorer -> Markets -> grouped secondary tools
```

Every screen should help a user do one of five jobs:

1. Manage money.
2. Understand the blockchain.
3. Participate.
4. Operate infrastructure.
5. Build.

## Design-system files

Canonical files:

```text
architecture/design-system.json
architecture/product-workflows.json
sites/shared/design-system.css
netcoin/design_system.py
tools/check_design_system.py
```

These files define the product rules before more UI is changed.

## Page template

Every page should follow the same skeleton:

1. Breadcrumb or context.
2. Title.
3. Plain-language description.
4. One primary action.
5. Summary cards.
6. Main content.
7. Secondary content.
8. Advanced details.

The density may change by surface. Wallet should feel open. Explorer should be medium density. Markets and Exchange can be dense. Operator can be very dense. But the structure should remain recognizable.

## Component taxonomy

Allowed card types:

```text
primary, summary, status, warning, action, table, timeline, advanced
```

Allowed button variants:

```text
primary, secondary, danger, ghost
```

Allowed status words:

```text
Healthy, Warning, Offline, Maintenance
```

Avoid one-off terms like `Connected`, `Ready`, `Running`, `Live`, `Operational`, or `Green` unless they appear as explanatory copy under one of the canonical status words.

## Interaction rules

- Irreversible actions require review, confirmation, result and recovery states.
- Danger buttons require explicit destructive wording.
- Copy actions must confirm what was copied.
- Local-only labels and notes must be marked local-only.
- Advanced controls remain collapsed until relevant.
- Every error explains what happened, why it matters and what to do next.

## Canonical workflows

The workflow architecture defines ten high-value paths:

| Workflow | Surface | Primary action |
|---|---|---|
| Receive NET | Wallet | Receive NET |
| Send NET | Wallet | Review transaction |
| Search chain | Explorer | Search |
| Claim faucet NET | Faucet | Claim testnet NET |
| Trade market | Markets | Preview order |
| Withdraw custody funds | Exchange | Review withdrawal |
| Handle operator incident | Operator | Open runbook |
| Build integration | Docs/API | Start integration |
| Verify release | Download/Security | Verify release |
| Prepare audit | Security/Operator | Generate audit bundle |

Future UI work should improve these workflows before creating new ones.

## What this prevents

Phase 0.2 prevents:

- every page inventing a new card style,
- every area using different status wording,
- wallet, explorer and markets duplicating transaction components,
- advanced tools showing too early,
- new broad features being added before existing workflows feel professional.

## Acceptance criteria

A release passes Phase 0.2 when:

```bash
python tools/check_product_architecture.py
python tools/check_design_system.py
make v0381-check
```

all pass.

## Rule for future features

A future feature is allowed only if it does at least one of these:

1. Makes an existing workflow significantly better.
2. Removes a hard technical or UX ceiling.
3. Increases trust, safety or clarity.
4. Reduces complexity.

If it does not satisfy one of those conditions, it should wait.
