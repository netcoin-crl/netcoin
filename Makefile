.PHONY: install-dev test test-fast test-full test-report ci-local lint format typecheck coverage release-check provenance-check upgrade-healthcheck ops-bundle site-audit site-sync product-check arch-check migration-check rust-workspace-check ts-api-check parity-check rust-consensus-parity-check rust-wallet-parity-check rust-markets-parity-check rust-signer-parity-check rust-p2p-parity-check rust-indexer-parity-check ts-openapi-codegen-check full-suite-report devnet fuzz browser-test browser-e2e browser-e2e-local openapi-contract security-check clean p2p-soak-check indexer-db-check ts-api-contract-check browser-e2e-matrix-check security-audit-prep-check product-architecture-check design-system-check product-simplification-check trust-interaction-check product-coherence-check v033-check v034-check v035-check v036-check v037-check v038-check v0381-check v0382-check v0383-check v0384-check

PYTHON ?= python3
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

product-architecture-check:
	$(PYTHON) tools/check_product_architecture.py

design-system-check:
	$(PYTHON) tools/check_design_system.py

product-simplification-check:
	$(PYTHON) tools/check_product_simplification.py

trust-interaction-check:
	$(PYTHON) tools/check_trust_interaction.py

product-coherence-check:
	$(PYTHON) tools/check_product_coherence.py

phase0-complete-check:
	$(PYTHON) tools/check_phase0_complete.py


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

.PHONY: v038-check
v038-check: product-architecture-check product-check site-audit
	$(PYTHON) -m compileall -q netcoin tools
	$(PYTHON) tools/run_parity_suite.py --no-write
	PYTHONPATH=. pytest -q tests/test_v038_phase0_product_architecture.py

.PHONY: v0381-check
v0381-check: product-architecture-check design-system-check product-check site-audit
	$(PYTHON) -m compileall -q netcoin tools
	$(PYTHON) tools/run_parity_suite.py --no-write
	PYTHONPATH=. pytest -q tests/test_v038_phase0_product_architecture.py tests/test_v0381_phase0_design_system.py

.PHONY: v0382-check
v0382-check: product-architecture-check design-system-check product-simplification-check product-check site-audit
	$(PYTHON) -m compileall -q netcoin tools
	$(PYTHON) tools/run_parity_suite.py --no-write
	PYTHONPATH=. pytest -q tests/test_v038_phase0_product_architecture.py tests/test_v0381_phase0_design_system.py tests/test_v0382_phase0_product_simplification.py

.PHONY: v0383-check
v0383-check: product-architecture-check design-system-check product-simplification-check trust-interaction-check product-check site-audit
	$(PYTHON) -m compileall -q netcoin tools
	$(PYTHON) tools/run_parity_suite.py --no-write
	PYTHONPATH=. pytest -q tests/test_v038_phase0_product_architecture.py tests/test_v0381_phase0_design_system.py tests/test_v0382_phase0_product_simplification.py tests/test_v0383_phase0_trust_interaction.py

.PHONY: v0384-check
v0384-check: product-architecture-check design-system-check product-simplification-check trust-interaction-check product-coherence-check product-check site-audit
	$(PYTHON) -m compileall -q netcoin tools
	$(PYTHON) tools/run_parity_suite.py --no-write
	PYTHONPATH=. pytest -q tests/test_v038_phase0_product_architecture.py tests/test_v0381_phase0_design_system.py tests/test_v0382_phase0_product_simplification.py tests/test_v0383_phase0_trust_interaction.py tests/test_v0384_phase0_product_coherence.py


.PHONY: v0385-check
v0385-check: product-architecture-check design-system-check product-simplification-check trust-interaction-check product-coherence-check phase0-complete-check product-check site-audit
	$(PYTHON) -m compileall -q netcoin tools
	$(PYTHON) tools/run_parity_suite.py --no-write
	PYTHONPATH=. pytest -q tests/test_v038_phase0_product_architecture.py tests/test_v0381_phase0_design_system.py tests/test_v0382_phase0_product_simplification.py tests/test_v0383_phase0_trust_interaction.py tests/test_v0384_phase0_product_coherence.py tests/test_v0385_phase0_completion.py

.PHONY: proof-hardening-check all-rust-parity-check accessibility-matrix-check release-readiness-check v039-check
proof-hardening-check:
	$(PYTHON) tools/check_proof_hardening.py

all-rust-parity-check:
	$(PYTHON) tools/run_all_rust_parity.py --allow-missing-cargo --no-write

accessibility-matrix-check:
	$(PYTHON) tools/run_accessibility_matrix.py --source-only

