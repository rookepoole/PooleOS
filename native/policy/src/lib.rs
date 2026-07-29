#![no_std]
#![deny(warnings)]

use sha2::{Digest, Sha256};

pub const CONTRACT_ID: &str = "PPOL1";
pub const MAGIC: [u8; 8] = *b"PPOL1\0\0\0";
pub const MAJOR_VERSION: u16 = 1;
pub const MINOR_VERSION: u16 = 0;
pub const HEADER_BYTES: usize = 512;
pub const MODE_RECORD_BYTES: usize = 128;
pub const CAPABILITY_RECORD_BYTES: usize = 64;
pub const MAX_BUNDLE_BYTES: usize = 64 * 1024;
pub const MAX_CAPABILITY_RULES: usize = 256;
pub const MODE_COUNT: usize = 6;
pub const OUTER_ROLE_POLICY_BUNDLE: u32 = 7;
pub const PROFILE_SYNTHETIC_QUALIFICATION: u16 = 1;

pub const MODE_NORMAL: u16 = 1;
pub const MODE_SAFE: u16 = 2;
pub const MODE_PREVIOUS: u16 = 3;
pub const MODE_RECOVERY: u16 = 4;
pub const MODE_DIAGNOSTIC: u16 = 5;
pub const MODE_FIRMWARE: u16 = 6;
pub const ALL_MODE_MASK: u32 = (1 << MODE_COUNT) - 1;
pub const PINIT_MODE_MASK: u32 = (1 << (MODE_NORMAL - 1))
    | (1 << (MODE_SAFE - 1))
    | (1 << (MODE_PREVIOUS - 1))
    | (1 << (MODE_DIAGNOSTIC - 1));

pub const REQUIRED_FLAGS: u32 = (1 << 22) - 1;
pub const MODE_FLAG_DEFAULT_DENY: u16 = 1 << 0;
pub const MODE_FLAG_AUDIT_REQUIRED: u16 = 1 << 1;
pub const MODE_FLAG_RECEIPT_REQUIRED: u16 = 1 << 2;
pub const MODE_FLAG_QUALIFICATION_ONLY: u16 = 1 << 3;
pub const MODE_FLAG_SAFE_FLOOR: u16 = 1 << 4;
pub const MODE_FLAG_RECOVERY_FLOOR: u16 = 1 << 5;
pub const MODE_FLAG_DISABLE_PDC: u16 = 1 << 6;
pub const MODE_FLAG_RECOVERY_INDEPENDENT: u16 = 1 << 7;
pub const MODE_FLAG_PHYSICAL_PRESENCE: u16 = 1 << 8;
pub const MODE_FLAG_SEPARATE_AUTHORITY: u16 = 1 << 9;
pub const MODE_BASE_FLAGS: u16 = MODE_FLAG_DEFAULT_DENY
    | MODE_FLAG_AUDIT_REQUIRED
    | MODE_FLAG_RECEIPT_REQUIRED
    | MODE_FLAG_QUALIFICATION_ONLY;
pub const MODE_KNOWN_FLAGS: u16 = (1 << 10) - 1;

pub const EFFECT_AUDIT: u64 = 1 << 0;
pub const EFFECT_READ_STATE: u64 = 1 << 1;
pub const EFFECT_WRITE_VOLATILE: u64 = 1 << 2;
pub const EFFECT_WRITE_PERSISTENT: u64 = 1 << 3;
pub const EFFECT_EXECUTE: u64 = 1 << 4;
pub const EFFECT_IPC: u64 = 1 << 5;
pub const EFFECT_NETWORK: u64 = 1 << 6;
pub const EFFECT_DEVICE_IO: u64 = 1 << 7;
pub const EFFECT_DMA: u64 = 1 << 8;
pub const EFFECT_DEBUG: u64 = 1 << 9;
pub const EFFECT_PDC_COMPUTE: u64 = 1 << 10;
pub const EFFECT_PDC_ACTUATE: u64 = 1 << 11;
pub const EFFECT_UPDATE: u64 = 1 << 12;
pub const EFFECT_FIRMWARE: u64 = 1 << 13;
pub const EFFECT_SECRET: u64 = 1 << 14;
pub const EFFECT_POWER: u64 = 1 << 15;
pub const KNOWN_EFFECTS: u64 = (1 << 16) - 1;
pub const CAPABILITY_EFFECT_CEILING: u64 =
    EFFECT_AUDIT | EFFECT_READ_STATE | EFFECT_WRITE_VOLATILE | EFFECT_EXECUTE | EFFECT_IPC;

pub const EVIDENCE_PHYSICAL_PRESENCE: u64 = 1 << 12;
pub const EVIDENCE_SEPARATE_AUTHORITY: u64 = 1 << 13;
pub const KNOWN_EVIDENCE: u64 = (1 << 18) - 1;
pub const BASE_EVIDENCE: u64 =
    KNOWN_EVIDENCE & !(EVIDENCE_PHYSICAL_PRESENCE | EVIDENCE_SEPARATE_AUTHORITY);
pub const ARTIFACT_ROLE_MASK: u32 = (1 << 2) | (1 << 3) | (1 << 4) | (1 << 5) | (1 << 6);
pub const KNOWN_RIGHTS: u64 = (1 << 5) - 1;
pub const KNOWN_CAPABILITY_FLAGS: u32 = (1 << 4) - 1;
pub const REQUIRED_CAPABILITY_FLAGS: u32 = (1 << 0) | (1 << 3);
pub const KNOWN_AUDIT_EVENTS: u64 = (1 << 6) - 1;
pub const SAFE_EFFECT_FLOOR: u64 = EFFECT_AUDIT
    | EFFECT_READ_STATE
    | EFFECT_WRITE_VOLATILE
    | EFFECT_EXECUTE
    | EFFECT_IPC
    | EFFECT_DEVICE_IO;
