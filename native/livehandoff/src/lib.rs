#![no_std]
#![deny(warnings)]

use core::cmp::Ordering;

use poole_handoff::{
    self as pbp1, ARTIFACT_ENTRY_BYTES, ARTIFACT_EXECUTABLE, ARTIFACT_FIRMWARE_MANIFEST,
    ARTIFACT_HASH_VERIFIED, ARTIFACT_INITIAL_SYSTEM, ARTIFACT_KERNEL, ARTIFACT_MICROCODE,
    ARTIFACT_POLICY_BUNDLE, ARTIFACT_RECOVERY, ARTIFACT_SYMBOLS, ARTIFACT_SYSTEM_MANIFEST,
    ARTIFACT_TRUST_POLICY, ARTIFACT_TRUST_STATE, BOOT_SERVICES_EXITED, CORE_BYTES,
    DEVELOPMENT_MODE, Encoder, FRAMEBUFFER_BYTES, MEMORY_ACPI_NVS, MEMORY_ACPI_RECLAIMABLE,
    MEMORY_BOOT_RECLAIMABLE, MEMORY_ENTRY_BYTES, MEMORY_LOADER_RESERVED, MEMORY_MMIO,
    MEMORY_PERSISTENT, MEMORY_RESERVED, MEMORY_RUNTIME_CODE, MEMORY_RUNTIME_DATA, MEMORY_UNUSABLE,
    MEMORY_USABLE, RECORD_ARRAY, RECORD_CORE, RECORD_FRAMEBUFFER, RECORD_LOADED_ARTIFACTS,
    RECORD_MEMORY_MAP, RECORD_REQUIRED,
};

pub const CONTRACT_ID: &str = "PBLIVE3";
pub const UEFI_DESCRIPTOR_VERSION: u32 = 1;
pub const MIN_DESCRIPTOR_BYTES: usize = 40;
pub const MAX_DESCRIPTOR_BYTES: usize = 256;
pub const MAX_MEMORY_ENTRIES: usize = 16_384;
pub const MAX_TRANSCRIPT_CHUNK_BYTES: usize = 64;
pub const RETAINED_TABLE_PAGE_COUNT: u32 = 4;
pub const RETAINED_STACK_PAGE_COUNT: u32 = 14;
pub const PROFILE_ARTIFACT_COUNT: usize = 10;
pub const PROFILE_ARTIFACT_ROLES: [u32; PROFILE_ARTIFACT_COUNT] = [
    ARTIFACT_KERNEL,
    ARTIFACT_INITIAL_SYSTEM,
    ARTIFACT_RECOVERY,
    ARTIFACT_SYMBOLS,
    ARTIFACT_MICROCODE,
    ARTIFACT_FIRMWARE_MANIFEST,
    ARTIFACT_POLICY_BUNDLE,
    ARTIFACT_SYSTEM_MANIFEST,
    ARTIFACT_TRUST_POLICY,
    ARTIFACT_TRUST_STATE,
];

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum Error {
    DescriptorSize,
    DescriptorVersion,
    MemoryMapShape,
    MemoryType,
    MemoryRange,
    MemoryOverlap,
    ScratchCapacity,
    OutputCapacity,
    Handoff(pbp1::Error),
    PreExitProfile,
    ExitProfile,
    RetainedRange,
    ArtifactSet,
}

