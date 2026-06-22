"""Network and consensus parameters for NetCoin.

NetCoin intentionally uses Bitcoin-like economics and validation concepts while
choosing different network/address bytes and an easy proof-of-work limit so the
chain can be mined on a laptop for learning and testing.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict

NAME = "NetCoin"
TICKER = "NET"

COIN = 100_000_000
MAX_MONEY = 21_000_000 * COIN
INITIAL_SUBSIDY = 50 * COIN
HALVING_INTERVAL = 210_000

TARGET_SPACING_SECONDS = 10 * 60
DIFFICULTY_ADJUSTMENT_INTERVAL = 2016
TARGET_TIMESPAN_SECONDS = TARGET_SPACING_SECONDS * DIFFICULTY_ADJUSTMENT_INTERVAL

INITIAL_BITS = 0x207FFFFF
POW_LIMIT_BITS = 0x207FFFFF
COINBASE_MATURITY = 100

# Address and key version bytes. NetCoin intentionally does NOT reuse Bitcoin's
# mainnet prefixes.
ADDRESS_VERSION = bytes([0x35])
P2PKH_ADDRESS_VERSION = ADDRESS_VERSION
P2SH_ADDRESS_VERSION = bytes([0x75])
WIF_VERSION = bytes([0xB5])
BECH32_HRP = "net"
BECH32M_HRP = "net"
WITNESS_HRP = BECH32_HRP

DEFAULT_DATA_DIR = ".netcoin"
DEFAULT_NODE_PORT = 18444
DEFAULT_RPC_PORT = 18445
DEFAULT_POOL_PORT = 18446
DEFAULT_P2P_PORT = 18447
PROTOCOL_VERSION = 2
# Keep in sync with pyproject.toml [project].version on every release.
NODE_VERSION = "0.4.2"
NETWORK_NAME = "testnet"
USER_AGENT = f"NetCoin:{NODE_VERSION}"
P2P_MAGIC = bytes.fromhex("fabfb5da")

# Built-in public testnet seeds so a new node can join without copying URLs.
DEFAULT_TESTNET_SEEDS = (
    "http://seed1.netcoin.online:28444",
    "http://seed2.netcoin.online:28444",
    "http://seed3.netcoin.online:28444",
)

# Maximum accepted HTTP request body for the node and RPC servers, in bytes.
# Anything larger is rejected before it is read, to blunt trivial memory-DoS
# attempts against public endpoints. A whole block (4M weight) serializes well
# under this in NetCoin's JSON encoding.
MAX_REQUEST_BODY_BYTES = 8 * 1024 * 1024

ZERO_HASH = "00" * 32
GENESIS_TIMESTAMP = 1_718_400_000
GENESIS_MESSAGE = "NetCoin genesis - an educational Bitcoin-like chain, not Bitcoin"

# Policy and standardness knobs.
MAX_BLOCK_WEIGHT = 4_000_000
MAX_STANDARD_TX_WEIGHT = 400_000
MIN_RELAY_FEE_PER_KB = 1000
INCREMENTAL_RELAY_FEE = 1000
DUST_LIMIT = 546
DUST_THRESHOLD = DUST_LIMIT
MAX_MEMPOOL_TRANSACTIONS = 50_000
MAX_ANCESTORS = 25
MAX_DESCENDANTS = 25
MAX_MEMPOOL_ANCESTORS = MAX_ANCESTORS
MAX_MEMPOOL_DESCENDANTS = MAX_DESCENDANTS
LOCKTIME_THRESHOLD = 500_000_000

SIGHASH_ALL = 1
SEQUENCE_FINAL = 0xFFFFFFFF
SEQUENCE_RBF = 0xFFFFFFFD


@dataclass(frozen=True)
class NetworkProfile:
    name: str
    description: str
    default_port: int
    default_rpc_port: int
    bech32_hrp: str
    initial_bits: int
    pow_limit_bits: int
    data_dir: str
    target_spacing_seconds: int = TARGET_SPACING_SECONDS
    coinbase_maturity: int = COINBASE_MATURITY


NETWORKS: Dict[str, NetworkProfile] = {
    "main": NetworkProfile(
        name="main",
        description="Local main NetCoin parameters",
        default_port=DEFAULT_NODE_PORT,
        default_rpc_port=DEFAULT_RPC_PORT,
        bech32_hrp=BECH32_HRP,
        initial_bits=INITIAL_BITS,
        pow_limit_bits=POW_LIMIT_BITS,
        data_dir=".netcoin",
    ),
    "testnet": NetworkProfile(
        name="testnet",
        description="Public-test style profile with separate data directory recommended",
        default_port=28444,
        default_rpc_port=28445,
        bech32_hrp="tnet",
        initial_bits=INITIAL_BITS,
        pow_limit_bits=POW_LIMIT_BITS,
        data_dir=".netcoin-testnet",
    ),
    "signet": NetworkProfile(
        name="signet",
        description="Federated-test style profile placeholder",
        default_port=38444,
        default_rpc_port=38445,
        bech32_hrp="snet",
        initial_bits=INITIAL_BITS,
        pow_limit_bits=POW_LIMIT_BITS,
        data_dir=".netcoin-signet",
    ),
    "regtest": NetworkProfile(
        name="regtest",
        description="Private regression-test profile for instant local experiments",
        default_port=18444,
        default_rpc_port=18445,
        bech32_hrp="rnet",
        initial_bits=INITIAL_BITS,
        pow_limit_bits=POW_LIMIT_BITS,
        data_dir=".netcoin-regtest",
    ),
}
