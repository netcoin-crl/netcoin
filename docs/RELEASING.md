# Releasing NetCoin

NetCoin uses [Semantic Versioning](https://semver.org/) (`MAJOR.MINOR.PATCH`) and
publishes a verifiable source archive for every release.

> Reminder: NetCoin is educational testnet software. A "release" is a tagged,
> checksummed snapshot — not a guarantee of production safety.

## Versioning

- **PATCH** (`0.2.0 -> 0.2.1`): bug fixes, doc fixes, test additions, no behavior
  change to consensus or wallet formats.
- **MINOR** (`0.2.x -> 0.3.0`): new features, new endpoints/commands, additive
  changes that stay backward compatible for existing testnet data.
- **MAJOR** (`0.x -> 1.0`): consensus changes, wallet-format changes, or anything
  that can invalidate existing chains/wallets. Include migration notes.

The version lives in [`pyproject.toml`](../pyproject.toml) and is the single
source of truth; the release script reads it.

## Release steps

1. **Update the changelog.** Move items from `Unreleased` into a new
   `## [X.Y.Z] - YYYY-MM-DD` section in [`CHANGELOG.md`](../CHANGELOG.md). Add
   migration notes for MAJOR releases.

2. **Bump the version** in `pyproject.toml` to `X.Y.Z`.

3. **Run the tests.**
   ```bash
   python -m pytest
   ```

4. **Commit and tag.** Tags are `vX.Y.Z`.
   ```bash
   git commit -am "Release vX.Y.Z"
   git tag -a vX.Y.Z -m "NetCoin vX.Y.Z"
   ```

5. **Build the signed artifact** from the tag (reproducible via `git archive`):
   ```bash
   tools/make_release.sh vX.Y.Z
   ```
   This writes `dist/netcoin-X.Y.Z.zip`, `dist/SHA256SUMS`, and — if a GPG key is
   available — `dist/SHA256SUMS.asc`.

6. **Push and publish.**
   ```bash
   git push && git push --tags
   ```
   Create the GitHub release for `vX.Y.Z` and attach all three `dist/` files.

## How users verify a download

```bash
# Checksum
sha256sum -c SHA256SUMS         # Linux
shasum -a 256 -c SHA256SUMS     # macOS

# Signature (if SHA256SUMS.asc is present)
gpg --verify SHA256SUMS.asc SHA256SUMS
```

The signing public key is published in this repo at
[`netcoin-signing-key.asc`](netcoin-signing-key.asc). Import it before verifying:

```bash
gpg --import docs/netcoin-signing-key.asc
gpg --verify SHA256SUMS.asc SHA256SUMS
```

A good signature reads:

```
gpg: Good signature from "NetCoin <netcoin2026@gmail.com>"
```

## Signing key

- **Identity:** `NetCoin <netcoin2026@gmail.com>`
- **Type:** Ed25519 (EdDSA), sign-only
- **Fingerprint:** `84F7 F2B9 50C9 D16F A628  AC67 5546 3C98 D439 9B90`
- **Short key id:** `55463C98D4399B90`
- Public key committed at `docs/netcoin-signing-key.asc`; the private key stays
  in the maintainer's local keyring and is **never** committed.
- To sign a release, set the key id and run the release script:
  ```bash
  NETCOIN_SIGNING_KEY=55463C98D4399B90 tools/make_release.sh vX.Y.Z
  ```
- Never commit private keys. `.gitignore` already blocks `*.key` / `*.pem`.