impl From<pbp1::Error> for Error {
    fn from(value: pbp1::Error) -> Self {
        Self::Handoff(value)
    }
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct KernelInput {
    pub physical_base: u64,
    pub physical_size: u64,
    pub virtual_base: u64,
    pub virtual_size: u64,
    pub entry_virtual: u64,
    pub sha256: [u8; 32],
    pub boot_attempt: u32,
    pub boot_attempt_limit: u32,
    pub boot_slot: u32,
    pub selected_entry: u32,
    pub uefi_revision: u32,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct FramebufferInput {
    pub physical_base: u64,
    pub byte_count: u64,
    pub width: u32,
    pub height: u32,
    pub stride: u32,
    pub pixel_format: u32,
    pub red_mask: u32,
    pub green_mask: u32,
    pub blue_mask: u32,
    pub reserved_mask: u32,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct ArtifactInput {
    pub role: u32,
    pub flags: u32,
    pub physical_base: u64,
    pub physical_size: u64,
    pub virtual_base: u64,
    pub virtual_size: u64,
    pub entry_virtual: u64,
    pub sha256: [u8; 32],
}

#[derive(Clone, Copy)]
pub struct BuildInput<'a> {
    pub raw_memory_map: &'a [u8],
    pub descriptor_size: usize,
    pub descriptor_version: u32,
    pub handoff_physical_base: u64,
    pub kernel: KernelInput,
    pub artifacts: [ArtifactInput; PROFILE_ARTIFACT_COUNT],
    pub framebuffer: Option<FramebufferInput>,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct RetainedInput {
    pub page_table_root_physical: u64,
    pub table_page_count: u32,
    pub stack_physical_base: u64,
    pub stack_page_count: u32,
    pub stack_top_virtual: u64,
    pub handoff_virtual_base: u64,
    pub handoff_capacity_bytes: u32,
}

#[derive(Clone, Copy)]
pub struct ExitBuildInput<'a> {
    pub raw_memory_map: &'a [u8],
    pub descriptor_size: usize,
    pub descriptor_version: u32,
    pub handoff_physical_base: u64,
    pub kernel: KernelInput,
    pub artifacts: [ArtifactInput; PROFILE_ARTIFACT_COUNT],
    pub framebuffer: Option<FramebufferInput>,
    pub retained: RetainedInput,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct Summary {
    pub total_bytes: usize,
    pub record_count: usize,
    pub memory_entry_count: usize,
    pub framebuffer_present: bool,
    pub artifact_count: usize,
    pub message_crc32: u32,
    pub fnv1a64: u64,
}

fn read_u32(bytes: &[u8], offset: usize) -> Result<u32, Error> {
    let value = bytes.get(offset..offset + 4).ok_or(Error::MemoryMapShape)?;
    Ok(u32::from_le_bytes([value[0], value[1], value[2], value[3]]))
}

fn read_u64(bytes: &[u8], offset: usize) -> Result<u64, Error> {
    let value = bytes.get(offset..offset + 8).ok_or(Error::MemoryMapShape)?;
    Ok(u64::from_le_bytes([
        value[0], value[1], value[2], value[3], value[4], value[5], value[6], value[7],
    ]))
}

fn write_u32(bytes: &mut [u8], offset: usize, value: u32) {
    bytes[offset..offset + 4].copy_from_slice(&value.to_le_bytes());
}

fn write_u64(bytes: &mut [u8], offset: usize, value: u64) {
    bytes[offset..offset + 8].copy_from_slice(&value.to_le_bytes());
}

fn normalized_kind(source_type: u32) -> Result<u32, Error> {
    match source_type {
        0 | 13 | 15 => Ok(MEMORY_RESERVED),
        1 | 2 => Ok(MEMORY_LOADER_RESERVED),
        3 | 4 => Ok(MEMORY_BOOT_RECLAIMABLE),
        5 => Ok(MEMORY_RUNTIME_CODE),
        6 => Ok(MEMORY_RUNTIME_DATA),
        7 => Ok(MEMORY_USABLE),
        8 => Ok(MEMORY_UNUSABLE),
        9 => Ok(MEMORY_ACPI_RECLAIMABLE),
        10 => Ok(MEMORY_ACPI_NVS),
        11 | 12 => Ok(MEMORY_MMIO),
        14 => Ok(MEMORY_PERSISTENT),
        _ => Err(Error::MemoryType),
    }
}

fn entry_start(bytes: &[u8], index: usize) -> Result<u64, Error> {
    read_u64(bytes, index * MEMORY_ENTRY_BYTES)
}

fn swap_entries(bytes: &mut [u8], left: usize, right: usize) {
    if left == right {
        return;
    }
    for offset in 0..MEMORY_ENTRY_BYTES {
        bytes.swap(
            left * MEMORY_ENTRY_BYTES + offset,
            right * MEMORY_ENTRY_BYTES + offset,
        );
    }
}

pub fn normalize_memory_map(
    raw: &[u8],
    descriptor_size: usize,
    descriptor_version: u32,
    output: &mut [u8],
) -> Result<usize, Error> {
    if !(MIN_DESCRIPTOR_BYTES..=MAX_DESCRIPTOR_BYTES).contains(&descriptor_size)
        || !descriptor_size.is_multiple_of(8)
    {
        return Err(Error::DescriptorSize);
    }
    if descriptor_version != UEFI_DESCRIPTOR_VERSION {
        return Err(Error::DescriptorVersion);
    }
    if raw.is_empty() || !raw.len().is_multiple_of(descriptor_size) {
        return Err(Error::MemoryMapShape);
    }
    let count = raw.len() / descriptor_size;
    if count == 0 || count > MAX_MEMORY_ENTRIES {
        return Err(Error::MemoryMapShape);
    }
    let required = count
        .checked_mul(MEMORY_ENTRY_BYTES)
        .ok_or(Error::ScratchCapacity)?;
    if output.len() < required {
        return Err(Error::ScratchCapacity);
    }
    let output = &mut output[..required];
    output.fill(0);
    for index in 0..count {
        let descriptor = &raw[index * descriptor_size..(index + 1) * descriptor_size];
        let source_type = read_u32(descriptor, 0)?;
        let start = read_u64(descriptor, 8)?;
        let pages = read_u64(descriptor, 24)?;
        let attributes = read_u64(descriptor, 32)?;
        if !start.is_multiple_of(pbp1::PAGE_BYTES) || pages == 0 {
            return Err(Error::MemoryRange);
        }
        let byte_count = pages
            .checked_mul(pbp1::PAGE_BYTES)
            .ok_or(Error::MemoryRange)?;
        start.checked_add(byte_count).ok_or(Error::MemoryRange)?;
        let base = index * MEMORY_ENTRY_BYTES;
        write_u64(output, base, start);
        write_u64(output, base + 8, pages);
        write_u64(output, base + 16, attributes);
        write_u32(output, base + 24, normalized_kind(source_type)?);
        write_u32(output, base + 28, source_type);
    }

    for index in 1..count {
        let mut cursor = index;
        while cursor > 0 {
            let left = entry_start(output, cursor - 1)?;
            let right = entry_start(output, cursor)?;
            if left.cmp(&right) != Ordering::Greater {
                break;
            }
            swap_entries(output, cursor - 1, cursor);
            cursor -= 1;
        }
    }

    let mut previous_end = 0u64;
    for index in 0..count {
        let base = index * MEMORY_ENTRY_BYTES;
        let start = read_u64(output, base)?;
        let pages = read_u64(output, base + 8)?;
        let end = start
            .checked_add(
                pages
                    .checked_mul(pbp1::PAGE_BYTES)
                    .ok_or(Error::MemoryRange)?,
            )
            .ok_or(Error::MemoryRange)?;
        if index != 0 && start < previous_end {
            return Err(Error::MemoryOverlap);
        }
        previous_end = end;
    }
    Ok(count)
}

fn core_payload(input: &BuildInput<'_>, total_bytes: usize) -> [u8; CORE_BYTES] {
    let mut value = [0u8; CORE_BYTES];
    write_u64(&mut value, 0, DEVELOPMENT_MODE);
    write_u64(&mut value, 8, input.kernel.physical_base);
    write_u64(&mut value, 16, input.kernel.physical_size);
    write_u64(&mut value, 24, input.kernel.virtual_base);
    write_u64(&mut value, 32, input.kernel.virtual_size);
    write_u64(&mut value, 40, input.kernel.entry_virtual);
    write_u64(&mut value, 64, input.handoff_physical_base);
    write_u64(&mut value, 72, input.handoff_physical_base);
    write_u64(&mut value, 80, total_bytes as u64);
    write_u32(&mut value, 104, input.kernel.boot_attempt);
    write_u32(&mut value, 108, input.kernel.boot_attempt_limit);
    write_u32(&mut value, 112, input.kernel.boot_slot);
    write_u32(&mut value, 116, input.kernel.selected_entry);
    write_u32(&mut value, 120, input.kernel.uefi_revision);
    value
}

fn exit_core_payload(input: &ExitBuildInput<'_>, total_bytes: usize) -> [u8; CORE_BYTES] {
    let mut value = [0u8; CORE_BYTES];
    write_u64(&mut value, 0, DEVELOPMENT_MODE | BOOT_SERVICES_EXITED);
    write_u64(&mut value, 8, input.kernel.physical_base);
    write_u64(&mut value, 16, input.kernel.physical_size);
    write_u64(&mut value, 24, input.kernel.virtual_base);
    write_u64(&mut value, 32, input.kernel.virtual_size);
    write_u64(&mut value, 40, input.kernel.entry_virtual);
    write_u64(&mut value, 48, input.retained.stack_top_virtual);
    write_u64(&mut value, 56, input.retained.page_table_root_physical);
    write_u64(&mut value, 64, input.handoff_physical_base);
    write_u64(&mut value, 72, input.retained.handoff_virtual_base);
    write_u64(&mut value, 80, total_bytes as u64);
    write_u32(&mut value, 104, input.kernel.boot_attempt);
    write_u32(&mut value, 108, input.kernel.boot_attempt_limit);
    write_u32(&mut value, 112, input.kernel.boot_slot);
    write_u32(&mut value, 116, input.kernel.selected_entry);
    write_u32(&mut value, 120, input.kernel.uefi_revision);
    value
}

fn overlaps(first: u64, first_bytes: u64, second: u64, second_bytes: u64) -> bool {
    first < second.saturating_add(second_bytes) && second < first.saturating_add(first_bytes)
}

fn validate_artifact_set(
    kernel: KernelInput,
    artifacts: &[ArtifactInput; PROFILE_ARTIFACT_COUNT],
) -> Result<(), Error> {
    for (index, artifact) in artifacts.iter().enumerate() {
        let expected_flags = if index == 0 {
            ARTIFACT_HASH_VERIFIED | ARTIFACT_EXECUTABLE
        } else {
            ARTIFACT_HASH_VERIFIED
        };
        if artifact.role != PROFILE_ARTIFACT_ROLES[index]
            || artifact.flags != expected_flags
            || artifact.physical_base == 0
            || !artifact.physical_base.is_multiple_of(pbp1::PAGE_BYTES)
            || artifact.physical_size == 0
            || artifact
                .physical_base
                .checked_add(artifact.physical_size)
                .is_none()
            || artifact.sha256.iter().all(|byte| *byte == 0)
        {
            return Err(Error::ArtifactSet);
        }
        if index == 0 {
            if !artifact.physical_size.is_multiple_of(pbp1::PAGE_BYTES)
                || artifact.physical_base != kernel.physical_base
                || artifact.physical_size != kernel.physical_size
                || artifact.virtual_base != kernel.virtual_base
                || artifact.virtual_size != kernel.virtual_size
                || artifact.entry_virtual != kernel.entry_virtual
                || artifact.sha256 != kernel.sha256
            {
                return Err(Error::ArtifactSet);
            }
        } else if artifact.virtual_base != 0
            || artifact.virtual_size != 0
            || artifact.entry_virtual != 0
        {
            return Err(Error::ArtifactSet);
        }
    }
    for first in 0..artifacts.len() {
        for second in first + 1..artifacts.len() {
            if overlaps(
                artifacts[first].physical_base,
                artifacts[first].physical_size,
                artifacts[second].physical_base,
                artifacts[second].physical_size,
            ) {
                return Err(Error::ArtifactSet);
            }
        }
    }
    Ok(())
}

fn validate_retained_shape(input: &ExitBuildInput<'_>) -> Result<(), Error> {
    validate_artifact_set(input.kernel, &input.artifacts)?;
    let retained = input.retained;
    if retained.page_table_root_physical == 0
        || !retained
            .page_table_root_physical
            .is_multiple_of(pbp1::PAGE_BYTES)
        || retained.table_page_count != RETAINED_TABLE_PAGE_COUNT
        || retained.stack_physical_base == 0
        || !retained
            .stack_physical_base
            .is_multiple_of(pbp1::PAGE_BYTES)
        || retained.stack_page_count != RETAINED_STACK_PAGE_COUNT
        || retained.stack_top_virtual == 0
        || !retained.stack_top_virtual.is_multiple_of(16)
        || retained.handoff_virtual_base == 0
        || !retained
            .handoff_virtual_base
            .is_multiple_of(pbp1::PAGE_BYTES)
        || retained.handoff_capacity_bytes as usize != pbp1::MAX_TOTAL_BYTES
        || input.handoff_physical_base == 0
        || !input.handoff_physical_base.is_multiple_of(pbp1::PAGE_BYTES)
    {
        return Err(Error::RetainedRange);
    }
    let mut ranges = [(0u64, 0u64); PROFILE_ARTIFACT_COUNT + 3];
    for (index, artifact) in input.artifacts.iter().enumerate() {
        ranges[index] = (artifact.physical_base, artifact.physical_size);
    }
    ranges[PROFILE_ARTIFACT_COUNT] = (
        retained.page_table_root_physical,
        u64::from(retained.table_page_count) * pbp1::PAGE_BYTES,
    );
    ranges[PROFILE_ARTIFACT_COUNT + 1] = (
        retained.stack_physical_base,
        u64::from(retained.stack_page_count) * pbp1::PAGE_BYTES,
    );
    ranges[PROFILE_ARTIFACT_COUNT + 2] = (
        input.handoff_physical_base,
        u64::from(retained.handoff_capacity_bytes),
    );
    for (start, byte_count) in ranges {
        if start == 0 || byte_count == 0 || start.checked_add(byte_count).is_none() {
            return Err(Error::RetainedRange);
        }
    }
    for first in 0..ranges.len() {
        for second in first + 1..ranges.len() {
            if overlaps(
                ranges[first].0,
                ranges[first].1,
                ranges[second].0,
                ranges[second].1,
            ) {
                return Err(Error::RetainedRange);
            }
        }
    }
    Ok(())
}

fn loader_range_covered(
    normalized: &[u8],
    count: usize,
    start: u64,
    byte_count: u64,
) -> Result<bool, Error> {
    let end = start.checked_add(byte_count).ok_or(Error::RetainedRange)?;
    let mut cursor = start;
    for index in 0..count {
        let base = index * MEMORY_ENTRY_BYTES;
        let entry_start = read_u64(normalized, base)?;
        let pages = read_u64(normalized, base + 8)?;
        let entry_end = entry_start
            .checked_add(
                pages
                    .checked_mul(pbp1::PAGE_BYTES)
                    .ok_or(Error::RetainedRange)?,
            )
            .ok_or(Error::RetainedRange)?;
        if cursor < entry_start {
            return Ok(false);
        }
        if cursor >= entry_end {
            continue;
        }
        if read_u32(normalized, base + 24)? != MEMORY_LOADER_RESERVED {
            return Ok(false);
        }
        cursor = core::cmp::min(entry_end, end);
        if cursor == end {
            return Ok(true);
        }
    }
    Ok(false)
}

fn validate_retained_coverage(
    input: &ExitBuildInput<'_>,
    normalized: &[u8],
    count: usize,
) -> Result<(), Error> {
    let retained = input.retained;
    let mut ranges = [(0u64, 0u64); PROFILE_ARTIFACT_COUNT + 3];
    for (index, artifact) in input.artifacts.iter().enumerate() {
        ranges[index] = (artifact.physical_base, artifact.physical_size);
    }
    ranges[PROFILE_ARTIFACT_COUNT] = (
        retained.page_table_root_physical,
        u64::from(retained.table_page_count) * pbp1::PAGE_BYTES,
    );
    ranges[PROFILE_ARTIFACT_COUNT + 1] = (
        retained.stack_physical_base,
        u64::from(retained.stack_page_count) * pbp1::PAGE_BYTES,
    );
    ranges[PROFILE_ARTIFACT_COUNT + 2] = (
        input.handoff_physical_base,
        u64::from(retained.handoff_capacity_bytes),
    );
    for (start, byte_count) in ranges {
        if !loader_range_covered(normalized, count, start, byte_count)? {
            return Err(Error::RetainedRange);
        }
    }
    Ok(())
}

fn framebuffer_payload(input: FramebufferInput) -> [u8; FRAMEBUFFER_BYTES] {
    let mut value = [0u8; FRAMEBUFFER_BYTES];
    write_u64(&mut value, 0, input.physical_base);
    write_u64(&mut value, 8, input.byte_count);
    write_u32(&mut value, 16, input.width);
    write_u32(&mut value, 20, input.height);
    write_u32(&mut value, 24, input.stride);
    write_u32(&mut value, 28, input.pixel_format);
    write_u32(&mut value, 32, input.red_mask);
    write_u32(&mut value, 36, input.green_mask);
    write_u32(&mut value, 40, input.blue_mask);
    write_u32(&mut value, 44, input.reserved_mask);
    value
}

fn artifact_payload(
    input: &[ArtifactInput; PROFILE_ARTIFACT_COUNT],
) -> [u8; ARTIFACT_ENTRY_BYTES * PROFILE_ARTIFACT_COUNT] {
    let mut value = [0u8; ARTIFACT_ENTRY_BYTES * PROFILE_ARTIFACT_COUNT];
    for (index, artifact) in input.iter().enumerate() {
        let base = index * ARTIFACT_ENTRY_BYTES;
        write_u32(&mut value, base, artifact.role);
        write_u32(&mut value, base + 4, artifact.flags);
        write_u64(&mut value, base + 8, artifact.physical_base);
        write_u64(&mut value, base + 16, artifact.physical_size);
        write_u64(&mut value, base + 24, artifact.virtual_base);
        write_u64(&mut value, base + 32, artifact.virtual_size);
        write_u64(&mut value, base + 40, artifact.entry_virtual);
        value[base + 48..base + 80].copy_from_slice(&artifact.sha256);
    }
    value
}

fn validate_profile_artifact_record(
    artifacts: &pbp1::Record<'_>,
    profile_error: Error,
) -> Result<(), Error> {
    if artifacts.descriptor.element_count != PROFILE_ARTIFACT_COUNT {
        return Err(profile_error);
    }
    for (index, role) in PROFILE_ARTIFACT_ROLES.iter().copied().enumerate() {
        let base = index * ARTIFACT_ENTRY_BYTES;
        let expected_flags = if index == 0 {
            ARTIFACT_HASH_VERIFIED | ARTIFACT_EXECUTABLE
        } else {
            ARTIFACT_HASH_VERIFIED
        };
        if read_u32(artifacts.payload, base)? != role
            || read_u32(artifacts.payload, base + 4)? != expected_flags
            || (index != 0
                && (read_u64(artifacts.payload, base + 24)? != 0
                    || read_u64(artifacts.payload, base + 32)? != 0
                    || read_u64(artifacts.payload, base + 40)? != 0))
        {
            return Err(profile_error);
        }
    }
    Ok(())
}

pub fn validate_pre_exit_profile(handoff: &pbp1::Handoff<'_>) -> Result<(), Error> {
    let expected_features = pbp1::FEATURE_CORE
        | pbp1::FEATURE_MEMORY_MAP
        | pbp1::FEATURE_LOADED_ARTIFACTS
        | if handoff.record(RECORD_FRAMEBUFFER).is_some() {
            pbp1::FEATURE_FRAMEBUFFER
        } else {
            0
        };
    let expected_required =
        pbp1::FEATURE_CORE | pbp1::FEATURE_MEMORY_MAP | pbp1::FEATURE_LOADED_ARTIFACTS;
    let header = handoff.header();
    let core = handoff.core()?;
    if header.features != expected_features
        || header.required_features != expected_required
        || !matches!(header.record_count, 3 | 4)
        || core.boot_flags != DEVELOPMENT_MODE
        || core.initial_stack_top_virtual != 0
        || core.page_table_root_physical != 0
        || core.uefi_system_table_physical != 0
        || core.uefi_runtime_services_physical != 0
    {
        return Err(Error::PreExitProfile);
    }
    let artifacts = handoff
        .record(RECORD_LOADED_ARTIFACTS)
        .ok_or(Error::PreExitProfile)?;
    validate_profile_artifact_record(&artifacts, Error::PreExitProfile)?;
    if pbp1::validate_kernel_entry_profile(handoff).is_ok() {
        return Err(Error::PreExitProfile);
    }
    Ok(())
}

pub fn validate_exit_development_profile(handoff: &pbp1::Handoff<'_>) -> Result<(), Error> {
    let expected_features = pbp1::FEATURE_CORE
        | pbp1::FEATURE_MEMORY_MAP
        | pbp1::FEATURE_LOADED_ARTIFACTS
        | if handoff.record(RECORD_FRAMEBUFFER).is_some() {
            pbp1::FEATURE_FRAMEBUFFER
        } else {
            0
        };
    let expected_required =
        pbp1::FEATURE_CORE | pbp1::FEATURE_MEMORY_MAP | pbp1::FEATURE_LOADED_ARTIFACTS;
    let header = handoff.header();
    let core = handoff.core()?;
    if header.features != expected_features
        || header.required_features != expected_required
        || !matches!(header.record_count, 3 | 4)
        || core.boot_flags != DEVELOPMENT_MODE | BOOT_SERVICES_EXITED
        || core.initial_stack_top_virtual == 0
        || !core.initial_stack_top_virtual.is_multiple_of(16)
        || core.page_table_root_physical == 0
        || !core
            .page_table_root_physical
            .is_multiple_of(pbp1::PAGE_BYTES)
        || core.uefi_system_table_physical != 0
        || core.uefi_runtime_services_physical != 0
    {
        return Err(Error::ExitProfile);
    }
    let artifacts = handoff
        .record(RECORD_LOADED_ARTIFACTS)
        .ok_or(Error::ExitProfile)?;
    validate_profile_artifact_record(&artifacts, Error::ExitProfile)?;
    if pbp1::validate_kernel_entry_profile(handoff).is_ok() {
        return Err(Error::ExitProfile);
    }
    Ok(())
}

pub fn build_pre_exit<'a>(
    input: BuildInput<'_>,
    normalized_memory: &mut [u8],
    output: &'a mut [u8],
) -> Result<(&'a [u8], Summary), Error> {
    validate_artifact_set(input.kernel, &input.artifacts)?;
    if input.handoff_physical_base == 0
        || !input
            .handoff_physical_base
            .is_multiple_of(pbp1::ALIGNMENT as u64)
    {
        return Err(Error::OutputCapacity);
    }
    let memory_count = normalize_memory_map(
        input.raw_memory_map,
        input.descriptor_size,
        input.descriptor_version,
        normalized_memory,
    )?;
    let memory_bytes = memory_count * MEMORY_ENTRY_BYTES;
    let record_count = if input.framebuffer.is_some() { 4 } else { 3 };
    let artifact_bytes = ARTIFACT_ENTRY_BYTES * PROFILE_ARTIFACT_COUNT;
    let mut lengths = [CORE_BYTES, memory_bytes, artifact_bytes, 0];
    if input.framebuffer.is_some() {
        lengths[2] = FRAMEBUFFER_BYTES;
        lengths[3] = artifact_bytes;
    }
    let total_bytes = pbp1::encoded_size(record_count, &lengths[..record_count])?;
    if output.len() < total_bytes {
        return Err(Error::OutputCapacity);
    }
    let core = core_payload(&input, total_bytes);
    let artifacts = artifact_payload(&input.artifacts);
    let mut encoder = Encoder::new(&mut output[..total_bytes], record_count, 0, 0)?;
    encoder.push(RECORD_CORE, 1, RECORD_REQUIRED, CORE_BYTES, 1, &core)?;
    encoder.push(
        RECORD_MEMORY_MAP,
        1,
        RECORD_REQUIRED | RECORD_ARRAY,
        MEMORY_ENTRY_BYTES,
        memory_count,
        &normalized_memory[..memory_bytes],
    )?;
    if let Some(framebuffer) = input.framebuffer {
        let framebuffer = framebuffer_payload(framebuffer);
        encoder.push(RECORD_FRAMEBUFFER, 1, 0, FRAMEBUFFER_BYTES, 1, &framebuffer)?;
    }
    encoder.push(
        RECORD_LOADED_ARTIFACTS,
        1,
        RECORD_REQUIRED | RECORD_ARRAY,
        ARTIFACT_ENTRY_BYTES,
        PROFILE_ARTIFACT_COUNT,
        &artifacts,
    )?;
    let bytes = encoder.finish()?;
    let handoff = pbp1::decode(bytes)?;
    validate_pre_exit_profile(&handoff)?;
    let summary = Summary {
        total_bytes: bytes.len(),
        record_count,
        memory_entry_count: memory_count,
        framebuffer_present: input.framebuffer.is_some(),
        artifact_count: PROFILE_ARTIFACT_COUNT,
        message_crc32: read_u32(bytes, 48)?,
        fnv1a64: fnv1a64(bytes),
    };
    Ok((bytes, summary))
}

pub fn build_exit_candidate<'a>(
    input: ExitBuildInput<'_>,
    normalized_memory: &mut [u8],
    output: &'a mut [u8],
) -> Result<(&'a [u8], Summary), Error> {
    validate_retained_shape(&input)?;
    let memory_count = normalize_memory_map(
        input.raw_memory_map,
        input.descriptor_size,
        input.descriptor_version,
        normalized_memory,
    )?;
    let memory_bytes = memory_count * MEMORY_ENTRY_BYTES;
    validate_retained_coverage(&input, &normalized_memory[..memory_bytes], memory_count)?;
    let record_count = if input.framebuffer.is_some() { 4 } else { 3 };
    let artifact_bytes = ARTIFACT_ENTRY_BYTES * PROFILE_ARTIFACT_COUNT;
    let mut lengths = [CORE_BYTES, memory_bytes, artifact_bytes, 0];
    if input.framebuffer.is_some() {
        lengths[2] = FRAMEBUFFER_BYTES;
        lengths[3] = artifact_bytes;
    }
    let total_bytes = pbp1::encoded_size(record_count, &lengths[..record_count])?;
    if output.len() < total_bytes
        || total_bytes
            > usize::try_from(input.retained.handoff_capacity_bytes)
                .map_err(|_| Error::OutputCapacity)?
    {
        return Err(Error::OutputCapacity);
    }
    let core = exit_core_payload(&input, total_bytes);
    let artifacts = artifact_payload(&input.artifacts);
    let mut encoder = Encoder::new(&mut output[..total_bytes], record_count, 0, 0)?;
    encoder.push(RECORD_CORE, 1, RECORD_REQUIRED, CORE_BYTES, 1, &core)?;
    encoder.push(
        RECORD_MEMORY_MAP,
        1,
        RECORD_REQUIRED | RECORD_ARRAY,
        MEMORY_ENTRY_BYTES,
        memory_count,
        &normalized_memory[..memory_bytes],
    )?;
    if let Some(framebuffer) = input.framebuffer {
        let framebuffer = framebuffer_payload(framebuffer);
        encoder.push(RECORD_FRAMEBUFFER, 1, 0, FRAMEBUFFER_BYTES, 1, &framebuffer)?;
    }
    encoder.push(
        RECORD_LOADED_ARTIFACTS,
        1,
        RECORD_REQUIRED | RECORD_ARRAY,
        ARTIFACT_ENTRY_BYTES,
        PROFILE_ARTIFACT_COUNT,
        &artifacts,
    )?;
    let bytes = encoder.finish()?;
    let handoff = pbp1::decode(bytes)?;
    validate_exit_development_profile(&handoff)?;
    let summary = Summary {
        total_bytes: bytes.len(),
        record_count,
        memory_entry_count: memory_count,
        framebuffer_present: input.framebuffer.is_some(),
        artifact_count: PROFILE_ARTIFACT_COUNT,
        message_crc32: read_u32(bytes, 48)?,
        fnv1a64: fnv1a64(bytes),
    };
    Ok((bytes, summary))
}

pub fn fnv1a64(bytes: &[u8]) -> u64 {
    let mut value = 0xcbf2_9ce4_8422_2325u64;
    for byte in bytes {
        value ^= u64::from(*byte);
        value = value.wrapping_mul(0x0000_0100_0000_01b3);
    }
    value
}

#[cfg(test)]
mod tests {
    extern crate std;

