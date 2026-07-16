#![no_std]
#![deny(warnings)]

use core::str;

pub const MAGIC: [u8; 8] = *b"PBP1\r\n\x1a\n";
pub const MAJOR: u16 = 1;
pub const MINOR: u16 = 0;
pub const HEADER_BYTES: usize = 64;
pub const DESCRIPTOR_BYTES: usize = 32;
pub const ALIGNMENT: usize = 8;
pub const MAX_TOTAL_BYTES: usize = 1024 * 1024;
pub const MAX_RECORDS: usize = 32;
pub const PAGE_BYTES: u64 = 4096;

pub const RECORD_CORE: u16 = 1;
pub const RECORD_MEMORY_MAP: u16 = 2;
pub const RECORD_FRAMEBUFFER: u16 = 3;
pub const RECORD_FIRMWARE_TABLES: u16 = 4;
pub const RECORD_LOADED_ARTIFACTS: u16 = 5;
pub const RECORD_COMMAND_LINE: u16 = 6;
pub const RECORD_BOOT_DEVICE: u16 = 7;
pub const RECORD_RANDOM_SEED: u16 = 8;
pub const RECORD_EARLY_LOG: u16 = 9;
pub const RECORD_CPU_BOOTSTRAP: u16 = 10;
pub const RECORD_BOOT_TIMESTAMPS: u16 = 11;
pub const RECORD_TCG_EVENT_LOG: u16 = 12;
pub const FIRST_EXTENSION_RECORD: u16 = 0x8000;

pub const FEATURE_CORE: u64 = 1 << 0;
pub const FEATURE_MEMORY_MAP: u64 = 1 << 1;
pub const FEATURE_FRAMEBUFFER: u64 = 1 << 2;
pub const FEATURE_FIRMWARE_TABLES: u64 = 1 << 3;
pub const FEATURE_LOADED_ARTIFACTS: u64 = 1 << 4;
pub const FEATURE_COMMAND_LINE: u64 = 1 << 5;
pub const FEATURE_BOOT_DEVICE: u64 = 1 << 6;
pub const FEATURE_RANDOM_SEED: u64 = 1 << 7;
pub const FEATURE_EARLY_LOG: u64 = 1 << 8;
pub const FEATURE_CPU_BOOTSTRAP: u64 = 1 << 9;
pub const FEATURE_BOOT_TIMESTAMPS: u64 = 1 << 10;
pub const FEATURE_TCG_EVENT_LOG: u64 = 1 << 11;
pub const KNOWN_FEATURES: u64 = (1 << 12) - 1;
pub const BASE_REQUIRED_FEATURES: u64 = FEATURE_CORE | FEATURE_MEMORY_MAP;
pub const KERNEL_ENTRY_REQUIRED_FEATURES: u64 = FEATURE_CORE
    | FEATURE_MEMORY_MAP
    | FEATURE_FIRMWARE_TABLES
    | FEATURE_LOADED_ARTIFACTS
    | FEATURE_BOOT_DEVICE
    | FEATURE_RANDOM_SEED
    | FEATURE_CPU_BOOTSTRAP;

pub const RECORD_REQUIRED: u32 = 1 << 0;
pub const RECORD_ARRAY: u32 = 1 << 1;
pub const RECORD_REDACT: u32 = 1 << 2;
const KNOWN_RECORD_FLAGS: u32 = RECORD_REQUIRED | RECORD_ARRAY | RECORD_REDACT;

pub const BOOT_SERVICES_EXITED: u64 = 1 << 0;
pub const SECURE_BOOT_ENABLED: u64 = 1 << 1;
pub const SECURE_BOOT_VERIFIED: u64 = 1 << 2;
pub const MEASURED_BOOT_ACTIVE: u64 = 1 << 3;
pub const DEVELOPMENT_MODE: u64 = 1 << 4;
pub const RECOVERY_MODE: u64 = 1 << 5;
pub const SAFE_MODE: u64 = 1 << 6;
pub const RUNTIME_SERVICES_RETAINED: u64 = 1 << 7;
const KNOWN_BOOT_FLAGS: u64 = (1 << 8) - 1;

pub const ARTIFACT_KERNEL: u32 = 1;
pub const ARTIFACT_INITIAL_SYSTEM: u32 = 2;
pub const ARTIFACT_RECOVERY: u32 = 3;
pub const ARTIFACT_SYMBOLS: u32 = 4;
pub const ARTIFACT_MICROCODE: u32 = 5;
pub const ARTIFACT_FIRMWARE_MANIFEST: u32 = 6;
pub const ARTIFACT_POLICY_BUNDLE: u32 = 7;
pub const ARTIFACT_CRASH_KERNEL: u32 = 8;
pub const ARTIFACT_HASH_VERIFIED: u32 = 1 << 0;
pub const ARTIFACT_SIGNATURE_VERIFIED: u32 = 1 << 1;
pub const ARTIFACT_MEASURED: u32 = 1 << 2;
pub const ARTIFACT_EXECUTABLE: u32 = 1 << 3;
pub const ARTIFACT_WRITABLE: u32 = 1 << 4;
const KNOWN_ARTIFACT_FLAGS: u32 = (1 << 5) - 1;

pub const MEMORY_RESERVED: u32 = 0;
pub const MEMORY_USABLE: u32 = 1;
pub const MEMORY_BOOT_RECLAIMABLE: u32 = 2;
pub const MEMORY_RUNTIME_CODE: u32 = 3;
pub const MEMORY_RUNTIME_DATA: u32 = 4;
pub const MEMORY_ACPI_RECLAIMABLE: u32 = 5;
pub const MEMORY_ACPI_NVS: u32 = 6;
pub const MEMORY_MMIO: u32 = 7;
pub const MEMORY_PERSISTENT: u32 = 8;
pub const MEMORY_UNUSABLE: u32 = 9;
pub const MEMORY_LOADER_RESERVED: u32 = 10;
pub const MEMORY_FRAMEBUFFER: u32 = 11;

