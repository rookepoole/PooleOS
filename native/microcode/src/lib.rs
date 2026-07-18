#![no_std]
#![deny(warnings)]

use sha2::{Digest, Sha256};

pub const CONTRACT_ID: &str = "PMCU1";
pub const MAGIC: [u8; 8] = *b"PMCU1\0\0\0";
pub const MAJOR_VERSION: u16 = 1;
pub const MINOR_VERSION: u16 = 0;
pub const HEADER_BYTES: usize = 512;
pub const PATCH_RECORD_BYTES: usize = 128;
pub const MAX_BUNDLE_BYTES: usize = 1024 * 1024 - 128;
pub const MAX_PATCHES: usize = 32;
pub const MAX_PATCH_BYTES: usize = 512 * 1024;
pub const MAX_PROCESSORS: usize = 256;
pub const PAYLOAD_ALIGNMENT: u32 = 16;

pub const PROFILE_EARLY_CPU_MICROCODE: u16 = 1;
pub const ARCH_X86_64: u16 = 1;
pub const VENDOR_AMD: u16 = 1;
pub const CONTAINER_AMD_OPAQUE_SIGNED_PATCH: u16 = 1;
pub const SELECTION_HIGHEST_ELIGIBLE: u16 = 1;
pub const APPLY_KERNEL_EARLY: u16 = 1;
pub const APPLY_EACH_PROCESSOR_BEFORE_ONLINE: u16 = 1;
pub const RESUME_REAPPLY_IF_REQUIRED: u16 = 1;
pub const ROLLBACK_RESET_THEN_KNOWN_GOOD: u16 = 1;
pub const MIXED_REVISION_FATAL_OR_QUARANTINE: u16 = 1;
pub const VERIFY_ALL_REVISIONS_AND_CPUID: u16 = 1;
pub const FAIL_NO_USER_SCHEDULING: u16 = 1;

pub const MODE_NORMAL: u16 = 1;
pub const MODE_PREVIOUS_KNOWN_GOOD: u16 = 2;
pub const DECISION_APPLY: u16 = 1;
pub const DECISION_SKIP_CURRENT: u16 = 2;
pub const DECISION_RESET_FOR_KNOWN_GOOD: u16 = 3;

pub const FLAG_EXACT_CPU_IDENTITY: u32 = 1 << 0;
pub const FLAG_OPAQUE_VENDOR_PAYLOAD: u32 = 1 << 1;
pub const FLAG_PAYLOAD_DIGESTS: u32 = 1 << 2;
pub const FLAG_SORTED_REVISIONS: u32 = 1 << 3;
pub const FLAG_MONOTONIC_FLOOR: u32 = 1 << 4;
pub const FLAG_OUTER_SIGNATURE: u32 = 1 << 5;
pub const FLAG_INNER_SIGNATURE: u32 = 1 << 6;
pub const FLAG_MANIFEST_SIGNATURE: u32 = 1 << 7;
pub const FLAG_VENDOR_SIGNATURE: u32 = 1 << 8;
pub const FLAG_EARLY_APPLY_ONLY: u32 = 1 << 9;
pub const FLAG_ALL_PROCESSORS: u32 = 1 << 10;
pub const FLAG_POST_APPLY_VERIFY: u32 = 1 << 11;
pub const FLAG_CPUID_REEVALUATE: u32 = 1 << 12;
pub const FLAG_NO_IN_SESSION_DOWNGRADE: u32 = 1 << 13;
pub const FLAG_KNOWN_GOOD_RESET_FALLBACK: u32 = 1 << 14;
pub const FLAG_MIXED_REVISION_FAIL_CLOSED: u32 = 1 << 15;
pub const FLAG_RECEIPT_REQUIRED: u32 = 1 << 16;
pub const FLAG_NO_AUTHORITY_FROM_PARSE: u32 = 1 << 17;
pub const REQUIRED_FLAGS: u32 = (1 << 18) - 1;

pub const PATCH_KNOWN_GOOD: u32 = 1 << 0;
pub const PATCH_PREFERRED: u32 = 1 << 1;
pub const PATCH_VENDOR_AUTH_REQUIRED: u32 = 1 << 2;
pub const PATCH_EARLY_BSP: u32 = 1 << 3;
pub const PATCH_EACH_AP: u32 = 1 << 4;
pub const PATCH_REAPPLY_RESUME: u32 = 1 << 5;
pub const PATCH_POST_VERIFY: u32 = 1 << 6;
pub const PATCH_CPUID_REEVALUATE: u32 = 1 << 7;
pub const PATCH_RECEIPT_REQUIRED: u32 = 1 << 8;
pub const PATCH_REQUIRED_FLAGS: u32 = PATCH_VENDOR_AUTH_REQUIRED
    | PATCH_EARLY_BSP
    | PATCH_EACH_AP
    | PATCH_REAPPLY_RESUME
    | PATCH_POST_VERIFY
    | PATCH_CPUID_REEVALUATE
    | PATCH_RECEIPT_REQUIRED;
pub const PATCH_KNOWN_FLAGS: u32 = PATCH_REQUIRED_FLAGS | PATCH_KNOWN_GOOD | PATCH_PREFERRED;

