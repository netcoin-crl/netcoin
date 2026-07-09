//! NetCoin wallet-core migration foundation.
//!
//! The Python wallet remains the live reference implementation. This crate is a
//! Rust migration boundary for wallet policy/risk decisions and executable
//! parity vectors.

use serde::{Deserialize, Serialize};
use serde_json::{json, Value};

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "lowercase")]
pub enum RiskDecision {
    Allow,
    Review,
    Block,
}

impl RiskDecision {
    pub fn as_str(&self) -> &'static str {
        match self {
            RiskDecision::Allow => "allow",
            RiskDecision::Review => "review",
            RiskDecision::Block => "block",
        }
    }
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct WalletPreview {
    pub input_count: u32,
    pub output_count: u32,
    pub amount_sats: i64,
    pub fee_sats: i64,
    pub balance_after_sats: i64,
    pub warnings: Vec<String>,
}

impl WalletPreview {
    pub fn decision(&self) -> RiskDecision {
        if self.amount_sats < 0 || self.fee_sats < 0 || self.balance_after_sats < 0 {
            return RiskDecision::Block;
        }
        if self.warnings.iter().any(|w| {
            let w = w.to_lowercase();
            w.contains("frozen") || w.contains("poison")
        }) {
            return RiskDecision::Block;
        }
        if !self.warnings.is_empty() || self.input_count > 20 {
            return RiskDecision::Review;
        }
        RiskDecision::Allow
    }
}

pub fn crate_role() -> &'static str {
    "wallet-core-executable-parity-domain"
}

