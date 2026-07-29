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

fn digest(value: &str) -> Result<[u8; 32], &'static str> {
    let bytes = decode_hex(value)?;
    bytes.try_into().map_err(|_| "transport")
}

fn boolean(value: &str) -> Result<bool, &'static str> {
    match value {
        "0" => Ok(false),
        "1" => Ok(true),
        _ => Err("transport"),
    }
}

fn policy_summary(value: &str) -> Result<String, &'static str> {
    let bytes = decode_hex(value)?;
    let policy = poole_boot_trust::parse_policy(&bytes).map_err(|error| error.code())?;
    Ok(format!(
        "OK;flags={};version={};epoch={};floor={};generation={};body={}",
        policy.flags,
        policy.policy_version,
        policy.trust_epoch,
        policy.minimum_secure_version,
        policy.minimum_state_generation,
        encode_hex(&policy.body_sha256),
    ))
}

fn state_summary(value: &str) -> Result<String, &'static str> {
    let bytes = decode_hex(value)?;
    let state = poole_boot_trust::parse_state(&bytes).map_err(|error| error.code())?;
    Ok(format!(
        "OK;flags={};copy={};generation={};epoch={};manifest={};policy={};body={}",
        state.flags,
        state.copy_index,
        state.state_generation,
        state.store_epoch,
        state.accepted_manifest_version,
        state.accepted_policy_version,
        encode_hex(&state.body_sha256),
    ))
}

fn development_summary(value: &str) -> Result<String, &'static str> {
    let fields: Vec<&str> = value.split(':').collect();
    if fields.len() != 8 {
        return Err("transport");
    }
    let policy = decode_hex(fields[0])?;
    let state = decode_hex(fields[1])?;
    let observed = poole_boot_trust::ObservedBoot {
        manifest_sha256: digest(fields[2])?,
        kernel_sha256: digest(fields[3])?,
        retained_set_sha256: digest(fields[4])?,
        revocation_set_sha256: digest(fields[5])?,
        manifest_version: fields[6].parse().map_err(|_| "transport")?,
        minimum_secure_version: fields[7].parse().map_err(|_| "transport")?,
        artifact_role_mask: poole_boot_trust::ARTIFACT_ROLE_MASK,
    };
    let summary = poole_boot_trust::validate_development(&policy, &state, &observed)
        .map_err(|error| error.code())?;
    Ok(format!(
        "OK;bindings={};denial={};policy={};state={};authority={};writes={}",
        summary.binding_count,
        summary.denial,
        encode_hex(&summary.policy_sha256),
        encode_hex(&summary.state_sha256),
        summary.authority_grants,
        summary.state_writes,
    ))
}

fn authorization_summary(value: &str) -> Result<String, &'static str> {
    let fields: Vec<&str> = value.split(':').collect();
    if fields.len() != 10 {
        return Err("transport");
    }
    let policy_bytes = decode_hex(fields[0])?;
    let state_bytes = decode_hex(fields[1])?;
    let policy = poole_boot_trust::parse_policy(&policy_bytes).map_err(|error| error.code())?;
    let state = poole_boot_trust::parse_state(&state_bytes).map_err(|error| error.code())?;
    let observed = poole_boot_trust::ObservedBoot {
        manifest_sha256: digest(fields[2])?,
        kernel_sha256: digest(fields[3])?,
        retained_set_sha256: digest(fields[4])?,
        revocation_set_sha256: digest(fields[5])?,
        manifest_version: fields[6].parse().map_err(|_| "transport")?,
        minimum_secure_version: fields[7].parse().map_err(|_| "transport")?,
        artifact_role_mask: fields[8].parse().map_err(|_| "transport")?,
    };
    let mask: u8 = fields[9].parse().map_err(|_| "transport")?;
    let evidence = poole_boot_trust::VerificationEvidence {
        policy_signature_verified: mask & (1 << 0) != 0,
        policy_threshold_verified: mask & (1 << 1) != 0,
        revocation_state_authenticated: mask & (1 << 2) != 0,
        policy_not_revoked: mask & (1 << 3) != 0,
        state_authenticated: mask & (1 << 4) != 0,
        state_monotonic: mask & (1 << 5) != 0,
        state_backend_writable: mask & (1 << 6) != 0,
        secure_boot_state_verified: mask & (1 << 7) != 0,
    };
    let authorized = poole_boot_trust::authorize(&policy, &state, &observed, &evidence)
        .map_err(|error| error.code())?;
    Ok(format!(
        "OK;policy={};state={};version={};generation={};epoch={}",
        encode_hex(&authorized.policy_sha256),
        encode_hex(&authorized.state_sha256),
        authorized.policy_version,
        authorized.state_generation,
        authorized.trust_epoch,
    ))
}

