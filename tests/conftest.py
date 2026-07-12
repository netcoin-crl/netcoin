import pytest


@pytest.fixture(autouse=True)
def _allow_local_webhooks(monkeypatch):
    """Most webhook tests deliver to a local http server, so enable the SSRF
    escape hatch by default in the test suite. Tests that assert the production
    (blocking) behavior clear this env var themselves."""
    monkeypatch.setenv("NETCOIN_ALLOW_PRIVATE_WEBHOOKS", "1")


def pytest_collection_modifyitems(config, items):
    markexpr = (getattr(config.option, "markexpr", "") or "").strip()
    localnet_enabled = "localnet" in markexpr or config.getoption("run_localnet", default=False)
    if localnet_enabled:
        return
    skip_localnet = pytest.mark.skip(reason="localnet tests require -m localnet or --run-localnet")
    for item in items:
        if "localnet" in item.keywords:
            item.add_marker(skip_localnet)


def pytest_addoption(parser):
    parser.addoption(
        "--run-localnet",
        action="store_true",
        default=False,
        help="run multi-node localnet tests that spawn real netcoin node processes",
    )
