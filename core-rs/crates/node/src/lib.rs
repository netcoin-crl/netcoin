//! NetCoin node migration foundation.
//!
//! This crate contains stable node/sync domain structs for future Rust P2P work.

use serde::{Deserialize, Serialize};
use serde_json::{json, Value};

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct PeerSnapshot {
    pub address: String,
    pub height: u64,
    pub chainwork: u128,
    pub score: i64,
    pub banned: bool,
}

pub fn best_peer(peers: &[PeerSnapshot]) -> Option<PeerSnapshot> {
    peers
        .iter()
        .filter(|p| !p.banned)
        .max_by_key(|p| (p.chainwork, p.height, p.score))
        .cloned()
}

pub fn crate_role() -> &'static str {
    "node-rs-sync-domain"
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn ignores_banned_best_peer() {
        let peers = vec![
            PeerSnapshot { address: "bad".into(), height: 100, chainwork: 200, score: 0, banned: true },
            PeerSnapshot { address: "good".into(), height: 90, chainwork: 150, score: 10, banned: false },
        ];
        assert_eq!(best_peer(&peers).unwrap().address, "good");
    }
}


fn value_i64(case: &Value, key: &str, default: i64) -> i64 { case.get(key).and_then(Value::as_i64).unwrap_or(default) }
fn value_str<'a>(case: &'a Value, key: &str, default: &'a str) -> &'a str { case.get(key).and_then(Value::as_str).unwrap_or(default) }

pub fn p2p_best_peer_summary(case: &Value) -> Value {
    let peers = case.get("peers").and_then(Value::as_array).cloned().unwrap_or_default();
    let mut best: Option<Value> = None;
    for peer in peers.into_iter().filter(|p| !p.get("banned").and_then(Value::as_bool).unwrap_or(false)) {
        let key = (
            peer.get("chainwork").and_then(Value::as_i64).unwrap_or(0),
            peer.get("height").and_then(Value::as_i64).unwrap_or(0),
            peer.get("score").and_then(Value::as_i64).unwrap_or(0),
            peer.get("address").and_then(Value::as_str).unwrap_or("").to_string(),
        );
        let best_key = best.as_ref().map(|p| (
            p.get("chainwork").and_then(Value::as_i64).unwrap_or(0),
            p.get("height").and_then(Value::as_i64).unwrap_or(0),
            p.get("score").and_then(Value::as_i64).unwrap_or(0),
            p.get("address").and_then(Value::as_str).unwrap_or("").to_string(),
        ));
        if best_key.map(|bk| key > bk).unwrap_or(true) {
            best = Some(peer);
        }
    }
    match best {
        Some(peer) => json!({"best_peer": peer.get("address").and_then(Value::as_str).unwrap_or(""), "height": peer.get("height").and_then(Value::as_i64).unwrap_or(0), "chainwork": peer.get("chainwork").and_then(Value::as_i64).unwrap_or(0)}),
        None => json!({"best_peer":"", "height":0, "chainwork":0}),
    }
}

pub fn p2p_headers_link(headers: &[Value], genesis_previous: &str) -> bool {
    let mut expected = genesis_previous.to_string();
    for (idx, header) in headers.iter().enumerate() {
        let previous = header.get("previous_hash").or_else(|| header.get("prev_hash")).and_then(Value::as_str).unwrap_or("");
        if idx == 0 && !expected.is_empty() && previous != expected { return false; }
        if idx > 0 && previous != expected { return false; }
        let hash = header.get("hash").and_then(Value::as_str).unwrap_or("");
        if hash.is_empty() { return false; }
        expected = hash.to_string();
    }
    true
}

pub fn p2p_checkpoint_ok(headers: &[Value], checkpoints: &Value) -> bool {
    let Some(map) = checkpoints.as_object() else { return true; };
    for header in headers {
        let height_key = header.get("height").and_then(Value::as_i64).unwrap_or(-1).to_string();
        if let Some(expected) = map.get(&height_key).and_then(Value::as_str) {
            if header.get("hash").and_then(Value::as_str).unwrap_or("") != expected { return false; }
        }
    }
    true
}

pub fn p2p_header_sync_summary(case: &Value) -> Value {
    let headers = case.get("headers").and_then(Value::as_array).cloned().unwrap_or_default();
    let linked = p2p_headers_link(&headers, value_str(case, "genesis_previous", ""));
    let checkpoint_ok = p2p_checkpoint_ok(&headers, &case["checkpoints"]);
    let protocol_ok = value_i64(case, "peer_protocol", 0) == value_i64(case, "local_protocol", 0);
    json!({"accepted": linked && checkpoint_ok && protocol_ok, "linked": linked, "checkpoint_ok": checkpoint_ok, "protocol_ok": protocol_ok})
}

pub fn p2p_ban_score_summary(case: &Value) -> Value {
    let score = value_i64(case, "score", 0) + value_i64(case, "penalty", 0);
    let threshold = value_i64(case, "ban_threshold", 100);
    json!({"score": score, "banned": score >= threshold})
}

pub fn p2p_actual_for_case(case: &Value) -> Value {
    match value_str(case, "kind", "") {
        "best_peer" => p2p_best_peer_summary(case),
        "header_sync" => p2p_header_sync_summary(case),
        "ban_score" => p2p_ban_score_summary(case),
        kind => json!({"unknown_kind": kind}),
    }
}

