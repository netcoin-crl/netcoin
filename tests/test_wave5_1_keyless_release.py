from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_release_workflow_uses_github_oidc_keyless_signing():
    workflow = read(".github/workflows/release.yml")
    assert "id-token: write" in workflow
    assert "sigstore/cosign-installer" in workflow
    assert "cosign sign-blob" in workflow
    assert "cosign verify-blob" in workflow
    assert '--certificate-identity "$CERT_IDENTITY"' in workflow
    assert '--certificate-oidc-issuer "$OIDC_ISSUER"' in workflow
    assert "https://token.actions.githubusercontent.com" in workflow
    assert "python tools/verify_release.py dist" in workflow
    assert "--require-keyless" in workflow
    assert "dist/*.sigstore.json" in workflow


def test_verify_release_supports_required_keyless_mode():
    verifier = read("tools/verify_release.py")
    assert "--require-keyless" in verifier
    assert "verify_keyless_signatures" in verifier
    assert "missing keyless signature bundle" in verifier
    assert "--certificate-identity is required for keyless verification" in verifier
    assert '"verify-blob"' in verifier


def test_release_docs_explain_keyless_identity_pinning():
    docs = read("docs/REPRODUCIBLE_RELEASES.md") + "\n" + read("docs/RELEASING.md")
    assert "Sigstore keyless" in docs
    assert "--require-keyless" in docs
    assert "https://github.com/OWNER/REPO/.github/workflows/release.yml@refs/tags/vX.Y.Z" in docs
    assert "https://token.actions.githubusercontent.com" in docs