    use super::*;
    use std::vec;

    fn descriptor(
        source_type: u32,
        start: u64,
        pages: u64,
        attributes: u64,
        stride: usize,
    ) -> std::vec::Vec<u8> {
        let mut value = vec![0xa5; stride];
        write_u32(&mut value, 0, source_type);
        write_u64(&mut value, 8, start);
        write_u64(&mut value, 16, 0);
        write_u64(&mut value, 24, pages);
        write_u64(&mut value, 32, attributes);
        value
    }

    fn raw_map(stride: usize) -> std::vec::Vec<u8> {
        let mut value = descriptor(7, 0x0040_0000, 16, 8, stride);
        value.extend(descriptor(2, 0x0020_0000, 48, 4, stride));
        value.extend(descriptor(11, 0x8000_0000, 256, 1, stride));
        value
    }

    fn exit_raw_map(stride: usize) -> std::vec::Vec<u8> {
        let mut value = descriptor(2, 0x0020_0000, 48, 4, stride);
        value.extend(descriptor(2, 0x0030_0000, 4, 4, stride));
        value.extend(descriptor(2, 0x0040_0000, 14, 4, stride));
        value.extend(descriptor(2, 0x0050_0000, 256, 4, stride));
        value.extend(descriptor(11, 0x8000_0000, 1024, 1, stride));
        value
    }

