#![no_std]
#![deny(warnings)]

use sha2::{Digest, Sha256};

pub const CONTRACT_ID: &str = "PFWM1";
pub const MAGIC: [u8; 8] = *b"PFWM1\0\0\0";
pub const MAJOR_VERSION: u16 = 1;
pub const MINOR_VERSION: u16 = 0;
pub const HEADER_BYTES: usize = 512;
pub const COMPONENT_RECORD_BYTES: usize = 256;
pub const DEPENDENCY_RECORD_BYTES: usize = 16;
pub const MAX_MANIFEST_BYTES: usize = 64 * 1024;
pub const MAX_COMPONENTS: usize = 32;
pub const MAX_DEPENDENCIES: usize = 128;
pub const MAX_EXTERNAL_PAYLOAD_BYTES: u64 = 64 * 1024 * 1024;
pub const MAX_APPLY_TIMEOUT_MS: u32 = 30 * 60 * 1000;
pub const MAX_RESET_TIMEOUT_MS: u32 = 15 * 60 * 1000;
pub const MAX_RETRY_LIMIT: u16 = 3;

pub const PROFILE_SYNTHETIC_QUALIFICATION: u16 = 1;

pub const KIND_PLATFORM_FIRMWARE: u16 = 1;
pub const KIND_CONTROLLER_FIRMWARE: u16 = 2;
pub const KIND_DEVICE_FIRMWARE: u16 = 3;
pub const TRANSPORT_UEFI_CAPSULE_ESRT: u16 = 1;
pub const TRANSPORT_DEVICE_PLUGIN: u16 = 2;
pub const TRANSPORT_PLDM: u16 = 3;

pub const REQUIRED_FLAGS: u32 = (1 << 20) - 1;
pub const COMPONENT_REQUIRED_FLAGS: u32 = (1 << 19) - 1;
pub const OUTER_ROLE_FIRMWARE_MANIFEST: u32 = 6;
pub const EXPECTED_LAST_ATTEMPT_SUCCESS: u32 = 0;

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum Error {
    Truncated,
    Oversized,
    Magic,
    Version,
    HeaderSize,
    RecordSize,
    Profile,
    Flags,
    ManifestVersion,
    Counts,
    TableLayout,
    TrailingBytes,
    Limits,
    DigestZero,
    ManifestId,
    Reserved,
    BodyDigest,
    ComponentId,
    ComponentOrder,
    ComponentKind,
    ComponentTransport,
    ComponentMapping,
    ComponentFlags,
    ComponentReserved,
    ComponentGuid,
    ComponentHardwareInstance,
    ComponentVersions,
    ComponentPayloadSize,
    ComponentDigest,
    DependencyLayout,
    DependencyId,
    DependencyOrder,
    DependencyVersion,
    DependencyPhase,
    PhaseOrder,
    ActivationOuterSignature,
    ActivationOuterRole,
    ActivationOuterVersion,
    ActivationOuterPayloadDigest,
    ActivationOuterFileDigest,
    ActivationManifestSignature,
    ActivationPackageSignature,
    ActivationVendorSignature,
    ActivationTargetProfile,
    ActivationHardwareInventory,
    ActivationDeviceIdentity,
    ActivationCurrentVersions,
    ActivationTransportSupport,
    ActivationFirmwareServices,
    ActivationUpdaterPlugins,
    ActivationPluginAuthority,
    ActivationExternalPayloads,
    ActivationPayloadDigests,
    ActivationLicensePolicy,
    ActivationRedistribution,
    ActivationRevocationState,
    ActivationComponentRevoked,
    ActivationAntiRollback,
    ActivationRecovery,
    ActivationRecoveryBackup,
    ActivationStaging,
    ActivationStagingCapacity,
    ActivationPower,
    ActivationAcPower,
    ActivationBattery,
    ActivationTransactionJournal,
    ActivationQuiescence,
    ActivationStorageGuard,
    ActivationSuspendShutdownGuard,
    ActivationResetAuthority,
    ActivationRebootAuthority,
    ActivationUserConfirmation,
    ActivationPhysicalPresence,
    ActivationPostResetVerifier,
    ActivationReceiptStorage,
    ActivationFirmwareChangeAuthority,
    ActivationNotQualificationOnly,
    ActivationLiveFirmwareCallRequested,
    ActivationDriverLoadRequested,
    ActivationPhysicalMediaWriteRequested,
    ActivationFirmwareMutationRequested,
    PostResetNotQualificationOnly,
    PostResetRecordCount,
    PostResetRecordOrder,
    PostResetResourceIdentity,
    PostResetHardwareInstance,
    PostResetVersion,
    PostResetLastAttemptVersion,
    PostResetLastAttemptStatus,
    PostResetReenumeration,
    PostResetSelfTest,
    PostResetRecovery,
    PostResetReceipt,
    PostResetBootLoopGuard,
    PostResetStateCommit,
    PostResetDriverRebind,
}

