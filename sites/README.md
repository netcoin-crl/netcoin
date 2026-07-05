# NetCoin public sites

Each folder under `sites/` is a standalone public website. The active deployment maps each subdomain to the matching folder.

Core sites:
- `www`: Start hub that merges the simple/community/pay basics into one beginner path.
- `wallet`: hosted non-custodial wallet.
- `explorer`: chain lookup and network health.
- `pay`: focused payment request/invoice/receipt tools; basics link back to Start.
- `merchant`: business tools.
- `faucet`: public-testnet faucet.
- `community`: deeper discussion, improvements, bounties, rewards; basics link back to Start.
- `markets`: prediction-market demos.
- `nodes`: public seed and node visibility.
- `status`: companion status page; active status lives in Network.
- `security`: public trust center.
- `governance`: NetCoin Improvement Proposal workflow.
- `treasury`: companion treasury page; active transparency lives in Governance.
- `learn`: beginner education.
- `download`: direct install and local run guide; also included in Learn.
- `docs`: audience map that points beginners to Learn and builders to Developers/API.
- `api`: developer API reference.

Never put private keys, seed phrases, admin tokens, server IPs, or SSH details in public site files.


## Shared public instructions

Every public site loads the shared `site-shell.js` and `site-shell.css` pair. The shell now adds a collapsed **Run NetCoin from GitHub** panel to every site with:

- GitHub clone and editable install commands.
- Local wallet command using `http://18.220.89.128/api`.
- Miner command using `http://18.220.89.128/api` with `--blocks 0` for mine-until-stopped.
- Read-only public seed check: `python tools/check_public_network.py`.
- Note that `https://api.netcoin.online/api` is the preferred API domain when a user network allows it.
- Note that legacy, p2sh-segwit, segwit, and taproot are different receiving addresses controlled by the same wallet.

When deploying static sites, copy every directory under `sites/` to `/opt/netcoin/sites/` so all sites get the same instruction panel.
