use core::slice::from_raw_parts;

use poole_bootload::{self as bootload, artifact};
use poole_handoff::{
    self as pbp1, ARTIFACT_ENTRY_BYTES, ARTIFACT_EXECUTABLE, ARTIFACT_HASH_VERIFIED,
    ARTIFACT_KERNEL, ARTIFACT_MEASURED, ARTIFACT_SIGNATURE_VERIFIED, ARTIFACT_SYSTEM_MANIFEST,
    ARTIFACT_TRUST_POLICY, ARTIFACT_TRUST_STATE, ARTIFACT_WRITABLE, BOOT_SERVICES_EXITED,
    RECORD_LOADED_ARTIFACTS,
};

pub const CONTRACT_ID: &str = "PKREVAL1";
pub const RETAINED_FILE_COUNT: usize = 9;
pub const PROFILE_ROLE_COUNT: usize = RETAINED_FILE_COUNT + 1;
pub const RETAINED_ROLES: [u32; RETAINED_FILE_COUNT] = [
    pbp1::ARTIFACT_INITIAL_SYSTEM,
    pbp1::ARTIFACT_RECOVERY,
    pbp1::ARTIFACT_SYMBOLS,
    pbp1::ARTIFACT_MICROCODE,
    pbp1::ARTIFACT_FIRMWARE_MANIFEST,
    pbp1::ARTIFACT_POLICY_BUNDLE,
    ARTIFACT_SYSTEM_MANIFEST,
    ARTIFACT_TRUST_POLICY,
    ARTIFACT_TRUST_STATE,
];
const PROFILE_ROLES: [u32; PROFILE_ROLE_COUNT] = [
    ARTIFACT_KERNEL,
    pbp1::ARTIFACT_INITIAL_SYSTEM,
    pbp1::ARTIFACT_RECOVERY,
    pbp1::ARTIFACT_SYMBOLS,
    pbp1::ARTIFACT_MICROCODE,
    pbp1::ARTIFACT_FIRMWARE_MANIFEST,
    pbp1::ARTIFACT_POLICY_BUNDLE,
    ARTIFACT_SYSTEM_MANIFEST,
    ARTIFACT_TRUST_POLICY,
    ARTIFACT_TRUST_STATE,
];
const MANIFEST_FILE_INDEX: usize = 6;
const TRUST_POLICY_FILE_INDEX: usize = 7;
const TRUST_STATE_FILE_INDEX: usize = 8;

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum Error {
    Handoff,
    ExitState,
    ArtifactProfile,
    ArtifactFlags,
    ArtifactRange,
    ArtifactOverlap,
    FileOrder,
    FileLocator,
    FileSize,
    FileDigest,
    Manifest(bootload::Error),
    ManifestBinding,
    Inner(&'static str),
    Trust(poole_boot_trust::Error),
    UnexpectedAuthority,
}

impl Error {
    pub const fn code(self) -> &'static str {
        match self {
            Self::Handoff => "pkreval_handoff",
            Self::ExitState => "pkreval_exit_state",
            Self::ArtifactProfile => "pkreval_artifact_profile",
            Self::ArtifactFlags => "pkreval_artifact_flags",
            Self::ArtifactRange => "pkreval_artifact_range",
            Self::ArtifactOverlap => "pkreval_artifact_overlap",
            Self::FileOrder => "pkreval_file_order",
            Self::FileLocator => "pkreval_file_locator",
            Self::FileSize => "pkreval_file_size",
            Self::FileDigest => "pkreval_file_digest",
            Self::Manifest(error) => error.code(),
            Self::ManifestBinding => "pkreval_manifest_binding",
            Self::Inner(code) => code,
            Self::Trust(error) => error.code(),
            Self::UnexpectedAuthority => "pkreval_unexpected_authority",
        }
    }
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct Summary {
    pub retained_file_count: u8,
    pub artifact_count: u8,
    pub parser_count: u8,
    pub manifest_bytes: u32,
    pub retained_file_bytes: u32,
    pub retained_set_sha256: [u8; 32],
    pub policy_sha256: [u8; 32],
    pub state_sha256: [u8; 32],
    pub denial: &'static str,
    pub authority_grants: u8,
    pub actions_authorized: u8,
    pub state_writes: u8,
}

#[derive(Clone, Copy)]
struct Descriptor {
    role: u32,
    physical_base: u64,
    byte_count: u64,
    sha256: [u8; 32],
}

impl Descriptor {
    const EMPTY: Self = Self {
        role: 0,
        physical_base: 0,
        byte_count: 0,
        sha256: [0; 32],
    };
}

#[derive(Clone, Copy)]
pub struct RetainedFile<'a> {
    pub role: u32,
    pub physical_base: u64,
    pub bytes: &'a [u8],
}

