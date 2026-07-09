#!/usr/bin/env python3
"""Source-check TypeScript API server and OpenAPI contract enforcement wiring.

This gate intentionally works without npm/node_modules so restricted sandboxes can
still catch drift. When npm is available, --run-npm additionally executes the TS
build/contract/parity script.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REQUIRED_FILES = [
    "api/src/server.ts",
    "api/src/openapi-enforce.ts",
    "api/src/openapi-parity.ts",
    "api/src/client.ts",
    "docs/openapi.yaml",
]
REQUIRED_SYMBOLS = {
    "api/src/server.ts": [
        "createNetCoinApiServer",
        "implementedApiRoutes",
        "assertOpenApiContract(requiredApiRoutes, implementedApiRoutes)",
        "summarizeBundledOpenApiParity",
        "startNetCoinApiServer",
    ],
    "api/src/openapi-enforce.ts": [
        "requiredApiRoutes",
        "summarizeOpenApiContract",
        "assertOpenApiContract",
        "implementedRoutes",
        "missingRoutes",
    ],
    "api/src/openapi-parity.ts": ["summarizeBundledOpenApiParity", "summarizeOpenApiParity"],
    "api/src/index.ts": ["openapi-enforce", "server.js"],
}

ROUTE_LITERAL_RE = re.compile(
    r"\{\s*path:\s*['\"]([^'\"]+)['\"]\s*,\s*method:\s*['\"](get|post|put|patch|delete)['\"]",
    re.IGNORECASE,
)
FASTIFY_ROUTE_RE = re.compile(r"app\.(get|post|put|patch|delete)\(\s*['\"]([^'\"]+)['\"]", re.IGNORECASE)
CLIENT_GET_RE = re.compile(r"getJson\(\s*(?:`([^`]+)`|'([^']+)'|\"([^\"]+)\")")


def normalize_path(path: str) -> str:
    path = path.rstrip("/") if len(path) > 1 else path
    path = re.sub(r":[A-Za-z_][A-Za-z0-9_]*", lambda m: "{" + m.group(0)[1:] + "}", path)
    path = re.sub(r"\$\{encodeURIComponent\(([A-Za-z_][A-Za-z0-9_]*)\)\}", lambda m: "{" + m.group(1) + "}", path)
    return path


def route_key(method: str, path: str) -> str:
    return f"{method.lower()} {normalize_path(path)}"


def parse_contract_routes(text: str, array_name: str, required_routes: set[str] | None = None) -> set[str]:
    marker = f"export const {array_name}"
    start = text.find(marker)
    if start == -1:
        return set()
    end = text.find("];", start)
    body = text[start : end if end != -1 else len(text)]
    routes = {route_key(method, path) for path, method in ROUTE_LITERAL_RE.findall(body)}
    if required_routes is not None and "...requiredApiRoutes" in body:
        routes.update(required_routes)
    return routes


def parse_fastify_routes(text: str) -> set[str]:
    return {route_key(method, path) for method, path in FASTIFY_ROUTE_RE.findall(text)}


def parse_client_get_routes(text: str) -> set[str]:
    routes: set[str] = set()
    for match in CLIENT_GET_RE.findall(text):
        literal = next((part for part in match if part), "")
        if literal:
            routes.add(route_key("get", literal))
    return routes


def openapi_contains_route(openapi_text: str, path: str) -> bool:
    normalized = normalize_path(path)
    unprefixed = re.sub(r"^/api(?=/)", "", normalized)
    return f"  {normalized}:" in openapi_text or f"  {unprefixed}:" in openapi_text


def source_check() -> dict[str, object]:
    issues: list[str] = []
    for rel in REQUIRED_FILES:
        if not (ROOT / rel).exists():
            issues.append(f"missing {rel}")
    for rel, symbols in REQUIRED_SYMBOLS.items():
        text = (ROOT / rel).read_text(encoding="utf-8") if (ROOT / rel).exists() else ""
        for symbol in symbols:
            if symbol not in text:
                issues.append(f"{rel} missing symbol {symbol}")

    enforce_text = (ROOT / "api/src/openapi-enforce.ts").read_text(encoding="utf-8")
    server_text = (ROOT / "api/src/server.ts").read_text(encoding="utf-8")
    client_text = (ROOT / "api/src/client.ts").read_text(encoding="utf-8")
    openapi_text = (ROOT / "docs/openapi.yaml").read_text(encoding="utf-8")

    required = parse_contract_routes(enforce_text, "requiredApiRoutes")
    implemented_manifest = parse_contract_routes(server_text, "implementedApiRoutes", required)
    registered = parse_fastify_routes(server_text)
    client_gets = parse_client_get_routes(client_text)

    missing_from_manifest = sorted(required - implemented_manifest)
    missing_from_server = sorted(required - registered)
    missing_client_routes = sorted(client_gets - registered)
    missing_openapi = sorted(key for key in required if not openapi_contains_route(openapi_text, key.split(" ", 1)[1]))

    if missing_from_manifest:
        issues.append(f"implementedApiRoutes missing required routes: {missing_from_manifest}")
    if missing_from_server:
        issues.append(f"Fastify server missing required routes: {missing_from_server}")
    if missing_client_routes:
        issues.append(f"client routes not registered by server: {missing_client_routes}")
    if missing_openapi:
        issues.append(f"docs/openapi.yaml missing required routes: {missing_openapi}")
    if "summarizeOpenApiParity()" in server_text:
        issues.append("server.ts calls summarizeOpenApiParity with no source arguments")

    result = {
        "ok": not issues,
        "mode": "source",
        "issues": issues,
        "checked_files": len(REQUIRED_FILES),
        "required_route_count": len(required),
        "implemented_manifest_route_count": len(implemented_manifest),
        "registered_route_count": len(registered),
        "client_get_route_count": len(client_gets),
        "tsc_checked": False,
    }

    tsc = shutil.which("tsc")
    node_modules = ROOT / "api" / "node_modules"
    if tsc and node_modules.exists():
        proc = subprocess.run([tsc, "--noEmit"], cwd=ROOT / "api", check=False, text=True, capture_output=True)
        result["tsc_checked"] = True
        result["tsc_returncode"] = proc.returncode
        result["tsc_stdout_tail"] = proc.stdout[-2000:]
        result["tsc_stderr_tail"] = proc.stderr[-2000:]
        if proc.returncode != 0:
            result["ok"] = False
            issues.append("TypeScript no-emit build failed")
            result["issues"] = issues
    elif tsc:
        result["tsc_checked"] = False
        result["tsc_skipped_reason"] = "api/node_modules is absent; regex/source contract checks still ran"
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-npm", action="store_true", help="Run npm build/contract if npm is available")
    parser.add_argument("--out", default="")
    args = parser.parse_args()
    result = source_check()
    if args.run_npm and result["ok"]:
        try:
            proc = subprocess.run(
                ["npm", "run", "ci:api"], cwd=ROOT / "api", check=False, text=True, capture_output=True
            )
            result["mode"] = "npm"
            result["npm_returncode"] = proc.returncode
            result["npm_stdout_tail"] = proc.stdout[-2000:]
            result["npm_stderr_tail"] = proc.stderr[-2000:]
            result["ok"] = proc.returncode == 0
        except FileNotFoundError:
            result["mode"] = "source-npm-missing"
            result["npm_missing"] = True
    text = json.dumps(result, indent=2, sort_keys=True)
    print(text)
    if args.out:
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.out).write_text(text + "\n", encoding="utf-8")
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