pub const CORE_BYTES: usize = 128;
pub const MEMORY_ENTRY_BYTES: usize = 40;
pub const FRAMEBUFFER_BYTES: usize = 48;
pub const FIRMWARE_TABLE_ENTRY_BYTES: usize = 40;
pub const ARTIFACT_ENTRY_BYTES: usize = 80;
pub const BOOT_DEVICE_BYTES: usize = 96;
pub const RANDOM_SEED_BYTES: usize = 72;
pub const EARLY_LOG_HEADER_BYTES: usize = 16;
pub const CPU_BOOTSTRAP_BYTES: usize = 64;
pub const BOOT_TIMESTAMPS_BYTES: usize = 48;
pub const TCG_EVENT_LOG_BYTES: usize = 56;

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum Error {
    BufferTooSmall,
    TotalSize,
    Magic,
    MajorVersion,
    MinorVersion,
    HeaderLayout,
    HeaderFlags,
    Reserved,
    RecordCount,
    ArithmeticOverflow,
    Checksum,
    RecordOrder,
    RecordFlags,
    RecordLayout,
    RecordChecksum,
    UnknownRequiredRecord,
    UnknownFeature,
    FeatureMismatch,
    MissingBaseRecord,
    PayloadShape,
    PayloadValue,
    AddressRange,
    Utf8,
    KernelProfile,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct Header {
    pub writer_major: u16,
    pub writer_minor: u16,
    pub minimum_reader_minor: u16,
    pub total_size: usize,
    pub record_count: usize,
    pub features: u64,
    pub required_features: u64,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct Descriptor {
    pub record_type: u16,
    pub revision: u16,
    pub flags: u32,
    pub offset: usize,
    pub length: usize,
    pub element_size: usize,
    pub element_count: usize,
    pub content_crc32: u32,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct CoreRecord {
    pub boot_flags: u64,
    pub kernel_physical_base: u64,
    pub kernel_physical_size: u64,
    pub kernel_virtual_base: u64,
    pub kernel_virtual_size: u64,
    pub kernel_entry_virtual: u64,
    pub initial_stack_top_virtual: u64,
    pub page_table_root_physical: u64,
    pub handoff_physical_base: u64,
    pub handoff_virtual_base: u64,
    pub handoff_byte_count: u64,
    pub uefi_system_table_physical: u64,
    pub uefi_runtime_services_physical: u64,
    pub boot_attempt: u32,
    pub boot_attempt_limit: u32,
    pub boot_slot: u32,
    pub selected_entry: u32,
    pub uefi_revision: u32,
}

#[derive(Clone, Copy)]
pub struct Record<'a> {
    pub descriptor: Descriptor,
    pub payload: &'a [u8],
}

pub struct Handoff<'a> {
    bytes: &'a [u8],
    header: Header,
}

pub struct Records<'a> {
    bytes: &'a [u8],
    index: usize,
    count: usize,
}

fn align_up(value: usize, alignment: usize) -> Result<usize, Error> {
    value
        .checked_add(alignment - 1)
        .map(|item| item & !(alignment - 1))
        .ok_or(Error::ArithmeticOverflow)
}

fn read_u16(bytes: &[u8], offset: usize) -> Result<u16, Error> {
    let value = bytes.get(offset..offset + 2).ok_or(Error::BufferTooSmall)?;
    Ok(u16::from_le_bytes([value[0], value[1]]))
}

fn read_u32(bytes: &[u8], offset: usize) -> Result<u32, Error> {
    let value = bytes.get(offset..offset + 4).ok_or(Error::BufferTooSmall)?;
    Ok(u32::from_le_bytes([value[0], value[1], value[2], value[3]]))
}

fn read_u64(bytes: &[u8], offset: usize) -> Result<u64, Error> {
    let value = bytes.get(offset..offset + 8).ok_or(Error::BufferTooSmall)?;
    Ok(u64::from_le_bytes([
        value[0], value[1], value[2], value[3], value[4], value[5], value[6], value[7],
    ]))
}

fn write_u16(bytes: &mut [u8], offset: usize, value: u16) -> Result<(), Error> {
    bytes
        .get_mut(offset..offset + 2)
        .ok_or(Error::BufferTooSmall)?
        .copy_from_slice(&value.to_le_bytes());
    Ok(())
}

fn write_u32(bytes: &mut [u8], offset: usize, value: u32) -> Result<(), Error> {
    bytes
        .get_mut(offset..offset + 4)
        .ok_or(Error::BufferTooSmall)?
        .copy_from_slice(&value.to_le_bytes());
    Ok(())
}

fn write_u64(bytes: &mut [u8], offset: usize, value: u64) -> Result<(), Error> {
    bytes
        .get_mut(offset..offset + 8)
        .ok_or(Error::BufferTooSmall)?
        .copy_from_slice(&value.to_le_bytes());
    Ok(())
}

pub fn crc32(bytes: &[u8]) -> u32 {
    let mut crc = u32::MAX;
    for byte in bytes {
        crc ^= u32::from(*byte);
        for _ in 0..8 {
            let mask = 0u32.wrapping_sub(crc & 1);
            crc = (crc >> 1) ^ (0xedb8_8320 & mask);
        }
    }
    !crc
}

fn message_crc32(bytes: &[u8]) -> u32 {
    let mut crc = u32::MAX;
    for (index, byte) in bytes.iter().enumerate() {
        let value = if (48..52).contains(&index) { 0 } else { *byte };
        crc ^= u32::from(value);
        for _ in 0..8 {
            let mask = 0u32.wrapping_sub(crc & 1);
            crc = (crc >> 1) ^ (0xedb8_8320 & mask);
        }
    }
    !crc
}

fn feature_for(record_type: u16) -> u64 {
    if (RECORD_CORE..=RECORD_TCG_EVENT_LOG).contains(&record_type) {
        1u64 << (record_type - 1)
    } else {
        0
    }
}

fn structural_flags(record_type: u16) -> u32 {
    match record_type {
        RECORD_MEMORY_MAP | RECORD_FIRMWARE_TABLES | RECORD_LOADED_ARTIFACTS => RECORD_ARRAY,
        RECORD_RANDOM_SEED => RECORD_REDACT,
        _ => 0,
    }
}

fn descriptor(bytes: &[u8], index: usize) -> Result<Descriptor, Error> {
    let base = HEADER_BYTES
        .checked_add(
            index
                .checked_mul(DESCRIPTOR_BYTES)
                .ok_or(Error::ArithmeticOverflow)?,
        )
        .ok_or(Error::ArithmeticOverflow)?;
    Ok(Descriptor {
        record_type: read_u16(bytes, base)?,
        revision: read_u16(bytes, base + 2)?,
        flags: read_u32(bytes, base + 4)?,
        offset: read_u32(bytes, base + 8)? as usize,
        length: read_u32(bytes, base + 12)? as usize,
        element_size: read_u16(bytes, base + 16)? as usize,
        element_count: read_u16(bytes, base + 18)? as usize,
        content_crc32: read_u32(bytes, base + 20)?,
    })
}

fn range_end(start: u64, size: u64) -> Result<u64, Error> {
    if size == 0 {
        return Err(Error::AddressRange);
    }
    start.checked_add(size).ok_or(Error::AddressRange)
}

