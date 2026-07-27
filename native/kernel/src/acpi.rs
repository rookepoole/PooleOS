use poole_handoff::{
    FIRMWARE_TABLE_ENTRY_BYTES, Handoff, MEMORY_ACPI_NVS, MEMORY_ACPI_RECLAIMABLE,
    MEMORY_ENTRY_BYTES, PAGE_BYTES, RECORD_FIRMWARE_TABLES, RECORD_MEMORY_MAP,
};

use crate::physical_memory::{
    AllocationHandle, PageAccessError, PhysicalMemoryError, PhysicalMemoryManager,
    PhysicalPageAccess, Zone, acpi_release_evidence,
};

pub const CONTRACT_ID: &str = "PKACPI1";
pub const SNAPSHOT_OWNER: u16 = 0x4143;
pub const REQUIRED_TABLE_COUNT: usize = 4;
pub const REQUIRED_TABLE_MASK: u8 = 0x0f;
pub const REQUIRED_SIGNATURES: [[u8; 4]; REQUIRED_TABLE_COUNT] =
    [*b"APIC", *b"FACP", *b"HPET", *b"MCFG"];
pub const ACPI_20_TABLE_GUID: [u8; 16] = [
    0x88, 0x68, 0xe8, 0x71, 0xe4, 0xf1, 0x11, 0xd3, 0xbc, 0x22, 0x00, 0x80, 0xc7, 0x3c, 0x88, 0x81,
];
pub const FIRMWARE_TABLE_PHYSICAL: u32 = 1 << 1;
pub const FIRMWARE_TABLE_CHECKSUM_VALIDATED: u32 = 1 << 2;
pub const MAX_XSDT_ENTRIES: usize = 64;
pub const MAX_TABLE_BYTES: u64 = 64 * 1024;
pub const MAX_SNAPSHOT_PAGES: u64 = 64;
const RSDP_BYTES: u64 = 36;
const TABLE_HEADER_BYTES: u64 = 36;
const FNV_OFFSET: u64 = 0xcbf2_9ce4_8422_2325;
const FNV_PRIME: u64 = 0x0000_0100_0000_01b3;

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum AcpiError {
    MissingFirmwareRecord,
    FirmwareRecordShape,
    FirmwareGuid,
    FirmwareFlags,
    SourceRange,
    PhysicalAccess,
    RsdpSignature,
    RsdpRevision,
    RsdpLength,
    RsdpChecksum,
    XsdtAddress,
    XsdtShape,
    TableAddress,
    TableLength,
    TableChecksum,
    DuplicateRequiredTable,
    MissingRequiredTable,
    SnapshotCapacity,
    SnapshotAllocation,
    SnapshotCopy,
    SnapshotReadback,
    SnapshotRollback,
    ReleaseEvidence,
}

impl AcpiError {
    pub const fn label(self) -> &'static str {
        match self {
            Self::MissingFirmwareRecord => "acpi_missing_firmware_record",
            Self::FirmwareRecordShape => "acpi_firmware_record_shape",
            Self::FirmwareGuid => "acpi_firmware_guid",
            Self::FirmwareFlags => "acpi_firmware_flags",
            Self::SourceRange => "acpi_source_range",
            Self::PhysicalAccess => "acpi_physical_access",
            Self::RsdpSignature => "acpi_rsdp_signature",
            Self::RsdpRevision => "acpi_rsdp_revision",
            Self::RsdpLength => "acpi_rsdp_length",
            Self::RsdpChecksum => "acpi_rsdp_checksum",
            Self::XsdtAddress => "acpi_xsdt_address",
            Self::XsdtShape => "acpi_xsdt_shape",
            Self::TableAddress => "acpi_table_address",
            Self::TableLength => "acpi_table_length",
            Self::TableChecksum => "acpi_table_checksum",
            Self::DuplicateRequiredTable => "acpi_duplicate_required_table",
            Self::MissingRequiredTable => "acpi_missing_required_table",
            Self::SnapshotCapacity => "acpi_snapshot_capacity",
            Self::SnapshotAllocation => "acpi_snapshot_allocation",
            Self::SnapshotCopy => "acpi_snapshot_copy",
            Self::SnapshotReadback => "acpi_snapshot_readback",
            Self::SnapshotRollback => "acpi_snapshot_rollback",
            Self::ReleaseEvidence => "acpi_release_evidence",
        }
    }
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct RequiredTableReceipt {
    pub signature: [u8; 4],
    pub source_address: u64,
    pub byte_count: u64,
    pub snapshot_offset: u64,
    pub revision: u8,
    pub content_checksum: u64,
}

