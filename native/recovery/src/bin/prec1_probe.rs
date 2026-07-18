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

fn encode_hex(bytes: &[u8]) -> String {
    let mut output = String::with_capacity(bytes.len() * 2);
    for byte in bytes {
        write!(output, "{byte:02X}").expect("writing to a String cannot fail");
    }
    output
}

fn parse_bool(value: &str) -> Result<bool, &'static str> {
    match value {
        "0" => Ok(false),
        "1" => Ok(true),
        _ => Err("transport"),
    }
}

fn policy_summary(bytes: &[u8]) -> Result<String, &'static str> {
    let bundle = poole_recovery::parse(bytes).map_err(|error| error.code())?;
    Ok(format!(
        "OK;version={};minimum_secure_version={};slots=2;failures=10;authorities=7;max_attempts={};state_floor={};body_sha256={}",
        bundle.bundle_version,
        bundle.minimum_secure_version,
        bundle.max_attempts,
        bundle.state_generation_floor,
        encode_hex(&bundle.body_sha256),
    ))
}

fn state_summary(state: &poole_recovery::State) -> String {
    format!(
        "OK;generation={};active={};pending={};known_good={};unbootable={};attempts={},{};mode={};failure={};inflight={}",
        state.generation,
        state.active_slot,
        state.pending_slot,
        state.known_good_mask,
        state.unbootable_mask,
        state.attempts_a,
        state.attempts_b,
        state.current_mode,
        state.last_failure,
        u8::from(state.flags & poole_recovery::STATE_INFLIGHT != 0),
    )
}

fn decision_summary(decision: &poole_recovery::Decision) -> String {
    let state = poole_recovery::encode_state(&decision.state);
    format!(
        "OK;mode={};slot={};trial={};persist={};reason={};generation={};attempts={},{};known_good={};unbootable={};state={}",
        decision.mode,
        decision.slot,
        u8::from(decision.trial),
        u8::from(decision.persistence_required),
        decision.reason,
        decision.state.generation,
        decision.state.attempts_a,
        decision.state.attempts_b,
        decision.state.known_good_mask,
        decision.state.unbootable_mask,
        encode_hex(&state),
    )
}

fn evaluate_transition(value: &str) -> Result<String, &'static str> {
    let fields: Vec<&str> = value.split(':').collect();
    if fields.len() != 7 {
        return Err("transport");
    }
    let requested = fields[0].parse::<u8>().map_err(|_| "transport")?;
    let presence = parse_bool(fields[1])?;
    let nonce = fields[2].parse::<u64>().map_err(|_| "transport")?;
    let authenticated = parse_bool(fields[3])?;
    let writable = parse_bool(fields[4])?;
    let policy_bytes = decode_hex(fields[5]).map_err(|()| "transport")?;
    let state_bytes = decode_hex(fields[6]).map_err(|()| "transport")?;
    let policy = poole_recovery::parse(&policy_bytes).map_err(|error| error.code())?;
    let state = poole_recovery::parse_state(&state_bytes).map_err(|error| error.code())?;
    let decision = poole_recovery::select_boot(
        &policy,
        &state,
        requested,
        presence,
        nonce,
        authenticated,
        writable,
    )
    .map_err(|error| error.code())?;
    Ok(decision_summary(&decision))
}

fn evaluate_success(value: &str) -> Result<String, &'static str> {
    let fields: Vec<&str> = value.split(':').collect();
    if fields.len() != 3 {
        return Err("transport");
    }
    let mode = fields[0];
    let policy_bytes = decode_hex(fields[1]).map_err(|()| "transport")?;
    let state_bytes = decode_hex(fields[2]).map_err(|()| "transport")?;
    let policy = poole_recovery::parse(&policy_bytes).map_err(|error| error.code())?;
    let state = poole_recovery::parse_state(&state_bytes).map_err(|error| error.code())?;
    let mut receipt = poole_recovery::SuccessReceipt {
        authenticated: true,
        generation: state.inflight_generation,
        slot: state.inflight_slot,
        mode: state.inflight_mode,
        boot_nonce: state.boot_nonce,
    };
    match mode {
        "qualified" => {}
        "auth" => receipt.authenticated = false,
        "generation" => receipt.generation = receipt.generation.wrapping_add(1),
        "slot" => receipt.slot = 3 - receipt.slot,
        "mode" => receipt.mode = if receipt.mode == 1 { 2 } else { 1 },
        "nonce" => receipt.boot_nonce = receipt.boot_nonce.wrapping_add(1),
        _ => return Err("transport"),
    }
    let next = poole_recovery::report_boot_success(&policy, &state, &receipt)
        .map_err(|error| error.code())?;
    let bytes = poole_recovery::encode_state(&next);
    Ok(format!("{};state={}", state_summary(&next), encode_hex(&bytes)))
}

