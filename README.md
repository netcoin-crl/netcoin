# NetCoin

NetCoin is an educational, from-scratch, Bitcoin-like cryptocurrency written in
Python. It runs on macOS, Linux, and Windows with Python 3.10+. Wallet-file
encryption uses the vetted `cryptography` package for AEAD; the rest stays small
and readable for learning.

NetCoin is **not Bitcoin**, does not connect to the Bitcoin network, and should
not be used as real money software. Public testnet NET has no real-money value.

> Current release: **v0.7.2**

## Start Here: Public Testnet

Most users should start by connecting to the public NetCoin testnet. The commands
below use the public AWS seed IPs because some home networks block the
`seed*.netcoin.online` hostnames.

Public nodes:

```text
seed1.netcoin.online:28444 -> http://18.220.89.128:28444
seed2.netcoin.online:28444 -> http://18.220.197.20:28444
seed3.netcoin.online:28444 -> http://18.226.74.252:28444
```

Public HTTPS apps:

```text
Wallet:    https://wallet.netcoin.online
Explorer:  https://explorer.netcoin.online
Pay:       https://pay.netcoin.online
Merchant:  https://merchant.netcoin.online
Faucet:    https://faucet.netcoin.online
Community: https://community.netcoin.online
Markets:   https://markets.netcoin.online
Docs:      https://docs.netcoin.online
API Docs:  https://api.netcoin.online
Status:    https://status.netcoin.online
```

NetCoin uses one EC2 server for these sites. DNS sends each subdomain to the
same EC2 public IP, and Nginx decides which site folder to show.

```text
wallet.netcoin.online      -> /opt/netcoin/sites/wallet
explorer.netcoin.online    -> /opt/netcoin/sites/explorer
pay.netcoin.online         -> /opt/netcoin/sites/pay
merchant.netcoin.online    -> /opt/netcoin/sites/merchant
faucet.netcoin.online      -> /opt/netcoin/sites/faucet
community.netcoin.online   -> /opt/netcoin/sites/community
markets.netcoin.online     -> /opt/netcoin/sites/markets
docs.netcoin.online        -> /opt/netcoin/sites/docs
api.netcoin.online         -> /opt/netcoin/sites/api
status.netcoin.online      -> /opt/netcoin/sites/status
```

The current production layout is intentionally separated so the Explorer does not
become bloated. Wallet tools live in the Wallet, business features live in
Merchant, community features live in Community, prediction-market demos live in
Markets, and API documentation lives in API Docs.

## Beginner Guide: How To Use These Commands

There are three places you may use a terminal:

1. **Your Mac / laptop terminal**: used to unzip the project, deploy files, and
   push to GitHub.
2. **The EC2 server terminal**: reached by running `ssh ubuntu@YOUR_EC2_IP`; used
   to test Nginx, Certbot, and services.
3. **A second terminal window**: sometimes needed when one window is already
   running a long-lived process like a node.

When a step says **open a new terminal**, on macOS open the Terminal app again or
press `Command + N`. Do not close a terminal that is running a server unless the
instructions say to stop it.

### Find your EC2 public IP address

Use one of these methods.

**AWS Console method**:

1. Open AWS Console.
2. Go to **EC2**.
3. Click **Instances**.
4. Click your NetCoin instance.
5. Copy **Public IPv4 address**.

**From inside the EC2 server**:

```bash
curl -4 https://checkip.amazonaws.com
```

**From your laptop, after DNS is set**:

```bash
dig wallet.netcoin.online +short
dig explorer.netcoin.online +short
```

For the current public NetCoin server, the IP is:

```text
18.220.89.128
```

If your EC2 instance is stopped and started later, a normal public IP can change.
Use an AWS Elastic IP if you want the DNS records to stay stable.

### SSH into the server

From your laptop terminal:

```bash
ssh ubuntu@18.220.89.128
```

If your server uses a `.pem` key, use:

```bash
ssh -i ~/Downloads/YOUR_KEY_NAME.pem ubuntu@18.220.89.128
```

If you see `Permission denied (publickey)`, you are either already inside the EC2
server or your laptop is not using the correct SSH key.

### Know where you are

If your prompt looks like this, you are on your laptop:

```text
yourname@MacBookPro ~ %
```

If your prompt looks like this, you are on EC2:

```text
ubuntu@ip-172-31-37-78:~$
```

To leave EC2 and go back to your laptop terminal:

```bash
exit
```

## Beginner Guide: Deploy the Website to EC2

