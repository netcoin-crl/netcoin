# NetCoin on Windows — beginner's guide

This walks you through NetCoin on Windows, step by step, assuming you've never
used a terminal. You'll install NetCoin, make a wallet, mine some test coins,
check your balance, and open a wallet in your browser.

> NetCoin is a **learning project on a test network**. Test NET has **no real
> money value**. Never put real funds or real passwords into it.

**A few words first:**
- You'll use **PowerShell** (not the old "Command Prompt"). It's an app where you
  type commands, then press **Enter**.
- When a command keeps running (a node, a miner, the wallet), **leave that
  PowerShell window open** and open a **new** one for the next steps.
- To stop something that's running, click its window and press **Ctrl + C**.
- A **wallet** holds your coins. Its **recovery phrase** is the master key —
  anyone who has it controls the coins, so keep it private.

---

## 1. Open PowerShell

Click **Start**, type **PowerShell**, click **Windows PowerShell**.

## 2. Check you have Python and Git

```powershell
py --version
git --version
```

You need **Python 3.10 or newer**. If either is missing, install it:

```powershell
winget install --id Python.Python.3.12 -e
winget install --id Git.Git -e
```

Then **close PowerShell, open a new PowerShell window**, and run the two `--version`
checks again.

## 3. Download NetCoin

```powershell
cd $HOME
git clone https://github.com/netcoin-crl/netcoin.git
cd netcoin
```

This downloads NetCoin into a `netcoin` folder in your user folder and moves into
it. (Already have it and want a clean copy? Run `cd $HOME`, then
`Remove-Item -Recurse -Force netcoin`, then the commands above.)

## 4. Set up NetCoin

```powershell
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e .
python -m netcoin --help
```

The first two lines make a private workspace (a "virtual environment"). When it's
active you'll see **`(.venv)`** at the start of your prompt. The last line should
print a list of commands — that means it worked.

> **If PowerShell refuses to activate** with a security/execution-policy error,
> run this once, then run the `Activate.ps1` line again:
> ```powershell
> Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
> ```

> **Every time you open a new PowerShell** to use NetCoin, first run:
> ```powershell
> cd $HOME\netcoin
> .\.venv\Scripts\Activate.ps1
> ```

## 5. Make a wallet

```powershell
python -m netcoin wallet-new --out my-wallet.json --mnemonic --confirm-backup
python -m netcoin wallet-info --wallet my-wallet.json
```

It shows a **recovery phrase** — write it on paper and keep it safe. The second
command shows your wallet, including your **address** (starts with `net1…`),
which is what you share to receive coins.

## 6. Get some test coins by mining

Mining is how new coins are created. This mines one block to your wallet using a
public NetCoin server:

```powershell
python -m netcoin miner --node http://18.220.89.128/api --wallet my-wallet.json --blocks 1 --sync-after
```

> We use the numeric address `http://18.220.89.128/api` on purpose — some home
> networks block the `netcoin.online` name. If your network allows the name,
> `https://api.netcoin.online/api` also works.

Mine continuously (stop anytime with **Ctrl + C**):

```powershell
while ($true) {
  python -m netcoin miner --node http://18.220.89.128/api --wallet my-wallet.json --blocks 1 --sync-after
  Start-Sleep -Seconds 2
}
```

**Already have an address** and just want to mine to it? You don't need a wallet
file — use `--address net1youraddress --address-type p2wpkh` instead of `--wallet`.

## 7. Check your balance

```powershell
python -m netcoin balance --node http://18.220.89.128/api --wallet my-wallet.json
```

Freshly mined coins show as **immature** for a while — mining rewards only become
spendable after **100 more blocks** are mined on top of them. That's normal.

## 8. Open the wallet in your browser

```powershell
python -m netcoin web --node http://18.220.89.128/api --faucet https://faucet.netcoin.online
```

Leave that PowerShell window open and go to **<http://127.0.0.1:8088/>** in your
browser. This wallet runs only on your computer — don't share the address or
expose it to the internet.

---

## Want to run your own node (trust no website)?

Everything above uses a public server. You can instead run your **own** node and
point the wallet/miner at it, so you trust only your own computer. See
**[RUN_YOUR_OWN.md](RUN_YOUR_OWN.md)** — it covers running a node, becoming a
public seed, and using NetCoin fully offline from the public sites.

## Trouble?

- **`python` not recognized** — use `py -3` for the setup step; after step 4's
  `Activate.ps1`, plain `python` works.
- **`No module named netcoin`** — you're outside the folder or the env isn't
  active. Re-run `cd $HOME\netcoin` and `.\.venv\Scripts\Activate.ps1`.
- **PowerShell won't activate `.venv`** — run
  `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`, then activate again.
- **"cannot reach the node"** — make sure the `python -m netcoin web` window is
  still open, and use `http://18.220.89.128/api`. Test it with
  `Invoke-RestMethod http://18.220.89.128/api/info`.
- **Something's stuck** — click that window, press **Ctrl + C**.

## Stay safe

- Never share your recovery phrase, private key, or wallet file.
- Test NET isn't real money.
- Keep the browser wallet on `127.0.0.1` — don't expose it publicly.
