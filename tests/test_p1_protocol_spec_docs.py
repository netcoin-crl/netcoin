from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC = ROOT / "docs" / "spec"


REQUIRED_SPEC_FILES = [
    "README.md",
    "block-format.md",
    "transaction-format.md",
    "sighash-and-signatures.md",
    "script-and-addresses.md",
    "chain-selection-and-difficulty.md",
    "emission-and-mempool-policy.md",
    "p2p-and-node-api.md",
]


REQUIRED_REFERENCES = [
    "netcoin/block.py",
    "netcoin/tx.py",
    "netcoin/script.py",
    "netcoin/crypto.py",
    "netcoin/chain.py",
    "netcoin/consensus.py",
    "netcoin/emission.py",
    "netcoin/mempool.py",
    "netcoin/node.py",
    "netcoin/p2p.py",
    "netcoin/addrv2.py",
    "netcoin/compact.py",
    "netcoin/sync.py",
    "core-rs/fixtures/parity-vectors.json",
    "tests/fixtures/consensus_vectors/genesis.json",
]


FORBIDDEN_EDIT_PATHS = [
    "sites/wallet/",
    "netcoin/wallet.py",
    "netcoin/psbt.py",
    "netcoin/offline_signing.py",
    "netcoin/fee_bump.py",
    "netcoin/webwallet.py",
    "netcoin/apps/markets/",
    "sites/markets/",
]


def test_protocol_spec_files_exist_and_are_linked_from_index():
    index = (SPEC / "README.md").read_text(encoding="utf-8")
    for rel in REQUIRED_SPEC_FILES:
        path = SPEC / rel
        assert path.exists(), rel
        assert path.read_text(encoding="utf-8").strip(), rel
        if rel != "README.md":
            assert rel in index


def test_protocol_spec_references_real_code_and_vector_paths():
    corpus = "\n".join((SPEC / rel).read_text(encoding="utf-8") for rel in REQUIRED_SPEC_FILES)
    for ref in REQUIRED_REFERENCES:
        assert ref in corpus, ref
        assert (ROOT / ref).exists(), ref


def test_protocol_spec_declares_consensus_and_policy_boundaries():
    corpus = "\n".join((SPEC / rel).read_text(encoding="utf-8") for rel in REQUIRED_SPEC_FILES)
    assert "Mempool behavior is policy, not consensus" in corpus
    assert "Mainnet versionbits and mainnet genesis remain governance-gated" in corpus
    assert "does not modify vectors or Rust parity code" in corpus


def test_p1_docs_do_not_claim_ownership_of_forbidden_files():
    corpus = "\n".join((SPEC / rel).read_text(encoding="utf-8") for rel in REQUIRED_SPEC_FILES)
    for forbidden in FORBIDDEN_EDIT_PATHS:
        assert f"modify {forbidden}" not in corpus