fn evaluate_failure(value: &str) -> Result<String, &'static str> {
    let fields: Vec<&str> = value.split(':').collect();
    if fields.len() != 4 {
        return Err("transport");
    }
    let failure_id = fields[0].parse::<u16>().map_err(|_| "transport")?;
    let authenticated = parse_bool(fields[1])?;
    let policy_bytes = decode_hex(fields[2]).map_err(|()| "transport")?;
    let state_bytes = decode_hex(fields[3]).map_err(|()| "transport")?;
    let policy = poole_recovery::parse(&policy_bytes).map_err(|error| error.code())?;
    let state = poole_recovery::parse_state(&state_bytes).map_err(|error| error.code())?;
    let decision = poole_recovery::report_boot_failure(&policy, &state, failure_id, authenticated)
        .map_err(|error| error.code())?;
    let bytes = poole_recovery::encode_state(&decision.state);
    Ok(format!(
        "OK;action={};{};state={}",
        decision.action,
        state_summary(&decision.state).trim_start_matches("OK;"),
        encode_hex(&bytes),
    ))
}

fn activation_result(mode: &str, bytes: &[u8]) -> Result<String, &'static str> {
    let bundle = poole_recovery::parse(bytes).map_err(|error| error.code())?;
    let mut context = poole_recovery::ActivationContext::synthetic_qualified(&bundle);
    match mode {
        "qualified" => {}
        "development" => context = poole_recovery::ActivationContext::development(),
        "role" => context.outer_role = 2,
        "version" => context.outer_artifact_version = context.outer_artifact_version.wrapping_add(1),
        "payload-digest" => context.outer_payload_digest_verified = false,
        "file-digest" => context.outer_file_digest_verified = false,
        "outer-signature" => context.outer_signature_verified = false,
        "inner-signature" => context.inner_signature_verified = false,
        "manifest-signature" => context.manifest_signature_verified = false,
        "state-auth" => context.state_authenticated = false,
        "state-generation" => context.state_generation_monotonic = false,
        "version-floor" => context.version_floor_persisted = false,
        "components" => context.manifest_and_components_verified = false,
        "pbp" => context.pbp_major = context.pbp_major.wrapping_add(1),
        "kernel-abi" => context.kernel_abi_major = context.kernel_abi_major.wrapping_add(1),
        "offline" => context.offline_path = false,
        "pdc-disabled" => context.pdc_disabled = false,
        "pooleglyph-independent" => context.pooleglyph_independent = false,
        "display-path" => context.serial_or_gop_software_path = false,
        "transaction-capacity" => context.transaction_capacity_verified = false,
        "evidence" => context.evidence_preservation_ready = false,
        "rollback" => context.rollback_available = false,
        "state-writable" => context.state_writable = false,
        _ => return Err("transport"),
    }
    poole_recovery::authorize_activation(&bundle, &context).map_err(|error| error.code())?;
    Ok("OK:activation".to_owned())
}

fn evaluate(line: &str) -> Result<String, &'static str> {
    if let Some(value) = line.strip_prefix("P:") {
        return policy_summary(&decode_hex(value).map_err(|()| "transport")?);
    }
    if let Some(value) = line.strip_prefix("S:") {
        let bytes = decode_hex(value).map_err(|()| "transport")?;
        let state = poole_recovery::parse_state(&bytes).map_err(|error| error.code())?;
        return Ok(state_summary(&state));
    }
    if let Some(value) = line.strip_prefix("T:") {
        return evaluate_transition(value);
    }
    if let Some(value) = line.strip_prefix("U:") {
        return evaluate_success(value);
    }
    if let Some(value) = line.strip_prefix("F:") {
        return evaluate_failure(value);
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
