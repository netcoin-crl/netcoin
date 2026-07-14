use std::fmt;
use std::io::{Read, Write};
use std::net::TcpStream;
use std::time::{SystemTime, UNIX_EPOCH};

pub const ENVELOPE_VERSION: &str = "netcoin-signed-envelope-v1";

#[derive(Debug)]
pub enum NetcoinError {
    InvalidUrl(String),
    Io(std::io::Error),
    HttpStatus(u16, String),
    InvalidResponse(String),
}

impl fmt::Display for NetcoinError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            NetcoinError::InvalidUrl(value) => write!(f, "invalid NetCoin URL: {value}"),
            NetcoinError::Io(error) => write!(f, "I/O error: {error}"),
            NetcoinError::HttpStatus(status, body) => write!(f, "HTTP {status}: {body}"),
            NetcoinError::InvalidResponse(value) => write!(f, "invalid response: {value}"),
        }
    }
}

impl std::error::Error for NetcoinError {}

impl From<std::io::Error> for NetcoinError {
    fn from(value: std::io::Error) -> Self {
        NetcoinError::Io(value)
    }
}

#[derive(Clone, Debug, Eq, PartialEq)]
pub struct SignedEnvelope {
    pub version: String,
    pub address: String,
    pub method: String,
    pub path: String,
    pub body_hash: String,
    pub timestamp: u64,
    pub nonce: String,
    pub signature: String,
}

impl SignedEnvelope {
    pub fn message(
        address: &str,
        method: &str,
        path: &str,
        body_hash: &str,
        timestamp: u64,
        nonce: &str,
    ) -> String {
        [
            "NetCoin signed request",
            ENVELOPE_VERSION,
            address,
            &method.to_ascii_uppercase(),
            path,
            body_hash,
            &timestamp.to_string(),
            nonce,
        ]
        .join("\n")
    }

    pub fn build<F>(
        address: impl Into<String>,
        method: &str,
        path: impl Into<String>,
        body_hash: impl Into<String>,
        nonce: impl Into<String>,
        signer: F,
    ) -> Self
    where
        F: FnOnce(&str) -> String,
    {
        let address = address.into();
        let method = method.to_ascii_uppercase();
        let path = path.into();
        let body_hash = body_hash.into();
        let nonce = nonce.into();
        let timestamp = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .map(|duration| duration.as_secs())
            .unwrap_or(0);
        let message = Self::message(&address, &method, &path, &body_hash, timestamp, &nonce);
        let signature = signer(&message);
        Self {
            version: ENVELOPE_VERSION.to_string(),
            address,
            method,
            path,
            body_hash,
            timestamp,
            nonce,
            signature,
        }
    }

    pub fn to_json(&self) -> String {
        format!(
            "{{\"version\":\"{}\",\"address\":\"{}\",\"method\":\"{}\",\"path\":\"{}\",\"body_hash\":\"{}\",\"timestamp\":{},\"nonce\":\"{}\",\"signature\":\"{}\"}}",
            escape_json(&self.version),
            escape_json(&self.address),
            escape_json(&self.method),
            escape_json(&self.path),
            escape_json(&self.body_hash),
            self.timestamp,
            escape_json(&self.nonce),
            escape_json(&self.signature)
        )
    }
}

#[derive(Clone, Debug)]
pub struct NetcoinClient {
    base_url: String,
}

impl NetcoinClient {
    pub fn new(base_url: impl Into<String>) -> Self {
        Self {
            base_url: base_url.into().trim_end_matches('/').to_string(),
        }
    }

    pub fn get(&self, path: &str) -> Result<String, NetcoinError> {
        request("GET", &self.base_url, path, None)
    }

    pub fn post_json(&self, path: &str, body: &str) -> Result<String, NetcoinError> {
        request("POST", &self.base_url, path, Some(body))
    }

    pub fn node_info(&self) -> Result<String, NetcoinError> {
        self.get("/v1/info")
    }

    pub fn node_health(&self) -> Result<String, NetcoinError> {
        self.get("/v1/health")
    }

    pub fn block_template(&self, address: Option<&str>) -> Result<String, NetcoinError> {
        match address {
            Some(address) if !address.is_empty() => self.get(&format!(
                "/v1/blocktemplate?address={}",
                percent_encode(address)
            )),
            _ => self.get("/v1/blocktemplate"),
        }
    }

