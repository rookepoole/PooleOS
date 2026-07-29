#![no_std]
#![deny(warnings)]

use core::fmt;
use sha2::{Digest, Sha256};

pub mod backend;

pub const CONTRACT_ID: &str = "PBTRUST1";
pub const POLICY_MAGIC: [u8; 8] = *b"PBTP1\0\0\0";
pub const STATE_MAGIC: [u8; 8] = *b"PBTS1\0\0\0";
pub const MAJOR_VERSION: u16 = 1;
pub const MINOR_VERSION: u16 = 0;
pub const POLICY_BYTES: usize = 320;
pub const STATE_BYTES: usize = 256;
pub const POLICY_BODY_BYTES: usize = 224;
pub const STATE_BODY_BYTES: usize = 224;
pub const SIGNATURE_CAPACITY: usize = 64;
pub const ARTIFACT_ROLE_MASK: u32 = 0x7f;
pub const MAX_SIGNERS: u16 = 8;

pub const POLICY_FLAG_DEVELOPMENT_UNSIGNED: u16 = 1 << 0;
pub const POLICY_FLAG_SIGNED: u16 = 1 << 1;
const POLICY_KNOWN_FLAGS: u16 = POLICY_FLAG_DEVELOPMENT_UNSIGNED | POLICY_FLAG_SIGNED;

pub const STATE_FLAG_DEVELOPMENT_CANDIDATE: u16 = 1 << 0;
pub const STATE_FLAG_COMMITTED: u16 = 1 << 1;
pub const STATE_FLAG_AUTHENTICATED_BACKEND: u16 = 1 << 2;
const STATE_KNOWN_FLAGS: u16 =
    STATE_FLAG_DEVELOPMENT_CANDIDATE | STATE_FLAG_COMMITTED | STATE_FLAG_AUTHENTICATED_BACKEND;
pub const COPY_COUNT: u8 = 2;
pub const COMMIT_COMPLETE: u16 = 1;

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum Error {
    PolicyTruncated,
    PolicySize,
    PolicyMagic,
    PolicyVersion,
    PolicyFlags,
    PolicyNumbers,
    PolicyRoleMask,
    PolicySignerShape,
    PolicyDigest,
    PolicyIdentifier,
    PolicyBodyDigest,
    PolicySignature,
    StateTruncated,
    StateSize,
    StateMagic,
    StateVersion,
    StateFlags,
    StateCopy,
    StateCommit,
    StateAuthProfile,
    StateNumbers,
    StateDigest,
    StatePrevious,
    StateBodyDigest,
    BindingManifest,
    BindingKernel,
    BindingRetainedSet,
    BindingRevocationSet,
    BindingRoleMask,
    BindingPolicyState,
    BindingStateManifest,
    BindingStateKernel,
    BindingStateRetainedSet,
    BindingPolicyVersion,
    RollbackManifestVersion,
    RollbackSecureVersion,
    RollbackStateGeneration,
    RollbackTrustEpoch,
    PolicyUnsigned,
    PolicyAuthentication,
    PolicyThreshold,
    PolicyRevocation,
    StateDevelopmentCandidate,
    StateAuthentication,
    StateMonotonicity,
    StateBackendWritable,
    SecureBootState,
    UnexpectedAuthority,
}

