from pathlib import Path

import pytest

from netcoin.apps import AppError, AppStore, route_app_get, route_app_post
from netcoin.chain import Blockchain
from netcoin.wallet import Wallet


def test_reward_succeeds_under_daily_cap_and_fails_over_it(tmp_path: Path):
    chain = Blockchain(tmp_path / "chain")
    recipient = Wallet.create()
    store = AppStore(chain.data_dir)

    status, policy = route_app_post(
        store, chain, "/api/developer/funding-policy", {"developer_id": "game-studio", "daily_cap_sats": 5_000}
    )
    assert status == 200
    assert policy["daily_cap_sats"] == 5_000

    ok_status, ok_reward = route_app_post(
        store,
        chain,
        "/api/developer/rewards",
        {"developer_id": "game-studio", "player_id": "p1", "address": recipient.address, "amount_sats": 4_000},
    )
    assert ok_status == 200
    assert ok_reward["amount_sats"] == 4_000

    with pytest.raises(AppError, match="daily spend cap exceeded"):
        store.create_developer_reward(
            {"developer_id": "game-studio", "player_id": "p2", "address": recipient.address, "amount_sats": 2_000}
        )


def test_withdrawal_respects_the_same_daily_cap(tmp_path: Path):
    chain = Blockchain(tmp_path / "chain")
    recipient = Wallet.create()
    store = AppStore(chain.data_dir)
    store.set_developer_funding_policy({"developer_id": "game-studio", "daily_cap_sats": 1_000})

    with pytest.raises(AppError, match="daily spend cap exceeded"):
        store.create_developer_withdrawal(
            {"developer_id": "game-studio", "address": recipient.address, "amount_sats": 1_500}
        )


def test_pause_blocks_all_new_rewards_and_withdrawals_for_that_developer(tmp_path: Path):
    chain = Blockchain(tmp_path / "chain")
    recipient = Wallet.create()
    store = AppStore(chain.data_dir)
    store.set_developer_funding_policy({"developer_id": "game-studio", "paused": True})

    with pytest.raises(AppError, match="funding is paused"):
        store.create_developer_reward({"developer_id": "game-studio", "address": recipient.address, "amount_sats": 100})
    with pytest.raises(AppError, match="funding is paused"):
        store.create_developer_withdrawal(
            {"developer_id": "game-studio", "address": recipient.address, "amount_sats": 100}
        )
    # a different, unpaused developer is unaffected
    other_status, other_reward = route_app_post(
        store,
        chain,
        "/api/developer/rewards",
        {"developer_id": "other-studio", "address": recipient.address, "amount_sats": 100},
    )
    assert other_status == 200
    assert other_reward["amount_sats"] == 100


def test_allowlist_rejects_a_non_listed_payout_address(tmp_path: Path):
    chain = Blockchain(tmp_path / "chain")
    allowed = Wallet.create()
    other = Wallet.create()
    store = AppStore(chain.data_dir)
    store.set_developer_funding_policy({"developer_id": "game-studio", "allowlisted_addresses": [allowed.address]})

    ok_status, ok_reward = route_app_post(
        store,
        chain,
        "/api/developer/rewards",
        {"developer_id": "game-studio", "address": allowed.address, "amount_sats": 100},
    )
    assert ok_status == 200

    with pytest.raises(AppError, match="not allowlisted"):
        store.create_developer_reward({"developer_id": "game-studio", "address": other.address, "amount_sats": 100})


def test_per_user_cap_limits_a_single_player_without_limiting_others(tmp_path: Path):
    chain = Blockchain(tmp_path / "chain")
    recipient = Wallet.create()
    store = AppStore(chain.data_dir)
    store.set_developer_funding_policy({"developer_id": "game-studio", "per_user_cap_sats": 1_000})

    store.create_developer_reward(
        {"developer_id": "game-studio", "player_id": "p1", "address": recipient.address, "amount_sats": 900}
    )
    with pytest.raises(AppError, match="per-user daily cap exceeded"):
        store.create_developer_reward(
            {"developer_id": "game-studio", "player_id": "p1", "address": recipient.address, "amount_sats": 200}
        )
    # a different player under the same developer is unaffected
    other_reward = store.create_developer_reward(
        {"developer_id": "game-studio", "player_id": "p2", "address": recipient.address, "amount_sats": 900}
    )
    assert other_reward["amount_sats"] == 900


def test_batch_rewards_enforce_the_same_policy_cumulatively(tmp_path: Path):
    chain = Blockchain(tmp_path / "chain")
    recipient = Wallet.create()
    store = AppStore(chain.data_dir)
    store.set_developer_funding_policy({"developer_id": "game-studio", "daily_cap_sats": 1_000})

    with pytest.raises(AppError, match="daily spend cap exceeded"):
        store.create_batch_rewards(
            {
                "developer_id": "game-studio",
                "rewards": [
                    {"address": recipient.address, "amount_sats": 600},
                    {"address": recipient.address, "amount_sats": 600},
                ],
            }
        )
    # nothing from the rejected batch should have been persisted
    assert not any(r.get("batch_id") for r in store.load().get("rewards", {}).values())


def test_funding_policy_get_reads_back_configured_values(tmp_path: Path):
    chain = Blockchain(tmp_path / "chain")
    store = AppStore(chain.data_dir)
    route_app_post(
        store,
        chain,
        "/api/developer/funding-policy",
        {"developer_id": "game-studio", "daily_cap_sats": 50_000, "paused": False},
    )
    status, policy, _ctype = route_app_get(
        store, chain, "/api/developer/funding-policy", {"developer_id": ["game-studio"]}
    )
    assert status == 200
    assert policy["daily_cap_sats"] == 50_000
    assert policy["paused"] is False