const EMPTY_TABLE_RECEIPT: RequiredTableReceipt = RequiredTableReceipt {
    signature: [0; 4],
    source_address: 0,
    byte_count: 0,
    snapshot_offset: 0,
    revision: 0,
    content_checksum: 0,
};

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct AcpiSnapshotReceipt {
    pub rsdp_source_address: u64,
    pub xsdt_source_address: u64,
    pub xsdt_entry_count: u64,
    pub required_table_mask: u8,
    pub required_tables: [RequiredTableReceipt; REQUIRED_TABLE_COUNT],
    pub allocation: AllocationHandle,
    pub snapshot_physical_address: u64,
    pub snapshot_page_count: u64,
    pub snapshot_byte_count: u64,
    pub copied_byte_count: u64,
    pub source_checksum: u64,
    pub snapshot_checksum: u64,
    pub copy_verified: bool,
    pub lifecycle_released: bool,
}

#[derive(Clone, Copy)]
struct TableHeader {
    signature: [u8; 4],
    length: u64,
    revision: u8,
}

fn read_u32(bytes: &[u8], offset: usize) -> Result<u32, AcpiError> {
    let value = bytes
        .get(offset..offset + 4)
        .ok_or(AcpiError::FirmwareRecordShape)?;
    Ok(u32::from_le_bytes([value[0], value[1], value[2], value[3]]))
}

fn read_u64(bytes: &[u8], offset: usize) -> Result<u64, AcpiError> {
    let value = bytes
        .get(offset..offset + 8)
        .ok_or(AcpiError::FirmwareRecordShape)?;
    Ok(u64::from_le_bytes([
        value[0], value[1], value[2], value[3], value[4], value[5], value[6], value[7],
    ]))
}

fn physical_byte<A: PhysicalPageAccess>(access: &mut A, address: u64) -> Result<u8, AcpiError> {
    let page = address / PAGE_BYTES * PAGE_BYTES;
    let page_offset = address.checked_sub(page).ok_or(AcpiError::PhysicalAccess)?;
    let word_index = usize::try_from(page_offset / 8).map_err(|_| AcpiError::PhysicalAccess)?;
    let shift = u32::try_from((page_offset % 8) * 8).map_err(|_| AcpiError::PhysicalAccess)?;
    let word = access
        .read_word(page, word_index)
        .map_err(|_| AcpiError::PhysicalAccess)?;
    Ok((word >> shift) as u8)
}

fn physical_u32<A: PhysicalPageAccess>(access: &mut A, address: u64) -> Result<u32, AcpiError> {
    let mut value = [0u8; 4];
    for (index, byte) in value.iter_mut().enumerate() {
        *byte = physical_byte(
            access,
            address
                .checked_add(index as u64)
                .ok_or(AcpiError::PhysicalAccess)?,
        )?;
    }
    Ok(u32::from_le_bytes(value))
}

fn physical_u64<A: PhysicalPageAccess>(access: &mut A, address: u64) -> Result<u64, AcpiError> {
    let mut value = [0u8; 8];
    for (index, byte) in value.iter_mut().enumerate() {
        *byte = physical_byte(
            access,
            address
                .checked_add(index as u64)
                .ok_or(AcpiError::PhysicalAccess)?,
        )?;
    }
    Ok(u64::from_le_bytes(value))
}

fn physical_signature<A: PhysicalPageAccess>(
    access: &mut A,
    address: u64,
    width: usize,
) -> Result<[u8; 8], AcpiError> {
    let mut value = [0u8; 8];
    for (index, byte) in value.iter_mut().take(width).enumerate() {
        *byte = physical_byte(
            access,
            address
                .checked_add(index as u64)
                .ok_or(AcpiError::PhysicalAccess)?,
        )?;
    }
    Ok(value)
}

fn checksum_is_zero<A: PhysicalPageAccess>(
    access: &mut A,
    address: u64,
    byte_count: u64,
) -> Result<bool, AcpiError> {
    let mut sum = 0u8;
    for offset in 0..byte_count {
        sum = sum.wrapping_add(physical_byte(
            access,
            address
                .checked_add(offset)
                .ok_or(AcpiError::PhysicalAccess)?,
        )?);
    }
    Ok(sum == 0)
}

fn fnv_byte(value: u64, byte: u8) -> u64 {
    (value ^ u64::from(byte)).wrapping_mul(FNV_PRIME)
}

fn fnv_range<A: PhysicalPageAccess>(
    access: &mut A,
    address: u64,
    byte_count: u64,
) -> Result<u64, AcpiError> {
    let mut value = FNV_OFFSET;
    for offset in 0..byte_count {
        value = fnv_byte(
            value,
            physical_byte(
                access,
                address
                    .checked_add(offset)
                    .ok_or(AcpiError::PhysicalAccess)?,
            )?,
        );
    }
    Ok(value)
}

