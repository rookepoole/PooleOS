#![no_std]
#![deny(warnings)]

use sha2::{Digest, Sha256};

pub const CONTRACT_ID: &str = "PSYM1";
pub const MAGIC: [u8; 8] = *b"PSYM1\0\0\0";
pub const MAJOR_VERSION: u16 = 1;
pub const MINOR_VERSION: u16 = 0;
pub const HEADER_BYTES: usize = 384;
pub const SEGMENT_BYTES: usize = 32;
pub const SYMBOL_BYTES: usize = 48;
pub const MAX_BUNDLE_BYTES: usize = 512 * 1024;
pub const MAX_IMAGE_BYTES: u64 = 64 * 1024 * 1024;
pub const MAX_SEGMENTS: usize = 16;
pub const MAX_SYMBOLS: usize = 4096;
pub const MAX_NAME_BYTES: usize = 127;
pub const MAX_STRING_BYTES: usize = 256 * 1024;
pub const MAX_LOOKUP_STEPS: u32 = 13;

pub const PROFILE_PUBLIC_DIAGNOSTIC: u16 = 1;
pub const ADDRESS_IMAGE_RELATIVE: u16 = 1;
pub const NAME_ASCII_OPAQUE: u16 = 1;
pub const PRIVACY_PUBLIC: u8 = 1;
pub const LOOKUP_BINARY_SEARCH: u16 = 1;
pub const MANGLING_OPAQUE_LINKER: u16 = 1;
pub const POINTER_REDACT_RUNTIME: u16 = 1;

pub const FLAG_IMAGE_RELATIVE: u32 = 1 << 0;
pub const FLAG_KERNEL_IDENTITY_BOUND: u32 = 1 << 1;
pub const FLAG_BUILD_ID_BOUND: u32 = 1 << 2;
pub const FLAG_SPLIT_DEBUG_BOUND: u32 = 1 << 3;
pub const FLAG_STRIPPED_PRODUCT: u32 = 1 << 4;
pub const FLAG_SORTED_NONOVERLAP: u32 = 1 << 5;
pub const FLAG_BOUNDED_LOOKUP: u32 = 1 << 6;
pub const FLAG_ASCII_OPAQUE_NAMES: u32 = 1 << 7;
pub const FLAG_NO_SOURCE_PATHS: u32 = 1 << 8;
pub const FLAG_POINTER_REDACTION_DEFAULT: u32 = 1 << 9;
pub const FLAG_DIAGNOSTIC_ONLY: u32 = 1 << 10;
pub const FLAG_NO_AUTHORITY: u32 = 1 << 11;
pub const FLAG_OUTER_SIGNATURE: u32 = 1 << 12;
pub const FLAG_INNER_SIGNATURE: u32 = 1 << 13;
pub const FLAG_MANIFEST_SIGNATURE: u32 = 1 << 14;
pub const REQUIRED_FLAGS: u32 = FLAG_IMAGE_RELATIVE
    | FLAG_KERNEL_IDENTITY_BOUND
    | FLAG_BUILD_ID_BOUND
    | FLAG_SPLIT_DEBUG_BOUND
    | FLAG_STRIPPED_PRODUCT
    | FLAG_SORTED_NONOVERLAP
    | FLAG_BOUNDED_LOOKUP
    | FLAG_ASCII_OPAQUE_NAMES
    | FLAG_NO_SOURCE_PATHS
    | FLAG_POINTER_REDACTION_DEFAULT
    | FLAG_DIAGNOSTIC_ONLY
    | FLAG_NO_AUTHORITY
    | FLAG_OUTER_SIGNATURE
    | FLAG_INNER_SIGNATURE
    | FLAG_MANIFEST_SIGNATURE;

pub const SEGMENT_READ: u32 = 1 << 0;
pub const SEGMENT_WRITE: u32 = 1 << 1;
pub const SEGMENT_EXECUTE: u32 = 1 << 2;
pub const SEGMENT_RELRO: u32 = 1 << 3;
const SEGMENT_KNOWN_FLAGS: u32 = SEGMENT_READ | SEGMENT_WRITE | SEGMENT_EXECUTE | SEGMENT_RELRO;
pub const SEGMENT_RODATA: u16 = 1;
pub const SEGMENT_TEXT: u16 = 2;
pub const SEGMENT_RELRO_DATA: u16 = 3;
pub const SEGMENT_DATA_BSS: u16 = 4;

