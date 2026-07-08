"""Small Bitcoin-Script-like engine for NetCoin.

This is not a byte-for-byte clone of Bitcoin Script. It is a practical readable
subset that supports the standard output templates most useful for NetCoin:
P2PKH, P2SH, P2WPKH, P2WSH, multisig redeem scripts, CLTV/CSV-style timelocks,
and Taproot-like key path spends handled by the transaction verifier.
"""

from __future__ import annotations

import hashlib
from collections.abc import Sequence
from dataclasses import dataclass

from .crypto import (
    decode_address,
    double_sha256,
    ecdsa_verify,
    hash160,
    script_hash_to_p2sh_address,
)
from .params import LOCKTIME_THRESHOLD


class ScriptError(ValueError):
    """Raised when script parsing or execution fails."""


TRUE_VALUES = {"01", "1", "true", "TRUE"}
FALSE_VALUES = {"", "00", "0", "false", "FALSE"}


def canonical_script(tokens: Sequence[str]) -> str:
    return " ".join(str(token) for token in tokens)


def tokenize(script: str) -> list[str]:
    return [part for part in script.strip().split() if part]


def script_bytes(script: str) -> bytes:
    return script.encode("utf-8")


def script_hash160(script: str) -> bytes:
    return hash160(script_bytes(script))


def script_sha256(script: str) -> bytes:
    return double_sha256(script_bytes(script))[:32]


def script_to_p2sh_address(script: str) -> str:
    return script_hash_to_p2sh_address(script_hash160(script))


def p2pkh_script(pubkey_hash_hex: str) -> str:
    return canonical_script(["OP_DUP", "OP_HASH160", pubkey_hash_hex, "OP_EQUALVERIFY", "OP_CHECKSIG"])


def p2sh_script(script_hash_hex: str) -> str:
    return canonical_script(["OP_HASH160", script_hash_hex, "OP_EQUAL"])


def p2wpkh_script(pubkey_hash_hex: str) -> str:
    return canonical_script(["OP_0", pubkey_hash_hex])


def p2wsh_script(script_hash_hex: str) -> str:
    return canonical_script(["OP_0", script_hash_hex])


def p2tr_script(xonly_pubkey_hex: str) -> str:
    return canonical_script(["OP_1", xonly_pubkey_hex])


def multisig_redeem_script(required: int, public_keys_hex: Sequence[str]) -> str:
    if not 1 <= required <= len(public_keys_hex) <= 16:
        raise ScriptError("multisig requires 1..16 keys and m <= n")
    return canonical_script([f"OP_{required}", *public_keys_hex, f"OP_{len(public_keys_hex)}", "OP_CHECKMULTISIG"])


def timelocked_redeem_script(locktime: int, public_key_hex: str) -> str:
    return canonical_script([str(int(locktime)), "OP_CHECKLOCKTIMEVERIFY", "OP_DROP", public_key_hex, "OP_CHECKSIG"])


def address_to_script_pubkey(address: str) -> str:
    decoded = decode_address(address)
    kind = decoded["type"]
    if kind == "p2pkh":
        return p2pkh_script(decoded["hash160"].hex())  # type: ignore[index]
    if kind == "p2sh":
        return p2sh_script(decoded["hash160"].hex())  # type: ignore[index]
    if kind == "p2wpkh":
        return p2wpkh_script(decoded["program"].hex())  # type: ignore[index]
    if kind == "p2wsh":
        return p2wsh_script(decoded["program"].hex())  # type: ignore[index]
    if kind == "p2tr":
        return p2tr_script(decoded["program"].hex())  # type: ignore[index]
    raise ScriptError(f"unsupported address type: {kind}")


