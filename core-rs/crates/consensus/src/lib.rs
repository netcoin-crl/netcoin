//! NetCoin Rust consensus parity foundation.
//!
//! This crate is a migration boundary, not yet the live consensus engine. It
//! exposes deterministic helpers and vector structures that must match the
//! Python reference implementation before Rust code can replace live paths.

use serde::{Deserialize, Serialize};
use serde_json::{json, Value};
use sha2::{Digest, Sha256};

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct ConsensusVectorSummary {
    pub vector_set: String,
    pub valid_cases: u64,
    pub invalid_cases: u64,
    pub reference: String,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct HeaderLink {
    pub height: u64,
    pub hash: String,
    pub previous_hash: String,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct MoneyRangeCheck {
    pub amount_sats: i64,
    pub max_money_sats: i64,
}

pub fn engine_name() -> &'static str {
    "netcoin-consensus-rs-parity-foundation"
}

pub fn validate_vector_summary(summary: &ConsensusVectorSummary) -> bool {
    !summary.vector_set.is_empty()
        && !summary.reference.is_empty()
        && summary.valid_cases > 0
        && summary.invalid_cases > 0
}

pub fn double_sha256_hex(bytes: &[u8]) -> String {
    let first = Sha256::digest(bytes);
    let second = Sha256::digest(first);
    to_hex(&second)
}

pub fn money_in_range(check: &MoneyRangeCheck) -> bool {
    check.amount_sats >= 0 && check.amount_sats <= check.max_money_sats
}

pub fn validate_linked_headers(headers: &[HeaderLink], genesis_previous: &str) -> bool {
    let mut expected_previous = genesis_previous.to_string();
    for header in headers {
        if header.previous_hash != expected_previous {
            return false;
        }
        if header.hash.is_empty() {
            return false;
        }
        expected_previous = header.hash.clone();
    }
    true
}

pub fn merkle_pair_hash(left_hex: &str, right_hex: &str) -> String {
    let payload = format!("{}{}", left_hex, right_hex);
    double_sha256_hex(payload.as_bytes())
}


pub const ZERO_HASH: &str = "0000000000000000000000000000000000000000000000000000000000000000";

fn invalid_summary() -> Value {
    json!({"valid": false})
}

fn as_i64_field(value: &Value, key: &str) -> Option<i64> {
    value.get(key).and_then(Value::as_i64)
}

fn as_u64_field(value: &Value, key: &str) -> Option<u64> {
    value.get(key).and_then(Value::as_u64)
}

fn lower_hex_64(value: &Value, key: &str) -> Option<String> {
    let out = value.get(key)?.as_str()?.to_ascii_lowercase();
    if out.len() == 64 && out.chars().all(|c| c.is_ascii_hexdigit() && !c.is_ascii_uppercase()) {
        Some(out)
    } else {
        None
    }
}

pub fn tx_parse_summary(tx: &Value) -> Value {
    let inputs = match tx.get("inputs").and_then(Value::as_array) {
        Some(items) if !items.is_empty() => items,
        _ => return invalid_summary(),
    };
    let outputs = match tx.get("outputs").and_then(Value::as_array) {
        Some(items) => items,
        None => return invalid_summary(),
    };

    let mut total_output: i64 = 0;
    for output in outputs {
        let Some(amount) = as_i64_field(output, "amount") else {
            return invalid_summary();
        };
        if amount < 0 {
            return invalid_summary();
        }
        total_output = match total_output.checked_add(amount) {
            Some(value) => value,
            None => return invalid_summary(),
        };
    }

    let first = &inputs[0];
    let coinbase = inputs.len() == 1
        && first.get("txid").and_then(Value::as_str).map(|s| s.eq_ignore_ascii_case(ZERO_HASH)).unwrap_or(false)
        && as_i64_field(first, "vout") == Some(-1)
        && first.get("coinbase").and_then(Value::as_str).map(|s| !s.is_empty()).unwrap_or(false);

    json!({
        "valid": true,
        "version": as_i64_field(tx, "version").unwrap_or(1),
        "locktime": as_i64_field(tx, "locktime").unwrap_or(0),
        "input_count": inputs.len(),
        "output_count": outputs.len(),
        "total_output_sats": total_output,
        "coinbase": coinbase,
    })
}

pub fn block_header_summary(header: &Value) -> Value {
    let Some(previous_hash) = lower_hex_64(header, "previous_hash") else {
        return invalid_summary();
    };
    let Some(merkle_root) = lower_hex_64(header, "merkle_root") else {
        return invalid_summary();
    };
    let Some(version) = as_i64_field(header, "version") else {
        return invalid_summary();
    };
    let Some(timestamp) = as_i64_field(header, "timestamp") else {
        return invalid_summary();
    };
    let Some(bits) = as_i64_field(header, "bits") else {
        return invalid_summary();
    };
    let Some(nonce) = as_i64_field(header, "nonce") else {
        return invalid_summary();
    };
    let Some(height) = as_i64_field(header, "height") else {
        return invalid_summary();
    };
    let payload = format!(
        "{{\"bits\":{},\"height\":{},\"merkle_root\":\"{}\",\"nonce\":{},\"previous_hash\":\"{}\",\"timestamp\":{},\"version\":{}}}",
        bits, height, merkle_root, nonce, previous_hash, timestamp, version
    );
    json!({"valid": true, "hash_hex": double_sha256_hex(payload.as_bytes()), "height": height})
}

pub fn basic_utxo_ok(case: &Value) -> bool {
    use std::collections::HashSet;

    let inputs = match case.get("inputs").and_then(Value::as_array) {
        Some(items) if !items.is_empty() => items,
        _ => return false,
    };
    let outputs = match case.get("outputs").and_then(Value::as_array) {
        Some(items) => items,
        None => return false,
    };
    let spend_height = as_i64_field(case, "spend_height").unwrap_or(0);
    let coinbase_maturity = as_i64_field(case, "coinbase_maturity").unwrap_or(0);
    let mut seen: HashSet<String> = HashSet::new();
    let mut total_in: i128 = 0;
    let mut total_out: i128 = 0;

    for input in inputs {
        let Some(outpoint) = input.get("outpoint").and_then(Value::as_str) else {
            return false;
        };
        if outpoint.is_empty() || !seen.insert(outpoint.to_string()) {
            return false;
        }
        let Some(amount) = as_i64_field(input, "amount_sats") else {
            return false;
        };
        if amount < 0 {
            return false;
        }
        let height = as_i64_field(input, "height").unwrap_or(0);
        if input.get("coinbase").and_then(Value::as_bool).unwrap_or(false)
            && spend_height - height < coinbase_maturity
        {
            return false;
        }
        total_in += i128::from(amount);
    }

    for output in outputs {
        let Some(amount) = as_i64_field(output, "amount_sats") else {
            return false;
        };
        if amount < 0 {
            return false;
        }
        total_out += i128::from(amount);
    }

    total_out <= total_in
}

pub fn headers_link_value(headers: &Value, genesis_previous: &str) -> bool {
    let Some(items) = headers.as_array() else {
        return false;
    };
    let mut expected_previous = genesis_previous.to_string();
    for header in items {
        let previous = header.get("previous_hash").or_else(|| header.get("prev_hash")).and_then(Value::as_str).unwrap_or("");
        let hash = header.get("hash").and_then(Value::as_str).unwrap_or("");
        if previous != expected_previous || hash.is_empty() {
            return false;
        }
        expected_previous = hash.to_string();
    }
    true
}

pub fn checkpoint_value_ok(headers: &Value, checkpoints: &Value) -> bool {
    let Some(items) = headers.as_array() else {
        return false;
    };
    let Some(points) = checkpoints.as_object() else {
        return true;
    };
    for header in items {
        let height_key = match as_i64_field(header, "height") {
            Some(height) => height.to_string(),
            None => continue,
        };
        if let Some(expected) = points.get(&height_key).and_then(Value::as_str) {
            let actual = header.get("hash").and_then(Value::as_str).unwrap_or("");
            if actual != expected {
                return false;
            }
        }
    }
    true
}


fn consensus_expected_for_case(case: &Value) -> Value {
    let kind = case.get("kind").and_then(Value::as_str).unwrap_or("");
    match kind {
        "double_sha256" | "merkle_pair" | "merkle_root" => case.get("expected_hex").cloned().unwrap_or(Value::Null),
        "money_range" | "headers" | "checkpoint" | "block_weight" | "tx_fee" | "basic_utxo" => {
            case.get("expected").cloned().unwrap_or(Value::Null)
        }
        "subsidy" => case.get("expected_sats").cloned().unwrap_or(Value::Null),
        "tx_parse" | "block_header" => case.get("expected_summary").cloned().unwrap_or(Value::Null),
        _ => json!({"unknown_kind": kind}),
    }
}

fn bytes_from_case(case: &Value) -> Vec<u8> {
    if let Some(hex) = case.get("input_hex").and_then(Value::as_str) {
        hex_to_bytes(hex).unwrap_or_default()
    } else {
        case.get("input_utf8").and_then(Value::as_str).unwrap_or("").as_bytes().to_vec()
    }
}

fn consensus_actual_for_case(case: &Value) -> Value {
    let kind = case.get("kind").and_then(Value::as_str).unwrap_or("");
    match kind {
        "double_sha256" => json!(double_sha256_hex(&bytes_from_case(case))),
        "money_range" => json!(money_in_range(&MoneyRangeCheck {
            amount_sats: as_i64_field(case, "amount_sats").unwrap_or(i64::MIN),
            max_money_sats: as_i64_field(case, "max_money_sats").unwrap_or(i64::MIN),
        })),
        "headers" => json!(headers_link_value(&case["headers"], case.get("genesis_previous").and_then(Value::as_str).unwrap_or(""))),
        "checkpoint" => json!(checkpoint_value_ok(&case["headers"], &case["checkpoints"])),
        "merkle_pair" => json!(merkle_pair_hash(
            case.get("left_hex").and_then(Value::as_str).unwrap_or(""),
            case.get("right_hex").and_then(Value::as_str).unwrap_or(""),
        )),
        "block_weight" => json!(block_weight_ok(
            as_u64_field(case, "weight").unwrap_or(u64::MAX),
            as_u64_field(case, "max_weight").unwrap_or(0),
        )),
        "tx_fee" => json!(tx_fee_ok(
            as_i64_field(case, "input_sats").unwrap_or(i64::MIN),
            as_i64_field(case, "output_sats").unwrap_or(i64::MIN),
        )),
        "merkle_root" => {
            let leaves: Vec<String> = case
                .get("leaves_hex")
                .and_then(Value::as_array)
                .map(|items| items.iter().filter_map(Value::as_str).map(str::to_string).collect())
                .unwrap_or_default();
            json!(merkle_root_hex(&leaves))
        }
        "subsidy" => match subsidy_at_height(
            as_u64_field(case, "base_reward_sats").unwrap_or(0),
            as_u64_field(case, "height").unwrap_or(0),
            as_u64_field(case, "interval").unwrap_or(0),
            as_u64_field(case, "numerator").unwrap_or(0),
            as_u64_field(case, "denominator").unwrap_or(0),
        ) {
            Some(value) => json!(value),
            None => Value::Null,
        },
        "tx_parse" => tx_parse_summary(&case["tx"]),
        "block_header" => block_header_summary(&case["header"]),
        "basic_utxo" => json!(basic_utxo_ok(case)),
        _ => json!({"unknown_kind": kind}),
    }
}

pub fn run_consensus_case(case: &Value) -> Value {
    let case_id = case.get("id").and_then(Value::as_str).unwrap_or("?");
    let kind = case.get("kind").and_then(Value::as_str).unwrap_or("");
    let expected = consensus_expected_for_case(case);
    let actual = consensus_actual_for_case(case);
    json!({
        "lane": "consensus",
        "case_id": case_id,
        "kind": kind,
        "passed": expected == actual,
        "expected": expected,
        "actual": actual,
        "detail": "rust-consensus-executable-parity",
    })
}

pub fn run_consensus_parity_vectors(vectors: &Value, input_file_sha256: Option<String>) -> Value {
    let cases = vectors
        .get("consensus")
        .and_then(|lane| lane.get("cases"))
        .and_then(Value::as_array)
        .cloned()
        .unwrap_or_default();
    let results: Vec<Value> = cases.iter().map(run_consensus_case).collect();
    let failed = results.iter().filter(|item| !item.get("passed").and_then(Value::as_bool).unwrap_or(false)).count();
    json!({
        "engine": engine_name(),
        "lane": "consensus",
        "schema_version": vectors.get("schema_version").cloned().unwrap_or(Value::Null),
        "vector_set": vectors.get("consensus").and_then(|lane| lane.get("vector_set")).cloned().unwrap_or(Value::Null),
        "input_file_sha256": input_file_sha256,
        "total": results.len(),
        "passed": results.len() - failed,
        "failed": failed,
        "ok": failed == 0,
        "results": results,
    })
}

fn hex_to_bytes(hex: &str) -> Option<Vec<u8>> {
    if hex.len() % 2 != 0 {
        return None;
    }
    let mut out = Vec::with_capacity(hex.len() / 2);
    let bytes = hex.as_bytes();
    let mut i = 0;
    while i < bytes.len() {
        let high = (bytes[i] as char).to_digit(16)?;
        let low = (bytes[i + 1] as char).to_digit(16)?;
        out.push(((high << 4) | low) as u8);
        i += 2;
    }
    Some(out)
}

fn to_hex(bytes: &[u8]) -> String {
    const HEX: &[u8; 16] = b"0123456789abcdef";
    let mut out = String::with_capacity(bytes.len() * 2);
    for byte in bytes {
        out.push(HEX[(byte >> 4) as usize] as char);
        out.push(HEX[(byte & 0x0f) as usize] as char);
    }
    out
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn validates_vector_summary() {
        let summary = ConsensusVectorSummary {
            vector_set: "starter".to_string(),
            valid_cases: 1,
            invalid_cases: 1,
            reference: "python".to_string(),
        };
        assert!(validate_vector_summary(&summary));
    }

    #[test]
    fn rejects_negative_money() {
        assert!(!money_in_range(&MoneyRangeCheck { amount_sats: -1, max_money_sats: 21_000_000 }));
        assert!(money_in_range(&MoneyRangeCheck { amount_sats: 1, max_money_sats: 21_000_000 }));
    }

    #[test]
    fn validates_header_links() {
        let headers = vec![
            HeaderLink { height: 0, hash: "a".to_string(), previous_hash: "0".to_string() },
            HeaderLink { height: 1, hash: "b".to_string(), previous_hash: "a".to_string() },
        ];
        assert!(validate_linked_headers(&headers, "0"));
    }
}

/// A deterministic parity-case status used by migration tooling.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct ParityCaseStatus {
    pub id: String,
    pub passed: bool,
    pub detail: String,
}

