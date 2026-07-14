use netcoin_rs::{NetcoinClient, SignedEnvelope};
use std::io::{Read, Write};
use std::net::TcpListener;
use std::thread;

fn one_response_server(body: &'static str) -> String {
    let listener = TcpListener::bind("127.0.0.1:0").expect("bind local test server");
    let addr = listener.local_addr().expect("local addr");
    thread::spawn(move || {
        let (mut stream, _) = listener.accept().expect("accept");
        let mut request = [0_u8; 1024];
        let _ = stream.read(&mut request);
        let response = format!(
            "HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nContent-Length: {}\r\nConnection: close\r\n\r\n{}",
            body.len(),
            body
        );
        stream
            .write_all(response.as_bytes())
            .expect("write response");
    });
    format!("http://{}", addr)
}

#[test]
fn client_reads_local_node_info_shape() {
    let base = one_response_server(r#"{"ok":true,"node":{"height":0}}"#);
    let client = NetcoinClient::new(base);
    let response = client.node_info().expect("node info");
    assert!(response.contains("\"node\""));
}

#[test]
fn client_builds_signed_envelope_with_caller_signer() {
    let envelope = SignedEnvelope::build(
        "net1qdemo",
        "POST",
        "/v1/tx",
        "abc123",
        "nonce",
        |message| {
            assert!(message.contains("netcoin-signed-envelope-v1"));
            "signature".to_string()
        },
    );
    assert_eq!(envelope.method, "POST");
    assert_eq!(envelope.path, "/v1/tx");
    assert_eq!(envelope.signature, "signature");
}
