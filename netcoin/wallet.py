"""Wallet helpers for NetCoin."""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import secrets
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import ChaCha20Poly1305

from .chain import Blockchain
from .crypto import (
    N,
    bytes_to_hex,
    generate_private_key,
    hash160,
    private_key_from_hex,
    private_key_from_wif,
    private_key_to_bytes,
    private_key_to_public_key,
    private_key_to_wif,
    private_key_to_xonly_public_key,
    public_key_to_address,
    public_key_to_p2wpkh_address,
    public_key_to_taproot_address,
    validate_address,
)
from .script import multisig_redeem_script, p2wpkh_script, script_to_p2sh_address
from .tx import SpendableOutput, Transaction, TxInput, TxOutput


class WalletError(ValueError):
    """Raised when wallet loading or transaction creation fails."""


WORD_LIST = [f"net{index:03d}" for index in range(256)]
WORD_INDEX = {word: index for index, word in enumerate(WORD_LIST)}


def new_seed_phrase(strength_bytes: int = 16) -> str:
    if strength_bytes not in (16, 24, 32):
        raise WalletError("seed strength must be 16, 24, or 32 bytes")
    entropy = secrets.token_bytes(strength_bytes)
    checksum = hashlib.sha256(entropy).digest()[0]
    return " ".join([WORD_LIST[b] for b in entropy] + [WORD_LIST[checksum]])


def seed_phrase_to_entropy(phrase: str) -> bytes:
    words = phrase.strip().split()
    if len(words) < 2:
        raise WalletError("seed phrase is too short")
    try:
        values = bytes(WORD_INDEX[word] for word in words[:-1])
        checksum = WORD_INDEX[words[-1]]
    except KeyError as exc:
        raise WalletError("seed phrase contains an unknown word") from exc
    if hashlib.sha256(values).digest()[0] != checksum:
        raise WalletError("seed phrase checksum is invalid")
    return values


COIN_SELECTION_STRATEGIES = ("greedy", "largest-first", "smallest-first", "random")


def order_utxos_for_strategy(utxos: list[SpendableOutput], strategy: str) -> list[SpendableOutput]:
    """Order spendable outputs for a coin-selection strategy."""
    s = (strategy or "greedy").lower()
    if s in ("greedy", "default"):
        return list(utxos)
    if s == "largest-first":
        return sorted(utxos, key=lambda u: u.output.amount, reverse=True)
    if s == "smallest-first":
        return sorted(utxos, key=lambda u: u.output.amount)
    if s == "random":
        shuffled = list(utxos)
        secrets.SystemRandom().shuffle(shuffled)
        return shuffled
    raise WalletError(f"unknown coin-selection strategy: {strategy}")


def confirm_seed_phrase(original: str, typed: str) -> bool:
    """True if `typed` matches `original` ignoring surrounding/extra whitespace.

    Used by the seed-confirmation step so a wallet is only considered safely
    backed up once the user can reproduce the phrase."""
    return original.split() == typed.split() and bool(original.split())


def verify_seed_phrase(phrase: str) -> bool:
    """Return True if the phrase is a well-formed NetCoin seed phrase.

    Checks that every word is known and the checksum word matches. Use this to
    confirm a written-down backup is valid before relying on it. Never raises.
    """
    try:
        seed_phrase_to_entropy(phrase)
        return True
    except WalletError:
        return False


def private_key_from_seed_phrase(phrase: str, index: int = 0) -> int:
    entropy = seed_phrase_to_entropy(phrase)
    seed = hashlib.pbkdf2_hmac("sha256", entropy, b"NetCoin seed phrase", 100_000, dklen=32)
    counter = 0
    while True:
        digest = hmac.new(seed, f"netcoin-key/{index}/{counter}".encode(), hashlib.sha256).digest()
        key = int.from_bytes(digest, "big") % N
        if 1 <= key < N:
            return key
        counter += 1


# KDF cost. v1 wallets used 250k PBKDF2 iterations; v2 raises this. Old files are
# still readable because the iteration count is read back from the file.
PBKDF2_ITERATIONS = 600_000
LEGACY_PBKDF2_ITERATIONS = 250_000

# Wallet file format version. v1 = original files with no version field (and 250k
# KDF for encrypted ones); v2 = stamped version + 600k KDF with the legacy
# HMAC stream; v3 = stamped version + 600k KDF + ChaCha20-Poly1305 AEAD.
# Loaders tolerate v1/v2 so users can migrate without losing wallet access.
WALLET_FORMAT_VERSION = 3
AEAD_CIPHER = "chacha20-poly1305-v3"
LEGACY_CIPHERS = {"netcoin-hmac-stream-v1", "netcoin-hmac-stream-v2"}
AEAD_ASSOCIATED_DATA = b"NetCoin encrypted wallet private key v3"


