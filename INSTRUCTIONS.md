# NetCoin Instructions

This guide is for public testnet users who want to run NetCoin from source, connect to the public seed nodes, create a local wallet, mine testnet blocks, check balances, run a local browser wallet, run a local node, or become a public seed.

NetCoin is an educational public-testnet project. It is not Bitcoin, it does not connect to the Bitcoin network, and testnet NET has no real-money value.

## Quick links

- Public wallet: <https://wallet.netcoin.online>
- Public explorer: <https://explorer.netcoin.online>
- Public faucet: <https://faucet.netcoin.online>
- API docs: <https://api.netcoin.online>
- Source code: <https://github.com/netcoin-crl/netcoin>
- Local wallet guide: [Run the local NetCoin wallet](#run-the-local-netcoin-wallet)
- Public seed guide: [Become a public seed](#become-a-public-seed)

## Public seed nodes

Use these node URLs when a command asks for a node:

```text
http://seed1.netcoin.online:28444
http://seed2.netcoin.online:28444
http://seed3.netcoin.online:28444
```

Start with `seed1`. If it is busy or unreachable, try `seed2` or `seed3`.

## Before you start

You will use a terminal window.

- macOS: open **Terminal**.
- Windows: open **PowerShell**, not Command Prompt.
- Linux: open your normal terminal app.

When a command starts a server or miner and keeps running, leave that terminal open. If the guide says **open a new terminal**, open a second terminal window and run the next commands there.

To stop a running node, web wallet, or mining loop, click that terminal and press:

```text
Ctrl+C
```

## macOS instructions

### 1. Open Terminal

Open the macOS **Terminal** app.

### 2. Check Python and Git

Copy and paste:

```bash
python3 --version
git --version
```

You need Python 3.10 or newer. If `git` is missing, macOS may ask you to install command line developer tools. Accept that prompt, wait for it to finish, then run the commands again.

### 3. Download NetCoin

```bash
cd ~
git clone https://github.com/netcoin-crl/netcoin.git
cd netcoin
```

If you already downloaded it before and want a fresh copy:

```bash
cd ~
rm -rf netcoin
git clone https://github.com/netcoin-crl/netcoin.git
cd netcoin
```

### 4. Create and activate a virtual environment

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e .
python -m netcoin --help
```

When the virtual environment is active, your terminal usually shows `(.venv)` near the prompt.

### 5. Create a local wallet

```bash
python -m netcoin wallet-new --out my-wallet.json --mnemonic --confirm-backup
python -m netcoin wallet-info --wallet my-wallet.json
```

Write down the recovery phrase. Do not share it. The wallet file and phrase control your testnet coins.

### 6. Mine one testnet block using a public seed

```bash
python -m netcoin miner --node http://seed1.netcoin.online:28444 --wallet my-wallet.json --blocks 1 --sync-after
```

If seed1 is unavailable, try:

```bash
python -m netcoin miner --node http://seed2.netcoin.online:28444 --wallet my-wallet.json --blocks 1 --sync-after
```

### 7. Mine continuously until you stop it

This keeps mining one block at a time. Stop with `Ctrl+C`.

```bash
while true; do
  python -m netcoin miner --node http://seed1.netcoin.online:28444 --wallet my-wallet.json --blocks 1 --sync-after
  sleep 2
done
```

### 8. Check your balance

```bash
python -m netcoin balance --node http://seed1.netcoin.online:28444 --wallet my-wallet.json
```

Mining rewards are coinbase rewards. They may show as immature until 100 more blocks are mined after them.

### 9. Run a local node connected to public seeds

Use this when you want your computer to run its own local node.

In the current Terminal, run:

```bash
python -m netcoin --data ~/.netcoin-testnet init
python -m netcoin --data ~/.netcoin-testnet node --host 127.0.0.1 --port 28444 --sync-interval 60 --peer http://seed1.netcoin.online:28444 --peer http://seed2.netcoin.online:28444 --peer http://seed3.netcoin.online:28444
```

Leave that terminal open.

### 10. Open a new Terminal and mine through your local node

Open a second Terminal window, then run:

```bash
cd ~/netcoin
source .venv/bin/activate
python -m netcoin miner --node http://127.0.0.1:28444 --wallet my-wallet.json --blocks 1 --sync-after
python -m netcoin balance --node http://127.0.0.1:28444 --wallet my-wallet.json
```

### 11. Run the local browser wallet

Open a new Terminal, then run:

```bash
cd ~/netcoin
source .venv/bin/activate
python -m netcoin web --node http://seed1.netcoin.online:28444 --faucet https://faucet.netcoin.online
```

Open this in your browser:

```text
http://127.0.0.1:8088/
```

The local browser wallet is for local testing only. Do not expose it publicly.

## Windows PowerShell instructions

### 1. Open PowerShell

Open **PowerShell** from the Start menu.

### 2. Check Python and Git

```powershell
py --version
git --version
```

If Python is missing, install it:

```powershell
winget install --id Python.Python.3.12 -e
```

If Git is missing, install it:

```powershell
winget install --id Git.Git -e
```

Close PowerShell, open a new PowerShell window, then run the check again:

```powershell
py --version
git --version
```

### 3. Download NetCoin

```powershell
cd $HOME
git clone https://github.com/netcoin-crl/netcoin.git
cd netcoin
```

If you already downloaded it before and want a fresh copy:

```powershell
cd $HOME
Remove-Item -Recurse -Force netcoin
git clone https://github.com/netcoin-crl/netcoin.git
cd netcoin
```

### 4. Create and activate a virtual environment

```powershell
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e .
python -m netcoin --help
```

If PowerShell blocks activation, run this once, then try activating again:

```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
.\.venv\Scripts\Activate.ps1
```

### 5. Create a local wallet

```powershell
python -m netcoin wallet-new --out my-wallet.json --mnemonic --confirm-backup
python -m netcoin wallet-info --wallet my-wallet.json
```

Write down the recovery phrase. Do not share it. The wallet file and phrase control your testnet coins.

### 6. Mine one testnet block using a public seed

```powershell
python -m netcoin miner --node http://seed1.netcoin.online:28444 --wallet my-wallet.json --blocks 1 --sync-after
```

If seed1 is unavailable, try:

```powershell
python -m netcoin miner --node http://seed2.netcoin.online:28444 --wallet my-wallet.json --blocks 1 --sync-after
```

### 7. Mine continuously until you stop it

This keeps mining one block at a time. Stop with `Ctrl+C`.

```powershell
while ($true) {
  python -m netcoin miner --node http://seed1.netcoin.online:28444 --wallet my-wallet.json --blocks 1 --sync-after
  Start-Sleep -Seconds 2
}
```

### 8. Check your balance

```powershell
python -m netcoin balance --node http://seed1.netcoin.online:28444 --wallet my-wallet.json
```

Mining rewards are coinbase rewards. They may show as immature until 100 more blocks are mined after them.

### 9. Run a local node connected to public seeds

Use this when you want your computer to run its own local node.

In the current PowerShell window, run:

```powershell
python -m netcoin --data netcoin-testnet init
python -m netcoin --data netcoin-testnet node --host 127.0.0.1 --port 28444 --sync-interval 60 --peer http://seed1.netcoin.online:28444 --peer http://seed2.netcoin.online:28444 --peer http://seed3.netcoin.online:28444
```

Leave that PowerShell window open.

### 10. Open a new PowerShell window and mine through your local node

Open a second PowerShell window, then run:

```powershell
cd $HOME\netcoin
.\.venv\Scripts\Activate.ps1
python -m netcoin miner --node http://127.0.0.1:28444 --wallet my-wallet.json --blocks 1 --sync-after
python -m netcoin balance --node http://127.0.0.1:28444 --wallet my-wallet.json
```

### 11. Run the local browser wallet

Open a new PowerShell window, then run:

```powershell
cd $HOME\netcoin
.\.venv\Scripts\Activate.ps1
python -m netcoin web --node http://seed1.netcoin.online:28444 --faucet https://faucet.netcoin.online
```

Open this in your browser:

```text
http://127.0.0.1:8088/
```

The local browser wallet is for local testing only. Do not expose it publicly.

## Linux instructions

These commands are for Ubuntu/Debian-style Linux. Other Linux distributions can use the same NetCoin commands after Python, venv, pip, and Git are installed.

### 1. Open Terminal

Open your Linux terminal.

### 2. Install Python and Git

```bash
sudo apt update
sudo apt install -y python3 python3-venv python3-pip git
```

### 3. Check versions

```bash
python3 --version
git --version
```

You need Python 3.10 or newer.

### 4. Download NetCoin

```bash
cd ~
git clone https://github.com/netcoin-crl/netcoin.git
cd netcoin
```

If you already downloaded it before and want a fresh copy:

```bash
cd ~
rm -rf netcoin
git clone https://github.com/netcoin-crl/netcoin.git
cd netcoin
```

### 5. Create and activate a virtual environment

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e .
python -m netcoin --help
```

When the virtual environment is active, your terminal usually shows `(.venv)` near the prompt.

### 6. Create a local wallet

```bash
python -m netcoin wallet-new --out my-wallet.json --mnemonic --confirm-backup
python -m netcoin wallet-info --wallet my-wallet.json
```

Write down the recovery phrase. Do not share it. The wallet file and phrase control your testnet coins.

### 7. Mine one testnet block using a public seed

```bash
python -m netcoin miner --node http://seed1.netcoin.online:28444 --wallet my-wallet.json --blocks 1 --sync-after
```

If seed1 is unavailable, try:

```bash
python -m netcoin miner --node http://seed2.netcoin.online:28444 --wallet my-wallet.json --blocks 1 --sync-after
```

### 8. Mine continuously until you stop it

This keeps mining one block at a time. Stop with `Ctrl+C`.

```bash
while true; do
  python -m netcoin miner --node http://seed1.netcoin.online:28444 --wallet my-wallet.json --blocks 1 --sync-after
  sleep 2
done
```

### 9. Check your balance

```bash
python -m netcoin balance --node http://seed1.netcoin.online:28444 --wallet my-wallet.json
```

Mining rewards are coinbase rewards. They may show as immature until 100 more blocks are mined after them.

### 10. Run a local node connected to public seeds

Use this when you want your computer to run its own local node.

In the current terminal, run:

```bash
python -m netcoin --data ~/.netcoin-testnet init
python -m netcoin --data ~/.netcoin-testnet node --host 127.0.0.1 --port 28444 --sync-interval 60 --peer http://seed1.netcoin.online:28444 --peer http://seed2.netcoin.online:28444 --peer http://seed3.netcoin.online:28444
```

Leave that terminal open.

### 11. Open a new terminal and mine through your local node

Open a second terminal window, then run:

```bash
cd ~/netcoin
source .venv/bin/activate
python -m netcoin miner --node http://127.0.0.1:28444 --wallet my-wallet.json --blocks 1 --sync-after
python -m netcoin balance --node http://127.0.0.1:28444 --wallet my-wallet.json
```

### 12. Run the local browser wallet

Open a new terminal, then run:

```bash
cd ~/netcoin
source .venv/bin/activate
python -m netcoin web --node http://seed1.netcoin.online:28444 --faucet https://faucet.netcoin.online
```

Open this in your browser:

```text
http://127.0.0.1:8088/
```

The local browser wallet is for local testing only. Do not expose it publicly.


## Run the local NetCoin wallet

The hosted wallet is available at <https://wallet.netcoin.online>. You can also run a local browser wallet on your own computer.

The local wallet runs only on your machine at:

```text
http://127.0.0.1:8088/
```

Keep it local. Do not publish it to the internet, do not run it on `0.0.0.0`, and do not share the browser URL with other people.

### macOS local wallet

Open Terminal:

```bash
cd ~/netcoin
source .venv/bin/activate
python -m netcoin web --node http://seed1.netcoin.online:28444 --faucet https://faucet.netcoin.online
```

Leave that Terminal open, then open this in your browser:

```text
http://127.0.0.1:8088/
```

### Windows local wallet

Open PowerShell:

```powershell
cd $HOME\netcoin
.\.venv\Scripts\Activate.ps1
python -m netcoin web --node http://seed1.netcoin.online:28444 --faucet https://faucet.netcoin.online
```

Leave that PowerShell window open, then open this in your browser:

```text
http://127.0.0.1:8088/
```

### Linux local wallet

Open Terminal:

```bash
cd ~/netcoin
source .venv/bin/activate
python -m netcoin web --node http://seed1.netcoin.online:28444 --faucet https://faucet.netcoin.online
```

Leave that Terminal open, then open this in your browser:

```text
http://127.0.0.1:8088/
```

### Local wallet troubleshooting

If the browser says it cannot connect, make sure the terminal running `python -m netcoin web` is still open.

If port `8088` is already in use, run on a different local port:

macOS / Linux:

```bash
python -m netcoin web --node http://seed1.netcoin.online:28444 --faucet https://faucet.netcoin.online --port 8090
```

Windows PowerShell:

```powershell
python -m netcoin web --node http://seed1.netcoin.online:28444 --faucet https://faucet.netcoin.online --port 8090
```

Then open:

```text
http://127.0.0.1:8090/
```

## Become a public seed

A public seed is a NetCoin node that other people can connect to. Running a public seed helps the testnet because new users can sync from more than one place.

You can run a seed in two ways:

```text
Easiest and most reliable: run it on a small VPS/cloud server.
Possible at home: run it on your computer and port-forward TCP 28444 in your router.
```

Public seed basics:

```text
HTTP node/API port: 28444
Optional raw P2P port: 18447
Recommended uptime: keep it running as much as possible
Recommended URL: a stable domain or static public IP
```

Do not expose your local browser wallet. Only expose the node port.

### Check your public IP

macOS / Linux:

```bash
curl -4 ifconfig.me
```

Windows PowerShell:

```powershell
Invoke-RestMethod -Uri "https://api.ipify.org"
```

If you are behind a home router, this is your router's public IP, not your computer's local IP.

### Find your computer's local IP for router port forwarding

macOS:

```bash
ipconfig getifaddr en0
```

If that prints nothing, try:

```bash
ipconfig getifaddr en1
```

Windows PowerShell:

```powershell
ipconfig
```

Look for your Wi-Fi or Ethernet IPv4 address, often like `192.168.x.x` or `10.0.x.x`.

Linux:

```bash
hostname -I
```

Use the first normal LAN address, often like `192.168.x.x` or `10.0.x.x`.

### Router or firewall rule needed

For a home computer to become a public seed, your router must forward:

```text
TCP 28444 -> your computer's local IP, port 28444
```

Optional raw P2P forwarding:

```text
TCP 18447 -> your computer's local IP, port 18447
```

Every router brand is different. In your router settings, look for **Port Forwarding**, **NAT**, or **Virtual Server**.

If you are on a VPS/cloud server, open the same inbound ports in the cloud firewall/security group.

### macOS public seed

Open Terminal and go to NetCoin:

```bash
cd ~/netcoin
source .venv/bin/activate
```

Initialize the seed data folder:

```bash
python -m netcoin --data ~/.netcoin-testnet init
```

Start the public seed:

```bash
python -m netcoin --data ~/.netcoin-testnet node \
  --host 0.0.0.0 \
  --port 28444 \
  --p2p-port 18447 \
  --seeds \
  --sync-interval 60 \
  --advertise http://YOUR_PUBLIC_IP_OR_DOMAIN:28444
```

Replace `YOUR_PUBLIC_IP_OR_DOMAIN` with your public IP or domain name.

Leave this Terminal open. To stop the seed, press `Ctrl+C`.

### Windows public seed

Open PowerShell and go to NetCoin:

```powershell
cd $HOME\netcoin
.\.venv\Scripts\Activate.ps1
```

Allow the NetCoin node through Windows Firewall:

```powershell
New-NetFirewallRule -DisplayName "NetCoin Node 28444" -Direction Inbound -Protocol TCP -LocalPort 28444 -Action Allow
New-NetFirewallRule -DisplayName "NetCoin P2P 18447" -Direction Inbound -Protocol TCP -LocalPort 18447 -Action Allow
```

Initialize the seed data folder:

```powershell
python -m netcoin --data netcoin-testnet init
```

Start the public seed:

```powershell
python -m netcoin --data netcoin-testnet node `
  --host 0.0.0.0 `
  --port 28444 `
  --p2p-port 18447 `
  --seeds `
  --sync-interval 60 `
  --advertise http://YOUR_PUBLIC_IP_OR_DOMAIN:28444
```

Replace `YOUR_PUBLIC_IP_OR_DOMAIN` with your public IP or domain name.

Leave this PowerShell window open. To stop the seed, press `Ctrl+C`.

### Linux public seed

Open Terminal and go to NetCoin:

```bash
cd ~/netcoin
source .venv/bin/activate
```

If you use `ufw`, allow the NetCoin ports:

```bash
sudo ufw allow 28444/tcp
sudo ufw allow 18447/tcp
```

Initialize the seed data folder:

```bash
python -m netcoin --data ~/.netcoin-testnet init
```

Start the public seed:

```bash
python -m netcoin --data ~/.netcoin-testnet node \
  --host 0.0.0.0 \
  --port 28444 \
  --p2p-port 18447 \
  --seeds \
  --sync-interval 60 \
  --advertise http://YOUR_PUBLIC_IP_OR_DOMAIN:28444
```

Replace `YOUR_PUBLIC_IP_OR_DOMAIN` with your public IP or domain name.

Leave this Terminal open. To stop the seed, press `Ctrl+C`.

### Test that your seed works

From a different internet connection, or from a friend's computer, run:

```bash
curl http://YOUR_PUBLIC_IP_OR_DOMAIN:28444/info
```

A working seed returns JSON with node information.

Then test syncing or querying through your seed:

```bash
python -m netcoin balance --node http://YOUR_PUBLIC_IP_OR_DOMAIN:28444 --address YOUR_NETCOIN_ADDRESS_HERE
```

### Mine through your own public seed

After your public seed is running, open a new terminal and mine through it.

macOS / Linux:

```bash
cd ~/netcoin
source .venv/bin/activate
python -m netcoin miner --node http://YOUR_PUBLIC_IP_OR_DOMAIN:28444 --wallet my-wallet.json --blocks 1 --sync-after
```

Windows PowerShell:

```powershell
cd $HOME\netcoin
.\.venv\Scripts\Activate.ps1
python -m netcoin miner --node http://YOUR_PUBLIC_IP_OR_DOMAIN:28444 --wallet my-wallet.json --blocks 1 --sync-after
```

### Keep a public seed reliable

For a seed that other people depend on:

```text
Use a stable domain or static IP.
Keep the computer/server online.
Keep NetCoin updated.
Open only the ports you need.
Do not run the browser wallet as a public service.
Back up your node data if you care about local history.
```

For more public-seed hosting options, see [docs/PUBLIC_SEED_HOSTING.md](docs/PUBLIC_SEED_HOSTING.md).

## Common commands after setup

Activate the virtual environment after opening a new terminal:

macOS / Linux:

```bash
cd ~/netcoin
source .venv/bin/activate
```

Windows PowerShell:

```powershell
cd $HOME\netcoin
.\.venv\Scripts\Activate.ps1
```

Show help:

```bash
python -m netcoin --help
```

Show wallet information:

```bash
python -m netcoin wallet-info --wallet my-wallet.json
```

Check a wallet balance through a public node:

```bash
python -m netcoin balance --node http://seed1.netcoin.online:28444 --wallet my-wallet.json
```

Check any address:

```bash
python -m netcoin balance --node http://seed1.netcoin.online:28444 --address YOUR_NETCOIN_ADDRESS_HERE
```

Mine one block through a public node:

```bash
python -m netcoin miner --node http://seed1.netcoin.online:28444 --wallet my-wallet.json --blocks 1 --sync-after
```

Mine one block through your local node:

```bash
python -m netcoin miner --node http://127.0.0.1:28444 --wallet my-wallet.json --blocks 1 --sync-after
```

Run the local browser wallet:

```bash
python -m netcoin web --node http://seed1.netcoin.online:28444 --faucet https://faucet.netcoin.online
```

## Troubleshooting

### `python: command not found`

Use `python3` on macOS/Linux or `py -3` on Windows for the setup step. After the virtual environment is active, `python` should work.

### `ModuleNotFoundError: No module named netcoin`

You are probably outside the project folder or the virtual environment is not active. Run the activation commands again, then reinstall:

```bash
python -m pip install -e .
```

### PowerShell will not activate `.venv`

Run:

```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
.\.venv\Scripts\Activate.ps1
```

### Public seed is not responding

Try another seed:

```bash
python -m netcoin balance --node http://seed2.netcoin.online:28444 --wallet my-wallet.json
python -m netcoin balance --node http://seed3.netcoin.online:28444 --wallet my-wallet.json
```

### Mining works, but balance is not spendable yet

Mining rewards need maturity. Wait until 100 more blocks are mined after your reward block.

### A command is stuck or keeps running

Press:

```text
Ctrl+C
```

## Safety reminders

- Do not share seed phrases.
- Do not share private keys.
- Do not share wallet files.
- Public-testnet NET has no real-money value.
- Keep local browser tools bound to `127.0.0.1` unless you understand the security risks.
