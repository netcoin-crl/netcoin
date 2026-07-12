# Reproducible Builds

NetCoin M2 adds a deterministic source-build recipe and verifier. This is a
source-level gate, not independent reproducibility proof by itself.

## Build

```bash
docker build -f Dockerfile.repro --build-arg NETCOIN_VERSION=$(python3 - <<'PY'
from netcoin.params import NODE_VERSION
print(NODE_VERSION)
PY
) -t netcoin-repro:local .
```

## Verify source archive determinism

```bash
python3 tools/verify_reproducible_build.py --out reports/reproducible_build_source_report.json
```

## Strict completion

Strict M2 requires two independent builders to produce matching source archives,
matching SBOM hashes, signed artifacts, and saved provenance attestations.
