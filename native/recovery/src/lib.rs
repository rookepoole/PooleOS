#![no_std]
#![deny(warnings)]

use sha2::{Digest, Sha256};

pub const CONTRACT_ID: &str = "PREC1";
pub const MAGIC: [u8; 8] = *b"PREC1\0\0\0";
pub const STATE_MAGIC: [u8; 8] = *b"PRECST1\0";
pub const MAJOR_VERSION: u16 = 1;
pub const MINOR_VERSION: u16 = 0;
pub const HEADER_BYTES: usize = 256;
pub const TOTAL_BYTES: usize = 992;
pub const STATE_BYTES: usize = 128;
pub const STATE_CHECKSUM_BYTES: usize = 16;
pub const RECORD_ALIGNMENT: u16 = 8;
pub const SLOT_COUNT: usize = 2;
pub const SLOT_BYTES: usize = 96;
pub const FAILURE_COUNT: usize = 10;
pub const FAILURE_BYTES: usize = 32;
pub const AUTHORITY_COUNT: usize = 7;
pub const AUTHORITY_BYTES: usize = 32;
pub const SLOT_OFFSET: usize = HEADER_BYTES;
pub const FAILURE_OFFSET: usize = SLOT_OFFSET + SLOT_COUNT * SLOT_BYTES;
pub const AUTHORITY_OFFSET: usize = FAILURE_OFFSET + FAILURE_COUNT * FAILURE_BYTES;
pub const MAX_ATTEMPTS_LIMIT: u8 = 7;

pub const FLAG_FAIL_CLOSED: u32 = 1 << 0;
pub const FLAG_AB_SLOTS: u32 = 1 << 1;
pub const FLAG_DECREMENT_BEFORE_HANDOFF: u32 = 1 << 2;
pub const FLAG_KNOWN_GOOD_FALLBACK: u32 = 1 << 3;
pub const FLAG_AUTHENTICATED_STATE: u32 = 1 << 4;
pub const FLAG_OUTER_SIGNATURE: u32 = 1 << 5;
pub const FLAG_INNER_SIGNATURE: u32 = 1 << 6;
pub const FLAG_VERSION_FLOOR: u32 = 1 << 7;
pub const FLAG_OFFLINE_RECOVERY: u32 = 1 << 8;
pub const FLAG_PDC_DISABLED: u32 = 1 << 9;
pub const FLAG_POOLEGLYPH_INDEPENDENT: u32 = 1 << 10;
pub const FLAG_BOUNDED_DISPLAY_PATH: u32 = 1 << 11;
pub const FLAG_PRESERVE_EVIDENCE: u32 = 1 << 12;
pub const FLAG_PHYSICAL_PRESENCE_DESTRUCTIVE: u32 = 1 << 13;
pub const REQUIRED_FLAGS: u32 = FLAG_FAIL_CLOSED
    | FLAG_AB_SLOTS
    | FLAG_DECREMENT_BEFORE_HANDOFF
    | FLAG_KNOWN_GOOD_FALLBACK
    | FLAG_AUTHENTICATED_STATE
    | FLAG_OUTER_SIGNATURE
    | FLAG_INNER_SIGNATURE
    | FLAG_VERSION_FLOOR
    | FLAG_OFFLINE_RECOVERY
    | FLAG_PDC_DISABLED
    | FLAG_POOLEGLYPH_INDEPENDENT
    | FLAG_BOUNDED_DISPLAY_PATH
    | FLAG_PRESERVE_EVIDENCE
    | FLAG_PHYSICAL_PRESENCE_DESTRUCTIVE;

pub const MODE_NORMAL: u8 = 1;
pub const MODE_SAFE: u8 = 2;
pub const MODE_PREVIOUS: u8 = 3;
pub const MODE_RECOVERY: u8 = 4;
pub const MODE_DIAGNOSTIC: u8 = 5;
pub const MODE_FIRMWARE: u8 = 6;
pub const MODE_MASK_ALL: u32 = 0x3f;

pub const FAIL_CONFIG_INVALID: u16 = 1;
pub const FAIL_STATE_INVALID: u16 = 2;
pub const FAIL_SIGNATURE_INVALID: u16 = 3;
pub const FAIL_VERSION_ROLLBACK: u16 = 4;
pub const FAIL_ARTIFACT_INTEGRITY: u16 = 5;
pub const FAIL_KERNEL_ENTRY: u16 = 6;
pub const FAIL_INITIAL_HEALTH_TIMEOUT: u16 = 7;
pub const FAIL_ATTEMPT_EXHAUSTED: u16 = 8;
pub const FAIL_KNOWN_GOOD_RUNTIME: u16 = 9;
pub const FAIL_OPERATOR_REQUEST: u16 = 10;
pub const FAILURE_MASK_ALL: u32 = (1 << FAILURE_COUNT) - 1;

pub const ACTION_RETRY_CANDIDATE: u16 = 1;
pub const ACTION_SAFE: u16 = 2;
pub const ACTION_PREVIOUS: u16 = 3;
pub const ACTION_RECOVERY: u16 = 4;
pub const ACTION_FIRMWARE: u16 = 5;
pub const ACTION_HALT: u16 = 6;
pub const ACTION_MASK_ALL: u32 = (1 << 6) - 1;

const SLOT_BOOTABLE: u16 = 1 << 0;
const SLOT_CANDIDATE_ALLOWED: u16 = 1 << 1;
const SLOT_SAFE_ELIGIBLE: u16 = 1 << 2;
const SLOT_FALLBACK_ELIGIBLE: u16 = 1 << 3;
const SLOT_REQUIRED_FLAGS: u16 = SLOT_BOOTABLE
    | SLOT_CANDIDATE_ALLOWED
    | SLOT_SAFE_ELIGIBLE
    | SLOT_FALLBACK_ELIGIBLE;

const FAILURE_PRESERVE_EVIDENCE: u16 = 1 << 0;
const FAILURE_CLEAR_PENDING: u16 = 1 << 1;
const FAILURE_MARK_UNBOOTABLE: u16 = 1 << 2;
const FAILURE_REQUIRE_PHYSICAL_PRESENCE: u16 = 1 << 3;
const FAILURE_KNOWN_FLAGS: u16 = FAILURE_PRESERVE_EVIDENCE
    | FAILURE_CLEAR_PENDING
    | FAILURE_MARK_UNBOOTABLE
    | FAILURE_REQUIRE_PHYSICAL_PRESENCE;

const AUTH_READ_ONLY: u16 = 1 << 0;
const AUTH_DESTRUCTIVE: u16 = 1 << 1;
const AUTH_OFFLINE_ONLY: u16 = 1 << 2;
const AUTH_AUDITED: u16 = 1 << 3;
const AUTH_KNOWN_FLAGS: u16 = AUTH_READ_ONLY | AUTH_DESTRUCTIVE | AUTH_OFFLINE_ONLY | AUTH_AUDITED;
const FACTOR_PHYSICAL_PRESENCE: u32 = 1 << 0;
const FACTOR_OPERATOR_AUTH: u32 = 1 << 1;
const FACTOR_VERIFIED_BACKUP: u32 = 1 << 2;
const FACTOR_SIGNATURE_VERIFIED: u32 = 1 << 3;
const FACTOR_VOLUME_UNLOCKED: u32 = 1 << 4;
const FACTOR_KNOWN_MASK: u32 = (1 << 5) - 1;
const PROHIBIT_AMBIENT_ALL: u32 = 0x7;
const AUTHORITY_CEILING: u32 = AUTHORITY_COUNT as u32;