def classify_script(script_pubkey: str) -> str:
    tokens = tokenize(script_pubkey)
    if (
        len(tokens) == 5
        and tokens[0] == "OP_DUP"
        and tokens[1] == "OP_HASH160"
        and tokens[3] == "OP_EQUALVERIFY"
        and tokens[4] == "OP_CHECKSIG"
    ):
        return "p2pkh"
    if len(tokens) == 3 and tokens[0] == "OP_HASH160" and tokens[2] == "OP_EQUAL":
        return "p2sh"
    if len(tokens) == 2 and tokens[0] == "OP_0" and len(tokens[1]) == 40:
        return "p2wpkh"
    if len(tokens) == 2 and tokens[0] == "OP_0" and len(tokens[1]) == 64:
        return "p2wsh"
    if len(tokens) == 2 and tokens[0] == "OP_1" and len(tokens[1]) == 64:
        return "p2tr"
    if (
        len(tokens) >= 4
        and tokens[-1] == "OP_CHECKMULTISIG"
        and tokens[0].startswith("OP_")
        and tokens[-2].startswith("OP_")
    ):
        return "multisig"
    if "OP_CHECKLOCKTIMEVERIFY" in tokens:
        return "cltv"
    return "unknown"


def op_n_value(token: str) -> int:
    if token == "OP_0":
        return 0
    if token.startswith("OP_"):
        try:
            value = int(token[3:])
        except ValueError as exc:
            raise ScriptError(f"not an OP_N token: {token}") from exc
        if 0 <= value <= 16:
            return value
    raise ScriptError(f"not an OP_N token: {token}")


def cast_to_bool(value: str) -> bool:
    if value in FALSE_VALUES:
        return False
    return True


def _as_int(value: str) -> int:
    try:
        return int(value, 10)
    except ValueError:
        return int(value, 16)


@dataclass
class ScriptContext:
    sighash: bytes
    locktime: int = 0
    sequence: int = 0xFFFFFFFF


def _push_bool(stack: list[str], value: bool) -> None:
    stack.append("01" if value else "00")


def _is_hex(value: str) -> bool:
    if len(value) % 2 != 0 or not value:
        return False
    try:
        bytes.fromhex(value)
        return True
    except ValueError:
        return False


