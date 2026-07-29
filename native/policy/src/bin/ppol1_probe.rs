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

fn mode_number(name: &str) -> Result<u16, &'static str> {
    match name {
        "normal" => Ok(poole_policy::MODE_NORMAL),
        "safe" => Ok(poole_policy::MODE_SAFE),
        "previous" => Ok(poole_policy::MODE_PREVIOUS),
        "recovery" => Ok(poole_policy::MODE_RECOVERY),
        "diagnostic" => Ok(poole_policy::MODE_DIAGNOSTIC),
        "firmware" => Ok(poole_policy::MODE_FIRMWARE),
        _ => Err("transport"),
    }
}

fn parse_summary(encoded: &str) -> Result<String, &'static str> {
    let bytes = decode_hex(encoded)?;
    let bundle = poole_policy::parse(&bytes).map_err(|error| error.code())?;
    Ok(format!(
        "OK;version={}.{};bytes={};modes={};capabilities={};body={}",
        poole_policy::MAJOR_VERSION,
        poole_policy::MINOR_VERSION,
        bundle.raw.len(),
        poole_policy::MODE_COUNT,
        bundle.capability_count,
        encode_hex(&bundle.body_sha256),
    ))
}

fn cross_bind_summary(value: &str) -> Result<String, &'static str> {
    let (policy_hex, pinit_hex) = value.split_once(':').ok_or("transport")?;
    let policy = decode_hex(policy_hex)?;
    let pinit = decode_hex(pinit_hex)?;
    let bundle = poole_policy::parse(&policy).map_err(|error| error.code())?;
    poole_policy::validate_initial_system(&bundle, &pinit).map_err(|error| error.code())?;
    Ok(format!(
        "OK;capabilities={};pinit={}",
        bundle.capability_count,
        encode_hex(&poole_policy::sha256(&pinit)),
    ))
}

fn activation_summary(value: &str) -> Result<String, &'static str> {
    let (case, encoded) = value.split_once(':').ok_or("transport")?;
    let bytes = decode_hex(encoded)?;
    let bundle = poole_policy::parse(&bytes).map_err(|error| error.code())?;
    let selected_mode = case
        .strip_prefix("qualified-")
        .map(mode_number)
        .transpose()?
        .unwrap_or(poole_policy::MODE_NORMAL);
    let mut context = poole_policy::ActivationContext::synthetic_qualified(&bundle, selected_mode)
        .map_err(|error| error.code())?;
    match case {
        "qualified-normal"
        | "qualified-safe"
        | "qualified-previous"
        | "qualified-recovery"
        | "qualified-diagnostic"
        | "qualified-firmware" => {}
        "development" => {
            context = poole_policy::ActivationContext::development(&bundle)
                .map_err(|error| error.code())?;
        }
        "outer-signature" => context.outer_signature_verified = false,
        "outer-role" => context.outer_role = 6,
        "outer-version" => context.outer_version += 1,
        "outer-payload" => context.outer_payload_sha256[0] ^= 1,
        "outer-file" => context.expected_outer_file_sha256[0] ^= 1,
        "policy-signature" => context.policy_signature_verified = false,
        "manifest-signature" => context.manifest_signature_verified = false,
        "artifact-signatures" => context.artifact_signatures_verified = false,
        "target-profile" => context.target_profile_verified = false,
        "initial-digest" => context.initial_system_digest_verified = false,
        "recovery-digest" => context.recovery_digest_verified = false,
        "symbols-digest" => context.symbols_digest_verified = false,
        "microcode-digest" => context.microcode_digest_verified = false,
        "firmware-digest" => context.firmware_digest_verified = false,
        "trust-policy" => context.trust_policy_authenticated = false,
        "revocation-state" => context.revocation_state_authenticated = false,
        "rollback-state" => context.rollback_state_authenticated = false,
        "audit-schema" => context.audit_schema_verified = false,
        "inner-contracts" => context.inner_contracts_verified = false,
        "pinit-cross-binding" => context.initial_system_cross_bound = false,
        "kernel-abi" => context.kernel_abi_verified = false,
        "pbp" => context.pbp_verified = false,
        "mode" => context.selected_mode = 99,
        "mode-authority" => context.mode_authorized = false,
        "transition-authority" => context.transition_authorized = false,
        "capability-allocator" => context.capability_allocator_ready = false,
        "resource-broker" => context.resource_broker_ready = false,
        "audit-sink" => context.audit_sink_ready = false,
        "receipt-store" => context.receipt_store_ready = false,
        "physical-presence" => {
            context = poole_policy::ActivationContext::synthetic_qualified(
                &bundle,
                poole_policy::MODE_FIRMWARE,
            )
            .map_err(|error| error.code())?;
            context.physical_presence_verified = false;
        }
        "separate-authority" => {
            context = poole_policy::ActivationContext::synthetic_qualified(
                &bundle,
                poole_policy::MODE_FIRMWARE,
            )
            .map_err(|error| error.code())?;
            context.separate_authority_verified = false;
        }
        "capability" => context.capability_id = 0,
        "capability-mode" => context.selected_mode = poole_policy::MODE_RECOVERY,
        "capability-revoked" => context.capability_revoked = true,
        "generation" => context.current_generation += 1,
        "issued-rights" => context.issued_rights |= 1 << 4,
        "requested-rights" => context.requested_rights |= 1 << 4,
        "requested-effects" => context.requested_effects |= poole_policy::EFFECT_FIRMWARE,
        "not-qualification" => context.qualification_only = false,
        "live-execution" => context.live_execution_requested = true,
        "persistent-write" => context.persistent_write_requested = true,
        "firmware-call" => context.firmware_call_requested = true,
        "driver-load" => context.driver_load_requested = true,
        "media-write" => context.physical_media_write_requested = true,
        "state-mutation" => context.state_mutation_requested = true,
        _ => return Err("transport"),
    }
    let decision = poole_policy::authorize_dry_run_decision(&bundle, &context)
        .map_err(|error| error.code())?;
    Ok(format!(
        "OK;mode={};capability={};rights={};effects={};mode_generation={};capability_generation={};allowed={};qualification={}",
        decision.mode,
        decision.capability_id,
        decision.effective_rights,
        decision.effective_effects,
        decision.mode_generation,
        decision.capability_generation,
        decision.allowed_capability_count,
        u8::from(decision.qualification_only),
    ))
}