const STATE_WRITE_RECOVERY: u16 = 1;
const REQUIRED_TRANSPORTS: u32 = 0x3;
const REQUIRED_HANDOFF_FIELDS: u32 = 0x3f;

pub const STATE_RECOVERY_REQUESTED: u16 = 1 << 0;
pub const STATE_SAFE_REQUESTED: u16 = 1 << 1;
pub const STATE_INFLIGHT: u16 = 1 << 2;
const STATE_KNOWN_FLAGS: u16 = STATE_RECOVERY_REQUESTED | STATE_SAFE_REQUESTED | STATE_INFLIGHT;

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum Error {
    Truncated,
    TotalSize,
    Magic,
    Version,
    HeaderSize,
    Alignment,
    Flags,
    VersionFloor,
    Abi,
    AttemptPolicy,
    SuccessDeadline,
    StateGeometry,
    RecordCount,
    StateWritePolicy,
    TableLayout,
    Modes,
    FailureActionMask,
    HandoffFields,
    StateGenerationFloor,
    BodyDigest,
    RecoveryComponentDigest,
    StateStoreId,
    FallbackPolicy,
    AuthorityCeiling,
    TransportPolicy,
    Reserved,
    SlotId,
    SlotFlags,
    SlotPriority,
    SlotVersion,
    SlotDigest,
    SlotReserved,
    FailureId,
    FailureRule,
    FailureEvidence,
    FailureReserved,
    AuthorityId,
    AuthorityRule,
    AuthorityAmbient,
    AuthorityReserved,
    StateTruncated,
    StateSize,
    StateMagic,
    StateVersion,
    StateFlags,
    StateFloor,
    StateSlot,
    StateMask,
    StateMaskConflict,
    StateActiveKnownGood,
    StateAttempts,
    StateMode,
    StateFailure,
    StateSuccess,
    StateMetadata,
    StatePolicyBinding,
    StateInflight,
    StateReserved,
    StateChecksum,
    Mode,
    TransitionSlot,
    TransitionGeneration,
    TransitionNonce,
    TransitionStateAuth,
    TransitionInflight,
    TransitionPhysicalPresence,
    ReceiptAuth,
    ReceiptInflight,
    ReceiptBinding,
    FailureReceiptAuth,
    FailureReceiptInflight,
    FailureReceiptId,
    ActivationRole,
    ActivationVersion,
    ActivationOuterPayloadDigest,
    ActivationOuterFileDigest,
    ActivationOuterSignature,
    ActivationInnerSignature,
    ActivationManifestSignature,
    ActivationStateAuth,
    ActivationStateGeneration,
    ActivationVersionFloor,
    ActivationComponents,
    ActivationPbp,
    ActivationKernelAbi,
    ActivationOffline,
    ActivationPdcDisabled,
    ActivationPooleGlyphIndependent,
    ActivationDisplayPath,
    ActivationTransactionCapacity,
    ActivationEvidence,
    ActivationRollback,
    ActivationStateWritable,
}

