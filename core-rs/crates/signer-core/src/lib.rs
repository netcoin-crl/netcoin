//! NetCoin signer-core executable parity foundation.
//!
//! This crate mirrors frozen Python signer/offline/hardware policy vectors. It is
//! not yet the live signer; it is a migration boundary for Rust signer safety.

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
            let body = sorted
                .into_iter()
                .map(|(key, value)| format!("{}:{}", serde_json::to_string(key).expect("key json"), canonical_json(value)))
                .collect::<Vec<_>>()
                .join(",");
            format!("{{{body}}}")
        }
    }
}

fn value_i64(case: &Value, key: &str, default: i64) -> i64 { case.get(key).and_then(Value::as_i64).unwrap_or(default) }
fn value_bool(case: &Value, key: &str, default: bool) -> bool { case.get(key).and_then(Value::as_bool).unwrap_or(default) }
fn value_str<'a>(case: &'a Value, key: &str, default: &'a str) -> &'a str { case.get(key).and_then(Value::as_str).unwrap_or(default) }

pub fn signer_digest(case: &Value) -> String {
    let payload = case.get("payload").unwrap_or(&Value::Null);
    double_sha256_hex(canonical_json(payload).as_bytes())
}

pub fn signer_policy_summary(case: &Value) -> Value {
    let required = value_i64(case, "required_signers", 1);
    let available = value_i64(case, "available_signers", 0);
    let amount = value_i64(case, "amount_sats", 0);
    let offline = value_bool(case, "offline", false);
    let hardware = value_bool(case, "hardware", false);
    let unknown_sighash = value_bool(case, "unknown_sighash", false);
    let decision = if amount < 0 || required <= 0 || available < required || unknown_sighash {
        "block"
    } else if offline || hardware {
        "review"
    } else {
        "allow"
    };
    json!({"decision": decision, "required_signers": required, "available_signers": available})
}

pub fn signer_envelope_summary(case: &Value) -> Value {
    let envelope = json!({
        "address": value_str(case, "address", ""),
        "kind": value_str(case, "kind_label", "offline-signing-envelope"),
        "network": value_str(case, "network", "testnet"),
        "tx_digest": value_str(case, "tx_digest", ""),
    });
    let valid = !value_str(case, "address", "").is_empty() && !value_str(case, "tx_digest", "").is_empty();
    json!({"valid": valid, "digest": double_sha256_hex(canonical_json(&envelope).as_bytes())})
}

pub fn signer_actual_for_case(case: &Value) -> Value {
    match value_str(case, "kind", "") {
        "digest" => json!(signer_digest(case)),
        "policy" => signer_policy_summary(case),
        "envelope" => signer_envelope_summary(case),
        kind => json!({"unknown_kind": kind}),
    }
}

pub fn signer_expected_for_case(case: &Value) -> Value {
    match value_str(case, "kind", "") {
        "digest" => case.get("expected_hex").cloned().unwrap_or(Value::Null),
        "policy" | "envelope" => case.get("expected_summary").cloned().unwrap_or(Value::Null),
        kind => json!({"unknown_kind": kind}),
    }
}

pub fn run_signer_case(case: &Value) -> Value {
    let expected = signer_expected_for_case(case);
    let actual = signer_actual_for_case(case);
    json!({"lane":"signer","case_id":value_str(case,"id","unknown-signer-case"),"passed":expected == actual,"expected":expected,"actual":actual,"detail":"rust-signer-core-executable-parity"})
}

pub fn run_signer_parity_vectors(vectors: &Value) -> Value {
    let cases = vectors.get("signer").and_then(|lane| lane.get("cases")).and_then(Value::as_array).cloned().unwrap_or_default();
    let results: Vec<Value> = cases.iter().map(run_signer_case).collect();
    let failed = results.iter().filter(|item| !item.get("passed").and_then(Value::as_bool).unwrap_or(false)).count();
    json!({"engine":"netcoin-signer-core-rs-parity","lane":"signer","schema_version":vectors.get("schema_version").cloned().unwrap_or(Value::Null),"vector_set":vectors.get("signer").and_then(|lane| lane.get("vector_set")).cloned().unwrap_or(Value::Null),"total":results.len(),"passed":results.len()-failed,"failed":failed,"ok":failed==0,"results":results})
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn blocks_missing_threshold() {
        let case = json!({"required_signers":2,"available_signers":1,"amount_sats":1});
        assert_eq!(signer_policy_summary(&case).get("decision").and_then(Value::as_str), Some("block"));
    }
}
