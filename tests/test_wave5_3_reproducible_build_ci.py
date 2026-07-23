from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def load_comparator():
    spec = importlib.util.spec_from_file_location(
        "compare_reproducible_builds",
        ROOT / "tools" / "compare_reproducible_builds.py",
    )
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_compare_reproducible_builds_reports_matching_hashes(tmp_path: Path):
    comparator = load_comparator()
    local = tmp_path / "local.tar.gz"
    docker = tmp_path / "docker.tar.gz"
    local.write_bytes(b"netcoin")
    docker.write_bytes(b"netcoin")

    report = comparator.build_report(local, docker)
    assert report["ok"] is True
    assert report["schema"] == "netcoin-independent-repro-build-v1"
    assert report["local_sha256"] == report["docker_sha256"]
    assert "third-party maintainer rebuild" in report["does_not_claim"]


def test_compare_reproducible_builds_detects_mismatch(tmp_path: Path):
    comparator = load_comparator()
    local = tmp_path / "local.tar.gz"
    docker = tmp_path / "docker.tar.gz"
    local.write_bytes(b"one")
    docker.write_bytes(b"two")

    report = comparator.build_report(local, docker)
    assert report["ok"] is False
    assert report["local_sha256"] != report["docker_sha256"]


def test_reproducible_builder_displays_outside_repo_archive_paths(tmp_path: Path):
    spec = importlib.util.spec_from_file_location(
        "verify_reproducible_build",
        ROOT / "tools" / "verify_reproducible_build.py",
    )
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)

    outside = tmp_path / "netcoin-source.tar.gz"
    assert module.display_path(outside) == str(outside)


def test_dockerfile_uses_shared_python_repro_builder():
    dockerfile = read("Dockerfile.repro")
    assert "tools/verify_reproducible_build.py" in dockerfile
    assert "--archive dist/netcoin-${NETCOIN_VERSION}-source.tar.gz" in dockerfile
    assert "tar --sort=name" not in dockerfile


def test_reproducible_build_workflow_compares_docker_and_local_outputs():
    workflow = read(".github/workflows/reproducible-build.yml")
    assert "docker build" in workflow
    assert "--output type=local,dest=/tmp/netcoin-repro-docker" in workflow
    assert "tools/compare_reproducible_builds.py" in workflow
    assert "reports/m2_evidence/independent_repro_build.json" in workflow
    assert "actions/upload-artifact@ea165f8d65b6e75b540449e92b4886f43607fa02 # v4" in workflow


def test_reproducible_build_docs_and_make_target_are_wired():
    docs = read("docs/REPRODUCIBLE_BUILDS.md")
    makefile = read("Makefile")
    assert "compare_reproducible_builds.py" in docs
    assert "netcoin-independent-repro-build-v1" in docs
    assert "reproducible-build-check" in makefile