fn memory_covers_acpi_range(
    handoff: &Handoff<'_>,
    address: u64,
    byte_count: u64,
) -> Result<bool, AcpiError> {
    let end = address
        .checked_add(byte_count)
        .ok_or(AcpiError::SourceRange)?;
    if byte_count == 0 {
        return Ok(false);
    }
    let record = handoff
        .record(RECORD_MEMORY_MAP)
        .ok_or(AcpiError::SourceRange)?;
    let mut cursor = address;
    for index in 0..record.descriptor.element_count {
        let base = index * MEMORY_ENTRY_BYTES;
        let start = read_u64(record.payload, base)?;
        let pages = read_u64(record.payload, base + 8)?;
        let kind = read_u32(record.payload, base + 24)?;
        let entry_end = start
            .checked_add(
                pages
                    .checked_mul(PAGE_BYTES)
                    .ok_or(AcpiError::SourceRange)?,
            )
            .ok_or(AcpiError::SourceRange)?;
        if entry_end <= cursor {
            continue;
        }
        if start > cursor || !matches!(kind, MEMORY_ACPI_RECLAIMABLE | MEMORY_ACPI_NVS) {
            break;
        }
        cursor = end.min(entry_end);
        if cursor == end {
            return Ok(true);
        }
    }
    Ok(false)
}

fn require_source_range(
    handoff: &Handoff<'_>,
    address: u64,
    byte_count: u64,
) -> Result<(), AcpiError> {
    if !address.is_multiple_of(4) || !memory_covers_acpi_range(handoff, address, byte_count)? {
        return Err(AcpiError::SourceRange);
    }
    Ok(())
}

fn table_header<A: PhysicalPageAccess>(
    handoff: &Handoff<'_>,
    access: &mut A,
    address: u64,
) -> Result<TableHeader, AcpiError> {
    if address == 0 || !address.is_multiple_of(4) {
        return Err(AcpiError::TableAddress);
    }
    require_source_range(handoff, address, TABLE_HEADER_BYTES)?;
    let signature8 = physical_signature(access, address, 4)?;
    let signature = [signature8[0], signature8[1], signature8[2], signature8[3]];
    let length = u64::from(physical_u32(access, address + 4)?);
    if !(TABLE_HEADER_BYTES..=MAX_TABLE_BYTES).contains(&length) {
        return Err(AcpiError::TableLength);
    }
    require_source_range(handoff, address, length)?;
    if !checksum_is_zero(access, address, length)? {
        return Err(AcpiError::TableChecksum);
    }
    Ok(TableHeader {
        signature,
        length,
        revision: physical_byte(access, address + 8)?,
    })
}

fn minimum_length(signature: [u8; 4]) -> u64 {
    match &signature {
        b"APIC" => 44,
        b"FACP" => 116,
        b"HPET" => 56,
        b"MCFG" => 44,
        _ => TABLE_HEADER_BYTES,
    }
}

fn required_index(signature: [u8; 4]) -> Option<usize> {
    REQUIRED_SIGNATURES
        .iter()
        .position(|candidate| *candidate == signature)
}

fn align8(value: u64) -> Result<u64, AcpiError> {
    value
        .checked_add(7)
        .map(|item| item & !7)
        .ok_or(AcpiError::SnapshotCapacity)
}

fn copy_range<A: PhysicalPageAccess>(
    access: &mut A,
    source: u64,
    destination: u64,
    byte_count: u64,
) -> Result<(), AcpiError> {
    let word_count = byte_count.div_ceil(8);
    for word_index in 0..word_count {
        let offset = word_index * 8;
        let mut bytes = [0u8; 8];
        let take = (byte_count - offset).min(8);
        for index in 0..take {
            bytes[index as usize] = physical_byte(
                access,
                source
                    .checked_add(offset + index)
                    .ok_or(AcpiError::SnapshotCopy)?,
            )?;
        }
        let destination_address = destination
            .checked_add(offset)
            .ok_or(AcpiError::SnapshotCopy)?;
        let page = destination_address / PAGE_BYTES * PAGE_BYTES;
        let page_offset = destination_address - page;
        let destination_word =
            usize::try_from(page_offset / 8).map_err(|_| AcpiError::SnapshotCopy)?;
        access
            .write_word(page, destination_word, u64::from_le_bytes(bytes))
            .map_err(|_| AcpiError::SnapshotCopy)?;
        let observed = access
            .read_word(page, destination_word)
            .map_err(|_| AcpiError::SnapshotReadback)?;
        if observed != u64::from_le_bytes(bytes) {
            return Err(AcpiError::SnapshotReadback);
        }
    }
    Ok(())
}