pub fn decision_from_parts(
    input_count: u32,
    amount_sats: i64,
    fee_sats: i64,
    balance_after_sats: i64,
    warnings: Vec<String>,
) -> RiskDecision {
    WalletPreview {
        input_count,
        output_count: 2,
        amount_sats,
        fee_sats,
        balance_after_sats,
        warnings,
    }
    .decision()
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct WalletPolicyPreview {
    pub input_count: u32,
    pub amount_sats: i64,
    pub fee_sats: i64,
    pub balance_after_sats: i64,
    pub fee_rate_sat_vb: u32,
    pub dust_change_sats: u64,
    pub recipient_reused: bool,
    pub warnings: Vec<String>,
}

pub fn policy_decision(preview: &WalletPolicyPreview) -> RiskDecision {
    if preview.amount_sats < 0 || preview.fee_sats < 0 || preview.balance_after_sats < 0 {
        return RiskDecision::Block;
    }
    if preview.warnings.iter().any(|w| {
        let w = w.to_lowercase();
        w.contains("frozen") || w.contains("poison")
    }) || preview.fee_rate_sat_vb >= 250
    {
        return RiskDecision::Block;
    }
    if !preview.warnings.is_empty()
        || preview.input_count > 20
        || preview.fee_rate_sat_vb >= 50
        || (preview.dust_change_sats > 0 && preview.dust_change_sats < 546)
        || preview.recipient_reused
    {
        return RiskDecision::Review;
    }
    RiskDecision::Allow
}

pub fn policy_decision_from_parts(
    input_count: u32,
    balance_after_sats: i64,
    fee_rate_sat_vb: u32,
    dust_change_sats: u64,
    recipient_reused: bool,
    warnings: Vec<String>,
) -> RiskDecision {
    policy_decision(&WalletPolicyPreview {
        input_count,
        amount_sats: 0,
        fee_sats: 0,
        balance_after_sats,
        fee_rate_sat_vb,
        dust_change_sats,
        recipient_reused,
        warnings,
    })
}

fn value_i64(case: &Value, key: &str, default: i64) -> i64 {
    case.get(key).and_then(Value::as_i64).unwrap_or(default)
}

fn value_u32(case: &Value, key: &str, default: u32) -> u32 {
    case.get(key)
        .and_then(Value::as_u64)
        .and_then(|v| u32::try_from(v).ok())
        .unwrap_or(default)
}

fn value_u64(case: &Value, key: &str, default: u64) -> u64 {
    case.get(key).and_then(Value::as_u64).unwrap_or(default)
}

fn value_bool(case: &Value, key: &str, default: bool) -> bool {
    case.get(key).and_then(Value::as_bool).unwrap_or(default)
}

fn value_warnings(case: &Value) -> Vec<String> {
    case.get("warnings")
        .and_then(Value::as_array)
        .map(|items| {
            items
                .iter()
                .filter_map(Value::as_str)
                .map(ToOwned::to_owned)
                .collect()
        })
        .unwrap_or_default()
}

pub fn wallet_decision(case: &Value) -> String {
    let preview = WalletPolicyPreview {
        input_count: value_u32(case, "input_count", 0),
        amount_sats: value_i64(case, "amount_sats", 0),
        fee_sats: value_i64(case, "fee_sats", 0),
        balance_after_sats: value_i64(case, "balance_after_sats", 0),
        fee_rate_sat_vb: value_u32(case, "fee_rate_sat_vb", 0),
        dust_change_sats: value_u64(case, "dust_change_sats", 0),
        recipient_reused: value_bool(case, "recipient_reused", false),
        warnings: value_warnings(case),
    };
    policy_decision(&preview).as_str().to_string()
}

pub fn wallet_policy_summary(case: &Value) -> Value {
    let decision = wallet_decision(case);
    let warnings = value_warnings(case);
    json!({
        "decision": decision,
        "input_count": value_u32(case, "input_count", 0),
        "output_count": value_u32(case, "output_count", 0),
        "warning_count": warnings.len(),
        "fee_rate_sat_vb": value_u32(case, "fee_rate_sat_vb", 0),
        "dust_change_sats": value_u64(case, "dust_change_sats", 0),
        "recipient_reused": value_bool(case, "recipient_reused", false),
    })
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub struct WalletParityCaseResult {
    pub lane: String,
    pub case_id: String,
    pub passed: bool,
    pub expected: Value,
    pub actual: Value,
    pub detail: String,
}

pub fn run_wallet_case(case: &Value) -> WalletParityCaseResult {
    let case_id = case
        .get("id")
        .and_then(Value::as_str)
        .unwrap_or("unknown-wallet-case")
        .to_string();
    let expected = case
        .get("decision")
        .cloned()
        .unwrap_or_else(|| Value::String("unknown".to_string()));
    let actual = Value::String(wallet_decision(case));
    WalletParityCaseResult {
        lane: "wallet".to_string(),
        case_id,
        passed: expected == actual,
        expected,
        actual,
        detail: "".to_string(),
    }
}

pub fn run_wallet_parity_vectors(vectors: &Value) -> Value {
    let cases: Vec<Value> = vectors
        .get("wallet")
        .and_then(|wallet| wallet.get("cases"))
        .and_then(Value::as_array)
        .cloned()
        .unwrap_or_default();
    let results: Vec<WalletParityCaseResult> = cases.iter().map(run_wallet_case).collect();
    let failed = results.iter().filter(|result| !result.passed).count();
    json!({
        "ok": failed == 0,
        "lane": "wallet",
        "schema_version": vectors.get("schema_version").cloned().unwrap_or(Value::Null),
        "wallet_cases": results.len(),
        "passed": results.len() - failed,
        "failed": failed,
        "results": results,
    })
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn blocks_negative_balance() {
        let preview = WalletPreview {
            input_count: 1,
            output_count: 2,
            amount_sats: 100,
            fee_sats: 1,
            balance_after_sats: -1,
            warnings: vec![],
        };
        assert_eq!(preview.decision(), RiskDecision::Block);
    }

    #[test]
    fn reviews_warning() {
        let preview = WalletPreview {
            input_count: 1,
            output_count: 2,
            amount_sats: 100,
            fee_sats: 1,
            balance_after_sats: 100,
            warnings: vec!["high fee".to_string()],
        };
        assert_eq!(preview.decision(), RiskDecision::Review);
    }

    #[test]
    fn executable_case_matches_policy() {
        let case = json!({
            "id": "preview-fee-rate-threshold-review",
            "input_count": 1,
            "amount_sats": 100_000,
            "fee_sats": 5_000,
            "balance_after_sats": 895_000,
            "fee_rate_sat_vb": 50,
            "warnings": [],
            "decision": "review"
        });
        let result = run_wallet_case(&case);
        assert!(result.passed);
        assert_eq!(result.actual, json!("review"));
    }
}