fn all_zero(bytes: &[u8]) -> bool {
    bytes.iter().all(|value| *value == 0)
}

fn validate_core(payload: &[u8], total_size: Option<usize>) -> Result<CoreRecord, Error> {
    if payload.len() != CORE_BYTES || read_u32(payload, 124)? != 0 {
        return Err(Error::PayloadShape);
    }
    let core = CoreRecord {
        boot_flags: read_u64(payload, 0)?,
        kernel_physical_base: read_u64(payload, 8)?,
        kernel_physical_size: read_u64(payload, 16)?,
        kernel_virtual_base: read_u64(payload, 24)?,
        kernel_virtual_size: read_u64(payload, 32)?,
        kernel_entry_virtual: read_u64(payload, 40)?,
        initial_stack_top_virtual: read_u64(payload, 48)?,
        page_table_root_physical: read_u64(payload, 56)?,
        handoff_physical_base: read_u64(payload, 64)?,
        handoff_virtual_base: read_u64(payload, 72)?,
        handoff_byte_count: read_u64(payload, 80)?,
        uefi_system_table_physical: read_u64(payload, 88)?,
        uefi_runtime_services_physical: read_u64(payload, 96)?,
        boot_attempt: read_u32(payload, 104)?,
        boot_attempt_limit: read_u32(payload, 108)?,
        boot_slot: read_u32(payload, 112)?,
        selected_entry: read_u32(payload, 116)?,
        uefi_revision: read_u32(payload, 120)?,
    };
    if core.boot_flags & !KNOWN_BOOT_FLAGS != 0
        || !core.kernel_physical_base.is_multiple_of(PAGE_BYTES)
        || !core.kernel_virtual_base.is_multiple_of(PAGE_BYTES)
        || core.page_table_root_physical == 0
        || !core.page_table_root_physical.is_multiple_of(PAGE_BYTES)
        || core.handoff_physical_base == 0
        || !core.handoff_physical_base.is_multiple_of(ALIGNMENT as u64)
        || core.handoff_virtual_base == 0
        || !core.handoff_virtual_base.is_multiple_of(ALIGNMENT as u64)
        || core.initial_stack_top_virtual == 0
        || !core.initial_stack_top_virtual.is_multiple_of(16)
        || core.boot_attempt_limit == 0
        || core.boot_attempt_limit > 32
        || core.boot_attempt > core.boot_attempt_limit
        || !(1..=4).contains(&core.boot_slot)
        || core.selected_entry == 0
        || core.uefi_revision == 0
    {
        return Err(Error::PayloadValue);
    }
    let kernel_physical_end = range_end(core.kernel_physical_base, core.kernel_physical_size)?;
    let kernel_virtual_end = range_end(core.kernel_virtual_base, core.kernel_virtual_size)?;
    if kernel_physical_end <= core.kernel_physical_base
        || core.kernel_entry_virtual < core.kernel_virtual_base
        || core.kernel_entry_virtual >= kernel_virtual_end
        || range_end(core.handoff_physical_base, core.handoff_byte_count).is_err()
        || range_end(core.handoff_virtual_base, core.handoff_byte_count).is_err()
    {
        return Err(Error::AddressRange);
    }
    if let Some(size) = total_size
        && core.handoff_byte_count != size as u64
    {
        return Err(Error::PayloadValue);
    }
    if core.boot_flags & SECURE_BOOT_VERIFIED != 0 && core.boot_flags & SECURE_BOOT_ENABLED == 0 {
        return Err(Error::PayloadValue);
    }
    if core.boot_flags & RUNTIME_SERVICES_RETAINED != 0 {
        if core.uefi_system_table_physical == 0 || core.uefi_runtime_services_physical == 0 {
            return Err(Error::PayloadValue);
        }
    } else if core.uefi_system_table_physical != 0 || core.uefi_runtime_services_physical != 0 {
        return Err(Error::PayloadValue);
    }
    Ok(core)
}

fn validate_memory_map(payload: &[u8], count: usize) -> Result<(), Error> {
    if count == 0 || count > 16_384 || payload.len() != count * MEMORY_ENTRY_BYTES {
        return Err(Error::PayloadShape);
    }
    let mut previous_end = 0u64;
    for index in 0..count {
        let base = index * MEMORY_ENTRY_BYTES;
        let start = read_u64(payload, base)?;
        let pages = read_u64(payload, base + 8)?;
        let kind = read_u32(payload, base + 24)?;
        if read_u64(payload, base + 32)? != 0
            || start % PAGE_BYTES != 0
            || pages == 0
            || kind > MEMORY_FRAMEBUFFER
        {
            return Err(Error::PayloadValue);
        }
        let size = pages.checked_mul(PAGE_BYTES).ok_or(Error::AddressRange)?;
        let end = range_end(start, size)?;
        if index != 0 && start < previous_end {
            return Err(Error::PayloadValue);
        }
        previous_end = end;
    }
    Ok(())
}

fn validate_framebuffer(payload: &[u8]) -> Result<(), Error> {
    if payload.len() != FRAMEBUFFER_BYTES {
        return Err(Error::PayloadShape);
    }
    let base = read_u64(payload, 0)?;
    let size = read_u64(payload, 8)?;
    let width = read_u32(payload, 16)? as u64;
    let height = read_u32(payload, 20)? as u64;
    let stride = read_u32(payload, 24)? as u64;
    let format = read_u32(payload, 28)?;
    let red = read_u32(payload, 32)?;
    let green = read_u32(payload, 36)?;
    let blue = read_u32(payload, 40)?;
    let reserved = read_u32(payload, 44)?;
    if base == 0
        || base & 3 != 0
        || !(320..=16_384).contains(&width)
        || !(200..=16_384).contains(&height)
        || stride < width
        || stride > 16_384
        || !(1..=3).contains(&format)
    {
        return Err(Error::PayloadValue);
    }
    let needed = stride
        .checked_mul(height)
        .and_then(|value| value.checked_mul(4))
        .ok_or(Error::AddressRange)?;
    if size < needed || size > 512 * 1024 * 1024 || range_end(base, size).is_err() {
        return Err(Error::AddressRange);
    }
    let masks = [red, green, blue, reserved];
    if format == 1 && masks != [0x0000_00ff, 0x0000_ff00, 0x00ff_0000, 0xff00_0000]
        || format == 2 && masks != [0x00ff_0000, 0x0000_ff00, 0x0000_00ff, 0xff00_0000]
        || format == 3
            && (red == 0
                || green == 0
                || blue == 0
                || red & green != 0
                || red & blue != 0
                || green & blue != 0
                || reserved & (red | green | blue) != 0)
    {
        return Err(Error::PayloadValue);
    }
    Ok(())
}