fn read_u32(bytes: &[u8], offset: usize) -> Result<u32, Error> {
    let value = bytes
        .get(offset..offset + 4)
        .ok_or(Error::ArtifactProfile)?;
    Ok(u32::from_le_bytes([value[0], value[1], value[2], value[3]]))
}

fn read_u64(bytes: &[u8], offset: usize) -> Result<u64, Error> {
    let value = bytes
        .get(offset..offset + 8)
        .ok_or(Error::ArtifactProfile)?;
    Ok(u64::from_le_bytes([
        value[0], value[1], value[2], value[3], value[4], value[5], value[6], value[7],
    ]))
}

fn file_size_allowed(role: u32, byte_count: u64) -> bool {
    match role {
        pbp1::ARTIFACT_INITIAL_SYSTEM
        | pbp1::ARTIFACT_RECOVERY
        | pbp1::ARTIFACT_SYMBOLS
        | pbp1::ARTIFACT_MICROCODE
        | pbp1::ARTIFACT_FIRMWARE_MANIFEST
        | pbp1::ARTIFACT_POLICY_BUNDLE => {
            (artifact::HEADER_BYTES as u64..=artifact::MAX_FILE_BYTES as u64).contains(&byte_count)
        }
        ARTIFACT_SYSTEM_MANIFEST => {
            (1..=bootload::manifest::MAX_MANIFEST_BYTES as u64).contains(&byte_count)
        }
        ARTIFACT_TRUST_POLICY => byte_count == poole_boot_trust::POLICY_BYTES as u64,
        ARTIFACT_TRUST_STATE => byte_count == poole_boot_trust::STATE_BYTES as u64,
        _ => false,
    }
}

fn ranges_overlap(first: Descriptor, second: Descriptor) -> bool {
    first.physical_base < second.physical_base.saturating_add(second.byte_count)
        && second.physical_base < first.physical_base.saturating_add(first.byte_count)
}

fn profile_descriptors(
    handoff: &pbp1::Handoff<'_>,
) -> Result<[Descriptor; PROFILE_ROLE_COUNT], Error> {
    let core = handoff.core().map_err(|_| Error::Handoff)?;
    if core.boot_flags & BOOT_SERVICES_EXITED == 0 {
        return Err(Error::ExitState);
    }
    let record = handoff
        .record(RECORD_LOADED_ARTIFACTS)
        .ok_or(Error::ArtifactProfile)?;
    if record.descriptor.element_size != ARTIFACT_ENTRY_BYTES
        || record.descriptor.element_count != PROFILE_ROLE_COUNT
        || record.payload.len() != PROFILE_ROLE_COUNT * ARTIFACT_ENTRY_BYTES
    {
        return Err(Error::ArtifactProfile);
    }
    let mut descriptors = [Descriptor::EMPTY; PROFILE_ROLE_COUNT];
    for (index, expected_role) in PROFILE_ROLES.iter().copied().enumerate() {
        let base = index * ARTIFACT_ENTRY_BYTES;
        let role = read_u32(record.payload, base)?;
        let flags = read_u32(record.payload, base + 4)?;
        let physical_base = read_u64(record.payload, base + 8)?;
        let byte_count = read_u64(record.payload, base + 16)?;
        let virtual_base = read_u64(record.payload, base + 24)?;
        let virtual_size = read_u64(record.payload, base + 32)?;
        let entry_virtual = read_u64(record.payload, base + 40)?;
        let sha256 = record.payload[base + 48..base + 80]
            .try_into()
            .map_err(|_| Error::ArtifactProfile)?;
        if role != expected_role {
            return Err(Error::ArtifactProfile);
        }
        if flags & ARTIFACT_HASH_VERIFIED == 0
            || flags & ARTIFACT_WRITABLE != 0
            || flags
                & !(ARTIFACT_HASH_VERIFIED
                    | ARTIFACT_SIGNATURE_VERIFIED
                    | ARTIFACT_MEASURED
                    | ARTIFACT_EXECUTABLE)
                != 0
            || (index == 0) != (flags & ARTIFACT_EXECUTABLE != 0)
        {
            return Err(Error::ArtifactFlags);
        }
        if physical_base == 0
            || !physical_base.is_multiple_of(pbp1::PAGE_BYTES)
            || byte_count == 0
            || physical_base.checked_add(byte_count).is_none()
        {
            return Err(Error::ArtifactRange);
        }
        if index == 0 {
            if physical_base != core.kernel_physical_base
                || byte_count != core.kernel_physical_size
                || virtual_base != core.kernel_virtual_base
                || virtual_size != core.kernel_virtual_size
                || entry_virtual != core.kernel_entry_virtual
            {
                return Err(Error::ArtifactProfile);
            }
        } else if virtual_base != 0
            || virtual_size != 0
            || entry_virtual != 0
            || !file_size_allowed(role, byte_count)
        {
            return Err(Error::ArtifactProfile);
        }
        descriptors[index] = Descriptor {
            role,
            physical_base,
            byte_count,
            sha256,
        };
    }
    for first in 0..descriptors.len() {
        for second in first + 1..descriptors.len() {
            if ranges_overlap(descriptors[first], descriptors[second]) {
                return Err(Error::ArtifactOverlap);
            }
        }
    }
    Ok(descriptors)
}

