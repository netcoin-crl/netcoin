# NetCoin Professional Site Roadmap

This roadmap tracks the professional public information architecture and trust upgrades.

## Site grouping

- Learn includes Download and install instructions.
- Governance includes Treasury transparency and NIP-style proposals.
- Network includes Nodes, Status, public seeds, mining, versions, and health checks.
- Developers includes API docs, SDKs, webhooks, examples, and local dev notes.
- Security remains a standalone trust center.
- Markets are labeled Labs and stay isolated from Simple mode.

## Site-wide modes

- Simple: Wallet, Pay, Explorer, Faucet, Learn, Community.
- Merchant: Pay, Merchant, Reports, API, Security.
- Developer: Developers, API, Explorer, Download, Security.
- Node Operator: Network, Explorer, Learn, Security, Governance.
- Community: Community, Ideas, Governance, Roadmap.
- Labs: Markets/Labs, Polls, Experimental contracts, API, Security.

## Security hardening priorities

- Rate-limit public write endpoints.
- Add request size limits and stricter input validation.
- Use HMAC for webhooks.
- Keep admin/operator tools private and audited.
- Use security headers at Nginx.
- Use passkeys/WebAuthn for merchant/community/admin accounts later.
- Keep wallet keys non-custodial.

## UX priorities

- Setup wizard for wallet.
- Merchant onboarding wizard.
- Universal search across docs, explorer, invoices, and proposals.
- Better empty/error states.
- Public Network, Security, Developers, Governance, and Learn hubs.