pub const SYMBOL_FUNCTION: u8 = 1;
pub const SYMBOL_OBJECT: u8 = 2;
pub const BIND_GLOBAL: u8 = 1;
pub const VISIBILITY_DEFAULT: u8 = 0;
pub const SYMBOL_EXECUTABLE: u16 = 1 << 0;
pub const SYMBOL_ENTRY: u16 = 1 << 1;
pub const SYMBOL_PANIC_SAFE: u16 = 1 << 2;
pub const SYMBOL_DIAGNOSTIC_PUBLIC: u16 = 1 << 3;
const SYMBOL_KNOWN_FLAGS: u16 =
    SYMBOL_EXECUTABLE | SYMBOL_ENTRY | SYMBOL_PANIC_SAFE | SYMBOL_DIAGNOSTIC_PUBLIC;

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
    AddressModel,
    NameEncoding,
    Privacy,
    Counts,
    TotalSize,
    TableLayout,
    StringSize,
    Bounds,
    LookupPolicy,
    ImageSize,
    VirtualWindow,
    SlideAlignment,
    EntryOffset,
    Identity,
    BodyDigest,
    SegmentId,
    SegmentKind,
    SegmentFlags,
    SegmentOrder,
    SegmentRange,
    SegmentCoverage,
    SymbolId,
    SymbolSegment,
    SymbolKind,
    SymbolBinding,
    SymbolVisibility,
    SymbolPrivacy,
    SymbolFlags,
    SymbolNameLayout,
    SymbolNameSize,
    SymbolNameAscii,
    SymbolNameFingerprint,
    SymbolRange,
    SymbolOrder,
    SymbolSegmentRange,
    SymbolPermissions,
    EntrySymbol,
    StringCoverage,
    LookupBase,
    LookupAddress,
    LookupBound,
    ActivationOuterSignature,
    ActivationInnerSignature,
    ActivationManifestSignature,
    ActivationKernelSignature,
    ActivationOuterRole,
    ActivationOuterVersion,
    ActivationOuterPayloadDigest,
    ActivationOuterFileDigest,
    ActivationCanonicalIdentity,
    ActivationLoadedIdentity,
    ActivationBuildId,
    ActivationDebugIdentity,
    ActivationSourceIdentity,
    ActivationIdentityEvidence,
    ActivationStrippedCorrespondence,
    ActivationDwarf5,
    ActivationPublicPolicy,
    ActivationSourcePaths,
    ActivationPointerRedaction,
    ActivationDiagnosticsAuthority,
    ActivationRuntimeBase,
    ActivationSymbolCapacity,
    ActivationStringCapacity,
    ActivationLookupCapacity,
    ActivationAuthorityEffect,
}