fn validate_firmware_tables(payload: &[u8], count: usize) -> Result<(), Error> {
    if count == 0 || count > 64 || payload.len() != count * FIRMWARE_TABLE_ENTRY_BYTES {
        return Err(Error::PayloadShape);
    }
    let mut previous_guid: Option<&[u8]> = None;
    for index in 0..count {
        let base = index * FIRMWARE_TABLE_ENTRY_BYTES;
        let guid = &payload[base..base + 16];
        let address = read_u64(payload, base + 16)?;
        let size = read_u64(payload, base + 24)?;
        let flags = read_u32(payload, base + 32)?;
        if all_zero(guid)
            || address == 0
            || address % 8 != 0
            || size == 0
            || size > 16 * 1024 * 1024
            || flags & !0x7 != 0
            || read_u32(payload, base + 36)? != 0
            || range_end(address, size).is_err()
        {
            return Err(Error::PayloadValue);
        }
        if previous_guid.is_some_and(|previous| previous >= guid) {
            return Err(Error::PayloadValue);
        }
        previous_guid = Some(guid);
    }
    Ok(())
}

fn validate_artifacts(payload: &[u8], count: usize) -> Result<(), Error> {
    if count == 0 || count > 64 || payload.len() != count * ARTIFACT_ENTRY_BYTES {
        return Err(Error::PayloadShape);
    }
    let mut previous_role = 0u32;
    for index in 0..count {
        let base = index * ARTIFACT_ENTRY_BYTES;
        let role = read_u32(payload, base)?;
        let flags = read_u32(payload, base + 4)?;
        let physical = read_u64(payload, base + 8)?;
        let size = read_u64(payload, base + 16)?;
        let virtual_start = read_u64(payload, base + 24)?;
        let virtual_size = read_u64(payload, base + 32)?;
        let entry = read_u64(payload, base + 40)?;
        let digest = &payload[base + 48..base + 80];
        if role == 0
            || role > ARTIFACT_CRASH_KERNEL
            || role <= previous_role
            || flags & !KNOWN_ARTIFACT_FLAGS != 0
            || physical == 0
            || physical % PAGE_BYTES != 0
            || size == 0
            || all_zero(digest)
            || range_end(physical, size).is_err()
        {
            return Err(Error::PayloadValue);
        }
        if flags & ARTIFACT_EXECUTABLE != 0 {
            let end = range_end(virtual_start, virtual_size)?;
            if virtual_start == 0
                || virtual_start % PAGE_BYTES != 0
                || entry < virtual_start
                || entry >= end
            {
                return Err(Error::AddressRange);
            }
        } else if entry != 0 || (virtual_start == 0) != (virtual_size == 0) {
            return Err(Error::PayloadValue);
        }
        previous_role = role;
    }
    Ok(())
}

fn validate_command_line(payload: &[u8]) -> Result<(), Error> {
    if payload.is_empty() || payload.len() > 4096 {
        return Err(Error::PayloadShape);
    }
    let text = str::from_utf8(payload).map_err(|_| Error::Utf8)?;
    if text.chars().any(|value| {
        value == '\0' || value == '\r' || value == '\n' || (value.is_control() && value != '\t')
    }) {
        return Err(Error::PayloadValue);
    }
    Ok(())
}

fn validate_boot_device(payload: &[u8]) -> Result<(), Error> {
    if payload.len() != BOOT_DEVICE_BYTES {
        return Err(Error::PayloadShape);
    }
    let start_lba = read_u64(payload, 32)?;
    let size_lba = read_u64(payload, 40)?;
    let block_size = read_u32(payload, 48)?;
    let flags = read_u32(payload, 52)?;
    if all_zero(&payload[0..16])
        || all_zero(&payload[16..32])
        || size_lba == 0
        || start_lba.checked_add(size_lba).is_none()
        || !(512..=65_536).contains(&block_size)
        || !block_size.is_power_of_two()
        || flags & !0x3 != 0
        || all_zero(&payload[56..88])
        || !all_zero(&payload[88..96])
    {
        return Err(Error::PayloadValue);
    }
    Ok(())
}

fn validate_random_seed(payload: &[u8]) -> Result<(), Error> {
    if payload.len() != RANDOM_SEED_BYTES {
        return Err(Error::PayloadShape);
    }
    let quality = read_u32(payload, 0)?;
    let sources = read_u32(payload, 4)?;
    if quality > 3 || sources & !0x0f != 0 || (quality != 0 && all_zero(&payload[8..72])) {
        return Err(Error::PayloadValue);
    }
    Ok(())
}

fn validate_early_log(payload: &[u8]) -> Result<(), Error> {
    if payload.len() < EARLY_LOG_HEADER_BYTES || payload.len() > EARLY_LOG_HEADER_BYTES + 65_536 {
        return Err(Error::PayloadShape);
    }
    if read_u16(payload, 12)? != 1 || read_u16(payload, 14)? != 0 {
        return Err(Error::PayloadValue);
    }
    str::from_utf8(&payload[16..]).map_err(|_| Error::Utf8)?;
    Ok(())
}

fn validate_cpu(payload: &[u8]) -> Result<(), Error> {
    if payload.len() != CPU_BOOTSTRAP_BYTES {
        return Err(Error::PayloadShape);
    }
    let flags = read_u32(payload, 4)?;
    let physical_bits = read_u16(payload, 8)?;
    let virtual_bits = read_u16(payload, 10)?;
    let stack_bottom = read_u64(payload, 16)?;
    let stack_size = read_u64(payload, 24)?;
    let page_levels = read_u32(payload, 32)?;
    let page_size = read_u32(payload, 36)?;
    if flags & !0x3 != 0
        || !(36..=64).contains(&physical_bits)
        || !(48..=64).contains(&virtual_bits)
        || stack_bottom == 0
        || stack_bottom % 16 != 0
        || stack_size < PAGE_BYTES
        || stack_size % PAGE_BYTES != 0
        || range_end(stack_bottom, stack_size).is_err()
        || !matches!(page_levels, 4 | 5)
        || page_size != PAGE_BYTES as u32
        || !all_zero(&payload[40..64])
    {
        return Err(Error::PayloadValue);
    }
    Ok(())
}

fn validate_timestamps(payload: &[u8]) -> Result<(), Error> {
    if payload.len() != BOOT_TIMESTAMPS_BYTES {
        return Err(Error::PayloadShape);
    }
    let flags = read_u64(payload, 0)?;
    let start = read_u64(payload, 16)?;
    let handoff = read_u64(payload, 24)?;
    let frequency = read_u64(payload, 32)?;
    if flags & !0x7 != 0 || start > handoff || ((start != 0 || handoff != 0) && frequency == 0) {
        return Err(Error::PayloadValue);
    }
    Ok(())
}

