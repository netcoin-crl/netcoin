from netcoin.professional import protocol_test_vectors, validate_protocol_vectors


def test_protocol_vectors_validate_and_include_wallet_security_parameters():
    vectors = protocol_test_vectors()
    assert vectors["schema"] == "netcoin-protocol-vectors-v1"
    assert vectors["wallet_address"].startswith("N")
    assert vectors["sample_txid"]
    assert vectors["sample_block_hash"]
    assert vectors["wallet_pbkdf2_iterations"] >= 600_000
    assert vectors["encrypted_wallet_roundtrip_ok"] is True
    assert validate_protocol_vectors(vectors)["ok"] is True


def test_protocol_vector_mismatch_is_reported():
    vectors = protocol_test_vectors()
    vectors["sample_txid"] = "00" * 32
    result = validate_protocol_vectors(vectors)
    assert result["ok"] is False
    assert any(m["field"] == "sample_txid" for m in result["mismatches"])
