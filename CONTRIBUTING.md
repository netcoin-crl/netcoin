# Contributing to NetCoin

Thanks for helping with NetCoin! NetCoin is **educational testnet software** — a
small, readable, Bitcoin-like chain. Contributions should keep it understandable
and well-tested.

## Ground rules

- **Testnet safety:** never commit wallet files, seed phrases, private keys, API
  tokens, or server credentials. NET has no real-money value; don't imply it does.
- **Small, focused changes** are easier to review than large ones.
- **Tests required:** add or update tests for any behavior change.

## Development setup

```bash
python -m pip install -e .
python -m pytest
```

All tests should pass before you open a pull request.

## Making a change

1. Branch from `main`.
2. Make the change with tests.
3. Run `python -m pytest` (the full suite).
4. Update `CHANGELOG.md` (under `Unreleased`) and any affected docs.
5. Open a PR using the template; describe what and why.

## Code style

- Match the surrounding code: prefer the standard library unless a dependency is
  clearly justified. `cryptography` is the intentional wallet-AEAD dependency.
- Keep comments about *why*, not *what*.
- Consensus-affecting code (`chain.py`, `block.py`, `tx.py`) needs extra care and
  must be called out explicitly in the PR — a subtle bug there can split the chain.

## What we especially welcome

- More tests (sync resilience, mempool attacks, fuzzing, multi-node).
- Documentation fixes and tester guides.
- Bug reports from running your own node or miner (use the issue templates).

## Reporting security issues

Do **not** open a public issue for a security-sensitive bug. Follow
[SECURITY.md](SECURITY.md) and use GitHub private advisories.

## Releases

See [docs/RELEASING.md](docs/RELEASING.md). Maintainers cut versioned, checksummed
(and, going forward, signed) releases.