fn validate_tcg_log(payload: &[u8]) -> Result<(), Error> {
    if payload.len() != TCG_EVENT_LOG_BYTES {
        return Err(Error::PayloadShape);
    }
    let physical = read_u64(payload, 0)?;
    let size = read_u64(payload, 8)?;
    let format = read_u32(payload, 16)?;
    let flags = read_u32(payload, 20)?;
    if physical == 0
        || physical % 8 != 0
        || size == 0
        || size > 16 * 1024 * 1024
        || !matches!(format, 1 | 2)
        || flags & !0x3 != 0
        || all_zero(&payload[24..56])
        || range_end(physical, size).is_err()
    {
        return Err(Error::PayloadValue);
    }
    Ok(())
}

fn validate_payload(
    record_type: u16,
    revision: u16,
    flags: u32,
    element_size: usize,
    element_count: usize,
    payload: &[u8],
    total_size: Option<usize>,
) -> Result<(), Error> {
    if flags & !KNOWN_RECORD_FLAGS != 0 {
        return Err(Error::RecordFlags);
    }
    if record_type <= RECORD_TCG_EVENT_LOG {
        if revision != 1 || flags & (RECORD_ARRAY | RECORD_REDACT) != structural_flags(record_type)
        {
            return Err(Error::RecordFlags);
        }
    } else if record_type < FIRST_EXTENSION_RECORD || revision == 0 || flags & RECORD_REQUIRED != 0
    {
        return Err(Error::UnknownRequiredRecord);
    }
    if flags & RECORD_ARRAY != 0 {
        if element_size == 0
            || element_count == 0
            || element_size.checked_mul(element_count) != Some(payload.len())
        {
            return Err(Error::PayloadShape);
        }
    } else {
        let variable = matches!(record_type, RECORD_COMMAND_LINE | RECORD_EARLY_LOG)
            || record_type >= FIRST_EXTENSION_RECORD;
        if variable {
            if element_size != 0 || element_count != 0 {
                return Err(Error::PayloadShape);
            }
        } else if element_count != 1 || element_size != payload.len() {
            return Err(Error::PayloadShape);
        }
    }
    match record_type {
        RECORD_CORE => validate_core(payload, total_size).map(|_| ()),
        RECORD_MEMORY_MAP => {
            if element_size != MEMORY_ENTRY_BYTES {
                Err(Error::PayloadShape)
            } else {
                validate_memory_map(payload, element_count)
            }
        }
        RECORD_FRAMEBUFFER => validate_framebuffer(payload),
        RECORD_FIRMWARE_TABLES => {
            if element_size != FIRMWARE_TABLE_ENTRY_BYTES {
                Err(Error::PayloadShape)
            } else {
                validate_firmware_tables(payload, element_count)
            }
        }
        RECORD_LOADED_ARTIFACTS => {
            if element_size != ARTIFACT_ENTRY_BYTES {
                Err(Error::PayloadShape)
            } else {
                validate_artifacts(payload, element_count)
            }
        }
        RECORD_COMMAND_LINE => validate_command_line(payload),
        RECORD_BOOT_DEVICE => validate_boot_device(payload),
        RECORD_RANDOM_SEED => validate_random_seed(payload),
        RECORD_EARLY_LOG => validate_early_log(payload),
        RECORD_CPU_BOOTSTRAP => validate_cpu(payload),
        RECORD_BOOT_TIMESTAMPS => validate_timestamps(payload),
        RECORD_TCG_EVENT_LOG => validate_tcg_log(payload),
        _ => Ok(()),
    }
}

pub fn decode(bytes: &[u8]) -> Result<Handoff<'_>, Error> {
    if bytes.len() < HEADER_BYTES {
        return Err(Error::BufferTooSmall);
    }
    if bytes.len() > MAX_TOTAL_BYTES || &bytes[0..8] != MAGIC.as_slice() {
        return Err(if bytes.len() > MAX_TOTAL_BYTES {
            Error::TotalSize
        } else {
            Error::Magic
        });
    }
    let writer_major = read_u16(bytes, 8)?;
    let writer_minor = read_u16(bytes, 10)?;
    let minimum_reader_minor = read_u16(bytes, 12)?;
    if writer_major != MAJOR {
        return Err(Error::MajorVersion);
    }
    if minimum_reader_minor > writer_minor || minimum_reader_minor > MINOR {
        return Err(Error::MinorVersion);
    }
    if read_u16(bytes, 14)? as usize != HEADER_BYTES {
        return Err(Error::HeaderLayout);
    }
    let total_size = read_u32(bytes, 16)? as usize;
    let record_count = read_u16(bytes, 20)? as usize;
    let descriptor_size = read_u16(bytes, 22)? as usize;
    let table_offset = read_u32(bytes, 24)? as usize;
    let payload_offset = read_u32(bytes, 28)? as usize;
    let features = read_u64(bytes, 32)?;
    let required_features = read_u64(bytes, 40)?;
    if total_size != bytes.len() || total_size > MAX_TOTAL_BYTES {
        return Err(Error::TotalSize);
    }
    if !(2..=MAX_RECORDS).contains(&record_count) {
        return Err(Error::RecordCount);
    }
    let expected_payload = align_up(
        HEADER_BYTES
            .checked_add(
                record_count
                    .checked_mul(DESCRIPTOR_BYTES)
                    .ok_or(Error::ArithmeticOverflow)?,
            )
            .ok_or(Error::ArithmeticOverflow)?,
        ALIGNMENT,
    )?;
    if descriptor_size != DESCRIPTOR_BYTES
        || table_offset != HEADER_BYTES
        || payload_offset != expected_payload
        || read_u32(bytes, 52)? != 0
    {
        return Err(Error::HeaderLayout);
    }
    if read_u64(bytes, 56)? != 0 {
        return Err(Error::Reserved);
    }
    if message_crc32(bytes) != read_u32(bytes, 48)? {
        return Err(Error::Checksum);
    }
    if required_features & !features != 0 || required_features & !KNOWN_FEATURES != 0 {
        return Err(Error::UnknownFeature);
    }
    if writer_minor == MINOR && features & !KNOWN_FEATURES != 0 {
        return Err(Error::UnknownFeature);
    }

    let mut expected_offset = payload_offset;
    let mut previous_type = 0u16;
    let mut observed_features = 0u64;
    let mut observed_required = 0u64;
    for index in 0..record_count {
        let item = descriptor(bytes, index)?;
        let descriptor_base = HEADER_BYTES + index * DESCRIPTOR_BYTES;
        if read_u64(bytes, descriptor_base + 24)? != 0 {
            return Err(Error::Reserved);
        }
        if item.record_type <= previous_type {
            return Err(Error::RecordOrder);
        }
        if item.offset != expected_offset || item.offset % ALIGNMENT != 0 || item.length == 0 {
            return Err(Error::RecordLayout);
        }
        let end = item
            .offset
            .checked_add(item.length)
            .ok_or(Error::ArithmeticOverflow)?;
        let payload = bytes.get(item.offset..end).ok_or(Error::RecordLayout)?;
        if crc32(payload) != item.content_crc32 {
            return Err(Error::RecordChecksum);
        }
        validate_payload(
            item.record_type,
            item.revision,
            item.flags,
            item.element_size,
            item.element_count,
            payload,
            Some(total_size),
        )?;
        let aligned_end = align_up(end, ALIGNMENT)?;
        if aligned_end > total_size || !all_zero(&bytes[end..aligned_end]) {
            return Err(Error::RecordLayout);
        }
        expected_offset = aligned_end;
        previous_type = item.record_type;
        let feature = feature_for(item.record_type);
        observed_features |= feature;
        if item.flags & RECORD_REQUIRED != 0 {
            observed_required |= feature;
        }
        if item.record_type >= FIRST_EXTENSION_RECORD && writer_minor == MINOR {
            return Err(Error::MinorVersion);
        }
    }
    if expected_offset != total_size {
        return Err(Error::RecordLayout);
    }
    if observed_features != features & KNOWN_FEATURES || observed_required != required_features {
        return Err(Error::FeatureMismatch);
    }
    if features & BASE_REQUIRED_FEATURES != BASE_REQUIRED_FEATURES
        || required_features & BASE_REQUIRED_FEATURES != BASE_REQUIRED_FEATURES
    {
        return Err(Error::MissingBaseRecord);
    }
    let handoff = Handoff {
        bytes,
        header: Header {
            writer_major,
            writer_minor,
            minimum_reader_minor,
            total_size,
            record_count,
            features,
            required_features,
        },
    };
    validate_cross_records(&handoff)?;
    Ok(handoff)
}

