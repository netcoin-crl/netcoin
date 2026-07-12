# M3 Home Node Bandwidth Mode

Home-node mode keeps relay bandwidth under the M3 target of 500 KB/s.

Source contract: `netcoin/bandwidth.py`.

Modes:

- `normal`: no artificial cap; best for VPS/public seed nodes.
- `home`: 500 KB/s target, compact-block relay enabled, 6 outbound peers.
- `low`: 250 KB/s target, compact-block relay enabled, inventory relay reduced, 4 outbound peers.

Recommended home operator command:

```bash
NETCOIN_BANDWIDTH_MODE=home python -m netcoin --data ~/.netcoin-testnet node --host 0.0.0.0 --port 28444 --advertise YOUR_PUBLIC_IP_OR_DNS:28444
```

This is source-level planning until integrated into the long-running node service loop and verified under public soak.
