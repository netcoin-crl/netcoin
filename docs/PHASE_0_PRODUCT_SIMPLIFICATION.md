# Phase 0.3 Product Simplification and Progressive Disclosure

NetCoin has enough breadth. Phase 0.3 prevents the project from becoming a set of disconnected mini-apps by defining how pages, modes, workflows, and advanced controls should be simplified before new UI or product surfaces are added.

## Goal

A normal user should see the product in this order:

```text
Wallet -> Explorer -> Markets -> More
```

Everything else belongs under a job, a mode, and a workflow. Advanced tools are still available, but they should be hidden until they are relevant.

## Canonical files

```text
architecture/product-simplification.json
netcoin/product_simplification.py
tools/check_product_simplification.py
```

## Product modes

NetCoin has four modes:

```text
User
Trader
Operator
Developer
```

Modes do not create separate products. They prioritize existing surfaces and hide advanced surfaces until needed.

## Progressive disclosure levels

NetCoin uses five levels:

```text
Beginner
Intermediate
Advanced
Operator
Developer
```

This keeps simple flows calm while preserving power-user and operator depth.

## Page creation rule

A new page is allowed only when a panel, drawer, details section, modal, or existing workflow step is not enough. Every new page proposal must define:

```text
owner_job
primary_action
workflow
target_mode
panel_rejected_reason
trust_signal
empty_state
loading_state
error_state
```

## Approved complementary features

The only new near-term features approved by Phase 0.3 are features that reduce complexity, improve existing workflows, increase trust, or remove hard ceilings:

```text
release-readiness-scorecard
wallet-security-center
global-command-search
unified-notification-center
guided-testnet-onboarding
local-labels-notes
market-order-preview
custody-risk-dashboard
e2e-screenshot-dashboard
audit-bundle-generator
```

## Avoid for now

These should wait until after an audit-candidate release:

```text
NFTs
cross-chain-bridges
multi-chain-wallet
mobile-app-rewrite
smart-contract-platform-expansion
advanced-trading-bots
full-dao-governance
more-market-types
mainnet-launch-marketing-page
complex-exchange-products
```

## Validation

Run:

```bash
python tools/check_product_simplification.py
```

Or the full Phase 0.3 gate:

```bash
make v0382-check
```

## Success criteria

Phase 0.3 is successful when:

- top navigation remains Wallet, Explorer, Markets only;
- normal users can complete receive, send, faucet, and explorer search without seeing operator/developer controls;
- every secondary surface belongs to a job, mode, and workflow;
- advanced crypto/operator/developer controls are hidden behind settings, details, drawers, or mode selection;
- new UI proposals fail validation unless they improve a workflow, remove a ceiling, increase trust/safety/clarity, or reduce complexity.
