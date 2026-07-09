//! NetCoin Rust mempool policy parity foundation.
//!
//! This crate is a migration boundary, not yet the live mempool. It mirrors the
//! frozen Python reference mempool vectors so fee policy, duplicate rejection,
//! orphan handling, RBF bump rules, and package limits can be promoted safely.

use serde::{Deserialize, Serialize};
use serde_json::{json, Value};
use std::collections::HashSet;

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct MempoolPolicySummary {
    pub accepted: bool,
    pub code: String,
    pub fee_rate_sat_vb: i64,
}

pub fn engine_name() -> &'static str {
    "netcoin-mempool-rs-parity-foundation"
}

pub fn mempool_fee_rate_sat_vb(fee_sats: i64, vsize: i64) -> i64 {
    if vsize <= 0 {
        return 0;
    }
    fee_sats / vsize
}

fn as_i64_field(value: &Value, key: &str, default: i64) -> i64 {
    value.get(key).and_then(Value::as_i64).unwrap_or(default)
}

fn string_set(value: &Value, key: &str) -> HashSet<String> {
    value
        .get(key)
        .and_then(Value::as_array)
        .map(|items| items.iter().filter_map(Value::as_str).map(str::to_string).collect())
        .unwrap_or_default()
}

pub fn mempool_policy_summary(case: &Value) -> Value {
    let txid = case.get("txid").and_then(Value::as_str).unwrap_or("");
    let fee_sats = as_i64_field(case, "fee_sats", 0);
    let vsize = as_i64_field(case, "vsize", 0);
    let fee_rate = mempool_fee_rate_sat_vb(fee_sats, vsize);
    let current_pool = string_set(case, "current_pool_txids");
    let inputs = case.get("inputs").and_then(Value::as_array);
    let outputs = case.get("outputs").and_then(Value::as_array);

    let mut accepted = true;
    let mut code = "accepted";

    if txid.is_empty()
        || inputs.map(|items| items.is_empty()).unwrap_or(true)
        || outputs.map(|items| items.is_empty()).unwrap_or(true)
        || vsize <= 0
        || fee_sats < 0
    {
        accepted = false;
        code = "malformed";
    } else if current_pool.contains(txid) {
        accepted = false;
        code = "duplicate";
    } else if vsize > as_i64_field(case, "max_vsize", 100_000) {
        accepted = false;
        code = "too_large";
    } else if inputs
        .unwrap()
        .iter()
        .any(|txin| !txin.get("available").and_then(Value::as_bool).unwrap_or(true))
    {
        accepted = false;
        code = "orphan";
    } else if as_i64_field(case, "locktime", 0) > as_i64_field(case, "current_height", 0) {
        accepted = false;
        code = "nonfinal";
    } else if as_i64_field(case, "ancestor_count", 0) > as_i64_field(case, "max_ancestors", 25) {
        accepted = false;
        code = "too_many_ancestors";
    } else if as_i64_field(case, "descendant_count", 0) > as_i64_field(case, "max_descendants", 25) {
        accepted = false;
        code = "too_many_descendants";
    } else if outputs.unwrap().iter().any(|output| {
        output.get("amount_sats").and_then(Value::as_i64).unwrap_or(0)
            < as_i64_field(case, "dust_threshold_sats", 546)
    }) {
        accepted = false;
        code = "dust";
    } else if fee_rate < as_i64_field(case, "min_relay_fee_rate_sat_vb", 1) {
        accepted = false;
        code = "low_fee_rate";
    } else if case.get("replacement_for").is_some()
        && fee_sats <= as_i64_field(case, "old_fee_sats", 0) + as_i64_field(case, "min_replacement_delta_sats", 0)
    {
        accepted = false;
        code = "insufficient_replacement_fee";
    }

    json!({"accepted": accepted, "code": code, "fee_rate_sat_vb": fee_rate})
}