Use these steps when you downloaded a NetCoin release zip and want to upload the
site files to the existing EC2 server.

### 1. Open a terminal on your laptop

Do **not** run this part inside EC2.

```bash
cd ~/Downloads
```

### 2. Unzip the project

Replace the zip name if your downloaded file has a newer name.

```bash
rm -rf netcoin-deploy
unzip netcoin-main-responsive-desktop-ec2.zip -d netcoin-deploy
cd netcoin-deploy/netcoin-main
chmod +x deploy/deploy_multisite_ec2.sh
```

### 3. Deploy the sites

```bash
./deploy/deploy_multisite_ec2.sh ubuntu@18.220.89.128
```

If you need a key file:

```bash
./deploy/deploy_multisite_ec2.sh ubuntu@18.220.89.128 ~/Downloads/YOUR_KEY_NAME.pem
```

The deploy script uploads only the site files by default. It does **not** overwrite
the live Certbot HTTPS Nginx config unless you deliberately set
`NETCOIN_DEPLOY_NGINX=1`.

### 4. Test from inside EC2

Open a new terminal or SSH into EC2:

```bash
ssh ubuntu@18.220.89.128
```

Then run:

```bash
curl -s -H "Host: wallet.netcoin.online"   http://127.0.0.1/ | grep -i "<title"
curl -s -H "Host: explorer.netcoin.online" http://127.0.0.1/ | grep -i "<title"
curl -s -H "Host: pay.netcoin.online"      http://127.0.0.1/ | grep -i "<title"
curl -s -H "Host: merchant.netcoin.online" http://127.0.0.1/ | grep -i "<title"
curl -s -H "Host: faucet.netcoin.online"   http://127.0.0.1/ | grep -i "<title"
curl -s -H "Host: community.netcoin.online" http://127.0.0.1/ | grep -i "<title"
curl -s -H "Host: markets.netcoin.online"  http://127.0.0.1/ | grep -i "<title"
curl -s -H "Host: docs.netcoin.online"     http://127.0.0.1/ | grep -i "<title"
curl -s -H "Host: api.netcoin.online"      http://127.0.0.1/ | grep -i "<title"
```

Expected titles:

```text
NetCoin Wallet
NetCoin Explorer
NetCoin Pay
NetCoin Merchant
NetCoin Faucet
NetCoin Community
NetCoin Markets
NetCoin Docs
NetCoin API
```

### 5. Test the API proxy

Still inside EC2:

```bash
curl -s -H "Host: pay.netcoin.online" https://127.0.0.1/api/latest -k | head
curl -s -H "Host: wallet.netcoin.online" https://127.0.0.1/api/fee-estimates -k | head
```

Expected output should start with NetCoin JSON, such as:

```text
"blocks"
"assumed_vbytes"
```

If you see `Final Trading Terminal`, Nginx is accidentally proxying to port
`3000`. NetCoin should use port `28444`, not port `3000`.

## Beginner Guide: DNS Records

If all sites are hosted on the same EC2 server, the DNS records should be A
records pointing to the same EC2 public IP.

In your DNS provider, create records like this:

```text
wallet      A      18.220.89.128
explorer    A      18.220.89.128
pay         A      18.220.89.128
merchant    A      18.220.89.128
faucet      A      18.220.89.128
community   A      18.220.89.128
markets     A      18.220.89.128
docs        A      18.220.89.128
api         A      18.220.89.128
status      A      18.220.89.128
```

Do not put `http://` or `https://` in DNS values. DNS values should be only the
IP address for A records.

Check DNS from your laptop:

```bash
for d in wallet explorer pay merchant faucet community markets docs api status; do
  echo "$d.netcoin.online -> $(dig +short $d.netcoin.online | tail -n1)"
done
```

Every line should show the EC2 IP.

## Beginner Guide: HTTPS With Certbot

Wallet encryption needs HTTPS because browser WebCrypto (`crypto.subtle`) only
works in secure browser contexts. If the wallet console says `importKey` is
undefined, you are probably using HTTP instead of HTTPS.

### 1. Make sure AWS allows HTTPS

In the EC2 Security Group, allow:

```text
HTTP   TCP 80   0.0.0.0/0
HTTPS  TCP 443  0.0.0.0/0
SSH    TCP 22   your IP, or restricted admin access
```

### 2. Install Certbot on EC2

SSH into EC2 first:

```bash
ssh ubuntu@18.220.89.128
```

Then run:

```bash
sudo cp /etc/nginx/sites-enabled/netcoin.conf /opt/netcoin/backups/nginx/netcoin.conf.before-ssl.$(date +%Y%m%d-%H%M%S)

sudo apt update
sudo apt install -y snapd
sudo snap install core
sudo snap refresh core
sudo apt remove -y certbot python3-certbot-nginx 2>/dev/null || true
sudo snap install --classic certbot
sudo ln -sf /snap/bin/certbot /usr/local/bin/certbot
```

### 3. Only include domains that point to this EC2 server

Do **not** include `netcoin.online` or `www.netcoin.online` unless those root
records also point to this EC2 IP.

Check first:

```bash
for d in wallet.netcoin.online explorer.netcoin.online pay.netcoin.online merchant.netcoin.online faucet.netcoin.online community.netcoin.online markets.netcoin.online docs.netcoin.online api.netcoin.online status.netcoin.online; do
  echo "$d -> $(dig +short $d | tail -n1)"
done
```

### 4. Request the certificate

```bash
sudo certbot --nginx \
  -d wallet.netcoin.online \
  -d explorer.netcoin.online \
  -d pay.netcoin.online \
  -d merchant.netcoin.online \
  -d faucet.netcoin.online \
  -d community.netcoin.online \
  -d markets.netcoin.online \
  -d docs.netcoin.online \
  -d api.netcoin.online \
  -d status.netcoin.online
```

If Certbot asks to expand an existing certificate, choose `E` for expand.
If it asks about redirecting HTTP to HTTPS, choose redirect.

### 5. Test HTTPS

```bash
sudo nginx -t
sudo systemctl reload nginx
sudo ss -ltnp | grep ':443'

curl -I https://wallet.netcoin.online
curl -I https://explorer.netcoin.online
curl -I https://merchant.netcoin.online
curl -I https://pay.netcoin.online
```

Expected:

```text
HTTP/1.1 200 OK
```

Test renewal:

```bash
sudo certbot renew --dry-run
```

## Beginner Guide: GitHub Update

After you test the site package locally and on EC2, update GitHub from your
laptop terminal.

```bash
cd ~/Downloads/netcoin-deploy/netcoin-main
git status
```

If this folder is not a git repository:

```bash
git init
git branch -M main
git remote add origin https://github.com/netcoin-crl/netcoin.git
```

Commit and push:

```bash
git add .
git commit -m "Update responsive HTTPS multisite NetCoin deployment"
git push -u origin main
```

If the remote already exists:

```bash
git remote set-url origin https://github.com/netcoin-crl/netcoin.git
git push -u origin main
```

If GitHub rejects the push because the remote has work you do not have locally,
do not use `--force` until you intentionally decide to replace the remote branch.

## 1. Install NetCoin Locally

Do this one time on each computer.

macOS / Linux:

```bash
git clone https://github.com/netcoin-crl/netcoin.git
cd netcoin
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e .
python -m netcoin --help
```

Windows PowerShell:

```powershell
git clone https://github.com/netcoin-crl/netcoin.git
cd netcoin
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e .
python -m netcoin --help
```

Run commands from the project folder, the one with `pyproject.toml`.

After install, if you close the terminal and open a new one, do not recreate the
venv. Just activate it again:

macOS / Linux:

```bash
cd netcoin
source .venv/bin/activate
```

Windows PowerShell:

```powershell
cd netcoin
.\.venv\Scripts\Activate.ps1
```

You can tell it worked when your prompt starts with `(.venv)`.

Quick health check:

macOS / Linux:

```bash
curl http://18.220.89.128:28444/info
curl http://18.220.197.20:28444/health
curl "http://18.226.74.252:28444/latest?n=5"
```

Windows PowerShell:

```powershell
Invoke-RestMethod http://18.220.89.128:28444/info
Invoke-RestMethod http://18.220.197.20:28444/health
Invoke-RestMethod "http://18.226.74.252:28444/latest?n=5"
```

## 2. Create A Wallet

```bash
python -m netcoin wallet-new --out miner.json --mnemonic --confirm-backup
python -m netcoin wallet-info --wallet miner.json
```

Write down the recovery phrase. The wallet file controls your testnet coins.

## 3. Mine On The Public Network

Open a new terminal if needed, then activate the venv first:

macOS / Linux:

```bash
cd netcoin
source .venv/bin/activate
```

Windows PowerShell:

```powershell
cd netcoin
.\.venv\Scripts\Activate.ps1
```

Mine one block:

```bash
python -m netcoin miner --node http://18.220.89.128:28444 --wallet miner.json --blocks 1
```

Mine continuously until you stop it with `Ctrl+C`:

macOS / Linux:

```bash
while true; do
  python -m netcoin miner --node http://18.220.197.20:28444 --wallet miner.json --blocks 1
done
```

Windows PowerShell:

```powershell
while ($true) {
  python -m netcoin miner --node http://18.220.197.20:28444 --wallet miner.json --blocks 1
}
```

Rotate seeds when mining so one seed does not take all the traffic:

```bash
python -m netcoin miner --node http://18.220.89.128:28444  --wallet miner.json --blocks 1
python -m netcoin miner --node http://18.220.197.20:28444  --wallet miner.json --blocks 1
python -m netcoin miner --node http://18.226.74.252:28444 --wallet miner.json --blocks 1
```

Mining rewards are coinbase rewards. They show as `immature` until 100 more
blocks are mined after them.

## 4. Check Balance

Use a terminal where `.venv` is active.

Check your wallet:

```bash
python -m netcoin balance --node http://18.220.89.128:28444 --wallet miner.json
```

Check any address:

```bash
python -m netcoin balance --node http://18.220.89.128:28444 --address <NETCOIN_ADDRESS>
```

Show your addresses:

```bash
python -m netcoin wallet-info --wallet miner.json
```

## 5. Run A Public Seed

Use this when other people should be able to connect to your node.

On a VPS or public server, first install NetCoin and activate `.venv`. Then run
the node command and leave that terminal open:

macOS / Linux:

```bash
python -m netcoin --data ~/.netcoin-testnet node \
  --host 0.0.0.0 \
  --port 28444 \
  --p2p-port 18447 \
  --sync-interval 60 \
  --rate-limit-per-min 240 \
  --advertise http://YOUR_PUBLIC_IP_OR_DOMAIN:28444 \
  --peer http://18.220.89.128:28444 \
  --peer http://18.220.197.20:28444 \
  --peer http://18.226.74.252:28444
```

Windows PowerShell:

```powershell
python -m netcoin --data ~/.netcoin-testnet node `
  --host 0.0.0.0 `
  --port 28444 `
  --p2p-port 18447 `
  --sync-interval 60 `
  --rate-limit-per-min 240 `
  --advertise http://YOUR_PUBLIC_IP_OR_DOMAIN:28444 `
  --peer http://18.220.89.128:28444 `
  --peer http://18.220.197.20:28444 `
  --peer http://18.226.74.252:28444