def wallet_file_version(data: dict[str, Any]) -> int:
    return int(data.get("wallet_version", 1))


def wallet_needs_migration(data: dict[str, Any]) -> bool:
    """True if a wallet dict is below the current format or uses an old KDF cost."""
    if wallet_file_version(data) < WALLET_FORMAT_VERSION:
        return True
    if data.get("encrypted"):
        encrypted = data.get("encrypted_private_key", {})
        if encrypted.get("cipher") != AEAD_CIPHER:
            return True
        iterations = int(encrypted.get("iterations", LEGACY_PBKDF2_ITERATIONS))
        if iterations < PBKDF2_ITERATIONS:
            return True
    return False


def _derive_encryption_key(passphrase: str, salt: bytes, iterations: int = PBKDF2_ITERATIONS) -> bytes:
    if not passphrase:
        raise WalletError("encrypted wallet requires a non-empty passphrase")
    return hashlib.pbkdf2_hmac("sha256", passphrase.encode("utf-8"), salt, iterations, dklen=32)


def _xor_stream(data: bytes, key: bytes, nonce: bytes) -> bytes:
    out = bytearray()
    counter = 0
    while len(out) < len(data):
        block = hmac.new(key, nonce + counter.to_bytes(8, "big"), hashlib.sha256).digest()
        out.extend(block)
        counter += 1
    return bytes(a ^ b for a, b in zip(data, out[: len(data)], strict=True))


def encrypt_private_key(private_key_hex: str, passphrase: str) -> dict[str, str]:
    salt = secrets.token_bytes(16)
    nonce = secrets.token_bytes(12)
    key = _derive_encryption_key(passphrase, salt, PBKDF2_ITERATIONS)
    plaintext = private_key_hex.encode("ascii")
    ciphertext = ChaCha20Poly1305(key).encrypt(nonce, plaintext, AEAD_ASSOCIATED_DATA)
    return {
        "cipher": AEAD_CIPHER,
        "kdf": "pbkdf2-hmac-sha256",
        "iterations": str(PBKDF2_ITERATIONS),
        "salt": salt.hex(),
        "nonce": nonce.hex(),
        "ciphertext": ciphertext.hex(),
        "aead": "chacha20-poly1305",
        "associated_data": AEAD_ASSOCIATED_DATA.decode("ascii"),
    }


def decrypt_private_key(encrypted: dict[str, str], passphrase: str) -> str:
    cipher = encrypted.get("cipher", "netcoin-hmac-stream-v1")
    salt = bytes.fromhex(encrypted["salt"])
    nonce = bytes.fromhex(encrypted["nonce"])
    ciphertext = bytes.fromhex(encrypted["ciphertext"])
    # Honor the file's own iteration count so older (250k) wallets still open.
    iterations = int(encrypted.get("iterations", LEGACY_PBKDF2_ITERATIONS))
    key = _derive_encryption_key(passphrase, salt, iterations)
    if cipher == AEAD_CIPHER:
        associated_data = AEAD_ASSOCIATED_DATA.decode("ascii")
        if encrypted.get("associated_data", associated_data) != associated_data:
            raise WalletError("wallet encryption metadata is unsupported or was modified")
        try:
            return ChaCha20Poly1305(key).decrypt(nonce, ciphertext, AEAD_ASSOCIATED_DATA).decode("ascii")
        except InvalidTag as exc:
            raise WalletError("wallet passphrase is incorrect or file was modified") from exc
    if cipher in LEGACY_CIPHERS:
        mac = hmac.new(key, nonce + ciphertext, hashlib.sha256).digest()
        if not hmac.compare_digest(mac.hex(), encrypted.get("mac", "")):
            raise WalletError("wallet passphrase is incorrect or file was modified")
        return _xor_stream(ciphertext, key, nonce).decode("ascii")
    raise WalletError(f"unsupported wallet encryption cipher: {cipher}")


