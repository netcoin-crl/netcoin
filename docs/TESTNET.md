# NetCoin Public Testnet Runbook

This guide launches NetCoin Testnet v0.1 style infrastructure from the v0.2 package. It is for testnet only. Coins have no real-money value.

## Ports

- Public peer/node port: `28444`
- Private JSON-RPC port: `28445`
- Private pool/template port: `28446`

Expose only SSH and `28444/tcp` on seed nodes. Keep RPC, wallet files, pool ports, and private keys off the public internet.

## 1. Prepare NetCoin on your Mac

```bash
cd ~/Downloads
unzip "netcoin-v2 (1).zip"
cd netcoin-v2
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -e . pytest
python -m netcoin --help
python -m pytest
```

Stay in the outer `netcoin-v2` folder, the one containing `pyproject.toml`.

## 2. Create or check your SSH key

```bash
ls ~/.ssh/id_ed25519.pub
ssh-keygen -t ed25519 -C "netcoin-seed"
cat ~/.ssh/id_ed25519.pub
```

Paste the public key into your VPS provider when creating servers.

## 3. Create seed1

Recommended starting server:

- Hostname: `netcoin-seed1`
- OS: Ubuntu 24.04 LTS
- Login: SSH key
- Size: small/basic test server

After the VPS is created, replace `SEED1_IP` in the commands below.

```bash
ssh root@SEED1_IP
adduser netcoin
usermod -aG sudo netcoin
mkdir -p /home/netcoin/.ssh
cp ~/.ssh/authorized_keys /home/netcoin/.ssh/authorized_keys
chown -R netcoin:netcoin /home/netcoin/.ssh
chmod 700 /home/netcoin/.ssh
chmod 600 /home/netcoin/.ssh/authorized_keys
exit
ssh netcoin@SEED1_IP
```

Install packages and open the node port:

```bash
sudo apt update
sudo apt install -y python3 python3-venv python3-pip unzip curl ufw
sudo ufw allow OpenSSH
sudo ufw allow 28444/tcp
sudo ufw enable
sudo ufw status
```

Upload and install from your Mac:

```bash
scp ~/Downloads/netcoin-v2.zip netcoin@SEED1_IP:~/
ssh netcoin@SEED1_IP
unzip -o netcoin-v2.zip
cd netcoin-v2
python3 -m venv .venv
. .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e .
python -m netcoin --help
```

Initialize seed1:

```bash
python -m netcoin --data /home/netcoin/.netcoin-testnet init
python -m netcoin --data /home/netcoin/.netcoin-testnet chain
```

Run it manually first:

```bash
python -m netcoin --data /home/netcoin/.netcoin-testnet node --host 0.0.0.0 --port 28444
```

From your Mac:

```bash
curl http://SEED1_IP:28444/info
```

If that returns JSON, seed1 is working.

## 4. Run seed1 under systemd

Stop the manual process with `Control+C`, then create the service:

```bash
sudo tee /etc/systemd/system/netcoin-node.service >/dev/null <<'EOF'
[Unit]
Description=NetCoin public seed node
After=network-online.target
Wants=network-online.target

[Service]
User=netcoin
WorkingDirectory=/home/netcoin/netcoin-v2
ExecStart=/home/netcoin/netcoin-v2/.venv/bin/python -m netcoin --data /home/netcoin/.netcoin-testnet node --host 0.0.0.0 --port 28444
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF
sudo systemctl daemon-reload
sudo systemctl enable --now netcoin-node
sudo systemctl status netcoin-node
sudo journalctl -u netcoin-node -f
```

Test again from your Mac:

```bash
curl http://SEED1_IP:28444/info
```

## 5. Add DNS and more seeds

Create DNS records:

```text
seed1.netcoin.online -> 18.220.89.128
seed2.netcoin.online -> 18.220.197.20
seed3.netcoin.online -> 18.226.74.252
```

Repeat setup for seed2 and seed3. Start seed2 with seed1 as a peer:

```ini
ExecStart=/home/netcoin/netcoin-v2/.venv/bin/python -m netcoin --data /home/netcoin/.netcoin-testnet node --host 0.0.0.0 --port 28444 --peer http://seed1.netcoin.online:28444
```

Start seed3 with seed1 and seed2:

```ini
ExecStart=/home/netcoin/netcoin-v2/.venv/bin/python -m netcoin --data /home/netcoin/.netcoin-testnet node --host 0.0.0.0 --port 28444 --peer http://seed1.netcoin.online:28444 --peer http://seed2.netcoin.online:28444
```

Then update seed1 to know seed2 and seed3:

```ini
ExecStart=/home/netcoin/netcoin-v2/.venv/bin/python -m netcoin --data /home/netcoin/.netcoin-testnet node --host 0.0.0.0 --port 28444 --peer http://seed2.netcoin.online:28444 --peer http://seed3.netcoin.online:28444
```

Reload after service edits:

```bash
sudo systemctl daemon-reload
sudo systemctl restart netcoin-node
```

Check all seeds:

```bash
curl http://seed1.netcoin.online:28444/info
curl http://seed2.netcoin.online:28444/info
curl http://seed3.netcoin.online:28444/info
curl http://seed1.netcoin.online:28444/peers
curl -X POST http://seed1.netcoin.online:28444/sync
```

## 6. Public user instructions

Users can run a local node that connects to the public seeds:

```bash
cd ~/Downloads
unzip netcoin-v2.zip
cd netcoin-v2
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -e .
python -m netcoin --data netcoin-testnet init
python -m netcoin --data netcoin-testnet node \
  --host 127.0.0.1 \
  --port 28444 \
  --peer http://seed1.netcoin.online:28444 \
  --peer http://seed2.netcoin.online:28444 \
  --peer http://seed3.netcoin.online:28444
```

Create a wallet:

```bash
python -m netcoin wallet-new --out my-wallet.json --mnemonic
python -m netcoin wallet-info --wallet my-wallet.json
chmod 600 my-wallet.json
```

Broadcast a transaction to a seed:

```bash
python -m netcoin --data netcoin-testnet send \
  --wallet my-wallet.json \
  --to RECIPIENT_ADDRESS \
  --amount 1 \
  --fee 0.01 \
  --broadcast-to http://seed1.netcoin.online:28444
```

## 7. Explorer

Serve the live Explorer SPA:

```bash
cd /home/netcoin/netcoin-v2
sudo apt install -y nginx
sudo mkdir -p /var/www/netcoin-explorer
sudo cp webexplorer/public/index.html /var/www/netcoin-explorer/index.html
sudo cp webexplorer/public/explorer-app.js /var/www/netcoin-explorer/explorer-app.js
```

Configure Nginx to serve the SPA and relay read-only Explorer API calls to the
local node:

```bash
sudo tee /etc/nginx/sites-available/netcoin-explorer >/dev/null <<'EOF'
server {
    listen 80;
    server_name explorer.YOURDOMAIN.com;

    root /var/www/netcoin-explorer;
    index index.html;

    location /api/ {
        proxy_pass http://127.0.0.1:28444/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
EOF
sudo ln -s /etc/nginx/sites-available/netcoin-explorer /etc/nginx/sites-enabled/netcoin-explorer
sudo nginx -t
sudo systemctl reload nginx
```

The old static generator is still useful for a local/private chain, but do not
run it as a cron job on the public Explorer host because it overwrites the live
UI:

```bash
python -m netcoin --data /home/netcoin/.netcoin-testnet explorer --out /home/netcoin/explorer-static
```

## 8. Faucet requirements

A faucet should:

- Accept a NetCoin address
- Rate-limit by IP, for example one request per day
- Send a small testnet-only amount
- Broadcast the transaction to a seed node
- Return the txid
- Keep only limited funds in its hot wallet

Do not store important wallet funds on the faucet server.

## 9. External miner workflow

The node can now act as the daemon, while an external miner process asks for work and submits solved blocks.

Create a miner wallet:

```bash
python -m netcoin wallet-new --out miner.json --mnemonic
```

Mine one block through a public seed:

```bash
python -m netcoin miner \
  --node http://seed1.netcoin.online:28444 \
  --wallet miner.json \
  --blocks 1
```

Save solved block JSON for audit/debugging:

```bash
python -m netcoin miner \
  --node http://seed1.netcoin.online:28444 \
  --wallet miner.json \
  --blocks 1 \
  --save-blocks solved-blocks
```

Submit a saved solved block:

```bash
python -m netcoin submitblock solved-blocks/block-HEIGHT-HASH.json \
  --node http://seed1.netcoin.online:28444
```

Useful daemon endpoints:

```bash
curl "http://seed1.netcoin.online:28444/blocktemplate?address=MINER_ADDRESS"
curl -X POST http://seed1.netcoin.online:28444/submitblock -d @solved-block.json
```

## 10. Monitoring checklist

Manual checks:

```bash
curl http://seed1.netcoin.online:28444/info
curl http://seed2.netcoin.online:28444/info
curl http://seed3.netcoin.online:28444/info
sudo systemctl status netcoin-node
sudo journalctl -u netcoin-node -n 100
df -h
free -h
uptime
```

Watch for:

- Node online status
- Block height
- Tip hash
- Peer count
- Disk space
- CPU and RAM pressure
- Repeated log errors

## 11. Launch order

1. Test the package on your Mac.
2. Bring seed1 online.
3. Confirm `curl http://SEED1_IP:28444/info` returns JSON.
4. Add DNS for seed1.
5. Bring seed2 and seed3 online.
6. Confirm `/info`, `/peers`, and `/sync` across all seeds.
7. Publish GitHub source, README, this runbook, and `SECURITY.md`.
8. Add explorer.
9. Add faucet.
10. Invite 2-3 private testers.
11. Fix bugs.
12. Publicly launch testnet.
13. Improve daemon/miner architecture before mainnet.
14. Get an external security and legal review before any mainnet or value claims.
