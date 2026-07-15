from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SITES = ROOT / "sites"


def read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_no_site_js_throws_a_raw_unparsed_response_body_as_an_error_message():
    """Regression: wallet-app.js, exchange.js, operator.js, and
    explorer-app.js all had the same bug — on a non-JSON response (a raw
    nginx 502/504 HTML error page, a proxy timeout page, etc.) the entire
    response body was stashed under an `error` key and then thrown/displayed
    verbatim to the user. Any site JS that stores the unparsed fetch body
    under a literal `error` key is doing this; `raw`/`text` keys are fine
    since nothing reads `.error` off of them.
    """
    offenders = []
    for js_path in sorted(SITES.rglob("*.js")):
        if "node_modules" in js_path.parts:
            continue
        text = js_path.read_text(encoding="utf-8")
        for needle in ("{error:text}", "{ error: text }", "{error:txt}", "{ error: txt }"):
            if needle in text:
                offenders.append(str(js_path.relative_to(ROOT)))
                break
    assert offenders == [], f"raw response body reachable as .error in: {offenders}"


def test_fixed_files_use_the_parsed_guard_pattern():
    for rel in ("sites/exchange/exchange.js", "sites/operator/operator.js", "sites/explorer/explorer-app.js"):
        js = read(rel)
        assert "parsed" in js, f"{rel} missing the parsed-response guard"
        assert "non-JSON response" in js, f"{rel} missing the safe fallback message"
