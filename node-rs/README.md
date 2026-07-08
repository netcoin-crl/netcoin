# node-rs

Rust node/P2P upgrade lane.

Final ownership:
- peer handshake and version negotiation
- headers-first sync
- hostile peer scoring
- bandwidth budgets
- block download scheduling
- RPC/metrics bridge to app/API services

The current Python node remains the reference implementation until this service passes parity and soak tests.