fn rollback_snapshot<A: PhysicalPageAccess>(
    manager: &mut PhysicalMemoryManager,
    access: &mut A,
    allocation: AllocationHandle,
    error: AcpiError,
) -> Result<AcpiSnapshotReceipt, AcpiError> {
    manager
        .free_scrubbed(allocation, access)
        .map_err(|_| AcpiError::SnapshotRollback)?;
    Err(error)
}

pub fn consume_required_tables<A: PhysicalPageAccess>(
    handoff: &Handoff<'_>,
    manager: &mut PhysicalMemoryManager,
    access: &mut A,
) -> Result<AcpiSnapshotReceipt, AcpiError> {
    let firmware = handoff
        .record(RECORD_FIRMWARE_TABLES)
        .ok_or(AcpiError::MissingFirmwareRecord)?;
    if firmware.descriptor.element_count != 1
        || firmware.descriptor.element_size != FIRMWARE_TABLE_ENTRY_BYTES
        || firmware.payload.len() != FIRMWARE_TABLE_ENTRY_BYTES
    {
        return Err(AcpiError::FirmwareRecordShape);
    }
    if firmware.payload[..16] != ACPI_20_TABLE_GUID {
        return Err(AcpiError::FirmwareGuid);
    }
    let rsdp_address = read_u64(firmware.payload, 16)?;
    let rsdp_length = read_u64(firmware.payload, 24)?;
    let firmware_flags = read_u32(firmware.payload, 32)?;
    if rsdp_length != RSDP_BYTES
        || firmware_flags != FIRMWARE_TABLE_PHYSICAL | FIRMWARE_TABLE_CHECKSUM_VALIDATED
    {
        return Err(AcpiError::FirmwareFlags);
    }
    require_source_range(handoff, rsdp_address, RSDP_BYTES)?;
    if &physical_signature(access, rsdp_address, 8)? != b"RSD PTR " {
        return Err(AcpiError::RsdpSignature);
    }
    if !checksum_is_zero(access, rsdp_address, 20)? {
        return Err(AcpiError::RsdpChecksum);
    }
    if physical_byte(access, rsdp_address + 15)? < 2 {
        return Err(AcpiError::RsdpRevision);
    }
    if physical_u32(access, rsdp_address + 20)? != RSDP_BYTES as u32 {
        return Err(AcpiError::RsdpLength);
    }
    if !checksum_is_zero(access, rsdp_address, RSDP_BYTES)? {
        return Err(AcpiError::RsdpChecksum);
    }
    let xsdt_address = physical_u64(access, rsdp_address + 24)?;
    if xsdt_address == 0 || !xsdt_address.is_multiple_of(4) {
        return Err(AcpiError::XsdtAddress);
    }
    let xsdt = table_header(handoff, access, xsdt_address)?;
    if xsdt.signature != *b"XSDT"
        || xsdt.length < TABLE_HEADER_BYTES + 8
        || !(xsdt.length - TABLE_HEADER_BYTES).is_multiple_of(8)
    {
        return Err(AcpiError::XsdtShape);
    }
    let xsdt_entry_count = usize::try_from((xsdt.length - TABLE_HEADER_BYTES) / 8)
        .map_err(|_| AcpiError::XsdtShape)?;
    if !(1..=MAX_XSDT_ENTRIES).contains(&xsdt_entry_count) {
        return Err(AcpiError::XsdtShape);
    }

    let mut required = [EMPTY_TABLE_RECEIPT; REQUIRED_TABLE_COUNT];
    let mut required_mask = 0u8;
    for index in 0..xsdt_entry_count {
        let entry_address =
            physical_u64(access, xsdt_address + TABLE_HEADER_BYTES + index as u64 * 8)?;
        let header = table_header(handoff, access, entry_address)?;
        let Some(required_index) = required_index(header.signature) else {
            continue;
        };
        if required_mask & (1 << required_index) != 0 {
            return Err(AcpiError::DuplicateRequiredTable);
        }
        if header.length < minimum_length(header.signature) {
            return Err(AcpiError::TableLength);
        }
        required[required_index] = RequiredTableReceipt {
            signature: header.signature,
            source_address: entry_address,
            byte_count: header.length,
            snapshot_offset: 0,
            revision: header.revision,
            content_checksum: fnv_range(access, entry_address, header.length)?,
        };
        required_mask |= 1 << required_index;
    }
    if required_mask != REQUIRED_TABLE_MASK {
        return Err(AcpiError::MissingRequiredTable);
    }

    let rsdp_offset = 0u64;
    let xsdt_offset = align8(RSDP_BYTES)?;
    let mut snapshot_bytes = align8(
        xsdt_offset
            .checked_add(xsdt.length)
            .ok_or(AcpiError::SnapshotCapacity)?,
    )?;
    for table in &mut required {
        table.snapshot_offset = snapshot_bytes;
        snapshot_bytes = align8(
            snapshot_bytes
                .checked_add(table.byte_count)
                .ok_or(AcpiError::SnapshotCapacity)?,
        )?;
    }
    let snapshot_pages = snapshot_bytes.div_ceil(PAGE_BYTES);
    if snapshot_pages == 0 || snapshot_pages > MAX_SNAPSHOT_PAGES {
        return Err(AcpiError::SnapshotCapacity);
    }
    let mut source_checksum = fnv_range(access, rsdp_address, RSDP_BYTES)?;
    for offset in 0..xsdt.length {
        source_checksum = fnv_byte(
            source_checksum,
            physical_byte(
                access,
                xsdt_address
                    .checked_add(offset)
                    .ok_or(AcpiError::SourceRange)?,
            )?,
        );
    }
    for table in &required {
        for offset in 0..table.byte_count {
            source_checksum = fnv_byte(
                source_checksum,
                physical_byte(
                    access,
                    table
                        .source_address
                        .checked_add(offset)
                        .ok_or(AcpiError::SourceRange)?,
                )?,
            );
        }
    }
    let copied_byte_count = RSDP_BYTES
        .checked_add(xsdt.length)
        .and_then(|value| {
            required
                .iter()
                .try_fold(value, |total, table| total.checked_add(table.byte_count))
        })
        .ok_or(AcpiError::SnapshotCapacity)?;
    let (allocation, _) = manager
        .allocate_scrubbed(Zone::Dma32, snapshot_pages, SNAPSHOT_OWNER, access)
        .map_err(|_| AcpiError::SnapshotAllocation)?;
    let snapshot_address = match allocation.start_page.checked_mul(PAGE_BYTES) {
        Some(value) => value,
        None => {
            return rollback_snapshot(manager, access, allocation, AcpiError::SnapshotCapacity);
        }
    };

    let copy_result = (|| {
        copy_range(
            access,
            rsdp_address,
            snapshot_address
                .checked_add(rsdp_offset)
                .ok_or(AcpiError::SnapshotCopy)?,
            RSDP_BYTES,
        )?;
        copy_range(
            access,
            xsdt_address,
            snapshot_address
                .checked_add(xsdt_offset)
                .ok_or(AcpiError::SnapshotCopy)?,
            xsdt.length,
        )?;
        for table in &required {
            copy_range(
                access,
                table.source_address,
                snapshot_address
                    .checked_add(table.snapshot_offset)
                    .ok_or(AcpiError::SnapshotCopy)?,
                table.byte_count,
            )?;
        }
        Ok(())
    })();
    if let Err(error) = copy_result {
        return rollback_snapshot(manager, access, allocation, error);
    }

    let snapshot_checksum = match fnv_range(access, snapshot_address, snapshot_bytes) {
        Ok(value) if value != 0 => value,
        Ok(_) => {
            return rollback_snapshot(manager, access, allocation, AcpiError::SnapshotReadback);
        }
        Err(_) => {
            return rollback_snapshot(manager, access, allocation, AcpiError::SnapshotReadback);
        }
    };
    let evidence = acpi_release_evidence(allocation, snapshot_checksum, required_mask);
    if manager.release_acpi_tables(evidence).is_err() {
        return rollback_snapshot(manager, access, allocation, AcpiError::ReleaseEvidence);
    }
    Ok(AcpiSnapshotReceipt {
        rsdp_source_address: rsdp_address,
        xsdt_source_address: xsdt_address,
        xsdt_entry_count: xsdt_entry_count as u64,
        required_table_mask: required_mask,
        required_tables: required,
        allocation,
        snapshot_physical_address: snapshot_address,
        snapshot_page_count: snapshot_pages,
        snapshot_byte_count: snapshot_bytes,
        copied_byte_count,
        source_checksum,
        snapshot_checksum,
        copy_verified: true,
        lifecycle_released: true,
    })
}