@dataclass
class Wallet:
    private_key: int

    @classmethod
    def create(cls, seed_phrase: str | None = None, index: int = 0) -> Wallet:
        if seed_phrase:
            return cls(private_key=private_key_from_seed_phrase(seed_phrase, index=index))
        return cls(private_key=generate_private_key())

    @property
    def private_key_hex(self) -> str:
        return private_key_to_bytes(self.private_key).hex()

    @property
    def public_key(self) -> bytes:
        return private_key_to_public_key(self.private_key, compressed=True)

    @property
    def public_key_hex(self) -> str:
        return bytes_to_hex(self.public_key)

    @property
    def xonly_public_key_hex(self) -> str:
        return private_key_to_xonly_public_key(self.private_key).hex()

    @property
    def address(self) -> str:
        return public_key_to_address(self.public_key)

    @property
    def segwit_address(self) -> str:
        return public_key_to_p2wpkh_address(self.public_key)

    @property
    def taproot_address(self) -> str:
        return public_key_to_taproot_address(private_key_to_xonly_public_key(self.private_key))

    @property
    def wif(self) -> str:
        return private_key_to_wif(self.private_key)

    @property
    def xonly_public_key(self) -> bytes:
        return private_key_to_xonly_public_key(self.private_key)

    @property
    def p2sh_segwit_address(self) -> str:
        redeem_script = p2wpkh_script(hash160(self.public_key).hex())
        return script_to_p2sh_address(redeem_script)

    @classmethod
    def from_mnemonic(cls, words: str, passphrase: str = "") -> Wallet:
        # Current NetCoin seed phrases already include their checksum. The optional
        # passphrase is accepted for CLI compatibility but not mixed into this simple
        # educational derivation.
        return cls.create(seed_phrase=words)

    @classmethod
    def create_with_mnemonic(cls, strength_bytes: int = 16) -> tuple[Wallet, str]:
        phrase = new_seed_phrase(strength_bytes)
        return cls.create(seed_phrase=phrase), phrase

    @classmethod
    def from_wif(cls, wif: str) -> Wallet:
        return cls(private_key=private_key_from_wif(wif))

    @staticmethod
    def watch_only(address: str) -> dict[str, Any]:
        if not validate_address(address):
            raise WalletError("address is not a valid NetCoin address")
        return {"network": "NetCoin", "address": address, "watch_only": True, "encrypted": False}

    def to_plain_dict(self) -> dict[str, Any]:
        data = self.to_dict(passphrase=None)
        data["wif"] = self.wif
        data["addresses"]["p2sh_segwit"] = self.p2sh_segwit_address
        return data

    def matches_seed_phrase(self, phrase: str, index: int = 0) -> bool:
        """Return True if the seed phrase regenerates this wallet's key.

        Lets a tester confirm a backup phrase actually controls this wallet
        before trusting it for recovery. Returns False for an invalid phrase
        rather than raising.
        """
        if not verify_seed_phrase(phrase):
            return False
        try:
            return private_key_from_seed_phrase(phrase, index=index) == self.private_key
        except WalletError:
            return False

    def address_for(self, address_type: str = "legacy") -> str:
        normalized = address_type.lower()
        if normalized in ("legacy", "p2pkh", "base58"):
            return self.address
        if normalized in ("segwit", "p2wpkh", "bech32"):
            return self.segwit_address
        if normalized in ("taproot", "p2tr", "bech32m"):
            return self.taproot_address
        if normalized in ("p2sh-segwit", "p2sh", "sh-wpkh"):
            return self.p2sh_segwit_address
        raise WalletError("address type must be legacy, segwit, or taproot")

    def public_dict(self, wallet_file: str | None = None) -> dict[str, Any]:
        data = {
            "network": "NetCoin",
            "public_key_hex": self.public_key_hex,
            "xonly_public_key_hex": self.xonly_public_key_hex,
            "address": self.address,
            "addresses": {
                "legacy": self.address,
                "segwit": self.segwit_address,
                "taproot": self.taproot_address,
                "p2sh_segwit": self.p2sh_segwit_address,
            },
        }
        if wallet_file is not None:
            data["wallet_file"] = wallet_file
        return data

    def to_dict(self, passphrase: str | None = None) -> dict[str, Any]:
        data = self.public_dict()
        data["wallet_version"] = WALLET_FORMAT_VERSION
        if passphrase:
            data["encrypted"] = True
            data["encrypted_private_key"] = encrypt_private_key(self.private_key_hex, passphrase)
            data["warning"] = "Educational encrypted wallet. Use real wallet software for real funds."
        else:
            data["encrypted"] = False
            data["private_key_hex"] = self.private_key_hex
            data["warning"] = "Unencrypted educational wallet. Do not use for real funds."
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any], passphrase: str | None = None) -> Wallet:
        if data.get("encrypted"):
            if passphrase is None:
                raise WalletError("wallet is encrypted; provide --passphrase")
            private_key_hex = decrypt_private_key(data["encrypted_private_key"], passphrase)
        else:
            private_key_hex = str(data["private_key_hex"])
        private_key = private_key_from_hex(private_key_hex)
        wallet = cls(private_key=private_key)
        expected_address = str(data.get("address", wallet.address))
        if wallet.address != expected_address:
            raise WalletError("wallet address does not match private key")
        return wallet

    def save(self, path: str | Path, passphrase: str | None = None) -> None:
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps(self.to_dict(passphrase=passphrase), indent=2, sort_keys=True)
        fd, tmp_name = tempfile.mkstemp(prefix=f".{target.name}.", suffix=".tmp", dir=str(target.parent))
        tmp_path = Path(tmp_name)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                handle.write(payload)
                handle.flush()
                os.fsync(handle.fileno())
            os.chmod(tmp_path, 0o600)
            os.replace(tmp_path, target)
            os.chmod(target, 0o600)
            try:
                dir_fd = os.open(str(target.parent), os.O_RDONLY)
                try:
                    os.fsync(dir_fd)
                finally:
                    os.close(dir_fd)
            except OSError:
                pass
        finally:
            tmp_path.unlink(missing_ok=True)

    @classmethod
    def load(cls, path: str | Path, passphrase: str | None = None) -> Wallet:
        return cls.from_dict(json.loads(Path(path).read_text()), passphrase=passphrase)

    @staticmethod
    def public_info_from_file(path: str | Path) -> dict[str, Any]:
        data = json.loads(Path(path).read_text())
        public = {
            key: data[key]
            for key in ("network", "public_key_hex", "xonly_public_key_hex", "address", "addresses", "encrypted")
            if key in data
        }
        public["wallet_file"] = str(path)
        return public

    def create_transaction(
        self,
        chain: Blockchain,
        to_address: str,
        amount: int,
        fee: int,
        *,
        from_type: str = "legacy",
        change_type: str = "legacy",
        rbf: bool = False,
        locktime: int = 0,
        select_outpoints: list[str] | None = None,
        strategy: str = "greedy",
    ) -> Transaction:
        if not validate_address(to_address):
            raise WalletError("destination is not a valid NetCoin address")
        if amount <= 0:
            raise WalletError("amount must be positive")
        if fee < 0:
            raise WalletError("fee cannot be negative")
        from_address = self.address_for(from_type)
        change_address = self.address_for(change_type)
        needed = amount + fee
        available = chain.utxos_for_address(from_address)
        if not rbf:
            mempool_spent = {txin.outpoint() for tx in chain.mempool for txin in tx.inputs}
            available = [u for u in available if u.outpoint() not in mempool_spent]
        available = order_utxos_for_strategy(available, strategy)

        if select_outpoints:
            # Coin control: spend exactly the chosen UTXOs (and only ours).
            wanted = list(dict.fromkeys(select_outpoints))
            by_outpoint = {u.outpoint(): u for u in available}
            selected = []
            for op in wanted:
                if op not in by_outpoint:
                    raise WalletError(f"outpoint not spendable by this wallet: {op}")
                selected.append(by_outpoint[op])
            selected_total = sum(u.output.amount for u in selected)
            if selected_total < needed:
                raise WalletError("selected UTXOs do not cover amount + fee")
        else:
            selected = []
            selected_total = 0
            for utxo in available:
                selected.append(utxo)
                selected_total += utxo.output.amount
                if selected_total >= needed:
                    break
            if selected_total < needed:
                raise WalletError("insufficient spendable NetCoin balance")

        sequence = 0xFFFFFFFD if rbf or locktime else 0xFFFFFFFF
        inputs = [TxInput(txid=utxo.txid, vout=utxo.vout, sequence=sequence) for utxo in selected]
        outputs = [TxOutput(amount=amount, address=to_address)]
        change = selected_total - needed
        if change > 0:
            outputs.append(TxOutput(amount=change, address=change_address))

        tx = Transaction(inputs=inputs, outputs=outputs, locktime=locktime)
        for index, utxo in enumerate(selected):
            tx.sign_input(index, self.private_key, utxo)

        temp_utxos = chain.utxo_set()
        chain.validate_regular_transaction(tx, temp_utxos, chain.height() + 1)
        return tx

    def create_multisig_address(self, required: int, public_keys_hex: list[str]) -> dict[str, str]:
        redeem_script = multisig_redeem_script(required, public_keys_hex)
        return {"address": script_to_p2sh_address(redeem_script), "redeem_script": redeem_script}