pub const RECOVERY_EFFECT_FLOOR: u64 = SAFE_EFFECT_FLOOR | EFFECT_WRITE_PERSISTENT | EFFECT_POWER;

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum Error {
    Truncated,
    Oversized,
    Magic,
    Version,
    RecordSize,
    Profile,
    Flags,
    VersionFloor,
    Counts,
    RequiredModes,
    TableLayout,
    TrailingBytes,
    Limits,
    DefaultCeiling,
    Digest,
    BodyDigest,
    PolicyId,
    Reserved,
    ModeOrder,
    ModeFlags,
    ModeReserved,
    ModeCapabilityCount,
    ModeEffects,
    ModeProhibitedEffects,
    ModeEvidence,
    ModeResourceCeiling,
    ModeCapabilityFlags,
    ModeRights,
    ModeArtifacts,
    ModeTransitions,
    ModeAudit,
    SafeFloor,
    RecoveryFloor,
    FirmwareBoundary,
    CapabilityOrder,
    CapabilityParent,
    CapabilityRoute,
    CapabilityDeclaredRights,
    CapabilityCeilingRights,
    CapabilityDeclaredFlags,
    CapabilityCeilingFlags,
    CapabilityRevokeGroup,
    CapabilityModes,
    CapabilityEffects,
    CapabilityAvailability,
    CapabilityGeneration,
    CapabilityParentAttenuation,
    PinitParse,
    PinitDigest,
    PinitCapabilityCount,
    PinitCapabilityRoute,
    PinitCapabilityAmplification,
    PinitCapabilityEffects,
    ActivationOuterSignature,
    ActivationOuterRole,
    ActivationOuterVersion,
    ActivationOuterPayloadDigest,
    ActivationOuterFileDigest,
    ActivationPolicySignature,
    ActivationManifestSignature,
    ActivationArtifactSignatures,
    ActivationTargetProfile,
    ActivationInitialSystemDigest,
    ActivationRecoveryDigest,
    ActivationSymbolsDigest,
    ActivationMicrocodeDigest,
    ActivationFirmwareDigest,
    ActivationTrustPolicy,
    ActivationRevocationState,
    ActivationRollbackState,
    ActivationAuditSchema,
    ActivationInnerContracts,
    ActivationInitialSystemCrossBinding,
    ActivationKernelAbi,
    ActivationPbp,
    ActivationMode,
    ActivationModeAuthority,
    ActivationTransitionAuthority,
    ActivationCapabilityAllocator,
    ActivationResourceBroker,
    ActivationAuditSink,
    ActivationReceiptStore,
    ActivationPhysicalPresence,
    ActivationSeparateAuthority,
    ActivationCapability,
    ActivationCapabilityMode,
    ActivationCapabilityRevoked,
    ActivationGeneration,
    ActivationIssuedRights,
    ActivationRequestedRights,
    ActivationRequestedEffects,
    ActivationNotQualificationOnly,
    ActivationLiveExecutionRequested,
    ActivationPersistentWriteRequested,
    ActivationFirmwareCallRequested,
    ActivationDriverLoadRequested,
    ActivationPhysicalMediaWriteRequested,
    ActivationStateMutationRequested,
    ReceiptNotQualificationOnly,
    ReceiptPolicyDigest,
    ReceiptMode,
    ReceiptCapability,
    ReceiptRights,
    ReceiptEffects,
    ReceiptGeneration,
    ReceiptRevocationEpoch,
    ReceiptAuditSequence,
    ReceiptNotDurable,
    ReceiptDecisionId,
}

