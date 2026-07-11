# Phase 0.5 Product Coherence and No-Dead-End Workflows

Phase 0.5 turns the Phase 0 product rules into an operating contract: every
NetCoin page must belong to a product lens, a user job, a workflow, a trust
signal, and a next action.

The goal is not to add features. The goal is to prevent NetCoin from drifting
back into disconnected mini-apps.

## Product lenses

NetCoin now has three product lenses:

1. **NetCoin** — public users: Wallet, Explorer, Markets.
2. **NetCoin Network** — advanced users and operators: Network, Nodes, Status,
   Operator, Exchange.
3. **NetCoin Studio** — developers, auditors, and release operators: Docs, API,
   Downloads, Architecture, Feature Catalog, Release Verification.

These are lenses into one ecosystem, not separate products.

## User jobs

Every surface must support one of five jobs:

- Manage money
- Understand the blockchain
- Participate
- Operate infrastructure
- Build

Anything that cannot be mapped to one of those jobs should not become a page.

## No-dead-end rule

Every page must answer:

- Where am I?
- What job am I doing?
- What is the one primary action?
- Can I trust the current state?
- What happens next?

A page fails Phase 0.5 if its empty, error, or success state leaves the user
with no clear next action.

## Required surface contract

Every major surface must define:

- surface
- product lens
- owner job
- primary action
- trust signal
- next step
- advanced destination

This contract is stored in:

```bash
architecture/product-coherence.json
```

## Validation

Run:

```bash
python tools/check_product_coherence.py
make v0384-check
```

The checker verifies product lenses, jobs, surface ownership, workflow evidence,
no-dead-end rules, and page exit requirements.

## Design helpers

The shared design system now includes classes for lens shells, owner-job chips,
primary-action rows, next-step panels, and no-dead-end sections:

- `.nc-lens-shell`
- `.nc-lens-header`
- `.nc-owner-job`
- `.nc-primary-action-row`
- `.nc-next-step`
- `.nc-no-dead-end`

Use these when converting existing screens so the UI becomes calmer and more
coherent without creating new product surfaces.
