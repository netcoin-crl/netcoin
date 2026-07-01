"""SSRF guard for merchant webhook URLs (apps.assert_public_webhook_url).

These run with the escape hatch OFF (production behavior)."""
import pytest
from netcoin.apps import assert_public_webhook_url, AppError


@pytest.fixture(autouse=True)
def _block(monkeypatch):
    monkeypatch.delenv("NETCOIN_ALLOW_PRIVATE_WEBHOOKS", raising=False)


@pytest.mark.parametrize("bad", [
    "http://example.com/hook",             # not https
    "https://localhost/hook",              # localhost name
    "https://127.0.0.1/hook",              # loopback
    "https://10.0.0.5/hook",               # private
    "https://192.168.1.10/hook",           # private
    "https://172.16.0.1/hook",             # private
    "https://169.254.169.254/latest",      # link-local / cloud metadata
    "https://[::1]/hook",                  # IPv6 loopback
    "ftp://example.com",                   # bad scheme
    "https:///nohost",                     # no host
])
def test_rejects_ssrf_targets(bad):
    with pytest.raises(AppError):
        assert_public_webhook_url(bad)


@pytest.mark.parametrize("ok", ["https://8.8.8.8/hook", "https://1.1.1.1:443/events"])
def test_allows_public_https(ok):
    assert assert_public_webhook_url(ok) is None


def test_escape_hatch_allows_localhost(monkeypatch):
    monkeypatch.setenv("NETCOIN_ALLOW_PRIVATE_WEBHOOKS", "1")
    assert assert_public_webhook_url("http://127.0.0.1:9000/hook") is None