    fn kernel() -> KernelInput {
        KernelInput {
            physical_base: 0x0020_0000,
            physical_size: 0x0002_0000,
            virtual_base: 0xffff_ffff_8000_0000,
            virtual_size: 0x0002_0000,
            entry_virtual: 0xffff_ffff_8000_4000,
            sha256: [0x5a; 32],
            boot_attempt: 0,
            boot_attempt_limit: 3,
            boot_slot: 1,
            selected_entry: 1,
            uefi_revision: 0x0002_0064,
        }
    }

    fn artifacts() -> [ArtifactInput; PROFILE_ARTIFACT_COUNT] {
        let kernel = kernel();
        let mut values = [ArtifactInput {
            role: ARTIFACT_KERNEL,
            flags: ARTIFACT_HASH_VERIFIED | ARTIFACT_EXECUTABLE,
            physical_base: kernel.physical_base,
            physical_size: kernel.physical_size,
            virtual_base: kernel.virtual_base,
            virtual_size: kernel.virtual_size,
            entry_virtual: kernel.entry_virtual,
            sha256: kernel.sha256,
        }; PROFILE_ARTIFACT_COUNT];
        for index in 1..PROFILE_ARTIFACT_COUNT {
            values[index] = ArtifactInput {
                role: PROFILE_ARTIFACT_ROLES[index],
                flags: ARTIFACT_HASH_VERIFIED,
                physical_base: 0x0022_0000 + (index as u64 - 1) * pbp1::PAGE_BYTES,
                physical_size: 256 + index as u64,
                virtual_base: 0,
                virtual_size: 0,
                entry_virtual: 0,
                sha256: [PROFILE_ARTIFACT_ROLES[index] as u8; 32],
            };
        }
        values
    }

