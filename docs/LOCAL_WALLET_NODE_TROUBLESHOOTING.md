# Local wallet and miner node connection troubleshooting

Use this when the local wallet or miner cannot reach the public NetCoin node.

## Recommended node URLs

Preferred domain:

```text
https://api.netcoin.online/api
```

No-tunnel fallback that currently works from blocked home networks:

```text
http://18.220.89.128/api
```

Direct seed ports for node operators:

```text
http://seed1.netcoin.online:28444
http://seed2.netcoin.online:28444
http://seed3.netcoin.online:28444
```

## Test the public API

macOS / Linux:

```bash
curl http://18.220.89.128/api/latest | head
```

Windows PowerShell:

```powershell
Invoke-RestMethod http://18.220.89.128/api/latest
```

A working response starts with JSON containing `blocks`.

## Create a wallet and mine

```bash
python -m netcoin wallet-new --out my-wallet.json --mnemonic
python -m netcoin miner --node http://18.220.89.128/api --wallet my-wallet.json --blocks 1 --sync-after
```

## Run the local browser wallet

```bash
python -m netcoin web --node http://18.220.89.128/api --faucet https://faucet.netcoin.online
```

Then open:

```text
http://127.0.0.1:8088/
```

If port `8088` is already in use, stop the old local wallet or use another port.

macOS / Linux:

```bash
kill $(lsof -tiTCP:8088 -sTCP:LISTEN) 2>/dev/null || true
python -m netcoin web --node http://18.220.89.128/api --faucet https://faucet.netcoin.online --port 8090
```

Then open `http://127.0.0.1:8090/`.

## Address types

The same wallet can show several receiving address formats: legacy, p2sh-segwit, segwit, and taproot. They are controlled by the same wallet/private key, but they are different blockchain addresses. If you mined with the default miner command, check the legacy address unless you passed `--address-type`.