pub fn block_weight_ok(weight: u64, max_weight: u64) -> bool {
    weight <= max_weight
}

pub fn checkpoint_ok(height: u64, hash: &str, checkpoint_hash: Option<&str>) -> bool {
    match checkpoint_hash {
        Some(expected) => expected == hash,
        None => true,
    }
}

pub fn tx_fee_ok(input_sats: i64, output_sats: i64) -> bool {
    input_sats >= 0 && output_sats >= 0 && input_sats >= output_sats
}

pub fn merkle_root_hex(leaves_hex: &[String]) -> String {
    if leaves_hex.is_empty() {
        return double_sha256_hex(b"");
    }
    let mut level = leaves_hex.to_vec();
    while level.len() > 1 {
        if level.len() % 2 == 1 {
            if let Some(last) = level.last().cloned() {
                level.push(last);
            }
        }
        let mut next = Vec::with_capacity(level.len() / 2);
        let mut i = 0usize;
        while i < level.len() {
            let payload = format!("{}{}", level[i], level[i + 1]);
            next.push(double_sha256_hex(payload.as_bytes()));
            i += 2;
        }
        level = next;
    }
    level[0].clone()
}

pub fn subsidy_at_height(base_reward_sats: u64, height: u64, interval: u64, numerator: u64, denominator: u64) -> Option<u64> {
    if interval == 0 || denominator == 0 {
        return None;
    }
    let mut reward = base_reward_sats;
    for _ in 0..(height / interval) {
        reward = reward.saturating_mul(numerator) / denominator;
    }
    Some(reward)
}

#[cfg(test)]
mod v022_parity_tests {
    use super::*;

    #[test]
    fn checks_tx_fee() {
        assert!(tx_fee_ok(150_000, 149_000));
        assert!(!tx_fee_ok(149_000, 150_000));
    }

    #[test]
    fn checks_subsidy_reductions() {
        assert_eq!(subsidy_at_height(5_000_000_000, 530_000, 265_000, 9, 10), Some(4_050_000_000));
    }
}
