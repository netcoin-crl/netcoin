from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_developers_index_links_to_the_console():
    html = read("sites/developers/index.html")
    assert 'href="console.html"' in html


def test_console_page_has_the_expected_structure():
    html = read("sites/developers/console.html")
    assert 'id="developerId"' in html
    assert 'id="statsGrid"' in html
    assert 'id="policyBody"' in html
    assert 'id="deadLettersTable"' in html
    assert 'id="depositsTable"' in html
    assert "<script>" not in html
    assert "Content-Security-Policy" in html
    assert "script-src 'self'" in html


def test_console_js_calls_the_real_developer_endpoints_only():
    js = read("sites/developers/console.js")
    assert "/developer/console" in js
    assert "/developer/webhook-events/dead-letters" in js
    assert "/developer/webhook-events/deliver" in js
    assert "/developer/deposits" in js
    assert "/developer/funding-policy" in js
    assert "event_id" in js


def test_console_js_syntax_is_valid():
    import subprocess
    import shutil

    node = shutil.which("node")
    if not node:
        return
    result = subprocess.run(
        [node, "--check", str(ROOT / "sites/developers/console.js")], capture_output=True, text=True
    )
    assert result.returncode == 0, result.stdout + result.stderr
