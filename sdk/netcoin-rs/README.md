# netcoin-rs

Small Rust SDK for NetCoin node API v1 routes and signed request envelopes.

```rust
use netcoin_rs::NetcoinClient;

let client = NetcoinClient::new("http://127.0.0.1:28444");
let info = client.node_info()?;
assert!(info.contains("\"node\""));
# Ok::<(), netcoin_rs::NetcoinError>(())
```

The client intentionally uses only the Rust standard library in this release so
localnet checks can run in restricted CI without fetching dependencies. It
supports plain `http://` node URLs; production HTTPS callers should place it
behind the hosted API proxy or a TLS-capable transport wrapper.
