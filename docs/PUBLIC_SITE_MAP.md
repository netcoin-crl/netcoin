# NetCoin Public Site Map

This document lists the public NetCoin sites and the intended purpose of each one. It does not contain private server details, IP addresses, SSH usernames, or deployment secrets.

## Public sites

| Site | Purpose |
|---|---|
| `wallet.netcoin.online` | Non-custodial browser wallet. |
| `explorer.netcoin.online` | Chain lookup, latest blocks/transactions, and network health summary. |
| `pay.netcoin.online` | Customer checkout and payment request pages. |
| `merchant.netcoin.online` | Merchant invoices, POS, refunds, API keys, webhooks, and reports. |
| `faucet.netcoin.online` | Public-testnet faucet. |
| `community.netcoin.online` | Public discussion, improvement ideas, bounties, and leaderboards. |
| `markets.netcoin.online` | Testnet-only prediction-market demos and Phase 7 experiments. |
| `nodes.netcoin.online` | Public node/seed dashboard and public seed onboarding. |
| `status.netcoin.online` | Service and network health status. |
| `security.netcoin.online` | Security trust center, responsible disclosure, and audit-readiness checklist. |
| `learn.netcoin.online` | Beginner education about wallets, nodes, seeds, mining, and safety. |
| `download.netcoin.online` | Public install/run instructions for macOS, Windows, and Linux. |
| `governance.netcoin.online` | NetCoin Improvement Proposal style idea board and voting. |
| `treasury.netcoin.online` | Read-only treasury transparency page when addresses are configured. |
| `docs.netcoin.online` | Public documentation hub. |
| `api.netcoin.online` | Developer API reference. |

## Generic Nginx map entries

Operators who host all public sites on one Nginx server can route by hostname using a map like this:

```nginx
map $host $netcoin_site_root {
    default                  /opt/netcoin/sites/explorer;
    wallet.netcoin.online    /opt/netcoin/sites/wallet;
    explorer.netcoin.online  /opt/netcoin/sites/explorer;
    pay.netcoin.online       /opt/netcoin/sites/pay;
    merchant.netcoin.online  /opt/netcoin/sites/merchant;
    faucet.netcoin.online    /opt/netcoin/sites/faucet;
    community.netcoin.online /opt/netcoin/sites/community;
    markets.netcoin.online   /opt/netcoin/sites/markets;
    nodes.netcoin.online     /opt/netcoin/sites/nodes;
    status.netcoin.online    /opt/netcoin/sites/status;
    security.netcoin.online  /opt/netcoin/sites/security;
    learn.netcoin.online     /opt/netcoin/sites/learn;
    download.netcoin.online  /opt/netcoin/sites/download;
    governance.netcoin.online /opt/netcoin/sites/governance;
    treasury.netcoin.online  /opt/netcoin/sites/treasury;
    docs.netcoin.online      /opt/netcoin/sites/docs;
    api.netcoin.online       /opt/netcoin/sites/api;
}
```

Keep any operator-only/admin site separate and protected. Do not expose admin tools publicly without authentication, IP allowlisting, and audit logging.