fn validate_cross_records(handoff: &Handoff<'_>) -> Result<(), Error> {
    let core = handoff.core()?;
    if core.boot_flags & MEASURED_BOOT_ACTIVE != 0
        && handoff.header.features & FEATURE_TCG_EVENT_LOG == 0
    {
        return Err(Error::FeatureMismatch);
    }
    if let Some(artifacts) = handoff.record(RECORD_LOADED_ARTIFACTS) {
        let mut kernel_found = false;
        for index in 0..artifacts.descriptor.element_count {
            let base = index * ARTIFACT_ENTRY_BYTES;
            if read_u32(artifacts.payload, base)? == ARTIFACT_KERNEL {
                kernel_found = true;
                if read_u64(artifacts.payload, base + 8)? != core.kernel_physical_base
                    || read_u64(artifacts.payload, base + 16)? != core.kernel_physical_size
                    || read_u64(artifacts.payload, base + 24)? != core.kernel_virtual_base
                    || read_u64(artifacts.payload, base + 32)? != core.kernel_virtual_size
                    || read_u64(artifacts.payload, base + 40)? != core.kernel_entry_virtual
                {
                    return Err(Error::FeatureMismatch);
                }
            }
        }
        if !kernel_found {
            return Err(Error::FeatureMismatch);
        }
    }
    Ok(())
}

impl<'a> Handoff<'a> {
    pub fn header(&self) -> Header {
        self.header
    }

    pub fn records(&self) -> Records<'a> {
        Records {
            bytes: self.bytes,
            index: 0,
            count: self.header.record_count,
        }
    }

    pub fn record(&self, record_type: u16) -> Option<Record<'a>> {
        self.records()
            .find(|item| item.descriptor.record_type == record_type)
    }

    pub fn core(&self) -> Result<CoreRecord, Error> {
        let record = self.record(RECORD_CORE).ok_or(Error::MissingBaseRecord)?;
        validate_core(record.payload, Some(self.header.total_size))
    }
}

impl<'a> Iterator for Records<'a> {
    type Item = Record<'a>;

    fn next(&mut self) -> Option<Self::Item> {
        if self.index >= self.count {
            return None;
        }
        let item = descriptor(self.bytes, self.index).ok()?;
        let payload = self.bytes.get(item.offset..item.offset + item.length)?;
        self.index += 1;
        Some(Record {
            descriptor: item,
            payload,
        })
    }
}

pub fn validate_kernel_entry_profile(handoff: &Handoff<'_>) -> Result<(), Error> {
    if handoff.header.features & KERNEL_ENTRY_REQUIRED_FEATURES != KERNEL_ENTRY_REQUIRED_FEATURES
        || handoff.header.required_features & KERNEL_ENTRY_REQUIRED_FEATURES
            != KERNEL_ENTRY_REQUIRED_FEATURES
    {
        return Err(Error::KernelProfile);
    }
    let core = handoff.core()?;
    if core.boot_flags & BOOT_SERVICES_EXITED == 0 {
        return Err(Error::KernelProfile);
    }
    let random = handoff
        .record(RECORD_RANDOM_SEED)
        .ok_or(Error::KernelProfile)?;
    if read_u32(random.payload, 0)? < 2 {
        return Err(Error::KernelProfile);
    }
    let artifacts = handoff
        .record(RECORD_LOADED_ARTIFACTS)
        .ok_or(Error::KernelProfile)?;
    let mut required_roles = 0u32;
    for index in 0..artifacts.descriptor.element_count {
        let base = index * ARTIFACT_ENTRY_BYTES;
        let role = read_u32(artifacts.payload, base)?;
        let flags = read_u32(artifacts.payload, base + 4)?;
        if matches!(role, ARTIFACT_KERNEL | ARTIFACT_INITIAL_SYSTEM) {
            required_roles |= 1 << (role - 1);
            if flags & (ARTIFACT_HASH_VERIFIED | ARTIFACT_SIGNATURE_VERIFIED)
                != ARTIFACT_HASH_VERIFIED | ARTIFACT_SIGNATURE_VERIFIED
            {
                return Err(Error::KernelProfile);
            }
        }
    }
    if required_roles != 0b11 {
        return Err(Error::KernelProfile);
    }
    Ok(())
}

