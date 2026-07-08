.PHONY: install-dev test test-fast test-full test-report ci-local lint format typecheck coverage release-check provenance-check upgrade-healthcheck ops-bundle site-audit site-sync product-check arch-check migration-check rust-workspace-check ts-api-check parity-check full-suite-report devnet fuzz browser-test browser-e2e browser-e2e-local openapi-contract security-check clean

PYTHON ?= python
PIP ?= $(PYTHON) -m pip

install-dev:
	$(PIP) install -e ".[dev]"

format:
	$(PYTHON) -m black netcoin tests tools
	$(PYTHON) -m ruff check --fix netcoin tests tools

lint:
	$(PYTHON) -m ruff check netcoin tests tools
	$(PYTHON) -m black --check netcoin tests tools

typecheck:
	$(PYTHON) -m mypy

test-fast:
	$(PYTHON) tools/run_test_suite_by_file.py --timeout 180 --files tests/test_protocol_vectors.py tests/test_reorg.py tests/test_markets_upgrade.py tests/test_polymarket_style_markets.py tests/test_professional_code_upgrades.py tests/test_gap_fixes.py

test:
	$(PYTHON) tools/run_test_suite_by_file.py --timeout 180

test-full:
	$(PYTHON) tools/full_suite_report.py --run --timeout 240 --out reports/full_suite_report.json

test-report:
	$(PYTHON) tools/full_suite_report.py --out reports/full_suite_plan.json

ci-local: lint typecheck release-check product-check arch-check migration-check rust-workspace-check ts-api-check parity-check site-audit test-fast

coverage:
	$(PYTHON) -m pytest -q --cov=netcoin --cov-report=term-missing --cov-report=xml

fuzz:
	$(PYTHON) -X dev -m netcoin fuzz --target all --iterations 500 --max-bytes 256
	$(PYTHON) tools/mutation_consensus_smoke.py

browser-test:
	cd webwallet-browser && npm ci && npm test

browser-e2e:
	npx playwright test webwallet-browser/tests/e2e sites/tests/e2e

browser-e2e-local:
	$(PYTHON) tools/run_browser_e2e.py

openapi-contract:
	$(PYTHON) tools/check_openapi_contract.py

security-check:
	$(PYTHON) -m bandit -r netcoin -x tests

release-check:
	$(PYTHON) -m compileall -q netcoin tools
	$(PYTHON) tools/professional_upgrade_audit.py --fail-on-issues
	$(PYTHON) tools/check_openapi_contract.py
	$(PYTHON) tools/generate_sbom.py --out dist/netcoin-sbom.json
	chmod +x tools/make_release.sh && tools/make_release.sh HEAD
	cd dist && sha256sum -c SHA256SUMS

devnet:
	NETCOIN_BACKEND=sqlite $(PYTHON) -m netcoin node --host 127.0.0.1 --port 28444 --p2p-port 28445 --data .netcoin-devnet

clean:
	rm -rf build dist *.egg-info .pytest_cache .mypy_cache .ruff_cache htmlcov coverage.xml

provenance-check:
	mkdir -p dist
	printf netcoin > dist/provenance-smoke.txt
	$(PYTHON) tools/generate_provenance.py dist/provenance-smoke.txt --out dist/provenance-smoke.provenance.json
	$(PYTHON) tools/verify_provenance.py dist/provenance-smoke.txt dist/provenance-smoke.provenance.json

upgrade-healthcheck:
	$(PYTHON) tools/upgrade_healthcheck.py

ops-bundle:
	mkdir -p dist
	$(PYTHON) tools/generate_ops_bundle.py --out dist/netcoin-ops-bundle.json

site-sync:
	$(PYTHON) tools/sync_site_assets.py

site-audit:
	$(PYTHON) tools/audit_site_ui.py

product-check:
	$(PYTHON) tools/check_product_surface.py

arch-check:
	$(PYTHON) tools/check_architecture_space.py

migration-check:
	$(PYTHON) tools/check_migration_parity.py

rust-workspace-check:
	$(PYTHON) tools/check_rust_workspace.py

ts-api-check:
	$(PYTHON) tools/check_ts_workspace.py

parity-check:
	$(PYTHON) tools/run_parity_suite.py

full-suite-report:
	$(PYTHON) tools/full_suite_report.py

v022-check: parity-check rust-workspace-check ts-api-check migration-check
	$(PYTHON) -m pytest -q tests/test_v022_rust_ts_parity_expansion.py