    pub fn broadcast_transaction(
        &self,
        transaction_json: &str,
        private_relay: bool,
    ) -> Result<String, NetcoinError> {
        self.post_json(
            if private_relay {
                "/v1/tx?private=1"
            } else {
                "/v1/tx"
            },
            transaction_json,
        )
    }
}

fn request(
    method: &str,
    base_url: &str,
    path: &str,
    body: Option<&str>,
) -> Result<String, NetcoinError> {
    let (host, port) = parse_http_base_url(base_url)?;
    let target = if path.starts_with('/') {
        path.to_string()
    } else {
        format!("/{path}")
    };
    let mut stream = TcpStream::connect((host.as_str(), port))?;
    let body = body.unwrap_or("");
    let request = if method == "POST" {
        format!(
            "POST {target} HTTP/1.1\r\nHost: {host}:{port}\r\nContent-Type: application/json\r\nContent-Length: {}\r\nConnection: close\r\n\r\n{body}",
            body.as_bytes().len()
        )
    } else {
        format!("GET {target} HTTP/1.1\r\nHost: {host}:{port}\r\nConnection: close\r\n\r\n")
    };
    stream.write_all(request.as_bytes())?;
    let mut response = String::new();
    stream.read_to_string(&mut response)?;
    let (head, body) = response
        .split_once("\r\n\r\n")
        .ok_or_else(|| NetcoinError::InvalidResponse(response.clone()))?;
    let status = head
        .lines()
        .next()
        .and_then(|line| line.split_whitespace().nth(1))
        .and_then(|value| value.parse::<u16>().ok())
        .ok_or_else(|| NetcoinError::InvalidResponse(head.to_string()))?;
    if !(200..300).contains(&status) {
        return Err(NetcoinError::HttpStatus(status, body.to_string()));
    }
    Ok(body.to_string())
}

fn parse_http_base_url(base_url: &str) -> Result<(String, u16), NetcoinError> {
    let rest = base_url
        .strip_prefix("http://")
        .ok_or_else(|| NetcoinError::InvalidUrl(base_url.to_string()))?;
    if rest.is_empty() || rest.contains('/') {
        return Err(NetcoinError::InvalidUrl(base_url.to_string()));
    }
    let (host, port) = match rest.rsplit_once(':') {
        Some((host, port)) => {
            let port = port
                .parse::<u16>()
                .map_err(|_| NetcoinError::InvalidUrl(base_url.to_string()))?;
            (host.to_string(), port)
        }
        None => (rest.to_string(), 80),
    };
    if host.is_empty() {
        return Err(NetcoinError::InvalidUrl(base_url.to_string()));
    }
    Ok((host, port))
}

fn escape_json(value: &str) -> String {
    value
        .replace('\\', "\\\\")
        .replace('"', "\\\"")
        .replace('\n', "\\n")
        .replace('\r', "\\r")
}

fn percent_encode(value: &str) -> String {
    let mut out = String::new();
    for byte in value.bytes() {
        if byte.is_ascii_alphanumeric() || matches!(byte, b'-' | b'_' | b'.' | b'~') {
            out.push(byte as char);
        } else {
            out.push_str(&format!("%{byte:02X}"));
        }
    }
    out
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn envelope_message_matches_sdk_contract() {
        let message = SignedEnvelope::message("net1qdemo", "post", "/v1/tx", "abc123", 42, "nonce");
        assert_eq!(
            message,
            "NetCoin signed request\nnetcoin-signed-envelope-v1\nnet1qdemo\nPOST\n/v1/tx\nabc123\n42\nnonce"
        );
    }

    #[test]
    fn envelope_json_escapes_strings() {
        let envelope = SignedEnvelope {
            version: ENVELOPE_VERSION.to_string(),
            address: "net1qdemo".to_string(),
            method: "POST".to_string(),
            path: "/v1/tx".to_string(),
            body_hash: "abc".to_string(),
            timestamp: 1,
            nonce: "n".to_string(),
            signature: "sig\"quoted".to_string(),
        };
        assert!(envelope.to_json().contains("sig\\\"quoted"));
    }
}
