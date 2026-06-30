# NetCoin public sites

Each folder under `sites/` is a standalone public website. The active deployment maps each subdomain to the matching folder.

Core sites:
- `wallet`: hosted non-custodial wallet.
- `explorer`: chain lookup and network health.
- `pay`: customer checkout.
- `merchant`: business tools.
- `faucet`: public-testnet faucet.
- `community`: discussion, improvements, bounties, rewards.
- `markets`: prediction-market demos.
- `nodes`: public seed and node visibility.
- `status`: service and network health.
- `security`: public trust center.
- `governance`: NetCoin Improvement Proposal workflow.
- `treasury`: transparent fund records if a treasury exists.
- `learn`: beginner education.
- `download`: install and local run guide.
- `docs`: docs landing page.
- `api`: developer API reference.

Never put private keys, seed phrases, admin tokens, server IPs, or SSH details in public site files.


## Shared public instructions

Every public site loads the shared `site-shell.js` and `site-shell.css` pair. The shell now adds a collapsed **Run NetCoin from GitHub** panel to every site with:

- GitHub clone and editable install commands.
- Local wallet command using `http://18.220.89.128/api`.
- Miner command using `http://18.220.89.128/api`.
- Note that `https://api.netcoin.online/api` is the preferred API domain when a user network allows it.
- Note that legacy, p2sh-segwit, segwit, and taproot are different receiving addresses controlled by the same wallet.

When deploying static sites, copy every directory under `sites/` to `/opt/netcoin/sites/` so all sites get the same instruction panel.