    fn framebuffer() -> FramebufferInput {
        FramebufferInput {
            physical_base: 0x8000_0000,
            byte_count: 0x0040_0000,
            width: 1024,
            height: 768,
            stride: 1024,
            pixel_format: 1,
            red_mask: 0x0000_00ff,
            green_mask: 0x0000_ff00,
            blue_mask: 0x00ff_0000,
            reserved_mask: 0xff00_0000,
        }
    }

    fn retained() -> RetainedInput {
        RetainedInput {
            page_table_root_physical: 0x0030_0000,
            table_page_count: RETAINED_TABLE_PAGE_COUNT,
            stack_physical_base: 0x0040_0000,
            stack_page_count: RETAINED_STACK_PAGE_COUNT,
            stack_top_virtual: 0xffff_ffff_8004_f000,
            handoff_virtual_base: 0xffff_ffff_8005_0000,
            handoff_capacity_bytes: pbp1::MAX_TOTAL_BYTES as u32,
        }
    }

    #[test]
    fn descriptor_stride_is_honored_and_entries_are_sorted() {
        let raw = raw_map(48);
        let mut output = [0u8; 3 * MEMORY_ENTRY_BYTES];
        assert_eq!(
            normalize_memory_map(&raw, 48, UEFI_DESCRIPTOR_VERSION, &mut output),
            Ok(3)
        );
        assert_eq!(read_u64(&output, 0).unwrap(), 0x0020_0000);
        assert_eq!(read_u64(&output, MEMORY_ENTRY_BYTES).unwrap(), 0x0040_0000);
        assert_eq!(read_u32(&output, 24).unwrap(), MEMORY_LOADER_RESERVED);
        assert_eq!(read_u32(&output, 28).unwrap(), 2);
        assert_eq!(read_u64(&output, 16).unwrap(), 4);
    }