pub const TARGET_VENDOR_ID: [u8; 12] = *b"AuthenticAMD";
pub const TARGET_CPUID_SIGNATURE: u32 = 0x00B4_0F40;
pub const TARGET_CPUID_MASK: u32 = u32::MAX;
pub const TARGET_PLATFORM_ID: u32 = 0;
pub const TARGET_PLATFORM_MASK: u32 = 0;
pub const SYNTHETIC_REVISION_BASE: u32 = 0xF1A4_4000;
pub const CANONICAL_SECURITY_FLOOR: u32 = SYNTHETIC_REVISION_BASE + 0x20;
pub const CANONICAL_KNOWN_GOOD_REVISION: u32 = SYNTHETIC_REVISION_BASE + 0x20;
pub const CANONICAL_PREFERRED_REVISION: u32 = SYNTHETIC_REVISION_BASE + 0x40;

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum Error {
    Truncated,
    Oversized,
    Magic,
    Version,
    HeaderSize,
    RecordSize,
    Reserved,
    Flags,
    Profile,
    Architecture,
    Vendor,
    ContainerProfile,
    Counts,
    TotalSize,
    TableLayout,
    PayloadSize,
    TargetIdentity,
    VendorId,
    Platform,
    Floor,
    Policy,
    Identity,
    BodyDigest,
    HeaderDigest,
    PatchId,
    PatchFlags,
    PatchIdentity,
    PatchRevision,
    PatchFloor,
    PatchLayout,
    PatchSize,
    PatchAlignment,
    PatchDigest,
    PatchMetadataDigest,
    PatchOrder,
    PatchRole,
    PayloadCoverage,
    SelectCpuid,
    SelectPlatform,
    SelectMode,
    SelectRollbackFloor,
    SelectNoEligible,
    SelectNoKnownGood,
    SelectCurrentRevoked,
    ActivationOuterSignature,
    ActivationInnerSignature,
    ActivationManifestSignature,
    ActivationVendorSignature,
    ActivationVendorContainer,
    ActivationVendorSource,
    ActivationRedistribution,
    ActivationRevocationState,
    ActivationHardwareEvidence,
    ActivationCpuidObservation,
    ActivationRevisionObservation,
    ActivationOuterRole,
    ActivationOuterVersion,
    ActivationOuterPayloadDigest,
    ActivationOuterFileDigest,
    ActivationVendorId,
    ActivationCpuid,
    ActivationPlatform,
    ActivationProcessorCount,
    ActivationMixedBefore,
    ActivationRollbackFloor,
    ActivationBootMode,
    ActivationStage,
    ActivationFeatureTiming,
    ActivationScheduleTiming,
    ActivationProcessorInventory,
    ActivationQuiescence,
    ActivationPayloadCapacity,
    ActivationPatchCapacity,
    ActivationProcessorCapacity,
    ActivationReceiptCapacity,
    ActivationApplyAuthority,
    ActivationFirmwareMutation,
    ActivationPhysicalMedia,
    ActivationNotImplemented,
    VerifyDecision,
    VerifyPatch,
    VerifyProcessorCount,
    VerifyMixedBefore,
    VerifyMixedAfter,
    VerifyRevision,
    VerifyRevoked,
    VerifyCpuidBefore,
    VerifyCpuidAfter,
    VerifyCpuidEvidenceBefore,
    VerifyCpuidEvidenceAfter,
    VerifyFeaturePolicy,
    VerifyMitigationPolicy,
    VerifyReceipt,
    VerifyMixedQuarantine,
    VerifyScheduleStarted,
}

impl Error {
    pub const fn code(self) -> &'static str {
        match self {
            Self::Truncated => "pmcu_truncated",
            Self::Oversized => "pmcu_oversized",
            Self::Magic => "pmcu_magic",
            Self::Version => "pmcu_version",
            Self::HeaderSize => "pmcu_header_size",
            Self::RecordSize => "pmcu_record_size",
            Self::Reserved => "pmcu_reserved",
            Self::Flags => "pmcu_flags",
            Self::Profile => "pmcu_profile",
            Self::Architecture => "pmcu_architecture",
            Self::Vendor => "pmcu_vendor",
            Self::ContainerProfile => "pmcu_container_profile",
            Self::Counts => "pmcu_counts",
            Self::TotalSize => "pmcu_total_size",
            Self::TableLayout => "pmcu_table_layout",
            Self::PayloadSize => "pmcu_payload_size",
            Self::TargetIdentity => "pmcu_target_identity",
            Self::VendorId => "pmcu_vendor_id",
            Self::Platform => "pmcu_platform",
            Self::Floor => "pmcu_floor",
            Self::Policy => "pmcu_policy",
            Self::Identity => "pmcu_identity",
            Self::BodyDigest => "pmcu_body_digest",
            Self::HeaderDigest => "pmcu_header_digest",
            Self::PatchId => "pmcu_patch_id",
            Self::PatchFlags => "pmcu_patch_flags",
            Self::PatchIdentity => "pmcu_patch_identity",
            Self::PatchRevision => "pmcu_patch_revision",
            Self::PatchFloor => "pmcu_patch_floor",
            Self::PatchLayout => "pmcu_patch_layout",
            Self::PatchSize => "pmcu_patch_size",
            Self::PatchAlignment => "pmcu_patch_alignment",
            Self::PatchDigest => "pmcu_patch_digest",
            Self::PatchMetadataDigest => "pmcu_patch_metadata_digest",
            Self::PatchOrder => "pmcu_patch_order",
            Self::PatchRole => "pmcu_patch_role",
            Self::PayloadCoverage => "pmcu_payload_coverage",
            Self::SelectCpuid => "pmcu_select_cpuid",
            Self::SelectPlatform => "pmcu_select_platform",
            Self::SelectMode => "pmcu_select_mode",
            Self::SelectRollbackFloor => "pmcu_select_rollback_floor",
            Self::SelectNoEligible => "pmcu_select_no_eligible",
            Self::SelectNoKnownGood => "pmcu_select_no_known_good",
            Self::SelectCurrentRevoked => "pmcu_select_current_revoked",
            Self::ActivationOuterSignature => "pmcu_activation_outer_signature",
            Self::ActivationInnerSignature => "pmcu_activation_inner_signature",
            Self::ActivationManifestSignature => "pmcu_activation_manifest_signature",
            Self::ActivationVendorSignature => "pmcu_activation_vendor_signature",
            Self::ActivationVendorContainer => "pmcu_activation_vendor_container",
            Self::ActivationVendorSource => "pmcu_activation_vendor_source",
            Self::ActivationRedistribution => "pmcu_activation_redistribution",
            Self::ActivationRevocationState => "pmcu_activation_revocation_state",
            Self::ActivationHardwareEvidence => "pmcu_activation_hardware_evidence",
            Self::ActivationCpuidObservation => "pmcu_activation_cpuid_observation",
            Self::ActivationRevisionObservation => "pmcu_activation_revision_observation",
            Self::ActivationOuterRole => "pmcu_activation_outer_role",
            Self::ActivationOuterVersion => "pmcu_activation_outer_version",
            Self::ActivationOuterPayloadDigest => "pmcu_activation_outer_payload_digest",
            Self::ActivationOuterFileDigest => "pmcu_activation_outer_file_digest",
            Self::ActivationVendorId => "pmcu_activation_vendor_id",
            Self::ActivationCpuid => "pmcu_activation_cpuid",
            Self::ActivationPlatform => "pmcu_activation_platform",
            Self::ActivationProcessorCount => "pmcu_activation_processor_count",
            Self::ActivationMixedBefore => "pmcu_activation_mixed_before",
            Self::ActivationRollbackFloor => "pmcu_activation_rollback_floor",
            Self::ActivationBootMode => "pmcu_activation_boot_mode",
            Self::ActivationStage => "pmcu_activation_stage",
            Self::ActivationFeatureTiming => "pmcu_activation_feature_timing",
            Self::ActivationScheduleTiming => "pmcu_activation_schedule_timing",
            Self::ActivationProcessorInventory => "pmcu_activation_processor_inventory",
            Self::ActivationQuiescence => "pmcu_activation_quiescence",
            Self::ActivationPayloadCapacity => "pmcu_activation_payload_capacity",
            Self::ActivationPatchCapacity => "pmcu_activation_patch_capacity",
            Self::ActivationProcessorCapacity => "pmcu_activation_processor_capacity",
            Self::ActivationReceiptCapacity => "pmcu_activation_receipt_capacity",
            Self::ActivationApplyAuthority => "pmcu_activation_apply_authority",
            Self::ActivationFirmwareMutation => "pmcu_activation_firmware_mutation",
            Self::ActivationPhysicalMedia => "pmcu_activation_physical_media",
            Self::ActivationNotImplemented => "pmcu_activation_not_implemented",
            Self::VerifyDecision => "pmcu_verify_decision",
            Self::VerifyPatch => "pmcu_verify_patch",
            Self::VerifyProcessorCount => "pmcu_verify_processor_count",
            Self::VerifyMixedBefore => "pmcu_verify_mixed_before",
            Self::VerifyMixedAfter => "pmcu_verify_mixed_after",
            Self::VerifyRevision => "pmcu_verify_revision",
            Self::VerifyRevoked => "pmcu_verify_revoked",
            Self::VerifyCpuidBefore => "pmcu_verify_cpuid_before",
            Self::VerifyCpuidAfter => "pmcu_verify_cpuid_after",
            Self::VerifyCpuidEvidenceBefore => "pmcu_verify_cpuid_evidence_before",
            Self::VerifyCpuidEvidenceAfter => "pmcu_verify_cpuid_evidence_after",
            Self::VerifyFeaturePolicy => "pmcu_verify_feature_policy",
            Self::VerifyMitigationPolicy => "pmcu_verify_mitigation_policy",
            Self::VerifyReceipt => "pmcu_verify_receipt",
            Self::VerifyMixedQuarantine => "pmcu_verify_mixed_quarantine",
            Self::VerifyScheduleStarted => "pmcu_verify_schedule_started",
        }
    }
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct Patch<'a> {
    pub patch_id: u32,
    pub flags: u32,
    pub cpuid_signature: u32,
    pub cpuid_mask: u32,
    pub platform_id: u32,
    pub platform_mask: u32,
    pub revision: u32,
    pub minimum_current_revision: u32,
    pub security_revision_floor: u32,
    pub payload_offset: usize,
    pub payload_bytes: usize,
    pub payload_alignment: u32,
    pub vendor_header_bytes: u32,
    pub payload_sha256: [u8; 32],
    pub vendor_metadata_sha256: [u8; 32],
    pub payload: &'a [u8],
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct Bundle<'a> {
    pub raw: &'a [u8],
    pub flags: u32,
    pub patch_count: usize,
    pub target_cpuid_signature: u32,
    pub target_cpuid_mask: u32,
    pub vendor_id: [u8; 12],
    pub target_platform_id: u32,
    pub target_platform_mask: u32,
    pub security_revision_floor: u32,
    pub known_good_revision: u32,
    pub preferred_revision: u32,
    pub body_sha256: [u8; 32],
    pub header_sha256: [u8; 32],
}

