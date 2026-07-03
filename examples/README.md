# NetCoin starter examples

Small, self-contained scripts that show how to build on the NetCoin app-layer
API with the bundled Python SDK (`sdk/netcoin-python`). They run against any
node with app-layer routes enabled:

```bash
# Public testnet relay (default)
python examples/store_checkout.py

# Your own node
NETCOIN_API=http://127.0.0.1:28444 python examples/store_checkout.py
```

| Example | What it shows |
|---|---|
| `store_checkout.py` | Create an invoice for an order, print the payment link/QR URI, poll until paid. |
| `token_points.py` | Create a NET-20 style loyalty token, mint points, transfer to a customer, check balances. |

More complete apps live in `bots/` (Discord and Telegram tip bots) and
`sdk/netcoin-js` for browser/Node integrations. The full endpoint list is in
[`docs/openapi.yaml`](../docs/openapi.yaml).