impl Error {
    pub const fn code(self) -> &'static str {
        match self {
            Self::Truncated => "pfwm_truncated",
            Self::Oversized => "pfwm_oversized",
            Self::Magic => "pfwm_magic",
            Self::Version => "pfwm_version",
            Self::HeaderSize => "pfwm_header_size",
            Self::RecordSize => "pfwm_record_size",
            Self::Profile => "pfwm_profile",
            Self::Flags => "pfwm_flags",
            Self::ManifestVersion => "pfwm_manifest_version",
            Self::Counts => "pfwm_counts",
            Self::TableLayout => "pfwm_table_layout",
            Self::TrailingBytes => "pfwm_trailing_bytes",
            Self::Limits => "pfwm_limits",
            Self::DigestZero => "pfwm_digest_zero",
            Self::ManifestId => "pfwm_manifest_id",
            Self::Reserved => "pfwm_reserved",
            Self::BodyDigest => "pfwm_body_digest",
            Self::ComponentId => "pfwm_component_id",
            Self::ComponentOrder => "pfwm_component_order",
            Self::ComponentKind => "pfwm_component_kind",
            Self::ComponentTransport => "pfwm_component_transport",
            Self::ComponentMapping => "pfwm_component_mapping",
            Self::ComponentFlags => "pfwm_component_flags",
            Self::ComponentReserved => "pfwm_component_reserved",
            Self::ComponentGuid => "pfwm_component_guid",
            Self::ComponentHardwareInstance => "pfwm_component_hardware_instance",
            Self::ComponentVersions => "pfwm_component_versions",
            Self::ComponentPayloadSize => "pfwm_component_payload_size",
            Self::ComponentDigest => "pfwm_component_digest",
            Self::DependencyLayout => "pfwm_dependency_layout",
            Self::DependencyId => "pfwm_dependency_id",
            Self::DependencyOrder => "pfwm_dependency_order",
            Self::DependencyVersion => "pfwm_dependency_version",
            Self::DependencyPhase => "pfwm_dependency_phase",
            Self::PhaseOrder => "pfwm_phase_order",
            Self::ActivationOuterSignature => "pfwm_activation_outer_signature",
            Self::ActivationOuterRole => "pfwm_activation_outer_role",
            Self::ActivationOuterVersion => "pfwm_activation_outer_version",
            Self::ActivationOuterPayloadDigest => "pfwm_activation_outer_payload_digest",
            Self::ActivationOuterFileDigest => "pfwm_activation_outer_file_digest",
            Self::ActivationManifestSignature => "pfwm_activation_manifest_signature",
            Self::ActivationPackageSignature => "pfwm_activation_package_signature",
            Self::ActivationVendorSignature => "pfwm_activation_vendor_signature",
            Self::ActivationTargetProfile => "pfwm_activation_target_profile",
            Self::ActivationHardwareInventory => "pfwm_activation_hardware_inventory",
            Self::ActivationDeviceIdentity => "pfwm_activation_device_identity",
            Self::ActivationCurrentVersions => "pfwm_activation_current_versions",
            Self::ActivationTransportSupport => "pfwm_activation_transport_support",
            Self::ActivationFirmwareServices => "pfwm_activation_firmware_services",
            Self::ActivationUpdaterPlugins => "pfwm_activation_updater_plugins",
            Self::ActivationPluginAuthority => "pfwm_activation_plugin_authority",
            Self::ActivationExternalPayloads => "pfwm_activation_external_payloads",
            Self::ActivationPayloadDigests => "pfwm_activation_payload_digests",
            Self::ActivationLicensePolicy => "pfwm_activation_license_policy",
            Self::ActivationRedistribution => "pfwm_activation_redistribution",
            Self::ActivationRevocationState => "pfwm_activation_revocation_state",
            Self::ActivationComponentRevoked => "pfwm_activation_component_revoked",
            Self::ActivationAntiRollback => "pfwm_activation_anti_rollback",
            Self::ActivationRecovery => "pfwm_activation_recovery",
            Self::ActivationRecoveryBackup => "pfwm_activation_recovery_backup",
            Self::ActivationStaging => "pfwm_activation_staging",
            Self::ActivationStagingCapacity => "pfwm_activation_staging_capacity",
            Self::ActivationPower => "pfwm_activation_power",
            Self::ActivationAcPower => "pfwm_activation_ac_power",
            Self::ActivationBattery => "pfwm_activation_battery",
            Self::ActivationTransactionJournal => "pfwm_activation_transaction_journal",
            Self::ActivationQuiescence => "pfwm_activation_quiescence",
            Self::ActivationStorageGuard => "pfwm_activation_storage_guard",
            Self::ActivationSuspendShutdownGuard => "pfwm_activation_suspend_shutdown_guard",
            Self::ActivationResetAuthority => "pfwm_activation_reset_authority",
            Self::ActivationRebootAuthority => "pfwm_activation_reboot_authority",
            Self::ActivationUserConfirmation => "pfwm_activation_user_confirmation",
            Self::ActivationPhysicalPresence => "pfwm_activation_physical_presence",
            Self::ActivationPostResetVerifier => "pfwm_activation_post_reset_verifier",
            Self::ActivationReceiptStorage => "pfwm_activation_receipt_storage",
            Self::ActivationFirmwareChangeAuthority => "pfwm_activation_firmware_change_authority",
            Self::ActivationNotQualificationOnly => "pfwm_activation_not_qualification_only",
            Self::ActivationLiveFirmwareCallRequested => {
                "pfwm_activation_live_firmware_call_requested"
            }
            Self::ActivationDriverLoadRequested => "pfwm_activation_driver_load_requested",
            Self::ActivationPhysicalMediaWriteRequested => {
                "pfwm_activation_physical_media_write_requested"
            }
            Self::ActivationFirmwareMutationRequested => {
                "pfwm_activation_firmware_mutation_requested"
            }
            Self::PostResetNotQualificationOnly => "pfwm_post_reset_not_qualification_only",
            Self::PostResetRecordCount => "pfwm_post_reset_record_count",
            Self::PostResetRecordOrder => "pfwm_post_reset_record_order",
            Self::PostResetResourceIdentity => "pfwm_post_reset_resource_identity",
            Self::PostResetHardwareInstance => "pfwm_post_reset_hardware_instance",
            Self::PostResetVersion => "pfwm_post_reset_version",
            Self::PostResetLastAttemptVersion => "pfwm_post_reset_last_attempt_version",
            Self::PostResetLastAttemptStatus => "pfwm_post_reset_last_attempt_status",
            Self::PostResetReenumeration => "pfwm_post_reset_reenumeration",
            Self::PostResetSelfTest => "pfwm_post_reset_self_test",
            Self::PostResetRecovery => "pfwm_post_reset_recovery",
            Self::PostResetReceipt => "pfwm_post_reset_receipt",
            Self::PostResetBootLoopGuard => "pfwm_post_reset_boot_loop_guard",
            Self::PostResetStateCommit => "pfwm_post_reset_state_commit",
            Self::PostResetDriverRebind => "pfwm_post_reset_driver_rebind",
        }
    }
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct Component {
    pub component_id: u32,
    pub kind: u16,
    pub transport: u16,
    pub phase: u16,
    pub dependency_count: u16,
    pub dependency_start: u32,
    pub flags: u32,
    pub resource_guid: [u8; 16],
    pub hardware_instance: u64,
    pub current_version: u64,
    pub target_version: u64,
    pub lowest_supported_version: u64,
    pub rollback_floor: u64,
    pub known_good_version: u64,
    pub external_payload_bytes: u64,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct Dependency {
    pub component_id: u32,
    pub required_component_id: u32,
    pub minimum_version: u64,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct Bundle<'a> {
    pub raw: &'a [u8],
    pub manifest_version: u64,
    pub profile: u16,
    pub flags: u32,
    pub component_count: u32,
    pub dependency_count: u32,
    pub maximum_external_payload_bytes: u64,
    pub maximum_transaction_components: u32,
    pub required_battery_percent: u16,
    pub retry_limit: u16,
    pub apply_timeout_ms: u32,
    pub reset_timeout_ms: u32,
    pub body_sha256: [u8; 32],
}

impl Bundle<'_> {
    pub fn component(&self, index: usize) -> Result<Component, Error> {
        if index >= self.component_count as usize {
            return Err(Error::ComponentId);
        }
        parse_component(self.raw, HEADER_BYTES + index * COMPONENT_RECORD_BYTES)
    }

    pub fn dependency(&self, index: usize) -> Result<Dependency, Error> {
        if index >= self.dependency_count as usize {
            return Err(Error::DependencyId);
        }
        let offset = HEADER_BYTES
            + self.component_count as usize * COMPONENT_RECORD_BYTES
            + index * DEPENDENCY_RECORD_BYTES;
        Ok(Dependency {
            component_id: read_u32(self.raw, offset)?,
            required_component_id: read_u32(self.raw, offset + 4)?,
            minimum_version: read_u64(self.raw, offset + 8)?,
        })
    }
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct ObservedVersion {
    pub component_id: u32,
    pub version: u64,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct ActivationContext<'a> {
    pub outer_role: u32,
    pub outer_version: u64,
    pub outer_payload_sha256: [u8; 32],
    pub outer_file_sha256: [u8; 32],
    pub expected_outer_file_sha256: [u8; 32],
    pub observed_versions: &'a [ObservedVersion],
    pub staging_capacity_bytes: u64,
    pub battery_percent: u16,
    pub outer_signature_verified: bool,
    pub manifest_signature_verified: bool,
    pub package_signature_verified: bool,
    pub vendor_signatures_verified: bool,
    pub target_profile_verified: bool,
    pub hardware_inventory_observed: bool,
    pub exact_device_identities_verified: bool,
    pub current_versions_observed: bool,
    pub transport_support_verified: bool,
    pub firmware_service_inventory_verified: bool,
    pub updater_plugins_verified: bool,
    pub plugin_authority_granted: bool,
    pub external_payloads_present: bool,
    pub payload_digests_verified: bool,
    pub license_policy_satisfied: bool,
    pub redistribution_authorized: bool,
    pub revocation_state_authenticated: bool,
    pub no_components_revoked: bool,
    pub anti_rollback_state_authenticated: bool,
    pub recovery_ready: bool,
    pub recovery_backup_verified: bool,
    pub protected_staging_ready: bool,
    pub stable_power: bool,
    pub ac_power_present: bool,
    pub transaction_journal_ready: bool,
    pub quiescence_ready: bool,
    pub storage_guard_ready: bool,
    pub suspend_shutdown_guard_ready: bool,
    pub reset_authorized: bool,
    pub reboot_authorized: bool,
    pub user_confirmed: bool,
    pub physical_presence_verified: bool,
    pub post_reset_verifier_ready: bool,
    pub receipt_storage_ready: bool,
    pub firmware_change_authorized: bool,
    pub qualification_only: bool,
    pub live_firmware_call_requested: bool,
    pub driver_load_requested: bool,
    pub physical_media_write_requested: bool,
    pub firmware_mutation_requested: bool,
}

impl<'a> ActivationContext<'a> {
    pub fn development(bundle: &Bundle<'_>, observed_versions: &'a [ObservedVersion]) -> Self {
        let payload = sha256(bundle.raw);
        let outer = sha256(b"PFWM1/UNSIGNED-OUTER-FILE");
        Self {
            outer_role: OUTER_ROLE_FIRMWARE_MANIFEST,
            outer_version: MAJOR_VERSION as u64,
            outer_payload_sha256: payload,
            outer_file_sha256: outer,
            expected_outer_file_sha256: outer,
            observed_versions,
            staging_capacity_bytes: bundle.maximum_external_payload_bytes,
            battery_percent: 100,
            outer_signature_verified: false,
            manifest_signature_verified: false,
            package_signature_verified: false,
            vendor_signatures_verified: false,
            target_profile_verified: false,
            hardware_inventory_observed: false,
            exact_device_identities_verified: false,
            current_versions_observed: false,
            transport_support_verified: false,
            firmware_service_inventory_verified: false,
            updater_plugins_verified: false,
            plugin_authority_granted: false,
            external_payloads_present: false,
            payload_digests_verified: false,
            license_policy_satisfied: false,
            redistribution_authorized: false,
            revocation_state_authenticated: false,
            no_components_revoked: false,
            anti_rollback_state_authenticated: false,
            recovery_ready: false,
            recovery_backup_verified: false,
            protected_staging_ready: false,
            stable_power: false,
            ac_power_present: false,
            transaction_journal_ready: false,
            quiescence_ready: false,
            storage_guard_ready: false,
            suspend_shutdown_guard_ready: false,
            reset_authorized: false,
            reboot_authorized: false,
            user_confirmed: false,
            physical_presence_verified: false,
            post_reset_verifier_ready: false,
            receipt_storage_ready: false,
            firmware_change_authorized: false,
            qualification_only: true,
            live_firmware_call_requested: false,
            driver_load_requested: false,
            physical_media_write_requested: false,
            firmware_mutation_requested: false,
        }
    }

    pub fn synthetic_qualified(
        bundle: &Bundle<'_>,
        observed_versions: &'a [ObservedVersion],
    ) -> Self {
        let mut context = Self::development(bundle, observed_versions);
        context.outer_signature_verified = true;
        context.manifest_signature_verified = true;
        context.package_signature_verified = true;
        context.vendor_signatures_verified = true;
        context.target_profile_verified = true;
        context.hardware_inventory_observed = true;
        context.exact_device_identities_verified = true;
        context.current_versions_observed = true;
        context.transport_support_verified = true;
        context.firmware_service_inventory_verified = true;
        context.updater_plugins_verified = true;
        context.plugin_authority_granted = true;
        context.external_payloads_present = true;
        context.payload_digests_verified = true;
        context.license_policy_satisfied = true;
        context.redistribution_authorized = true;
        context.revocation_state_authenticated = true;
        context.no_components_revoked = true;
        context.anti_rollback_state_authenticated = true;
        context.recovery_ready = true;
        context.recovery_backup_verified = true;
        context.protected_staging_ready = true;
        context.stable_power = true;
        context.ac_power_present = true;
        context.transaction_journal_ready = true;
        context.quiescence_ready = true;
        context.storage_guard_ready = true;
        context.suspend_shutdown_guard_ready = true;
        context.reset_authorized = true;
        context.reboot_authorized = true;
        context.user_confirmed = true;
        context.physical_presence_verified = true;
        context.post_reset_verifier_ready = true;
        context.receipt_storage_ready = true;
        context.firmware_change_authorized = true;
        context
    }
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct DryRunPlan {
    pub component_count: u32,
    pub maximum_parallel_components: u32,
    pub external_payload_bytes: u64,
    pub reset_required: bool,
    pub qualification_only: bool,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct PostResetRecord {
    pub component_id: u32,
    pub resource_guid: [u8; 16],
    pub hardware_instance: u64,
    pub observed_version: u64,
    pub last_attempt_version: u64,
    pub last_attempt_status: u32,
    pub reenumerated: bool,
    pub self_test_passed: bool,
    pub recovery_intact: bool,
    pub receipt_persisted: bool,
    pub boot_loop_prevented: bool,
    pub state_committed: bool,
    pub driver_rebound_after_validation: bool,
}

fn read_u16(bytes: &[u8], offset: usize) -> Result<u16, Error> {
    let value = bytes.get(offset..offset + 2).ok_or(Error::Truncated)?;
    Ok(u16::from_le_bytes([value[0], value[1]]))
}

fn read_u32(bytes: &[u8], offset: usize) -> Result<u32, Error> {
    let value = bytes.get(offset..offset + 4).ok_or(Error::Truncated)?;
    Ok(u32::from_le_bytes([value[0], value[1], value[2], value[3]]))
}

fn read_u64(bytes: &[u8], offset: usize) -> Result<u64, Error> {
    let value = bytes.get(offset..offset + 8).ok_or(Error::Truncated)?;
    Ok(u64::from_le_bytes([
        value[0], value[1], value[2], value[3], value[4], value[5], value[6], value[7],
    ]))
}

fn read_array<const N: usize>(bytes: &[u8], offset: usize) -> Result<[u8; N], Error> {
    let value = bytes.get(offset..offset + N).ok_or(Error::Truncated)?;
    let mut result = [0u8; N];
    result.copy_from_slice(value);
    Ok(result)
}

pub fn sha256(bytes: &[u8]) -> [u8; 32] {
    let value = Sha256::digest(bytes);
    let mut result = [0u8; 32];
    result.copy_from_slice(&value);
    result
}

fn digest_nonzero(bytes: &[u8], offset: usize, error: Error) -> Result<(), Error> {
    let value = bytes.get(offset..offset + 32).ok_or(Error::Truncated)?;
    if value.iter().all(|byte| *byte == 0) {
        return Err(error);
    }
    Ok(())
}

fn manifest_id_valid(bytes: &[u8]) -> bool {
    let Some(field) = bytes.get(408..448) else {
        return false;
    };
    let Some(nul) = field.iter().position(|byte| *byte == 0) else {
        return false;
    };
    if nul == 0 || nul > 39 || field[nul..].iter().any(|byte| *byte != 0) {
        return false;
    }
    field[..nul].iter().enumerate().all(|(index, byte)| {
        byte.is_ascii_uppercase()
            || byte.is_ascii_digit()
            || (index > 0 && matches!(byte, b'.' | b'_' | b'-'))
    })
}

fn transport_allowed(kind: u16, transport: u16) -> bool {
    (kind == KIND_PLATFORM_FIRMWARE && transport == TRANSPORT_UEFI_CAPSULE_ESRT)
        || (kind == KIND_CONTROLLER_FIRMWARE && transport == TRANSPORT_DEVICE_PLUGIN)
        || (kind == KIND_DEVICE_FIRMWARE
            && matches!(transport, TRANSPORT_DEVICE_PLUGIN | TRANSPORT_PLDM))
}

fn parse_component(bytes: &[u8], offset: usize) -> Result<Component, Error> {
    let record = bytes
        .get(offset..offset + COMPONENT_RECORD_BYTES)
        .ok_or(Error::Truncated)?;
    let component_id = read_u32(record, 0)?;
    let kind = read_u16(record, 4)?;
    let transport = read_u16(record, 6)?;
    let phase = read_u16(record, 8)?;
    let dependency_count = read_u16(record, 10)?;
    let dependency_start = read_u32(record, 12)?;
    let flags = read_u32(record, 16)?;
    if component_id == 0 {
        return Err(Error::ComponentId);
    }
    if !matches!(
        kind,
        KIND_PLATFORM_FIRMWARE | KIND_CONTROLLER_FIRMWARE | KIND_DEVICE_FIRMWARE
    ) {
        return Err(Error::ComponentKind);
    }
    if !matches!(
        transport,
        TRANSPORT_UEFI_CAPSULE_ESRT | TRANSPORT_DEVICE_PLUGIN | TRANSPORT_PLDM
    ) {
        return Err(Error::ComponentTransport);
    }
    if !transport_allowed(kind, transport) {
        return Err(Error::ComponentMapping);
    }
    if flags != COMPONENT_REQUIRED_FLAGS {
        return Err(Error::ComponentFlags);
    }
    if read_u32(record, 20)? != 0 {
        return Err(Error::ComponentReserved);
    }
    let resource_guid = read_array(record, 24)?;
    if resource_guid.iter().all(|byte| *byte == 0) {
        return Err(Error::ComponentGuid);
    }
    let hardware_instance = read_u64(record, 40)?;
    if hardware_instance == 0 {
        return Err(Error::ComponentHardwareInstance);
    }
    let current_version = read_u64(record, 48)?;
    let target_version = read_u64(record, 56)?;
    let lowest_supported_version = read_u64(record, 64)?;
    let rollback_floor = read_u64(record, 72)?;
    let known_good_version = read_u64(record, 80)?;
    if !(lowest_supported_version > 0
        && lowest_supported_version <= rollback_floor
        && rollback_floor <= known_good_version
        && known_good_version <= current_version
        && current_version < target_version)
    {
        return Err(Error::ComponentVersions);
    }
    let external_payload_bytes = read_u64(record, 88)?;
    if external_payload_bytes == 0 || external_payload_bytes > MAX_EXTERNAL_PAYLOAD_BYTES {
        return Err(Error::ComponentPayloadSize);
    }
    for digest_offset in [96, 128, 160, 192, 224] {
        digest_nonzero(record, digest_offset, Error::ComponentDigest)?;
    }
    Ok(Component {
        component_id,
        kind,
        transport,
        phase,
        dependency_count,
        dependency_start,
        flags,
        resource_guid,
        hardware_instance,
        current_version,
        target_version,
        lowest_supported_version,
        rollback_floor,
        known_good_version,
        external_payload_bytes,
    })
}

fn component_by_id(bundle: &Bundle<'_>, component_id: u32) -> Result<Component, Error> {
    for index in 0..bundle.component_count as usize {
        let component = bundle.component(index)?;
        if component.component_id == component_id {
            return Ok(component);
        }
    }
    Err(Error::DependencyId)
}

pub fn parse(bytes: &[u8]) -> Result<Bundle<'_>, Error> {
    if bytes.len() < HEADER_BYTES {
        return Err(Error::Truncated);
    }
    if bytes.len() > MAX_MANIFEST_BYTES {
        return Err(Error::Oversized);
    }
    if bytes[..8] != MAGIC {
        return Err(Error::Magic);
    }
    if read_u16(bytes, 8)? != MAJOR_VERSION || read_u16(bytes, 10)? != MINOR_VERSION {
        return Err(Error::Version);
    }
    if read_u16(bytes, 12)? as usize != HEADER_BYTES {
        return Err(Error::HeaderSize);
    }
    if read_u16(bytes, 14)? as usize != COMPONENT_RECORD_BYTES
        || read_u16(bytes, 16)? as usize != DEPENDENCY_RECORD_BYTES
    {
        return Err(Error::RecordSize);
    }
    let profile = read_u16(bytes, 18)?;
    if profile != PROFILE_SYNTHETIC_QUALIFICATION {
        return Err(Error::Profile);
    }
    let flags = read_u32(bytes, 20)?;
    if flags != REQUIRED_FLAGS {
        return Err(Error::Flags);
    }
    let manifest_version = read_u64(bytes, 24)?;
    if manifest_version == 0 {
        return Err(Error::ManifestVersion);
    }
    let component_count = read_u32(bytes, 32)?;
    let dependency_count = read_u32(bytes, 36)?;
    if component_count == 0
        || component_count as usize > MAX_COMPONENTS
        || dependency_count as usize > MAX_DEPENDENCIES
    {
        return Err(Error::Counts);
    }
    let expected_dependency_offset = HEADER_BYTES
        .checked_add(component_count as usize * COMPONENT_RECORD_BYTES)
        .ok_or(Error::TableLayout)?;
    let expected_total = expected_dependency_offset
        .checked_add(dependency_count as usize * DEPENDENCY_RECORD_BYTES)
        .ok_or(Error::TableLayout)?;
    if read_u64(bytes, 40)? as usize != HEADER_BYTES
        || read_u64(bytes, 48)? as usize != expected_dependency_offset
    {
        return Err(Error::TableLayout);
    }
    if read_u64(bytes, 56)? as usize != expected_total || bytes.len() < expected_total {
        return Err(Error::Truncated);
    }
    if bytes.len() > expected_total {
        return Err(Error::TrailingBytes);
    }
    let maximum_external_payload_bytes = read_u64(bytes, 64)?;
    let maximum_transaction_components = read_u32(bytes, 72)?;
    let required_battery_percent = read_u16(bytes, 76)?;
    let retry_limit = read_u16(bytes, 78)?;
    let apply_timeout_ms = read_u32(bytes, 80)?;
    let reset_timeout_ms = read_u32(bytes, 84)?;
    if maximum_external_payload_bytes == 0
        || maximum_external_payload_bytes > MAX_EXTERNAL_PAYLOAD_BYTES
        || maximum_transaction_components != 1
        || !(1..=100).contains(&required_battery_percent)
        || retry_limit > MAX_RETRY_LIMIT
        || !(1..=MAX_APPLY_TIMEOUT_MS).contains(&apply_timeout_ms)
        || !(1..=MAX_RESET_TIMEOUT_MS).contains(&reset_timeout_ms)
    {
        return Err(Error::Limits);
    }
    for digest_offset in (88..408).step_by(32) {
        digest_nonzero(bytes, digest_offset, Error::DigestZero)?;
    }
    if !manifest_id_valid(bytes) {
        return Err(Error::ManifestId);
    }
    if bytes[448..HEADER_BYTES].iter().any(|byte| *byte != 0) {
        return Err(Error::Reserved);
    }
    let body_sha256 = read_array(bytes, 376)?;
    if sha256(&bytes[HEADER_BYTES..]) != body_sha256 {
        return Err(Error::BodyDigest);
    }
    let bundle = Bundle {
        raw: bytes,
        manifest_version,
        profile,
        flags,
        component_count,
        dependency_count,
        maximum_external_payload_bytes,
        maximum_transaction_components,
        required_battery_percent,
        retry_limit,
        apply_timeout_ms,
        reset_timeout_ms,
        body_sha256,
    };

    let mut previous_phase = 0u16;
    let mut previous_id = 0u32;
    let mut expected_dependency_start = 0u32;
    let mut seen_phase_mask = 0u64;
    for index in 0..component_count as usize {
        let component = bundle.component(index)?;
        if index > 0
            && (component.phase < previous_phase
                || (component.phase == previous_phase && component.component_id <= previous_id))
        {
            return Err(Error::ComponentOrder);
        }
        for earlier in 0..index {
            let item = bundle.component(earlier)?;
            if item.component_id == component.component_id {
                return Err(Error::ComponentId);
            }
            if item.resource_guid == component.resource_guid
                && item.hardware_instance == component.hardware_instance
            {
                return Err(Error::ComponentGuid);
            }
        }
        if component.dependency_start != expected_dependency_start {
            return Err(Error::DependencyLayout);
        }
        expected_dependency_start = expected_dependency_start
            .checked_add(component.dependency_count as u32)
            .ok_or(Error::DependencyLayout)?;
        if expected_dependency_start > dependency_count {
            return Err(Error::DependencyLayout);
        }
        if component.external_payload_bytes > maximum_external_payload_bytes {
            return Err(Error::ComponentPayloadSize);
        }
        if component.phase as usize >= MAX_COMPONENTS {
            return Err(Error::PhaseOrder);
        }
        seen_phase_mask |= 1u64 << component.phase;
        previous_phase = component.phase;
        previous_id = component.component_id;
    }
    if expected_dependency_start != dependency_count {
        return Err(Error::DependencyLayout);
    }
    let highest_phase = previous_phase;
    let expected_mask = (1u64 << (highest_phase as u32 + 1)) - 1;
    if seen_phase_mask != expected_mask {
        return Err(Error::PhaseOrder);
    }

    for index in 0..dependency_count as usize {
        let dependency = bundle.dependency(index)?;
        let source = component_by_id(&bundle, dependency.component_id)?;
        let required = component_by_id(&bundle, dependency.required_component_id)?;
        if source.component_id == required.component_id {
            return Err(Error::DependencyId);
        }
        let start = source.dependency_start as usize;
        let end = start + source.dependency_count as usize;
        if !(start..end).contains(&index) {
            return Err(Error::DependencyLayout);
        }
        if index > start {
            let previous = bundle.dependency(index - 1)?;
            if previous.required_component_id >= dependency.required_component_id {
                return Err(Error::DependencyOrder);
            }
        }
        if dependency.minimum_version != required.target_version {
            return Err(Error::DependencyVersion);
        }
        if required.phase >= source.phase {
            return Err(Error::DependencyPhase);
        }
    }
    Ok(bundle)
}

fn versions_match(bundle: &Bundle<'_>, observed: &[ObservedVersion]) -> Result<bool, Error> {
    if observed.len() != bundle.component_count as usize {
        return Ok(false);
    }
    for (index, actual) in observed.iter().enumerate() {
        let expected = bundle.component(index)?;
        if actual.component_id != expected.component_id
            || actual.version != expected.current_version
        {
            return Ok(false);
        }
    }
    Ok(true)
}

fn external_payload_bytes(bundle: &Bundle<'_>) -> Result<u64, Error> {
    let mut total = 0u64;
    for index in 0..bundle.component_count as usize {
        total = total
            .checked_add(bundle.component(index)?.external_payload_bytes)
            .ok_or(Error::ActivationStagingCapacity)?;
    }
    Ok(total)
}

pub fn activation_error(
    bundle: &Bundle<'_>,
    context: &ActivationContext<'_>,
) -> Result<Option<Error>, Error> {
    let result = if !context.outer_signature_verified {
        Some(Error::ActivationOuterSignature)
    } else if context.outer_role != OUTER_ROLE_FIRMWARE_MANIFEST {
        Some(Error::ActivationOuterRole)
    } else if context.outer_version != bundle.manifest_version {
        Some(Error::ActivationOuterVersion)
    } else if context.outer_payload_sha256 != sha256(bundle.raw) {
        Some(Error::ActivationOuterPayloadDigest)
    } else if context.outer_file_sha256 != context.expected_outer_file_sha256 {
        Some(Error::ActivationOuterFileDigest)
    } else if !context.manifest_signature_verified {
        Some(Error::ActivationManifestSignature)
    } else if !context.package_signature_verified {
        Some(Error::ActivationPackageSignature)
    } else if !context.vendor_signatures_verified {
        Some(Error::ActivationVendorSignature)
    } else if !context.target_profile_verified {
        Some(Error::ActivationTargetProfile)
    } else if !context.hardware_inventory_observed {
        Some(Error::ActivationHardwareInventory)
    } else if !context.exact_device_identities_verified {
        Some(Error::ActivationDeviceIdentity)
    } else if !context.current_versions_observed
        || !versions_match(bundle, context.observed_versions)?
    {
        Some(Error::ActivationCurrentVersions)
    } else if !context.transport_support_verified {
        Some(Error::ActivationTransportSupport)
    } else if !context.firmware_service_inventory_verified {
        Some(Error::ActivationFirmwareServices)
    } else if !context.updater_plugins_verified {
        Some(Error::ActivationUpdaterPlugins)
    } else if !context.plugin_authority_granted {
        Some(Error::ActivationPluginAuthority)
    } else if !context.external_payloads_present {
        Some(Error::ActivationExternalPayloads)
    } else if !context.payload_digests_verified {
        Some(Error::ActivationPayloadDigests)
    } else if !context.license_policy_satisfied {
        Some(Error::ActivationLicensePolicy)
    } else if !context.redistribution_authorized {
        Some(Error::ActivationRedistribution)
    } else if !context.revocation_state_authenticated {
        Some(Error::ActivationRevocationState)
    } else if !context.no_components_revoked {
        Some(Error::ActivationComponentRevoked)
    } else if !context.anti_rollback_state_authenticated {
        Some(Error::ActivationAntiRollback)
    } else if !context.recovery_ready {
        Some(Error::ActivationRecovery)
    } else if !context.recovery_backup_verified {
        Some(Error::ActivationRecoveryBackup)
    } else if !context.protected_staging_ready {
        Some(Error::ActivationStaging)
    } else if context.staging_capacity_bytes < external_payload_bytes(bundle)? {
        Some(Error::ActivationStagingCapacity)
    } else if !context.stable_power {
        Some(Error::ActivationPower)
    } else if !context.ac_power_present {
        Some(Error::ActivationAcPower)
    } else if context.battery_percent < bundle.required_battery_percent {
        Some(Error::ActivationBattery)
    } else if !context.transaction_journal_ready {
        Some(Error::ActivationTransactionJournal)
    } else if !context.quiescence_ready {
        Some(Error::ActivationQuiescence)
    } else if !context.storage_guard_ready {
        Some(Error::ActivationStorageGuard)
    } else if !context.suspend_shutdown_guard_ready {
        Some(Error::ActivationSuspendShutdownGuard)
    } else if !context.reset_authorized {
        Some(Error::ActivationResetAuthority)
    } else if !context.reboot_authorized {
        Some(Error::ActivationRebootAuthority)
    } else if !context.user_confirmed {
        Some(Error::ActivationUserConfirmation)
    } else if !context.physical_presence_verified {
        Some(Error::ActivationPhysicalPresence)
    } else if !context.post_reset_verifier_ready {
        Some(Error::ActivationPostResetVerifier)
    } else if !context.receipt_storage_ready {
        Some(Error::ActivationReceiptStorage)
    } else if !context.firmware_change_authorized {
        Some(Error::ActivationFirmwareChangeAuthority)
    } else if !context.qualification_only {
        Some(Error::ActivationNotQualificationOnly)
    } else if context.live_firmware_call_requested {
        Some(Error::ActivationLiveFirmwareCallRequested)
    } else if context.driver_load_requested {
        Some(Error::ActivationDriverLoadRequested)
    } else if context.physical_media_write_requested {
        Some(Error::ActivationPhysicalMediaWriteRequested)
    } else if context.firmware_mutation_requested {
        Some(Error::ActivationFirmwareMutationRequested)
    } else {
        None
    };
    Ok(result)
}

pub fn authorize_dry_run_plan(
    bundle: &Bundle<'_>,
    context: &ActivationContext<'_>,
) -> Result<DryRunPlan, Error> {
    if let Some(error) = activation_error(bundle, context)? {
        return Err(error);
    }
    Ok(DryRunPlan {
        component_count: bundle.component_count,
        maximum_parallel_components: 1,
        external_payload_bytes: external_payload_bytes(bundle)?,
        reset_required: true,
        qualification_only: true,
    })
}

pub fn verify_post_reset(
    bundle: &Bundle<'_>,
    records: &[PostResetRecord],
    qualification_only: bool,
) -> Result<(), Error> {
    if !qualification_only {
        return Err(Error::PostResetNotQualificationOnly);
    }
    if records.len() != bundle.component_count as usize {
        return Err(Error::PostResetRecordCount);
    }
    for (index, record) in records.iter().enumerate() {
        let component = bundle.component(index)?;
        if record.component_id != component.component_id {
            return Err(Error::PostResetRecordOrder);
        }
        if record.resource_guid != component.resource_guid {
            return Err(Error::PostResetResourceIdentity);
        }
        if record.hardware_instance != component.hardware_instance {
            return Err(Error::PostResetHardwareInstance);
        }
        if record.observed_version != component.target_version {
            return Err(Error::PostResetVersion);
        }
        if record.last_attempt_version != component.target_version {
            return Err(Error::PostResetLastAttemptVersion);
        }
        if record.last_attempt_status != EXPECTED_LAST_ATTEMPT_SUCCESS {
            return Err(Error::PostResetLastAttemptStatus);
        }
        if !record.reenumerated {
            return Err(Error::PostResetReenumeration);
        }
        if !record.self_test_passed {
            return Err(Error::PostResetSelfTest);
        }
        if !record.recovery_intact {
            return Err(Error::PostResetRecovery);
        }
        if !record.receipt_persisted {
            return Err(Error::PostResetReceipt);
        }
        if !record.boot_loop_prevented {
            return Err(Error::PostResetBootLoopGuard);
        }
        if !record.state_committed {
            return Err(Error::PostResetStateCommit);
        }
        if !record.driver_rebound_after_validation {
            return Err(Error::PostResetDriverRebind);
        }
    }
    Ok(())
}

#[cfg(test)]
mod tests {
    extern crate std;

    use super::*;
    use std::vec;

    fn write_u16(bytes: &mut [u8], offset: usize, value: u16) {
        bytes[offset..offset + 2].copy_from_slice(&value.to_le_bytes());
    }

    fn write_u32(bytes: &mut [u8], offset: usize, value: u32) {
        bytes[offset..offset + 4].copy_from_slice(&value.to_le_bytes());
    }

    fn write_u64(bytes: &mut [u8], offset: usize, value: u64) {
        bytes[offset..offset + 8].copy_from_slice(&value.to_le_bytes());
    }

    fn fixture() -> std::vec::Vec<u8> {
        let mut bytes = vec![0u8; HEADER_BYTES + COMPONENT_RECORD_BYTES];
        bytes[..8].copy_from_slice(&MAGIC);
        write_u16(&mut bytes, 8, MAJOR_VERSION);
        write_u16(&mut bytes, 10, MINOR_VERSION);
        write_u16(&mut bytes, 12, HEADER_BYTES as u16);
        write_u16(&mut bytes, 14, COMPONENT_RECORD_BYTES as u16);
        write_u16(&mut bytes, 16, DEPENDENCY_RECORD_BYTES as u16);
        write_u16(&mut bytes, 18, PROFILE_SYNTHETIC_QUALIFICATION);
        write_u32(&mut bytes, 20, REQUIRED_FLAGS);
        write_u64(&mut bytes, 24, 1);
        write_u32(&mut bytes, 32, 1);
        write_u64(&mut bytes, 40, HEADER_BYTES as u64);
        write_u64(
            &mut bytes,
            48,
            (HEADER_BYTES + COMPONENT_RECORD_BYTES) as u64,
        );
        let byte_len = bytes.len() as u64;
        write_u64(&mut bytes, 56, byte_len);
        write_u64(&mut bytes, 64, MAX_EXTERNAL_PAYLOAD_BYTES);
        write_u32(&mut bytes, 72, 1);
        write_u16(&mut bytes, 76, 80);
        write_u16(&mut bytes, 78, 1);
        write_u32(&mut bytes, 80, 300_000);
        write_u32(&mut bytes, 84, 300_000);
        for offset in (88..376).step_by(32) {
            bytes[offset..offset + 32].fill(1);
        }
        bytes[408..423].copy_from_slice(b"PFWM1-RUST-TEST");
        let offset = HEADER_BYTES;
        write_u32(&mut bytes, offset, 1);
        write_u16(&mut bytes, offset + 4, KIND_PLATFORM_FIRMWARE);
        write_u16(&mut bytes, offset + 6, TRANSPORT_UEFI_CAPSULE_ESRT);
        write_u32(&mut bytes, offset + 16, COMPONENT_REQUIRED_FLAGS);
        bytes[offset + 24..offset + 40].fill(2);
        write_u64(&mut bytes, offset + 40, 1);
        write_u64(&mut bytes, offset + 48, 10);
        write_u64(&mut bytes, offset + 56, 11);
        write_u64(&mut bytes, offset + 64, 10);
        write_u64(&mut bytes, offset + 72, 10);
        write_u64(&mut bytes, offset + 80, 10);
        write_u64(&mut bytes, offset + 88, 4096);
        bytes[offset + 96..offset + COMPONENT_RECORD_BYTES].fill(3);
        let body = sha256(&bytes[HEADER_BYTES..]);
        bytes[376..408].copy_from_slice(&body);
        bytes
    }

    fn observed(bundle: &Bundle<'_>) -> std::vec::Vec<ObservedVersion> {
        (0..bundle.component_count as usize)
            .map(|index| {
                let item = bundle.component(index).unwrap();
                ObservedVersion {
                    component_id: item.component_id,
                    version: item.current_version,
                }
            })
            .collect()
    }

    #[test]
    fn parses_fixed_manifest_without_allocation() {
        let bytes = fixture();
        let bundle = parse(&bytes).unwrap();
        assert_eq!(bundle.component_count, 1);
        assert_eq!(bundle.dependency_count, 0);
        assert_eq!(bundle.component(0).unwrap().target_version, 11);
    }

    #[test]
    fn rejects_digest_identity_and_floor_substitution() {
        let mut bytes = fixture();
        bytes[376] ^= 1;
        assert_eq!(parse(&bytes), Err(Error::BodyDigest));

        let mut bytes = fixture();
        bytes[HEADER_BYTES + 24..HEADER_BYTES + 40].fill(0);
        let body = sha256(&bytes[HEADER_BYTES..]);
        bytes[376..408].copy_from_slice(&body);
        assert_eq!(parse(&bytes), Err(Error::ComponentGuid));

        let mut bytes = fixture();
        write_u64(&mut bytes, HEADER_BYTES + 72, 12);
        let body = sha256(&bytes[HEADER_BYTES..]);
        bytes[376..408].copy_from_slice(&body);
        assert_eq!(parse(&bytes), Err(Error::ComponentVersions));
    }

    #[test]
    fn development_context_fails_at_outer_signature() {
        let bytes = fixture();
        let bundle = parse(&bytes).unwrap();
        let versions = observed(&bundle);
        let context = ActivationContext::development(&bundle, &versions);
        assert_eq!(
            authorize_dry_run_plan(&bundle, &context),
            Err(Error::ActivationOuterSignature)
        );
    }

    #[test]
    fn qualified_context_only_returns_dry_run_plan() {
        let bytes = fixture();
        let bundle = parse(&bytes).unwrap();
        let versions = observed(&bundle);
        let context = ActivationContext::synthetic_qualified(&bundle, &versions);
        let plan = authorize_dry_run_plan(&bundle, &context).unwrap();
        assert!(plan.qualification_only);
        assert_eq!(plan.maximum_parallel_components, 1);
        assert_eq!(plan.external_payload_bytes, 4096);
    }

    #[test]
    fn post_reset_rebind_requires_prior_validation() {
        let bytes = fixture();
        let bundle = parse(&bytes).unwrap();
        let component = bundle.component(0).unwrap();
        let mut record = PostResetRecord {
            component_id: component.component_id,
            resource_guid: component.resource_guid,
            hardware_instance: component.hardware_instance,
            observed_version: component.target_version,
            last_attempt_version: component.target_version,
            last_attempt_status: 0,
            reenumerated: true,
            self_test_passed: true,
            recovery_intact: true,
            receipt_persisted: true,
            boot_loop_prevented: true,
            state_committed: true,
            driver_rebound_after_validation: true,
        };
        verify_post_reset(&bundle, &[record], true).unwrap();
        record.driver_rebound_after_validation = false;
        assert_eq!(
            verify_post_reset(&bundle, &[record], true),
            Err(Error::PostResetDriverRebind)
        );
    }
}
