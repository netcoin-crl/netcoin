//! NetCoin markets-core migration foundation.
//!
//! This crate captures money-sensitive prediction-market invariants that should
//! eventually be enforced in Rust before the TypeScript UI submits orders.

use serde::{Deserialize, Serialize};
use serde_json::{json, Value};

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


fn value_i64(case: &Value, key: &str, default: i64) -> i64 {
    case.get(key).and_then(Value::as_i64).unwrap_or(default)
}

fn value_u64(case: &Value, key: &str, default: u64) -> u64 {
    case.get(key).and_then(Value::as_u64).unwrap_or(default)
}

fn value_str<'a>(case: &'a Value, key: &str, default: &'a str) -> &'a str {
    case.get(key).and_then(Value::as_str).unwrap_or(default)
}

pub fn valid_quote_value(case: &Value) -> bool {
    value_i64(case, "quantity", 0) > 0 && value_i64(case, "price_bps", 0) > 0 && value_i64(case, "price_bps", 0) < 10_000
}

pub fn probability_sum_value_ok(case: &Value) -> bool {
    let total = value_i64(case, "yes_bps", 0) + value_i64(case, "no_bps", 0);
    let tolerance = value_i64(case, "tolerance_bps", 0);
    total >= 10_000 - tolerance && total <= 10_000 + tolerance
}

pub fn settlement_value_conserves(case: &Value) -> bool {
    value_i64(case, "claimable_payout_sats", 0) + value_i64(case, "fees_sats", 0) <= value_i64(case, "locked_collateral_sats", 0)
}

pub fn price_tick_ok(case: &Value) -> bool {
    let price = value_i64(case, "price_bps", 0);
    let tick = value_i64(case, "tick_bps", 1);
    tick > 0 && price > 0 && price < 10_000 && price % tick == 0
}

pub fn collateral_ok(case: &Value) -> bool {
    let required = value_i64(case, "required_collateral_sats", 0);
    let available = value_i64(case, "available_collateral_sats", 0);
    required >= 0 && available >= required
}

pub fn order_crosses(case: &Value) -> bool {
    let side = value_str(case, "side", "").to_ascii_lowercase();
    let price = value_i64(case, "price_bps", 0);
    let bid = value_i64(case, "best_bid_bps", 0);
    let ask = value_i64(case, "best_ask_bps", 10_000);
    match side.as_str() {
        "buy" => price >= ask,
        "sell" => price <= bid,
        _ => false,
    }
}

pub fn lifecycle_allows_order(case: &Value) -> bool {
    matches!(value_str(case, "state", "").to_ascii_lowercase().as_str(), "open" | "trading")
}

pub fn settlement_state_ok(case: &Value) -> bool {
    let state = value_str(case, "state", "").to_ascii_lowercase();
    let has_outcome = case.get("resolved_outcome").and_then(Value::as_str).map(|s| !s.is_empty()).unwrap_or(false);
    let disputed = case.get("disputed").and_then(Value::as_bool).unwrap_or(false);
    match state.as_str() {
        "resolved" => has_outcome && !disputed,
        "disputed" => disputed,
        _ => !has_outcome,
    }
}

pub fn portfolio_conserves(case: &Value) -> bool {
    let cash = value_i64(case, "cash_sats", 0);
    let pos = value_i64(case, "position_value_sats", 0);
    let locked = value_i64(case, "locked_collateral_sats", 0);
    let equity = value_i64(case, "equity_sats", 0);
    cash >= 0 && pos >= 0 && locked >= 0 && cash + pos + locked == equity
}

pub fn market_actual_for_case(case: &Value) -> Value {
    match value_str(case, "kind", "") {
        "quote" => json!(valid_quote_value(case)),
        "probability_sum" => json!(probability_sum_value_ok(case)),
        "settlement" => json!(settlement_value_conserves(case)),
        "fee_cap" => json!(fee_within_cap(value_u64(case, "fee_bps", 0) as u32, value_u64(case, "max_fee_bps", 0) as u32)),
        "order_notional" => json!(order_notional_ok(value_u64(case, "price_bps", 0) as u32, value_u64(case, "quantity", 0), value_u64(case, "min_notional_sats", 0))),
        "price_tick" => json!(price_tick_ok(case)),
        "collateral" => json!(collateral_ok(case)),
        "crossing" => json!(order_crosses(case)),
        "lifecycle" => json!(lifecycle_allows_order(case)),
        "settlement_state" => json!(settlement_state_ok(case)),
        "portfolio" => json!(portfolio_conserves(case)),
        kind => json!({"unknown_kind": kind}),
    }
}

pub fn run_market_case(case: &Value) -> Value {
    let case_id = value_str(case, "id", "unknown-market-case");
    let expected = case.get("expected").cloned().unwrap_or(Value::Null);
    let actual = market_actual_for_case(case);
    json!({"lane":"markets","case_id":case_id,"passed":expected == actual,"expected":expected,"actual":actual,"detail":"rust-markets-core-executable-parity"})
}

pub fn run_markets_parity_vectors(vectors: &Value) -> Value {
    let cases = vectors.get("markets").and_then(|lane| lane.get("cases")).and_then(Value::as_array).cloned().unwrap_or_default();
    let results: Vec<Value> = cases.iter().map(run_market_case).collect();
    let failed = results.iter().filter(|item| !item.get("passed").and_then(Value::as_bool).unwrap_or(false)).count();
    json!({
        "engine": "netcoin-markets-core-rs-parity",
        "lane": "markets",
        "schema_version": vectors.get("schema_version").cloned().unwrap_or(Value::Null),
        "vector_set": vectors.get("markets").and_then(|lane| lane.get("vector_set")).cloned().unwrap_or(Value::Null),
        "total": results.len(),
        "passed": results.len() - failed,
        "failed": failed,
        "ok": failed == 0,
        "results": results,
    })
}
