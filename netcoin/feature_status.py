"""Live feature status wiring for the NetCoin product catalog."""

from __future__ import annotations

from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any

from .feature_catalog import feature_catalog

ROOT = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class FeatureProbe:
    key: str
    label: str
    route: str
    files: tuple[str, ...]
    tests: tuple[str, ...] = ()


PROBES: tuple[FeatureProbe, ...] = (
    FeatureProbe(
        "wallet",
        "Wallet safety workflow",
        "/api/wallet/workflow",
        ("sites/wallet/index.html", "sites/wallet/wallet-app.js", "netcoin/wallet.py", "netcoin/live_product.py"),
        ("tests/test_v018_live_product_wiring.py",),
    ),
    FeatureProbe(
        "explorer",
        "Explorer live pages",
        "/api/explorer/address/{address}",
        (
            "sites/explorer/index.html",
            "sites/explorer/address.html",
            "sites/explorer/tx.html",
            "sites/explorer/block.html",
            "sites/explorer/mempool.html",
            "sites/explorer/explorer-pro.js",
            "netcoin/live_product.py",
            "netcoin/indexer.py",
        ),
        ("tests/test_v018_live_product_wiring.py",),
    ),
    FeatureProbe(
        "markets",
        "Markets trading workspace",
        "https://markets.netcoin.online",
        (
            "sites/markets/index.html",
            "sites/markets/trade.html",
            "sites/markets/portfolio.html",
            "sites/markets/disputes.html",
            "sites/markets/settlement.html",
            "netcoin/apps/markets",
        ),
        ("tests/test_polymarket_style_markets.py",),
    ),
    FeatureProbe(
        "faucet",
        "Faucet admin",
        "https://faucet.netcoin.online/admin.html",
        ("sites/faucet/admin.html", "netcoin/faucet_abuse.py"),
        ("tests/test_do_it_big_impact_fixes.py",),
    ),
    FeatureProbe(
        "exchange",
        "Exchange live custody dashboard",
        "/api/exchange/live",
        (
            "sites/exchange/index.html",
            "sites/exchange/exchange.js",
            "netcoin/exchange.py",
            "netcoin/exchange_reserves.py",
            "netcoin/live_product.py",
        ),
        ("tests/test_v018_live_product_wiring.py",),
    ),
    FeatureProbe(
        "operator",
        "Operator live controls",
        "/api/operator/live",
        (
            "sites/operator/index.html",
            "sites/operator/operator.js",
            "netcoin/health_center.py",
            "netcoin/live_product.py",
            "tools/generate_ops_bundle.py",
        ),
        ("tests/test_v018_live_product_wiring.py",),
    ),
    FeatureProbe(
        "release",
        "Release verification",
        "https://download.netcoin.online/verify.html",
        (
            "sites/download/verify.html",
            "tools/verify_signature.py",
            "tools/verify_provenance.py",
            "tools/generate_sbom.py",
        ),
        (),
    ),
    FeatureProbe(
        "browser_e2e",
        "Browser E2E runner",
        "make browser-e2e-local",
        ("tools/run_browser_e2e.py", "playwright.config.js", "sites/tests/e2e/product.spec.js"),
        (),
    ),
    FeatureProbe(
        "api_contract",
        "OpenAPI contract",
        "make openapi-contract",
        ("tools/check_openapi_contract.py", "docs/openapi.yaml", "sites/api/openapi.yaml"),
        (),
    ),
)


def _exists(rel: str, root: Path) -> bool:
    return (root / rel).exists()


def live_feature_status(root: str | Path | None = None) -> dict[str, Any]:
    base = Path(root) if root else ROOT
    records = []
    for probe in PROBES:
        files = [{"path": f, "exists": _exists(f, base)} for f in probe.files]
        tests = [{"path": t, "exists": _exists(t, base)} for t in probe.tests]
        present = sum(1 for f in files if f["exists"])
        expected = len(files)
        status = (
            "working"
            if present == expected and all(t["exists"] for t in tests)
            else "partial" if present else "missing"
        )
        records.append(
            {
                **asdict(probe),
                "files": files,
                "tests": tests,
                "present": present,
                "expected": expected,
                "status": status,
            }
        )
    summary = {s: sum(1 for r in records if r["status"] == s) for s in ("working", "partial", "missing")}
    return {"summary": summary, "probes": records, "catalog": feature_catalog()}
