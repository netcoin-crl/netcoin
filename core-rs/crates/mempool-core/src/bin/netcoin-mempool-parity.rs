use netcoin_mempool_core::run_mempool_parity_vectors;
use sha2::{Digest, Sha256};
use std::{env, fs, process};

fn to_hex(bytes: &[u8]) -> String {
    const HEX: &[u8; 16] = b"0123456789abcdef";
    let mut out = String::with_capacity(bytes.len() * 2);
    for byte in bytes {
        out.push(HEX[(byte >> 4) as usize] as char);
        out.push(HEX[(byte & 0x0f) as usize] as char);
    }
    out
}

fn main() {
    let Some(path) = env::args().nth(1) else {
        eprintln!("usage: netcoin-mempool-parity <parity-vectors.json>");
        process::exit(2);
    };
    let bytes = match fs::read(&path) {
        Ok(bytes) => bytes,
        Err(err) => {
            eprintln!("failed to read {path}: {err}");
            process::exit(2);
        }
    };
    let vectors: serde_json::Value = match serde_json::from_slice(&bytes) {
        Ok(value) => value,
        Err(err) => {
            eprintln!("failed to parse {path}: {err}");
            process::exit(2);
        }
    };
    let digest = to_hex(&Sha256::digest(&bytes));
    let report = run_mempool_parity_vectors(&vectors, Some(digest));
    match serde_json::to_string_pretty(&report) {
        Ok(text) => println!("{text}"),
        Err(err) => {
            eprintln!("failed to serialize report: {err}");
            process::exit(2);
        }
    }
    if !report.get("ok").and_then(serde_json::Value::as_bool).unwrap_or(false) {
        process::exit(1);
    }
}