impl Error {
    pub const fn code(self) -> &'static str {
        match self {
            Self::Truncated => "ppol_truncated",
            Self::Oversized => "ppol_oversized",
            Self::Magic => "ppol_magic",
            Self::Version => "ppol_version",
            Self::RecordSize => "ppol_record_size",
            Self::Profile => "ppol_profile",
            Self::Flags => "ppol_flags",
            Self::VersionFloor => "ppol_version_floor",
            Self::Counts => "ppol_counts",
            Self::RequiredModes => "ppol_required_modes",
            Self::TableLayout => "ppol_table_layout",
            Self::TrailingBytes => "ppol_trailing_bytes",
            Self::Limits => "ppol_limits",
            Self::DefaultCeiling => "ppol_default_ceiling",
            Self::Digest => "ppol_digest",
            Self::BodyDigest => "ppol_body_digest",
            Self::PolicyId => "ppol_policy_id",
            Self::Reserved => "ppol_reserved",
            Self::ModeOrder => "ppol_mode_order",
            Self::ModeFlags => "ppol_mode_flags",
            Self::ModeReserved => "ppol_mode_reserved",
            Self::ModeCapabilityCount => "ppol_mode_capability_count",
            Self::ModeEffects => "ppol_mode_effects",
            Self::ModeProhibitedEffects => "ppol_mode_prohibited_effects",
            Self::ModeEvidence => "ppol_mode_evidence",
            Self::ModeResourceCeiling => "ppol_mode_resource_ceiling",
            Self::ModeCapabilityFlags => "ppol_mode_capability_flags",
            Self::ModeRights => "ppol_mode_rights",
            Self::ModeArtifacts => "ppol_mode_artifacts",
            Self::ModeTransitions => "ppol_mode_transitions",
            Self::ModeAudit => "ppol_mode_audit",
            Self::SafeFloor => "ppol_safe_floor",
            Self::RecoveryFloor => "ppol_recovery_floor",
            Self::FirmwareBoundary => "ppol_firmware_boundary",
            Self::CapabilityOrder => "ppol_capability_order",
            Self::CapabilityParent => "ppol_capability_parent",
            Self::CapabilityRoute => "ppol_capability_route",
            Self::CapabilityDeclaredRights => "ppol_capability_declared_rights",
            Self::CapabilityCeilingRights => "ppol_capability_ceiling_rights",
            Self::CapabilityDeclaredFlags => "ppol_capability_declared_flags",
            Self::CapabilityCeilingFlags => "ppol_capability_ceiling_flags",
            Self::CapabilityRevokeGroup => "ppol_capability_revoke_group",
            Self::CapabilityModes => "ppol_capability_modes",
            Self::CapabilityEffects => "ppol_capability_effects",
            Self::CapabilityAvailability => "ppol_capability_availability",
            Self::CapabilityGeneration => "ppol_capability_generation",
            Self::CapabilityParentAttenuation => "ppol_capability_parent_attenuation",
            Self::PinitParse => "ppol_pinit_parse",
            Self::PinitDigest => "ppol_pinit_digest",
            Self::PinitCapabilityCount => "ppol_pinit_capability_count",
            Self::PinitCapabilityRoute => "ppol_pinit_capability_route",
            Self::PinitCapabilityAmplification => "ppol_pinit_capability_amplification",
            Self::PinitCapabilityEffects => "ppol_pinit_capability_effects",
            Self::ActivationOuterSignature => "ppol_activation_outer_signature",
            Self::ActivationOuterRole => "ppol_activation_outer_role",
            Self::ActivationOuterVersion => "ppol_activation_outer_version",
            Self::ActivationOuterPayloadDigest => "ppol_activation_outer_payload_digest",
            Self::ActivationOuterFileDigest => "ppol_activation_outer_file_digest",
            Self::ActivationPolicySignature => "ppol_activation_policy_signature",
            Self::ActivationManifestSignature => "ppol_activation_manifest_signature",
            Self::ActivationArtifactSignatures => "ppol_activation_artifact_signatures",
            Self::ActivationTargetProfile => "ppol_activation_target_profile",
            Self::ActivationInitialSystemDigest => "ppol_activation_initial_system_digest",
            Self::ActivationRecoveryDigest => "ppol_activation_recovery_digest",
            Self::ActivationSymbolsDigest => "ppol_activation_symbols_digest",
            Self::ActivationMicrocodeDigest => "ppol_activation_microcode_digest",
            Self::ActivationFirmwareDigest => "ppol_activation_firmware_digest",
            Self::ActivationTrustPolicy => "ppol_activation_trust_policy",
            Self::ActivationRevocationState => "ppol_activation_revocation_state",
            Self::ActivationRollbackState => "ppol_activation_rollback_state",
            Self::ActivationAuditSchema => "ppol_activation_audit_schema",
            Self::ActivationInnerContracts => "ppol_activation_inner_contracts",
            Self::ActivationInitialSystemCrossBinding => {
                "ppol_activation_initial_system_cross_binding"
            }
            Self::ActivationKernelAbi => "ppol_activation_kernel_abi",
            Self::ActivationPbp => "ppol_activation_pbp",
            Self::ActivationMode => "ppol_activation_mode",
            Self::ActivationModeAuthority => "ppol_activation_mode_authority",
            Self::ActivationTransitionAuthority => "ppol_activation_transition_authority",
            Self::ActivationCapabilityAllocator => "ppol_activation_capability_allocator",
            Self::ActivationResourceBroker => "ppol_activation_resource_broker",
            Self::ActivationAuditSink => "ppol_activation_audit_sink",
            Self::ActivationReceiptStore => "ppol_activation_receipt_store",
            Self::ActivationPhysicalPresence => "ppol_activation_physical_presence",
            Self::ActivationSeparateAuthority => "ppol_activation_separate_authority",
            Self::ActivationCapability => "ppol_activation_capability",
            Self::ActivationCapabilityMode => "ppol_activation_capability_mode",
            Self::ActivationCapabilityRevoked => "ppol_activation_capability_revoked",
            Self::ActivationGeneration => "ppol_activation_generation",
            Self::ActivationIssuedRights => "ppol_activation_issued_rights",
            Self::ActivationRequestedRights => "ppol_activation_requested_rights",
            Self::ActivationRequestedEffects => "ppol_activation_requested_effects",
            Self::ActivationNotQualificationOnly => "ppol_activation_not_qualification_only",
            Self::ActivationLiveExecutionRequested => "ppol_activation_live_execution_requested",
            Self::ActivationPersistentWriteRequested => {
                "ppol_activation_persistent_write_requested"
            }
            Self::ActivationFirmwareCallRequested => "ppol_activation_firmware_call_requested",
            Self::ActivationDriverLoadRequested => "ppol_activation_driver_load_requested",
            Self::ActivationPhysicalMediaWriteRequested => {
                "ppol_activation_physical_media_write_requested"
            }
            Self::ActivationStateMutationRequested => "ppol_activation_state_mutation_requested",
            Self::ReceiptNotQualificationOnly => "ppol_receipt_not_qualification_only",
            Self::ReceiptPolicyDigest => "ppol_receipt_policy_digest",
            Self::ReceiptMode => "ppol_receipt_mode",
            Self::ReceiptCapability => "ppol_receipt_capability",
            Self::ReceiptRights => "ppol_receipt_rights",
            Self::ReceiptEffects => "ppol_receipt_effects",
            Self::ReceiptGeneration => "ppol_receipt_generation",
            Self::ReceiptRevocationEpoch => "ppol_receipt_revocation_epoch",
            Self::ReceiptAuditSequence => "ppol_receipt_audit_sequence",
            Self::ReceiptNotDurable => "ppol_receipt_not_durable",
            Self::ReceiptDecisionId => "ppol_receipt_decision_id",
        }
    }
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct ModePolicy {
    pub mode: u16,
    pub flags: u16,
    pub allowed_capability_count: u16,
    pub allowed_effects: u64,
    pub required_evidence: u64,
    pub prohibited_effects: u64,
    pub max_memory_pages: u32,
    pub max_thread_slots: u32,
    pub max_endpoint_slots: u32,
    pub max_restarts: u32,
    pub max_pdc_units: u32,
    pub max_network_sessions: u32,
    pub allowed_capability_flags: u32,
    pub allowed_rights: u64,
    pub required_artifact_mask: u32,
    pub transition_mask: u32,
    pub audit_event_mask: u64,
    pub generation: u64,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct CapabilityRule {
    pub capability_id: u32,
    pub parent_id: u32,
    pub holder_service_id: u32,
    pub resource_id: u32,
    pub declared_rights: u64,
    pub ceiling_rights: u64,
    pub declared_flags: u32,
    pub ceiling_flags: u32,
    pub revoke_group: u32,
    pub allowed_mode_mask: u32,
    pub effect_mask: u64,
    pub availability: u16,
    pub max_derivations: u16,
    pub resource_generation: u32,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct Bundle<'a> {
    pub raw: &'a [u8],
    pub policy_version: u64,
    pub minimum_secure_version: u64,
    pub capability_count: u16,
    pub max_audit_receipts: u32,
    pub max_generation_advance: u32,
    pub default_effect_ceiling: u64,
    pub target_profile_sha256: [u8; 32],
    pub initial_system_sha256: [u8; 32],
    pub recovery_sha256: [u8; 32],
    pub symbols_sha256: [u8; 32],
    pub microcode_sha256: [u8; 32],
    pub firmware_sha256: [u8; 32],
    pub trust_policy_sha256: [u8; 32],
    pub revocation_schema_sha256: [u8; 32],
    pub rollback_schema_sha256: [u8; 32],
    pub audit_schema_sha256: [u8; 32],
    pub body_sha256: [u8; 32],
}

impl Bundle<'_> {
    pub fn mode(&self, index: usize) -> Result<ModePolicy, Error> {
        if index >= MODE_COUNT {
            return Err(Error::ModeOrder);
        }
        parse_mode(
            &self.raw[HEADER_BYTES + index * MODE_RECORD_BYTES
                ..HEADER_BYTES + (index + 1) * MODE_RECORD_BYTES],
            u16::try_from(index + 1).map_err(|_| Error::ModeOrder)?,
            self.capability_count,
        )
    }

    pub fn capability(&self, index: usize) -> Result<CapabilityRule, Error> {
        if index >= usize::from(self.capability_count) {
            return Err(Error::CapabilityOrder);
        }
        let offset =
            HEADER_BYTES + MODE_COUNT * MODE_RECORD_BYTES + index * CAPABILITY_RECORD_BYTES;
        parse_rule(
            &self.raw[offset..offset + CAPABILITY_RECORD_BYTES],
            u32::try_from(index + 1).map_err(|_| Error::CapabilityOrder)?,
            self,
        )
    }
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct ActivationContext {
    pub outer_role: u32,
    pub outer_version: u64,
    pub outer_payload_sha256: [u8; 32],
    pub outer_file_sha256: [u8; 32],
    pub expected_outer_file_sha256: [u8; 32],
    pub selected_mode: u16,
    pub previous_mode: u16,
    pub capability_id: u32,
    pub issued_rights: u64,
    pub requested_rights: u64,
    pub requested_effects: u64,
    pub issued_generation: u32,
    pub current_generation: u32,
    pub outer_signature_verified: bool,
    pub policy_signature_verified: bool,
    pub manifest_signature_verified: bool,
    pub artifact_signatures_verified: bool,
    pub target_profile_verified: bool,
    pub initial_system_digest_verified: bool,
    pub recovery_digest_verified: bool,
    pub symbols_digest_verified: bool,
    pub microcode_digest_verified: bool,
    pub firmware_digest_verified: bool,
    pub trust_policy_authenticated: bool,
    pub revocation_state_authenticated: bool,
    pub rollback_state_authenticated: bool,
    pub audit_schema_verified: bool,
    pub inner_contracts_verified: bool,
    pub initial_system_cross_bound: bool,
    pub kernel_abi_verified: bool,
    pub pbp_verified: bool,
    pub mode_authorized: bool,
    pub transition_authorized: bool,
    pub capability_allocator_ready: bool,
    pub resource_broker_ready: bool,
    pub audit_sink_ready: bool,
    pub receipt_store_ready: bool,
    pub physical_presence_verified: bool,
    pub separate_authority_verified: bool,
    pub capability_revoked: bool,
    pub qualification_only: bool,
    pub live_execution_requested: bool,
    pub persistent_write_requested: bool,
    pub firmware_call_requested: bool,
    pub driver_load_requested: bool,
    pub physical_media_write_requested: bool,
    pub state_mutation_requested: bool,
}

impl ActivationContext {
    pub fn synthetic_qualified(bundle: &Bundle<'_>, mode: u16) -> Result<Self, Error> {
        let selected = mode_policy(bundle, mode)?;
        let capability_id = if selected.allowed_capability_count == 0 {
            0
        } else {
            1
        };
        let rule = if capability_id == 0 {
            None
        } else {
            Some(bundle.capability(0)?)
        };
        let rights = rule.map_or(0, |item| item.ceiling_rights & selected.allowed_rights);
        let effects = rule.map_or(EFFECT_AUDIT, |item| {
            item.effect_mask & selected.allowed_effects
        });
        let generation = rule.map_or(0, |item| item.resource_generation);
        let digest = sha256(bundle.raw);
        Ok(Self {
            outer_role: OUTER_ROLE_POLICY_BUNDLE,
            outer_version: bundle.policy_version,
            outer_payload_sha256: digest,
            outer_file_sha256: digest,
            expected_outer_file_sha256: digest,
            selected_mode: mode,
            previous_mode: mode,
            capability_id,
            issued_rights: rights,
            requested_rights: rights,
            requested_effects: effects,
            issued_generation: generation,
            current_generation: generation,
            outer_signature_verified: true,
            policy_signature_verified: true,
            manifest_signature_verified: true,
            artifact_signatures_verified: true,
            target_profile_verified: true,
            initial_system_digest_verified: true,
            recovery_digest_verified: true,
            symbols_digest_verified: true,
            microcode_digest_verified: true,
            firmware_digest_verified: true,
            trust_policy_authenticated: true,
            revocation_state_authenticated: true,
            rollback_state_authenticated: true,
            audit_schema_verified: true,
            inner_contracts_verified: true,
            initial_system_cross_bound: true,
            kernel_abi_verified: true,
            pbp_verified: true,
            mode_authorized: true,
            transition_authorized: true,
            capability_allocator_ready: true,
            resource_broker_ready: true,
            audit_sink_ready: true,
            receipt_store_ready: true,
            physical_presence_verified: mode == MODE_FIRMWARE,
            separate_authority_verified: mode == MODE_FIRMWARE,
            capability_revoked: false,
            qualification_only: true,
            live_execution_requested: false,
            persistent_write_requested: false,
            firmware_call_requested: false,
            driver_load_requested: false,
            physical_media_write_requested: false,
            state_mutation_requested: false,
        })
    }

    pub fn development(bundle: &Bundle<'_>) -> Result<Self, Error> {
        let mut value = Self::synthetic_qualified(bundle, MODE_NORMAL)?;
        value.outer_signature_verified = false;
        value.policy_signature_verified = false;
        value.manifest_signature_verified = false;
        value.artifact_signatures_verified = false;
        value.target_profile_verified = false;
        value.trust_policy_authenticated = false;
        value.revocation_state_authenticated = false;
        value.rollback_state_authenticated = false;
        value.audit_schema_verified = false;
        value.inner_contracts_verified = false;
        value.initial_system_cross_bound = false;
        value.mode_authorized = false;
        value.transition_authorized = false;
        value.capability_allocator_ready = false;
        value.resource_broker_ready = false;
        value.audit_sink_ready = false;
        value.receipt_store_ready = false;
        Ok(value)
    }
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct DryRunDecision {
    pub policy_sha256: [u8; 32],
    pub mode: u16,
    pub capability_id: u32,
    pub effective_rights: u64,
    pub effective_effects: u64,
    pub mode_generation: u64,
    pub capability_generation: u32,
    pub allowed_capability_count: u16,
    pub audit_receipt_required: bool,
    pub qualification_only: bool,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct DecisionReceipt {
    pub policy_sha256: [u8; 32],
    pub mode: u16,
    pub capability_id: u32,
    pub effective_rights: u64,
    pub effective_effects: u64,
    pub mode_generation: u64,
    pub capability_generation: u32,
    pub revocation_epoch: u64,
    pub audit_sequence: u64,
    pub durable: bool,
    pub qualification_only: bool,
    pub decision_id: [u8; 32],
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

pub fn sha256(bytes: &[u8]) -> [u8; 32] {
    let value = Sha256::digest(bytes);
    let mut result = [0u8; 32];
    result.copy_from_slice(&value);
    result
}

fn read_digest(bytes: &[u8], offset: usize) -> Result<[u8; 32], Error> {
    let value = bytes.get(offset..offset + 32).ok_or(Error::Digest)?;
    if value.iter().all(|byte| *byte == 0) {
        return Err(Error::Digest);
    }
    let mut result = [0u8; 32];
    result.copy_from_slice(value);
    Ok(result)
}

fn all_zero(bytes: &[u8]) -> bool {
    bytes.iter().all(|byte| *byte == 0)
}

fn mode_bit(mode: u16) -> u32 {
    if !(MODE_NORMAL..=MODE_FIRMWARE).contains(&mode) {
        0
    } else {
        1 << (mode - 1)
    }
}

fn valid_policy_id(field: &[u8]) -> bool {
    let Some(end) = field.iter().position(|byte| *byte == 0) else {
        return false;
    };
    if end == 0 || end > 39 || !all_zero(&field[end..]) {
        return false;
    }
    field[..end].iter().enumerate().all(|(index, byte)| {
        byte.is_ascii_uppercase()
            || byte.is_ascii_digit()
            || (index > 0 && matches!(*byte, b'.' | b'_' | b'-'))
    })
}

fn parse_mode(record: &[u8], expected: u16, capability_count: u16) -> Result<ModePolicy, Error> {
    if record.len() != MODE_RECORD_BYTES {
        return Err(Error::Truncated);
    }
    let mode = read_u16(record, 0)?;
    let flags = read_u16(record, 2)?;
    let allowed_capability_count = read_u16(record, 4)?;
    if mode != expected {
        return Err(Error::ModeOrder);
    }
    if flags & !MODE_KNOWN_FLAGS != 0 || flags & MODE_BASE_FLAGS != MODE_BASE_FLAGS {
        return Err(Error::ModeFlags);
    }
    if read_u16(record, 6)? != 0 || !all_zero(&record[88..]) {
        return Err(Error::ModeReserved);
    }
    if allowed_capability_count > capability_count {
        return Err(Error::ModeCapabilityCount);
    }
    let allowed_effects = read_u64(record, 8)?;
    let required_evidence = read_u64(record, 16)?;
    let prohibited_effects = read_u64(record, 24)?;
    if allowed_effects == 0 || allowed_effects & !KNOWN_EFFECTS != 0 {
        return Err(Error::ModeEffects);
    }
    if prohibited_effects != KNOWN_EFFECTS ^ allowed_effects {
        return Err(Error::ModeProhibitedEffects);
    }
    let firmware_evidence = EVIDENCE_PHYSICAL_PRESENCE | EVIDENCE_SEPARATE_AUTHORITY;
    let expected_evidence = BASE_EVIDENCE
        | if mode == MODE_FIRMWARE {
            firmware_evidence
        } else {
            0
        };
    if required_evidence != expected_evidence {
        return Err(Error::ModeEvidence);
    }
    let max_memory_pages = read_u32(record, 32)?;
    let max_thread_slots = read_u32(record, 36)?;
    let max_endpoint_slots = read_u32(record, 40)?;
    let max_restarts = read_u32(record, 44)?;
    let max_pdc_units = read_u32(record, 48)?;
    let max_network_sessions = read_u32(record, 52)?;
    if max_memory_pages > 65_536
        || max_thread_slots > 1_024
        || max_endpoint_slots > 4_096
        || max_restarts > 1_024
        || max_pdc_units > 1_024
        || max_network_sessions > 4_096
    {
        return Err(Error::ModeResourceCeiling);
    }
    let allowed_capability_flags = read_u32(record, 56)?;
    let allowed_rights = u64::from(read_u32(record, 60)?);
    let required_artifact_mask = read_u32(record, 64)?;
    let transition_mask = read_u32(record, 68)?;
    let audit_event_mask = read_u64(record, 72)?;
    let generation = read_u64(record, 80)?;
    if allowed_capability_flags & !KNOWN_CAPABILITY_FLAGS != 0 {
        return Err(Error::ModeCapabilityFlags);
    }
    if allowed_rights & !KNOWN_RIGHTS != 0
        || (allowed_capability_count == 0) != (allowed_rights == 0)
    {
        return Err(Error::ModeRights);
    }
    if required_artifact_mask != ARTIFACT_ROLE_MASK {
        return Err(Error::ModeArtifacts);
    }
    if transition_mask == 0 || transition_mask & !ALL_MODE_MASK != 0 {
        return Err(Error::ModeTransitions);
    }
    if audit_event_mask != KNOWN_AUDIT_EVENTS || generation == 0 {
        return Err(Error::ModeAudit);
    }
    if mode == MODE_SAFE
        && (flags & (MODE_FLAG_SAFE_FLOOR | MODE_FLAG_DISABLE_PDC)
            != MODE_FLAG_SAFE_FLOOR | MODE_FLAG_DISABLE_PDC
            || allowed_effects & !SAFE_EFFECT_FLOOR != 0)
    {
        return Err(Error::SafeFloor);
    }
    if mode == MODE_RECOVERY
        && (flags
            & (MODE_FLAG_RECOVERY_FLOOR | MODE_FLAG_DISABLE_PDC | MODE_FLAG_RECOVERY_INDEPENDENT)
            != MODE_FLAG_RECOVERY_FLOOR | MODE_FLAG_DISABLE_PDC | MODE_FLAG_RECOVERY_INDEPENDENT
            || allowed_effects & !RECOVERY_EFFECT_FLOOR != 0
            || allowed_capability_count != 0
            || allowed_rights != 0)
    {
        return Err(Error::RecoveryFloor);
    }
    if mode == MODE_FIRMWARE
        && (flags
            & (MODE_FLAG_PHYSICAL_PRESENCE | MODE_FLAG_SEPARATE_AUTHORITY | MODE_FLAG_DISABLE_PDC)
            != MODE_FLAG_PHYSICAL_PRESENCE | MODE_FLAG_SEPARATE_AUTHORITY | MODE_FLAG_DISABLE_PDC
            || allowed_capability_count != 0
            || allowed_rights != 0)
    {
        return Err(Error::FirmwareBoundary);
    }
    if mode != MODE_FIRMWARE
        && flags & (MODE_FLAG_PHYSICAL_PRESENCE | MODE_FLAG_SEPARATE_AUTHORITY) != 0
    {
        return Err(Error::ModeFlags);
    }
    Ok(ModePolicy {
        mode,
        flags,
        allowed_capability_count,
        allowed_effects,
        required_evidence,
        prohibited_effects,
        max_memory_pages,
        max_thread_slots,
        max_endpoint_slots,
        max_restarts,
        max_pdc_units,
        max_network_sessions,
        allowed_capability_flags,
        allowed_rights,
        required_artifact_mask,
        transition_mask,
        audit_event_mask,
        generation,
    })
}

fn parse_rule(record: &[u8], expected: u32, bundle: &Bundle<'_>) -> Result<CapabilityRule, Error> {
    if record.len() != CAPABILITY_RECORD_BYTES {
        return Err(Error::Truncated);
    }
    let capability_id = read_u32(record, 0)?;
    let parent_id = read_u32(record, 4)?;
    let holder_service_id = read_u32(record, 8)?;
    let resource_id = read_u32(record, 12)?;
    if capability_id != expected {
        return Err(Error::CapabilityOrder);
    }
    if parent_id >= capability_id {
        return Err(Error::CapabilityParent);
    }
    if holder_service_id == 0 || resource_id == 0 {
        return Err(Error::CapabilityRoute);
    }
    let declared_rights = read_u64(record, 16)?;
    let ceiling_rights = read_u64(record, 24)?;
    if declared_rights == 0 || declared_rights & !KNOWN_RIGHTS != 0 {
        return Err(Error::CapabilityDeclaredRights);
    }
    if ceiling_rights == 0 || ceiling_rights & !declared_rights != 0 {
        return Err(Error::CapabilityCeilingRights);
    }
    let declared_flags = read_u32(record, 32)?;
    let ceiling_flags = read_u32(record, 36)?;
    let revoke_group = read_u32(record, 40)?;
    let allowed_mode_mask = read_u32(record, 44)?;
    if declared_flags & !KNOWN_CAPABILITY_FLAGS != 0
        || declared_flags & REQUIRED_CAPABILITY_FLAGS != REQUIRED_CAPABILITY_FLAGS
    {
        return Err(Error::CapabilityDeclaredFlags);
    }
    if ceiling_flags & !declared_flags != 0
        || ceiling_flags & REQUIRED_CAPABILITY_FLAGS != REQUIRED_CAPABILITY_FLAGS
    {
        return Err(Error::CapabilityCeilingFlags);
    }
    if revoke_group == 0 {
        return Err(Error::CapabilityRevokeGroup);
    }
    if allowed_mode_mask == 0
        || allowed_mode_mask & !ALL_MODE_MASK != 0
        || allowed_mode_mask & !PINIT_MODE_MASK != 0
    {
        return Err(Error::CapabilityModes);
    }
    let effect_mask = read_u64(record, 48)?;
    let availability = read_u16(record, 56)?;
    let max_derivations = read_u16(record, 58)?;
    let resource_generation = read_u32(record, 60)?;
    if effect_mask == 0 || effect_mask & !CAPABILITY_EFFECT_CEILING != 0 {
        return Err(Error::CapabilityEffects);
    }
    if !matches!(availability, 1 | 2) {
        return Err(Error::CapabilityAvailability);
    }
    if resource_generation == 0 {
        return Err(Error::CapabilityGeneration);
    }
    let result = CapabilityRule {
        capability_id,
        parent_id,
        holder_service_id,
        resource_id,
        declared_rights,
        ceiling_rights,
        declared_flags,
        ceiling_flags,
        revoke_group,
        allowed_mode_mask,
        effect_mask,
        availability,
        max_derivations,
        resource_generation,
    };
    if parent_id != 0 {
        let parent_index = usize::try_from(parent_id - 1).map_err(|_| Error::CapabilityParent)?;
        let parent = bundle.capability(parent_index)?;
        if ceiling_rights & !parent.ceiling_rights != 0
            || ceiling_flags & !parent.ceiling_flags != 0
            || allowed_mode_mask & !parent.allowed_mode_mask != 0
            || effect_mask & !parent.effect_mask != 0
        {
            return Err(Error::CapabilityParentAttenuation);
        }
    }
    Ok(result)
}

pub fn parse(data: &[u8]) -> Result<Bundle<'_>, Error> {
    if data.len() < HEADER_BYTES {
        return Err(Error::Truncated);
    }
    if data.len() > MAX_BUNDLE_BYTES {
        return Err(Error::Oversized);
    }
    if data[..8] != MAGIC {
        return Err(Error::Magic);
    }
    if read_u16(data, 8)? != MAJOR_VERSION || read_u16(data, 10)? != MINOR_VERSION {
        return Err(Error::Version);
    }
    if usize::from(read_u16(data, 12)?) != HEADER_BYTES
        || usize::from(read_u16(data, 14)?) != MODE_RECORD_BYTES
        || usize::from(read_u16(data, 16)?) != CAPABILITY_RECORD_BYTES
    {
        return Err(Error::RecordSize);
    }
    if read_u16(data, 18)? != PROFILE_SYNTHETIC_QUALIFICATION {
        return Err(Error::Profile);
    }
    if read_u32(data, 20)? != REQUIRED_FLAGS {
        return Err(Error::Flags);
    }
    let policy_version = read_u64(data, 24)?;
    let minimum_secure_version = read_u64(data, 32)?;
    if policy_version == 0 || minimum_secure_version == 0 || policy_version < minimum_secure_version
    {
        return Err(Error::VersionFloor);
    }
    let mode_count = usize::from(read_u16(data, 40)?);
    let capability_count = read_u16(data, 42)?;
    if mode_count != MODE_COUNT
        || capability_count == 0
        || usize::from(capability_count) > MAX_CAPABILITY_RULES
    {
        return Err(Error::Counts);
    }
    if read_u32(data, 44)? != ALL_MODE_MASK {
        return Err(Error::RequiredModes);
    }
    let mode_offset = usize::try_from(read_u64(data, 48)?).map_err(|_| Error::TableLayout)?;
    let capability_offset = usize::try_from(read_u64(data, 56)?).map_err(|_| Error::TableLayout)?;
    let total_bytes = usize::try_from(read_u64(data, 64)?).map_err(|_| Error::TableLayout)?;
    let expected_capability_offset = HEADER_BYTES + MODE_COUNT * MODE_RECORD_BYTES;
    let expected_total = expected_capability_offset
        .checked_add(usize::from(capability_count) * CAPABILITY_RECORD_BYTES)
        .ok_or(Error::TableLayout)?;
    if mode_offset != HEADER_BYTES || capability_offset != expected_capability_offset {
        return Err(Error::TableLayout);
    }
    if total_bytes > data.len() {
        return Err(Error::Truncated);
    }
    if total_bytes != expected_total {
        return Err(Error::TableLayout);
    }
    if data.len() > total_bytes {
        return Err(Error::TrailingBytes);
    }
    let max_audit_receipts = read_u32(data, 72)?;
    let max_generation_advance = read_u32(data, 76)?;
    let default_effect_ceiling = read_u64(data, 80)?;
    if !(1..=1_000_000).contains(&max_audit_receipts) || max_generation_advance != 1 {
        return Err(Error::Limits);
    }
    if default_effect_ceiling != KNOWN_EFFECTS || read_u64(data, 88)? != 0 {
        return Err(Error::DefaultCeiling);
    }
    let target_profile_sha256 = read_digest(data, 96)?;
    let initial_system_sha256 = read_digest(data, 128)?;
    let recovery_sha256 = read_digest(data, 160)?;
    let symbols_sha256 = read_digest(data, 192)?;
    let microcode_sha256 = read_digest(data, 224)?;
    let firmware_sha256 = read_digest(data, 256)?;
    let trust_policy_sha256 = read_digest(data, 288)?;
    let revocation_schema_sha256 = read_digest(data, 320)?;
    let rollback_schema_sha256 = read_digest(data, 352)?;
    let audit_schema_sha256 = read_digest(data, 384)?;
    let body_sha256 = read_digest(data, 416).map_err(|_| Error::BodyDigest)?;
    if sha256(&data[HEADER_BYTES..]) != body_sha256 {
        return Err(Error::BodyDigest);
    }
    if !valid_policy_id(&data[448..488]) {
        return Err(Error::PolicyId);
    }
    if !all_zero(&data[488..HEADER_BYTES]) {
        return Err(Error::Reserved);
    }
    let bundle = Bundle {
        raw: data,
        policy_version,
        minimum_secure_version,
        capability_count,
        max_audit_receipts,
        max_generation_advance,
        default_effect_ceiling,
        target_profile_sha256,
        initial_system_sha256,
        recovery_sha256,
        symbols_sha256,
        microcode_sha256,
        firmware_sha256,
        trust_policy_sha256,
        revocation_schema_sha256,
        rollback_schema_sha256,
        audit_schema_sha256,
        body_sha256,
    };
    for index in 0..MODE_COUNT {
        bundle.mode(index)?;
    }
    for index in 0..usize::from(capability_count) {
        bundle.capability(index)?;
    }
    for index in 0..MODE_COUNT {
        let mode = bundle.mode(index)?;
        let mut actual = 0u16;
        for rule_index in 0..usize::from(capability_count) {
            if bundle.capability(rule_index)?.allowed_mode_mask & mode_bit(mode.mode) != 0 {
                actual = actual.checked_add(1).ok_or(Error::ModeCapabilityCount)?;
            }
        }
        if actual != mode.allowed_capability_count {
            return Err(Error::ModeCapabilityCount);
        }
    }
    Ok(bundle)
}

fn pinit_resource_effects(rights: u64, kind: u16) -> u64 {
    let mut effects = 0;
    if kind == 5 {
        effects |= EFFECT_AUDIT;
    }
    if rights & (1 << 0) != 0 {
        effects |= EFFECT_READ_STATE;
    }
    if rights & (1 << 1) != 0 && kind != 5 {
        effects |= EFFECT_WRITE_VOLATILE;
    }
    if rights & (1 << 2) != 0 && kind == 2 {
        effects |= EFFECT_EXECUTE;
    }
    if rights & (1 << 2) != 0 && kind == 3 {
        effects |= EFFECT_IPC;
    }
    if effects == 0 { EFFECT_AUDIT } else { effects }
}

pub fn validate_initial_system(bundle: &Bundle<'_>, bytes: &[u8]) -> Result<(), Error> {
    let initial = poole_initial_system::parse(bytes).map_err(|_| Error::PinitParse)?;
    if sha256(bytes) != bundle.initial_system_sha256 {
        return Err(Error::PinitDigest);
    }
    if initial.capability_count != bundle.capability_count {
        return Err(Error::PinitCapabilityCount);
    }
    let resource_offset = usize::try_from(read_u32(bytes, 80)?).map_err(|_| Error::PinitParse)?;
    let capability_offset = usize::try_from(read_u32(bytes, 84)?).map_err(|_| Error::PinitParse)?;
    for index in 0..usize::from(bundle.capability_count) {
        let rule = bundle.capability(index)?;
        let offset = capability_offset + index * poole_initial_system::CAPABILITY_BYTES;
        let cap = bytes
            .get(offset..offset + poole_initial_system::CAPABILITY_BYTES)
            .ok_or(Error::PinitParse)?;
        let resource_id = read_u32(cap, 12)?;
        if resource_id == 0 || resource_id > u32::from(initial.resource_count) {
            return Err(Error::PinitCapabilityRoute);
        }
        let resource_index = usize::try_from(resource_id - 1).map_err(|_| Error::PinitParse)?;
        let resource_start =
            resource_offset + resource_index * poole_initial_system::RESOURCE_BYTES;
        let resource = bytes
            .get(resource_start..resource_start + poole_initial_system::RESOURCE_BYTES)
            .ok_or(Error::PinitParse)?;
        let expected = (
            read_u32(cap, 0)?,
            read_u32(cap, 4)?,
            read_u32(cap, 8)?,
            resource_id,
            read_u64(cap, 16)?,
            read_u32(cap, 24)?,
            read_u32(cap, 28)?,
            read_u16(cap, 38)?,
            read_u16(cap, 36)?,
            read_u32(resource, 40)?,
        );
        let actual = (
            rule.capability_id,
            rule.parent_id,
            rule.holder_service_id,
            rule.resource_id,
            rule.declared_rights,
            rule.declared_flags,
            rule.revoke_group,
            rule.availability,
            rule.max_derivations,
            rule.resource_generation,
        );
        if actual != expected {
            return Err(Error::PinitCapabilityRoute);
        }
        if rule.ceiling_rights & !expected.4 != 0 || rule.ceiling_flags & !expected.5 != 0 {
            return Err(Error::PinitCapabilityAmplification);
        }
        if rule.effect_mask != pinit_resource_effects(expected.4, read_u16(resource, 14)?) {
            return Err(Error::PinitCapabilityEffects);
        }
    }
    Ok(())
}

fn mode_policy(bundle: &Bundle<'_>, mode: u16) -> Result<ModePolicy, Error> {
    if !(MODE_NORMAL..=MODE_FIRMWARE).contains(&mode) {
        return Err(Error::ActivationMode);
    }
    bundle.mode(usize::from(mode - 1))
}

fn capability_rule(bundle: &Bundle<'_>, capability_id: u32) -> Result<CapabilityRule, Error> {
    if capability_id == 0 || capability_id > u32::from(bundle.capability_count) {
        return Err(Error::ActivationCapability);
    }
    bundle.capability(usize::try_from(capability_id - 1).map_err(|_| Error::ActivationCapability)?)
}

pub fn activation_error(bundle: &Bundle<'_>, context: &ActivationContext) -> Option<Error> {
    let expected_digest = sha256(bundle.raw);
    let checks = [
        (
            context.outer_signature_verified,
            Error::ActivationOuterSignature,
        ),
        (
            context.outer_role == OUTER_ROLE_POLICY_BUNDLE,
            Error::ActivationOuterRole,
        ),
        (
            context.outer_version == bundle.policy_version,
            Error::ActivationOuterVersion,
        ),
        (
            context.outer_payload_sha256 == expected_digest,
            Error::ActivationOuterPayloadDigest,
        ),
        (
            context.outer_file_sha256 == context.expected_outer_file_sha256,
            Error::ActivationOuterFileDigest,
        ),
        (
            context.policy_signature_verified,
            Error::ActivationPolicySignature,
        ),
        (
            context.manifest_signature_verified,
            Error::ActivationManifestSignature,
        ),
        (
            context.artifact_signatures_verified,
            Error::ActivationArtifactSignatures,
        ),
        (
            context.target_profile_verified,
            Error::ActivationTargetProfile,
        ),
        (
            context.initial_system_digest_verified,
            Error::ActivationInitialSystemDigest,
        ),
        (
            context.recovery_digest_verified,
            Error::ActivationRecoveryDigest,
        ),
        (
            context.symbols_digest_verified,
            Error::ActivationSymbolsDigest,
        ),
        (
            context.microcode_digest_verified,
            Error::ActivationMicrocodeDigest,
        ),
        (
            context.firmware_digest_verified,
            Error::ActivationFirmwareDigest,
        ),
        (
            context.trust_policy_authenticated,
            Error::ActivationTrustPolicy,
        ),
        (
            context.revocation_state_authenticated,
            Error::ActivationRevocationState,
        ),
        (
            context.rollback_state_authenticated,
            Error::ActivationRollbackState,
        ),
        (context.audit_schema_verified, Error::ActivationAuditSchema),
        (
            context.inner_contracts_verified,
            Error::ActivationInnerContracts,
        ),
        (
            context.initial_system_cross_bound,
            Error::ActivationInitialSystemCrossBinding,
        ),
        (context.kernel_abi_verified, Error::ActivationKernelAbi),
        (context.pbp_verified, Error::ActivationPbp),
    ];
    for (condition, error) in checks {
        if !condition {
            return Some(error);
        }
    }
    let Ok(mode) = mode_policy(bundle, context.selected_mode) else {
        return Some(Error::ActivationMode);
    };
    if !context.mode_authorized {
        return Some(Error::ActivationModeAuthority);
    }
    if !context.transition_authorized || mode.transition_mask & mode_bit(context.previous_mode) == 0
    {
        return Some(Error::ActivationTransitionAuthority);
    }
    for (condition, error) in [
        (
            context.capability_allocator_ready,
            Error::ActivationCapabilityAllocator,
        ),
        (
            context.resource_broker_ready,
            Error::ActivationResourceBroker,
        ),
        (context.audit_sink_ready, Error::ActivationAuditSink),
        (context.receipt_store_ready, Error::ActivationReceiptStore),
    ] {
        if !condition {
            return Some(error);
        }
    }
    if context.selected_mode == MODE_FIRMWARE && !context.physical_presence_verified {
        return Some(Error::ActivationPhysicalPresence);
    }
    if context.selected_mode == MODE_FIRMWARE && !context.separate_authority_verified {
        return Some(Error::ActivationSeparateAuthority);
    }
    if context.capability_id == 0 {
        if mode.allowed_capability_count != 0 {
            return Some(Error::ActivationCapability);
        }
        if context.capability_revoked {
            return Some(Error::ActivationCapabilityRevoked);
        }
        if context.issued_generation != 0 || context.current_generation != 0 {
            return Some(Error::ActivationGeneration);
        }
        if context.issued_rights != 0 || context.requested_rights != 0 {
            return Some(Error::ActivationIssuedRights);
        }
        if context.requested_effects == 0 || context.requested_effects & !mode.allowed_effects != 0
        {
            return Some(Error::ActivationRequestedEffects);
        }
    } else {
        let Ok(rule) = capability_rule(bundle, context.capability_id) else {
            return Some(Error::ActivationCapability);
        };
        if rule.allowed_mode_mask & mode_bit(context.selected_mode) == 0 {
            return Some(Error::ActivationCapabilityMode);
        }
        if context.capability_revoked {
            return Some(Error::ActivationCapabilityRevoked);
        }
        if context.issued_generation != rule.resource_generation
            || context.current_generation != rule.resource_generation
        {
            return Some(Error::ActivationGeneration);
        }
        let ceiling = rule.ceiling_rights & mode.allowed_rights;
        if context.issued_rights == 0 || context.issued_rights & !ceiling != 0 {
            return Some(Error::ActivationIssuedRights);
        }
        if context.requested_rights == 0 || context.requested_rights & !context.issued_rights != 0 {
            return Some(Error::ActivationRequestedRights);
        }
        if context.requested_effects == 0
            || context.requested_effects & !(rule.effect_mask & mode.allowed_effects) != 0
        {
            return Some(Error::ActivationRequestedEffects);
        }
    }
    for (condition, error) in [
        (
            context.qualification_only,
            Error::ActivationNotQualificationOnly,
        ),
        (
            !context.live_execution_requested,
            Error::ActivationLiveExecutionRequested,
        ),
        (
            !context.persistent_write_requested,
            Error::ActivationPersistentWriteRequested,
        ),
        (
            !context.firmware_call_requested,
            Error::ActivationFirmwareCallRequested,
        ),
        (
            !context.driver_load_requested,
            Error::ActivationDriverLoadRequested,
        ),
        (
            !context.physical_media_write_requested,
            Error::ActivationPhysicalMediaWriteRequested,
        ),
        (
            !context.state_mutation_requested,
            Error::ActivationStateMutationRequested,
        ),
    ] {
        if !condition {
            return Some(error);
        }
    }
    None
}

pub fn authorize_dry_run_decision(
    bundle: &Bundle<'_>,
    context: &ActivationContext,
) -> Result<DryRunDecision, Error> {
    if let Some(error) = activation_error(bundle, context) {
        return Err(error);
    }
    let mode = mode_policy(bundle, context.selected_mode)?;
    let (rights, effects, generation) = if context.capability_id == 0 {
        (0, context.requested_effects & mode.allowed_effects, 0)
    } else {
        let rule = capability_rule(bundle, context.capability_id)?;
        (
            context.requested_rights
                & context.issued_rights
                & rule.ceiling_rights
                & mode.allowed_rights,
            context.requested_effects & rule.effect_mask & mode.allowed_effects,
            rule.resource_generation,
        )
    };
    Ok(DryRunDecision {
        policy_sha256: sha256(bundle.raw),
        mode: mode.mode,
        capability_id: context.capability_id,
        effective_rights: rights,
        effective_effects: effects,
        mode_generation: mode.generation,
        capability_generation: generation,
        allowed_capability_count: mode.allowed_capability_count,
        audit_receipt_required: true,
        qualification_only: true,
    })
}

fn decision_id(plan: &DryRunDecision, revocation_epoch: u64, audit_sequence: u64) -> [u8; 32] {
    let mut hasher = Sha256::new();
    hasher.update(plan.policy_sha256);
    hasher.update(u32::from(plan.mode).to_le_bytes());
    hasher.update(plan.capability_id.to_le_bytes());
    hasher.update(plan.effective_rights.to_le_bytes());
    hasher.update(plan.effective_effects.to_le_bytes());
    hasher.update(plan.mode_generation.to_le_bytes());
    hasher.update(u64::from(plan.capability_generation).to_le_bytes());
    hasher.update(revocation_epoch.to_le_bytes());
    hasher.update(audit_sequence.to_le_bytes());
    let value = hasher.finalize();
    let mut result = [0u8; 32];
    result.copy_from_slice(&value);
    result
}

impl DecisionReceipt {
    pub fn synthetic(plan: &DryRunDecision) -> Self {
        Self {
            policy_sha256: plan.policy_sha256,
            mode: plan.mode,
            capability_id: plan.capability_id,
            effective_rights: plan.effective_rights,
            effective_effects: plan.effective_effects,
            mode_generation: plan.mode_generation,
            capability_generation: plan.capability_generation,
            revocation_epoch: 1,
            audit_sequence: 1,
            durable: true,
            qualification_only: true,
            decision_id: decision_id(plan, 1, 1),
        }
    }
}

pub fn receipt_error(plan: &DryRunDecision, receipt: &DecisionReceipt) -> Option<Error> {
    let checks = [
        (
            receipt.qualification_only,
            Error::ReceiptNotQualificationOnly,
        ),
        (
            receipt.policy_sha256 == plan.policy_sha256,
            Error::ReceiptPolicyDigest,
        ),
        (receipt.mode == plan.mode, Error::ReceiptMode),
        (
            receipt.capability_id == plan.capability_id,
            Error::ReceiptCapability,
        ),
        (
            receipt.effective_rights == plan.effective_rights,
            Error::ReceiptRights,
        ),
        (
            receipt.effective_effects == plan.effective_effects,
            Error::ReceiptEffects,
        ),
        (
            receipt.mode_generation == plan.mode_generation
                && receipt.capability_generation == plan.capability_generation,
            Error::ReceiptGeneration,
        ),
        (receipt.revocation_epoch > 0, Error::ReceiptRevocationEpoch),
        (receipt.audit_sequence > 0, Error::ReceiptAuditSequence),
        (receipt.durable, Error::ReceiptNotDurable),
        (
            receipt.decision_id
                == decision_id(plan, receipt.revocation_epoch, receipt.audit_sequence),
            Error::ReceiptDecisionId,
        ),
    ];
    checks
        .into_iter()
        .find_map(|(condition, error)| if condition { None } else { Some(error) })
}

pub fn verify_receipt(plan: &DryRunDecision, receipt: &DecisionReceipt) -> Result<(), Error> {
    receipt_error(plan, receipt).map_or(Ok(()), Err)
}

#[cfg(test)]
mod tests {
    use super::*;

    const CANONICAL: &[u8] = include_bytes!("../../../specs/fixtures/ppol1-canonical.bin");
    const MINIMAL: &[u8] = include_bytes!("../../../specs/fixtures/ppol1-minimal.bin");
    const BOUNDARY: &[u8] = include_bytes!("../../../specs/fixtures/ppol1-boundary.bin");
    const PINIT: &[u8] = include_bytes!("../../../specs/fixtures/ppol1-canonical-pinit.bin");

    #[test]
    fn parses_all_frozen_vectors() {
        assert!(parse(CANONICAL).is_ok());
        assert!(parse(MINIMAL).is_ok());
        assert_eq!(parse(BOUNDARY).expect("boundary").capability_count, 256);
    }

    #[test]
    fn rejects_body_substitution() {
        let mut bytes = CANONICAL.to_vec();
        let last = bytes.len() - 1;
        bytes[last] ^= 1;
        assert_eq!(parse(&bytes), Err(Error::BodyDigest));
    }

    #[test]
    fn cross_binds_canonical_pinit_routes() {
        let bundle = parse(CANONICAL).expect("canonical");
        assert_eq!(validate_initial_system(&bundle, PINIT), Ok(()));
    }

    #[test]
    fn development_denies_at_outer_signature() {
        let bundle = parse(CANONICAL).expect("canonical");
        let context = ActivationContext::development(&bundle).expect("context");
        assert_eq!(
            activation_error(&bundle, &context),
            Some(Error::ActivationOuterSignature)
        );
    }

    #[test]
    fn every_mode_yields_only_a_dry_run() {
        let bundle = parse(CANONICAL).expect("canonical");
        for mode in MODE_NORMAL..=MODE_FIRMWARE {
            let context = ActivationContext::synthetic_qualified(&bundle, mode).expect("context");
            let decision = authorize_dry_run_decision(&bundle, &context).expect("decision");
            assert!(decision.qualification_only);
        }
    }

    #[test]
    fn receipt_is_bound_and_durable() {
        let bundle = parse(CANONICAL).expect("canonical");
        let context =
            ActivationContext::synthetic_qualified(&bundle, MODE_NORMAL).expect("context");
        let decision = authorize_dry_run_decision(&bundle, &context).expect("decision");
        let mut receipt = DecisionReceipt::synthetic(&decision);
        assert_eq!(verify_receipt(&decision, &receipt), Ok(()));
        receipt.durable = false;
        assert_eq!(
            verify_receipt(&decision, &receipt),
            Err(Error::ReceiptNotDurable)
        );
    }
}