fn backend_summary(value: &str) -> Result<String, &'static str> {
    let fields: Vec<&str> = value.split(':').collect();
    if fields.len() != 17 {
        return Err("transport");
    }
    let copy0 = if fields[13] == "-" {
        None
    } else {
        Some(decode_hex(fields[13])?)
    };
    let copy1 = if fields[15] == "-" {
        None
    } else {
        Some(decode_hex(fields[15])?)
    };
    let copies = [
        poole_boot_trust::backend::BackendCopy {
            bytes: copy0.as_deref(),
            authentication_verified: boolean(fields[14])?,
        },
        poole_boot_trust::backend::BackendCopy {
            bytes: copy1.as_deref(),
            authentication_verified: boolean(fields[16])?,
        },
    ];
    let anchor = poole_boot_trust::backend::MonotonicAnchor {
        state_generation: fields[0].parse().map_err(|_| "transport")?,
        store_epoch: fields[1].parse().map_err(|_| "transport")?,
        auth_profile: fields[2].parse().map_err(|_| "transport")?,
        logical_state_sha256: digest(fields[3])?,
        previous_state_sha256: digest(fields[4])?,
        authenticated: boolean(fields[5])?,
        monotonic: boolean(fields[6])?,
    };
    let requirements = poole_boot_trust::backend::BackendRequirements {
        minimum_state_generation: fields[7].parse().map_err(|_| "transport")?,
        minimum_store_epoch: fields[8].parse().map_err(|_| "transport")?,
        target_store_epoch: fields[9].parse().map_err(|_| "transport")?,
        target_auth_profile: fields[10].parse().map_err(|_| "transport")?,
    };
    let access = poole_boot_trust::backend::BackendAccess {
        writable: boolean(fields[11])?,
        repair_capacity: boolean(fields[12])?,
    };
    let selected =
        poole_boot_trust::backend::select_backend_state(&copies, &anchor, &requirements, &access)
            .map_err(|error| error.code())?;
    Ok(format!(
        "OK;copy={};present={};parsed={};authenticated={};anchored={};repair={};stale={};future={};generation={};epoch={};profile={};logical={};migration={};authority={};writes={}",
        selected.selected_copy,
        selected.present_copy_mask,
        selected.parsed_copy_mask,
        selected.authenticated_copy_mask,
        selected.anchored_copy_mask,
        selected.repair_copy_mask,
        selected.stale_copy_mask,
        selected.future_copy_mask,
        selected.state_generation,
        selected.store_epoch,
        selected.auth_profile,
        encode_hex(&selected.logical_state_sha256),
        u8::from(selected.migration_required),
        selected.authority_grants,
        selected.state_writes,
    ))
}

fn evaluate(line: &str) -> Result<String, &'static str> {
    if let Some(value) = line.strip_prefix("P:") {
        return policy_summary(value);
    }
    if let Some(value) = line.strip_prefix("S:") {
        return state_summary(value);
    }
    if let Some(value) = line.strip_prefix("D:") {
        return development_summary(value);
    }
    if let Some(value) = line.strip_prefix("A:") {
        return authorization_summary(value);
    }
    if let Some(value) = line.strip_prefix("B:") {
        return backend_summary(value);
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