pub fn mempool_ordering_summary(case: &Value) -> Value {
    let mut txs: Vec<(String, i64)> = case
        .get("txs")
        .and_then(Value::as_array)
        .map(|items| {
            items
                .iter()
                .map(|item| {
                    (
                        item.get("txid").and_then(Value::as_str).unwrap_or("").to_string(),
                        mempool_fee_rate_sat_vb(as_i64_field(item, "fee_sats", 0), as_i64_field(item, "vsize", 0)),
                    )
                })
                .collect()
        })
        .unwrap_or_default();
    txs.sort_by(|a, b| b.1.cmp(&a.1).then_with(|| a.0.cmp(&b.0)));
    let ordered_txids: Vec<String> = txs.iter().map(|item| item.0.clone()).collect();
    let top_fee_rate = txs.first().map(|item| item.1).unwrap_or(0);
    json!({"ordered_txids": ordered_txids, "top_fee_rate_sat_vb": top_fee_rate})
}

fn mempool_expected_for_case(case: &Value) -> Value {
    case.get("expected_summary").cloned().unwrap_or(Value::Null)
}

fn mempool_actual_for_case(case: &Value) -> Value {
    match case.get("kind").and_then(Value::as_str).unwrap_or("") {
        "policy" => mempool_policy_summary(case),
        "ordering" => mempool_ordering_summary(case),
        other => json!({"accepted": false, "code": format!("unknown:{other}"), "fee_rate_sat_vb": 0}),
    }
}

pub fn run_mempool_case(case: &Value) -> Value {
    let case_id = case.get("id").and_then(Value::as_str).unwrap_or("?");
    let kind = case.get("kind").and_then(Value::as_str).unwrap_or("");
    let expected = mempool_expected_for_case(case);
    let actual = mempool_actual_for_case(case);
    json!({
        "lane": "mempool",
        "case_id": case_id,
        "kind": kind,
        "passed": expected == actual,
        "expected": expected,
        "actual": actual,
        "detail": "rust-mempool-policy-parity",
    })
}

pub fn run_mempool_parity_vectors(vectors: &Value, input_file_sha256: Option<String>) -> Value {
    let cases = vectors
        .get("mempool")
        .and_then(|lane| lane.get("cases"))
        .and_then(Value::as_array)
        .cloned()
        .unwrap_or_default();
    let results: Vec<Value> = cases.iter().map(run_mempool_case).collect();
    let failed = results.iter().filter(|item| !item.get("passed").and_then(Value::as_bool).unwrap_or(false)).count();
    json!({
        "engine": engine_name(),
        "lane": "mempool",
        "schema_version": vectors.get("schema_version").cloned().unwrap_or(Value::Null),
        "vector_set": vectors.get("mempool").and_then(|lane| lane.get("vector_set")).cloned().unwrap_or(Value::Null),
        "input_file_sha256": input_file_sha256,
        "total": results.len(),
        "passed": results.len() - failed,
        "failed": failed,
        "ok": failed == 0,
        "results": results,
    })
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn checks_fee_rate_floor() {
        assert_eq!(mempool_fee_rate_sat_vb(1200, 200), 6);
        assert_eq!(mempool_fee_rate_sat_vb(1, 0), 0);
    }

    #[test]
    fn accepts_basic_standard_policy_case() {
        let case = json!({
            "txid": "tx-standard",
            "fee_sats": 1200,
            "vsize": 200,
            "inputs": [{"outpoint": "aa:0", "available": true}],
            "outputs": [{"amount_sats": 50000}],
            "current_pool_txids": [],
            "min_relay_fee_rate_sat_vb": 2,
            "dust_threshold_sats": 546,
            "max_vsize": 100000,
            "ancestor_count": 0,
            "max_ancestors": 25,
            "descendant_count": 0,
            "max_descendants": 25,
            "locktime": 0,
            "current_height": 100
        });
        assert_eq!(mempool_policy_summary(&case), json!({"accepted": true, "code": "accepted", "fee_rate_sat_vb": 6}));
    }
}
