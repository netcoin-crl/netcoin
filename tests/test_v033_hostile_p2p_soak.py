from netcoin.hostile_p2p_soak import load_soak_scenarios, run_hostile_p2p_soak, run_hostile_p2p_soak_scenario


def test_v033_hostile_p2p_soak_vectors_pass():
    result = run_hostile_p2p_soak()
    assert result["ok"] is True
    assert result["scenario_count"] == 3
    assert result["passed"] == 3


def test_v033_eclipse_attempt_is_detected_but_vector_still_stable():
    scenarios = load_soak_scenarios()["scenarios"]
    eclipse = next(item for item in scenarios if item["id"] == "eclipse-attempt-detected")
    actual = run_hostile_p2p_soak_scenario(eclipse)
    assert actual == eclipse["expected_summary"]
    assert actual["eclipse_detected"] is True
    assert actual["ok"] is False
