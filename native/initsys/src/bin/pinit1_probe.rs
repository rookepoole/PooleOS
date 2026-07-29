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

fn parse_summary(bytes: &[u8]) -> Result<String, &'static str> {
    let bundle = poole_initial_system::parse(bytes).map_err(|error| error.code())?;
    let mut order = String::new();
    for (index, service_id) in bundle.start_order[..usize::from(bundle.service_count)]
        .iter()
        .enumerate()
    {
        if index != 0 {
            order.push(',');
        }
        write!(order, "{service_id}").expect("writing to a String cannot fail");
    }
    Ok(format!(
        "OK;version={};minimum_secure_version={};components={};services={};dependencies={};resources={};capabilities={};root={};start_order={};body_sha256={}",
        bundle.bundle_version,
        bundle.minimum_secure_version,
        bundle.component_count,
        bundle.service_count,
        bundle.dependency_count,
        bundle.resource_count,
        bundle.capability_count,
        bundle.root_service_id,
        order,
        encode_digest(&bundle.body_sha256),
    ))
}

fn activation_result(mode: &str, bytes: &[u8]) -> Result<String, &'static str> {
    let bundle = poole_initial_system::parse(bytes).map_err(|error| error.code())?;
    let mut context = poole_initial_system::ActivationContext::synthetic_qualified();
    match mode {
        "qualified" => {}
        "development" => context = poole_initial_system::ActivationContext::development(),
        "role" => context.outer_role = 7,
        "version" => context.outer_artifact_version = 2,
        "payload-digest" => context.outer_payload_digest_verified = false,
        "file-digest" => context.outer_file_digest_verified = false,
        "outer-signature" => context.outer_signature_verified = false,
        "manifest-signature" => context.manifest_signature_verified = false,
        "rollback-state" => context.rollback_state_authenticated = false,
        "rollback-floor" => context.trusted_minimum_secure_version = 2,
        "kernel-abi" => context.kernel_abi_major = 2,
        "pbp" => context.pbp_major = 2,
        "boot-mode" => context.boot_mode = 1 << 3,
        "capability-allocator" => context.capability_allocator_ready = false,
        "resource-broker" => context.resource_broker_ready = false,
        "component-contracts" => context.component_contracts_verified = false,
        "transaction-capacity" => context.transaction_capacity_verified = false,
        _ => return Err("transport"),
    }
    poole_initial_system::authorize_activation(&bundle, &context).map_err(|error| error.code())?;
    Ok("OK:activation".to_owned())
}

fn evaluate(line: &str) -> Result<String, &'static str> {
    if let Some(value) = line.strip_prefix("P:") {
        let bytes = decode_hex(value).map_err(|()| "transport")?;
        return parse_summary(&bytes);
    }
    if let Some(value) = line.strip_prefix("A:") {
        let (mode, encoded) = value.split_once(':').ok_or("transport")?;
        let bytes = decode_hex(encoded).map_err(|()| "transport")?;
        return activation_result(mode, &bytes);
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
