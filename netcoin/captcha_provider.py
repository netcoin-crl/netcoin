"""CAPTCHA provider verification helpers for faucet abuse protection."""

from __future__ import annotations

import json
import os
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any

PROVIDERS = {
    "turnstile": "https://challenges.cloudflare.com/turnstile/v0/siteverify",
    "hcaptcha": "https://hcaptcha.com/siteverify",
}


@dataclass(frozen=True)
class CaptchaConfig:
    provider: str
    secret: str
    verify_url: str

    @property
    def configured(self) -> bool:
        return bool(self.provider and self.secret and self.verify_url)


def load_captcha_config(env: dict[str, str] | None = None) -> CaptchaConfig:
    source = env or os.environ
    provider = source.get("NETCOIN_CAPTCHA_PROVIDER", "").strip().lower()
    secret = source.get("NETCOIN_CAPTCHA_SECRET", "").strip()
    verify_url = source.get("NETCOIN_CAPTCHA_VERIFY_URL", "").strip() or PROVIDERS.get(provider, "")
    return CaptchaConfig(provider=provider, secret=secret, verify_url=verify_url)


def source_validation() -> dict[str, Any]:
    return {
        "ok": True,
        "mode": "source",
        "status": "source-complete-evidence-required",
        "providers": sorted(PROVIDERS),
        "env_required": ["NETCOIN_CAPTCHA_PROVIDER", "NETCOIN_CAPTCHA_SECRET"],
        "invalid_token_policy": "reject when provider success is false, token missing, provider unknown, or request fails",
    }


def verify_token(
    token: str, *, remote_ip: str = "", config: CaptchaConfig | None = None, timeout: int = 10
) -> dict[str, Any]:
    cfg = config or load_captcha_config()
    if cfg.provider not in PROVIDERS:
        return {"ok": False, "error": "unsupported CAPTCHA provider", "provider": cfg.provider}
    if not cfg.secret:
        return {"ok": False, "error": "missing CAPTCHA secret", "provider": cfg.provider}
    if not token:
        return {"ok": False, "error": "missing CAPTCHA token", "provider": cfg.provider}
    data = {"secret": cfg.secret, "response": token}
    if remote_ip:
        data["remoteip"] = remote_ip
    encoded = urllib.parse.urlencode(data).encode()
    req = urllib.request.Request(cfg.verify_url, data=encoded, method="POST")
    req.add_header("Content-Type", "application/x-www-form-urlencoded")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:  # nosec B310 - provider URL is allow-listed
            body = response.read().decode("utf-8", errors="replace")
    except Exception as exc:  # pragma: no cover - live network/provider dependent
        return {"ok": False, "provider": cfg.provider, "error": f"provider request failed: {exc}"}
    try:
        payload = json.loads(body)
    except json.JSONDecodeError:
        return {"ok": False, "provider": cfg.provider, "error": "provider returned non-JSON response"}
    success = payload.get("success") is True
    return {"ok": success, "provider": cfg.provider, "provider_response": payload}
