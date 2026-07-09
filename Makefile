.PHONY: install-dev test test-fast test-full test-report ci-local lint format typecheck coverage release-check provenance-check upgrade-healthcheck ops-bundle site-audit site-sync product-check arch-check migration-check rust-workspace-check ts-api-check parity-check rust-consensus-parity-check rust-wallet-parity-check rust-markets-parity-check rust-signer-parity-check rust-p2p-parity-check rust-indexer-parity-check ts-openapi-codegen-check full-suite-report devnet fuzz browser-test browser-e2e browser-e2e-local openapi-contract security-check clean p2p-soak-check indexer-db-check ts-api-contract-check browser-e2e-matrix-check security-audit-prep-check v033-check v034-check v035-check v036-check v037-check

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

rust-consensus-parity-check:
	$(PYTHON) tools/run_rust_consensus_parity.py --allow-missing-cargo

rust-mempool-parity-check:
	$(PYTHON) tools/run_rust_mempool_parity.py --allow-missing-cargo

rust-wallet-parity-check:
	$(PYTHON) tools/run_rust_wallet_parity.py --allow-missing-cargo

rust-markets-parity-check:
	$(PYTHON) tools/run_rust_markets_parity.py --allow-missing-cargo

rust-signer-parity-check:
	$(PYTHON) tools/run_rust_signer_parity.py --allow-missing-cargo

rust-p2p-parity-check:
	$(PYTHON) tools/run_rust_p2p_parity.py --allow-missing-cargo

rust-indexer-parity-check:
	$(PYTHON) tools/run_rust_indexer_parity.py --allow-missing-cargo

ts-openapi-codegen-check:
	$(PYTHON) tools/run_ts_openapi_codegen_parity.py

full-suite-report:
	$(PYTHON) tools/full_suite_report.py

v022-check: parity-check rust-workspace-check ts-api-check migration-check
	$(PYTHON) -m pytest -q tests/test_v022_rust_ts_parity_expansion.py


v023-check: parity-check rust-workspace-check ts-api-check migration-check
	$(PYTHON) -m pytest -q tests/test_v022_rust_ts_parity_expansion.py tests/test_v023_rust_consensus_parity.py


v024-check: parity-check rust-workspace-check ts-api-check migration-check rust-consensus-parity-check
	$(PYTHON) -m pytest -q tests/test_v022_rust_ts_parity_expansion.py tests/test_v023_rust_consensus_parity.py tests/test_v024_rust_executable_consensus_parity.py


v025-check: parity-check rust-workspace-check ts-api-check migration-check rust-consensus-parity-check rust-mempool-parity-check
	$(PYTHON) -m pytest -q tests/test_v022_rust_ts_parity_expansion.py tests/test_v023_rust_consensus_parity.py tests/test_v024_rust_executable_consensus_parity.py tests/test_v025_rust_mempool_parity.py


v026-check: parity-check rust-workspace-check ts-api-check migration-check rust-consensus-parity-check rust-mempool-parity-check rust-wallet-parity-check
	$(PYTHON) -m pytest -q tests/test_v022_rust_ts_parity_expansion.py tests/test_v023_rust_consensus_parity.py tests/test_v024_rust_executable_consensus_parity.py tests/test_v025_rust_mempool_parity.py tests/test_v026_rust_wallet_core_parity.py



v027-check: parity-check rust-workspace-check ts-api-check migration-check rust-consensus-parity-check rust-mempool-parity-check rust-wallet-parity-check rust-markets-parity-check
	$(PYTHON) -m pytest -q tests/test_v022_rust_ts_parity_expansion.py tests/test_v023_rust_consensus_parity.py tests/test_v024_rust_executable_consensus_parity.py tests/test_v025_rust_mempool_parity.py tests/test_v026_rust_wallet_core_parity.py tests/test_v027_rust_markets_core_parity.py


v028-check: parity-check rust-workspace-check ts-api-check migration-check rust-consensus-parity-check rust-mempool-parity-check rust-wallet-parity-check rust-markets-parity-check rust-signer-parity-check
	$(PYTHON) -m pytest -q tests/test_v028_rust_signer_core_parity.py


v029-check: parity-check rust-workspace-check ts-api-check migration-check rust-consensus-parity-check rust-mempool-parity-check rust-wallet-parity-check rust-markets-parity-check rust-signer-parity-check rust-p2p-parity-check
	$(PYTHON) -m pytest -q tests/test_v029_rust_p2p_sync_parity.py


v030-check: parity-check rust-workspace-check ts-api-check migration-check rust-consensus-parity-check rust-mempool-parity-check rust-wallet-parity-check rust-markets-parity-check rust-signer-parity-check rust-p2p-parity-check rust-indexer-parity-check
	$(PYTHON) -m pytest -q tests/test_v030_rust_indexer_core_parity.py


v031-check: parity-check rust-workspace-check ts-api-check migration-check rust-consensus-parity-check rust-mempool-parity-check rust-wallet-parity-check rust-markets-parity-check rust-signer-parity-check rust-p2p-parity-check rust-indexer-parity-check ts-openapi-codegen-check
	$(PYTHON) -m pytest -q tests/test_v031_ts_openapi_codegen_parity.py


p2p-soak-check:
	$(PYTHON) tools/run_p2p_soak.py

indexer-db-check:
	$(PYTHON) tools/check_indexer_db_integration.py

ts-api-contract-check:
	$(PYTHON) tools/run_ts_api_contract_enforcement.py

browser-e2e-matrix-check:
	$(PYTHON) tools/run_browser_e2e_matrix.py

security-audit-prep-check:
	$(PYTHON) tools/run_security_audit_prep.py


v033-check: parity-check rust-workspace-check ts-api-check migration-check p2p-soak-check
	$(PYTHON) -m pytest -q tests/test_v033_hostile_p2p_soak.py

v034-check: parity-check rust-workspace-check ts-api-check migration-check p2p-soak-check indexer-db-check
	$(PYTHON) -m pytest -q tests/test_v033_hostile_p2p_soak.py tests/test_v034_indexer_db_integration.py

v035-check: parity-check rust-workspace-check ts-api-check migration-check p2p-soak-check indexer-db-check ts-api-contract-check openapi-contract
	$(PYTHON) -m pytest -q tests/test_v033_hostile_p2p_soak.py tests/test_v034_indexer_db_integration.py tests/test_v035_ts_api_openapi_enforcement.py

v036-check: parity-check rust-workspace-check ts-api-check migration-check p2p-soak-check indexer-db-check ts-api-contract-check openapi-contract browser-e2e-matrix-check
	$(PYTHON) -m pytest -q tests/test_v033_hostile_p2p_soak.py tests/test_v034_indexer_db_integration.py tests/test_v035_ts_api_openapi_enforcement.py tests/test_v036_browser_e2e_matrix.py

v037-check: parity-check rust-workspace-check ts-api-check migration-check p2p-soak-check indexer-db-check ts-api-contract-check openapi-contract browser-e2e-matrix-check security-audit-prep-check
	$(PYTHON) -m pytest -q tests/test_v033_hostile_p2p_soak.py tests/test_v034_indexer_db_integration.py tests/test_v035_ts_api_openapi_enforcement.py tests/test_v036_browser_e2e_matrix.py tests/test_v037_security_fuzz_audit_prep.py

.PHONY: v0374-check
v0374-check:
	python -m compileall -q netcoin tools
	python tools/run_parity_suite.py --no-write
	python tools/check_product_surface.py
	PYTHONPATH=. pytest -q tests/test_v0374_wallet_ui_compact.py