    #[test]
    fn all_standard_uefi_types_have_a_fail_closed_mapping() {
        let expected = [
            MEMORY_RESERVED,
            MEMORY_LOADER_RESERVED,
            MEMORY_LOADER_RESERVED,
            MEMORY_BOOT_RECLAIMABLE,
            MEMORY_BOOT_RECLAIMABLE,
            MEMORY_RUNTIME_CODE,
            MEMORY_RUNTIME_DATA,
            MEMORY_USABLE,
            MEMORY_UNUSABLE,
            MEMORY_ACPI_RECLAIMABLE,
            MEMORY_ACPI_NVS,
            MEMORY_MMIO,
            MEMORY_MMIO,
            MEMORY_RESERVED,
            MEMORY_PERSISTENT,
            MEMORY_RESERVED,
        ];
        for (source, expected) in expected.into_iter().enumerate() {
            assert_eq!(normalized_kind(source as u32), Ok(expected));
        }
        assert_eq!(normalized_kind(16), Err(Error::MemoryType));
    }

    #[test]
    fn malformed_descriptor_geometry_and_ranges_fail_closed() {
        let mut scratch = [0u8; MEMORY_ENTRY_BYTES];
        let raw = descriptor(7, 0x1000, 1, 0, 40);
        assert_eq!(
            normalize_memory_map(&raw, 39, 1, &mut scratch),
            Err(Error::DescriptorSize)
        );
        assert_eq!(
            normalize_memory_map(&raw, 40, 2, &mut scratch),
            Err(Error::DescriptorVersion)
        );
        assert_eq!(
            normalize_memory_map(&raw[..39], 40, 1, &mut scratch),
            Err(Error::MemoryMapShape)
        );
        let raw = descriptor(7, 0x1001, 1, 0, 40);
        assert_eq!(
            normalize_memory_map(&raw, 40, 1, &mut scratch),
            Err(Error::MemoryRange)
        );
        let raw = descriptor(7, 0x1000, 0, 0, 40);
        assert_eq!(
            normalize_memory_map(&raw, 40, 1, &mut scratch),
            Err(Error::MemoryRange)
        );
    }

