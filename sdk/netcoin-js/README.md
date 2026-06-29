# netcoin-js

Small JavaScript SDK for the NetCoin app-layer APIs.

```js
import { NetcoinClient } from './index.js';
const nc = new NetcoinClient('https://wallet.netcoin.online');
const invoice = await nc.createInvoice({ address: 'net1...', amount: '1.25', memo: 'Order #123' });
```
