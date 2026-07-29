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

fn main() {
    for line in io::stdin().lock().lines() {
        let result = line.map_err(|_| "transport").and_then(|value| {
            let bytes = decode_hex(value.strip_prefix("P:").ok_or("transport")?)
                .map_err(|_| "transport")?;
            let artifact = poole_boot_artifact::parse(&bytes).map_err(|error| error.code())?;
            Ok(format!(
                "OK;role={};version={};payload_bytes={};payload_sha256={};file_sha256={}",
                artifact.role.code(),
                artifact.version,
                artifact.payload.len(),
                encode_digest(&artifact.payload_sha256),
                encode_digest(&poole_boot_artifact::sha256(&bytes)),
            ))
        });
        match result {
            Ok(summary) => println!("{summary}"),
            Err(code) => println!("ERR:{code}"),
        }
    }
}