    #[test]
    fn overlap_and_capacity_fail_closed() {
        let mut raw = descriptor(7, 0x1000, 2, 0, 40);
        raw.extend(descriptor(2, 0x2000, 1, 0, 40));
        let mut scratch = [0u8; 2 * MEMORY_ENTRY_BYTES];
        assert_eq!(
            normalize_memory_map(&raw, 40, 1, &mut scratch),
            Err(Error::MemoryOverlap)
        );
        assert_eq!(
            normalize_memory_map(&raw_map(40), 40, 1, &mut scratch),
            Err(Error::ScratchCapacity)
        );
    }

    #[test]
    fn pre_exit_snapshot_with_framebuffer_is_exact_and_non_transferable() {
        let raw = raw_map(48);
        let mut scratch = [0u8; 3 * MEMORY_ENTRY_BYTES];
        let mut output = [0u8; 2048];
        let input = BuildInput {
            raw_memory_map: &raw,
            descriptor_size: 48,
            descriptor_version: 1,
            handoff_physical_base: 0x0030_0000,
            kernel: kernel(),
            artifacts: artifacts(),
            framebuffer: Some(framebuffer()),
        };
        let (bytes, summary) = build_pre_exit(input, &mut scratch, &mut output).unwrap();
        assert_eq!(summary.record_count, 4);
        assert_eq!(summary.memory_entry_count, 3);
        assert!(summary.framebuffer_present);
        assert_eq!(summary.artifact_count, PROFILE_ARTIFACT_COUNT);
        assert_eq!(summary.fnv1a64, fnv1a64(bytes));
        let decoded = pbp1::decode(bytes).unwrap();
        assert_eq!(validate_pre_exit_profile(&decoded), Ok(()));
        assert_eq!(
            pbp1::validate_kernel_entry_profile(&decoded),
            Err(pbp1::Error::KernelProfile)
        );
    }