pub fn encoded_size(record_count: usize, payload_lengths: &[usize]) -> Result<usize, Error> {
    if !(2..=MAX_RECORDS).contains(&record_count) || payload_lengths.len() != record_count {
        return Err(Error::RecordCount);
    }
    let mut size = align_up(
        HEADER_BYTES
            .checked_add(
                record_count
                    .checked_mul(DESCRIPTOR_BYTES)
                    .ok_or(Error::ArithmeticOverflow)?,
            )
            .ok_or(Error::ArithmeticOverflow)?,
        ALIGNMENT,
    )?;
    for length in payload_lengths {
        if *length == 0 {
            return Err(Error::PayloadShape);
        }
        size = align_up(
            size.checked_add(*length).ok_or(Error::ArithmeticOverflow)?,
            ALIGNMENT,
        )?;
    }
    if size > MAX_TOTAL_BYTES {
        return Err(Error::TotalSize);
    }
    Ok(size)
}

pub struct Encoder<'a> {
    output: &'a mut [u8],
    record_count: usize,
    index: usize,
    cursor: usize,
    previous_type: u16,
    writer_minor: u16,
    features: u64,
    required_features: u64,
}

impl<'a> Encoder<'a> {
    pub fn new(
        output: &'a mut [u8],
        record_count: usize,
        writer_minor: u16,
        minimum_reader_minor: u16,
    ) -> Result<Self, Error> {
        if !(2..=MAX_RECORDS).contains(&record_count) {
            return Err(Error::RecordCount);
        }
        if minimum_reader_minor > writer_minor || minimum_reader_minor > MINOR {
            return Err(Error::MinorVersion);
        }
        let cursor = align_up(
            HEADER_BYTES
                .checked_add(
                    record_count
                        .checked_mul(DESCRIPTOR_BYTES)
                        .ok_or(Error::ArithmeticOverflow)?,
                )
                .ok_or(Error::ArithmeticOverflow)?,
            ALIGNMENT,
        )?;
        if output.len() < cursor || output.len() > MAX_TOTAL_BYTES {
            return Err(Error::BufferTooSmall);
        }
        output.fill(0);
        output[0..8].copy_from_slice(&MAGIC);
        write_u16(output, 8, MAJOR)?;
        write_u16(output, 10, writer_minor)?;
        write_u16(output, 12, minimum_reader_minor)?;
        write_u16(output, 14, HEADER_BYTES as u16)?;
        write_u16(output, 20, record_count as u16)?;
        write_u16(output, 22, DESCRIPTOR_BYTES as u16)?;
        write_u32(output, 24, HEADER_BYTES as u32)?;
        write_u32(output, 28, cursor as u32)?;
        Ok(Self {
            output,
            record_count,
            index: 0,
            cursor,
            previous_type: 0,
            writer_minor,
            features: 0,
            required_features: 0,
        })
    }

    pub fn push(
        &mut self,
        record_type: u16,
        revision: u16,
        flags: u32,
        element_size: usize,
        element_count: usize,
        payload: &[u8],
    ) -> Result<(), Error> {
        if self.index >= self.record_count || record_type <= self.previous_type {
            return Err(Error::RecordOrder);
        }
        if record_type >= FIRST_EXTENSION_RECORD && self.writer_minor == MINOR {
            return Err(Error::MinorVersion);
        }
        validate_payload(
            record_type,
            revision,
            flags,
            element_size,
            element_count,
            payload,
            None,
        )?;
        let end = self
            .cursor
            .checked_add(payload.len())
            .ok_or(Error::ArithmeticOverflow)?;
        let aligned_end = align_up(end, ALIGNMENT)?;
        if aligned_end > self.output.len() {
            return Err(Error::BufferTooSmall);
        }
        self.output[self.cursor..end].copy_from_slice(payload);
        self.output[end..aligned_end].fill(0);
        let base = HEADER_BYTES + self.index * DESCRIPTOR_BYTES;
        write_u16(self.output, base, record_type)?;
        write_u16(self.output, base + 2, revision)?;
        write_u32(self.output, base + 4, flags)?;
        write_u32(self.output, base + 8, self.cursor as u32)?;
        write_u32(self.output, base + 12, payload.len() as u32)?;
        write_u16(self.output, base + 16, element_size as u16)?;
        write_u16(self.output, base + 18, element_count as u16)?;
        write_u32(self.output, base + 20, crc32(payload))?;
        self.features |= feature_for(record_type);
        if flags & RECORD_REQUIRED != 0 {
            self.required_features |= feature_for(record_type);
        }
        self.previous_type = record_type;
        self.cursor = aligned_end;
        self.index += 1;
        Ok(())
    }

    pub fn finish(self) -> Result<&'a [u8], Error> {
        if self.index != self.record_count
            || self.features & BASE_REQUIRED_FEATURES != BASE_REQUIRED_FEATURES
            || self.required_features & BASE_REQUIRED_FEATURES != BASE_REQUIRED_FEATURES
        {
            return Err(Error::MissingBaseRecord);
        }
        let total = self.cursor;
        let output = self.output;
        write_u32(output, 16, total as u32)?;
        write_u64(output, 32, self.features)?;
        write_u64(output, 40, self.required_features)?;
        write_u32(output, 48, 0)?;
        write_u32(output, 48, message_crc32(&output[..total]))?;
        let result = &output[..total];
        decode(result)?;
        Ok(result)
    }
}

#[cfg(test)]
mod tests {
    extern crate std;

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

    fn core(total: usize, flags: u64) -> Vec<u8> {
        let mut value = vec![0u8; CORE_BYTES];
        put_u64(&mut value, 0, flags);
        put_u64(&mut value, 8, 0x0020_0000);
        put_u64(&mut value, 16, 0x0010_0000);
        put_u64(&mut value, 24, 0xffff_ffff_8000_0000);
        put_u64(&mut value, 32, 0x0010_0000);
        put_u64(&mut value, 40, 0xffff_ffff_8000_1000);
        put_u64(&mut value, 48, 0xffff_ffff_8020_0000);
        put_u64(&mut value, 56, 0x003f_0000);
        put_u64(&mut value, 64, 0x0038_0000);
        put_u64(&mut value, 72, 0xffff_8000_0038_0000);
        put_u64(&mut value, 80, total as u64);
        put_u32(&mut value, 104, 1);
        put_u32(&mut value, 108, 3);
        put_u32(&mut value, 112, 1);
        put_u32(&mut value, 116, 1);
        put_u32(&mut value, 120, 0x0002_0064);
        value
    }

