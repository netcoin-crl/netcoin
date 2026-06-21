# NetCoin Brand & Identity

This page clarifies what "NetCoin" is and how to tell official resources apart from
forks or copies.

## What NetCoin is

- An **educational, Bitcoin-like cryptocurrency** and **public testnet**.
- Code plus a small public 3-seed testnet for learning and experimentation.

## What NetCoin is NOT

- **Not Bitcoin.** It does not connect to the Bitcoin network.
- **Not real-money software.** Testnet NET has no monetary value.
- **Not an investment.** No one should buy, sell, or trade NET expecting value.
- **Not production-hardened.** It has not had an external security review.

Do not use the NetCoin name to imply real-money value, investment returns, or any
affiliation with Bitcoin.

## Official resources

- Source repository: https://github.com/Adoniyas1/netcoin
- Public testnet seeds: `seed1.netcoin.online`, `seed2.netcoin.online`,
  `seed3.netcoin.online` (port 28444)
- Explorer / faucet / status: served from the seed1 host (see the README)

If a resource is not linked from the official repository, treat it as unofficial.

## Forks and copies

NetCoin is open source — forking is welcome for learning. If you run a fork:

- Use a **different name and genesis** so testers don't confuse it with the public
  NetCoin testnet.
- Don't advertise your fork as the official NetCoin network.
- Keep the educational, no-real-value framing.

## Genesis identity

Nodes verify they are on the same network by comparing the **genesis hash** and
**network name** (`testnet`) in `/info`. A different genesis is a different network.