release-readiness-check:
	$(PYTHON) tools/run_release_readiness.py --timeout 60

v039-check: proof-hardening-check release-readiness-check
	$(PYTHON) tools/check_phase0_complete.py
	$(PYTHON) -m compileall -q netcoin tools
	$(PYTHON) tools/run_parity_suite.py --no-write
	PYTHONPATH=. $(PYTHON) -m pytest -q tests/test_v039_phase1_proof_hardening.py


.PHONY: strict-proof-execution-check strict-proof-plan v0391-check
strict-proof-execution-check:
	$(PYTHON) tools/check_strict_proof_execution.py

strict-proof-plan:
	$(PYTHON) tools/print_strict_proof_plan.py --profile sandbox

v0391-check:
	$(PYTHON) tools/check_strict_proof_execution.py
	PYTHONPATH=. $(PYTHON) -m pytest -q tests/test_v0391_phase1_strict_proof_execution.py

.PHONY: proof-evidence-check proof-evidence-collect v0392-check
proof-evidence-check:
	$(PYTHON) tools/check_proof_evidence.py

proof-evidence-collect:
	$(PYTHON) tools/collect_proof_evidence.py --mode sandbox

v0392-check:
	$(PYTHON) tools/run_v0392_check.py

.PHONY: local-proof-runner-check local-proof-run v0393-check
local-proof-runner-check:
	$(PYTHON) tools/check_local_proof_runner.py

local-proof-run:
	$(PYTHON) tools/run_local_proof.py --profile sandbox --timeout 120

v0393-check:
	$(PYTHON) tools/run_v0393_check.py

.PHONY: proof-triage-check proof-triage-run v0394-check
proof-triage-check:
	$(PYTHON) tools/check_proof_triage.py

proof-triage-run:
	$(PYTHON) tools/run_proof_triage.py

v0394-check:
	$(PYTHON) tools/run_v0394_check.py


.PHONY: product-completion-check v040-check
product-completion-check:
	$(PYTHON) tools/check_product_completion.py

v040-check: product-completion-check phase0-complete-check proof-triage-check product-check site-audit
	$(PYTHON) -m compileall -q netcoin tools
	$(PYTHON) tools/run_parity_suite.py --no-write
	$(PYTHON) tools/check_ts_workspace.py
	$(PYTHON) tools/run_ts_api_contract_enforcement.py
	PYTHONPATH=. $(PYTHON) -m pytest -q tests/test_v040_product_completion.py


.PHONY: v0401-check
v0401-check: product-completion-check phase0-complete-check proof-triage-check product-check site-audit
	$(PYTHON) -m compileall -q netcoin tools
	$(PYTHON) tools/run_browser_e2e_matrix.py
	$(PYTHON) tools/run_accessibility_matrix.py --source-only
	$(PYTHON) tools/run_parity_suite.py --no-write
	$(PYTHON) tools/check_ts_workspace.py
	$(PYTHON) tools/run_ts_api_contract_enforcement.py
	PYTHONPATH=. $(PYTHON) -m pytest -q tests/test_v040_product_completion.py tests/test_v0401_browser_strict_fixes.py

.PHONY: mainnet-readiness-check mainnet-readiness-source v041-check
mainnet-readiness-check:
	$(PYTHON) tools/check_mainnet_readiness_gates.py

mainnet-readiness-source:
	$(PYTHON) tools/run_mainnet_readiness.py --quiet --out reports/mainnet_readiness_source_report.json

v041-check: mainnet-readiness-check product-completion-check phase0-complete-check proof-triage-check product-check site-audit
	$(PYTHON) -m compileall -q netcoin tools
	$(PYTHON) tools/run_mainnet_readiness.py --quiet --out reports/mainnet_readiness_source_report.json
	$(PYTHON) tools/run_parity_suite.py --no-write
	$(PYTHON) tools/check_ts_workspace.py
	$(PYTHON) tools/run_ts_api_contract_enforcement.py
	PYTHONPATH=. $(PYTHON) -m pytest -q tests/test_v041_mainnet_readiness.py

.PHONY: site-ui-polish-check m1-readiness-check m1-live-smoke-plan m1-live-smoke m1-rc-check m1-rc-strict v042-check
site-ui-polish-check:
	$(PYTHON) tools/check_site_ui_polish.py

m1-readiness-check:
	$(PYTHON) tools/check_m1_readiness.py --out reports/m1_readiness_source_report.json


m1-live-smoke-plan:
	$(PYTHON) tools/check_m1_live_smoke.py --out reports/m1_live_smoke_plan.json

m1-live-smoke:
	$(PYTHON) tools/check_m1_live_smoke.py --run --out reports/m1_live_smoke_report.json

