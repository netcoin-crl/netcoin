# NetCoin Public Site Map

This document lists the public NetCoin sites and the intended purpose of each one. It does not contain private server details, IP addresses, SSH usernames, or deployment secrets.

## Public sites

| Site | Purpose |
|---|---|
| `netcoin.online` / `www.netcoin.online` | Start hub merging the simple wallet/pay/community basics plus download, faucet, explorer, and safety links. |
| `wallet.netcoin.online` | Non-custodial browser wallet. |
| `explorer.netcoin.online` | Chain lookup, latest blocks/transactions, and network health summary. |
| `pay.netcoin.online` | Focused customer checkout, payment request, invoice, and receipt pages; basic payment guidance links back to Start. |
| `merchant.netcoin.online` | Merchant invoices, POS, refunds, API keys, webhooks, and reports. |
| `faucet.netcoin.online` | Public-testnet faucet. |
| `community.netcoin.online` | Deeper public discussion, improvement ideas, bounties, and leaderboards; basic community guidance links back to Start. |
| `markets.netcoin.online` | Testnet-only prediction-market demos and Phase 7 experiments. |
| `nodes.netcoin.online` | Network hub: public seeds, status, peers, mining, and node-operator onboarding. |
| `status.netcoin.online` | Companion/legacy status link that points users to the Network hub. |
| `security.netcoin.online` | Security trust center, responsible disclosure, and audit-readiness checklist. |
| `learn.netcoin.online` | Beginner education about wallets, nodes, seeds, mining, and safety. |
| `download.netcoin.online` | Companion/legacy download link; install instructions live under Learn. |
| `governance.netcoin.online` | NetCoin Improvement Proposal style idea board and voting. |
| `treasury.netcoin.online` | Companion/legacy treasury link; treasury transparency lives under Governance. |
| `docs.netcoin.online` | Companion docs link; developer docs live under API/Developers and beginner docs live under Learn. |
| `api.netcoin.online` | Developers hub and machine API host under `/api/*`. |

## Generic Nginx map entries

Operators who host all public sites on one Nginx server can route by hostname using a map like this:

```nginx
map $host $netcoin_site_root {
    default                  /opt/netcoin/sites/www;
    netcoin.online           /opt/netcoin/sites/www;
    www.netcoin.online       /opt/netcoin/sites/www;
    wallet.netcoin.online    /opt/netcoin/sites/wallet;
    explorer.netcoin.online  /opt/netcoin/sites/explorer;
    pay.netcoin.online       /opt/netcoin/sites/pay;
    merchant.netcoin.online  /opt/netcoin/sites/merchant;
    faucet.netcoin.online    /opt/netcoin/sites/faucet;
    community.netcoin.online /opt/netcoin/sites/community;
    markets.netcoin.online   /opt/netcoin/sites/markets;
    nodes.netcoin.online     /opt/netcoin/sites/nodes; # Network hub
    status.netcoin.online    /opt/netcoin/sites/status;
    security.netcoin.online  /opt/netcoin/sites/security;
    learn.netcoin.online     /opt/netcoin/sites/learn;
    download.netcoin.online  /opt/netcoin/sites/download;
    governance.netcoin.online /opt/netcoin/sites/governance;
    treasury.netcoin.online  /opt/netcoin/sites/treasury;
    docs.netcoin.online      /opt/netcoin/sites/docs;
    api.netcoin.online       /opt/netcoin/sites/api; # Developer hub and API host
}
```

Keep any operator-only/admin site separate and protected. Do not expose admin tools publicly without authentication, IP allowlisting, and audit logging.