impl<'a> Bundle<'a> {
    pub fn patch(&self, index: usize) -> Result<Patch<'a>, Error> {
        if index >= self.patch_count {
            return Err(Error::PatchId);
        }
        parse_patch(self.raw, HEADER_BYTES + index * PATCH_RECORD_BYTES)
    }
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct Selection<'a> {
    pub decision: u16,
    pub patch: Option<Patch<'a>>,
    pub current_revision: u32,
    pub required_floor: u32,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct ApplyContext<'a> {
    pub outer_role: u32,
    pub outer_version: u64,
    pub outer_payload_sha256: [u8; 32],
    pub outer_file_sha256: [u8; 32],
    pub expected_outer_file_sha256: [u8; 32],
    pub outer_signature_verified: bool,
    pub inner_signature_verified: bool,
    pub manifest_signature_verified: bool,
    pub vendor_signature_verified: bool,
    pub vendor_container_validated: bool,
    pub vendor_source_trusted: bool,
    pub redistribution_authorized: bool,
    pub revocation_state_authenticated: bool,
    pub target_hardware_evidence_verified: bool,
    pub cpuid_observation_trusted: bool,
    pub revision_observation_trusted: bool,
    pub vendor_id: [u8; 12],
    pub cpuid_signature: u32,
    pub platform_id: u32,
    pub current_revisions: &'a [u32],
    pub authenticated_rollback_floor: u32,
    pub boot_mode: u16,
    pub executor_stage: u16,
    pub before_affected_features: bool,
    pub before_user_scheduling: bool,
    pub processor_inventory_complete: bool,
    pub processor_set_quiesced: bool,
    pub payload_capacity: usize,
    pub patch_capacity: usize,
    pub processor_capacity: usize,
    pub receipt_capacity: usize,
    pub apply_authority_granted: bool,
    pub firmware_mutation_requested: bool,
    pub physical_media_write_requested: bool,
    pub qualification_only: bool,
}

impl<'a> ApplyContext<'a> {
    pub fn synthetic_qualified(bundle: &Bundle<'_>, current_revisions: &'a [u32]) -> Self {
        let payload_digest = sha256(bundle.raw);
        let file_digest = sha256(b"synthetic-pbart1:pmcu1");
        Self {
            outer_role: 5,
            outer_version: 1,
            outer_payload_sha256: payload_digest,
            outer_file_sha256: file_digest,
            expected_outer_file_sha256: file_digest,
            outer_signature_verified: true,
            inner_signature_verified: true,
            manifest_signature_verified: true,
            vendor_signature_verified: true,
            vendor_container_validated: true,
            vendor_source_trusted: true,
            redistribution_authorized: true,
            revocation_state_authenticated: true,
            target_hardware_evidence_verified: true,
            cpuid_observation_trusted: true,
            revision_observation_trusted: true,
            vendor_id: bundle.vendor_id,
            cpuid_signature: bundle.target_cpuid_signature,
            platform_id: bundle.target_platform_id,
            current_revisions,
            authenticated_rollback_floor: bundle.security_revision_floor,
            boot_mode: MODE_NORMAL,
            executor_stage: APPLY_KERNEL_EARLY,
            before_affected_features: true,
            before_user_scheduling: true,
            processor_inventory_complete: true,
            processor_set_quiesced: true,
            payload_capacity: bundle.raw.len(),
            patch_capacity: bundle.patch_count,
            processor_capacity: current_revisions.len(),
            receipt_capacity: current_revisions.len(),
            apply_authority_granted: true,
            firmware_mutation_requested: false,
            physical_media_write_requested: false,
            qualification_only: true,
        }
    }