impl Error {
    pub const fn code(self) -> &'static str {
        match self {
            Self::PolicyTruncated => "pbtrust_policy_truncated",
            Self::PolicySize => "pbtrust_policy_size",
            Self::PolicyMagic => "pbtrust_policy_magic",
            Self::PolicyVersion => "pbtrust_policy_version",
            Self::PolicyFlags => "pbtrust_policy_flags",
            Self::PolicyNumbers => "pbtrust_policy_numbers",
            Self::PolicyRoleMask => "pbtrust_policy_role_mask",
            Self::PolicySignerShape => "pbtrust_policy_signer_shape",
            Self::PolicyDigest => "pbtrust_policy_digest",
            Self::PolicyIdentifier => "pbtrust_policy_identifier",
            Self::PolicyBodyDigest => "pbtrust_policy_body_digest",
            Self::PolicySignature => "pbtrust_policy_signature",
            Self::StateTruncated => "pbtrust_state_truncated",
            Self::StateSize => "pbtrust_state_size",
            Self::StateMagic => "pbtrust_state_magic",
            Self::StateVersion => "pbtrust_state_version",
            Self::StateFlags => "pbtrust_state_flags",
            Self::StateCopy => "pbtrust_state_copy",
            Self::StateCommit => "pbtrust_state_commit",
            Self::StateAuthProfile => "pbtrust_state_auth_profile",
            Self::StateNumbers => "pbtrust_state_numbers",
            Self::StateDigest => "pbtrust_state_digest",
            Self::StatePrevious => "pbtrust_state_previous",
            Self::StateBodyDigest => "pbtrust_state_body_digest",
            Self::BindingManifest => "pbtrust_binding_manifest",
            Self::BindingKernel => "pbtrust_binding_kernel",
            Self::BindingRetainedSet => "pbtrust_binding_retained_set",
            Self::BindingRevocationSet => "pbtrust_binding_revocation_set",
            Self::BindingRoleMask => "pbtrust_binding_role_mask",
            Self::BindingPolicyState => "pbtrust_binding_policy_state",
            Self::BindingStateManifest => "pbtrust_binding_state_manifest",
            Self::BindingStateKernel => "pbtrust_binding_state_kernel",
            Self::BindingStateRetainedSet => "pbtrust_binding_state_retained_set",
            Self::BindingPolicyVersion => "pbtrust_binding_policy_version",
            Self::RollbackManifestVersion => "pbtrust_rollback_manifest_version",
            Self::RollbackSecureVersion => "pbtrust_rollback_secure_version",
            Self::RollbackStateGeneration => "pbtrust_rollback_state_generation",
            Self::RollbackTrustEpoch => "pbtrust_rollback_trust_epoch",
            Self::PolicyUnsigned => "pbtrust_policy_unsigned",
            Self::PolicyAuthentication => "pbtrust_policy_authentication",
            Self::PolicyThreshold => "pbtrust_policy_threshold",
            Self::PolicyRevocation => "pbtrust_policy_revocation",
            Self::StateDevelopmentCandidate => "pbtrust_state_development_candidate",
            Self::StateAuthentication => "pbtrust_state_authentication",
            Self::StateMonotonicity => "pbtrust_state_monotonicity",
            Self::StateBackendWritable => "pbtrust_state_backend_writable",
            Self::SecureBootState => "pbtrust_secure_boot_state",
            Self::UnexpectedAuthority => "pbtrust_unexpected_authority",
        }
    }
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct Policy<'a> {
    pub flags: u16,
    pub policy_version: u64,
    pub trust_epoch: u64,
    pub minimum_secure_version: u64,
    pub minimum_state_generation: u64,
    pub artifact_role_mask: u32,
    pub signer_threshold: u16,
    pub signer_count: u16,
    pub auth_profile: u16,
    pub signature_bytes: u16,
    pub manifest_sha256: [u8; 32],
    pub kernel_sha256: [u8; 32],
    pub retained_set_sha256: [u8; 32],
    pub revocation_set_sha256: [u8; 32],
    pub root_set_id: [u8; 16],
    pub signer_set_id: [u8; 16],
    pub body_sha256: [u8; 32],
    pub raw: &'a [u8],
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct State<'a> {
    pub flags: u16,
    pub copy_index: u8,
    pub auth_profile: u16,
    pub state_generation: u64,
    pub store_epoch: u64,
    pub minimum_secure_version: u64,
    pub accepted_manifest_version: u64,
    pub accepted_policy_version: u64,
    pub policy_sha256: [u8; 32],
    pub manifest_sha256: [u8; 32],
    pub kernel_sha256: [u8; 32],
    pub retained_set_sha256: [u8; 32],
    pub previous_state_sha256: [u8; 32],
    pub body_sha256: [u8; 32],
    pub raw: &'a [u8],
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct ObservedBoot {
    pub manifest_sha256: [u8; 32],
    pub kernel_sha256: [u8; 32],
    pub retained_set_sha256: [u8; 32],
    pub revocation_set_sha256: [u8; 32],
    pub manifest_version: u64,
    pub minimum_secure_version: u64,
    pub artifact_role_mask: u32,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct VerificationEvidence {
    pub policy_signature_verified: bool,
    pub policy_threshold_verified: bool,
    pub revocation_state_authenticated: bool,
    pub policy_not_revoked: bool,
    pub state_authenticated: bool,
    pub state_monotonic: bool,
    pub state_backend_writable: bool,
    pub secure_boot_state_verified: bool,
}

impl VerificationEvidence {
    pub const fn development() -> Self {
        Self {
            policy_signature_verified: false,
            policy_threshold_verified: false,
            revocation_state_authenticated: false,
            policy_not_revoked: false,
            state_authenticated: false,
            state_monotonic: false,
            state_backend_writable: false,
            secure_boot_state_verified: false,
        }
    }

    pub const fn synthetic_qualified() -> Self {
        Self {
            policy_signature_verified: true,
            policy_threshold_verified: true,
            revocation_state_authenticated: true,
            policy_not_revoked: true,
            state_authenticated: true,
            state_monotonic: true,
            state_backend_writable: true,
            secure_boot_state_verified: true,
        }
    }
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct AuthorizedTrust {
    pub policy_sha256: [u8; 32],
    pub state_sha256: [u8; 32],
    pub policy_version: u64,
    pub state_generation: u64,
    pub trust_epoch: u64,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct DevelopmentSummary {
    pub policy_bytes: u16,
    pub state_bytes: u16,
    pub binding_count: u8,
    pub denial_count: u8,
    pub policy_sha256: [u8; 32],
    pub state_sha256: [u8; 32],
    pub denial: &'static str,
    pub authority_grants: u8,
    pub state_writes: u8,
}

pub struct DigestHex<'a>(&'a [u8; 32]);

impl<'a> DigestHex<'a> {
    pub const fn new(digest: &'a [u8; 32]) -> Self {
        Self(digest)
    }
}

impl fmt::Display for DigestHex<'_> {
    fn fmt(&self, formatter: &mut fmt::Formatter<'_>) -> fmt::Result {
        for byte in self.0 {
            write!(formatter, "{byte:02X}")?;
        }
        Ok(())
    }
}

fn bytes<const N: usize>(data: &[u8], offset: usize, error: Error) -> Result<[u8; N], Error> {
    data.get(offset..offset + N)
        .ok_or(error)?
        .try_into()
        .map_err(|_| error)
}

fn u16_at(data: &[u8], offset: usize, error: Error) -> Result<u16, Error> {
    Ok(u16::from_le_bytes(bytes(data, offset, error)?))
}

fn u32_at(data: &[u8], offset: usize, error: Error) -> Result<u32, Error> {
    Ok(u32::from_le_bytes(bytes(data, offset, error)?))
}

fn u64_at(data: &[u8], offset: usize, error: Error) -> Result<u64, Error> {
    Ok(u64::from_le_bytes(bytes(data, offset, error)?))
}

fn all_zero(data: &[u8]) -> bool {
    data.iter().all(|byte| *byte == 0)
}

pub fn sha256(data: &[u8]) -> [u8; 32] {
    let result = Sha256::digest(data);
    let mut output = [0u8; 32];
    output.copy_from_slice(&result);
    output
}

pub fn parse_policy(data: &[u8]) -> Result<Policy<'_>, Error> {
    if data.len() < POLICY_BYTES {
        return Err(Error::PolicyTruncated);
    }
    if data.len() != POLICY_BYTES
        || u16_at(data, 12, Error::PolicyTruncated)? as usize != POLICY_BYTES
    {
        return Err(Error::PolicySize);
    }
    if data[..8] != POLICY_MAGIC {
        return Err(Error::PolicyMagic);
    }
    if u16_at(data, 8, Error::PolicyTruncated)? != MAJOR_VERSION
        || u16_at(data, 10, Error::PolicyTruncated)? != MINOR_VERSION
    {
        return Err(Error::PolicyVersion);
    }
    let flags = u16_at(data, 14, Error::PolicyTruncated)?;
    if flags & !POLICY_KNOWN_FLAGS != 0 || flags.count_ones() != 1 || flags == 0 {
        return Err(Error::PolicyFlags);
    }
    let policy_version = u64_at(data, 16, Error::PolicyTruncated)?;
    let trust_epoch = u64_at(data, 24, Error::PolicyTruncated)?;
    let minimum_secure_version = u64_at(data, 32, Error::PolicyTruncated)?;
    let minimum_state_generation = u64_at(data, 40, Error::PolicyTruncated)?;
    if policy_version == 0
        || trust_epoch == 0
        || minimum_secure_version == 0
        || minimum_state_generation == 0
    {
        return Err(Error::PolicyNumbers);
    }
    let artifact_role_mask = u32_at(data, 48, Error::PolicyTruncated)?;
    if artifact_role_mask != ARTIFACT_ROLE_MASK {
        return Err(Error::PolicyRoleMask);
    }
    let signer_threshold = u16_at(data, 52, Error::PolicyTruncated)?;
    let signer_count = u16_at(data, 54, Error::PolicyTruncated)?;
    let auth_profile = u16_at(data, 56, Error::PolicyTruncated)?;
    let signature_bytes = u16_at(data, 58, Error::PolicyTruncated)?;
    if u32_at(data, 60, Error::PolicyTruncated)? != 0 {
        return Err(Error::PolicySignerShape);
    }
    let manifest_sha256 = bytes(data, 64, Error::PolicyTruncated)?;
    let kernel_sha256 = bytes(data, 96, Error::PolicyTruncated)?;
    let retained_set_sha256 = bytes(data, 128, Error::PolicyTruncated)?;
    let revocation_set_sha256 = bytes(data, 160, Error::PolicyTruncated)?;
    if [
        &manifest_sha256[..],
        &kernel_sha256[..],
        &retained_set_sha256[..],
        &revocation_set_sha256[..],
    ]
    .iter()
    .any(|value| all_zero(value))
    {
        return Err(Error::PolicyDigest);
    }
    let root_set_id = bytes(data, 192, Error::PolicyTruncated)?;
    let signer_set_id = bytes(data, 208, Error::PolicyTruncated)?;
    let body_sha256 = bytes(data, 224, Error::PolicyTruncated)?;
    if sha256(&data[..POLICY_BODY_BYTES]) != body_sha256 {
        return Err(Error::PolicyBodyDigest);
    }
    let signature = &data[256..POLICY_BYTES];
    if flags == POLICY_FLAG_DEVELOPMENT_UNSIGNED {
        if signer_threshold != 0
            || signer_count != 0
            || auth_profile != 0
            || signature_bytes != 0
            || !all_zero(&root_set_id)
            || !all_zero(&signer_set_id)
            || !all_zero(signature)
        {
            return Err(Error::PolicySignerShape);
        }
    } else {
        let signature_bytes = signature_bytes as usize;
        if signer_threshold == 0
            || signer_count == 0
            || signer_count > MAX_SIGNERS
            || signer_threshold > signer_count
            || auth_profile == 0
            || signature_bytes == 0
            || signature_bytes > SIGNATURE_CAPACITY
            || all_zero(&root_set_id)
            || all_zero(&signer_set_id)
        {
            return Err(Error::PolicySignerShape);
        }
        if all_zero(&signature[..signature_bytes]) || !all_zero(&signature[signature_bytes..]) {
            return Err(Error::PolicySignature);
        }
    }
    Ok(Policy {
        flags,
        policy_version,
        trust_epoch,
        minimum_secure_version,
        minimum_state_generation,
        artifact_role_mask,
        signer_threshold,
        signer_count,
        auth_profile,
        signature_bytes,
        manifest_sha256,
        kernel_sha256,
        retained_set_sha256,
        revocation_set_sha256,
        root_set_id,
        signer_set_id,
        body_sha256,
        raw: data,
    })
}

