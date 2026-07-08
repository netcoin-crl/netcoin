"""Fuller Script VM (#25): conditionals, arithmetic, stack ops, crypto opcodes."""

import hashlib

import pytest

from netcoin.script import ScriptContext, ScriptError, execute_script, verify_script

CTX = ScriptContext(sighash=b"\x00" * 32, locktime=0, sequence=0xFFFFFFFF)


def run(script, stack=None):
    return execute_script(script, list(stack or []), CTX)


# --- arithmetic ---


def test_arithmetic_ops():
    assert run("2 3 OP_ADD") == ["5"]
    assert run("10 4 OP_SUB") == ["6"]
    assert run("7 2 OP_MIN") == ["2"]
    assert run("7 2 OP_MAX") == ["7"]
    assert run("5 OP_1ADD") == ["6"]
    assert run("5 OP_1SUB") == ["4"]
    assert run("5 OP_NEGATE") == ["-5"]
    assert run("-5 OP_ABS") == ["5"]


def test_comparisons_push_bool():
    assert run("3 3 OP_NUMEQUAL") == ["01"]
    assert run("3 4 OP_NUMEQUAL") == ["00"]
    assert run("2 5 OP_LESSTHAN") == ["01"]
    assert run("5 2 OP_GREATERTHAN") == ["01"]
    assert run("3 1 5 OP_WITHIN") == ["01"]  # 1 <= 3 < 5
    assert run("5 1 5 OP_WITHIN") == ["00"]  # 5 not < 5


def test_numequalverify():
    assert run("4 4 OP_NUMEQUALVERIFY") == []
    with pytest.raises(ScriptError, match="NUMEQUALVERIFY"):
        run("4 5 OP_NUMEQUALVERIFY")


# --- conditionals ---


def test_if_else_endif():
    assert run("1 OP_IF 10 OP_ELSE 20 OP_ENDIF") == ["10"]
    assert run("0 OP_IF 10 OP_ELSE 20 OP_ENDIF") == ["20"]
    assert run("1 OP_IF 1 OP_IF 99 OP_ENDIF OP_ENDIF") == ["99"]  # nested
    assert run("0 OP_NOTIF 42 OP_ENDIF") == ["42"]


def test_unbalanced_conditional_raises():
    with pytest.raises(ScriptError, match="unbalanced"):
        run("1 OP_IF 10")
    with pytest.raises(ScriptError, match="without OP_IF"):
        run("10 OP_ENDIF")


# --- stack manipulation ---


def test_stack_ops():
    assert run("1 2 OP_SWAP") == ["2", "1"]
    assert run("1 2 OP_OVER") == ["1", "2", "1"]
    assert run("1 2 3 OP_ROT") == ["2", "3", "1"]
    assert run("1 2 OP_NIP") == ["2"]
    assert run("1 2 OP_TUCK") == ["2", "1", "2"]
    assert run("1 2 OP_2DUP") == ["1", "2", "1", "2"]
    assert run("1 2 3 OP_DEPTH") == ["1", "2", "3", "3"]


# --- crypto ---


def test_crypto_ops():
    assert run("aa OP_SHA256") == [hashlib.sha256(b"\xaa").hexdigest()]
    assert run("aa OP_RIPEMD160") == [hashlib.new("ripemd160", b"\xaa").hexdigest()]
    double = hashlib.sha256(hashlib.sha256(b"\xaa").digest()).hexdigest()
    assert run("aa OP_HASH256") == [double]


def test_op_return_aborts():
    with pytest.raises(ScriptError, match="OP_RETURN"):
        run("1 OP_RETURN")


# --- end-to-end hashlock via verify_script ---


def test_hashlock_script_verifies():
    preimage = "deadbeef"
    h = hashlib.sha256(bytes.fromhex(preimage)).hexdigest()
    script_pubkey = f"OP_SHA256 {h} OP_EQUAL"
    assert verify_script(preimage, script_pubkey, CTX) is True
    # Wrong preimage fails.
    assert verify_script("00", script_pubkey, CTX) is False


def test_dead_branch_is_skipped():
    # The OP_RETURN in the not-taken branch must not abort execution.
    assert run("0 OP_IF OP_RETURN OP_ELSE 7 OP_ENDIF") == ["7"]