m1-rc-check: m1-readiness-check site-ui-polish-check
	$(PYTHON) tools/run_m1_release_candidate.py --profile source --out reports/m1_release_candidate_report.json

m1-rc-strict: m1-readiness-check site-ui-polish-check
	$(PYTHON) tools/run_m1_release_candidate.py --profile strict --timeout 300 --out reports/m1_release_candidate_report.json

v042-check: site-ui-polish-check product-completion-check mainnet-readiness-check product-check site-audit
	$(PYTHON) -m compileall -q netcoin tools
	$(PYTHON) tools/run_browser_e2e_matrix.py
	$(PYTHON) tools/run_accessibility_matrix.py --source-only
	$(PYTHON) tools/run_parity_suite.py --no-write
	$(PYTHON) tools/check_ts_workspace.py
	$(PYTHON) tools/run_ts_api_contract_enforcement.py
	PYTHONPATH=. $(PYTHON) -m pytest -q tests/test_v040_product_completion.py tests/test_v0401_browser_strict_fixes.py tests/test_v042_site_ui_polish.py

.PHONY: m2-readiness-check m2-rc-check m2-rc-strict

m2-readiness-check:
	$(PYTHON) tools/check_m2_readiness.py --out reports/m2_readiness_source_report.json

m2-rc-check: m2-readiness-check
	$(PYTHON) tools/run_m2_release_candidate.py --profile source --out reports/m2_release_candidate_report.json

m2-rc-strict: m2-readiness-check
	$(PYTHON) tools/run_m2_release_candidate.py --profile strict --timeout 300 --out reports/m2_release_candidate_report.json

.PHONY: m3-readiness-check m3-rc-check m3-rc-strict m3-node-map

m3-readiness-check:
	$(PYTHON) tools/check_m3_readiness.py --out reports/m3_readiness_source_report.json

m3-node-map:
	$(PYTHON) tools/export_node_map.py --input api/nodes/map --out reports/m3_node_map_source_report.json

m3-rc-check: m3-readiness-check m3-node-map
	$(PYTHON) tools/run_m3_release_candidate.py --profile source --out reports/m3_release_candidate_report.json

m3-rc-strict: m3-readiness-check
	$(PYTHON) tools/run_m3_release_candidate.py --profile strict --timeout 300 --out reports/m3_release_candidate_report.json

.PHONY: m4-readiness-check m4-distribution-check m4-rc-check m4-rc-strict

m4-readiness-check:
	$(PYTHON) tools/check_m4_readiness.py --out reports/m4_readiness_source_report.json

m4-distribution-check:
	$(PYTHON) tools/validate_mainnet_distribution.py --out reports/m4_mainnet_distribution_source_report.json

m4-rc-check: m4-readiness-check m4-distribution-check
	$(PYTHON) tools/run_m4_release_candidate.py --profile source --out reports/m4_release_candidate_report.json

m4-rc-strict: m4-readiness-check m4-distribution-check
	$(PYTHON) tools/run_m4_release_candidate.py --profile strict --timeout 300 --out reports/m4_release_candidate_report.json


.PHONY: m5-readiness-check m5-launch-plan-check m5-rc-check m5-rc-strict

m5-readiness-check:
	$(PYTHON) tools/check_m5_readiness.py --out reports/m5_readiness_source_report.json

m5-launch-plan-check:
	$(PYTHON) tools/validate_m5_launch_plan.py --out reports/m5_mainnet_launch_plan_source_report.json

m5-rc-check: m5-readiness-check m5-launch-plan-check
	$(PYTHON) tools/run_m5_release_candidate.py --profile source --out reports/m5_release_candidate_report.json

m5-rc-strict: m5-readiness-check m5-launch-plan-check
	$(PYTHON) tools/run_m5_release_candidate.py --profile strict --timeout 300 --out reports/m5_release_candidate_report.json

.PHONY: post-m5-engineering-check post-m5-engineering-strict post-m5-rc-check post-m5-rc-strict

post-m5-engineering-check:
	$(PYTHON) tools/check_post_m5_engineering.py --out reports/post_m5_engineering_source_report.json

post-m5-engineering-strict:
	$(PYTHON) tools/check_post_m5_engineering.py --strict --out reports/post_m5_engineering_strict_report.json

post-m5-rc-check: post-m5-engineering-check
	$(PYTHON) tools/run_post_m5_release_candidate.py --profile source --out reports/post_m5_release_candidate_report.json

post-m5-rc-strict: post-m5-engineering-check
	$(PYTHON) tools/run_post_m5_release_candidate.py --profile strict --timeout 300 --out reports/post_m5_release_candidate_report.json
