//! NetCoin markets-core migration foundation.
//!
//! This crate captures money-sensitive prediction-market invariants that should
//! eventually be enforced in Rust before the TypeScript UI submits orders.

use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub enum Side {
    Buy,
    Sell,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub enum Outcome {
    Yes,
    No,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct Quote {
    pub outcome: Outcome,
    pub side: Side,
    /// Price in basis points from 0 to 10_000, representing 0% to 100%.
    pub price_bps: u32,
    pub quantity: u64,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct SettlementCheck {
    pub locked_collateral_sats: u64,
    pub claimable_payout_sats: u64,
    pub fees_sats: u64,
}

pub fn valid_quote(q: &Quote) -> bool {
    q.quantity > 0 && q.price_bps > 0 && q.price_bps < 10_000
}

pub fn settlement_conserves_value(s: &SettlementCheck) -> bool {
    s.claimable_payout_sats.saturating_add(s.fees_sats) <= s.locked_collateral_sats
}

pub fn binary_probability_sum_ok(yes_bps: u32, no_bps: u32, tolerance_bps: u32) -> bool {
    let sum = yes_bps.saturating_add(no_bps);
    let lower = 10_000u32.saturating_sub(tolerance_bps);
    let upper = 10_000u32.saturating_add(tolerance_bps);
    sum >= lower && sum <= upper
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn quote_bounds() {
        assert!(valid_quote(&Quote { outcome: Outcome::Yes, side: Side::Buy, price_bps: 5000, quantity: 1 }));
        assert!(!valid_quote(&Quote { outcome: Outcome::Yes, side: Side::Buy, price_bps: 10000, quantity: 1 }));
    }

    #[test]
    fn settlement_cannot_overpay() {
        assert!(settlement_conserves_value(&SettlementCheck { locked_collateral_sats: 100, claimable_payout_sats: 99, fees_sats: 1 }));
        assert!(!settlement_conserves_value(&SettlementCheck { locked_collateral_sats: 100, claimable_payout_sats: 101, fees_sats: 0 }));
    }
}

pub fn quote_from_bps(outcome: Outcome, side: Side, price_bps: u32, quantity: u64) -> Quote {
    Quote { outcome, side, price_bps, quantity }
}

pub fn fee_within_cap(fee_bps: u32, max_fee_bps: u32) -> bool {
    fee_bps <= max_fee_bps
}

pub fn order_notional_ok(price_bps: u32, quantity: u64, min_notional_sats: u64) -> bool {
    let notional = (price_bps as u128).saturating_mul(quantity as u128) / 10_000u128;
    notional >= min_notional_sats as u128
}

pub fn market_accounting_conserves(locked_collateral_sats: u64, claimable_payout_sats: u64, fees_sats: u64) -> bool {
    claimable_payout_sats.saturating_add(fees_sats) <= locked_collateral_sats
}
