"""Exchange-facing JSON-RPC helpers.

These methods intentionally wrap existing chain indexes instead of adding any
custodial wallet behavior to the node.
"""

from netcoin.chain import Blockchain
from netcoin.params import COINBASE_MATURITY
from netcoin.rpc import RPCServer
from netcoin.wallet import Wallet


def test_exchange_rpc_address_and_tx_status(tmp_path):
    chain = Blockchain(tmp_path / "chain")
    miner = Wallet.create()
    for _ in range(COINBASE_MATURITY + 1):
        chain.mine_block(miner.segwit_address)

    rpc = RPCServer(chain)
    coinbase = chain.chain[1].transactions[0]

    valid = rpc.call("validateaddress", [miner.segwit_address])
    assert valid["isvalid"] is True
    assert valid["network"] == "netcoin"
    assert valid["iswitness"] is True

    balance = rpc.call("getaddressbalance", [miner.segwit_address])
    assert balance["spendable_sats"] > 0
    assert balance["immature_sats"] > 0
    assert balance["tip_hash"] == chain.tip_hash()

    utxos = rpc.call("listaddressutxos", [miner.segwit_address])
    assert any(item["txid"] == coinbase.txid() and item["spendable"] is True for item in utxos["utxos"])
    assert all("confirmations" in item and "amount" in item for item in utxos["utxos"])

    summary = rpc.call("getaddresssummary", [miner.segwit_address, 5, 0])
    assert summary["transaction_count"] == COINBASE_MATURITY + 1
    assert summary["transaction_ids_limit"] == 5
    assert summary["has_next"] is True

    status = rpc.call("gettransactionstatus", [coinbase.txid()])
    assert status["confirmed"] is True
    assert status["confirmations"] == chain.height() - 1 + 1
    assert status["block_height"] == 1
    assert status["total_output_sats"] > 0


def test_exchange_rpc_info_payload(tmp_path):
    chain = Blockchain(tmp_path / "chain")
    rpc = RPCServer(chain)

    info = rpc.call("getexchangeinfo", [])
    assert info["chain"] == "netcoin"
    assert info["ticker"] == "NET"
    assert info["recommended_min_confirmations"] >= 1
    assert info["coinbase_maturity"] == COINBASE_MATURITY
    assert info["withdrawal_broadcast_method"] == "sendrawtransaction"
