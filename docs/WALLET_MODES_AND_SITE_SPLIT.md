# Wallet modes and Netcoin site split

This refactor turns the browser wallet from a long feature dump into a mode-driven tabbed app, and turns the explorer bundle into separate static entry pages for different audiences.

## Wallet modes

The browser wallet now stores a UI mode in `localStorage` under `ncw.walletMode.v1`.

Modes:

- **Simple**: normal users. Shows Overview, Send, Receive, Activity, Contacts, and Settings.
- **Business**: merchants/creators/clubs. Adds Payments and Reports.
- **Advanced**: power users. Adds Watch-only, Escrow, and Advanced tools such as coin control, PSBT, descriptors, and raw transaction workflows.
- **Developer**: local/testnet developers. Adds Contracts and Developer links for app-layer experiments, API docs, and admin/debug surfaces.

The selected mode controls visibility only. It does not delete data and it does not disable backend features.

## Wallet tabs

The wallet page is organized into tabs:

- Overview: node status, address, balance, quick refresh/copy.
- Send: recipient, payment URI parsing, fee selection, contact picker, coin control, send review.
- Receive: receive address, payment URI, QR code, share/copy link.
- Activity: transaction history, labels, notes, receipts, categories.
- Contacts: contact import/export and encrypted contact backup.
- Payments: links to payment and merchant surfaces.
- Reports: statements, CSV/PDF export, balance alerts, spending limits, backup-required/savings-mode options.
- Watch-only: watched addresses and imported simple descriptors.
- Escrow: advanced link into escrow/contract tools.
- Advanced: descriptors, PSBT export, raw/offline-signing tools.
- Contracts: developer-mode Phase 7 contract tools link.
- Developer: API/admin/debug links.
- Settings: wallet mode selector and mode explanations.

## Separate explorer entry pages

The original explorer bundle is still reused, but different entry pages now present focused site shells:

- `index.html`: public explorer only: blocks, transactions, addresses, mempool, fees, peers, mining, and public labels.
- `pay.html`: checkout, receipts, tips, donations, public names/profiles.
- `merchant.html`: merchant dashboard, invoices, POS, refunds, API keys, webhooks, exports.
- `faucet.html`: testnet faucet status and claims.
- `status.html`: service/network health.
- `community.html`: bounties, rewards, gifts, leaderboards, names/profiles.
- `markets.html`: Phase 7 demos such as recurring agreements, escrow, polls, contract templates, and prediction markets.
- `docs.html`: documentation/API entry point.
- `api.html`: API and SDK entry point.
- `admin.html`: operator dashboard, already separate and protected by admin token when enabled.

## Suggested subdomains

For deployment, map these entry pages to separate subdomains or static paths:

- `wallet.netcoin.online` -> `webwallet-browser/public/wallet.html`
- `explorer.netcoin.online` -> `webexplorer/public/index.html`
- `pay.netcoin.online` -> `webexplorer/public/pay.html`
- `merchant.netcoin.online` -> `webexplorer/public/merchant.html`
- `admin.netcoin.online` -> `webexplorer/public/admin.html`
- `faucet.netcoin.online` -> `webexplorer/public/faucet.html`
- `status.netcoin.online` -> `webexplorer/public/status.html`
- `community.netcoin.online` -> `webexplorer/public/community.html`
- `markets.netcoin.online` -> `webexplorer/public/markets.html`
- `docs.netcoin.online` -> `webexplorer/public/docs.html`
- `api.netcoin.online` -> `webexplorer/public/api.html`

Prediction markets should remain testnet/demo-only until legal and security review are complete.
