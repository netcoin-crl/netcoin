# NetCoin v0.35 TypeScript API Server + OpenAPI Contract Enforcement

v0.35 adds a TypeScript API server shell and contract enforcement layer:

- `api/src/server.ts`
- `api/src/openapi-enforce.ts`
- `tools/run_ts_api_contract_enforcement.py`

The server is still a migration shell; the Python app remains live. The important change is that TypeScript now has a concrete API boundary that asserts write routes require signed-envelope protections and that required routes document responses.

Run:

```bash
python tools/run_ts_api_contract_enforcement.py
make v035-check
```

When Node dependencies are available, run:

```bash
cd api
npm ci
npm run ci:api
```
