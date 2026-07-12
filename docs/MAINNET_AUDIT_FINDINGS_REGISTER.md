# Mainnet external audit findings register

This register is the source template for tracking an external security audit.
It is empty until a real auditor is engaged.

## Required fields per finding

- Finding id.
- Severity.
- Component.
- Auditor summary.
- Maintainer response.
- Fix commit or waiver rationale.
- Retest result.
- Public disclosure status.

## Release rule

Mainnet launch is blocked if any critical/high finding is open without a public,
reviewed waiver.

## Evidence path

Strict M4 requires:

```text
reports/m4_evidence/external_audit_completion.json
```
