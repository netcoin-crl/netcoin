# NetCoin independent site split

The public NetCoin websites are separated by purpose.

- wallet.netcoin.online: wallet, contacts, backups, labels, watch-only, coin control, PSBT/export flows.
- explorer.netcoin.online: chain lookup only plus Home network summary. No merchant/admin/community/wallet-tools tabs.
- pay.netcoin.online: customer checkout and invoice lookup.
- merchant.netcoin.online: invoices, POS, names/profiles, webhooks, API keys, exports, refunds, and business agreements.
- faucet.netcoin.online: testnet coin requests and faucet health.
- community.netcoin.online: community campaigns, bounties, leaderboards, gifts, and social links.
- markets.netcoin.online: Phase 7 prediction-market demos only.
- docs.netcoin.online: documentation.
- api.netcoin.online: API docs and examples.

The active EC2 deployment should serve this folder from `/opt/netcoin/sites` with `/etc/nginx/sites-enabled/netcoin.conf`.
