# Reproducible Releases and Verification

## Build

Preferred release build:

```bash
tools/make_release.sh v0.12.0
```

This creates a source archive and `SHA256SUMS`. If GPG is configured, it also writes `SHA256SUMS.asc`.

## Verify

```bash
python tools/verify_release.py dist/
```

The verifier checks every listed file hash and verifies the detached GPG signature when present.

## Manifest and SBOM

Generate a JSON release manifest with file hashes and dependency metadata:

```bash
python tools/professional_readiness.py --manifest dist/netcoin-release-manifest.json
```

## Release Checklist

- Version matches `pyproject.toml`, README, and release notes.
- Full test suite passes or documented exceptions exist.
- Professional readiness checker is clean or open items are explicitly accepted.
- Archive checksum is published.
- Signature is published for official releases.
- Security advisory review is complete.