pub fn parse_state(data: &[u8]) -> Result<State<'_>, Error> {
    if data.len() < STATE_BYTES {
        return Err(Error::StateTruncated);
    }
    if data.len() != STATE_BYTES || u16_at(data, 12, Error::StateTruncated)? as usize != STATE_BYTES
    {
        return Err(Error::StateSize);
    }
    if data[..8] != STATE_MAGIC {
        return Err(Error::StateMagic);
    }
    if u16_at(data, 8, Error::StateTruncated)? != MAJOR_VERSION
        || u16_at(data, 10, Error::StateTruncated)? != MINOR_VERSION
    {
        return Err(Error::StateVersion);
    }
    let flags = u16_at(data, 14, Error::StateTruncated)?;
    let profile_flags =
        flags & (STATE_FLAG_DEVELOPMENT_CANDIDATE | STATE_FLAG_AUTHENTICATED_BACKEND);
    if flags & !STATE_KNOWN_FLAGS != 0
        || flags & STATE_FLAG_COMMITTED == 0
        || profile_flags.count_ones() != 1
    {
        return Err(Error::StateFlags);
    }
    let copy_index = data[16];
    if copy_index >= COPY_COUNT || data[17] != COPY_COUNT {
        return Err(Error::StateCopy);
    }
    if u16_at(data, 18, Error::StateTruncated)? != COMMIT_COMPLETE {
        return Err(Error::StateCommit);
    }
    let auth_profile = u16_at(data, 20, Error::StateTruncated)?;
    if u16_at(data, 22, Error::StateTruncated)? != 0
        || (profile_flags == STATE_FLAG_DEVELOPMENT_CANDIDATE && auth_profile != 0)
        || (profile_flags == STATE_FLAG_AUTHENTICATED_BACKEND && auth_profile == 0)
    {
        return Err(Error::StateAuthProfile);
    }
    let state_generation = u64_at(data, 24, Error::StateTruncated)?;
    let store_epoch = u64_at(data, 32, Error::StateTruncated)?;
    let minimum_secure_version = u64_at(data, 40, Error::StateTruncated)?;
    let accepted_manifest_version = u64_at(data, 48, Error::StateTruncated)?;
    let accepted_policy_version = u64_at(data, 56, Error::StateTruncated)?;
    if state_generation == 0
        || store_epoch == 0
        || minimum_secure_version == 0
        || accepted_manifest_version == 0
        || accepted_policy_version == 0
        || accepted_manifest_version < minimum_secure_version
    {
        return Err(Error::StateNumbers);
    }
    let policy_sha256 = bytes(data, 64, Error::StateTruncated)?;
    let manifest_sha256 = bytes(data, 96, Error::StateTruncated)?;
    let kernel_sha256 = bytes(data, 128, Error::StateTruncated)?;
    let retained_set_sha256 = bytes(data, 160, Error::StateTruncated)?;
    if [
        &policy_sha256[..],
        &manifest_sha256[..],
        &kernel_sha256[..],
        &retained_set_sha256[..],
    ]
    .iter()
    .any(|value| all_zero(value))
    {
        return Err(Error::StateDigest);
    }
    let previous_state_sha256 = bytes(data, 192, Error::StateTruncated)?;
    if (state_generation == 1) != all_zero(&previous_state_sha256) {
        return Err(Error::StatePrevious);
    }
    let body_sha256 = bytes(data, 224, Error::StateTruncated)?;
    if sha256(&data[..STATE_BODY_BYTES]) != body_sha256 {
        return Err(Error::StateBodyDigest);
    }
    Ok(State {
        flags,
        copy_index,
        auth_profile,
        state_generation,
        store_epoch,
        minimum_secure_version,
        accepted_manifest_version,
        accepted_policy_version,
        policy_sha256,
        manifest_sha256,
        kernel_sha256,
        retained_set_sha256,
        previous_state_sha256,
        body_sha256,
        raw: data,
    })
}

