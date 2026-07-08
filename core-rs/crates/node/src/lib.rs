//! NetCoin node migration foundation.
//!
//! This crate contains stable node/sync domain structs for future Rust P2P work.

use serde::{Deserialize, Serialize};

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
