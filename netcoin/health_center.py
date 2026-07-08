"""Product health-center helpers for NetCoin operator and exchange dashboards.

The health center is intentionally read-only. It collects existing signals from
chain, node, app storage, docs, release files, and public site assets into a
single dashboard payload so the UI can show real operational status without
hard-coding JSON blobs.
"""

from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path
from typing import Any

from .feature_catalog import feature_catalog
from .metrics import collect_metrics, evaluate_alerts


def _ok(name: str, status: str, detail: str = "", **extra: Any) -> dict[str, Any]:
    return {"name": name, "status": status, "detail": detail, **extra}


def _root(root: str | Path | None = None) -> Path:
    return Path(root or Path(__file__).resolve().parents[1]).resolve()


def site_inventory(root: str | Path | None = None) -> dict[str, Any]:
    base = _root(root)
    sites_dir = base / "sites"
    sites: list[dict[str, Any]] = []
    if sites_dir.exists():
        for folder in sorted(p for p in sites_dir.iterdir() if p.is_dir() and p.name not in {"shared", "tests"}):
            index = folder / "index.html"
            js_files = sorted(p.name for p in folder.glob("*.js"))
            css_files = sorted(p.name for p in folder.glob("*.css"))
            html = index.read_text(encoding="utf-8", errors="ignore") if index.exists() else ""
            sites.append(
                {
                    "site": folder.name,
                    "index": index.exists(),
                    "scripts": js_files,
                    "styles": css_files,
                    "shared_shell": "site-shell.js" in js_files and "site-shell.css" in css_files,
                    "feature_dock": "site-shell.js" in html or "site-nav" in html,
                }
            )
    return {
        "site_count": len(sites),
        "sites": sites,
        "missing_shell": [s["site"] for s in sites if not s["shared_shell"]],
        "missing_index": [s["site"] for s in sites if not s["index"]],
    }


def release_trust_status(root: str | Path | None = None) -> dict[str, Any]:
    base = _root(root)
    tools = base / "tools"
    files = {
        "sbom": tools / "generate_sbom.py",
        "sign_release": tools / "sign_release.py",
        "verify_signature": tools / "verify_signature.py",
        "provenance": tools / "generate_provenance.py",
        "verify_provenance": tools / "verify_provenance.py",
    }
    present = {k: v.exists() for k, v in files.items()}
    score = sum(1 for ok in present.values() if ok)
    return {
        "score": score,
        "max_score": len(present),
        "status": "healthy" if score == len(present) else "partial",
        "checks": present,
    }


def feature_status(root: str | Path | None = None) -> dict[str, Any]:
    base = _root(root)
    catalog = feature_catalog()
    features = []
    if isinstance(catalog, dict):
        for items in catalog.get("groups", {}).values():
            if isinstance(items, list):
                features.extend(items)
        if not features and isinstance(catalog.get("features"), list):
            features = catalog.get("features", [])
    anchors = {
        "wallet": [base / "sites" / "wallet" / "index.html", base / "netcoin" / "wallet.py"],
        "markets": [base / "sites" / "markets" / "index.html", base / "netcoin" / "apps" / "markets"],
        "explorer": [base / "sites" / "explorer" / "index.html", base / "netcoin" / "indexer.py"],
        "community": [base / "sites" / "community" / "index.html"],
        "faucet": [base / "sites" / "faucet" / "index.html", base / "netcoin" / "faucet_abuse.py"],
        "exchange": [base / "sites" / "exchange" / "index.html", base / "netcoin" / "exchange.py"],
        "operator": [base / "sites" / "operator" / "index.html", base / "netcoin" / "health_center.py"],
        "release": [base / "tools" / "verify_provenance.py", base / "tools" / "verify_signature.py"],
    }
    areas = []
    for name, paths in anchors.items():
        found = [str(p.relative_to(base)) for p in paths if p.exists()]
        areas.append(
            {
                "area": name,
                "status": "working" if len(found) == len(paths) else "partial" if found else "missing",
                "artifacts": found,
                "expected": [str(p.relative_to(base)) for p in paths],
            }
        )
    return {
        "catalog_count": len(features),
        "areas": areas,
        "partial_or_missing": [a for a in areas if a["status"] != "working"],
    }


def api_contract_depth(root: str | Path | None = None) -> dict[str, Any]:
    base = _root(root)
    paths = []
    for candidate in (base / "docs" / "openapi.yaml", base / "sites" / "api" / "openapi.yaml"):
        if not candidate.exists():
            continue
        for line in candidate.read_text(encoding="utf-8", errors="ignore").splitlines():
            stripped = line.strip()
            if stripped.startswith("/") and stripped.endswith(":"):
                paths.append(stripped[:-1])
    unique = sorted(set(paths))
    return {
        "documented_paths": len(unique),
        "has_market_routes": any("/markets" in p for p in unique),
        "has_community_routes": any("/community" in p for p in unique),
        "has_health_center": any("/health-center" in p for p in unique),
        "sample": unique[:25],
    }


def build_health_center(
    *,
    root: str | Path | None = None,
    chain: Any | None = None,
    node: Any | None = None,
    store: Any | None = None,
) -> dict[str, Any]:
    base = _root(root)
    generated_at = int(time.time())
    metrics: dict[str, int | float] = {}
    alerts: list[dict[str, Any]] = []
    if chain is not None:
        try:
            metrics = collect_metrics(chain, node=node, app=store)
            alerts = evaluate_alerts(metrics)
        except Exception as exc:  # dashboard payload must not break the node
            metrics = {"netcoin_metrics_error": 1}
            alerts = [{"alert": "NetCoinHealthCollectionError", "severity": "warning", "message": str(exc)}]
    inventory = site_inventory(base)
    features = feature_status(base)
    try:
        from .feature_status import live_feature_status

        live_features = live_feature_status(base)
    except Exception:
        live_features = {"summary": {}, "probes": []}
    release = release_trust_status(base)
    contract = api_contract_depth(base)
    checks = [
        _ok(
            "sites",
            "healthy" if not inventory["missing_shell"] and not inventory["missing_index"] else "partial",
            f"{inventory['site_count']} public sites",
        ),
        _ok(
            "features",
            "healthy" if not features["partial_or_missing"] else "partial",
            f"{features['catalog_count']} catalog entries",
        ),
        _ok("release", release["status"], f"{release['score']}/{release['max_score']} trust tools"),
        _ok(
            "api",
            "healthy" if contract["documented_paths"] >= 20 else "partial",
            f"{contract['documented_paths']} documented paths",
        ),
        _ok("alerts", "healthy" if not alerts else "warning", f"{len(alerts)} active alerts"),
    ]
    status = "healthy"
    if any(c["status"] in {"warning", "partial"} for c in checks):
        status = "partial"
    if any(a.get("severity") == "critical" for a in alerts):
        status = "critical"
    digest = hashlib.sha256(json.dumps({"checks": checks, "metrics": metrics}, sort_keys=True).encode()).hexdigest()
    return {
        "status": status,
        "generated_at": generated_at,
        "fingerprint": digest,
        "checks": checks,
        "metrics": metrics,
        "alerts": alerts,
        "sites": inventory,
        "features": features,
        "live_features": live_features,
        "release": release,
        "api_contract": contract,
    }