pub fn authorize(
    policy: &Policy<'_>,
    state: &State<'_>,
    observed: &ObservedBoot,
    evidence: &VerificationEvidence,
) -> Result<AuthorizedTrust, Error> {
    if policy.manifest_sha256 != observed.manifest_sha256 {
        return Err(Error::BindingManifest);
    }
    if policy.kernel_sha256 != observed.kernel_sha256 {
        return Err(Error::BindingKernel);
    }
    if policy.retained_set_sha256 != observed.retained_set_sha256 {
        return Err(Error::BindingRetainedSet);
    }
    if policy.revocation_set_sha256 != observed.revocation_set_sha256 {
        return Err(Error::BindingRevocationSet);
    }
    if policy.artifact_role_mask != observed.artifact_role_mask {
        return Err(Error::BindingRoleMask);
    }
    let policy_sha256 = sha256(policy.raw);
    if state.policy_sha256 != policy_sha256 {
        return Err(Error::BindingPolicyState);
    }
    if state.manifest_sha256 != observed.manifest_sha256 {
        return Err(Error::BindingStateManifest);
    }
    if state.kernel_sha256 != observed.kernel_sha256 {
        return Err(Error::BindingStateKernel);
    }
    if state.retained_set_sha256 != observed.retained_set_sha256 {
        return Err(Error::BindingStateRetainedSet);
    }
    if state.accepted_policy_version != policy.policy_version {
        return Err(Error::BindingPolicyVersion);
    }
    if state.accepted_manifest_version != observed.manifest_version {
        return Err(Error::RollbackManifestVersion);
    }
    if observed.minimum_secure_version < policy.minimum_secure_version
        || observed.minimum_secure_version < state.minimum_secure_version
        || observed.manifest_version < observed.minimum_secure_version
    {
        return Err(Error::RollbackSecureVersion);
    }
    if state.state_generation < policy.minimum_state_generation {
        return Err(Error::RollbackStateGeneration);
    }
    if state.store_epoch < policy.trust_epoch {
        return Err(Error::RollbackTrustEpoch);
    }
    if policy.flags == POLICY_FLAG_DEVELOPMENT_UNSIGNED {
        return Err(Error::PolicyUnsigned);
    }
    if !evidence.policy_signature_verified {
        return Err(Error::PolicyAuthentication);
    }
    if !evidence.policy_threshold_verified {
        return Err(Error::PolicyThreshold);
    }
    if !evidence.revocation_state_authenticated || !evidence.policy_not_revoked {
        return Err(Error::PolicyRevocation);
    }
    if state.flags & STATE_FLAG_DEVELOPMENT_CANDIDATE != 0 {
        return Err(Error::StateDevelopmentCandidate);
    }
    if !evidence.state_authenticated {
        return Err(Error::StateAuthentication);
    }
    if !evidence.state_monotonic {
        return Err(Error::StateMonotonicity);
    }
    if !evidence.state_backend_writable {
        return Err(Error::StateBackendWritable);
    }
    if !evidence.secure_boot_state_verified {
        return Err(Error::SecureBootState);
    }
    Ok(AuthorizedTrust {
        policy_sha256,
        state_sha256: sha256(state.raw),
        policy_version: policy.policy_version,
        state_generation: state.state_generation,
        trust_epoch: policy.trust_epoch,
    })
}

