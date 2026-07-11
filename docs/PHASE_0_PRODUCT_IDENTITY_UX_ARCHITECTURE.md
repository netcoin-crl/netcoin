# Phase 0: Product Identity and UX Architecture

Phase 0 is the anti-sprawl phase. NetCoin already has enough breadth: wallet, explorer, markets, faucet, community, exchange/custody, operator tools, architecture, API, docs and release/security tooling. The next improvement is not to add more surfaces. It is to make the existing surfaces feel like one coherent product.

## Product statement

NetCoin is a wallet-first public testnet cryptocurrency ecosystem: manage NET, understand the chain, participate in markets/community, operate infrastructure, and build on the protocol.

A first-time user should understand the product in under 30 seconds:

```text
Wallet -> Explorer -> Markets -> everything else
```

## Five user jobs

Every NetCoin screen belongs to exactly one job.

1. **Manage money**: Wallet, Pay, Merchant, contacts, labels, backups and signing.
2. **Understand the blockchain**: Explorer, Network, Nodes and Status.
3. **Participate**: Markets, Faucet, Community, Governance and Treasury.
4. **Operate infrastructure**: Operator, Exchange, Security, Release and diagnostics.
5. **Build**: Docs, API, SDKs, Architecture, Features and Learn.

Nothing should exist outside these jobs.

## Navigation hierarchy

The top navigation should stay intentionally small:

```text
Wallet | Explorer | Markets | More
```

`More` is grouped into:

```text
Network
Community
Developers
```

This does not remove capabilities. It reduces cognitive load by stopping every microsite from competing as a first-class product.

## User modes

Modes reorder and reveal context; they should not fragment the product.

- **User**: Wallet, Explorer, Markets, Faucet, Pay, Learn, Community.
- **Trader**: Markets, Wallet, Explorer, Portfolio, Orders, Disputes, Settlement.
- **Operator**: Operator, Status, Nodes, Exchange, Security, Release, Architecture.
- **Developer**: Docs, API, Architecture, Downloads, Features, Security.

## Page template

Every product page should use the same skeleton:

1. Breadcrumb/context
2. Title
3. Short plain-language description
4. One primary action
5. Summary cards
6. Main content
7. Secondary content
8. Advanced details

A page may be dense or sparse depending on its audience, but it should not invent a new structure unless there is a strong reason.

## Component rules

Allowed card types:

```text
primary, summary, status, warning, action, table, timeline, advanced
```

Allowed button types:

```text
primary, secondary, danger, ghost
```

Allowed status vocabulary:

```text
Healthy, Warning, Offline, Maintenance
```

Spacing scale:

```text
4, 8, 12, 16, 24, 32, 48
```

Typography scale:

```text
Display 32
Page 24
Section 20
Card 18
Body 15
Caption 13
```

## Product rules

- Every page has one visually dominant primary action.
- Advanced controls are hidden until they are relevant.
- Never create a page when a panel or drawer is enough.
- Never create a new component when an existing component can be reused.
- Every button should make clear what happens next.
- Every error explains what happened, why it matters and what to do next.
- Every irreversible flow has review, confirmation, result and recovery states.
- Every new feature must improve an existing workflow, remove a hard ceiling, increase trust/safety/clarity, or reduce complexity.

## Complementary features allowed after Phase 0

These are allowed because they improve current workflows instead of adding random scope:

- Release Readiness Scorecard
- Wallet Security Center
- Global command/search
- Unified notification center
- Guided testnet onboarding
- Local labels and notes
- Market order preview
- Custody risk dashboard
- E2E screenshot dashboard
- Audit bundle generator

## Features to avoid for now

Avoid until a later audit-candidate release:

- NFTs
- Cross-chain bridges
- Full DAO governance
- More market types
- Mobile app rewrite
- Advanced trading bots
- Multi-chain wallet
- Smart contract expansion
- Mainnet marketing page
- Complex exchange products

## Phase 0 acceptance criteria

- Primary navigation is limited to Wallet, Explorer and Markets plus grouped More.
- Every public surface is assigned to one of the five jobs.
- The design system defines a page template, card taxonomy, button taxonomy, status vocabulary, spacing scale and typography scale.
- The homepage explains Wallet, Explorer, Markets, Network, Community and Developers without listing every capability.
- A checker exists to prevent future information-architecture sprawl.