impl From<PageAccessError> for AcpiError {
    fn from(_: PageAccessError) -> Self {
        Self::PhysicalAccess
    }
}

impl From<PhysicalMemoryError> for AcpiError {
    fn from(_: PhysicalMemoryError) -> Self {
        Self::SnapshotAllocation
    }
}

#[cfg(test)]
mod tests {
    extern crate std;

    use std::collections::BTreeMap;
    use std::vec;
    use std::vec::Vec;

    use poole_handoff::{
        BOOT_SERVICES_EXITED, CORE_BYTES, DEVELOPMENT_MODE, Encoder, MEMORY_LOADER_RESERVED,
        MEMORY_USABLE, RECORD_ARRAY, RECORD_CORE, RECORD_REQUIRED, encoded_size,
    };

    use super::*;
    use crate::physical_memory::{ReclaimClass, ReclaimStage};

    const RSDP: u64 = 0x0208_0000;
    const XSDT: u64 = 0x0208_0040;
    const FACP: u64 = 0x0208_0100;
    const APIC: u64 = 0x0208_0200;
    const HPET: u64 = 0x0208_0300;
    const MCFG: u64 = 0x0208_0400;

    #[derive(Default)]
    struct FakeAccess {
        words: BTreeMap<u64, u64>,
        write_count: u64,
        read_count: u64,
        fail_write_at: Option<u64>,
        drop_write_at: Option<u64>,
    }

