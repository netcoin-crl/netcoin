//! Cross-implementation parity: the Rust consensus helpers must reproduce the
//! SAME frozen vectors that the Python reference (`architecture/parity-vectors.json`)
//! and the executable parity suite use. This is a real differential check, not an
//! isolated unit assert — the fixture is the shared source of truth for cutover.

use netcoin_consensus::{block_weight_ok, money_in_range, subsidy_at_height, tx_fee_ok, MoneyRangeCheck};
use serde_json::Value;

const FIXTURE: &str = include_str!(concat!(env!("CARGO_MANIFEST_DIR"), "/../../fixtures/parity-vectors.json"));

#[test]
fn rust_reproduces_frozen_parity_vectors() {
    let root: Value = serde_json::from_str(FIXTURE).expect("fixture is valid JSON");
    let mut checked = 0u32;

    for (_section, value) in root.as_object().expect("fixture root is an object") {
        let cases = match value.get("cases").and_then(Value::as_array) {
            Some(cases) => cases,
            None => continue,
        };
        for case in cases {
            let kind = case.get("kind").and_then(Value::as_str).unwrap_or("");
            let id = case.get("id").and_then(Value::as_str).unwrap_or("?");

            let result = match kind {
                "money_range" => {
                    let check = MoneyRangeCheck {
                        amount_sats: case["amount_sats"].as_i64().unwrap(),
                        max_money_sats: case["max_money_sats"].as_i64().unwrap(),
                    };
                    Some((money_in_range(&check), case["expected"].as_bool().unwrap()))
                }
                "tx_fee" => Some((
                    tx_fee_ok(case["input_sats"].as_i64().unwrap(), case["output_sats"].as_i64().unwrap()),
                    case["expected"].as_bool().unwrap(),
                )),
                "block_weight" => Some((
                    block_weight_ok(case["weight"].as_u64().unwrap(), case["max_weight"].as_u64().unwrap()),
                    case["expected"].as_bool().unwrap(),
                )),
                "subsidy" => {
                    let got = subsidy_at_height(
                        case["base_reward_sats"].as_u64().unwrap(),
                        case["height"].as_u64().unwrap(),
                        case["interval"].as_u64().unwrap(),
                        case["numerator"].as_u64().unwrap(),
                        case["denominator"].as_u64().unwrap(),
                    );
                    Some((got == Some(case["expected_sats"].as_u64().unwrap()), true))
                }
                _ => None,
            };

            if let Some((got, expected)) = result {
                assert_eq!(got, expected, "parity mismatch on frozen vector {id}");
                checked += 1;
            }
        }
    }

    assert!(checked >= 7, "expected to check at least 7 frozen vectors, checked {checked}");
}
