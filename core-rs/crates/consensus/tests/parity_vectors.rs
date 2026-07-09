//! Cross-implementation parity: the Rust consensus helpers must reproduce the
//! SAME frozen vectors that the Python reference (`architecture/parity-vectors.json`)
//! and the executable parity suite use. This is a real differential check, not an
//! isolated unit assert — the fixture is the shared source of truth for cutover.

use netcoin_consensus::{
    basic_utxo_ok, block_header_summary, block_weight_ok, checkpoint_value_ok, double_sha256_hex, headers_link_value,
    merkle_pair_hash, merkle_root_hex, money_in_range, subsidy_at_height, tx_fee_ok, tx_parse_summary, MoneyRangeCheck,
};
use serde_json::Value;

const FIXTURE: &str = include_str!(concat!(env!("CARGO_MANIFEST_DIR"), "/../../fixtures/parity-vectors.json"));

fn hex_to_bytes(hex: &str) -> Vec<u8> {
    assert!(hex.len() % 2 == 0, "hex inputs must have even length");
    (0..hex.len())
        .step_by(2)
        .map(|i| u8::from_str_radix(&hex[i..i + 2], 16).expect("valid fixture hex"))
        .collect()
}

#[test]
fn rust_reproduces_frozen_consensus_parity_vectors() {
    let root: Value = serde_json::from_str(FIXTURE).expect("fixture is valid JSON");
    let cases = root["consensus"]["cases"].as_array().expect("consensus cases exist");
    let mut checked = 0u32;

    for case in cases {
        let kind = case.get("kind").and_then(Value::as_str).unwrap_or("");
        let id = case.get("id").and_then(Value::as_str).unwrap_or("?");

        match kind {
            "double_sha256" => {
                let payload = if let Some(hex) = case.get("input_hex").and_then(Value::as_str) {
                    hex_to_bytes(hex)
                } else {
                    case.get("input_utf8").and_then(Value::as_str).unwrap_or("").as_bytes().to_vec()
                };
                assert_eq!(double_sha256_hex(&payload), case["expected_hex"].as_str().unwrap(), "{id}");
            }
            "money_range" => {
                let check = MoneyRangeCheck {
                    amount_sats: case["amount_sats"].as_i64().unwrap(),
                    max_money_sats: case["max_money_sats"].as_i64().unwrap(),
                };
                assert_eq!(money_in_range(&check), case["expected"].as_bool().unwrap(), "{id}");
            }
            "headers" => {
                let genesis_previous = case.get("genesis_previous").and_then(Value::as_str).unwrap_or("");
                assert_eq!(headers_link_value(&case["headers"], genesis_previous), case["expected"].as_bool().unwrap(), "{id}");
            }
            "checkpoint" => {
                assert_eq!(checkpoint_value_ok(&case["headers"], &case["checkpoints"]), case["expected"].as_bool().unwrap(), "{id}");
            }
            "merkle_pair" => {
                assert_eq!(
                    merkle_pair_hash(case["left_hex"].as_str().unwrap(), case["right_hex"].as_str().unwrap()),
                    case["expected_hex"].as_str().unwrap(),
                    "{id}"
                );
            }
            "block_weight" => {
                assert_eq!(block_weight_ok(case["weight"].as_u64().unwrap(), case["max_weight"].as_u64().unwrap()), case["expected"].as_bool().unwrap(), "{id}");
            }
            "tx_fee" => {
                assert_eq!(tx_fee_ok(case["input_sats"].as_i64().unwrap(), case["output_sats"].as_i64().unwrap()), case["expected"].as_bool().unwrap(), "{id}");
            }
            "merkle_root" => {
                let leaves: Vec<String> = case["leaves_hex"].as_array().unwrap().iter().map(|v| v.as_str().unwrap().to_string()).collect();
                assert_eq!(merkle_root_hex(&leaves), case["expected_hex"].as_str().unwrap(), "{id}");
            }
            "subsidy" => {
                let got = subsidy_at_height(
                    case["base_reward_sats"].as_u64().unwrap(),
                    case["height"].as_u64().unwrap(),
                    case["interval"].as_u64().unwrap(),
                    case["numerator"].as_u64().unwrap(),
                    case["denominator"].as_u64().unwrap(),
                );
                assert_eq!(got, Some(case["expected_sats"].as_u64().unwrap()), "{id}");
            }
            "tx_parse" => {
                assert_eq!(tx_parse_summary(&case["tx"]), case["expected_summary"].clone(), "{id}");
            }
            "block_header" => {
                assert_eq!(block_header_summary(&case["header"]), case["expected_summary"].clone(), "{id}");
            }
            "basic_utxo" => {
                assert_eq!(basic_utxo_ok(case), case["expected"].as_bool().unwrap(), "{id}");
            }
            other => panic!("unhandled consensus vector kind {other} in {id}"),
        }
        checked += 1;
    }

    assert_eq!(checked as usize, cases.len(), "every consensus vector must be covered by Rust");
}