pub fn run_p2p_case(case: &Value) -> Value {
    let expected = case.get("expected_summary").cloned().unwrap_or(Value::Null);
    let actual = p2p_actual_for_case(case);
    json!({"lane":"p2p","case_id":value_str(case,"id","unknown-p2p-case"),"passed":expected == actual,"expected":expected,"actual":actual,"detail":"rust-p2p-header-sync-parity"})
}

pub fn run_p2p_parity_vectors(vectors: &Value) -> Value {
    let cases = vectors.get("p2p").and_then(|lane| lane.get("cases")).and_then(Value::as_array).cloned().unwrap_or_default();
    let results: Vec<Value> = cases.iter().map(run_p2p_case).collect();
    let failed = results.iter().filter(|item| !item.get("passed").and_then(Value::as_bool).unwrap_or(false)).count();
    json!({"engine":"netcoin-node-rs-p2p-parity","lane":"p2p","schema_version":vectors.get("schema_version").cloned().unwrap_or(Value::Null),"vector_set":vectors.get("p2p").and_then(|lane| lane.get("vector_set")).cloned().unwrap_or(Value::Null),"total":results.len(),"passed":results.len()-failed,"failed":failed,"ok":failed==0,"results":results})
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct AddrV2Snapshot {
    pub host: String,
    pub port: u16,
    pub network_id: String,
    pub services: Vec<String>,
    pub best_height: u64,
    pub operator: String,
    pub region: String,
}

pub fn addrv2_network_id(host: &str) -> &'static str {
    let text = host.trim().trim_matches(|c| c == '[' || c == ']').to_ascii_lowercase();
    if text.ends_with(".onion") {
        return "torv3";
    }
    if text.parse::<std::net::Ipv4Addr>().is_ok() {
        return "ipv4";
    }
    if text.parse::<std::net::Ipv6Addr>().is_ok() {
        return "ipv6";
    }
    "dns"
}

pub fn addrv2_snapshot(host: &str, port: u16) -> AddrV2Snapshot {
    AddrV2Snapshot {
        host: host.trim().trim_matches(|c| c == '[' || c == ']').to_ascii_lowercase(),
        port,
        network_id: addrv2_network_id(host).to_string(),
        services: vec![
            "NODE_NETWORK".to_string(),
            "NETCOIN_PEX".to_string(),
            "NETCOIN_COMPACT_BLOCKS".to_string(),
        ],
        best_height: 0,
        operator: String::new(),
        region: String::new(),
    }
}

pub fn pex_select_addrs(peers: &[AddrV2Snapshot], max_records: usize) -> Vec<AddrV2Snapshot> {
    let mut out = Vec::new();
    if max_records == 0 {
        return out;
    }
    for peer in peers.iter() {
        if peer.services.iter().any(|svc| svc == "NETCOIN_PEX") {
            out.push(peer.clone());
        }
        if out.len() >= max_records {
            break;
        }
    }
    out
}

pub fn compact_block_shortid(txid: &str) -> String {
    txid.chars().take(12).collect()
}

#[cfg(test)]
mod m3_tests {
    use super::*;

    #[test]
    fn addrv2_classifies_hosts() {
        assert_eq!(addrv2_network_id("18.220.89.128"), "ipv4");
        assert_eq!(addrv2_network_id("2001:db8::1"), "ipv6");
        assert_eq!(addrv2_network_id("seed.netcoin.online"), "dns");
    }

    #[test]
    fn pex_selects_advertising_peers() {
        let a = addrv2_snapshot("18.220.89.128", 28444);
        let mut b = addrv2_snapshot("18.220.197.20", 28444);
        b.services.clear();
        let selected = pex_select_addrs(&[a.clone(), b], 8);
        assert_eq!(selected, vec![a]);
    }

    #[test]
    fn compact_shortid_is_stable_prefix() {
        assert_eq!(compact_block_shortid("abcdef1234567890"), "abcdef123456");
    }

    #[test]
    fn addrv2_snapshot_normalizes_bracketed_ipv6_and_onion() {
        let ipv6 = addrv2_snapshot("[2001:db8::1]", 28444);
        assert_eq!(ipv6.host, "2001:db8::1");
        assert_eq!(ipv6.network_id, "ipv6");
        let onion = addrv2_snapshot(
            "abcdefghijklmnopqrstuvwxyzabcdefghijklmnopqrstuvwxyzabcd.onion",
            28444,
        );
        assert_eq!(onion.network_id, "torv3");
    }

    #[test]
    fn pex_select_addrs_honors_exact_cap_boundaries() {
        let peers = vec![
            addrv2_snapshot("18.220.89.128", 28444),
            addrv2_snapshot("18.220.197.20", 28444),
            addrv2_snapshot("18.226.74.252", 28444),
        ];
        assert!(pex_select_addrs(&peers, 0).is_empty());
        assert_eq!(pex_select_addrs(&peers, 2).len(), 2);
        assert_eq!(pex_select_addrs(&peers, 3).len(), 3);
        assert_eq!(pex_select_addrs(&peers, 4).len(), 3);
    }

    #[test]
    fn compact_shortid_handles_short_and_empty_txids() {
        assert_eq!(compact_block_shortid("abc"), "abc");
        assert_eq!(compact_block_shortid(""), "");
    }
}