class AutoLockWalletSession:
    """In-memory wallet unlock session with a TTL.

    This does not create a background thread; callers check `get_wallet()` before
    each sensitive operation. Once expired, the private-key reference is dropped
    and future access raises WalletError. It gives CLI/daemon code a simple
    primitive for auto-locking decrypted wallet material.
    """

    def __init__(self, path: str | Path, passphrase: str | None = None, ttl_seconds: int = 300):
        if ttl_seconds <= 0:
            raise WalletError("auto-lock ttl must be positive")
        self.path = str(path)
        self.unlocked_at = time.time()
        self.expires_at = self.unlocked_at + int(ttl_seconds)
        self._wallet: Wallet | None = Wallet.load(path, passphrase=passphrase)

    @property
    def locked(self) -> bool:
        if self._wallet is None:
            return True
        if time.time() >= self.expires_at:
            self.lock()
            return True
        return False

    def lock(self) -> None:
        self._wallet = None

    def get_wallet(self) -> Wallet:
        if self.locked or self._wallet is None:
            raise WalletError("wallet session is locked")
        return self._wallet

    def status(self) -> dict[str, Any]:
        return {
            "wallet_file": self.path,
            "locked": self.locked,
            "unlocked_at": int(self.unlocked_at),
            "expires_at": int(self.expires_at),
            "seconds_remaining": max(0, int(self.expires_at - time.time())) if not self.locked else 0,
        }


