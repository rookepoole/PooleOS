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

fn parse_hex_u64(value: &str) -> Result<u64, &'static str> {
    u64::from_str_radix(value, 16).map_err(|_| "transport")
}

fn parse_summary(encoded: &str) -> Result<String, &'static str> {
    let bytes = decode_hex(encoded)?;
    let bundle = poole_symbols::parse(&bytes).map_err(|error| error.code())?;
    Ok(format!(
        "OK;version={}.{};bytes={};segments={};symbols={};strings={};image={};entry={:X};body={}",
        poole_symbols::MAJOR_VERSION,
        poole_symbols::MINOR_VERSION,
        bundle.raw.len(),
        bundle.segment_count,
        bundle.symbol_count,
        bundle.string_bytes,
        bundle.image_bytes,
        bundle.entry_offset,
        encode_hex(&bundle.body_sha256),
    ))
}

fn lookup_summary(value: &str) -> Result<String, &'static str> {
    let mut fields = value.split(':');
    let bytes = decode_hex(fields.next().ok_or("transport")?)?;
    let base = parse_hex_u64(fields.next().ok_or("transport")?)?;
    let address = parse_hex_u64(fields.next().ok_or("transport")?)?;
    if fields.next().is_some() {
        return Err("transport");
    }
    let bundle = poole_symbols::parse(&bytes).map_err(|error| error.code())?;
    match poole_symbols::lookup(&bundle, base, address).map_err(|error| error.code())? {
        Some(result) => Ok(format!(
            "OK;id={};name={};offset={:X};steps={}",
            result.symbol.symbol_id,
            std::str::from_utf8(result.symbol.name).map_err(|_| "transport")?,
            result.symbol_offset,
            result.steps,
        )),
        None => Ok("MISS".to_owned()),
    }
}

fn activation_summary(value: &str) -> Result<String, &'static str> {
    let (mode, encoded) = value.split_once(':').ok_or("transport")?;
    let bytes = decode_hex(encoded)?;
    let bundle = poole_symbols::parse(&bytes).map_err(|error| error.code())?;
    let mut context = poole_symbols::ConsumptionContext::synthetic_qualified(&bundle);
    match mode {
        "qualified" => {}
        "development" => context = poole_symbols::ConsumptionContext::development(&bundle),
        "outer-signature" => context.outer_signature_verified = false,
        "inner-signature" => context.inner_signature_verified = false,
        "manifest-signature" => context.manifest_signature_verified = false,
        "kernel-signature" => context.kernel_signature_verified = false,
        "role" => context.outer_role = 3,
        "version" => context.outer_version = context.outer_version.wrapping_add(1),
        "payload-digest" => context.outer_payload_sha256[0] ^= 1,
        "file-digest" => context.expected_outer_file_sha256[0] ^= 1,
        "canonical-identity" => context.canonical_file_sha256[0] ^= 1,
        "loaded-identity" => context.preferred_loaded_sha256[0] ^= 1,
        "build-id" => context.build_id_sha256[0] ^= 1,
        "debug-identity" => context.debug_file_sha256[0] ^= 1,
        "source-identity" => context.source_manifest_sha256[0] ^= 1,
        "identity-evidence" => context.identity_evidence_verified = false,
        "stripped-correspondence" => context.stripped_correspondence_verified = false,
        "dwarf5" => context.dwarf5_verified = false,
        "public-policy" => context.public_policy_verified = false,
        "source-paths" => context.source_paths_absent = false,
        "pointer-redaction" => context.pointer_redaction_enabled = false,
        "diagnostics-authority" => context.diagnostics_authorized = false,
        "runtime-base" => context.runtime_base = context.runtime_base.wrapping_add(1),
        "symbol-capacity" => context.symbol_capacity = 0,
        "string-capacity" => context.string_capacity = 0,
        "lookup-capacity" => context.lookup_step_capacity = 0,
        "authority-effect" => context.authority_effect_requested = true,
        _ => return Err("transport"),
    }
    poole_symbols::authorize_consumption(&bundle, &context).map_err(|error| error.code())?;
    Ok("OK:activation".to_owned())
}

fn evaluate(line: &str) -> Result<String, &'static str> {
    if let Some(value) = line.strip_prefix("P:") {
        return parse_summary(value);
    }
    if let Some(value) = line.strip_prefix("L:") {
        return lookup_summary(value);
    }
    if let Some(value) = line.strip_prefix("A:") {
        return activation_summary(value);
    }
    Err("transport")
}

fn main() {
    for line in io::stdin().lock().lines() {
        let result = line
            .map_err(|_| "transport")
            .and_then(|value| evaluate(&value));
        match result {
            Ok(summary) => println!("{summary}"),
            Err(code) => println!("ERR:{code}"),
        }
    }
}
