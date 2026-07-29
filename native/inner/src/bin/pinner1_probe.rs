use std::fmt::Write as _;
use std::io::{self, BufRead};

fn decode_hex(value: &str) -> Result<Vec<u8>, &'static str> {
    if !value.len().is_multiple_of(2) {
        return Err("transport");
    }
    value
        .as_bytes()
        .chunks_exact(2)
        .map(|pair| {
            let text = std::str::from_utf8(pair).map_err(|_| "transport")?;
            u8::from_str_radix(text, 16).map_err(|_| "transport")
        })
        .collect()
}

fn encode_hex(bytes: &[u8]) -> String {
    let mut output = String::with_capacity(bytes.len() * 2);
    for byte in bytes {
        write!(output, "{byte:02X}").expect("writing to a String cannot fail");
    }
    output
}

fn evaluate(line: &str) -> Result<String, String> {
    let encoded = line
        .strip_prefix("V:")
        .ok_or_else(|| "transport".to_owned())?;
    let fields: Vec<&str> = encoded.split(':').collect();
    if fields.len() != poole_inner_live::ARTIFACT_COUNT {
        return Err("transport".to_owned());
    }
    let files: Vec<Vec<u8>> = fields
        .iter()
        .map(|field| decode_hex(field).map_err(str::to_owned))
        .collect::<Result<_, _>>()?;
    let summary = poole_inner_live::validate_development_set([
        &files[0], &files[1], &files[2], &files[3], &files[4], &files[5],
    ])
    .map_err(|failure| format!("{}:{}", failure.stage.code(), failure.code))?;
    Ok(format!(
        "OK;artifacts={};parsers={};bindings={};denials={};file_bytes={};payload_bytes={};set={};grants={};actions={};state_writes={};hardware_observations={}",
        summary.artifact_count,
        summary.parser_count,
        summary.cross_binding_count,
        summary.development_denial_count,
        summary.file_bytes,
        summary.payload_bytes,
        encode_hex(&summary.retained_set_sha256),
        summary.authority_grants,
        summary.actions_authorized,
        summary.state_writes,
        summary.hardware_observations,
    ))
}

fn main() {
    for line in io::stdin().lock().lines() {
        let result = line
            .map_err(|_| "transport".to_owned())
            .and_then(|value| evaluate(&value));
        match result {
            Ok(summary) => println!("{summary}"),
            Err(code) => println!("ERR:{code}"),
        }
    }
}