pub fn validate_development(
    policy_bytes: &[u8],
    state_bytes: &[u8],
    observed: &ObservedBoot,
) -> Result<DevelopmentSummary, Error> {
    let policy = parse_policy(policy_bytes)?;
    let state = parse_state(state_bytes)?;
    match authorize(
        &policy,
        &state,
        observed,
        &VerificationEvidence::development(),
    ) {
        Err(Error::PolicyUnsigned) => Ok(DevelopmentSummary {
            policy_bytes: POLICY_BYTES as u16,
            state_bytes: STATE_BYTES as u16,
            binding_count: 14,
            denial_count: 1,
            policy_sha256: sha256(policy_bytes),
            state_sha256: sha256(state_bytes),
            denial: Error::PolicyUnsigned.code(),
            authority_grants: 0,
            state_writes: 0,
        }),
        Err(error) => Err(error),
        Ok(_) => Err(Error::UnexpectedAuthority),
    }
}

#[cfg(test)]
mod tests {
    extern crate std;

    use super::*;

    const MANIFEST: [u8; 32] = [0x11; 32];
    const KERNEL: [u8; 32] = [0x22; 32];
    const RETAINED: [u8; 32] = [0x33; 32];
    const REVOCATION: [u8; 32] = [0x44; 32];

    fn policy(signed: bool) -> [u8; POLICY_BYTES] {
        let mut output = [0u8; POLICY_BYTES];
        output[..8].copy_from_slice(&POLICY_MAGIC);
        output[8..10].copy_from_slice(&MAJOR_VERSION.to_le_bytes());
        output[10..12].copy_from_slice(&MINOR_VERSION.to_le_bytes());
        output[12..14].copy_from_slice(&(POLICY_BYTES as u16).to_le_bytes());
        output[14..16].copy_from_slice(
            &(if signed {
                POLICY_FLAG_SIGNED
            } else {
                POLICY_FLAG_DEVELOPMENT_UNSIGNED
            })
            .to_le_bytes(),
        );
        output[16..24].copy_from_slice(&1u64.to_le_bytes());
        output[24..32].copy_from_slice(&1u64.to_le_bytes());
        output[32..40].copy_from_slice(&1u64.to_le_bytes());
        output[40..48].copy_from_slice(&1u64.to_le_bytes());
        output[48..52].copy_from_slice(&ARTIFACT_ROLE_MASK.to_le_bytes());
        output[64..96].copy_from_slice(&MANIFEST);
        output[96..128].copy_from_slice(&KERNEL);
        output[128..160].copy_from_slice(&RETAINED);
        output[160..192].copy_from_slice(&REVOCATION);
        if signed {
            output[52..54].copy_from_slice(&1u16.to_le_bytes());
            output[54..56].copy_from_slice(&1u16.to_le_bytes());
            output[56..58].copy_from_slice(&1u16.to_le_bytes());
            output[58..60].copy_from_slice(&(SIGNATURE_CAPACITY as u16).to_le_bytes());
            output[192..208].fill(0x55);
            output[208..224].fill(0x66);
            output[256..320].fill(0x77);
        }
        let digest = sha256(&output[..POLICY_BODY_BYTES]);
        output[224..256].copy_from_slice(&digest);
        output
    }

