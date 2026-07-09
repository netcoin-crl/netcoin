use netcoin_consensus::run_consensus_parity_vectors;
use serde_json::Value;
use sha2::{Digest, Sha256};
use std::{env, fs, process};

fn main() {
    let path = env::args().nth(1).unwrap_or_else(|| "../../fixtures/parity-vectors.json".to_string());
    let raw = match fs::read_to_string(&path) {
        Ok(value) => value,
        Err(err) => {
            eprintln!("failed to read parity vector file {path}: {err}");
            process::exit(2);
        }
    };
    let vectors: Value = match serde_json::from_str(&raw) {
        Ok(value) => value,
        Err(err) => {
            eprintln!("failed to parse parity vector JSON {path}: {err}");
            process::exit(2);
        }
    };
    let input_sha = {
        let digest = Sha256::digest(raw.as_bytes());
        digest.iter().map(|byte| format!("{:02x}", byte)).collect::<String>()
    };
    let report = run_consensus_parity_vectors(&vectors, Some(input_sha));
    println!("{}", serde_json::to_string_pretty(&report).expect("report serializes"));
    if report.get("ok").and_then(Value::as_bool).unwrap_or(false) {
        process::exit(0);
    }
    process::exit(1);
}