    pub fn development(bundle: &Bundle<'_>, current_revisions: &'a [u32]) -> Self {
        let mut context = Self::synthetic_qualified(bundle, current_revisions);
        context.outer_signature_verified = false;
        context.inner_signature_verified = false;
        context.manifest_signature_verified = false;
        context.vendor_signature_verified = false;
        context.vendor_container_validated = false;
        context.vendor_source_trusted = false;
        context.redistribution_authorized = false;
        context.revocation_state_authenticated = false;
        context.target_hardware_evidence_verified = false;
        context.cpuid_observation_trusted = false;
        context.revision_observation_trusted = false;
        context.apply_authority_granted = false;
        context
    }
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct PostApplyObservation<'a> {
    pub patch_id: u32,
    pub target_revision: u32,
    pub before_revisions: &'a [u32],
    pub after_revisions: &'a [u32],
    pub cpuid_signature_before: u32,
    pub cpuid_signature_after: u32,
    pub cpuid_evidence_before_sha256: [u8; 32],
    pub cpuid_evidence_after_sha256: [u8; 32],
    pub feature_policy_revalidated: bool,
    pub mitigation_policy_revalidated: bool,
    pub receipt_persisted: bool,
    pub mixed_failure_quarantined: bool,
    pub user_scheduling_started: bool,
}

fn checked_range(offset: usize, size: usize, limit: usize, error: Error) -> Result<(), Error> {
    if offset > limit || size > limit - offset {
        return Err(error);
    }
    Ok(())
}

fn read_u16(bytes: &[u8], offset: usize) -> Result<u16, Error> {
    checked_range(offset, 2, bytes.len(), Error::Truncated)?;
    Ok(u16::from_le_bytes([bytes[offset], bytes[offset + 1]]))
}

fn read_u32(bytes: &[u8], offset: usize) -> Result<u32, Error> {
    checked_range(offset, 4, bytes.len(), Error::Truncated)?;
    Ok(u32::from_le_bytes([
        bytes[offset],
        bytes[offset + 1],
        bytes[offset + 2],
        bytes[offset + 3],
    ]))
}

fn read_u64(bytes: &[u8], offset: usize) -> Result<u64, Error> {
    checked_range(offset, 8, bytes.len(), Error::Truncated)?;
    Ok(u64::from_le_bytes([
        bytes[offset],
        bytes[offset + 1],
        bytes[offset + 2],
        bytes[offset + 3],
        bytes[offset + 4],
        bytes[offset + 5],
        bytes[offset + 6],
        bytes[offset + 7],
    ]))
}

fn read_array<const N: usize>(bytes: &[u8], offset: usize) -> Result<[u8; N], Error> {
    checked_range(offset, N, bytes.len(), Error::Truncated)?;
    let mut output = [0u8; N];
    output.copy_from_slice(&bytes[offset..offset + N]);
    Ok(output)
}

fn to_usize(value: u64, error: Error) -> Result<usize, Error> {
    usize::try_from(value).map_err(|_| error)
}

fn sha256(bytes: &[u8]) -> [u8; 32] {
    Sha256::digest(bytes).into()
}

fn digest_is_zero(value: &[u8; 32]) -> bool {
    *value == [0u8; 32]
}

fn parse_patch(bytes: &[u8], offset: usize) -> Result<Patch<'_>, Error> {
    checked_range(offset, PATCH_RECORD_BYTES, bytes.len(), Error::PatchLayout)?;
    let patch_id = read_u32(bytes, offset)?;
    let flags = read_u32(bytes, offset + 4)?;
    let cpuid_signature = read_u32(bytes, offset + 8)?;
    let cpuid_mask = read_u32(bytes, offset + 12)?;
    let platform_id = read_u32(bytes, offset + 16)?;
    let platform_mask = read_u32(bytes, offset + 20)?;
    let revision = read_u32(bytes, offset + 24)?;
    let minimum_current_revision = read_u32(bytes, offset + 28)?;
    let security_revision_floor = read_u32(bytes, offset + 32)?;
    if read_u32(bytes, offset + 36)? != 0 {
        return Err(Error::Reserved);
    }
    let payload_offset = to_usize(read_u64(bytes, offset + 40)?, Error::PatchLayout)?;
    let payload_bytes = to_usize(read_u64(bytes, offset + 48)?, Error::PatchSize)?;
    let payload_alignment = read_u32(bytes, offset + 56)?;
    let vendor_header_bytes = read_u32(bytes, offset + 60)?;
    if flags & !PATCH_KNOWN_FLAGS != 0 || flags & PATCH_REQUIRED_FLAGS != PATCH_REQUIRED_FLAGS {
        return Err(Error::PatchFlags);
    }
    if cpuid_signature != TARGET_CPUID_SIGNATURE || cpuid_mask != TARGET_CPUID_MASK {
        return Err(Error::PatchIdentity);
    }
    if platform_id != TARGET_PLATFORM_ID || platform_mask != TARGET_PLATFORM_MASK {
        return Err(Error::PatchIdentity);
    }
    if revision == 0 || minimum_current_revision >= revision {
        return Err(Error::PatchRevision);
    }
    if security_revision_floor == 0 || security_revision_floor > revision {
        return Err(Error::PatchFloor);
    }
    if payload_alignment != PAYLOAD_ALIGNMENT || !payload_alignment.is_power_of_two() {
        return Err(Error::PatchAlignment);
    }
    if payload_offset % payload_alignment as usize != 0 {
        return Err(Error::PatchAlignment);
    }
    if payload_bytes == 0 || payload_bytes > MAX_PATCH_BYTES {
        return Err(Error::PatchSize);
    }
    checked_range(
        payload_offset,
        payload_bytes,
        bytes.len(),
        Error::PatchLayout,
    )?;
    let payload = &bytes[payload_offset..payload_offset + payload_bytes];
    let payload_sha256 = read_array::<32>(bytes, offset + 64)?;
    if sha256(payload) != payload_sha256 {
        return Err(Error::PatchDigest);
    }
    let vendor_metadata_sha256 = read_array::<32>(bytes, offset + 96)?;
    if sha256(&bytes[offset..offset + 96]) != vendor_metadata_sha256 {
        return Err(Error::PatchMetadataDigest);
    }
    Ok(Patch {
        patch_id,
        flags,
        cpuid_signature,
        cpuid_mask,
        platform_id,
        platform_mask,
        revision,
        minimum_current_revision,
        security_revision_floor,
        payload_offset,
        payload_bytes,
        payload_alignment,
        vendor_header_bytes,
        payload_sha256,
        vendor_metadata_sha256,
        payload,
    })
}