def execute_script(script: str, stack: list[str], context: ScriptContext) -> list[str]:
    """Execute a Script subset and return the resulting stack.

    Supports data pushes, hashing, equality/verify, alt-stack, timelocks,
    signature checks, conditionals (OP_IF/NOTIF/ELSE/ENDIF), stack manipulation,
    and numeric opcodes. Integers are decimal strings; booleans are 01/00."""
    alt_stack: list[str] = []
    exec_stack: list[bool] = []  # conditional-execution flags (OP_IF/ELSE/ENDIF)
    tokens = tokenize(script)

    def executing() -> bool:
        return all(exec_stack)

    for token in tokens:
        # Conditionals are processed even inside a skipped branch (to keep nesting).
        if token in ("OP_IF", "OP_NOTIF"):
            condition = False
            if executing():
                if not stack:
                    raise ScriptError(f"{token} on empty stack")
                value = cast_to_bool(stack.pop())
                condition = value if token == "OP_IF" else not value
            exec_stack.append(condition)
            continue
        if token == "OP_ELSE":
            if not exec_stack:
                raise ScriptError("OP_ELSE without OP_IF")
            exec_stack[-1] = not exec_stack[-1]
            continue
        if token == "OP_ENDIF":
            if not exec_stack:
                raise ScriptError("OP_ENDIF without OP_IF")
            exec_stack.pop()
            continue
        if not executing():
            continue  # in a dead branch: skip everything except conditionals

        if token == "OP_DUP":
            if not stack:
                raise ScriptError("OP_DUP on empty stack")
            stack.append(stack[-1])
        elif token == "OP_HASH160":
            if not stack:
                raise ScriptError("OP_HASH160 on empty stack")
            data = bytes.fromhex(stack.pop())
            stack.append(hash160(data).hex())
        elif token == "OP_SHA256":
            if not stack:
                raise ScriptError("OP_SHA256 on empty stack")
            stack.append(hashlib.sha256(bytes.fromhex(stack.pop())).hexdigest())
        elif token == "OP_HASH256":
            if not stack:
                raise ScriptError("OP_HASH256 on empty stack")
            stack.append(double_sha256(bytes.fromhex(stack.pop())).hex())
        elif token == "OP_RIPEMD160":
            if not stack:
                raise ScriptError("OP_RIPEMD160 on empty stack")
            stack.append(hashlib.new("ripemd160", bytes.fromhex(stack.pop())).hexdigest())
        elif token == "OP_SIZE":
            if not stack:
                raise ScriptError("OP_SIZE on empty stack")
            stack.append(str(len(bytes.fromhex(stack[-1])) if _is_hex(stack[-1]) else len(stack[-1])))
        elif token == "OP_SWAP":
            if len(stack) < 2:
                raise ScriptError("OP_SWAP needs two items")
            stack[-1], stack[-2] = stack[-2], stack[-1]
        elif token == "OP_OVER":
            if len(stack) < 2:
                raise ScriptError("OP_OVER needs two items")
            stack.append(stack[-2])
        elif token == "OP_NIP":
            if len(stack) < 2:
                raise ScriptError("OP_NIP needs two items")
            del stack[-2]
        elif token == "OP_TUCK":
            if len(stack) < 2:
                raise ScriptError("OP_TUCK needs two items")
            stack.insert(-2, stack[-1])
        elif token == "OP_ROT":
            if len(stack) < 3:
                raise ScriptError("OP_ROT needs three items")
            stack[-3], stack[-2], stack[-1] = stack[-2], stack[-1], stack[-3]
        elif token == "OP_2DUP":
            if len(stack) < 2:
                raise ScriptError("OP_2DUP needs two items")
            stack.extend(stack[-2:])
        elif token == "OP_DEPTH":
            stack.append(str(len(stack)))
        elif token == "OP_IFDUP":
            if not stack:
                raise ScriptError("OP_IFDUP on empty stack")
            if cast_to_bool(stack[-1]):
                stack.append(stack[-1])
        elif token in (
            "OP_ADD",
            "OP_SUB",
            "OP_MIN",
            "OP_MAX",
            "OP_BOOLAND",
            "OP_BOOLOR",
            "OP_NUMEQUAL",
            "OP_NUMEQUALVERIFY",
            "OP_NUMNOTEQUAL",
            "OP_LESSTHAN",
            "OP_GREATERTHAN",
            "OP_LESSTHANOREQUAL",
            "OP_GREATERTHANOREQUAL",
        ):
            if len(stack) < 2:
                raise ScriptError(f"{token} needs two items")
            b = _as_int(stack.pop())
            a = _as_int(stack.pop())
            if token == "OP_ADD":
                stack.append(str(a + b))
            elif token == "OP_SUB":
                stack.append(str(a - b))
            elif token == "OP_MIN":
                stack.append(str(min(a, b)))
            elif token == "OP_MAX":
                stack.append(str(max(a, b)))
            elif token == "OP_BOOLAND":
                _push_bool(stack, a != 0 and b != 0)
            elif token == "OP_BOOLOR":
                _push_bool(stack, a != 0 or b != 0)
            elif token == "OP_NUMEQUAL":
                _push_bool(stack, a == b)
            elif token == "OP_NUMEQUALVERIFY":
                if a != b:
                    raise ScriptError("OP_NUMEQUALVERIFY failed")
            elif token == "OP_NUMNOTEQUAL":
                _push_bool(stack, a != b)
            elif token == "OP_LESSTHAN":
                _push_bool(stack, a < b)
            elif token == "OP_GREATERTHAN":
                _push_bool(stack, a > b)
            elif token == "OP_LESSTHANOREQUAL":
                _push_bool(stack, a <= b)
            elif token == "OP_GREATERTHANOREQUAL":
                _push_bool(stack, a >= b)
        elif token in ("OP_NEGATE", "OP_ABS", "OP_NOT", "OP_0NOTEQUAL", "OP_1ADD", "OP_1SUB"):
            if not stack:
                raise ScriptError(f"{token} on empty stack")
            a = _as_int(stack.pop())
            if token == "OP_NEGATE":
                stack.append(str(-a))
            elif token == "OP_ABS":
                stack.append(str(abs(a)))
            elif token == "OP_NOT":
                _push_bool(stack, a == 0)
            elif token == "OP_0NOTEQUAL":
                _push_bool(stack, a != 0)
            elif token == "OP_1ADD":
                stack.append(str(a + 1))
            elif token == "OP_1SUB":
                stack.append(str(a - 1))
        elif token == "OP_WITHIN":
            if len(stack) < 3:
                raise ScriptError("OP_WITHIN needs three items")
            maximum = _as_int(stack.pop())
            minimum = _as_int(stack.pop())
            value = _as_int(stack.pop())
            _push_bool(stack, minimum <= value < maximum)
        elif token == "OP_1NEGATE":
            stack.append("-1")
        elif token == "OP_RETURN":
            raise ScriptError("OP_RETURN encountered")
        elif token == "OP_CHECKSIGVERIFY":
            stack = execute_script("OP_CHECKSIG", stack, context)
            if not stack or not cast_to_bool(stack.pop()):
                raise ScriptError("OP_CHECKSIGVERIFY failed")
        elif token == "OP_CHECKMULTISIGVERIFY":
            stack = execute_script("OP_CHECKMULTISIG", stack, context)
            if not stack or not cast_to_bool(stack.pop()):
                raise ScriptError("OP_CHECKMULTISIGVERIFY failed")
        elif token == "OP_EQUAL":
            if len(stack) < 2:
                raise ScriptError("OP_EQUAL needs two stack items")
            a = stack.pop()
            b = stack.pop()
            stack.append("01" if a == b else "00")
        elif token == "OP_EQUALVERIFY":
            stack = execute_script("OP_EQUAL", stack, context)
            if not stack or not cast_to_bool(stack.pop()):
                raise ScriptError("OP_EQUALVERIFY failed")
        elif token == "OP_VERIFY":
            if not stack or not cast_to_bool(stack.pop()):
                raise ScriptError("OP_VERIFY failed")
        elif token == "OP_DROP":
            if not stack:
                raise ScriptError("OP_DROP on empty stack")
            stack.pop()
        elif token == "OP_TOALTSTACK":
            if not stack:
                raise ScriptError("OP_TOALTSTACK on empty stack")
            alt_stack.append(stack.pop())
        elif token == "OP_FROMALTSTACK":
            if not alt_stack:
                raise ScriptError("OP_FROMALTSTACK on empty alt stack")
            stack.append(alt_stack.pop())
        elif token == "OP_CHECKLOCKTIMEVERIFY":
            if not stack:
                raise ScriptError("OP_CHECKLOCKTIMEVERIFY on empty stack")
            required = _as_int(stack[-1])
            if required < 0:
                raise ScriptError("negative locktime")
            if required < LOCKTIME_THRESHOLD and context.locktime >= LOCKTIME_THRESHOLD:
                raise ScriptError("CLTV type mismatch")
            if required >= LOCKTIME_THRESHOLD and context.locktime < LOCKTIME_THRESHOLD:
                raise ScriptError("CLTV type mismatch")
            if context.locktime < required:
                raise ScriptError("transaction locktime is too low")
            if context.sequence == 0xFFFFFFFF:
                raise ScriptError("CLTV requires non-final sequence")
        elif token == "OP_CHECKSEQUENCEVERIFY":
            if not stack:
                raise ScriptError("OP_CHECKSEQUENCEVERIFY on empty stack")
            required = _as_int(stack[-1])
            if context.sequence < required:
                raise ScriptError("input sequence is too low")
        elif token == "OP_CHECKSIG":
            if len(stack) < 2:
                raise ScriptError("OP_CHECKSIG needs signature and public key")
            public_key_hex = stack.pop()
            signature_hex = stack.pop()
            ok = ecdsa_verify(bytes.fromhex(public_key_hex), context.sighash, bytes.fromhex(signature_hex))
            stack.append("01" if ok else "00")
        elif token == "OP_CHECKMULTISIG":
            if len(stack) < 1:
                raise ScriptError("OP_CHECKMULTISIG missing key count")
            n = op_n_value(stack.pop())
            if n < 1 or n > 16 or len(stack) < n + 1:
                raise ScriptError("invalid CHECKMULTISIG key count")
            public_keys = [stack.pop() for _ in range(n)][::-1]
            m = op_n_value(stack.pop())
            if m < 1 or m > n or len(stack) < m:
                raise ScriptError("invalid CHECKMULTISIG signature count")
            signatures = [stack.pop() for _ in range(m)][::-1]
            # Bitcoin has a historical extra dummy pop. NetCoin accepts an optional
            # OP_0/dummy item below the signatures for familiarity.
            if stack and stack[-1] in ("", "00", "OP_0"):
                stack.pop()
            sig_index = 0
            key_index = 0
            while sig_index < m and key_index < n:
                if ecdsa_verify(
                    bytes.fromhex(public_keys[key_index]), context.sighash, bytes.fromhex(signatures[sig_index])
                ):
                    sig_index += 1
                key_index += 1
            stack.append("01" if sig_index == m else "00")
        elif token == "OP_0":
            stack.append("00")
        elif token.startswith("OP_") and token[3:].isdigit() and 1 <= int(token[3:]) <= 16:
            stack.append(token)
        else:
            # Data push. NetCoin script assembly represents pushed byte strings as
            # hex and small integers as decimal strings.
            stack.append(token)
    if exec_stack:
        raise ScriptError("unbalanced OP_IF / OP_ENDIF")
    return stack


