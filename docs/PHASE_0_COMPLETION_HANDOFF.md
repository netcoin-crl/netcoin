# Phase 0 Completion and Phase 1 Handoff

NetCoin Phase 0 is complete in v0.38.5. This release freezes the product
identity, design-system foundation, simplification policy, trust/interaction
standards, and no-dead-end workflow contract before the project moves back into
proof hardening.

Phase 0 does not claim mainnet readiness. It answers a narrower question:

> Can NetCoin keep improving without becoming a scattered collection of mini-apps?

The answer is now enforced by machine-checkable architecture files and release
gates.

## Locked product model

- Public product: **NetCoin**
- Primary surfaces: **Wallet**, **Explorer**, **Markets**
- Secondary grouping: **More** -> Network, Community, Developers
- Product lenses: **NetCoin**, **NetCoin Network**, **NetCoin Studio**
- User jobs: manage money, understand the blockchain, participate, operate
  infrastructure, and build
- Status vocabulary: Healthy, Warning, Offline, Maintenance
- Trust vocabulary: Fresh, Stale, Verified, Unverified, Risk

## Phase 0 artifacts

| Layer | Artifact | Checker |
| --- | --- | --- |
| Product identity | `architecture/product-ux-architecture.json` | `python tools/check_product_architecture.py` |
| Design system | `architecture/design-system.json` | `python tools/check_design_system.py` |
| Workflow architecture | `architecture/product-workflows.json` | `python tools/check_design_system.py` |
| Product simplification | `architecture/product-simplification.json` | `python tools/check_product_simplification.py` |
| Trust interaction | `architecture/trust-interaction.json` | `python tools/check_trust_interaction.py` |
| Product coherence | `architecture/product-coherence.json` | `python tools/check_product_coherence.py` |
| Phase 0 completion | `architecture/phase0-completion.json` | `python tools/check_phase0_complete.py` |

## Anti-sprawl rule

Every future feature must do at least one of these:

1. improve an existing workflow significantly,
2. remove a technical or UX ceiling,
3. increase trust, safety, or clarity,
4. reduce complexity.

If none of those are true, the feature should not be added.

## New page rule

Do not create a new top-level page until these alternatives fail:

1. add a panel to the existing page,
2. add a drawer,
3. add a settings section,
4. add a details view,
5. add a developer/operator advanced section.

A new page must have one owner job, one primary action, one trust signal, one
next step, and one advanced destination.

## Phase 1 handoff

The next phase is **Proof Hardening**. Its job is not to add broad product
surface area. Its job is to prove the current system.

Required evidence:

- full Python test-suite report,
- `cargo test --workspace` report,
- all Rust parity binary reports,
- `npm ci && npm run ci:api` report,
- real Playwright E2E report,
- accessibility report,
- release readiness scorecard.

Until those are green, NetCoin should not claim to be production ready, mainnet
ready, externally audited, real custody ready, or hardware-wallet ready.

## Completion command

```bash
make v0385-check
```

That gate runs every Phase 0 checker, the product/site surface checks, Python
compile checks, parity, and the Phase 0 test suite.
