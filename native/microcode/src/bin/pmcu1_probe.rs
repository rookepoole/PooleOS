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

fn parse_hex_u32(value: &str) -> Result<u32, &'static str> {
    u32::from_str_radix(value, 16).map_err(|_| "transport")
}

fn parse_bool(value: &str) -> Result<bool, &'static str> {
    match value {
        "0" => Ok(false),
        "1" => Ok(true),
        _ => Err("transport"),
    }
}

fn parse_revisions(value: &str) -> Result<Vec<u32>, &'static str> {
    if value == "-" {
        return Ok(Vec::new());
    }
    value.split(',').map(parse_hex_u32).collect()
}

fn parse_summary(encoded: &str) -> Result<String, &'static str> {
    let bytes = decode_hex(encoded)?;
    let bundle = poole_microcode::parse(&bytes).map_err(|error| error.code())?;
    Ok(format!(
        "OK;version={}.{};bytes={};patches={};floor={:X};known={:X};preferred={:X};body={}",
        poole_microcode::MAJOR_VERSION,
        poole_microcode::MINOR_VERSION,
        bundle.raw.len(),
        bundle.patch_count,
        bundle.security_revision_floor,
        bundle.known_good_revision,
        bundle.preferred_revision,
        encode_hex(&bundle.body_sha256),
    ))
}

fn selection_text(selection: poole_microcode::Selection<'_>) -> String {
    let decision = match selection.decision {
        poole_microcode::DECISION_APPLY => "apply",
        poole_microcode::DECISION_SKIP_CURRENT => "skip_current",
        poole_microcode::DECISION_RESET_FOR_KNOWN_GOOD => "reset_for_known_good",
        _ => "invalid",
    };
    let (patch_id, revision) = selection
        .patch
        .map_or(("-".to_owned(), "-".to_owned()), |patch| {
            (patch.patch_id.to_string(), format!("{:X}", patch.revision))
        });
    format!(
        "OK;decision={decision};id={patch_id};revision={revision};current={:X};floor={:X}",
        selection.current_revision, selection.required_floor
    )
}

fn select_summary(value: &str) -> Result<String, &'static str> {
    let fields: Vec<_> = value.split(':').collect();
    if fields.len() != 7 {
        return Err("transport");
    }
    let bytes = decode_hex(fields[0])?;
    let bundle = poole_microcode::parse(&bytes).map_err(|error| error.code())?;
    let revoked = parse_revisions(fields[6])?;
    let selection = poole_microcode::select_patch(
        &bundle,
        parse_hex_u32(fields[1])?,
        parse_hex_u32(fields[2])?,
        parse_hex_u32(fields[3])?,
        parse_hex_u32(fields[4])?,
        u16::try_from(parse_hex_u32(fields[5])?).map_err(|_| "transport")?,
        &revoked,
    )
    .map_err(|error| error.code())?;
    Ok(selection_text(selection))
}