pub fn parse(bytes: &[u8]) -> Result<Bundle<'_>, Error> {
    if bytes.len() < HEADER_BYTES {
        return Err(Error::Truncated);
    }
    if bytes.len() > MAX_BUNDLE_BYTES {
        return Err(Error::Oversized);
    }
    if bytes[..8] != MAGIC {
        return Err(Error::Magic);
    }
    if read_u16(bytes, 8)? != MAJOR_VERSION || read_u16(bytes, 10)? != MINOR_VERSION {
        return Err(Error::Version);
    }
    if read_u32(bytes, 12)? != HEADER_BYTES as u32 {
        return Err(Error::HeaderSize);
    }
    if read_u32(bytes, 16)? != PATCH_RECORD_BYTES as u32 {
        return Err(Error::RecordSize);
    }
    let flags = read_u32(bytes, 20)?;
    if flags != REQUIRED_FLAGS {
        return Err(Error::Flags);
    }
    if read_u16(bytes, 24)? != PROFILE_EARLY_CPU_MICROCODE {
        return Err(Error::Profile);
    }
    if read_u16(bytes, 26)? != ARCH_X86_64 {
        return Err(Error::Architecture);
    }
    if read_u16(bytes, 28)? != VENDOR_AMD {
        return Err(Error::Vendor);
    }
    if read_u16(bytes, 30)? != CONTAINER_AMD_OPAQUE_SIGNED_PATCH {
        return Err(Error::ContainerProfile);
    }
    let patch_count = read_u32(bytes, 32)? as usize;
    if !(1..=MAX_PATCHES).contains(&patch_count) || read_u32(bytes, 36)? as usize != MAX_PATCHES {
        return Err(Error::Counts);
    }
    if to_usize(read_u64(bytes, 40)?, Error::TotalSize)? != bytes.len() {
        return Err(Error::TotalSize);
    }
    let records_offset = to_usize(read_u64(bytes, 48)?, Error::TableLayout)?;
    let payload_offset = to_usize(read_u64(bytes, 56)?, Error::TableLayout)?;
    let payload_bytes = to_usize(read_u64(bytes, 64)?, Error::PayloadSize)?;
    let expected_payload_offset = HEADER_BYTES + patch_count * PATCH_RECORD_BYTES;
    if records_offset != HEADER_BYTES || payload_offset != expected_payload_offset {
        return Err(Error::TableLayout);
    }
    if payload_bytes == 0 || payload_bytes != bytes.len() - payload_offset {
        return Err(Error::PayloadSize);
    }
    let target_cpuid_signature = read_u32(bytes, 72)?;
    let target_cpuid_mask = read_u32(bytes, 76)?;
    if target_cpuid_signature != TARGET_CPUID_SIGNATURE || target_cpuid_mask != TARGET_CPUID_MASK {
        return Err(Error::TargetIdentity);
    }
    let vendor_id = read_array::<12>(bytes, 80)?;
    if vendor_id != TARGET_VENDOR_ID {
        return Err(Error::VendorId);
    }
    let target_platform_id = read_u32(bytes, 92)?;
    let target_platform_mask = read_u32(bytes, 96)?;
    if target_platform_id != TARGET_PLATFORM_ID || target_platform_mask != TARGET_PLATFORM_MASK {
        return Err(Error::Platform);
    }
    let security_revision_floor = read_u32(bytes, 100)?;
    let known_good_revision = read_u32(bytes, 104)?;
    let preferred_revision = read_u32(bytes, 108)?;
    if security_revision_floor == 0
        || known_good_revision < security_revision_floor
        || preferred_revision < known_good_revision
    {
        return Err(Error::Floor);
    }
    let expected_policies = [
        SELECTION_HIGHEST_ELIGIBLE,
        APPLY_KERNEL_EARLY,
        APPLY_EACH_PROCESSOR_BEFORE_ONLINE,
        RESUME_REAPPLY_IF_REQUIRED,
        ROLLBACK_RESET_THEN_KNOWN_GOOD,
        MIXED_REVISION_FATAL_OR_QUARANTINE,
        VERIFY_ALL_REVISIONS_AND_CPUID,
        FAIL_NO_USER_SCHEDULING,
    ];
    for (index, expected) in expected_policies.into_iter().enumerate() {
        if read_u16(bytes, 112 + index * 2)? != expected {
            return Err(Error::Policy);
        }
    }
    for offset in [128usize, 160, 192, 224, 256] {
        if digest_is_zero(&read_array::<32>(bytes, offset)?) {
            return Err(Error::Identity);
        }
    }
    if bytes[352..HEADER_BYTES].iter().any(|value| *value != 0) {
        return Err(Error::Reserved);
    }
    let body_sha256 = read_array::<32>(bytes, 288)?;
    if sha256(&bytes[HEADER_BYTES..]) != body_sha256 {
        return Err(Error::BodyDigest);
    }
    let header_sha256 = read_array::<32>(bytes, 320)?;
    let mut hasher = Sha256::new();
    hasher.update(&bytes[..320]);
    hasher.update([0u8; 32]);
    hasher.update(&bytes[352..HEADER_BYTES]);
    let observed_header: [u8; 32] = hasher.finalize().into();
    if observed_header != header_sha256 {
        return Err(Error::HeaderDigest);
    }
    // Finish every record-local integrity check before cross-record policy so
    // independent validators expose the same first failing layer.
    for index in 0..patch_count {
        parse_patch(bytes, HEADER_BYTES + index * PATCH_RECORD_BYTES)?;
    }
    let mut previous_revision = 0u32;
    let mut expected_payload_cursor = payload_offset;
    let mut known_good_count = 0usize;
    let mut preferred_count = 0usize;
    for index in 0..patch_count {
        let patch = parse_patch(bytes, HEADER_BYTES + index * PATCH_RECORD_BYTES)?;
        if patch.patch_id as usize != index + 1 {
            return Err(Error::PatchId);
        }
        if patch.revision <= previous_revision {
            return Err(Error::PatchOrder);
        }
        if patch.security_revision_floor != security_revision_floor {
            return Err(Error::PatchFloor);
        }
        if patch.payload_offset != expected_payload_cursor {
            return Err(Error::PayloadCoverage);
        }
        expected_payload_cursor = expected_payload_cursor
            .checked_add(patch.payload_bytes)
            .ok_or(Error::PayloadCoverage)?;
        previous_revision = patch.revision;
        if patch.flags & PATCH_KNOWN_GOOD != 0 {
            known_good_count += 1;
            if patch.revision != known_good_revision {
                return Err(Error::PatchRole);
            }
        }
        if patch.flags & PATCH_PREFERRED != 0 {
            preferred_count += 1;
            if patch.revision != preferred_revision {
                return Err(Error::PatchRole);
            }
        }
    }
    if expected_payload_cursor != bytes.len() {
        return Err(Error::PayloadCoverage);
    }
    if known_good_count != 1 || preferred_count != 1 {
        return Err(Error::PatchRole);
    }
    Ok(Bundle {
        raw: bytes,
        flags,
        patch_count,
        target_cpuid_signature,
        target_cpuid_mask,
        vendor_id,
        target_platform_id,
        target_platform_mask,
        security_revision_floor,
        known_good_revision,
        preferred_revision,
        body_sha256,
        header_sha256,
    })
}

fn patch_matches(patch: &Patch<'_>, cpuid_signature: u32, platform_id: u32) -> bool {
    cpuid_signature & patch.cpuid_mask == patch.cpuid_signature & patch.cpuid_mask
        && (patch.platform_mask == 0
            || platform_id & patch.platform_mask == patch.platform_id & patch.platform_mask)
}

