//! Cross-implementation parity: the Rust mempool helpers must reproduce the
//! frozen Python reference mempool vectors.

use netcoin_mempool_core::{mempool_ordering_summary, mempool_policy_summary};
use serde_json::Value;

const FIXTURE: &str = include_str!(concat!(env!("CARGO_MANIFEST_DIR"), "/../../fixtures/parity-vectors.json"));

#[test]
fn rust_reproduces_frozen_mempool_parity_vectors() {
    let root: Value = serde_json::from_str(FIXTURE).expect("fixture is valid JSON");
    let cases = root["mempool"]["cases"].as_array().expect("mempool cases exist");
    let mut checked = 0u32;

    for case in cases {
        let kind = case.get("kind").and_then(Value::as_str).unwrap_or("");
        let id = case.get("id").and_then(Value::as_str).unwrap_or("?");
        match kind {
            "policy" => assert_eq!(mempool_policy_summary(case), case["expected_summary"].clone(), "{id}"),
            "ordering" => assert_eq!(mempool_ordering_summary(case), case["expected_summary"].clone(), "{id}"),
            other => panic!("unhandled mempool vector kind {other} in {id}"),
        }
        checked += 1;
    }

    assert_eq!(checked as usize, cases.len(), "every mempool vector must be covered by Rust");
}