    fn memory_map() -> Vec<u8> {
        let entries = [
            (0x000f_0000u64, 16u64, MEMORY_ACPI_RECLAIMABLE, 9u32),
            (0x0010_0000, 256, MEMORY_USABLE, 7),
            (0x0020_0000, 512, MEMORY_LOADER_RESERVED, 2),
            (0x0040_0000, 4096, MEMORY_USABLE, 7),
            (0x8000_0000, 1000, MEMORY_FRAMEBUFFER, 11),
        ];
        let mut value = vec![0u8; entries.len() * MEMORY_ENTRY_BYTES];
        for (index, (start, pages, kind, source)) in entries.iter().enumerate() {
            let base = index * MEMORY_ENTRY_BYTES;
            put_u64(&mut value, base, *start);
            put_u64(&mut value, base + 8, *pages);
            put_u64(&mut value, base + 16, 0);
            put_u32(&mut value, base + 24, *kind);
            put_u32(&mut value, base + 28, *source);
        }
        value
    }

    fn minimal() -> Vec<u8> {
        let memory = memory_map();
        let total = encoded_size(2, &[CORE_BYTES, memory.len()]).unwrap();
        let core = core(total, BOOT_SERVICES_EXITED);
        let mut output = vec![0u8; total];
        let mut encoder = Encoder::new(&mut output, 2, 0, 0).unwrap();
        encoder
            .push(RECORD_CORE, 1, RECORD_REQUIRED, CORE_BYTES, 1, &core)
            .unwrap();
        encoder
            .push(
                RECORD_MEMORY_MAP,
                1,
                RECORD_REQUIRED | RECORD_ARRAY,
                MEMORY_ENTRY_BYTES,
                memory.len() / MEMORY_ENTRY_BYTES,
                &memory,
            )
            .unwrap();
        encoder.finish().unwrap().to_vec()
    }

    #[test]
    fn layout_constants_are_exact() {
        assert_eq!(HEADER_BYTES, 64);
        assert_eq!(DESCRIPTOR_BYTES, 32);
        assert_eq!(CORE_BYTES, 128);
        assert_eq!(MEMORY_ENTRY_BYTES, 40);
        assert_eq!(FRAMEBUFFER_BYTES, 48);
        assert_eq!(FIRMWARE_TABLE_ENTRY_BYTES, 40);
        assert_eq!(ARTIFACT_ENTRY_BYTES, 80);
        assert_eq!(BOOT_DEVICE_BYTES, 96);
        assert_eq!(RANDOM_SEED_BYTES, 72);
        assert_eq!(CPU_BOOTSTRAP_BYTES, 64);
        assert_eq!(BOOT_TIMESTAMPS_BYTES, 48);
        assert_eq!(TCG_EVENT_LOG_BYTES, 56);
    }

    #[test]
    fn standard_crc_vector_matches() {
        assert_eq!(crc32(b"123456789"), 0xcbf4_3926);
    }

    #[test]
    fn minimal_round_trip_is_canonical_but_not_kernel_ready() {
        let bytes = minimal();
        let decoded = decode(&bytes).unwrap();
        assert_eq!(decoded.header().record_count, 2);
        assert_eq!(decoded.records().count(), 2);
        assert_eq!(
            validate_kernel_entry_profile(&decoded),
            Err(Error::KernelProfile)
        );
    }

    #[test]
    fn checksum_and_truncation_fail_closed() {
        let bytes = minimal();
        for length in [0, 7, 63, bytes.len() - 1] {
            assert!(decode(&bytes[..length]).is_err());
        }
        let mut changed = bytes.clone();
        let last = changed.len() - 1;
        changed[last] ^= 1;
        assert!(matches!(decode(&changed), Err(Error::Checksum)));
    }

    #[test]
    fn major_and_required_minor_downgrades_are_rejected() {
        let bytes = minimal();
        let mut major = bytes.clone();
        put_u16(&mut major, 8, 0);
        put_u32(&mut major, 48, 0);
        let crc = message_crc32(&major);
        put_u32(&mut major, 48, crc);
        assert!(matches!(decode(&major), Err(Error::MajorVersion)));

        let mut minor = bytes.clone();
        put_u16(&mut minor, 10, 1);
        put_u16(&mut minor, 12, 1);
        put_u32(&mut minor, 48, 0);
        let crc = message_crc32(&minor);
        put_u32(&mut minor, 48, crc);
        assert!(matches!(decode(&minor), Err(Error::MinorVersion)));
    }

    #[test]
    fn unknown_record_requires_a_new_optional_minor() {
        let memory = memory_map();
        let extension = b"future";
        let total = encoded_size(3, &[CORE_BYTES, memory.len(), extension.len()]).unwrap();
        let core = core(total, BOOT_SERVICES_EXITED);
        let mut output = vec![0u8; total];
        let mut encoder = Encoder::new(&mut output, 3, 1, 0).unwrap();
        encoder
            .push(RECORD_CORE, 1, RECORD_REQUIRED, CORE_BYTES, 1, &core)
            .unwrap();
        encoder
            .push(
                RECORD_MEMORY_MAP,
                1,
                RECORD_REQUIRED | RECORD_ARRAY,
                MEMORY_ENTRY_BYTES,
                memory.len() / MEMORY_ENTRY_BYTES,
                &memory,
            )
            .unwrap();
        encoder
            .push(FIRST_EXTENSION_RECORD, 1, 0, 0, 0, extension)
            .unwrap();
        assert_eq!(encoder.finish().unwrap().len(), total);
    }

    #[test]
    fn malformed_map_overlap_is_rejected_after_crc_repair() {
        let bytes = minimal();
        let decoded = decode(&bytes).unwrap();
        let map = decoded.record(RECORD_MEMORY_MAP).unwrap();
        let mut changed = bytes.clone();
        put_u64(
            &mut changed,
            map.descriptor.offset + MEMORY_ENTRY_BYTES,
            0x000f_8000,
        );
        let payload =
            &changed[map.descriptor.offset..map.descriptor.offset + map.descriptor.length];
        let descriptor_base = HEADER_BYTES + DESCRIPTOR_BYTES;
        let payload_crc = crc32(payload);
        put_u32(&mut changed, descriptor_base + 20, payload_crc);
        put_u32(&mut changed, 48, 0);
        let crc = message_crc32(&changed);
        put_u32(&mut changed, 48, crc);
        assert!(matches!(decode(&changed), Err(Error::PayloadValue)));
    }

    #[test]
    fn every_single_bit_mutation_is_rejected_or_remains_structurally_valid() {
        let bytes = minimal();
        for index in 0..bytes.len() {
            for bit in 0..8 {
                let mut changed = bytes.clone();
                changed[index] ^= 1 << bit;
                let _ = decode(&changed);
            }
        }
    }
}