fn is_revoked(revision: u32, revoked_revisions: &[u32]) -> bool {
    revoked_revisions.contains(&revision)
}

pub fn select_patch<'a>(
    bundle: &Bundle<'a>,
    cpuid_signature: u32,
    platform_id: u32,
    current_revision: u32,
    authenticated_rollback_floor: u32,
    boot_mode: u16,
    revoked_revisions: &[u32],
) -> Result<Selection<'a>, Error> {
    if cpuid_signature != bundle.target_cpuid_signature {
        return Err(Error::SelectCpuid);
    }
    if bundle.target_platform_mask != 0
        && platform_id & bundle.target_platform_mask
            != bundle.target_platform_id & bundle.target_platform_mask
    {
        return Err(Error::SelectPlatform);
    }
    if boot_mode != MODE_NORMAL && boot_mode != MODE_PREVIOUS_KNOWN_GOOD {
        return Err(Error::SelectMode);
    }
    let required_floor =
        core::cmp::max(bundle.security_revision_floor, authenticated_rollback_floor);
    if required_floor > bundle.preferred_revision {
        return Err(Error::SelectRollbackFloor);
    }
    let mut best: Option<Patch<'a>> = None;
    let mut known_good: Option<Patch<'a>> = None;
    for index in 0..bundle.patch_count {
        let patch = bundle.patch(index)?;
        if !patch_matches(&patch, cpuid_signature, platform_id)
            || patch.revision < required_floor
            || is_revoked(patch.revision, revoked_revisions)
            || current_revision < patch.minimum_current_revision
        {
            continue;
        }
        if patch.flags & PATCH_KNOWN_GOOD != 0 {
            known_good = Some(patch);
        }
        if best.is_none_or(|selected| patch.revision > selected.revision) {
            best = Some(patch);
        }
    }
    if best.is_none() {
        if current_revision >= required_floor && !is_revoked(current_revision, revoked_revisions) {
            return Ok(Selection {
                decision: DECISION_SKIP_CURRENT,
                patch: None,
                current_revision,
                required_floor,
            });
        }
        return Err(Error::SelectNoEligible);
    }
    if boot_mode == MODE_PREVIOUS_KNOWN_GOOD {
        let patch = known_good.ok_or(Error::SelectNoKnownGood)?;
        let decision = if current_revision > patch.revision {
            DECISION_RESET_FOR_KNOWN_GOOD
        } else if current_revision == patch.revision {
            DECISION_SKIP_CURRENT
        } else {
            DECISION_APPLY
        };
        return Ok(Selection {
            decision,
            patch: Some(patch),
            current_revision,
            required_floor,
        });
    }
    let patch = best.ok_or(Error::SelectNoEligible)?;
    if current_revision >= patch.revision {
        if is_revoked(current_revision, revoked_revisions) {
            return Err(Error::SelectCurrentRevoked);
        }
        return Ok(Selection {
            decision: DECISION_SKIP_CURRENT,
            patch: Some(patch),
            current_revision,
            required_floor,
        });
    }
    Ok(Selection {
        decision: DECISION_APPLY,
        patch: Some(patch),
        current_revision,
        required_floor,
    })
}

fn revisions_are_uniform(revisions: &[u32]) -> bool {
    revisions
        .first()
        .is_some_and(|first| revisions.iter().all(|value| value == first))
}

pub fn apply_plan_error(bundle: &Bundle<'_>, context: &ApplyContext<'_>) -> Option<Error> {
    let checks = [
        (
            context.outer_signature_verified,
            Error::ActivationOuterSignature,
        ),
        (
            context.inner_signature_verified,
            Error::ActivationInnerSignature,
        ),
        (
            context.manifest_signature_verified,
            Error::ActivationManifestSignature,
        ),
        (
            context.vendor_signature_verified,
            Error::ActivationVendorSignature,
        ),
        (
            context.vendor_container_validated,
            Error::ActivationVendorContainer,
        ),
        (context.vendor_source_trusted, Error::ActivationVendorSource),
        (
            context.redistribution_authorized,
            Error::ActivationRedistribution,
        ),
        (
            context.revocation_state_authenticated,
            Error::ActivationRevocationState,
        ),
        (
            context.target_hardware_evidence_verified,
            Error::ActivationHardwareEvidence,
        ),
        (
            context.cpuid_observation_trusted,
            Error::ActivationCpuidObservation,
        ),
        (
            context.revision_observation_trusted,
            Error::ActivationRevisionObservation,
        ),
    ];
    for (passed, error) in checks {
        if !passed {
            return Some(error);
        }
    }
    if context.outer_role != 5 {
        return Some(Error::ActivationOuterRole);
    }
    if context.outer_version != 1 {
        return Some(Error::ActivationOuterVersion);
    }
    if context.outer_payload_sha256 != sha256(bundle.raw) {
        return Some(Error::ActivationOuterPayloadDigest);
    }
    if context.outer_file_sha256 != context.expected_outer_file_sha256 {
        return Some(Error::ActivationOuterFileDigest);
    }
    if context.vendor_id != bundle.vendor_id {
        return Some(Error::ActivationVendorId);
    }
    if context.cpuid_signature != bundle.target_cpuid_signature {
        return Some(Error::ActivationCpuid);
    }
    if context.platform_id != bundle.target_platform_id {
        return Some(Error::ActivationPlatform);
    }
    if context.current_revisions.is_empty() || context.current_revisions.len() > MAX_PROCESSORS {
        return Some(Error::ActivationProcessorCount);
    }
    if !revisions_are_uniform(context.current_revisions) {
        return Some(Error::ActivationMixedBefore);
    }
    if context.authenticated_rollback_floor < bundle.security_revision_floor {
        return Some(Error::ActivationRollbackFloor);
    }
    if context.boot_mode != MODE_NORMAL && context.boot_mode != MODE_PREVIOUS_KNOWN_GOOD {
        return Some(Error::ActivationBootMode);
    }
    if context.executor_stage != APPLY_KERNEL_EARLY {
        return Some(Error::ActivationStage);
    }
    if !context.before_affected_features {
        return Some(Error::ActivationFeatureTiming);
    }
    if !context.before_user_scheduling {
        return Some(Error::ActivationScheduleTiming);
    }
    if !context.processor_inventory_complete {
        return Some(Error::ActivationProcessorInventory);
    }
    if !context.processor_set_quiesced {
        return Some(Error::ActivationQuiescence);
    }
    if context.payload_capacity < bundle.raw.len() {
        return Some(Error::ActivationPayloadCapacity);
    }
    if context.patch_capacity < bundle.patch_count {
        return Some(Error::ActivationPatchCapacity);
    }
    if context.processor_capacity < context.current_revisions.len() {
        return Some(Error::ActivationProcessorCapacity);
    }
    if context.receipt_capacity < context.current_revisions.len() {
        return Some(Error::ActivationReceiptCapacity);
    }
    if !context.apply_authority_granted {
        return Some(Error::ActivationApplyAuthority);
    }
    if context.firmware_mutation_requested {
        return Some(Error::ActivationFirmwareMutation);
    }
    if context.physical_media_write_requested {
        return Some(Error::ActivationPhysicalMedia);
    }
    if !context.qualification_only {
        return Some(Error::ActivationNotImplemented);
    }
    None
}

