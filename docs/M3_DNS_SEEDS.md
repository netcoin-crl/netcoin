# M3 DNS Seed Rotation Plan

Operational M3 requires DNS seed diversity. One domain controlled by the founder is not enough.

## Source-level records

Seed definitions live in `config/dns_seeds.json`.

## Operational requirements

- At least two independent DNS domains are delegated or controlled by separate operators.
- At least two independent seed operators are represented.
- DNS answers include live nodes beyond the founder AWS account.
- Seed records are monitored for stale entries.

## Evidence file

Strict M3 expects:

```text
reports/m3_evidence/dns_seed_delegation.json
```

It must include:

- `ok: true`
- domains
- operator names/handles
- proof timestamp
- resolver samples
- stale-record policy
