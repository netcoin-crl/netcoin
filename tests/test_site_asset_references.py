import re
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
SITES = ROOT / "sites"


def _is_local(url: str) -> bool:
    if not url or url.startswith(("#", "data:", "mailto:", "tel:")):
        return False
    parsed = urlsplit(url)
    return parsed.scheme == "" and parsed.netloc == ""


def _strip_query(url: str) -> str:
    return urlsplit(url).path


def test_all_site_indexes_reference_existing_local_scripts_and_stylesheets():
    missing = []
    for index in sorted(SITES.glob("*/index.html")):
        html = index.read_text()
        refs = re.findall(r'<script[^>]+src="([^"]+)"', html)
        refs += re.findall(r'<link[^>]+href="([^"]+)"', html)
        for ref in refs:
            if not _is_local(ref):
                continue
            target = (index.parent / _strip_query(ref)).resolve()
            if not target.exists():
                missing.append(f"{index.relative_to(ROOT)} -> {ref}")
    assert missing == []


def test_markets_site_loads_real_markets_app_not_missing_labs_script():
    html = (SITES / "markets" / "index.html").read_text()
    assert "markets.js" in html
    assert "labs.js" not in html
    assert (SITES / "markets" / "markets.js").exists()


def test_shared_site_shell_wrappers_have_existing_targets():
    assert (SITES / "shared" / "site-shell.css").exists()
    assert (SITES / "shared" / "site-shell.js").exists()
    for wrapper in sorted(SITES.glob("*/site-shell.css")):
        if wrapper.parent.name == "shared":
            continue
        text = wrapper.read_text()
        assert "../shared/site-shell.css" in text
    for wrapper in sorted(SITES.glob("*/site-shell.js")):
        if wrapper.parent.name == "shared":
            continue
        text = wrapper.read_text()
        assert "../shared/site-shell.js" in text
