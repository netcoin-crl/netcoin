//! NetCoin indexer-core executable parity foundation.
//!
//! This crate mirrors Python reference indexer snapshots for address history,
//! reorg rollback, market-event rollups, and deterministic snapshot hashes.

use serde_json::{json, Value};
use sha2::{Digest, Sha256};
use std::collections::BTreeMap;

fn to_hex(bytes: &[u8]) -> String {
    const HEX: &[u8; 16] = b"0123456789abcdef";
    let mut out = String::with_capacity(bytes.len() * 2);
    for byte in bytes {
        out.push(HEX[(byte >> 4) as usize] as char);
        out.push(HEX[(byte & 0x0f) as usize] as char);
    }
    out
}

pub fn double_sha256_hex(bytes: &[u8]) -> String {
    let first = Sha256::digest(bytes);
    let second = Sha256::digest(first);
    to_hex(&second)
}

pub fn canonical_json(value: &Value) -> String {
    match value {
        Value::Null | Value::Bool(_) | Value::Number(_) | Value::String(_) => serde_json::to_string(value).expect("scalar json"),
        Value::Array(items) => format!("[{}]", items.iter().map(canonical_json).collect::<Vec<_>>().join(",")),
        Value::Object(map) => {
            let sorted: BTreeMap<_, _> = map.iter().collect();
            let body = sorted.into_iter().map(|(k,v)| format!("{}:{}", serde_json::to_string(k).expect("key json"), canonical_json(v))).collect::<Vec<_>>().join(",");
            format!("{{{body}}}")
        }
    }
}

fn value_i64(case: &Value, key: &str, default: i64) -> i64 { case.get(key).and_then(Value::as_i64).unwrap_or(default) }
fn value_str<'a>(case: &'a Value, key: &str, default: &'a str) -> &'a str { case.get(key).and_then(Value::as_str).unwrap_or(default) }

pub fn indexer_address_summary(case: &Value) -> Value {
    let mut received = 0i64;
    let mut sent = 0i64;
    let events = case.get("events").and_then(Value::as_array).cloned().unwrap_or_default();
    for event in &events {
        let amount = event.get("amount_sats").and_then(Value::as_i64).unwrap_or(0);
        match event.get("direction").and_then(Value::as_str).unwrap_or("") {
            "receive" => received += amount,
            "send" => sent += amount,
            _ => {}
        }
    }
    json!({"received_sats": received, "sent_sats": sent, "balance_sats": received - sent, "event_count": events.len()})
}

pub fn indexer_reorg_summary(case: &Value) -> Value {
    let old_height = value_i64(case, "old_tip_height", 0);
    let fork_height = value_i64(case, "fork_height", 0);
    let new_height = value_i64(case, "new_tip_height", 0);
    json!({"rollback_blocks": (old_height - fork_height).max(0), "apply_blocks": (new_height - fork_height).max(0), "new_tip_height": new_height})
}

pub fn indexer_market_event_summary(case: &Value) -> Value {
    let events = case.get("events").and_then(Value::as_array).cloned().unwrap_or_default();
    let mut volume = 0i64;
    let mut disputes = 0usize;
    let mut settlements = 0usize;
    for event in &events {
        match event.get("type").and_then(Value::as_str).unwrap_or("") {
            "trade" => volume += event.get("notional_sats").and_then(Value::as_i64).unwrap_or(0),
            "dispute" => disputes += 1,
            "settlement" => settlements += 1,
            _ => {}
        }
    }
    json!({"trade_volume_sats": volume, "disputes": disputes, "settlements": settlements, "event_count": events.len()})
}

pub fn indexer_snapshot_hash(case: &Value) -> String {
    let snapshot = case.get("snapshot").unwrap_or(&Value::Null);
    double_sha256_hex(canonical_json(snapshot).as_bytes())
}

pub fn indexer_actual_for_case(case: &Value) -> Value {
    match value_str(case, "kind", "") {
        "address_summary" => indexer_address_summary(case),
        "reorg" => indexer_reorg_summary(case),
        "market_events" => indexer_market_event_summary(case),
        "snapshot_hash" => json!(indexer_snapshot_hash(case)),
        kind => json!({"unknown_kind": kind}),
    }
}

pub fn indexer_expected_for_case(case: &Value) -> Value {
    match value_str(case, "kind", "") {
        "address_summary" | "reorg" | "market_events" => case.get("expected_summary").cloned().unwrap_or(Value::Null),
        "snapshot_hash" => case.get("expected_hex").cloned().unwrap_or(Value::Null),
        kind => json!({"unknown_kind": kind}),
    }
}

pub fn run_indexer_case(case: &Value) -> Value {
    let expected = indexer_expected_for_case(case);
    let actual = indexer_actual_for_case(case);
    json!({"lane":"indexer","case_id":value_str(case,"id","unknown-indexer-case"),"passed":expected == actual,"expected":expected,"actual":actual,"detail":"rust-indexer-core-executable-parity"})
}

pub fn run_indexer_parity_vectors(vectors: &Value) -> Value {
    let cases = vectors.get("indexer").and_then(|lane| lane.get("cases")).and_then(Value::as_array).cloned().unwrap_or_default();
    let results: Vec<Value> = cases.iter().map(run_indexer_case).collect();
    let failed = results.iter().filter(|item| !item.get("passed").and_then(Value::as_bool).unwrap_or(false)).count();
    json!({"engine":"netcoin-indexer-core-rs-parity","lane":"indexer","schema_version":vectors.get("schema_version").cloned().unwrap_or(Value::Null),"vector_set":vectors.get("indexer").and_then(|lane| lane.get("vector_set")).cloned().unwrap_or(Value::Null),"total":results.len(),"passed":results.len()-failed,"failed":failed,"ok":failed==0,"results":results})
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn summarizes_address_events() {
        let case = json!({"events":[{"direction":"receive","amount_sats":10},{"direction":"send","amount_sats":3}]});
        assert_eq!(indexer_address_summary(&case), json!({"received_sats":10,"sent_sats":3,"balance_sats":7,"event_count":2}));
    }
}
