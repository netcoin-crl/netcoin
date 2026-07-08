"""Taproot script trees (BIP341/342-style) for NetCoin.

Key-path Taproot (a single Schnorr key) already exists. This adds the *script
path*: commit a tree of alternative spending scripts (tapscripts) to a Taproot
output by tweaking the internal key with the tree's merkle root, then spend by
revealing one leaf script + a merkle proof (the control block).

The tweak math is standard BIP341 (validated against the BIP341 test vectors).
Leaf scripts are NetCoin text scripts (executed by the existing Script VM), so the
leaf bytes are the UTF-8 script — NetCoin-flavored, not Bitcoin bytecode.
"""

from __future__ import annotations

from .crypto import G, N, P, encode_witness_address, point_add, scalar_mult, tagged_hash

TAPROOT_LEAF_VERSION = 0xC0


def _compact_size(n: int) -> bytes:
    if n < 0xFD:
        return bytes([n])
    if n <= 0xFFFF:
        return b"\xfd" + n.to_bytes(2, "little")
    if n <= 0xFFFFFFFF:
        return b"\xfe" + n.to_bytes(4, "little")
    return b"\xff" + n.to_bytes(8, "little")


def _lift_x(x: int) -> tuple[int, int] | None:
    """BIP340 lift_x: the point on secp256k1 with x-coordinate x and even y."""
    if x <= 0 or x >= P:
        return None
    y_sq = (pow(x, 3, P) + 7) % P
    y = pow(y_sq, (P + 1) // 4, P)
    if pow(y, 2, P) != y_sq:
        return None
    if y % 2 != 0:
        y = P - y
    return (x, y)


def tap_leaf_hash(script: bytes, leaf_version: int = TAPROOT_LEAF_VERSION) -> bytes:
    return tagged_hash("TapLeaf", bytes([leaf_version]) + _compact_size(len(script)) + script)


def tap_branch_hash(a: bytes, b: bytes) -> bytes:
    # Children are sorted so the proof is order-independent.
    return tagged_hash("TapBranch", a + b if a <= b else b + a)


def merkle_root(leaf_hashes: list[bytes]) -> bytes:
    """Merkle root of a list of leaf hashes (balanced left-to-right pairing)."""
    if not leaf_hashes:
        return b""
    level = list(leaf_hashes)
    while len(level) > 1:
        nxt: list[bytes] = []
        for i in range(0, len(level), 2):
            if i + 1 < len(level):
                nxt.append(tap_branch_hash(level[i], level[i + 1]))
            else:
                nxt.append(level[i])  # odd one carries up
        level = nxt
    return level[0]


def taproot_tweak(internal_xonly: bytes, root: bytes) -> tuple[bytes, int]:
    """Tweak the internal key by the script-tree root. Returns (output x-only, parity)."""
    if len(internal_xonly) != 32:
        raise ValueError("internal key must be 32-byte x-only")
    point = _lift_x(int.from_bytes(internal_xonly, "big"))
    if point is None:
        raise ValueError("internal key is not a valid x-only point")
    t = int.from_bytes(tagged_hash("TapTweak", internal_xonly + root), "big")
    if t >= N:
        raise ValueError("invalid tweak")
    q = point_add(point, scalar_mult(t, G))
    if q is None:
        raise ValueError("tweak produced the point at infinity")
    return q[0].to_bytes(32, "big"), q[1] & 1


def taproot_output(internal_xonly: bytes, scripts: list[str]) -> dict:
    """Build a Taproot output committing to `scripts` (NetCoin text scripts).

    Returns the address, output key, parity, and per-leaf control blocks so each
    script can later be spent via the script path.
    """
    leaves = [tap_leaf_hash(s.encode("utf-8")) for s in scripts]
    root = merkle_root(leaves) if leaves else b""
    output_xonly, parity = taproot_tweak(internal_xonly, root)
    controls = {}
    for index, script in enumerate(scripts):
        path = _merkle_path(leaves, index)
        controls[script] = control_block(internal_xonly, parity, path)
    return {
        "address": encode_witness_address(1, output_xonly),
        "output_key": output_xonly.hex(),
        "parity": parity,
        "merkle_root": root.hex(),
        "control_blocks": {s: c.hex() for s, c in controls.items()},
    }


def _merkle_path(leaf_hashes: list[bytes], index: int) -> list[bytes]:
    """The sibling hashes proving leaf `index` is in the tree, bottom-up."""
    path: list[bytes] = []
    level = list(leaf_hashes)
    idx = index
    while len(level) > 1:
        nxt: list[bytes] = []
        for i in range(0, len(level), 2):
            if i + 1 < len(level):
                if i == idx or i + 1 == idx:
                    sibling = level[i + 1] if i == idx else level[i]
                    path.append(sibling)
                nxt.append(tap_branch_hash(level[i], level[i + 1]))
            else:
                nxt.append(level[i])
        idx //= 2
        level = nxt
    return path


def control_block(
    internal_xonly: bytes, parity: int, merkle_path: list[bytes], leaf_version: int = TAPROOT_LEAF_VERSION
) -> bytes:
    return bytes([leaf_version | (parity & 1)]) + internal_xonly + b"".join(merkle_path)


def verify_script_path(output_xonly: bytes, script: bytes, control: bytes) -> bool:
    """True if `control` proves `script` is committed to the Taproot `output_xonly`."""
    if len(control) < 33 or (len(control) - 33) % 32 != 0:
        return False
    leaf_version = control[0] & 0xFE
    parity = control[0] & 0x01
    internal_xonly = control[1:33]
    path = [control[i : i + 32] for i in range(33, len(control), 32)]
    node = tap_leaf_hash(script, leaf_version)
    for sibling in path:
        node = tap_branch_hash(node, sibling)
    try:
        computed_xonly, computed_parity = taproot_tweak(internal_xonly, node)
    except ValueError:
        return False
    return computed_xonly == output_xonly and computed_parity == parity