impl Error {
    pub const fn code(self) -> &'static str {
        match self {
            Self::Truncated => "psym_truncated",
            Self::Oversized => "psym_oversized",
            Self::Magic => "psym_magic",
            Self::Version => "psym_version",
            Self::HeaderSize => "psym_header_size",
            Self::RecordSize => "psym_record_size",
            Self::Reserved => "psym_reserved",
            Self::Flags => "psym_flags",
            Self::Profile => "psym_profile",
            Self::AddressModel => "psym_address_model",
            Self::NameEncoding => "psym_name_encoding",
            Self::Privacy => "psym_privacy",
            Self::Counts => "psym_counts",
            Self::TotalSize => "psym_total_size",
            Self::TableLayout => "psym_table_layout",
            Self::StringSize => "psym_string_size",
            Self::Bounds => "psym_bounds",
            Self::LookupPolicy => "psym_lookup_policy",
            Self::ImageSize => "psym_image_size",
            Self::VirtualWindow => "psym_virtual_window",
            Self::SlideAlignment => "psym_slide_alignment",
            Self::EntryOffset => "psym_entry_offset",
            Self::Identity => "psym_identity",
            Self::BodyDigest => "psym_body_digest",
            Self::SegmentId => "psym_segment_id",
            Self::SegmentKind => "psym_segment_kind",
            Self::SegmentFlags => "psym_segment_flags",
            Self::SegmentOrder => "psym_segment_order",
            Self::SegmentRange => "psym_segment_range",
            Self::SegmentCoverage => "psym_segment_coverage",
            Self::SymbolId => "psym_symbol_id",
            Self::SymbolSegment => "psym_symbol_segment",
            Self::SymbolKind => "psym_symbol_kind",
            Self::SymbolBinding => "psym_symbol_binding",
            Self::SymbolVisibility => "psym_symbol_visibility",
            Self::SymbolPrivacy => "psym_symbol_privacy",
            Self::SymbolFlags => "psym_symbol_flags",
            Self::SymbolNameLayout => "psym_symbol_name_layout",
            Self::SymbolNameSize => "psym_symbol_name_size",
            Self::SymbolNameAscii => "psym_symbol_name_ascii",
            Self::SymbolNameFingerprint => "psym_symbol_name_fingerprint",
            Self::SymbolRange => "psym_symbol_range",
            Self::SymbolOrder => "psym_symbol_order",
            Self::SymbolSegmentRange => "psym_symbol_segment_range",
            Self::SymbolPermissions => "psym_symbol_permissions",
            Self::EntrySymbol => "psym_entry_symbol",
            Self::StringCoverage => "psym_string_coverage",
            Self::LookupBase => "psym_lookup_base",
            Self::LookupAddress => "psym_lookup_address",
            Self::LookupBound => "psym_lookup_bound",
            Self::ActivationOuterSignature => "psym_activation_outer_signature",
            Self::ActivationInnerSignature => "psym_activation_inner_signature",
            Self::ActivationManifestSignature => "psym_activation_manifest_signature",
            Self::ActivationKernelSignature => "psym_activation_kernel_signature",
            Self::ActivationOuterRole => "psym_activation_outer_role",
            Self::ActivationOuterVersion => "psym_activation_outer_version",
            Self::ActivationOuterPayloadDigest => "psym_activation_outer_payload_digest",
            Self::ActivationOuterFileDigest => "psym_activation_outer_file_digest",
            Self::ActivationCanonicalIdentity => "psym_activation_canonical_identity",
            Self::ActivationLoadedIdentity => "psym_activation_loaded_identity",
            Self::ActivationBuildId => "psym_activation_build_id",
            Self::ActivationDebugIdentity => "psym_activation_debug_identity",
            Self::ActivationSourceIdentity => "psym_activation_source_identity",
            Self::ActivationIdentityEvidence => "psym_activation_identity_evidence",
            Self::ActivationStrippedCorrespondence => "psym_activation_stripped_correspondence",
            Self::ActivationDwarf5 => "psym_activation_dwarf5",
            Self::ActivationPublicPolicy => "psym_activation_public_policy",
            Self::ActivationSourcePaths => "psym_activation_source_paths",
            Self::ActivationPointerRedaction => "psym_activation_pointer_redaction",
            Self::ActivationDiagnosticsAuthority => "psym_activation_diagnostics_authority",
            Self::ActivationRuntimeBase => "psym_activation_runtime_base",
            Self::ActivationSymbolCapacity => "psym_activation_symbol_capacity",
            Self::ActivationStringCapacity => "psym_activation_string_capacity",
            Self::ActivationLookupCapacity => "psym_activation_lookup_capacity",
            Self::ActivationAuthorityEffect => "psym_activation_authority_effect",
        }
    }
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct Identity {
    pub canonical_file_sha256: [u8; 32],
    pub preferred_loaded_sha256: [u8; 32],
    pub build_id_sha256: [u8; 32],
    pub debug_file_sha256: [u8; 32],
    pub source_manifest_sha256: [u8; 32],
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct Segment {
    pub segment_id: u16,
    pub kind: u16,
    pub flags: u32,
    pub start_offset: u64,
    pub byte_count: u64,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct Symbol<'a> {
    pub symbol_id: u32,
    pub segment_id: u16,
    pub kind: u8,
    pub binding: u8,
    pub visibility: u8,
    pub privacy: u8,
    pub flags: u16,
    pub start_offset: u64,
    pub byte_count: u64,
    pub name: &'a [u8],
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct Bundle<'a> {
    pub raw: &'a [u8],
    pub flags: u32,
    pub image_bytes: u64,
    pub preferred_virtual_base: u64,
    pub virtual_window_end_exclusive: u64,
    pub slide_alignment: u64,
    pub entry_offset: u64,
    pub identity: Identity,
    pub body_sha256: [u8; 32],
    pub segment_count: usize,
    pub symbol_count: usize,
    pub string_bytes: usize,
    segment_offset: usize,
    symbol_offset: usize,
    string_offset: usize,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct LookupResult<'a> {
    pub symbol: Symbol<'a>,
    pub symbol_offset: u64,
    pub steps: u32,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct ConsumptionContext {
    pub outer_role: u16,
    pub outer_version: u16,
    pub outer_payload_sha256: [u8; 32],
    pub outer_file_sha256: [u8; 32],
    pub expected_outer_file_sha256: [u8; 32],
    pub outer_signature_verified: bool,
    pub inner_signature_verified: bool,
    pub manifest_signature_verified: bool,
    pub kernel_signature_verified: bool,
    pub canonical_file_sha256: [u8; 32],
    pub preferred_loaded_sha256: [u8; 32],
    pub build_id_sha256: [u8; 32],
    pub debug_file_sha256: [u8; 32],
    pub source_manifest_sha256: [u8; 32],
    pub identity_evidence_verified: bool,
    pub stripped_correspondence_verified: bool,
    pub dwarf5_verified: bool,
    pub public_policy_verified: bool,
    pub source_paths_absent: bool,
    pub pointer_redaction_enabled: bool,
    pub diagnostics_authorized: bool,
    pub runtime_base: u64,
    pub symbol_capacity: usize,
    pub string_capacity: usize,
    pub lookup_step_capacity: u32,
    pub authority_effect_requested: bool,
}

impl ConsumptionContext {
    pub fn development(bundle: &Bundle<'_>) -> Self {
        Self {
            outer_role: 4,
            outer_version: MAJOR_VERSION,
            outer_payload_sha256: sha256(bundle.raw),
            outer_file_sha256: [0; 32],
            expected_outer_file_sha256: [0; 32],
            outer_signature_verified: false,
            inner_signature_verified: false,
            manifest_signature_verified: false,
            kernel_signature_verified: false,
            canonical_file_sha256: bundle.identity.canonical_file_sha256,
            preferred_loaded_sha256: bundle.identity.preferred_loaded_sha256,
            build_id_sha256: bundle.identity.build_id_sha256,
            debug_file_sha256: bundle.identity.debug_file_sha256,
            source_manifest_sha256: bundle.identity.source_manifest_sha256,
            identity_evidence_verified: false,
            stripped_correspondence_verified: false,
            dwarf5_verified: false,
            public_policy_verified: false,
            source_paths_absent: false,
            pointer_redaction_enabled: true,
            diagnostics_authorized: false,
            runtime_base: bundle.preferred_virtual_base,
            symbol_capacity: bundle.symbol_count,
            string_capacity: bundle.string_bytes,
            lookup_step_capacity: MAX_LOOKUP_STEPS,
            authority_effect_requested: false,
        }
    }

    pub fn synthetic_qualified(bundle: &Bundle<'_>) -> Self {
        Self {
            outer_file_sha256: [0xA5; 32],
            expected_outer_file_sha256: [0xA5; 32],
            outer_signature_verified: true,
            inner_signature_verified: true,
            manifest_signature_verified: true,
            kernel_signature_verified: true,
            identity_evidence_verified: true,
            stripped_correspondence_verified: true,
            dwarf5_verified: true,
            public_policy_verified: true,
            source_paths_absent: true,
            pointer_redaction_enabled: true,
            diagnostics_authorized: true,
            ..Self::development(bundle)
        }
    }
}

fn sha256(data: &[u8]) -> [u8; 32] {
    let digest = Sha256::digest(data);
    let mut output = [0; 32];
    output.copy_from_slice(&digest);
    output
}

fn range(data: &[u8], offset: usize, count: usize) -> Result<&[u8], Error> {
    let end = offset.checked_add(count).ok_or(Error::Truncated)?;
    data.get(offset..end).ok_or(Error::Truncated)
}

fn u16_at(data: &[u8], offset: usize) -> Result<u16, Error> {
    Ok(u16::from_le_bytes(
        range(data, offset, 2)?
            .try_into()
            .map_err(|_| Error::Truncated)?,
    ))
}

fn u32_at(data: &[u8], offset: usize) -> Result<u32, Error> {
    Ok(u32::from_le_bytes(
        range(data, offset, 4)?
            .try_into()
            .map_err(|_| Error::Truncated)?,
    ))
}

fn u64_at(data: &[u8], offset: usize) -> Result<u64, Error> {
    Ok(u64::from_le_bytes(
        range(data, offset, 8)?
            .try_into()
            .map_err(|_| Error::Truncated)?,
    ))
}

fn digest_at(data: &[u8], offset: usize) -> Result<[u8; 32], Error> {
    let mut output = [0; 32];
    output.copy_from_slice(range(data, offset, 32)?);
    Ok(output)
}

fn is_canonical_x86_64(value: u64) -> bool {
    let upper = value >> 48;
    let sign = (value >> 47) & 1;
    upper == if sign == 1 { 0xffff } else { 0 }
}

fn checked_end(start: u64, count: u64, maximum: u64, error: Error) -> Result<u64, Error> {
    if count == 0 || start > maximum || count > maximum - start {
        return Err(error);
    }
    Ok(start + count)
}

fn expected_segment_flags(kind: u16) -> Result<u32, Error> {
    match kind {
        SEGMENT_RODATA => Ok(SEGMENT_READ),
        SEGMENT_TEXT => Ok(SEGMENT_READ | SEGMENT_EXECUTE),
        SEGMENT_RELRO_DATA => Ok(SEGMENT_READ | SEGMENT_RELRO),
        SEGMENT_DATA_BSS => Ok(SEGMENT_READ | SEGMENT_WRITE),
        _ => Err(Error::SegmentKind),
    }
}

fn name_allowed(name: &[u8]) -> bool {
    !name.is_empty()
        && !b".$@-".contains(&name[0])
        && name
            .iter()
            .all(|byte| byte.is_ascii_alphanumeric() || b"_.$@-".contains(byte))
}

fn name_fingerprint(name: &[u8]) -> u32 {
    u32::from_le_bytes(sha256(name)[..4].try_into().expect("fixed digest size"))
}

fn segment_raw(data: &[u8], offset: usize) -> Result<Segment, Error> {
    Ok(Segment {
        segment_id: u16_at(data, offset)?,
        kind: u16_at(data, offset + 2)?,
        flags: u32_at(data, offset + 4)?,
        start_offset: u64_at(data, offset + 8)?,
        byte_count: u64_at(data, offset + 16)?,
    })
}

fn symbol_raw<'a>(
    data: &'a [u8],
    offset: usize,
    string_offset: usize,
    string_bytes: usize,
) -> Result<Symbol<'a>, Error> {
    let name_offset =
        usize::try_from(u32_at(data, offset + 12)?).map_err(|_| Error::SymbolNameSize)?;
    let name_bytes = usize::from(u16_at(data, offset + 16)?);
    if name_offset > string_bytes || name_bytes > string_bytes - name_offset {
        return Err(Error::SymbolNameSize);
    }
    let absolute_name = string_offset
        .checked_add(name_offset)
        .ok_or(Error::SymbolNameSize)?;
    Ok(Symbol {
        symbol_id: u32_at(data, offset)?,
        segment_id: u16_at(data, offset + 4)?,
        kind: data[offset + 6],
        binding: data[offset + 7],
        visibility: data[offset + 8],
        privacy: data[offset + 9],
        flags: u16_at(data, offset + 10)?,
        start_offset: u64_at(data, offset + 24)?,
        byte_count: u64_at(data, offset + 32)?,
        name: range(data, absolute_name, name_bytes)?,
    })
}

