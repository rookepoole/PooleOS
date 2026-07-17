use std::fmt::Write as _;
use std::io::{self, BufRead};

fn decode_hex(value: &str) -> Result<Vec<u8>, ()> {
    if !value.len().is_multiple_of(2) {
        return Err(());
    }
    value
        .as_bytes()
        .chunks_exact(2)
        .map(|pair| {
            let text = std::str::from_utf8(pair).map_err(|_| ())?;
            u8::from_str_radix(text, 16).map_err(|_| ())
        })
        .collect()
}

fn encode_digest(digest: &[u8; 32]) -> String {
    let mut output = String::with_capacity(64);
    for byte in digest {
        write!(output, "{byte:02X}").expect("writing to a String cannot fail");
    }
    output
}

fn parse_request(value: &str) -> Result<String, &'static str> {
    let (capacity_text, encoded) = value
        .strip_prefix("P:")
        .and_then(|rest| rest.split_once(':'))
        .ok_or("transport")?;
    let capacity = capacity_text.parse::<usize>().map_err(|_| "transport")?;
    if capacity > poole_manifest::MAX_ARTIFACTS {
        return Err("transport");
    }
    let bytes = decode_hex(encoded).map_err(|_| "transport")?;
    let mut storage = [poole_manifest::Artifact::EMPTY; poole_manifest::MAX_ARTIFACTS];
    let manifest = poole_manifest::parse(&bytes, &mut storage[..capacity])
        .map_err(|error| error.code())?;
    let mut summary = format!(
        "OK;manifest_id={};slot={};manifest_version={};minimum_secure_version={};artifact_count={}",
        manifest.manifest_id,
        manifest.slot,
        manifest.manifest_version,
        manifest.minimum_secure_version,
        manifest.artifacts.len()
    );
    for artifact in manifest.artifacts {
        write!(
            summary,
            ";artifact={},{},{},{},{},{},{},{},{}",
            artifact.id,
            artifact.kind.as_str(),
            artifact.format,
            artifact.version,
            artifact.path,
            artifact.file_bytes,
            artifact.image_bytes,
            encode_digest(&artifact.sha256),
            artifact.entry_contract
        )
        .map_err(|_| "transport")?;
    }
    Ok(summary)
}

fn digest_request(value: &str) -> Result<String, &'static str> {
    let bytes = decode_hex(value.strip_prefix("D:").ok_or("transport")?)
        .map_err(|_| "transport")?;
    Ok(format!("OK;sha256={}", encode_digest(&poole_manifest::sha256(&bytes))))
}

fn main() {
    for line in io::stdin().lock().lines() {
        let result = line.map_err(|_| "transport").and_then(|value| {
            if value.starts_with("P:") {
                parse_request(&value)
            } else if value.starts_with("D:") {
                digest_request(&value)
            } else {
                Err("transport")
            }
        });
        match result {
            Ok(summary) => println!("{summary}"),
            Err(code) => println!("ERR:{code}"),
        }
    }
}
