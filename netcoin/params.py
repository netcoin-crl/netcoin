"""Network and consensus parameters for NetCoin.

NetCoin intentionally uses Bitcoin-like economics and validation concepts while
choosing different network/address bytes and an easy proof-of-work limit so the
chain can be mined on a laptop for learning and testing.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

NAME = "NetCoin"
TICKER = "NET"

COIN = 100_000_000
# The deterministic 10% reduction schedule has an asymptotic supply of roughly
# 132.5M NET: 265,000 blocks * 50 NET / 10% reduction.
MAX_MONEY = 132_500_000 * COIN
INITIAL_SUBSIDY = 50 * COIN

# Public reward schedule: start at 50 NET and reduce by 10% every 265,000 blocks.
# The deterministic schedule activates at height 4,200 so already-mined public
# testnet blocks stay valid. Its reduction epochs are still absolute-height based,
# so the first public 10% event is at height 265,000.
REWARD_START_SUBSIDY = INITIAL_SUBSIDY
REWARD_REDUCTION_INTERVAL = 265_000
REWARD_REDUCTION_NUMERATOR = 9
REWARD_REDUCTION_DENOMINATOR = 10
REWARD_SCHEDULE_ACTIVATION_HEIGHT = 4_200
# Backwards-compatible name for tools/docs that still say "halving interval".
HALVING_INTERVAL = REWARD_REDUCTION_INTERVAL

# Legacy random-emission compatibility window. The live public testnet activated
# this at height 1,000 before the deterministic schedule was chosen. Keep it only
# until REWARD_SCHEDULE_ACTIVATION_HEIGHT so historical blocks validate.
LEGACY_NRE_ACTIVATION_HEIGHT = 1_000
LEGACY_NRE_YEAR_BLOCKS = 720
LEGACY_NRE_BASE_SUBSIDY = 15 * COIN
LEGACY_NRE_SEED_BLOCKS = 10
LEGACY_NRE_SAMPLE_SIZE = 100
LEGACY_NRE_EVEN_THRESHOLD = 40
LEGACY_NRE_CUT_NUMERATOR = 9
LEGACY_NRE_CUT_DENOMINATOR = 10
LEGACY_NRE_DRY_YEAR_LIMIT = 3

# Testnet v2 (real-difficulty relaunch): 2-minute target blocks, retarget every
# 30 blocks (~1h) so difficulty tracks a small, changing miner set quickly.
TARGET_SPACING_SECONDS = 120
DIFFICULTY_ADJUSTMENT_INTERVAL = 30
TARGET_TIMESPAN_SECONDS = TARGET_SPACING_SECONDS * DIFFICULTY_ADJUSTMENT_INTERVAL

# Spacing v2 (NIP-0005 activation-gated, no chain reset): 5-minute target blocks
# from SPACING_V2_ACTIVATION_HEIGHT onward. The activation height is a retarget
# boundary (multiple of DIFFICULTY_ADJUSTMENT_INTERVAL) so exactly one adjustment
# window straddles old-spacing blocks; the standard timespan clamp bounds that
# transition. Below the activation height the original 2-minute schedule applies
# so all historical blocks stay valid.
SPACING_V2_ACTIVATION_HEIGHT = 5_010
TARGET_SPACING_V2_SECONDS = 300


def target_spacing_at(height: int) -> int:
    return TARGET_SPACING_V2_SECONDS if height >= SPACING_V2_ACTIVATION_HEIGHT else TARGET_SPACING_SECONDS


def target_timespan_at(height: int) -> int:
    return target_spacing_at(height) * DIFFICULTY_ADJUSTMENT_INTERVAL


def min_difficulty_gap_at(height: int) -> int:
    return 2 * target_spacing_at(height)


# Launch easy (at the PoW floor) and let the fast retarget ramp difficulty up as
# miners join. MIN_DIFFICULTY_GAP enables the testnet lone-miner rule: a block
# more than this many seconds after its parent may be mined at the PoW floor, so
# the chain can't get stuck if hashpower drops.
INITIAL_BITS = 0x207FFFFF
POW_LIMIT_BITS = 0x207FFFFF
MIN_DIFFICULTY_GAP_SECONDS = 2 * TARGET_SPACING_SECONDS
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
NODE_VERSION = "0.14.0"
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
# New genesis for the testnet v2 relaunch — a different hash from the v1 chain so
# old and new nodes never cross-talk.
GENESIS_TIMESTAMP = 1_750_000_000
GENESIS_MESSAGE = "NetCoin testnet v2 - real proof-of-work relaunch - not Bitcoin"

# Policy and standardness knobs.
MAX_BLOCK_WEIGHT = 4_000_000
MIN_RELAY_FEE_PER_KB = 1000
INCREMENTAL_RELAY_FEE = 1000
DUST_LIMIT = 546
DUST_THRESHOLD = DUST_LIMIT
MAX_MEMPOOL_TRANSACTIONS = 50_000
# Public-node policy guards. These keep one oversized wallet send or stale
# unconfirmed pool from slowing explorer/mining/API traffic. They are policy
# limits only; they do not change consensus validation for confirmed blocks.
MAX_MEMPOOL_BYTES = 32 * 1024 * 1024
MEMPOOL_EXPIRY_SECONDS = 24 * 60 * 60
# Relay/standardness caps. NOT consensus (blocks may contain larger txs); these
# only bound what a node will relay/mempool, protecting public nodes. Raised in
# v0.12.0 now that fast verification (NETCOIN_FAST_CRYPTO / libsecp256k1) keeps
# big-transaction validation cheap. All env-overridable so an operator on the
# pure-Python path can stay conservative.
MAX_STANDARD_TX_INPUTS = int(os.environ.get("NETCOIN_MAX_STD_TX_INPUTS", "1000"))
MAX_STANDARD_TX_WEIGHT = int(os.environ.get("NETCOIN_MAX_STD_TX_WEIGHT", "1000000"))
MAX_WALLET_SEND_INPUTS = int(os.environ.get("NETCOIN_MAX_WALLET_INPUTS", "200"))
MAX_WALLET_SEND_WEIGHT = int(os.environ.get("NETCOIN_MAX_WALLET_WEIGHT", "600000"))
MAX_ANCESTORS = int(os.environ.get("NETCOIN_MAX_ANCESTORS", "100"))
MAX_DESCENDANTS = int(os.environ.get("NETCOIN_MAX_DESCENDANTS", "100"))
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


NETWORKS: dict[str, NetworkProfile] = {
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