fn receipt_summary(value: &str) -> Result<String, &'static str> {
    let (case, encoded) = value.split_once(':').ok_or("transport")?;
    let bytes = decode_hex(encoded)?;
    let bundle = poole_policy::parse(&bytes).map_err(|error| error.code())?;
    let context =
        poole_policy::ActivationContext::synthetic_qualified(&bundle, poole_policy::MODE_NORMAL)
            .map_err(|error| error.code())?;
    let decision = poole_policy::authorize_dry_run_decision(&bundle, &context)
        .map_err(|error| error.code())?;
    let mut receipt = poole_policy::DecisionReceipt::synthetic(&decision);
    match case {
        "qualified" => {}
        "not-qualification" => receipt.qualification_only = false,
        "policy-digest" => receipt.policy_sha256[0] ^= 1,
        "mode" => receipt.mode += 1,
        "capability" => receipt.capability_id += 1,
        "rights" => receipt.effective_rights ^= 1,
        "effects" => receipt.effective_effects ^= 1,
        "generation" => receipt.mode_generation += 1,
        "revocation-epoch" => receipt.revocation_epoch = 0,
        "audit-sequence" => receipt.audit_sequence = 0,
        "not-durable" => receipt.durable = false,
        "decision-id" => receipt.decision_id[0] ^= 1,
        _ => return Err("transport"),
    }
    poole_policy::verify_receipt(&decision, &receipt).map_err(|error| error.code())?;
    Ok("OK:verified".to_owned())
}

fn evaluate(line: &str) -> Result<String, &'static str> {
    if let Some(value) = line.strip_prefix("P:") {
        return parse_summary(value);
    }
    if let Some(value) = line.strip_prefix("X:") {
        return cross_bind_summary(value);
    }
    if let Some(value) = line.strip_prefix("A:") {
        return activation_summary(value);
    }
    if let Some(value) = line.strip_prefix("R:") {
        return receipt_summary(value);
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
