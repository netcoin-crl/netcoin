//! NetCoin Rust consensus parity foundation.
//!
//! This crate is a migration boundary, not yet the live consensus engine. It
//! exposes deterministic helpers and vector structures that must match the
//! Python reference implementation before Rust code can replace live paths.

use serde::{Deserialize, Serialize};
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