pub fn authorize_apply_plan<'a>(
    bundle: &Bundle<'a>,
    context: &ApplyContext<'_>,
    revoked_revisions: &[u32],
) -> Result<Selection<'a>, Error> {
    if let Some(error) = apply_plan_error(bundle, context) {
        return Err(error);
    }
    select_patch(
        bundle,
        context.cpuid_signature,
        context.platform_id,
        context.current_revisions[0],
        context.authenticated_rollback_floor,
        context.boot_mode,
        revoked_revisions,
    )
}

fn digest_present(value: &[u8; 32]) -> bool {
    !digest_is_zero(value)
}

pub fn post_apply_error(
    bundle: &Bundle<'_>,
    selection: &Selection<'_>,
    observation: &PostApplyObservation<'_>,
    revoked_revisions: &[u32],
) -> Option<Error> {
    if selection.decision != DECISION_APPLY {
        return Some(Error::VerifyDecision);
    }
    let patch = match selection.patch {
        Some(value) => value,
        None => return Some(Error::VerifyDecision),
    };
    if observation.patch_id != patch.patch_id || observation.target_revision != patch.revision {
        return Some(Error::VerifyPatch);
    }
    if observation.before_revisions.is_empty()
        || observation.before_revisions.len() > MAX_PROCESSORS
        || observation.before_revisions.len() != observation.after_revisions.len()
    {
        return Some(Error::VerifyProcessorCount);
    }
    if !revisions_are_uniform(observation.before_revisions) {
        return Some(Error::VerifyMixedBefore);
    }
    if !revisions_are_uniform(observation.after_revisions) {
        if !observation.mixed_failure_quarantined {
            return Some(Error::VerifyMixedQuarantine);
        }
        return Some(Error::VerifyMixedAfter);
    }
    let required_floor = core::cmp::max(bundle.security_revision_floor, selection.required_floor);
    for (before, after) in observation
        .before_revisions
        .iter()
        .zip(observation.after_revisions)
    {
        if after < before || *after < patch.revision || *after < required_floor {
            return Some(Error::VerifyRevision);
        }
        if is_revoked(*after, revoked_revisions) {
            return Some(Error::VerifyRevoked);
        }
    }
    if observation.cpuid_signature_before != bundle.target_cpuid_signature {
        return Some(Error::VerifyCpuidBefore);
    }
    if observation.cpuid_signature_after != bundle.target_cpuid_signature {
        return Some(Error::VerifyCpuidAfter);
    }
    if !digest_present(&observation.cpuid_evidence_before_sha256) {
        return Some(Error::VerifyCpuidEvidenceBefore);
    }
    if !digest_present(&observation.cpuid_evidence_after_sha256) {
        return Some(Error::VerifyCpuidEvidenceAfter);
    }
    if !observation.feature_policy_revalidated {
        return Some(Error::VerifyFeaturePolicy);
    }
    if !observation.mitigation_policy_revalidated {
        return Some(Error::VerifyMitigationPolicy);
    }
    if !observation.receipt_persisted {
        return Some(Error::VerifyReceipt);
    }
    if observation.user_scheduling_started {
        return Some(Error::VerifyScheduleStarted);
    }
    None
}

pub fn verify_post_apply(
    bundle: &Bundle<'_>,
    selection: &Selection<'_>,
    observation: &PostApplyObservation<'_>,
    revoked_revisions: &[u32],
) -> Result<(), Error> {
    if let Some(error) = post_apply_error(bundle, selection, observation, revoked_revisions) {
        return Err(error);
    }
    Ok(())
}

#[cfg(test)]
extern crate std;

#[cfg(test)]
mod tests {
    use super::*;
    use std::vec;
    use std::vec::Vec;

    fn put_u16(bytes: &mut [u8], offset: usize, value: u16) {
        bytes[offset..offset + 2].copy_from_slice(&value.to_le_bytes());
    }

    fn put_u32(bytes: &mut [u8], offset: usize, value: u32) {
        bytes[offset..offset + 4].copy_from_slice(&value.to_le_bytes());
    }

    fn put_u64(bytes: &mut [u8], offset: usize, value: u64) {
        bytes[offset..offset + 8].copy_from_slice(&value.to_le_bytes());
    }

    fn payload(label: &[u8], byte_count: usize) -> Vec<u8> {
        let mut output = vec![0u8; byte_count];
        let prefix = b"POOLEOS PMCU1 SYNTHETIC TEST PAYLOAD - NEVER APPLY\0";
        output[..prefix.len()].copy_from_slice(prefix);
        let remaining = core::cmp::min(label.len(), byte_count - prefix.len());
        output[prefix.len()..prefix.len() + remaining].copy_from_slice(&label[..remaining]);
        output
    }