    impl FakeAccess {
        fn byte(&self, address: u64) -> u8 {
            let word_address = address & !7;
            let shift = ((address & 7) * 8) as u32;
            (self.words.get(&word_address).copied().unwrap_or(0) >> shift) as u8
        }

        fn set_byte(&mut self, address: u64, value: u8) {
            let word_address = address & !7;
            let shift = ((address & 7) * 8) as u32;
            let mask = !(0xffu64 << shift);
            let word = self.words.get(&word_address).copied().unwrap_or(0);
            self.words
                .insert(word_address, (word & mask) | (u64::from(value) << shift));
        }

        fn set_bytes(&mut self, address: u64, bytes: &[u8]) {
            for (index, byte) in bytes.iter().copied().enumerate() {
                self.set_byte(address + index as u64, byte);
            }
        }

        fn fix_checksum(&mut self, address: u64, length: usize, checksum_offset: usize) {
            self.set_byte(address + checksum_offset as u64, 0);
            let sum = (0..length).fold(0u8, |value, index| {
                value.wrapping_add(self.byte(address + index as u64))
            });
            self.set_byte(address + checksum_offset as u64, 0u8.wrapping_sub(sum));
        }

        fn table(&mut self, address: u64, signature: &[u8; 4], length: usize) {
            self.set_bytes(address, signature);
            self.set_bytes(address + 4, &(length as u32).to_le_bytes());
            self.set_byte(address + 8, 1);
            self.set_bytes(address + 10, b"POOLE ");
            self.set_bytes(address + 16, b"POOLEOS ");
            self.fix_checksum(address, length, 9);
        }

        fn valid_tables() -> Self {
            let mut value = Self::default();
            value.table(FACP, b"FACP", 116);
            value.table(APIC, b"APIC", 44);
            value.table(HPET, b"HPET", 56);
            value.table(MCFG, b"MCFG", 44);
            let xsdt_length = 36 + REQUIRED_TABLE_COUNT * 8;
            value.table(XSDT, b"XSDT", xsdt_length);
            for (index, address) in [FACP, APIC, HPET, MCFG].iter().copied().enumerate() {
                value.set_bytes(XSDT + 36 + index as u64 * 8, &address.to_le_bytes());
            }
            value.fix_checksum(XSDT, xsdt_length, 9);

            value.set_bytes(RSDP, b"RSD PTR ");
            value.set_bytes(RSDP + 9, b"POOLE ");
            value.set_byte(RSDP + 15, 2);
            value.set_bytes(RSDP + 20, &(RSDP_BYTES as u32).to_le_bytes());
            value.set_bytes(RSDP + 24, &XSDT.to_le_bytes());
            value.fix_checksum(RSDP, 20, 8);
            value.fix_checksum(RSDP, RSDP_BYTES as usize, 32);
            value
        }
    }

    impl PhysicalPageAccess for FakeAccess {
        fn write_word(
            &mut self,
            physical_address: u64,
            word_index: usize,
            value: u64,
        ) -> Result<(), PageAccessError> {
            let sequence = self.write_count + 1;
            if self.fail_write_at == Some(sequence) {
                self.fail_write_at = None;
                return Err(PageAccessError::Access);
            }
            self.write_count = sequence;
            let address = physical_address + word_index as u64 * 8;
            if self.drop_write_at != Some(sequence) {
                self.words.insert(address, value);
            }
            Ok(())
        }

        fn read_word(
            &mut self,
            physical_address: u64,
            word_index: usize,
        ) -> Result<u64, PageAccessError> {
            self.read_count += 1;
            Ok(self
                .words
                .get(&(physical_address + word_index as u64 * 8))
                .copied()
                .unwrap_or(0))
        }
    }

    fn put_u32(bytes: &mut [u8], offset: usize, value: u32) {
        bytes[offset..offset + 4].copy_from_slice(&value.to_le_bytes());
    }