    fn state(policy_bytes: &[u8], authenticated: bool) -> [u8; STATE_BYTES] {
        let mut output = [0u8; STATE_BYTES];
        output[..8].copy_from_slice(&STATE_MAGIC);
        output[8..10].copy_from_slice(&MAJOR_VERSION.to_le_bytes());
        output[10..12].copy_from_slice(&MINOR_VERSION.to_le_bytes());
        output[12..14].copy_from_slice(&(STATE_BYTES as u16).to_le_bytes());
        let flags = STATE_FLAG_COMMITTED
            | if authenticated {
                STATE_FLAG_AUTHENTICATED_BACKEND
            } else {
                STATE_FLAG_DEVELOPMENT_CANDIDATE
            };
        output[14..16].copy_from_slice(&flags.to_le_bytes());
        output[16] = 0;
        output[17] = COPY_COUNT;
        output[18..20].copy_from_slice(&COMMIT_COMPLETE.to_le_bytes());
        output[20..22].copy_from_slice(&(u16::from(authenticated)).to_le_bytes());
        output[24..32].copy_from_slice(&1u64.to_le_bytes());
        output[32..40].copy_from_slice(&1u64.to_le_bytes());
        output[40..48].copy_from_slice(&1u64.to_le_bytes());
        output[48..56].copy_from_slice(&1u64.to_le_bytes());
        output[56..64].copy_from_slice(&1u64.to_le_bytes());
        output[64..96].copy_from_slice(&sha256(policy_bytes));
        output[96..128].copy_from_slice(&MANIFEST);
        output[128..160].copy_from_slice(&KERNEL);
        output[160..192].copy_from_slice(&RETAINED);
        let digest = sha256(&output[..STATE_BODY_BYTES]);
        output[224..256].copy_from_slice(&digest);
        output
    }