_original_create_transaction = Wallet.create_transaction


def _create_transaction_extended(
    self: Wallet,
    chain: Blockchain,
    to_address: str,
    amount: int,
    fee: int,
    *,
    from_type: str = "legacy",
    change_type: str = "legacy",
    rbf: bool = False,
    locktime: int = 0,
    from_address: str | None = None,
    change_address: str | None = None,
    select_outpoints: list[str] | None = None,
    strategy: str = "greedy",
) -> Transaction:
    if from_address is None and change_address is None:
        return _original_create_transaction(
            self,
            chain,
            to_address,
            amount,
            fee,
            from_type=from_type,
            change_type=change_type,
            rbf=rbf,
            locktime=locktime,
            select_outpoints=select_outpoints,
            strategy=strategy,
        )
    if not validate_address(to_address):
        raise WalletError("destination is not a valid NetCoin address")
    spend_from = from_address or self.address_for(from_type)
    change_to = change_address or self.address_for(change_type)
    if not validate_address(spend_from) or not validate_address(change_to):
        raise WalletError("source/change address is not valid")
    needed = amount + fee
    available = chain.utxos_for_address(spend_from)
    if not rbf:
        mempool_spent = {txin.outpoint() for tx in chain.mempool for txin in tx.inputs}
        available = [u for u in available if u.outpoint() not in mempool_spent]
    available = order_utxos_for_strategy(available, strategy)
    if select_outpoints:
        by_outpoint = {u.outpoint(): u for u in available}
        selected = []
        for op in dict.fromkeys(select_outpoints):
            if op not in by_outpoint:
                raise WalletError(f"outpoint not spendable from {spend_from}: {op}")
            selected.append(by_outpoint[op])
        selected_total = sum(u.output.amount for u in selected)
        if selected_total < needed:
            raise WalletError("selected UTXOs do not cover amount + fee")
    else:
        selected = []
        selected_total = 0
        for utxo in available:
            selected.append(utxo)
            selected_total += utxo.output.amount
            if selected_total >= needed:
                break
        if selected_total < needed:
            raise WalletError("insufficient spendable NetCoin balance")
    sequence = 0xFFFFFFFD if rbf or locktime else 0xFFFFFFFF
    inputs = [TxInput(txid=utxo.txid, vout=utxo.vout, sequence=sequence) for utxo in selected]
    outputs = [TxOutput(amount=amount, address=to_address)]
    change = selected_total - needed
    if change > 0:
        outputs.append(TxOutput(amount=change, address=change_to))
    tx = Transaction(inputs=inputs, outputs=outputs, locktime=locktime)
    for index, utxo in enumerate(selected):
        tx.sign_input(index, self.private_key, utxo)
    temp_utxos = chain.utxo_set()
    chain.validate_regular_transaction(tx, temp_utxos, chain.height() + 1)
    return tx


Wallet.create_transaction = _create_transaction_extended  # type: ignore[assignment]
