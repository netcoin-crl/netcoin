use netcoin_signer_core::run_signer_parity_vectors;
use serde_json::Value;
use std::{env, fs, process};

fn main() {
    let Some(path) = env::args().nth(1) else {
        eprintln!("usage: netcoin-signer-parity <parity-vectors.json>");
        process::exit(2);
    };
    let payload = match fs::read_to_string(&path) {
        Ok(payload) => payload,
        Err(err) => { eprintln!("could not read {path}: {err}"); process::exit(2); }
    };
    let vectors: Value = match serde_json::from_str(&payload) {
        Ok(value) => value,
        Err(err) => { eprintln!("could not parse {path}: {err}"); process::exit(2); }
    };
    let report = run_signer_parity_vectors(&vectors);
    println!("{}", serde_json::to_string_pretty(&report).expect("serialize signer parity report"));
    if report.get("ok").and_then(Value::as_bool) != Some(true) { process::exit(1); }
}