impl Error {
    pub const fn code(self) -> &'static str {
        match self {
            Self::Truncated => "prec_truncated",
            Self::TotalSize => "prec_total_size",
            Self::Magic => "prec_magic",
            Self::Version => "prec_version",
            Self::HeaderSize => "prec_header_size",
            Self::Alignment => "prec_alignment",
            Self::Flags => "prec_flags",
            Self::VersionFloor => "prec_version_floor",
            Self::Abi => "prec_abi",
            Self::AttemptPolicy => "prec_attempt_policy",
            Self::SuccessDeadline => "prec_success_deadline",
            Self::StateGeometry => "prec_state_geometry",
            Self::RecordCount => "prec_record_count",
            Self::StateWritePolicy => "prec_state_write_policy",
            Self::TableLayout => "prec_table_layout",
            Self::Modes => "prec_modes",
            Self::FailureActionMask => "prec_failure_action_mask",
            Self::HandoffFields => "prec_handoff_fields",
            Self::StateGenerationFloor => "prec_state_generation_floor",
            Self::BodyDigest => "prec_body_digest",
            Self::RecoveryComponentDigest => "prec_recovery_component_digest",
            Self::StateStoreId => "prec_state_store_id",
            Self::FallbackPolicy => "prec_fallback_policy",
            Self::AuthorityCeiling => "prec_authority_ceiling",
            Self::TransportPolicy => "prec_transport_policy",
            Self::Reserved => "prec_reserved",
            Self::SlotId => "prec_slot_id",
            Self::SlotFlags => "prec_slot_flags",
            Self::SlotPriority => "prec_slot_priority",
            Self::SlotVersion => "prec_slot_version",
            Self::SlotDigest => "prec_slot_digest",
            Self::SlotReserved => "prec_slot_reserved",
            Self::FailureId => "prec_failure_id",
            Self::FailureRule => "prec_failure_rule",
            Self::FailureEvidence => "prec_failure_evidence",
            Self::FailureReserved => "prec_failure_reserved",
            Self::AuthorityId => "prec_authority_id",
            Self::AuthorityRule => "prec_authority_rule",
            Self::AuthorityAmbient => "prec_authority_ambient",
            Self::AuthorityReserved => "prec_authority_reserved",
            Self::StateTruncated => "prec_state_truncated",
            Self::StateSize => "prec_state_size",
            Self::StateMagic => "prec_state_magic",
            Self::StateVersion => "prec_state_version",
            Self::StateFlags => "prec_state_flags",
            Self::StateFloor => "prec_state_floor",
            Self::StateSlot => "prec_state_slot",
            Self::StateMask => "prec_state_mask",
            Self::StateMaskConflict => "prec_state_mask_conflict",
            Self::StateActiveKnownGood => "prec_state_active_known_good",
            Self::StateAttempts => "prec_state_attempts",
            Self::StateMode => "prec_state_mode",
            Self::StateFailure => "prec_state_failure",
            Self::StateSuccess => "prec_state_success",
            Self::StateMetadata => "prec_state_metadata",
            Self::StatePolicyBinding => "prec_state_policy_binding",
            Self::StateInflight => "prec_state_inflight",
            Self::StateReserved => "prec_state_reserved",
            Self::StateChecksum => "prec_state_checksum",
            Self::Mode => "prec_mode",
            Self::TransitionSlot => "prec_transition_slot",
            Self::TransitionGeneration => "prec_transition_generation",
            Self::TransitionNonce => "prec_transition_nonce",
            Self::TransitionStateAuth => "prec_transition_state_auth",
            Self::TransitionInflight => "prec_transition_inflight",
            Self::TransitionPhysicalPresence => "prec_transition_physical_presence",
            Self::ReceiptAuth => "prec_receipt_auth",
            Self::ReceiptInflight => "prec_receipt_inflight",
            Self::ReceiptBinding => "prec_receipt_binding",
            Self::FailureReceiptAuth => "prec_failure_receipt_auth",
            Self::FailureReceiptInflight => "prec_failure_receipt_inflight",
            Self::FailureReceiptId => "prec_failure_receipt_id",
            Self::ActivationRole => "prec_activation_role",
            Self::ActivationVersion => "prec_activation_version",
            Self::ActivationOuterPayloadDigest => "prec_activation_outer_payload_digest",
            Self::ActivationOuterFileDigest => "prec_activation_outer_file_digest",
            Self::ActivationOuterSignature => "prec_activation_outer_signature",
            Self::ActivationInnerSignature => "prec_activation_inner_signature",
            Self::ActivationManifestSignature => "prec_activation_manifest_signature",
            Self::ActivationStateAuth => "prec_activation_state_auth",
            Self::ActivationStateGeneration => "prec_activation_state_generation",
            Self::ActivationVersionFloor => "prec_activation_version_floor",
            Self::ActivationComponents => "prec_activation_components",
            Self::ActivationPbp => "prec_activation_pbp",
            Self::ActivationKernelAbi => "prec_activation_kernel_abi",
            Self::ActivationOffline => "prec_activation_offline",
            Self::ActivationPdcDisabled => "prec_activation_pdc_disabled",
            Self::ActivationPooleGlyphIndependent => "prec_activation_pooleglyph_independent",
            Self::ActivationDisplayPath => "prec_activation_display_path",
            Self::ActivationTransactionCapacity => "prec_activation_transaction_capacity",
            Self::ActivationEvidence => "prec_activation_evidence",
            Self::ActivationRollback => "prec_activation_rollback",
            Self::ActivationStateWritable => "prec_activation_state_writable",
        }
    }
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct Bundle<'a> {
    pub bundle_version: u64,
    pub minimum_secure_version: u64,
    pub required_pbp_major: u16,
    pub minimum_pbp_minor: u16,
    pub required_kernel_abi_major: u16,
    pub minimum_kernel_abi_minor: u16,
    pub max_attempts: u8,
    pub max_safe_attempts: u8,
    pub success_deadline_seconds: u32,
    pub state_generation_floor: u64,
    pub body_sha256: [u8; 32],
    pub raw: &'a [u8],
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct State {
    pub flags: u16,
    pub generation: u64,
    pub minimum_secure_version: u64,
    pub active_slot: u8,
    pub pending_slot: u8,
    pub known_good_mask: u8,
    pub unbootable_mask: u8,
    pub attempts_a: u8,
    pub attempts_b: u8,
    pub safe_attempted_mask: u8,
    pub current_mode: u8,
    pub last_failure: u16,
    pub transaction_id: u64,
    pub boot_nonce: u64,
    pub inflight_generation: u64,
    pub inflight_slot: u8,
    pub inflight_mode: u8,
    pub last_success_slot: u8,
    pub last_success_generation: u64,
    pub policy_version: u64,
    pub state_store_epoch: u64,
    pub evidence_sequence: u64,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct Decision {
    pub mode: u8,
    pub slot: u8,
    pub trial: bool,
    pub persistence_required: bool,
    pub reason: u16,
    pub state: State,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct FailureDecision {
    pub action: u16,
    pub state: State,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct SuccessReceipt {
    pub authenticated: bool,
    pub generation: u64,
    pub slot: u8,
    pub mode: u8,
    pub boot_nonce: u64,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct ActivationContext {
    pub outer_role: u32,
    pub outer_artifact_version: u64,
    pub outer_payload_digest_verified: bool,
    pub outer_file_digest_verified: bool,
    pub outer_signature_verified: bool,
    pub inner_signature_verified: bool,
    pub manifest_signature_verified: bool,
    pub state_authenticated: bool,
    pub state_generation_monotonic: bool,
    pub version_floor_persisted: bool,
    pub manifest_and_components_verified: bool,
    pub pbp_major: u16,
    pub pbp_minor: u16,
    pub kernel_abi_major: u16,
    pub kernel_abi_minor: u16,
    pub offline_path: bool,
    pub pdc_disabled: bool,
    pub pooleglyph_independent: bool,
    pub serial_or_gop_software_path: bool,
    pub transaction_capacity_verified: bool,
    pub evidence_preservation_ready: bool,
    pub rollback_available: bool,
    pub state_writable: bool,
}

impl ActivationContext {
    pub const fn development() -> Self {
        Self {
            outer_role: 3,
            outer_artifact_version: 1,
            outer_payload_digest_verified: true,
            outer_file_digest_verified: true,
            outer_signature_verified: false,
            inner_signature_verified: false,
            manifest_signature_verified: false,
            state_authenticated: false,
            state_generation_monotonic: false,
            version_floor_persisted: false,
            manifest_and_components_verified: false,
            pbp_major: 1,
            pbp_minor: 0,
            kernel_abi_major: 1,
            kernel_abi_minor: 0,
            offline_path: true,
            pdc_disabled: true,
            pooleglyph_independent: true,
            serial_or_gop_software_path: true,
            transaction_capacity_verified: false,
            evidence_preservation_ready: false,
            rollback_available: false,
            state_writable: false,
        }
    }

    pub const fn synthetic_qualified(bundle: &Bundle<'_>) -> Self {
        Self {
            outer_role: 3,
            outer_artifact_version: bundle.bundle_version,
            outer_payload_digest_verified: true,
            outer_file_digest_verified: true,
            outer_signature_verified: true,
            inner_signature_verified: true,
            manifest_signature_verified: true,
            state_authenticated: true,
            state_generation_monotonic: true,
            version_floor_persisted: true,
            manifest_and_components_verified: true,
            pbp_major: bundle.required_pbp_major,
            pbp_minor: bundle.minimum_pbp_minor,
            kernel_abi_major: bundle.required_kernel_abi_major,
            kernel_abi_minor: bundle.minimum_kernel_abi_minor,
            offline_path: true,
            pdc_disabled: true,
            pooleglyph_independent: true,
            serial_or_gop_software_path: true,
            transaction_capacity_verified: true,
            evidence_preservation_ready: true,
            rollback_available: true,
            state_writable: true,
        }
    }
}

fn bytes<const N: usize>(data: &[u8], offset: usize) -> Result<[u8; N], Error> {
    data.get(offset..offset + N)
        .ok_or(Error::Truncated)?
        .try_into()
        .map_err(|_| Error::Truncated)
}

fn u16_at(data: &[u8], offset: usize) -> Result<u16, Error> {
    Ok(u16::from_le_bytes(bytes(data, offset)?))
}

fn u32_at(data: &[u8], offset: usize) -> Result<u32, Error> {
    Ok(u32::from_le_bytes(bytes(data, offset)?))
}

fn u64_at(data: &[u8], offset: usize) -> Result<u64, Error> {
    Ok(u64::from_le_bytes(bytes(data, offset)?))
}

fn all_zero(data: &[u8]) -> bool {
    data.iter().all(|byte| *byte == 0)
}

fn mode_bit(mode: u8) -> Result<u32, Error> {
    if !(MODE_NORMAL..=MODE_FIRMWARE).contains(&mode) {
        return Err(Error::Mode);
    }
    Ok(1 << (mode - 1))
}

const FAILURE_ROWS: [(u16, u16, u16, u16, u32); FAILURE_COUNT] = [
    (ACTION_RECOVERY, ACTION_HALT, FAILURE_PRESERVE_EVIDENCE, 0, MODE_MASK_ALL),
    (ACTION_RECOVERY, ACTION_HALT, FAILURE_PRESERVE_EVIDENCE, 0, MODE_MASK_ALL),
    (
        ACTION_RECOVERY,
        ACTION_HALT,
        FAILURE_PRESERVE_EVIDENCE | FAILURE_CLEAR_PENDING | FAILURE_MARK_UNBOOTABLE,
        0,
        MODE_MASK_ALL,
    ),
    (
        ACTION_PREVIOUS,
        ACTION_RECOVERY,
        FAILURE_PRESERVE_EVIDENCE | FAILURE_CLEAR_PENDING | FAILURE_MARK_UNBOOTABLE,
        0,
        MODE_MASK_ALL,
    ),
    (
        ACTION_PREVIOUS,
        ACTION_RECOVERY,
        FAILURE_PRESERVE_EVIDENCE | FAILURE_CLEAR_PENDING | FAILURE_MARK_UNBOOTABLE,
        0,
        MODE_MASK_ALL,
    ),
    (ACTION_SAFE, ACTION_PREVIOUS, FAILURE_PRESERVE_EVIDENCE, 1, MODE_MASK_ALL),
    (
        ACTION_RETRY_CANDIDATE,
        ACTION_PREVIOUS,
        FAILURE_PRESERVE_EVIDENCE,
        2,
        MODE_MASK_ALL,
    ),
    (
        ACTION_PREVIOUS,
        ACTION_RECOVERY,
        FAILURE_PRESERVE_EVIDENCE | FAILURE_CLEAR_PENDING | FAILURE_MARK_UNBOOTABLE,
        0,
        MODE_MASK_ALL,
    ),
    (ACTION_SAFE, ACTION_RECOVERY, FAILURE_PRESERVE_EVIDENCE, 1, MODE_MASK_ALL),
    (ACTION_RECOVERY, ACTION_FIRMWARE, FAILURE_PRESERVE_EVIDENCE, 0, MODE_MASK_ALL),
];

const AUTHORITY_ROWS: [(u16, u32, u32, u16, u32); AUTHORITY_COUNT] = [
    (AUTH_READ_ONLY | AUTH_OFFLINE_ONLY | AUTH_AUDITED, 0, 0x18, 0, 201),
    (
        AUTH_READ_ONLY | AUTH_OFFLINE_ONLY | AUTH_AUDITED,
        FACTOR_OPERATOR_AUTH,
        0x08,
        0,
        202,
    ),
    (
        AUTH_OFFLINE_ONLY | AUTH_AUDITED,
        FACTOR_PHYSICAL_PRESENCE | FACTOR_OPERATOR_AUTH,
        0x08,
        1,
        203,
    ),
    (AUTH_OFFLINE_ONLY | AUTH_AUDITED, FACTOR_OPERATOR_AUTH, 0x08, 1, 204),
    (
        AUTH_OFFLINE_ONLY | AUTH_AUDITED,
        FACTOR_PHYSICAL_PRESENCE | FACTOR_OPERATOR_AUTH | FACTOR_VOLUME_UNLOCKED,
        0x08,
        3,
        205,
    ),
    (
        AUTH_DESTRUCTIVE | AUTH_OFFLINE_ONLY | AUTH_AUDITED,
        FACTOR_PHYSICAL_PRESENCE | FACTOR_OPERATOR_AUTH | FACTOR_VERIFIED_BACKUP | FACTOR_SIGNATURE_VERIFIED,
        0x08,
        1,
        206,
    ),
    (
        AUTH_DESTRUCTIVE | AUTH_OFFLINE_ONLY | AUTH_AUDITED,
        FACTOR_PHYSICAL_PRESENCE | FACTOR_OPERATOR_AUTH | FACTOR_VERIFIED_BACKUP | FACTOR_SIGNATURE_VERIFIED,
        0x08,
        1,
        207,
    ),
];

pub fn parse(data: &[u8]) -> Result<Bundle<'_>, Error> {
    if data.len() < HEADER_BYTES {
        return Err(Error::Truncated);
    }
    if data.len() != TOTAL_BYTES {
        return Err(Error::TotalSize);
    }
    if data[..8] != MAGIC {
        return Err(Error::Magic);
    }
    if u16_at(data, 8)? != MAJOR_VERSION || u16_at(data, 10)? != MINOR_VERSION {
        return Err(Error::Version);
    }
    if u16_at(data, 12)? as usize != HEADER_BYTES {
        return Err(Error::HeaderSize);
    }
    if u16_at(data, 14)? != RECORD_ALIGNMENT {
        return Err(Error::Alignment);
    }
    if u32_at(data, 16)? != TOTAL_BYTES as u32 {
        return Err(Error::TotalSize);
    }
    if u32_at(data, 20)? != REQUIRED_FLAGS {
        return Err(Error::Flags);
    }
    let bundle_version = u64_at(data, 24)?;
    let minimum_secure_version = u64_at(data, 32)?;
    if bundle_version == 0 || minimum_secure_version == 0 || bundle_version < minimum_secure_version {
        return Err(Error::VersionFloor);
    }
    let required_pbp_major = u16_at(data, 40)?;
    let minimum_pbp_minor = u16_at(data, 42)?;
    let required_kernel_abi_major = u16_at(data, 44)?;
    let minimum_kernel_abi_minor = u16_at(data, 46)?;
    if required_pbp_major == 0 || required_kernel_abi_major == 0 {
        return Err(Error::Abi);
    }
    let max_attempts = u16_at(data, 48)?;
    let max_safe_attempts = u16_at(data, 50)?;
    if !(1..=u16::from(MAX_ATTEMPTS_LIMIT)).contains(&max_attempts) || max_safe_attempts != 1 {
        return Err(Error::AttemptPolicy);
    }
    let success_deadline_seconds = u32_at(data, 52)?;
    if !(1..=3600).contains(&success_deadline_seconds) {
        return Err(Error::SuccessDeadline);
    }
    if u16_at(data, 56)? != STATE_BYTES as u16 || u16_at(data, 58)? != STATE_CHECKSUM_BYTES as u16 {
        return Err(Error::StateGeometry);
    }
    if u16_at(data, 60)? != SLOT_COUNT as u16
        || u16_at(data, 62)? != FAILURE_COUNT as u16
        || u16_at(data, 64)? != AUTHORITY_COUNT as u16
    {
        return Err(Error::RecordCount);
    }
    if u16_at(data, 66)? != STATE_WRITE_RECOVERY {
        return Err(Error::StateWritePolicy);
    }
    if u32_at(data, 68)? != SLOT_OFFSET as u32
        || u32_at(data, 72)? != FAILURE_OFFSET as u32
        || u32_at(data, 76)? != AUTHORITY_OFFSET as u32
    {
        return Err(Error::TableLayout);
    }
    if u32_at(data, 80)? != MODE_MASK_ALL {
        return Err(Error::Modes);
    }
    if u32_at(data, 84)? != FAILURE_MASK_ALL || u32_at(data, 88)? != ACTION_MASK_ALL {
        return Err(Error::FailureActionMask);
    }
    if u32_at(data, 92)? != REQUIRED_HANDOFF_FIELDS {
        return Err(Error::HandoffFields);
    }
    let state_generation_floor = u64_at(data, 96)?;
    if state_generation_floor == 0 {
        return Err(Error::StateGenerationFloor);
    }
    let body_sha256: [u8; 32] = bytes(data, 104)?;
    if Sha256::digest(&data[HEADER_BYTES..]).as_slice() != body_sha256 {
        return Err(Error::BodyDigest);
    }
    if all_zero(&data[136..168]) {
        return Err(Error::RecoveryComponentDigest);
    }
    if all_zero(&data[168..184]) {
        return Err(Error::StateStoreId);
    }
    if (u16_at(data, 184)?, u16_at(data, 186)?, u16_at(data, 188)?, u16_at(data, 190)?)
        != (ACTION_PREVIOUS, ACTION_RECOVERY, ACTION_RECOVERY, ACTION_RECOVERY)
    {
        return Err(Error::FallbackPolicy);
    }
    if u32_at(data, 192)? != AUTHORITY_CEILING {
        return Err(Error::AuthorityCeiling);
    }
    if u32_at(data, 196)? != REQUIRED_TRANSPORTS {
        return Err(Error::TransportPolicy);
    }
    if !all_zero(&data[200..HEADER_BYTES]) {
        return Err(Error::Reserved);
    }

    let mut previous_priority = u32::MAX;
    for index in 0..SLOT_COUNT {
        let offset = SLOT_OFFSET + index * SLOT_BYTES;
        if u16_at(data, offset)? != (index + 1) as u16 {
            return Err(Error::SlotId);
        }
        if u16_at(data, offset + 2)? != SLOT_REQUIRED_FLAGS {
            return Err(Error::SlotFlags);
        }
        let priority = u32_at(data, offset + 4)?;
        if priority == 0 || priority >= previous_priority {
            return Err(Error::SlotPriority);
        }
        previous_priority = priority;
        let version = u64_at(data, offset + 8)?;
        let minimum_recovery = u64_at(data, offset + 16)?;
        if version < minimum_secure_version || minimum_recovery == 0 || minimum_recovery > bundle_version {
            return Err(Error::SlotVersion);
        }
        if all_zero(&data[offset + 24..offset + 56]) || all_zero(&data[offset + 56..offset + 88]) {
            return Err(Error::SlotDigest);
        }
        if index == 1 {
            if data[offset + 24..offset + 56] == data[SLOT_OFFSET + 24..SLOT_OFFSET + 56]
                || data[offset + 56..offset + 88] == data[SLOT_OFFSET + 56..SLOT_OFFSET + 88]
            {
                return Err(Error::SlotDigest);
            }
        }
        if !all_zero(&data[offset + 88..offset + SLOT_BYTES]) {
            return Err(Error::SlotReserved);
        }
    }

    for (index, expected) in FAILURE_ROWS.iter().enumerate() {
        let offset = FAILURE_OFFSET + index * FAILURE_BYTES;
        if u16_at(data, offset)? != (index + 1) as u16 {
            return Err(Error::FailureId);
        }
        let actual = (
            u16_at(data, offset + 2)?,
            u16_at(data, offset + 4)?,
            u16_at(data, offset + 6)?,
            u16_at(data, offset + 8)?,
            u32_at(data, offset + 12)?,
        );
        if actual != *expected || actual.2 & !FAILURE_KNOWN_FLAGS != 0 {
            return Err(Error::FailureRule);
        }
        if u16_at(data, offset + 10)? != 101 + index as u16 {
            return Err(Error::FailureEvidence);
        }
        if !all_zero(&data[offset + 16..offset + FAILURE_BYTES]) {
            return Err(Error::FailureReserved);
        }
    }

    for (index, expected) in AUTHORITY_ROWS.iter().enumerate() {
        let offset = AUTHORITY_OFFSET + index * AUTHORITY_BYTES;
        if u16_at(data, offset)? != (index + 1) as u16 {
            return Err(Error::AuthorityId);
        }
        let flags = u16_at(data, offset + 2)?;
        let factors = u32_at(data, offset + 4)?;
        let actual = (
            flags,
            factors,
            u32_at(data, offset + 12)?,
            u16_at(data, offset + 16)?,
            u32_at(data, offset + 20)?,
        );
        if actual != *expected || flags & !AUTH_KNOWN_FLAGS != 0 || factors & !FACTOR_KNOWN_MASK != 0 {
            return Err(Error::AuthorityRule);
        }
        if u32_at(data, offset + 8)? != PROHIBIT_AMBIENT_ALL {
            return Err(Error::AuthorityAmbient);
        }
        if u16_at(data, offset + 18)? != 0 || !all_zero(&data[offset + 24..offset + AUTHORITY_BYTES]) {
            return Err(Error::AuthorityReserved);
        }
    }

    Ok(Bundle {
        bundle_version,
        minimum_secure_version,
        required_pbp_major,
        minimum_pbp_minor,
        required_kernel_abi_major,
        minimum_kernel_abi_minor,
        max_attempts: max_attempts as u8,
        max_safe_attempts: max_safe_attempts as u8,
        success_deadline_seconds,
        state_generation_floor,
        body_sha256,
        raw: data,
    })
}

fn state_checksum(data: &[u8]) -> Result<[u8; STATE_CHECKSUM_BYTES], Error> {
    if data.len() < STATE_BYTES - STATE_CHECKSUM_BYTES {
        return Err(Error::StateTruncated);
    }
    let digest = Sha256::digest(&data[..STATE_BYTES - STATE_CHECKSUM_BYTES]);
    digest[..STATE_CHECKSUM_BYTES]
        .try_into()
        .map_err(|_| Error::StateChecksum)
}

pub fn parse_state(data: &[u8]) -> Result<State, Error> {
    if data.len() < STATE_BYTES {
        return Err(Error::StateTruncated);
    }
    if data.len() != STATE_BYTES {
        return Err(Error::StateSize);
    }
    if data[..8] != STATE_MAGIC {
        return Err(Error::StateMagic);
    }
    if u16_at(data, 8)? != MAJOR_VERSION || u16_at(data, 10)? != MINOR_VERSION {
        return Err(Error::StateVersion);
    }
    if u16_at(data, 12)? != STATE_BYTES as u16 {
        return Err(Error::StateSize);
    }
    let flags = u16_at(data, 14)?;
    if flags & !STATE_KNOWN_FLAGS != 0 {
        return Err(Error::StateFlags);
    }
    let generation = u64_at(data, 16)?;
    let minimum_secure_version = u64_at(data, 24)?;
    if generation == 0 || minimum_secure_version == 0 {
        return Err(Error::StateFloor);
    }
    let active_slot = data[32];
    let pending_slot = data[33];
    let known_good_mask = data[34];
    let unbootable_mask = data[35];
    let attempts_a = data[36];
    let attempts_b = data[37];
    let safe_attempted_mask = data[38];
    let current_mode = data[39];
    if !(1..=2).contains(&active_slot)
        || pending_slot > 2
        || pending_slot == active_slot
    {
        return Err(Error::StateSlot);
    }
    if known_good_mask == 0
        || known_good_mask & !0x3 != 0
        || unbootable_mask & !0x3 != 0
        || safe_attempted_mask & !0x3 != 0
    {
        return Err(Error::StateMask);
    }
    if known_good_mask & unbootable_mask != 0 {
        return Err(Error::StateMaskConflict);
    }
    if known_good_mask & (1 << (active_slot - 1)) == 0 {
        return Err(Error::StateActiveKnownGood);
    }
    if attempts_a > MAX_ATTEMPTS_LIMIT || attempts_b > MAX_ATTEMPTS_LIMIT {
        return Err(Error::StateAttempts);
    }
    if current_mode > MODE_FIRMWARE {
        return Err(Error::StateMode);
    }
    let last_failure = u16_at(data, 40)?;
    if last_failure > FAILURE_COUNT as u16 || u16_at(data, 42)? != 0 {
        return Err(Error::StateFailure);
    }
    let transaction_id = u64_at(data, 44)?;
    let boot_nonce = u64_at(data, 52)?;
    let inflight_generation = u64_at(data, 60)?;
    let inflight_slot = data[68];
    let inflight_mode = data[69];
    let last_success_slot = data[70];
    let last_success_generation = u64_at(data, 72)?;
    let policy_version = u64_at(data, 80)?;
    let state_store_epoch = u64_at(data, 88)?;
    let evidence_sequence = u64_at(data, 96)?;
    if !(1..=2).contains(&last_success_slot)
        || last_success_generation == 0
        || last_success_generation > generation
    {
        return Err(Error::StateSuccess);
    }
    if policy_version == 0 || state_store_epoch == 0 || evidence_sequence == 0 {
        return Err(Error::StateMetadata);
    }
    let inflight = flags & STATE_INFLIGHT != 0;
    if inflight {
        if boot_nonce == 0
            || inflight_generation != generation
            || !(1..=2).contains(&inflight_slot)
            || !(MODE_NORMAL..=MODE_FIRMWARE).contains(&inflight_mode)
            || current_mode != inflight_mode
        {
            return Err(Error::StateInflight);
        }
    } else if boot_nonce != 0 || inflight_generation != 0 || inflight_slot != 0 || inflight_mode != 0 {
        return Err(Error::StateInflight);
    }
    if data[71] != 0 || u64_at(data, 104)? != 0 {
        return Err(Error::StateReserved);
    }
    if data[112..128] != state_checksum(data)? {
        return Err(Error::StateChecksum);
    }
    Ok(State {
        flags,
        generation,
        minimum_secure_version,
        active_slot,
        pending_slot,
        known_good_mask,
        unbootable_mask,
        attempts_a,
        attempts_b,
        safe_attempted_mask,
        current_mode,
        last_failure,
        transaction_id,
        boot_nonce,
        inflight_generation,
        inflight_slot,
        inflight_mode,
        last_success_slot,
        last_success_generation,
        policy_version,
        state_store_epoch,
        evidence_sequence,
    })
}

pub fn encode_state(state: &State) -> [u8; STATE_BYTES] {
    let mut output = [0u8; STATE_BYTES];
    output[..8].copy_from_slice(&STATE_MAGIC);
    output[8..10].copy_from_slice(&MAJOR_VERSION.to_le_bytes());
    output[10..12].copy_from_slice(&MINOR_VERSION.to_le_bytes());
    output[12..14].copy_from_slice(&(STATE_BYTES as u16).to_le_bytes());
    output[14..16].copy_from_slice(&state.flags.to_le_bytes());
    output[16..24].copy_from_slice(&state.generation.to_le_bytes());
    output[24..32].copy_from_slice(&state.minimum_secure_version.to_le_bytes());
    output[32] = state.active_slot;
    output[33] = state.pending_slot;
    output[34] = state.known_good_mask;
    output[35] = state.unbootable_mask;
    output[36] = state.attempts_a;
    output[37] = state.attempts_b;
    output[38] = state.safe_attempted_mask;
    output[39] = state.current_mode;
    output[40..42].copy_from_slice(&state.last_failure.to_le_bytes());
    output[44..52].copy_from_slice(&state.transaction_id.to_le_bytes());
    output[52..60].copy_from_slice(&state.boot_nonce.to_le_bytes());
    output[60..68].copy_from_slice(&state.inflight_generation.to_le_bytes());
    output[68] = state.inflight_slot;
    output[69] = state.inflight_mode;
    output[70] = state.last_success_slot;
    output[72..80].copy_from_slice(&state.last_success_generation.to_le_bytes());
    output[80..88].copy_from_slice(&state.policy_version.to_le_bytes());
    output[88..96].copy_from_slice(&state.state_store_epoch.to_le_bytes());
    output[96..104].copy_from_slice(&state.evidence_sequence.to_le_bytes());
    let digest = Sha256::digest(&output[..112]);
    output[112..128].copy_from_slice(&digest[..16]);
    output
}

fn validate_state_for_policy(policy: &Bundle<'_>, state: &State) -> Result<(), Error> {
    let encoded = encode_state(state);
    parse_state(&encoded)?;
    if state.generation < policy.state_generation_floor
        || state.minimum_secure_version < policy.minimum_secure_version
        || state.policy_version != policy.bundle_version
        || state.attempts_a > policy.max_attempts
        || state.attempts_b > policy.max_attempts
    {
        return Err(Error::StatePolicyBinding);
    }
    Ok(())
}

fn next_generation(state: &State) -> Result<u64, Error> {
    state.generation.checked_add(1).ok_or(Error::TransitionGeneration)
}

fn slot_bit(slot: u8) -> Result<u8, Error> {
    if !(1..=2).contains(&slot) {
        return Err(Error::TransitionSlot);
    }
    Ok(1 << (slot - 1))
}

fn slot_version(policy: &Bundle<'_>, slot: u8) -> Result<u64, Error> {
    let offset = SLOT_OFFSET + usize::from(slot - 1) * SLOT_BYTES + 8;
    u64_at(policy.raw, offset)
}

fn eligible(policy: &Bundle<'_>, state: &State, slot: u8, known_good: bool) -> Result<bool, Error> {
    let bit = slot_bit(slot)?;
    if state.unbootable_mask & bit != 0
        || slot_version(policy, slot)? < core::cmp::max(policy.minimum_secure_version, state.minimum_secure_version)
    {
        return Ok(false);
    }
    Ok(!known_good || state.known_good_mask & bit != 0)
}

fn attempts(state: &State, slot: u8) -> u8 {
    if slot == 1 { state.attempts_a } else { state.attempts_b }
}

fn set_attempts(state: &mut State, slot: u8, value: u8) {
    if slot == 1 {
        state.attempts_a = value;
    } else {
        state.attempts_b = value;
    }
}

fn recovery_decision(mut state: State, reason: u16) -> Result<Decision, Error> {
    state.flags &= !(STATE_INFLIGHT | STATE_SAFE_REQUESTED);
    state.generation = next_generation(&state)?;
    state.current_mode = MODE_RECOVERY;
    state.last_failure = reason;
    state.boot_nonce = 0;
    state.inflight_generation = 0;
    state.inflight_slot = 0;
    state.inflight_mode = 0;
    state.evidence_sequence = state.evidence_sequence.wrapping_add(1);
    Ok(Decision {
        mode: MODE_RECOVERY,
        slot: 0,
        trial: false,
        persistence_required: true,
        reason,
        state,
    })
}

fn select_slot(
    mut state: State,
    slot: u8,
    mode: u8,
    trial: bool,
    nonce: u64,
    safe_mask: Option<u8>,
) -> Result<Decision, Error> {
    if nonce == 0 {
        return Err(Error::TransitionNonce);
    }
    state.generation = next_generation(&state)?;
    state.flags = (state.flags | STATE_INFLIGHT) & !(STATE_RECOVERY_REQUESTED | STATE_SAFE_REQUESTED);
    state.current_mode = mode;
    state.boot_nonce = nonce;
    state.inflight_generation = state.generation;
    state.inflight_slot = slot;
    state.inflight_mode = mode;
    if let Some(value) = safe_mask {
        state.safe_attempted_mask = value;
    }
    state.evidence_sequence = state.evidence_sequence.wrapping_add(1);
    Ok(Decision {
        mode,
        slot,
        trial,
        persistence_required: true,
        reason: 0,
        state,
    })
}

pub fn select_boot(
    policy: &Bundle<'_>,
    state: &State,
    requested_mode: u8,
    physical_presence: bool,
    boot_nonce: u64,
    state_authenticated: bool,
    state_writable: bool,
) -> Result<Decision, Error> {
    validate_state_for_policy(policy, state)?;
    if !state_authenticated {
        return Err(Error::TransitionStateAuth);
    }
    if state.flags & STATE_INFLIGHT != 0 {
        return Err(Error::TransitionInflight);
    }
    if !state_writable {
        return Ok(Decision {
            mode: MODE_RECOVERY,
            slot: 0,
            trial: false,
            persistence_required: false,
            reason: FAIL_STATE_INVALID,
            state: *state,
        });
    }
    let mut next = *state;
    let mut mode = requested_mode;
    if state.flags & STATE_RECOVERY_REQUESTED != 0 {
        mode = MODE_RECOVERY;
    } else if state.flags & STATE_SAFE_REQUESTED != 0 {
        mode = MODE_SAFE;
    } else if mode == 0 {
        mode = MODE_NORMAL;
    }
    mode_bit(mode)?;
    if mode == MODE_FIRMWARE {
        if !physical_presence {
            return Err(Error::TransitionPhysicalPresence);
        }
        next.generation = next_generation(&next)?;
        next.current_mode = MODE_FIRMWARE;
        next.evidence_sequence = next.evidence_sequence.wrapping_add(1);
        return Ok(Decision {
            mode,
            slot: 0,
            trial: false,
            persistence_required: true,
            reason: 0,
            state: next,
        });
    }
    if mode == MODE_RECOVERY {
        return recovery_decision(next, next.last_failure);
    }
    if mode == MODE_NORMAL && next.pending_slot != 0 {
        let slot = next.pending_slot;
        if eligible(policy, &next, slot, false)? && attempts(&next, slot) > 0 {
            let remaining = attempts(&next, slot) - 1;
            set_attempts(&mut next, slot, remaining);
            return select_slot(next, slot, mode, true, boot_nonce, None);
        }
        let bit = slot_bit(slot)?;
        next.pending_slot = 0;
        next.unbootable_mask |= bit;
        next.known_good_mask &= !bit;
        next.last_failure = FAIL_ATTEMPT_EXHAUSTED;
        mode = MODE_PREVIOUS;
    }
    if mode == MODE_SAFE {
        let candidates = [next.active_slot, 3 - next.active_slot];
        for slot in candidates {
            let bit = slot_bit(slot)?;
            if eligible(policy, &next, slot, true)? && next.safe_attempted_mask & bit == 0 {
                return select_slot(next, slot, mode, false, boot_nonce, Some(next.safe_attempted_mask | bit));
            }
        }
        return recovery_decision(next, FAIL_ATTEMPT_EXHAUSTED);
    }
    let candidates = if mode == MODE_PREVIOUS {
        [3 - next.active_slot, next.active_slot]
    } else {
        [next.active_slot, 3 - next.active_slot]
    };
    for slot in candidates {
        if eligible(policy, &next, slot, true)? {
            return select_slot(next, slot, mode, false, boot_nonce, None);
        }
    }
    recovery_decision(next, FAIL_ATTEMPT_EXHAUSTED)
}

pub fn report_boot_success(
    policy: &Bundle<'_>,
    state: &State,
    receipt: &SuccessReceipt,
) -> Result<State, Error> {
    validate_state_for_policy(policy, state)?;
    if !receipt.authenticated {
        return Err(Error::ReceiptAuth);
    }
    if state.flags & STATE_INFLIGHT == 0 {
        return Err(Error::ReceiptInflight);
    }
    if receipt.generation != state.inflight_generation
        || receipt.slot != state.inflight_slot
        || receipt.mode != state.inflight_mode
        || receipt.boot_nonce != state.boot_nonce
    {
        return Err(Error::ReceiptBinding);
    }
    let mut next = *state;
    let bit = slot_bit(receipt.slot)?;
    let pending_success = next.pending_slot == receipt.slot;
    next.flags &= !(STATE_INFLIGHT | STATE_RECOVERY_REQUESTED | STATE_SAFE_REQUESTED);
    next.generation = next_generation(&next)?;
    next.minimum_secure_version = core::cmp::max(next.minimum_secure_version, policy.minimum_secure_version);
    next.active_slot = receipt.slot;
    if pending_success {
        next.pending_slot = 0;
    }
    next.known_good_mask |= bit;
    next.unbootable_mask &= !bit;
    set_attempts(&mut next, receipt.slot, policy.max_attempts);
    next.current_mode = receipt.mode;
    next.last_failure = 0;
    next.boot_nonce = 0;
    next.inflight_generation = 0;
    next.inflight_slot = 0;
    next.inflight_mode = 0;
    next.last_success_slot = receipt.slot;
    next.last_success_generation = next.generation;
    next.policy_version = policy.bundle_version;
    next.evidence_sequence = next.evidence_sequence.wrapping_add(1);
    Ok(next)
}

fn failure_rule(policy: &Bundle<'_>, failure_id: u16) -> Result<(u16, u16, u16), Error> {
    if !(1..=FAILURE_COUNT as u16).contains(&failure_id) {
        return Err(Error::FailureReceiptId);
    }
    let offset = FAILURE_OFFSET + usize::from(failure_id - 1) * FAILURE_BYTES;
    Ok((u16_at(policy.raw, offset + 2)?, u16_at(policy.raw, offset + 4)?, u16_at(policy.raw, offset + 6)?))
}

pub fn report_boot_failure(
    policy: &Bundle<'_>,
    state: &State,
    failure_id: u16,
    authenticated: bool,
) -> Result<FailureDecision, Error> {
    validate_state_for_policy(policy, state)?;
    if !authenticated {
        return Err(Error::FailureReceiptAuth);
    }
    if state.flags & STATE_INFLIGHT == 0 {
        return Err(Error::FailureReceiptInflight);
    }
    let (mut action, fallback, rule_flags) = failure_rule(policy, failure_id)?;
    let mut next = *state;
    let slot = next.inflight_slot;
    let bit = slot_bit(slot)?;
    let trial = next.pending_slot == slot && next.known_good_mask & bit == 0;
    if rule_flags & FAILURE_MARK_UNBOOTABLE != 0 {
        next.unbootable_mask |= bit;
        next.known_good_mask &= !bit;
    }
    if rule_flags & FAILURE_CLEAR_PENDING != 0 && next.pending_slot == slot {
        next.pending_slot = 0;
    }
    if action == ACTION_RETRY_CANDIDATE && (!trial || attempts(&next, slot) == 0) {
        action = fallback;
    }
    if action == ACTION_SAFE && next.safe_attempted_mask & bit != 0 {
        action = fallback;
    }
    if action == ACTION_PREVIOUS {
        let other = 3 - slot;
        if !eligible(policy, &next, other, true)? {
            action = ACTION_RECOVERY;
        }
    }
    next.flags &= !STATE_INFLIGHT;
    next.generation = next_generation(&next)?;
    next.current_mode = match action {
        ACTION_RETRY_CANDIDATE => MODE_NORMAL,
        ACTION_SAFE => MODE_SAFE,
        ACTION_PREVIOUS => MODE_PREVIOUS,
        ACTION_RECOVERY | ACTION_HALT => MODE_RECOVERY,
        ACTION_FIRMWARE => MODE_FIRMWARE,
        _ => return Err(Error::FailureRule),
    };
    next.last_failure = failure_id;
    next.boot_nonce = 0;
    next.inflight_generation = 0;
    next.inflight_slot = 0;
    next.inflight_mode = 0;
    next.evidence_sequence = next.evidence_sequence.wrapping_add(1);
    Ok(FailureDecision { action, state: next })
}

pub fn authorize_activation(bundle: &Bundle<'_>, context: &ActivationContext) -> Result<(), Error> {
    let checks = [
        (context.outer_role == 3, Error::ActivationRole),
        (context.outer_artifact_version == bundle.bundle_version, Error::ActivationVersion),
        (context.outer_payload_digest_verified, Error::ActivationOuterPayloadDigest),
        (context.outer_file_digest_verified, Error::ActivationOuterFileDigest),
        (context.outer_signature_verified, Error::ActivationOuterSignature),
        (context.inner_signature_verified, Error::ActivationInnerSignature),
        (context.manifest_signature_verified, Error::ActivationManifestSignature),
        (context.state_authenticated, Error::ActivationStateAuth),
        (context.state_generation_monotonic, Error::ActivationStateGeneration),
        (context.version_floor_persisted, Error::ActivationVersionFloor),
        (context.manifest_and_components_verified, Error::ActivationComponents),
        (
            context.pbp_major == bundle.required_pbp_major && context.pbp_minor >= bundle.minimum_pbp_minor,
            Error::ActivationPbp,
        ),
        (
            context.kernel_abi_major == bundle.required_kernel_abi_major
                && context.kernel_abi_minor >= bundle.minimum_kernel_abi_minor,
            Error::ActivationKernelAbi,
        ),
        (context.offline_path, Error::ActivationOffline),
        (context.pdc_disabled, Error::ActivationPdcDisabled),
        (context.pooleglyph_independent, Error::ActivationPooleGlyphIndependent),
        (context.serial_or_gop_software_path, Error::ActivationDisplayPath),
        (context.transaction_capacity_verified, Error::ActivationTransactionCapacity),
        (context.evidence_preservation_ready, Error::ActivationEvidence),
        (context.rollback_available, Error::ActivationRollback),
        (context.state_writable, Error::ActivationStateWritable),
    ];
    for (passed, error) in checks {
        if !passed {
            return Err(error);
        }
    }
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    const POLICY: &[u8] = include_bytes!("../../../specs/fixtures/prec1-canonical.bin");
    const STATE: &[u8] = include_bytes!("../../../specs/fixtures/prec1-canonical-state.bin");

    #[test]
    fn canonical_policy_and_state_parse() {
        let policy = parse(POLICY).expect("canonical policy");
        let state = parse_state(STATE).expect("canonical state");
        validate_state_for_policy(&policy, &state).expect("policy state binding");
        assert_eq!(policy.bundle_version, 1);
        assert_eq!(state.pending_slot, 1);
    }

    #[test]
    fn candidate_attempt_is_decremented_before_handoff() {
        let policy = parse(POLICY).expect("canonical policy");
        let state = parse_state(STATE).expect("canonical state");
        let decision = select_boot(&policy, &state, MODE_NORMAL, false, 0xA002, true, true)
            .expect("trial selection");
        assert!(decision.trial);
        assert!(decision.persistence_required);
        assert_eq!(decision.slot, 1);
        assert_eq!(decision.state.attempts_a, 2);
        assert_eq!(decision.state.flags & STATE_INFLIGHT, STATE_INFLIGHT);
    }

    #[test]
    fn matching_authenticated_success_promotes_candidate() {
        let policy = parse(POLICY).expect("canonical policy");
        let state = parse_state(STATE).expect("canonical state");
        let decision = select_boot(&policy, &state, MODE_NORMAL, false, 0xA002, true, true)
            .expect("trial selection");
        let receipt = SuccessReceipt {
            authenticated: true,
            generation: decision.state.generation,
            slot: decision.slot,
            mode: decision.mode,
            boot_nonce: decision.state.boot_nonce,
        };
        let promoted = report_boot_success(&policy, &decision.state, &receipt).expect("success");
        assert_eq!(promoted.active_slot, 1);
        assert_eq!(promoted.pending_slot, 0);
        assert_eq!(promoted.known_good_mask, 0x3);
        assert_eq!(promoted.flags & STATE_INFLIGHT, 0);
    }
}