impl<'a> Bundle<'a> {
    pub fn segment(&self, index: usize) -> Result<Segment, Error> {
        if index >= self.segment_count {
            return Err(Error::SegmentId);
        }
        segment_raw(self.raw, self.segment_offset + index * SEGMENT_BYTES)
    }

    pub fn symbol(&self, index: usize) -> Result<Symbol<'a>, Error> {
        if index >= self.symbol_count {
            return Err(Error::SymbolId);
        }
        symbol_raw(
            self.raw,
            self.symbol_offset + index * SYMBOL_BYTES,
            self.string_offset,
            self.string_bytes,
        )
    }
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
    if (u16_at(data, 8)?, u16_at(data, 10)?) != (MAJOR_VERSION, MINOR_VERSION) {
        return Err(Error::Version);
    }
    if usize::from(u16_at(data, 12)?) != HEADER_BYTES {
        return Err(Error::HeaderSize);
    }
    if (
        usize::from(u16_at(data, 14)?),
        usize::from(u16_at(data, 16)?),
    ) != (SEGMENT_BYTES, SYMBOL_BYTES)
    {
        return Err(Error::RecordSize);
    }
    if u16_at(data, 18)? != 0 {
        return Err(Error::Reserved);
    }
    let flags = u32_at(data, 20)?;
    if flags != REQUIRED_FLAGS {
        return Err(Error::Flags);
    }
    if u16_at(data, 24)? != PROFILE_PUBLIC_DIAGNOSTIC {
        return Err(Error::Profile);
    }
    if u16_at(data, 26)? != ADDRESS_IMAGE_RELATIVE {
        return Err(Error::AddressModel);
    }
    if u16_at(data, 28)? != NAME_ASCII_OPAQUE {
        return Err(Error::NameEncoding);
    }
    if u16_at(data, 30)? != u16::from(PRIVACY_PUBLIC) {
        return Err(Error::Privacy);
    }
    let segment_count = usize::try_from(u32_at(data, 32)?).map_err(|_| Error::Counts)?;
    let symbol_count = usize::try_from(u32_at(data, 36)?).map_err(|_| Error::Counts)?;
    if !(1..=MAX_SEGMENTS).contains(&segment_count) || !(1..=MAX_SYMBOLS).contains(&symbol_count) {
        return Err(Error::Counts);
    }
    let total_bytes = usize::try_from(u64_at(data, 40)?).map_err(|_| Error::TotalSize)?;
    if total_bytes != data.len() {
        return Err(Error::TotalSize);
    }
    let segment_offset = usize::try_from(u64_at(data, 48)?).map_err(|_| Error::TableLayout)?;
    let symbol_offset = usize::try_from(u64_at(data, 56)?).map_err(|_| Error::TableLayout)?;
    let string_offset = usize::try_from(u64_at(data, 64)?).map_err(|_| Error::TableLayout)?;
    let string_bytes = usize::try_from(u64_at(data, 72)?).map_err(|_| Error::StringSize)?;
    let expected_symbol_offset = HEADER_BYTES
        .checked_add(segment_count * SEGMENT_BYTES)
        .ok_or(Error::TableLayout)?;
    let expected_string_offset = expected_symbol_offset
        .checked_add(symbol_count * SYMBOL_BYTES)
        .ok_or(Error::TableLayout)?;
    if segment_offset != HEADER_BYTES
        || symbol_offset != expected_symbol_offset
        || string_offset != expected_string_offset
        || string_offset > data.len()
    {
        return Err(Error::TableLayout);
    }
    if string_bytes == 0
        || string_bytes > MAX_STRING_BYTES
        || string_bytes != data.len() - string_offset
    {
        return Err(Error::StringSize);
    }
    if (
        usize::try_from(u32_at(data, 120)?).map_err(|_| Error::Bounds)?,
        usize::try_from(u32_at(data, 124)?).map_err(|_| Error::Bounds)?,
        usize::try_from(u32_at(data, 128)?).map_err(|_| Error::Bounds)?,
        u32_at(data, 132)?,
    ) != (MAX_SEGMENTS, MAX_SYMBOLS, MAX_NAME_BYTES, MAX_LOOKUP_STEPS)
    {
        return Err(Error::Bounds);
    }
    if (u16_at(data, 136)?, u16_at(data, 138)?, u16_at(data, 140)?)
        != (
            LOOKUP_BINARY_SEARCH,
            MANGLING_OPAQUE_LINKER,
            POINTER_REDACT_RUNTIME,
        )
    {
        return Err(Error::LookupPolicy);
    }
    if u16_at(data, 142)? != 0 {
        return Err(Error::Reserved);
    }
    let image_bytes = u64_at(data, 80)?;
    if image_bytes == 0 || image_bytes > MAX_IMAGE_BYTES {
        return Err(Error::ImageSize);
    }
    let preferred_virtual_base = u64_at(data, 88)?;
    let virtual_window_end_exclusive = u64_at(data, 96)?;
    if preferred_virtual_base >= virtual_window_end_exclusive
        || !is_canonical_x86_64(preferred_virtual_base)
        || !is_canonical_x86_64(virtual_window_end_exclusive - 1)
        || image_bytes > virtual_window_end_exclusive - preferred_virtual_base
    {
        return Err(Error::VirtualWindow);
    }
    let slide_alignment = u64_at(data, 104)?;
    if slide_alignment < 4096
        || !slide_alignment.is_power_of_two()
        || !preferred_virtual_base.is_multiple_of(slide_alignment)
    {
        return Err(Error::SlideAlignment);
    }
    let entry_offset = u64_at(data, 112)?;
    if entry_offset >= image_bytes {
        return Err(Error::EntryOffset);
    }
    let identity = Identity {
        canonical_file_sha256: digest_at(data, 144)?,
        preferred_loaded_sha256: digest_at(data, 176)?,
        build_id_sha256: digest_at(data, 208)?,
        debug_file_sha256: digest_at(data, 240)?,
        source_manifest_sha256: digest_at(data, 272)?,
    };
    if [
        identity.canonical_file_sha256,
        identity.preferred_loaded_sha256,
        identity.build_id_sha256,
        identity.debug_file_sha256,
        identity.source_manifest_sha256,
    ]
    .contains(&[0; 32])
    {
        return Err(Error::Identity);
    }
    if data[336..HEADER_BYTES].iter().any(|byte| *byte != 0) {
        return Err(Error::Reserved);
    }
    let body_sha256 = digest_at(data, 304)?;
    if sha256(&data[HEADER_BYTES..]) != body_sha256 {
        return Err(Error::BodyDigest);
    }

    let mut previous_end = 0;
    for index in 0..segment_count {
        let offset = segment_offset + index * SEGMENT_BYTES;
        let segment = segment_raw(data, offset)?;
        if usize::from(segment.segment_id) != index + 1 {
            return Err(Error::SegmentId);
        }
        let expected_flags = expected_segment_flags(segment.kind)?;
        if segment.flags & !SEGMENT_KNOWN_FLAGS != 0
            || segment.flags != expected_flags
            || segment.flags & SEGMENT_WRITE != 0 && segment.flags & SEGMENT_EXECUTE != 0
        {
            return Err(Error::SegmentFlags);
        }
        if segment.start_offset != previous_end {
            return Err(Error::SegmentOrder);
        }
        previous_end = checked_end(
            segment.start_offset,
            segment.byte_count,
            image_bytes,
            Error::SegmentRange,
        )?;
        if u64_at(data, offset + 24)? != 0 {
            return Err(Error::Reserved);
        }
    }
    if previous_end != image_bytes {
        return Err(Error::SegmentCoverage);
    }

    let mut expected_name_offset = 0usize;
    let mut previous_symbol_end = 0u64;
    let mut entry_count = 0usize;
    for index in 0..symbol_count {
        let offset = symbol_offset + index * SYMBOL_BYTES;
        let symbol_id = u32_at(data, offset)?;
        let segment_id = u16_at(data, offset + 4)?;
        let kind = data[offset + 6];
        let binding = data[offset + 7];
        let visibility = data[offset + 8];
        let privacy = data[offset + 9];
        let flags = u16_at(data, offset + 10)?;
        if usize::try_from(symbol_id).map_err(|_| Error::SymbolId)? != index + 1 {
            return Err(Error::SymbolId);
        }
        if segment_id == 0 || usize::from(segment_id) > segment_count {
            return Err(Error::SymbolSegment);
        }
        if !matches!(kind, SYMBOL_FUNCTION | SYMBOL_OBJECT) {
            return Err(Error::SymbolKind);
        }
        if binding != BIND_GLOBAL {
            return Err(Error::SymbolBinding);
        }
        if visibility != VISIBILITY_DEFAULT {
            return Err(Error::SymbolVisibility);
        }
        if privacy != PRIVACY_PUBLIC {
            return Err(Error::SymbolPrivacy);
        }
        if flags & !SYMBOL_KNOWN_FLAGS != 0 || flags & SYMBOL_DIAGNOSTIC_PUBLIC == 0 {
            return Err(Error::SymbolFlags);
        }
        let name_offset =
            usize::try_from(u32_at(data, offset + 12)?).map_err(|_| Error::SymbolNameLayout)?;
        if name_offset != expected_name_offset {
            return Err(Error::SymbolNameLayout);
        }
        let name_bytes = usize::from(u16_at(data, offset + 16)?);
        if name_bytes == 0
            || name_bytes > MAX_NAME_BYTES
            || name_offset > string_bytes
            || name_bytes > string_bytes - name_offset
        {
            return Err(Error::SymbolNameSize);
        }
        let symbol = symbol_raw(data, offset, string_offset, string_bytes)?;
        if u16_at(data, offset + 18)? != 0 || u64_at(data, offset + 40)? != 0 {
            return Err(Error::Reserved);
        }
        if !name_allowed(symbol.name) {
            return Err(Error::SymbolNameAscii);
        }
        if u32_at(data, offset + 20)? != name_fingerprint(symbol.name) {
            return Err(Error::SymbolNameFingerprint);
        }
        let end = checked_end(
            symbol.start_offset,
            symbol.byte_count,
            image_bytes,
            Error::SymbolRange,
        )?;
        if index != 0 && symbol.start_offset < previous_symbol_end {
            return Err(Error::SymbolOrder);
        }
        let segment = segment_raw(
            data,
            segment_offset + (usize::from(symbol.segment_id) - 1) * SEGMENT_BYTES,
        )?;
        if symbol.start_offset < segment.start_offset
            || end > segment.start_offset + segment.byte_count
        {
            return Err(Error::SymbolSegmentRange);
        }
        let executable = segment.flags & SEGMENT_EXECUTE != 0;
        if symbol.kind == SYMBOL_FUNCTION {
            if !executable || symbol.flags & SYMBOL_EXECUTABLE == 0 {
                return Err(Error::SymbolPermissions);
            }
        } else if executable || symbol.flags & SYMBOL_EXECUTABLE != 0 {
            return Err(Error::SymbolPermissions);
        }
        if symbol.flags & SYMBOL_ENTRY != 0 {
            entry_count += 1;
            if symbol.start_offset != entry_offset
                || symbol.kind != SYMBOL_FUNCTION
                || symbol.name != b"poole_kernel_entry"
            {
                return Err(Error::EntrySymbol);
            }
        }
        expected_name_offset += symbol.name.len();
        previous_symbol_end = end;
    }
    if expected_name_offset != string_bytes {
        return Err(Error::StringCoverage);
    }
    if entry_count != 1 {
        return Err(Error::EntrySymbol);
    }

    Ok(Bundle {
        raw: data,
        flags,
        image_bytes,
        preferred_virtual_base,
        virtual_window_end_exclusive,
        slide_alignment,
        entry_offset,
        identity,
        body_sha256,
        segment_count,
        symbol_count,
        string_bytes,
        segment_offset,
        symbol_offset,
        string_offset,
    })
}

