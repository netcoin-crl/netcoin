"""M1 faucet CAPTCHA and per-address rate-limit hardening."""

from __future__ import annotations

import importlib.util
import time
from pathlib import Path

from netcoin.captcha_provider import CaptchaConfig, load_captcha_config


def load_faucet_module():
    path = Path(__file__).resolve().parents[1] / "tools" / "faucet_server.py"
    spec = importlib.util.spec_from_file_location("netcoin_faucet_server_m1_hardening", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_captcha_provider_accepts_faucet_specific_environment_aliases():
    cfg = load_captcha_config(
        {
            "NETCOIN_FAUCET_CAPTCHA_PROVIDER": "turnstile",
            "NETCOIN_FAUCET_CAPTCHA_SECRET": "secret-from-host",
        }
    )
    assert cfg.provider == "turnstile"
    assert cfg.secret == "secret-from-host"
    assert cfg.verify_url.endswith("/siteverify")


def test_captcha_token_from_form_supports_turnstile_hcaptcha_and_generic_field():
    faucet = load_faucet_module()
    assert faucet.captcha_token_from_form({"cf-turnstile-response": ["turnstile-token"]}) == "turnstile-token"
    assert faucet.captcha_token_from_form({"h-captcha-response": ["hcaptcha-token"]}) == "hcaptcha-token"
    assert faucet.captcha_token_from_form({"captcha_token": ["generic-token"]}) == "generic-token"
    assert faucet.captcha_token_from_form({}) == ""


def test_verify_captcha_delegates_to_provider_adapter(monkeypatch):
    faucet = load_faucet_module()
    monkeypatch.setattr(faucet, "CAPTCHA_PROVIDER", "turnstile")
    monkeypatch.setattr(faucet, "CAPTCHA_SECRET", "host-secret")
    monkeypatch.setattr(faucet, "CAPTCHA_VERIFY_URL", "")
    captured = {}

    def fake_verify_token(token, *, remote_ip, config, timeout=10):
        captured["token"] = token
        captured["remote_ip"] = remote_ip
        captured["config"] = config
        captured["timeout"] = timeout
        return {"ok": True, "provider": "turnstile"}

    monkeypatch.setattr(faucet, "verify_token", fake_verify_token)
    ok, reason = faucet.verify_captcha({"cf-turnstile-response": ["token-123"]}, "203.0.113.4")
    assert ok is True
    assert reason == "turnstile"
    assert captured["token"] == "token-123"
    assert captured["remote_ip"] == "203.0.113.4"
    assert captured["config"] == CaptchaConfig(provider="turnstile", secret="host-secret", verify_url="")


def test_verify_captcha_rejects_missing_provider_secret(monkeypatch):
    faucet = load_faucet_module()
    monkeypatch.setattr(faucet, "CAPTCHA_PROVIDER", "hcaptcha")
    monkeypatch.setattr(faucet, "CAPTCHA_SECRET", "")
    ok, reason = faucet.verify_captcha({"h-captcha-response": ["token"]}, "203.0.113.4")
    assert ok is False
    assert "missing CAPTCHA secret" in reason


def test_address_rate_limit_blocks_same_address_across_ips(monkeypatch):
    faucet = load_faucet_module()
    monkeypatch.setattr(faucet, "ADDRESS_COOLDOWN_SECONDS", 3600)
    now = int(time.time())
    monkeypatch.setattr(faucet.time, "time", lambda: now)
    state = {
        "requests": [{"ip": "203.0.113.10", "address": "Nsame", "timestamp": now - 60}],
        "queue": [{"ip": "203.0.113.11", "address": "Nqueued", "timestamp": now - 120, "status": "queued"}],
    }
    limited, remaining = faucet.address_rate_limited("Nsame", state)
    assert limited is True
    assert remaining == 3540

    queued_limited, queued_remaining = faucet.address_rate_limited("Nqueued", state)
    assert queued_limited is True
    assert queued_remaining == 3480

    other_limited, other_remaining = faucet.address_rate_limited("Nnew", state)
    assert other_limited is False
    assert other_remaining == 0


def test_env_example_documents_no_secret_commitment():
    text = (Path(__file__).resolve().parents[1] / ".env.example").read_text()
    assert "NETCOIN_FAUCET_CAPTCHA_PROVIDER" in text
    assert "NETCOIN_FAUCET_CAPTCHA_SECRET" in text
    assert "replace-with-provider-secret" in text
    assert "Do not commit real site keys or secrets" in text
