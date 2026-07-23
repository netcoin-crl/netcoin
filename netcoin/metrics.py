"""Prometheus metrics and alert evaluation for NetCoin."""

from __future__ import annotations

import time
from typing import Any


def _line(name: str, value: int | float, labels: dict[str, str] | None = None) -> str:
    if labels:
        rendered = ",".join(f'{k}="{v}"' for k, v in sorted(labels.items()))
        return f"{name}{{{rendered}}} {value}"
    return f"{name} {value}"


def collect_metrics(chain: Any, node: Any | None = None, app: Any | None = None) -> dict[str, int | float]:
    info = (
        chain.chain_info()
        if hasattr(chain, "chain_info")
        else {
            "height": getattr(chain, "height", lambda: 0)(),
            "mempool_transactions": len(getattr(chain, "mempool", [])),
        }
    )
    metrics: dict[str, int | float] = {
        "netcoin_block_height": int(info.get("height", 0)),
        "netcoin_mempool_transactions": int(info.get("mempool_transactions", len(getattr(chain, "mempool", [])))),
        "netcoin_peer_count": len(getattr(node, "peers", [])) if node is not None else 0,
        "netcoin_reorg_count": int(getattr(chain, "reorg_count", 0) or 0),
        "netcoin_orphan_count": (
            int(info.get("orphan_candidates", len(getattr(chain, "orphan_blocks", {}))))
            if isinstance(info, dict)
            else 0
        ),
        "netcoin_timestamp": int(time.time()),
    }
    if app is not None:
        try:
            data = app.load()
            metrics.update(
                {
                    "netcoin_market_count": len(data.get("prediction_markets", {})),
                    "netcoin_faucet_request_count": len(data.get("faucet_requests", [])),
                    "netcoin_webhook_dead_letters": sum(
                        1 for e in data.get("webhook_events", []) if e.get("dead_letter")
                    ),
                }
            )
        except Exception:
            metrics["netcoin_app_metrics_error"] = 1
    return metrics


def prometheus_text(metrics: dict[str, int | float]) -> str:
    lines = ["# HELP netcoin_info NetCoin exported metrics.", "# TYPE netcoin_info gauge", "netcoin_info 1"]
    for name, value in sorted(metrics.items()):
        kind = "counter" if name.endswith("_count") else "gauge"
        lines.append(f"# TYPE {name} {kind}")
        lines.append(_line(name, value))
    return "\n".join(lines) + "\n"


def evaluate_alerts(
    metrics: dict[str, int | float],
    *,
    previous_height: int | None = None,
    previous_timestamp: int | None = None,
    stuck_seconds: int = 1800,
) -> list[dict[str, Any]]:
    alerts = []
    current_height = int(metrics.get("netcoin_block_height", 0))
    current_ts = int(metrics.get("netcoin_timestamp", time.time()))
    if (
        previous_height is not None
        and previous_timestamp is not None
        and current_height <= int(previous_height)
        and current_ts - int(previous_timestamp) >= int(stuck_seconds)
    ):
        alerts.append(
            {
                "alert": "NetCoinStuckChain",
                "severity": "critical",
                "message": "Block height has not advanced within the stuck-chain window.",
            }
        )
    if int(metrics.get("netcoin_peer_count", 0)) == 0:
        alerts.append({"alert": "NetCoinNoPeers", "severity": "warning", "message": "Node has zero known peers."})
    if int(metrics.get("netcoin_webhook_dead_letters", 0)) > 0:
        alerts.append(
            {
                "alert": "NetCoinWebhookDeadLetters",
                "severity": "warning",
                "message": "Webhook delivery has dead-letter events.",
            }
        )
    return alerts


class MetricsHistory:
    """Tiny in-memory metric history for local alert comparisons and dashboards."""

    def __init__(self, max_points: int = 288):
        self.max_points = int(max_points)
        self.points: list[dict[str, int | float]] = []

    def add(self, metrics: dict[str, int | float]) -> dict[str, int | float]:
        item = dict(metrics)
        item.setdefault("netcoin_timestamp", int(time.time()))
        self.points.append(item)
        if len(self.points) > self.max_points:
            self.points = self.points[-self.max_points :]
        return item

    def latest(self) -> dict[str, int | float]:
        return self.points[-1] if self.points else {}

    def previous(self) -> dict[str, int | float]:
        return self.points[-2] if len(self.points) >= 2 else {}

    def evaluate(self, *, stuck_seconds: int = 1800) -> list[dict[str, Any]]:
        latest = self.latest()
        previous = self.previous()
        return evaluate_alerts(
            latest,
            previous_height=int(previous.get("netcoin_block_height", 0)) if previous else None,
            previous_timestamp=int(previous.get("netcoin_timestamp", 0)) if previous else None,
            stuck_seconds=stuck_seconds,
        )


def service_health(metrics: dict[str, int | float], alerts: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    alerts = alerts or []
    critical = [a for a in alerts if a.get("severity") == "critical"]
    warning = [a for a in alerts if a.get("severity") == "warning"]
    status = "healthy" if not alerts else "degraded" if not critical else "critical"
    return {
        "status": status,
        "ok": not critical,
        "alert_count": len(alerts),
        "critical_count": len(critical),
        "warning_count": len(warning),
        "height": int(metrics.get("netcoin_block_height", 0)),
        "peers": int(metrics.get("netcoin_peer_count", 0)),
        "mempool_transactions": int(metrics.get("netcoin_mempool_transactions", 0)),
    }