def verify_script(script_sig: str, script_pubkey: str, context: ScriptContext) -> bool:
    kind = classify_script(script_pubkey)
    if kind == "p2sh":
        # P2SH scriptSig format: <sig...> <redeem_script_json_or_hexasm>
        items = tokenize(script_sig)
        if not items:
            return False
        redeem_encoded = items[-1]
        try:
            redeem_script = bytes.fromhex(redeem_encoded).decode("utf-8")
        except ValueError:
            redeem_script = redeem_encoded
        expected = tokenize(script_pubkey)[1]
        if script_hash160(redeem_script).hex() != expected:
            return False
        try:
            stack = items[:-1]
            stack = execute_script(redeem_script, stack, context)
            return bool(stack and cast_to_bool(stack[-1]))
        except (ScriptError, ValueError):
            return False

    try:
        stack = execute_script(script_sig, [], context)
        stack = execute_script(script_pubkey, stack, context)
        return bool(stack and cast_to_bool(stack[-1]))
    except (ScriptError, ValueError):
        return False


# Compatibility object for newer CLI code.
@dataclass(frozen=True)
class ScriptTemplate:
    kind: str
    script_pubkey: str
    description: str


def describe_address(address: str) -> ScriptTemplate:
    script = address_to_script_pubkey(address)
    kind = classify_script(script)
    descriptions = {
        "p2pkh": "legacy pay-to-public-key-hash, ECDSA signature plus public key",
        "p2sh": "pay-to-script-hash, redeem script commitment",
        "p2wpkh": "native SegWit v0 pay-to-witness-public-key-hash",
        "p2wsh": "native SegWit v0 pay-to-witness-script-hash",
        "p2tr": "Taproot-like witness v1 key-path output using Schnorr",
    }
    return ScriptTemplate(kind=kind, script_pubkey=script, description=descriptions.get(kind, "custom NetCoin Script"))