pub fn lookup<'a>(
    bundle: &Bundle<'a>,
    runtime_base: u64,
    runtime_address: u64,
) -> Result<Option<LookupResult<'a>>, Error> {
    if runtime_base < bundle.preferred_virtual_base
        || runtime_base > bundle.virtual_window_end_exclusive - bundle.image_bytes
        || !(runtime_base - bundle.preferred_virtual_base).is_multiple_of(bundle.slide_alignment)
        || !is_canonical_x86_64(runtime_base)
    {
        return Err(Error::LookupBase);
    }
    let runtime_end = runtime_base
        .checked_add(bundle.image_bytes)
        .ok_or(Error::LookupAddress)?;
    if runtime_address < runtime_base
        || runtime_address >= runtime_end
        || !is_canonical_x86_64(runtime_address)
    {
        return Err(Error::LookupAddress);
    }
    let target = runtime_address - runtime_base;
    let mut low = 0usize;
    let mut high = bundle.symbol_count;
    let mut steps = 0u32;
    while low < high {
        steps += 1;
        if steps > MAX_LOOKUP_STEPS {
            return Err(Error::LookupBound);
        }
        let middle = low + (high - low) / 2;
        let symbol = bundle.symbol(middle)?;
        if target < symbol.start_offset {
            high = middle;
        } else if target >= symbol.start_offset + symbol.byte_count {
            low = middle + 1;
        } else {
            return Ok(Some(LookupResult {
                symbol,
                symbol_offset: target - symbol.start_offset,
                steps,
            }));
        }
    }
    Ok(None)
}

