import pytest


@pytest.fixture(autouse=True)
def _allow_local_webhooks(monkeypatch):
    """Most webhook tests deliver to a local http server, so enable the SSRF
    escape hatch by default in the test suite. Tests that assert the production
    (blocking) behavior clear this env var themselves."""
    monkeypatch.setenv("NETCOIN_ALLOW_PRIVATE_WEBHOOKS", "1")