    fn put_u64(bytes: &mut [u8], offset: usize, value: u64) {
        bytes[offset..offset + 8].copy_from_slice(&value.to_le_bytes());
    }

    fn memory_entry(start: u64, pages: u64, kind: u32, source: u32) -> [u8; MEMORY_ENTRY_BYTES] {
        let mut value = [0u8; MEMORY_ENTRY_BYTES];
        put_u64(&mut value, 0, start);
        put_u64(&mut value, 8, pages);
        put_u32(&mut value, 24, kind);
        put_u32(&mut value, 28, source);
        value
    }

    fn handoff_fixture() -> (Vec<u8>, poole_handoff::CoreRecord) {
        let entries = [
            memory_entry(0, 4096, MEMORY_USABLE, 7),
            memory_entry(0x0100_0000, 4096, MEMORY_USABLE, 7),
            memory_entry(0x0200_0000, 96, MEMORY_LOADER_RESERVED, 2),
            memory_entry(0x0206_0000, 32, poole_handoff::MEMORY_BOOT_RECLAIMABLE, 4),
            memory_entry(RSDP, 4, MEMORY_ACPI_RECLAIMABLE, 9),
        ];
        let mut memory = Vec::new();
        for entry in entries {
            memory.extend_from_slice(&entry);
        }
        let mut firmware = [0u8; FIRMWARE_TABLE_ENTRY_BYTES];
        firmware[..16].copy_from_slice(&ACPI_20_TABLE_GUID);
        put_u64(&mut firmware, 16, RSDP);
        put_u64(&mut firmware, 24, RSDP_BYTES);
        put_u32(
            &mut firmware,
            32,
            FIRMWARE_TABLE_PHYSICAL | FIRMWARE_TABLE_CHECKSUM_VALIDATED,
        );
        let total = encoded_size(3, &[CORE_BYTES, memory.len(), firmware.len()]).unwrap();
        let mut core = [0u8; CORE_BYTES];
        put_u64(&mut core, 0, DEVELOPMENT_MODE | BOOT_SERVICES_EXITED);
        put_u64(&mut core, 8, 0x0200_0000);
        put_u64(&mut core, 16, 0x0004_0000);
        put_u64(&mut core, 24, 0xffff_ffff_8000_0000);
        put_u64(&mut core, 32, 0x0004_0000);
        put_u64(&mut core, 40, 0xffff_ffff_8000_8000);
        put_u64(&mut core, 48, 0xffff_ffff_8004_9000);
        put_u64(&mut core, 56, 0x0204_0000);
        put_u64(&mut core, 64, 0x0205_0000);
        put_u64(&mut core, 72, 0xffff_ffff_8005_0000);
        put_u64(&mut core, 80, total as u64);
        put_u32(&mut core, 108, 3);
        put_u32(&mut core, 112, 1);
        put_u32(&mut core, 116, 1);
        put_u32(&mut core, 120, 0x0002_0064);
        let mut output = vec![0u8; total];
        let mut encoder = Encoder::new(&mut output, 3, 0, 0).unwrap();
        encoder
            .push(RECORD_CORE, 1, RECORD_REQUIRED, CORE_BYTES, 1, &core)
            .unwrap();
        encoder
            .push(
                RECORD_MEMORY_MAP,
                1,
                RECORD_REQUIRED | RECORD_ARRAY,
                MEMORY_ENTRY_BYTES,
                entries.len(),
                &memory,
            )
            .unwrap();
        encoder
            .push(
                RECORD_FIRMWARE_TABLES,
                1,
                RECORD_REQUIRED | RECORD_ARRAY,
                FIRMWARE_TABLE_ENTRY_BYTES,
                1,
                &firmware,
            )
            .unwrap();
        let bytes = encoder.finish().unwrap().to_vec();
        let core = poole_handoff::decode(&bytes).unwrap().core().unwrap();
        (bytes, core)
    }

