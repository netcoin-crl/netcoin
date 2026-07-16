# NetCoin v0.31 TypeScript OpenAPI Codegen Parity

NetCoin v0.31 completes the current migration batch by adding TypeScript OpenAPI/schema/client codegen parity. The Python API remains live; TypeScript is still a contract and future app/API layer.

Added coverage:

- required OpenAPI route presence
- required Zod schema exports
- typed client method presence
- OpenAPI parity helper/codegen symbols
- frozen API vector summary for schema, route, client, and codegen status

Key files:

- `api/src/schemas.ts`
- `api/src/client.ts`
- `api/src/openapi-parity.ts`
- `tools/run_ts_openapi_codegen_parity.py`
- `tests/test_v031_ts_openapi_codegen_parity.py`

Gate:

```bash
make v031-check
```

Sandbox note: `make v031-check` chains all previous version gates and can exceed constrained sandbox timeouts. Running the same commands individually is equivalent evidence when each command passes.