fn activation_summary(value: &str) -> Result<String, &'static str> {
    let (mode, encoded) = value.split_once(':').ok_or("transport")?;
    let bytes = decode_hex(encoded)?;
    let bundle = poole_microcode::parse(&bytes).map_err(|error| error.code())?;
    let revisions = [poole_microcode::SYNTHETIC_REVISION_BASE + 0x10];
    let mut context = poole_microcode::ApplyContext::synthetic_qualified(&bundle, &revisions);
    match mode {
        "qualified" => {}
        "development" => context = poole_microcode::ApplyContext::development(&bundle, &revisions),
        "outer-signature" => context.outer_signature_verified = false,
        "inner-signature" => context.inner_signature_verified = false,
        "manifest-signature" => context.manifest_signature_verified = false,
        "vendor-signature" => context.vendor_signature_verified = false,
        "vendor-container" => context.vendor_container_validated = false,
        "vendor-source" => context.vendor_source_trusted = false,
        "redistribution" => context.redistribution_authorized = false,
        "revocation-state" => context.revocation_state_authenticated = false,
        "hardware-evidence" => context.target_hardware_evidence_verified = false,
        "cpuid-observation" => context.cpuid_observation_trusted = false,
        "revision-observation" => context.revision_observation_trusted = false,
        "role" => context.outer_role = 4,
        "version" => context.outer_version = 2,
        "payload-digest" => context.outer_payload_sha256[0] ^= 1,
        "file-digest" => context.expected_outer_file_sha256[0] ^= 1,
        "vendor-id" => context.vendor_id[0] ^= 1,
        "cpuid" => context.cpuid_signature ^= 1,
        "platform" => context.platform_id = 1,
        "processor-count" => context.current_revisions = &[],
        "mixed-before" => {
            static MIXED: [u32; 2] = [
                poole_microcode::SYNTHETIC_REVISION_BASE + 0x10,
                poole_microcode::SYNTHETIC_REVISION_BASE + 0x11,
            ];
            context.current_revisions = &MIXED;
            context.processor_capacity = 2;
            context.receipt_capacity = 2;
        }
        "rollback-floor" => context.authenticated_rollback_floor = 0,
        "boot-mode" => context.boot_mode = 0,
        "stage" => context.executor_stage = 0,
        "feature-timing" => context.before_affected_features = false,
        "schedule-timing" => context.before_user_scheduling = false,
        "processor-inventory" => context.processor_inventory_complete = false,
        "quiescence" => context.processor_set_quiesced = false,
        "payload-capacity" => context.payload_capacity = 0,
        "patch-capacity" => context.patch_capacity = 0,
        "processor-capacity" => context.processor_capacity = 0,
        "receipt-capacity" => context.receipt_capacity = 0,
        "apply-authority" => context.apply_authority_granted = false,
        "firmware-mutation" => context.firmware_mutation_requested = true,
        "physical-media" => context.physical_media_write_requested = true,
        "implemented" => context.qualification_only = false,
        _ => return Err("transport"),
    }
    let selection = poole_microcode::authorize_apply_plan(&bundle, &context, &[])
        .map_err(|error| error.code())?;
    Ok(selection_text(selection))
}

fn verify_summary(value: &str) -> Result<String, &'static str> {
    let fields: Vec<_> = value.split(':').collect();
    if fields.len() != 9 {
        return Err("transport");
    }
    let bytes = decode_hex(fields[0])?;
    let bundle = poole_microcode::parse(&bytes).map_err(|error| error.code())?;
    let current = parse_hex_u32(fields[1])?;
    let after = parse_revisions(fields[2])?;
    if after.is_empty() {
        return Err("transport");
    }
    let before = vec![current; after.len()];
    let selection = poole_microcode::select_patch(
        &bundle,
        bundle.target_cpuid_signature,
        bundle.target_platform_id,
        current,
        bundle.security_revision_floor,
        poole_microcode::MODE_NORMAL,
        &[],
    )
    .map_err(|error| error.code())?;
    let observation = poole_microcode::PostApplyObservation {
        patch_id: selection.patch.ok_or("transport")?.patch_id,
        target_revision: selection.patch.ok_or("transport")?.revision,
        before_revisions: &before,
        after_revisions: &after,
        cpuid_signature_before: bundle.target_cpuid_signature,
        cpuid_signature_after: bundle.target_cpuid_signature,
        cpuid_evidence_before_sha256: [1u8; 32],
        cpuid_evidence_after_sha256: [2u8; 32],
        feature_policy_revalidated: parse_bool(fields[3])?,
        mitigation_policy_revalidated: parse_bool(fields[4])?,
        receipt_persisted: parse_bool(fields[5])?,
        mixed_failure_quarantined: parse_bool(fields[6])?,
        user_scheduling_started: parse_bool(fields[7])?,
    };
    if fields[8] != "-" {
        return Err("transport");
    }
    poole_microcode::verify_post_apply(&bundle, &selection, &observation, &[])
        .map_err(|error| error.code())?;
    Ok("OK:verified".to_owned())
}

fn evaluate(line: &str) -> Result<String, &'static str> {
    if let Some(value) = line.strip_prefix("P:") {
        return parse_summary(value);
    }
    if let Some(value) = line.strip_prefix("S:") {
        return select_summary(value);
    }
    if let Some(value) = line.strip_prefix("A:") {
        return activation_summary(value);
    }
    if let Some(value) = line.strip_prefix("V:") {
        return verify_summary(value);
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