    fn manager_fixture<'a>(
        bytes: &'a [u8],
        core: poole_handoff::CoreRecord,
    ) -> (Handoff<'a>, PhysicalMemoryManager) {
        let handoff = poole_handoff::decode(bytes).unwrap();
        let mut manager = PhysicalMemoryManager::from_handoff(&handoff, core, 64).unwrap();
        manager
            .advance_reclaim_stage(ReclaimStage::PostExitBootServices)
            .unwrap();
        (handoff, manager)
    }

    #[test]
    fn copies_every_required_table_before_acpi_reclaim_and_retains_snapshot() {
        let (bytes, core) = handoff_fixture();
        let (handoff, mut manager) = manager_fixture(&bytes, core);
        let mut access = FakeAccess::valid_tables();
        assert_eq!(
            manager.advance_reclaim_stage(ReclaimStage::AcpiTablesReleased),
            Err(PhysicalMemoryError::ReclaimTiming)
        );
        let receipt = consume_required_tables(&handoff, &mut manager, &mut access).unwrap();
        assert_eq!(REQUIRED_TABLE_MASK, receipt.required_table_mask);
        assert_eq!(4, receipt.xsdt_entry_count);
        assert_eq!(1, receipt.snapshot_page_count);
        assert_eq!(384, receipt.snapshot_byte_count);
        assert!(receipt.copy_verified);
        assert!(receipt.lifecycle_released);
        assert_ne!(0, receipt.source_checksum);
        assert_ne!(0, receipt.snapshot_checksum);
        assert_eq!(
            REQUIRED_SIGNATURES,
            receipt.required_tables.map(|table| table.signature)
        );
        manager.validate_allocation(receipt.allocation).unwrap();
        let reclaimed = manager
            .reclaim_held(ReclaimClass::Acpi, &mut access)
            .unwrap();
        assert!(reclaimed.newly_reclaimed);
        assert_eq!(4, reclaimed.receipt.page_count);
        let repeated = manager
            .reclaim_held(ReclaimClass::Acpi, &mut access)
            .unwrap();
        assert!(!repeated.newly_reclaimed);
        assert_eq!(reclaimed.receipt, repeated.receipt);
        manager.validate_allocation(receipt.allocation).unwrap();
    }

    #[test]
    fn rejects_rsdp_xsdt_and_required_table_corruption() {
        let (bytes, core) = handoff_fixture();
        let cases = [
            (RSDP + 10, AcpiError::RsdpChecksum),
            (XSDT + 20, AcpiError::TableChecksum),
            (FACP + 20, AcpiError::TableChecksum),
        ];
        for (address, expected) in cases {
            let (handoff, mut manager) = manager_fixture(&bytes, core);
            let mut access = FakeAccess::valid_tables();
            access.set_byte(address, access.byte(address).wrapping_add(1));
            assert_eq!(
                consume_required_tables(&handoff, &mut manager, &mut access),
                Err(expected)
            );
            assert_eq!(
                ReclaimStage::PostExitBootServices,
                manager.summary().reclaim_stage
            );
        }
    }

    #[test]
    fn rejects_missing_duplicate_and_out_of_class_required_tables() {
        let (bytes, core) = handoff_fixture();

        let (handoff, mut manager) = manager_fixture(&bytes, core);
        let mut missing = FakeAccess::valid_tables();
        missing.set_bytes(MCFG, b"WAET");
        missing.fix_checksum(MCFG, 44, 9);
        assert_eq!(
            consume_required_tables(&handoff, &mut manager, &mut missing),
            Err(AcpiError::MissingRequiredTable)
        );

        let (handoff, mut manager) = manager_fixture(&bytes, core);
        let mut duplicate = FakeAccess::valid_tables();
        duplicate.set_bytes(MCFG, b"APIC");
        duplicate.fix_checksum(MCFG, 44, 9);
        assert_eq!(
            consume_required_tables(&handoff, &mut manager, &mut duplicate),
            Err(AcpiError::DuplicateRequiredTable)
        );

        let (handoff, mut manager) = manager_fixture(&bytes, core);
        let mut outside = FakeAccess::valid_tables();
        outside.set_bytes(RSDP + 24, &0x0200_0000u64.to_le_bytes());
        outside.fix_checksum(RSDP, RSDP_BYTES as usize, 32);
        assert_eq!(
            consume_required_tables(&handoff, &mut manager, &mut outside),
            Err(AcpiError::SourceRange)
        );
    }

    #[test]
    fn copy_and_readback_faults_roll_back_without_releasing_acpi() {
        let (bytes, core) = handoff_fixture();
        for (fail_write_at, drop_write_at, expected) in [
            (Some(513), None, AcpiError::SnapshotCopy),
            (None, Some(513), AcpiError::SnapshotReadback),
        ] {
            let (handoff, mut manager) = manager_fixture(&bytes, core);
            let mut access = FakeAccess::valid_tables();
            access.fail_write_at = fail_write_at;
            access.drop_write_at = drop_write_at;
            assert_eq!(
                consume_required_tables(&handoff, &mut manager, &mut access),
                Err(expected)
            );
            let summary = manager.summary();
            assert_eq!(0, summary.allocated_pages);
            assert_eq!(ReclaimStage::PostExitBootServices, summary.reclaim_stage);
            assert_eq!(
                manager.reclaim_held(ReclaimClass::Acpi, &mut access),
                Err(PhysicalMemoryError::ReclaimTiming)
            );
        }
    }
}
