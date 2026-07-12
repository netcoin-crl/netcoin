# Reproducible Builds

NetCoin M2 adds a deterministic source-build recipe and verifier. Local source
verification proves the archive builder is stable on one machine. The GitHub
CI lane compares that local archive against the same builder executed inside
`Dockerfile.repro`, producing an independent-builder evidence report.

## Build

```bash
docker build -f Dockerfile.repro --build-arg NETCOIN_VERSION=$(python3 - <<'PY'
from netcoin.params import NODE_VERSION
print(NODE_VERSION)
PY
) --output type=local,dest=/tmp/netcoin-repro-docker .
```

## Verify source archive determinism

```bash
python3 tools/verify_reproducible_build.py --out reports/reproducible_build_source_report.json
```

Or through Make:

```bash
make reproducible-build-check
```

## Compare independent outputs

The CI workflow `.github/workflows/reproducible-build.yml` runs both:

- local Python archive builder:
  `dist/netcoin-local-source.tar.gz`
- Docker/BuildKit archive builder:
  `/tmp/netcoin-repro-docker/src/dist/netcoin-ci-source.tar.gz`

Then it writes:

```bash
reports/m2_evidence/independent_repro_build.json
```

The report uses schema `netcoin-independent-repro-build-v1` and is `ok: true`
only when the local and Docker archive SHA256 digests match.

To compare two already-built archives manually:

```bash
python3 tools/compare_reproducible_builds.py \
  --local-archive dist/netcoin-local-source.tar.gz \
  --docker-archive /tmp/netcoin-repro-docker/src/dist/netcoin-ci-source.tar.gz \
  --out reports/m2_evidence/independent_repro_build.json
```

## Strict completion

Strict M2 requires two independent builders to produce matching source archives,
matching SBOM hashes, signed artifacts, and saved provenance attestations.