pub fn authorize_consumption(
    bundle: &Bundle<'_>,
    context: &ConsumptionContext,
) -> Result<(), Error> {
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
            context.kernel_signature_verified,
            Error::ActivationKernelSignature,
        ),
        (context.outer_role == 4, Error::ActivationOuterRole),
        (
            context.outer_version == MAJOR_VERSION,
            Error::ActivationOuterVersion,
        ),
        (
            context.outer_payload_sha256 == sha256(bundle.raw),
            Error::ActivationOuterPayloadDigest,
        ),
        (
            context.outer_file_sha256 == context.expected_outer_file_sha256
                && context.outer_file_sha256 != [0; 32],
            Error::ActivationOuterFileDigest,
        ),
        (
            context.canonical_file_sha256 == bundle.identity.canonical_file_sha256,
            Error::ActivationCanonicalIdentity,
        ),
        (
            context.preferred_loaded_sha256 == bundle.identity.preferred_loaded_sha256,
            Error::ActivationLoadedIdentity,
        ),
        (
            context.build_id_sha256 == bundle.identity.build_id_sha256,
            Error::ActivationBuildId,
        ),
        (
            context.debug_file_sha256 == bundle.identity.debug_file_sha256,
            Error::ActivationDebugIdentity,
        ),
        (
            context.source_manifest_sha256 == bundle.identity.source_manifest_sha256,
            Error::ActivationSourceIdentity,
        ),
        (
            context.identity_evidence_verified,
            Error::ActivationIdentityEvidence,
        ),
        (
            context.stripped_correspondence_verified,
            Error::ActivationStrippedCorrespondence,
        ),
        (context.dwarf5_verified, Error::ActivationDwarf5),
        (
            context.public_policy_verified,
            Error::ActivationPublicPolicy,
        ),
        (context.source_paths_absent, Error::ActivationSourcePaths),
        (
            context.pointer_redaction_enabled,
            Error::ActivationPointerRedaction,
        ),
        (
            context.diagnostics_authorized,
            Error::ActivationDiagnosticsAuthority,
        ),
        (
            context.runtime_base >= bundle.preferred_virtual_base
                && context.runtime_base <= bundle.virtual_window_end_exclusive - bundle.image_bytes
                && (context.runtime_base - bundle.preferred_virtual_base)
                    .is_multiple_of(bundle.slide_alignment),
            Error::ActivationRuntimeBase,
        ),
        (
            context.symbol_capacity >= bundle.symbol_count,
            Error::ActivationSymbolCapacity,
        ),
        (
            context.string_capacity >= bundle.string_bytes,
            Error::ActivationStringCapacity,
        ),
        (
            context.lookup_step_capacity >= MAX_LOOKUP_STEPS,
            Error::ActivationLookupCapacity,
        ),
        (
            !context.authority_effect_requested,
            Error::ActivationAuthorityEffect,
        ),
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

    const CANONICAL: &[u8] = include_bytes!("../../../specs/fixtures/psym1-canonical.bin");
    const MINIMAL: &[u8] = include_bytes!("../../../specs/fixtures/psym1-minimal.bin");
    const BOUNDARY: &[u8] = include_bytes!("../../../specs/fixtures/psym1-boundary.bin");

    #[test]
    fn canonical_and_boundary_profiles_parse() {
        let canonical = parse(CANONICAL).expect("canonical PSYM1");
        let minimal = parse(MINIMAL).expect("minimal PSYM1");
        let boundary = parse(BOUNDARY).expect("boundary PSYM1");
        assert_eq!((canonical.segment_count, canonical.symbol_count), (4, 3));
        assert_eq!((minimal.segment_count, minimal.symbol_count), (1, 1));
        assert_eq!((boundary.segment_count, boundary.symbol_count), (2, 3));
    }

    #[test]
    fn lookup_is_image_relative_and_bounded() {
        let bundle = parse(CANONICAL).expect("canonical PSYM1");
        let base = bundle.preferred_virtual_base;
        let result = lookup(&bundle, base, base + 0xF4CA)
            .expect("lookup")
            .expect("known symbol");
        assert_eq!(result.symbol.name, b"poole_kernel_rust_entry");
        assert_eq!(result.symbol_offset, 0);
        assert!(result.steps <= MAX_LOOKUP_STEPS);
        assert_eq!(lookup(&bundle, base, base + 0x8047).expect("gap"), None);
    }

    #[test]
    fn malformed_body_and_runtime_address_fail_closed() {
        let mut corrupted = [0u8; 725];
        corrupted.copy_from_slice(CANONICAL);
        corrupted[HEADER_BYTES] ^= 1;
        assert_eq!(parse(&corrupted), Err(Error::BodyDigest));
        let bundle = parse(CANONICAL).expect("canonical PSYM1");
        assert_eq!(
            lookup(&bundle, bundle.preferred_virtual_base, 0),
            Err(Error::LookupAddress)
        );
    }

    #[test]
    fn unsigned_development_context_is_never_consumable() {
        let bundle = parse(CANONICAL).expect("canonical PSYM1");
        assert_eq!(
            authorize_consumption(&bundle, &ConsumptionContext::development(&bundle)),
            Err(Error::ActivationOuterSignature)
        );
        authorize_consumption(&bundle, &ConsumptionContext::synthetic_qualified(&bundle))
            .expect("synthetic qualification context");
    }
}