    fn observed() -> ObservedBoot {
        ObservedBoot {
            manifest_sha256: MANIFEST,
            kernel_sha256: KERNEL,
            retained_set_sha256: RETAINED,
            revocation_set_sha256: REVOCATION,
            manifest_version: 1,
            minimum_secure_version: 1,
            artifact_role_mask: ARTIFACT_ROLE_MASK,
        }
    }

    #[test]
    fn development_pair_cross_binds_then_denies_without_effects() {
        let policy = policy(false);
        let state = state(&policy, false);
        let summary = validate_development(&policy, &state, &observed()).unwrap();
        assert_eq!(summary.binding_count, 14);
        assert_eq!(summary.denial, "pbtrust_policy_unsigned");
        assert_eq!(summary.authority_grants, 0);
        assert_eq!(summary.state_writes, 0);
    }

    #[test]
    fn mutation_and_substitution_fail_closed() {
        let mut policy_bytes = policy(false);
        policy_bytes[96] ^= 1;
        assert_eq!(parse_policy(&policy_bytes), Err(Error::PolicyBodyDigest));
        let policy_bytes = policy(false);
        let mut state_bytes = state(&policy_bytes, false);
        state_bytes[96] ^= 1;
        let body = sha256(&state_bytes[..STATE_BODY_BYTES]);
        state_bytes[224..256].copy_from_slice(&body);
        assert_eq!(
            validate_development(&policy_bytes, &state_bytes, &observed()),
            Err(Error::BindingStateManifest)
        );
    }

    #[test]
    fn rollback_floors_precede_authentication() {
        let policy = policy(false);
        let mut state = state(&policy, false);
        state[48..56].copy_from_slice(&2u64.to_le_bytes());
        let body = sha256(&state[..STATE_BODY_BYTES]);
        state[224..256].copy_from_slice(&body);
        assert_eq!(
            validate_development(&policy, &state, &observed()),
            Err(Error::RollbackManifestVersion)
        );
    }

    #[test]
    fn synthetic_signed_profile_requires_every_external_evidence_gate() {
        let policy_bytes = policy(true);
        let state_bytes = state(&policy_bytes, true);
        let policy = parse_policy(&policy_bytes).unwrap();
        let state = parse_state(&state_bytes).unwrap();
        let mut evidence = VerificationEvidence::synthetic_qualified();
        evidence.state_monotonic = false;
        assert_eq!(
            authorize(&policy, &state, &observed(), &evidence),
            Err(Error::StateMonotonicity)
        );
        let result = authorize(
            &policy,
            &state,
            &observed(),
            &VerificationEvidence::synthetic_qualified(),
        )
        .unwrap();
        assert_eq!(result.policy_version, 1);
        assert_eq!(result.state_generation, 1);
    }
}