#[inline(never)]
pub fn revalidate_development(
    handoff_bytes: &[u8],
    files: [RetainedFile<'_>; RETAINED_FILE_COUNT],
) -> Result<Summary, Error> {
    let handoff = pbp1::decode(handoff_bytes).map_err(|_| Error::Handoff)?;
    let descriptors = profile_descriptors(&handoff)?;
    let core = handoff.core().map_err(|_| Error::Handoff)?;
    let mut ordered: [&[u8]; RETAINED_FILE_COUNT] = [&[]; RETAINED_FILE_COUNT];
    let mut retained_file_bytes = 0usize;
    for (index, file) in files.iter().enumerate() {
        let descriptor = descriptors[index + 1];
        if file.role != RETAINED_ROLES[index] || descriptor.role != file.role {
            return Err(Error::FileOrder);
        }
        if file.physical_base != descriptor.physical_base {
            return Err(Error::FileLocator);
        }
        if file.bytes.len() as u64 != descriptor.byte_count {
            return Err(Error::FileSize);
        }
        if artifact::sha256(file.bytes) != descriptor.sha256 {
            return Err(Error::FileDigest);
        }
        retained_file_bytes = retained_file_bytes
            .checked_add(file.bytes.len())
            .ok_or(Error::FileSize)?;
        ordered[index] = file.bytes;
    }

    let selected_slot = u8::try_from(core.boot_slot).map_err(|_| Error::ManifestBinding)?;
    let manifest = bootload::parse_manifest(ordered[MANIFEST_FILE_INDEX], selected_slot)
        .map_err(Error::Manifest)?;
    if manifest.manifest_sha256 != descriptors[MANIFEST_FILE_INDEX + 1].sha256
        || manifest.kernel_sha256 != descriptors[0].sha256
        || manifest.kernel_image_bytes as u64 != core.kernel_virtual_size
        || manifest.artifact_count != bootload::PROFILE_ARTIFACT_COUNT
    {
        return Err(Error::ManifestBinding);
    }
    for (index, manifest_artifact) in manifest.artifacts.iter().enumerate() {
        let descriptor = descriptors[index + 1];
        if manifest_artifact.role.code() != descriptor.role
            || manifest_artifact.file_bytes as u64 != descriptor.byte_count
            || manifest_artifact.sha256 != descriptor.sha256
        {
            return Err(Error::ManifestBinding);
        }
    }

    let artifact_files: [&[u8]; poole_inner_live::ARTIFACT_COUNT] = ordered
        [..poole_inner_live::ARTIFACT_COUNT]
        .try_into()
        .map_err(|_| Error::ArtifactProfile)?;
    let inner = poole_inner_live::validate_development_set(artifact_files)
        .map_err(|failure| Error::Inner(failure.code))?;
    if inner.authority_grants != 0
        || inner.actions_authorized != 0
        || inner.state_writes != 0
        || inner.hardware_observations != 0
    {
        return Err(Error::UnexpectedAuthority);
    }
    let observed = poole_boot_trust::ObservedBoot {
        manifest_sha256: manifest.manifest_sha256,
        kernel_sha256: manifest.kernel_sha256,
        retained_set_sha256: inner.retained_set_sha256,
        revocation_set_sha256: poole_boot_trust::sha256(&[]),
        manifest_version: manifest.manifest_version,
        minimum_secure_version: manifest.minimum_secure_version,
        artifact_role_mask: poole_boot_trust::ARTIFACT_ROLE_MASK,
    };
    let trust = poole_boot_trust::validate_development(
        ordered[TRUST_POLICY_FILE_INDEX],
        ordered[TRUST_STATE_FILE_INDEX],
        &observed,
    )
    .map_err(Error::Trust)?;
    if trust.denial != poole_boot_trust::Error::PolicyUnsigned.code()
        || trust.authority_grants != 0
        || trust.state_writes != 0
    {
        return Err(Error::UnexpectedAuthority);
    }
    Ok(Summary {
        retained_file_count: RETAINED_FILE_COUNT as u8,
        artifact_count: inner.artifact_count,
        parser_count: inner.parser_count + 3,
        manifest_bytes: u32::try_from(ordered[MANIFEST_FILE_INDEX].len())
            .map_err(|_| Error::FileSize)?,
        retained_file_bytes: u32::try_from(retained_file_bytes).map_err(|_| Error::FileSize)?,
        retained_set_sha256: inner.retained_set_sha256,
        policy_sha256: trust.policy_sha256,
        state_sha256: trust.state_sha256,
        denial: trust.denial,
        authority_grants: 0,
        actions_authorized: 0,
        state_writes: 0,
    })
}

#[inline(never)]
pub fn revalidate_development_files(
    handoff_bytes: &[u8],
    files: [&[u8]; RETAINED_FILE_COUNT],
) -> Result<Summary, Error> {
    let handoff = pbp1::decode(handoff_bytes).map_err(|_| Error::Handoff)?;
    let descriptors = profile_descriptors(&handoff)?;
    let retained = core::array::from_fn(|index| RetainedFile {
        role: RETAINED_ROLES[index],
        physical_base: descriptors[index + 1].physical_base,
        bytes: files[index],
    });
    revalidate_development(handoff_bytes, retained)
}

pub fn retained_locators(handoff_bytes: &[u8]) -> Result<[u64; RETAINED_FILE_COUNT], Error> {
    let handoff = pbp1::decode(handoff_bytes).map_err(|_| Error::Handoff)?;
    let descriptors = profile_descriptors(&handoff)?;
    Ok(core::array::from_fn(|index| {
        descriptors[index + 1].physical_base
    }))
}

/// # Safety
///
/// Every retained physical range named by the validated PBP1 profile must be
/// identity-mapped, immutable, and readable for its exact declared byte count.
#[inline(never)]
pub unsafe fn revalidate_development_from_handoff(handoff_bytes: &[u8]) -> Result<Summary, Error> {
    let handoff = pbp1::decode(handoff_bytes).map_err(|_| Error::Handoff)?;
    let descriptors = profile_descriptors(&handoff)?;
    let mut files: [&[u8]; RETAINED_FILE_COUNT] = [&[]; RETAINED_FILE_COUNT];
    for index in 0..RETAINED_FILE_COUNT {
        let descriptor = descriptors[index + 1];
        let address =
            usize::try_from(descriptor.physical_base).map_err(|_| Error::ArtifactRange)?;
        let byte_count =
            usize::try_from(descriptor.byte_count).map_err(|_| Error::ArtifactRange)?;
        address
            .checked_add(byte_count)
            .ok_or(Error::ArtifactRange)?;
        files[index] = unsafe { from_raw_parts(address as *const u8, byte_count) };
    }
    revalidate_development_files(handoff_bytes, files)
}
