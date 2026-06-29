# netcoin-python

Standard-library SDK for NetCoin app-layer APIs.

```python
from netcoin_sdk import NetcoinClient
nc = NetcoinClient('https://wallet.netcoin.online')
invoice = nc.create_invoice('net1...', '1.25', memo='Order #123')
```
