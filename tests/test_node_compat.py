"""Client-side remote-node compatibility warnings (helps diagnose a seed that
runs an older NetCoin than the CLI)."""
import netcoin.cli as cli
from netcoin.params import NODE_VERSION, PROTOCOL_VERSION


def _patch_info(monkeypatch, node):
    monkeypatch.setattr(cli, "get_json", lambda url: {"node": node})


def test_warns_when_node_reports_no_version(monkeypatch, capsys):
    # An old seed: correct protocol but no version field (predates the handshake).
    _patch_info(monkeypatch, {"protocol_version": PROTOCOL_VERSION, "services": ["block-template"]})
    cli.warn_if_node_incompatible("http://seed")
    err = capsys.readouterr().err
    assert "may be incompatible" in err and "predates v0.4.x" in err


def test_warns_on_protocol_mismatch(monkeypatch, capsys):
    _patch_info(monkeypatch, {"protocol_version": PROTOCOL_VERSION + 1, "version": "9.9.9", "services": []})
    cli.warn_if_node_incompatible("http://seed")
    assert "protocol v" in capsys.readouterr().err


def test_warns_on_missing_required_service(monkeypatch, capsys):
    _patch_info(monkeypatch, {"protocol_version": PROTOCOL_VERSION, "version": NODE_VERSION, "services": ["mempool"]})
    cli.warn_if_node_incompatible("http://seed", need_service="block-template")
    assert "missing 'block-template'" in capsys.readouterr().err


def test_no_warning_for_compatible_node(monkeypatch, capsys):
    _patch_info(monkeypatch, {"protocol_version": PROTOCOL_VERSION, "version": NODE_VERSION, "services": ["block-template", "mempool"]})
    cli.warn_if_node_incompatible("http://seed", need_service="block-template")
    assert capsys.readouterr().err == ""


def test_unreachable_node_is_silent(monkeypatch, capsys):
    def boom(url):
        raise OSError("connection refused")

    monkeypatch.setattr(cli, "get_json", boom)
    cli.warn_if_node_incompatible("http://seed")  # must not raise
    assert capsys.readouterr().err == ""