    fn canonical() -> Vec<u8> {
        let payloads = [payload(b"known-good", 256), payload(b"preferred", 384)];
        let patch_count = payloads.len();
        let payload_offset = HEADER_BYTES + patch_count * PATCH_RECORD_BYTES;
        let total_bytes = payload_offset + payloads.iter().map(Vec::len).sum::<usize>();
        let mut output = vec![0u8; total_bytes];
        output[..8].copy_from_slice(&MAGIC);
        put_u16(&mut output, 8, MAJOR_VERSION);
        put_u16(&mut output, 10, MINOR_VERSION);
        put_u32(&mut output, 12, HEADER_BYTES as u32);
        put_u32(&mut output, 16, PATCH_RECORD_BYTES as u32);
        put_u32(&mut output, 20, REQUIRED_FLAGS);
        put_u16(&mut output, 24, PROFILE_EARLY_CPU_MICROCODE);
        put_u16(&mut output, 26, ARCH_X86_64);
        put_u16(&mut output, 28, VENDOR_AMD);
        put_u16(&mut output, 30, CONTAINER_AMD_OPAQUE_SIGNED_PATCH);
        put_u32(&mut output, 32, patch_count as u32);
        put_u32(&mut output, 36, MAX_PATCHES as u32);
        put_u64(&mut output, 40, total_bytes as u64);
        put_u64(&mut output, 48, HEADER_BYTES as u64);
        put_u64(&mut output, 56, payload_offset as u64);
        put_u64(&mut output, 64, (total_bytes - payload_offset) as u64);
        put_u32(&mut output, 72, TARGET_CPUID_SIGNATURE);
        put_u32(&mut output, 76, TARGET_CPUID_MASK);
        output[80..92].copy_from_slice(&TARGET_VENDOR_ID);
        put_u32(&mut output, 92, TARGET_PLATFORM_ID);
        put_u32(&mut output, 96, TARGET_PLATFORM_MASK);
        put_u32(&mut output, 100, CANONICAL_SECURITY_FLOOR);
        put_u32(&mut output, 104, CANONICAL_KNOWN_GOOD_REVISION);
        put_u32(&mut output, 108, CANONICAL_PREFERRED_REVISION);
        for (index, policy) in [
            SELECTION_HIGHEST_ELIGIBLE,
            APPLY_KERNEL_EARLY,
            APPLY_EACH_PROCESSOR_BEFORE_ONLINE,
            RESUME_REAPPLY_IF_REQUIRED,
            ROLLBACK_RESET_THEN_KNOWN_GOOD,
            MIXED_REVISION_FATAL_OR_QUARANTINE,
            VERIFY_ALL_REVISIONS_AND_CPUID,
            FAIL_NO_USER_SCHEDULING,
        ]
        .into_iter()
        .enumerate()
        {
            put_u16(&mut output, 112 + index * 2, policy);
        }
        for offset in [128usize, 160, 192, 224, 256] {
            output[offset..offset + 32].copy_from_slice(&sha256(&offset.to_le_bytes()));
        }
        let mut cursor = payload_offset;
        for (index, item) in payloads.iter().enumerate() {
            let offset = HEADER_BYTES + index * PATCH_RECORD_BYTES;
            put_u32(&mut output, offset, (index + 1) as u32);
            let role = if index == 0 {
                PATCH_KNOWN_GOOD
            } else {
                PATCH_PREFERRED
            };
            put_u32(&mut output, offset + 4, PATCH_REQUIRED_FLAGS | role);
            put_u32(&mut output, offset + 8, TARGET_CPUID_SIGNATURE);
            put_u32(&mut output, offset + 12, TARGET_CPUID_MASK);
            put_u32(&mut output, offset + 16, TARGET_PLATFORM_ID);
            put_u32(&mut output, offset + 20, TARGET_PLATFORM_MASK);
            put_u32(
                &mut output,
                offset + 24,
                if index == 0 {
                    CANONICAL_KNOWN_GOOD_REVISION
                } else {
                    CANONICAL_PREFERRED_REVISION
                },
            );
            put_u32(&mut output, offset + 28, 0);
            put_u32(&mut output, offset + 32, CANONICAL_SECURITY_FLOOR);
            put_u64(&mut output, offset + 40, cursor as u64);
            put_u64(&mut output, offset + 48, item.len() as u64);
            put_u32(&mut output, offset + 56, PAYLOAD_ALIGNMENT);
            output[cursor..cursor + item.len()].copy_from_slice(item);
            let payload_digest = sha256(item);
            output[offset + 64..offset + 96].copy_from_slice(&payload_digest);
            let metadata_digest = sha256(&output[offset..offset + 96]);
            output[offset + 96..offset + 128].copy_from_slice(&metadata_digest);
            cursor += item.len();
        }
        let body_digest = sha256(&output[HEADER_BYTES..]);
        output[288..320].copy_from_slice(&body_digest);
        let header_digest = sha256(&output[..HEADER_BYTES]);
        output[320..352].copy_from_slice(&header_digest);
        output
    }

    #[test]
    fn parses_and_selects_canonical_package() {
        let bytes = canonical();
        let bundle = parse(&bytes).unwrap();
        assert_eq!(bundle.patch_count, 2);
        let selected = select_patch(
            &bundle,
            TARGET_CPUID_SIGNATURE,
            0,
            SYNTHETIC_REVISION_BASE + 0x10,
            CANONICAL_SECURITY_FLOOR,
            MODE_NORMAL,
            &[],
        )
        .unwrap();
        assert_eq!(selected.decision, DECISION_APPLY);
        assert_eq!(
            selected.patch.unwrap().revision,
            CANONICAL_PREFERRED_REVISION
        );
    }

    #[test]
    fn recovery_never_downgrades_in_session() {
        let bytes = canonical();
        let bundle = parse(&bytes).unwrap();
        let selected = select_patch(
            &bundle,
            TARGET_CPUID_SIGNATURE,
            0,
            CANONICAL_PREFERRED_REVISION,
            CANONICAL_SECURITY_FLOOR,
            MODE_PREVIOUS_KNOWN_GOOD,
            &[CANONICAL_PREFERRED_REVISION],
        )
        .unwrap();
        assert_eq!(selected.decision, DECISION_RESET_FOR_KNOWN_GOOD);
        assert_eq!(
            selected.patch.unwrap().revision,
            CANONICAL_KNOWN_GOOD_REVISION
        );
    }

    #[test]
    fn malformed_payload_and_unsigned_context_fail_closed() {
        let bytes = canonical();
        let mut malformed = bytes.clone();
        *malformed.last_mut().unwrap() ^= 1;
        assert_eq!(parse(&malformed), Err(Error::BodyDigest));
        let bundle = parse(&bytes).unwrap();
        let revisions = [SYNTHETIC_REVISION_BASE + 0x10];
        let development = ApplyContext::development(&bundle, &revisions);
        assert_eq!(
            authorize_apply_plan(&bundle, &development, &[]),
            Err(Error::ActivationOuterSignature)
        );
    }

    #[test]
    fn post_apply_verification_rejects_mixed_processors() {
        let bytes = canonical();
        let bundle = parse(&bytes).unwrap();
        let selection = select_patch(
            &bundle,
            TARGET_CPUID_SIGNATURE,
            0,
            SYNTHETIC_REVISION_BASE + 0x10,
            CANONICAL_SECURITY_FLOOR,
            MODE_NORMAL,
            &[],
        )
        .unwrap();
        let before = [SYNTHETIC_REVISION_BASE + 0x10; 2];
        let after = [CANONICAL_PREFERRED_REVISION, CANONICAL_KNOWN_GOOD_REVISION];
        let observation = PostApplyObservation {
            patch_id: 2,
            target_revision: CANONICAL_PREFERRED_REVISION,
            before_revisions: &before,
            after_revisions: &after,
            cpuid_signature_before: TARGET_CPUID_SIGNATURE,
            cpuid_signature_after: TARGET_CPUID_SIGNATURE,
            cpuid_evidence_before_sha256: sha256(b"before"),
            cpuid_evidence_after_sha256: sha256(b"after"),
            feature_policy_revalidated: true,
            mitigation_policy_revalidated: true,
            receipt_persisted: true,
            mixed_failure_quarantined: true,
            user_scheduling_started: false,
        };
        assert_eq!(
            verify_post_apply(&bundle, &selection, &observation, &[]),
            Err(Error::VerifyMixedAfter)
        );
    }
}