    #[test]
    fn framebuffer_is_optional_and_output_capacity_is_bounded() {
        let raw = raw_map(40);
        let mut scratch = [0u8; 3 * MEMORY_ENTRY_BYTES];
        let mut output = [0u8; 2048];
        let input = BuildInput {
            raw_memory_map: &raw,
            descriptor_size: 40,
            descriptor_version: 1,
            handoff_physical_base: 0x0030_0000,
            kernel: kernel(),
            artifacts: artifacts(),
            framebuffer: None,
        };
        let (_, summary) = build_pre_exit(input, &mut scratch, &mut output).unwrap();
        assert_eq!(summary.record_count, 3);
        let mut tiny = [0u8; 128];
        assert_eq!(
            build_pre_exit(input, &mut scratch, &mut tiny).map(|_| ()),
            Err(Error::OutputCapacity)
        );
    }

    #[test]
    fn exited_development_handoff_binds_every_retained_range() {
        let raw = exit_raw_map(48);
        let mut scratch = [0u8; 5 * MEMORY_ENTRY_BYTES];
        let mut output = [0u8; 4096];
        let input = ExitBuildInput {
            raw_memory_map: &raw,
            descriptor_size: 48,
            descriptor_version: 1,
            handoff_physical_base: 0x0050_0000,
            kernel: kernel(),
            artifacts: artifacts(),
            framebuffer: Some(framebuffer()),
            retained: retained(),
        };
        let (bytes, summary) = build_exit_candidate(input, &mut scratch, &mut output).unwrap();
        assert_eq!(summary.record_count, 4);
        assert_eq!(summary.memory_entry_count, 5);
        assert_eq!(summary.artifact_count, PROFILE_ARTIFACT_COUNT);
        let decoded = pbp1::decode(bytes).unwrap();
        assert_eq!(validate_exit_development_profile(&decoded), Ok(()));
        let core = decoded.core().unwrap();
        assert_eq!(core.boot_flags, DEVELOPMENT_MODE | BOOT_SERVICES_EXITED);
        assert_eq!(core.initial_stack_top_virtual, retained().stack_top_virtual);
        assert_eq!(
            core.page_table_root_physical,
            retained().page_table_root_physical
        );
        assert_eq!(core.handoff_virtual_base, retained().handoff_virtual_base);
        assert_eq!(
            pbp1::validate_kernel_entry_profile(&decoded),
            Err(pbp1::Error::KernelProfile)
        );
    }

    #[test]
    fn exited_handoff_rejects_missing_or_overlapping_retained_ranges() {
        let mut raw = exit_raw_map(48);
        write_u32(&mut raw, 2 * 48, 7);
        let mut scratch = [0u8; 5 * MEMORY_ENTRY_BYTES];
        let mut output = [0u8; 4096];
        let input = ExitBuildInput {
            raw_memory_map: &raw,
            descriptor_size: 48,
            descriptor_version: 1,
            handoff_physical_base: 0x0050_0000,
            kernel: kernel(),
            artifacts: artifacts(),
            framebuffer: Some(framebuffer()),
            retained: retained(),
        };
        assert_eq!(
            build_exit_candidate(input, &mut scratch, &mut output).map(|_| ()),
            Err(Error::RetainedRange)
        );
        let mut overlap = retained();
        overlap.stack_physical_base = kernel().physical_base;
        let input = ExitBuildInput {
            retained: overlap,
            ..input
        };
        assert_eq!(
            build_exit_candidate(input, &mut scratch, &mut output).map(|_| ()),
            Err(Error::RetainedRange)
        );
        let mut overlapping_artifacts = artifacts();
        overlapping_artifacts[2].physical_base = overlapping_artifacts[1].physical_base;
        let input = ExitBuildInput {
            artifacts: overlapping_artifacts,
            ..input
        };
        assert_eq!(
            build_exit_candidate(input, &mut scratch, &mut output).map(|_| ()),
            Err(Error::ArtifactSet)
        );
    }
}
