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

fn observed_versions(
    bundle: &poole_firmware::Bundle<'_>,
) -> Result<Vec<poole_firmware::ObservedVersion>, &'static str> {
    (0..bundle.component_count as usize)
        .map(|index| {
            let item = bundle.component(index).map_err(|error| error.code())?;
            Ok(poole_firmware::ObservedVersion {
                component_id: item.component_id,
                version: item.current_version,
            })
        })
        .collect()
}

fn parse_summary(encoded: &str) -> Result<String, &'static str> {
    let bytes = decode_hex(encoded)?;
    let bundle = poole_firmware::parse(&bytes).map_err(|error| error.code())?;
    let payload_bytes = (0..bundle.component_count as usize).try_fold(0u64, |total, index| {
        let component = bundle.component(index).map_err(|error| error.code())?;
        total
            .checked_add(component.external_payload_bytes)
            .ok_or("transport")
    })?;
    Ok(format!(
        "OK;version={}.{};bytes={};components={};dependencies={};payload={};body={}",
        poole_firmware::MAJOR_VERSION,
        poole_firmware::MINOR_VERSION,
        bundle.raw.len(),
        bundle.component_count,
        bundle.dependency_count,
        payload_bytes,
        encode_hex(&bundle.body_sha256),
    ))
}

fn activation_summary(value: &str) -> Result<String, &'static str> {
    let (mode, encoded) = value.split_once(':').ok_or("transport")?;
    let bytes = decode_hex(encoded)?;
    let bundle = poole_firmware::parse(&bytes).map_err(|error| error.code())?;
    let mut versions = observed_versions(&bundle)?;
    if mode == "current-versions" {
        versions[0].version ^= 1;
    }
    let mut context = poole_firmware::ActivationContext::synthetic_qualified(&bundle, &versions);
    match mode {
        "qualified" => {}
        "development" => {
            context = poole_firmware::ActivationContext::development(&bundle, &versions)
        }
        "outer-signature" => context.outer_signature_verified = false,
        "outer-role" => context.outer_role = 5,
        "outer-version" => context.outer_version = 2,
        "outer-payload" => context.outer_payload_sha256[0] ^= 1,
        "outer-file" => context.expected_outer_file_sha256[0] ^= 1,
        "manifest-signature" => context.manifest_signature_verified = false,
        "package-signature" => context.package_signature_verified = false,
        "vendor-signature" => context.vendor_signatures_verified = false,
        "target-profile" => context.target_profile_verified = false,
        "hardware-inventory" => context.hardware_inventory_observed = false,
        "device-identity" => context.exact_device_identities_verified = false,
        "current-versions" => {}
        "transport-support" => context.transport_support_verified = false,
        "firmware-services" => context.firmware_service_inventory_verified = false,
        "updater-plugins" => context.updater_plugins_verified = false,
        "plugin-authority" => context.plugin_authority_granted = false,
        "external-payloads" => context.external_payloads_present = false,
        "payload-digests" => context.payload_digests_verified = false,
        "license-policy" => context.license_policy_satisfied = false,
        "redistribution" => context.redistribution_authorized = false,
        "revocation-state" => context.revocation_state_authenticated = false,
        "component-revoked" => context.no_components_revoked = false,
        "anti-rollback" => context.anti_rollback_state_authenticated = false,
        "recovery" => context.recovery_ready = false,
        "recovery-backup" => context.recovery_backup_verified = false,
        "staging" => context.protected_staging_ready = false,
        "staging-capacity" => context.staging_capacity_bytes = 0,
        "power" => context.stable_power = false,
        "ac-power" => context.ac_power_present = false,
        "battery" => context.battery_percent = 0,
        "transaction-journal" => context.transaction_journal_ready = false,
        "quiescence" => context.quiescence_ready = false,
        "storage-guard" => context.storage_guard_ready = false,
        "suspend-shutdown" => context.suspend_shutdown_guard_ready = false,
        "reset-authority" => context.reset_authorized = false,
        "reboot-authority" => context.reboot_authorized = false,
        "user-confirmation" => context.user_confirmed = false,
        "physical-presence" => context.physical_presence_verified = false,
        "post-reset-verifier" => context.post_reset_verifier_ready = false,
        "receipt-storage" => context.receipt_storage_ready = false,
        "firmware-authority" => context.firmware_change_authorized = false,
        "not-qualification" => context.qualification_only = false,
        "live-call" => context.live_firmware_call_requested = true,
        "driver-load" => context.driver_load_requested = true,
        "media-write" => context.physical_media_write_requested = true,
        "firmware-mutation" => context.firmware_mutation_requested = true,
        _ => return Err("transport"),
    }
    let plan =
        poole_firmware::authorize_dry_run_plan(&bundle, &context).map_err(|error| error.code())?;
    Ok(format!(
        "OK;components={};parallel={};payload={};reset={};qualification={}",
        plan.component_count,
        plan.maximum_parallel_components,
        plan.external_payload_bytes,
        u8::from(plan.reset_required),
        u8::from(plan.qualification_only),
    ))
}

fn post_reset_summary(value: &str) -> Result<String, &'static str> {
    let (mode, encoded) = value.split_once(':').ok_or("transport")?;
    let bytes = decode_hex(encoded)?;
    let bundle = poole_firmware::parse(&bytes).map_err(|error| error.code())?;
    let mut records: Vec<_> = (0..bundle.component_count as usize)
        .map(|index| {
            let item = bundle.component(index).map_err(|error| error.code())?;
            Ok(poole_firmware::PostResetRecord {
                component_id: item.component_id,
                resource_guid: item.resource_guid,
                hardware_instance: item.hardware_instance,
                observed_version: item.target_version,
                last_attempt_version: item.target_version,
                last_attempt_status: poole_firmware::EXPECTED_LAST_ATTEMPT_SUCCESS,
                reenumerated: true,
                self_test_passed: true,
                recovery_intact: true,
                receipt_persisted: true,
                boot_loop_prevented: true,
                state_committed: true,
                driver_rebound_after_validation: true,
            })
        })
        .collect::<Result<_, &'static str>>()?;
    let mut qualification_only = true;
    match mode {
        "qualified" => {}
        "not-qualification" => qualification_only = false,
        "count" => {
            records.pop();
        }
        "order" => records[0].component_id ^= 1,
        "resource" => records[0].resource_guid[0] ^= 1,
        "hardware-instance" => records[0].hardware_instance ^= 1,
        "version" => records[0].observed_version ^= 1,
        "last-version" => records[0].last_attempt_version ^= 1,
        "last-status" => records[0].last_attempt_status = 1,
        "reenumeration" => records[0].reenumerated = false,
        "self-test" => records[0].self_test_passed = false,
        "recovery" => records[0].recovery_intact = false,
        "receipt" => records[0].receipt_persisted = false,
        "boot-loop" => records[0].boot_loop_prevented = false,
        "state-commit" => records[0].state_committed = false,
        "driver-rebind" => records[0].driver_rebound_after_validation = false,
        _ => return Err("transport"),
    }
    poole_firmware::verify_post_reset(&bundle, &records, qualification_only)
        .map_err(|error| error.code())?;
    Ok("OK:verified".to_owned())
}

fn evaluate(line: &str) -> Result<String, &'static str> {
    if let Some(value) = line.strip_prefix("P:") {
        return parse_summary(value);
    }
    if let Some(value) = line.strip_prefix("A:") {
        return activation_summary(value);
    }
    if let Some(value) = line.strip_prefix("R:") {
        return post_reset_summary(value);
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
