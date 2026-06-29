# NetCoin Private Beta — Tester Invite

Hi, and thanks for helping test **NetCoin**! This is a short, copy-paste message
you can follow to try the public testnet in about 10 minutes.

> **Safety:** NetCoin is educational testnet software. Test NET has **no real-money
> value**. Never reuse a real wallet seed phrase here, and never share your wallet
> file or seed phrase with anyone — including me.

## What I'd love you to try

1. **Install & make a wallet** (2 min)
2. **Get test coins from the faucet** (1 min)
3. **Send a transaction** (2 min)
4. **(Optional) run a node or mine a block** (5 min)
5. **Tell me what broke or felt confusing** — that's the whole point.

## Steps

```bash
# 1. Get the code & install (needs Python 3.10+; works on macOS/Linux/Windows)
git clone https://github.com/netcoin-crl/netcoin.git
cd netcoin
python -m pip install -e .

# 2. New wallet (write the seed phrase on paper!)
python -m netcoin wallet-new --out my-wallet.json --mnemonic --confirm-backup
chmod 600 my-wallet.json
python -m netcoin wallet-info --wallet my-wallet.json    # copy your address
```

3. **Faucet:** open https://seed1.netcoin.online/faucet and paste your address (5 test NET,
   once per IP per day).

```bash
# 4. Point a node at the public seeds (built-in seed list)
python -m netcoin --data ~/.netcoin-testnet node --seeds

# 5. Send some NET (in another terminal)
python -m netcoin --data ~/.netcoin-testnet send \
  --wallet my-wallet.json --to <A_FRIENDS_ADDRESS> \
  --amount 1 --fee 0.01 --broadcast-to http://seed1.netcoin.online:28444
```

Optional: mine a block — see [MINING.md](MINING.md). Run your own full node — see
[NODE_RUNNER.md](NODE_RUNNER.md).

## What to send back

- What worked / what didn't (exact command + what happened).
- Anything confusing in the docs.
- Your node height/tip if you ran one (`curl http://127.0.0.1:28444/health`).

Open an issue with the **Testnet node report** or **Bug report** template, or just
message me. Please don't include your wallet file or seed phrase.

Thank you! Every independent tester makes the network more real.

— See also: [STARTER_KIT.md](STARTER_KIT.md) · [LIMITATIONS.md](LIMITATIONS.md)
