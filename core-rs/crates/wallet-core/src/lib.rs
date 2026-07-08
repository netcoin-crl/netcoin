//! NetCoin wallet-core migration foundation.
//!
//! This crate defines stable wallet-domain types that future desktop, mobile,
//! browser, and Python bindings can share once parity vectors are complete.

use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub enum RiskDecision {
    Allow,
    Review,
    Block,
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
        if self.warnings.iter().any(|w| w.contains("frozen") || w.contains("poison")) {
            return RiskDecision::Block;
        }
        if !self.warnings.is_empty() || self.input_count > 20 {
            return RiskDecision::Review;
        }
        RiskDecision::Allow
    }
}

pub fn crate_role() -> &'static str {
    "wallet-core-parity-domain"
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn blocks_negative_balance() {
        let preview = WalletPreview { input_count: 1, output_count: 2, amount_sats: 100, fee_sats: 1, balance_after_sats: -1, warnings: vec![] };
        assert_eq!(preview.decision(), RiskDecision::Block);
    }

    #[test]
    fn reviews_warning() {
        let preview = WalletPreview { input_count: 1, output_count: 2, amount_sats: 100, fee_sats: 1, balance_after_sats: 100, warnings: vec!["high fee".to_string()] };
        assert_eq!(preview.decision(), RiskDecision::Review);
    }
}

pub fn decision_from_parts(input_count: u32, amount_sats: i64, fee_sats: i64, balance_after_sats: i64, warnings: Vec<String>) -> RiskDecision {
    WalletPreview {
        input_count,
        output_count: 2,
        amount_sats,
        fee_sats,
        balance_after_sats,
        warnings,
    }.decision()
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
    }) || preview.fee_rate_sat_vb >= 250 {
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

pub fn policy_decision_from_parts(input_count: u32, balance_after_sats: i64, fee_rate_sat_vb: u32, dust_change_sats: u64, recipient_reused: bool, warnings: Vec<String>) -> RiskDecision {
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