```

Open these inbound firewall/security-group ports:

| Port | Purpose | Public? |
| --- | --- | --- |
| `28444` | HTTP node API | yes |
| `18447` | experimental binary P2P | yes, optional |
| `28445` | JSON-RPC | no |
| `28446` | pool/template server | no |

Keep RPC and pool ports private. Do not expose wallet files, seed phrases, private
keys, server keys, or RPC tokens.

NetCoin ignores `X-Forwarded-For` by default so direct public clients cannot spoof
IP addresses to bypass rate limits. Only add `--trust-proxy-headers` when the node
is behind a reverse proxy you control.

No-port-forwarding options are in
[docs/PUBLIC_SEED_HOSTING.md](docs/PUBLIC_SEED_HOSTING.md).

## 6. Use The Browser Wallet

For the public hosted wallet, open:

```text
https://wallet.netcoin.online
```

For a local-only wallet on your own computer, open a terminal, activate `.venv`,
then run:

```bash
python -m netcoin web --node http://18.220.89.128:28444
```

Open this in your browser:

```text
http://127.0.0.1:8088/
```

The local web wallet is local. Your private keys stay on your computer. It only
sends signed transactions to the public node.

## 7. Run Your Own Public-Testnet Node

This runs a node on your computer, syncs with the public seeds, and lets you mine
through your own node instead of directly hitting the AWS seeds.

Terminal 1: start your node and leave it running:

```bash
python -m netcoin --data ~/.netcoin-testnet node --host 127.0.0.1 --port 28444 --sync-interval 60 --peer http://18.220.89.128:28444 --peer http://18.220.197.20:28444 --peer http://18.226.74.252:28444
```

Terminal 2: activate `.venv`, then check your node:

macOS / Linux:

```bash
curl http://127.0.0.1:28444/info
```

Windows PowerShell:

```powershell
Invoke-RestMethod http://127.0.0.1:28444/info
```

Terminal 2: mine through your own node:

```bash
python -m netcoin miner --node http://127.0.0.1:28444 --wallet miner.json --blocks 1
```

You can also use the built-in seed list:

```bash
python -m netcoin --data ~/.netcoin-testnet node --host 127.0.0.1 --port 28444 --sync-interval 60 --seeds
```

If your network blocks `seed*.netcoin.online`, use the raw-IP `--peer` command
above.

## 8. Send Coins

Use the hosted wallet or the local browser wallet for the simplest public-network
send flow.

Hosted wallet:

```text
https://wallet.netcoin.online
```

Local browser wallet:

```bash
python -m netcoin web --node http://18.220.89.128:28444
```

Then open:

```text
http://127.0.0.1:8088/
```

For local/private CLI practice, see the next section.

## What Is Implemented

Hosted product sites:

- Responsive HTTPS app ecosystem for phone, tablet, laptop, and desktop.
- Independent site folders under `/opt/netcoin/sites` so the Explorer is not
  bloated with unrelated tools.
- Shared navigation across Wallet, Explorer, Pay, Merchant, Faucet, Community,
  Markets, Docs, API Docs, and Status.
- Wallet site for user wallet actions, contacts, backups/imports, wallet modes,
  and wallet tools.
- Explorer site focused on chain lookup, latest blocks, latest transactions, and
  network-health summary.
- Pay site for customer checkout, payment requests, invoices, and receipts.
- Merchant site for business tools: invoices, POS, names/profiles, API keys,
  webhooks, exports, refunds, agreements, escrow-style flows, and merchant
  reports.
- Faucet site for testnet coin requests and faucet status.
- Community site for community links, campaigns, bounties, gifts, and
  leaderboards.
- Markets site for Phase 7 prediction-market demos and market experiments.
- Docs site for user, miner, node, merchant, and operator guides.
- API Docs site for endpoint documentation, examples, authentication notes, and
  webhook references.
- Nginx host-based routing for many subdomains on one EC2 IP.
- HTTPS with Certbot / Let's Encrypt for public subdomains.
- API proxy from `/api/*` to the NetCoin node on `127.0.0.1:28444`.
- Faucet proxy routes to the local faucet service on `127.0.0.1:8081`.
- Clean deployment layout with active files in `/opt/netcoin/sites`, backups in
  `/opt/netcoin/backups`, and no NetCoin dependency on port `3000`.

Core chain:

- UTXO chain validation
- Real proof-of-work mining
- 2-minute target blocks with difficulty retargeting
- Testnet lone-miner rule so the chain can keep moving
- Merkle roots
- Coinbase rewards and 100-block coinbase maturity
- secp256k1 ECDSA signatures
- BIP340-style Schnorr signatures for Taproot-like key-path spends
- Legacy, P2SH-SegWit, SegWit-style, and Taproot-style addresses
- Educational Script engine
- P2PKH, P2SH, P2WPKH, P2WSH, and P2TR script templates
- Multisig helpers
- Timelock helpers
- Transaction locktime and sequence handling
- Opt-in RBF signaling
- Mempool policy limits
- Block weight limit
- Raw Bitcoin-style transaction and block hex export
- SegWit-style txid/wtxid split

Network:

- HTTP node API
- Experimental binary TCP P2P server/client
- Headers-first sync shape
- Compact-block summaries
- BIP158-style compact block filters
- Relay queue and peer inventory cache
- Cumulative-work fork choice
- Reorg, rollback, and mempool revalidation
- Orphan block candidate handling
- Public endpoint rate limiting
- API-backed explorer and public status endpoints

Wallet and tools:

- Encrypted wallet files
- Deterministic NetCoin seed phrases
- HD wallet derivation
- Watch-only wallet files
- Descriptor helpers
- PSBT-like signing flow
- Browser wallet and local web wallet
- Saved contacts shared between wallet and explorer tools
- Payment URI support
- QR/payment-link support in browser tools
- Backup/import/export flows for wallet-related data
- Signed messages
- JSON-RPC server
- Mining-pool template server
- Faucet hardening support
- Local multi-node soak/stress harness
- Deterministic fuzz smoke runner
- Reindex and crash-safe JSON persistence
- Optional SQLite backend
- Pruned mode

Still not something code alone can create:

- Real global hashpower
- A worldwide independent node network
- Exchange listings
- Real liquidity
- Hardware wallet vendor support
- A production security review
- A public user ecosystem

Those require people, infrastructure, review, miners, users, and time.
