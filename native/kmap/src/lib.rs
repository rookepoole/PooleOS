#![no_std]
#![deny(warnings)]

pub const CONTRACT_ID: &str = "PKMAP1";
pub const RETAINED_CONTRACT_ID: &str = "PKMAP2";
pub const PAGE_SIZE: u64 = 4096;
pub const TABLE_ENTRIES: usize = 512;
pub const TABLE_PAGE_COUNT: usize = 4;
pub const MAX_MAPPINGS: usize = 8;
pub const WINDOW_BYTES: u64 = 2 * 1024 * 1024;
pub const MIN_VIRTUAL_BASE: u64 = 0xffff_ffff_8000_0000;
pub const MAX_VIRTUAL_EXCLUSIVE: u64 = 0xffff_ffff_c000_0000;
pub const STACK_GUARD_LOW_PAGE: usize = 70;
pub const STACK_FIRST_PAGE: usize = 71;
pub const STACK_PAGE_COUNT: usize = 14;
pub const STACK_GUARD_HIGH_PAGE: usize = 85;
pub const HANDOFF_FIRST_PAGE: usize = 86;
pub const HANDOFF_PAGE_COUNT: usize = 256;
pub const HANDOFF_CAPACITY_BYTES: u64 = HANDOFF_PAGE_COUNT as u64 * PAGE_SIZE;
pub const TEMPORARY_PAGE_INDEX: usize = HANDOFF_FIRST_PAGE + HANDOFF_PAGE_COUNT;
pub const METADATA_GUARD_LOW_PAGE: usize = TEMPORARY_PAGE_INDEX + 1;
pub const METADATA_FIRST_PAGE: usize = METADATA_GUARD_LOW_PAGE + 1;
pub const METADATA_PAGE_COUNT: usize = 5;
pub const METADATA_GUARD_HIGH_PAGE: usize = METADATA_FIRST_PAGE + METADATA_PAGE_COUNT;

pub const ENTRY_PRESENT: u64 = 1 << 0;
pub const ENTRY_WRITABLE: u64 = 1 << 1;
pub const ENTRY_USER: u64 = 1 << 2;
pub const ENTRY_PWT: u64 = 1 << 3;
pub const ENTRY_PCD: u64 = 1 << 4;
pub const ENTRY_ACCESSED: u64 = 1 << 5;
pub const ENTRY_DIRTY: u64 = 1 << 6;
pub const ENTRY_PAGE_SIZE_OR_PAT: u64 = 1 << 7;
pub const ENTRY_GLOBAL: u64 = 1 << 8;
pub const ENTRY_LARGE_PAT: u64 = 1 << 12;
pub const ENTRY_NO_EXECUTE: u64 = 1 << 63;

const PARENT_FLAGS: u64 = ENTRY_PRESENT | ENTRY_WRITABLE;
const FNV_OFFSET: u64 = 0xcbf2_9ce4_8422_2325;
const FNV_PRIME: u64 = 0x0000_0100_0000_01b3;

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum Error {
    PagingDisabled,
    PaeDisabled,
    LongModeDisabled,
    WriteProtectDisabled,
    NxUnsupported,
    NxDisabled,
    FiveLevelPaging,
    PcidEnabled,
    PhysicalAddressBits,
    PhysicalAddress,
    VirtualAddress,
    ImageSize,
    PageCount,
    MappingCount,
    MappingAlignment,
    MappingCoverage,
    Permission,
    WritableExecutable,
    EntryPoint,
    WindowOverflow,
    TableAddress,
    TableOverlap,
    RootSlotOccupied,
    ParentEntry,
    LeafEntry,
    UnexpectedEntry,
    TranslationMissing,
    TranslationReserved,
    TranslationAddress,
    LargePageCollision,
    FramebufferRange,
    FramebufferDrift,
    ActivationMismatch,
    RollbackMismatch,
    FirmwareBeforeRollback,
    RetainedRange,
    RetainedOverlap,
    GuardPage,
    RetentionOrder,
    ReleaseOrder,
}

impl Error {
    pub const fn code(self) -> &'static str {
        match self {
            Self::PagingDisabled => "paging_disabled",
            Self::PaeDisabled => "pae_disabled",
            Self::LongModeDisabled => "long_mode_disabled",
            Self::WriteProtectDisabled => "write_protect_disabled",
            Self::NxUnsupported => "nx_unsupported",
            Self::NxDisabled => "nx_disabled",
            Self::FiveLevelPaging => "five_level_paging",
            Self::PcidEnabled => "pcid_enabled",
            Self::PhysicalAddressBits => "physical_address_bits",
            Self::PhysicalAddress => "physical_address",
            Self::VirtualAddress => "virtual_address",
            Self::ImageSize => "image_size",
            Self::PageCount => "page_count",
            Self::MappingCount => "mapping_count",
            Self::MappingAlignment => "mapping_alignment",
            Self::MappingCoverage => "mapping_coverage",
            Self::Permission => "permission",
            Self::WritableExecutable => "writable_executable",
            Self::EntryPoint => "entry_point",
            Self::WindowOverflow => "window_overflow",
            Self::TableAddress => "table_address",
            Self::TableOverlap => "table_overlap",
            Self::RootSlotOccupied => "root_slot_occupied",
            Self::ParentEntry => "parent_entry",
            Self::LeafEntry => "leaf_entry",
            Self::UnexpectedEntry => "unexpected_entry",
            Self::TranslationMissing => "translation_missing",
            Self::TranslationReserved => "translation_reserved",
            Self::TranslationAddress => "translation_address",
            Self::LargePageCollision => "large_page_collision",
            Self::FramebufferRange => "framebuffer_range",
            Self::FramebufferDrift => "framebuffer_drift",
            Self::ActivationMismatch => "activation_mismatch",
            Self::RollbackMismatch => "rollback_mismatch",
            Self::FirmwareBeforeRollback => "firmware_before_rollback",
            Self::RetainedRange => "retained_range",
            Self::RetainedOverlap => "retained_overlap",
            Self::GuardPage => "guard_page",
            Self::RetentionOrder => "retention_order",
            Self::ReleaseOrder => "release_order",
        }
    }
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct CpuProfile {
    pub paging: bool,
    pub pae: bool,
    pub long_mode: bool,
    pub write_protect: bool,
    pub nx_supported: bool,
    pub nx_enabled: bool,
    pub five_level_paging: bool,
    pub pcid_enabled: bool,
    pub physical_address_bits: u8,
}

pub fn validate_cpu(profile: CpuProfile) -> Result<(), Error> {
    if !profile.paging {
        return Err(Error::PagingDisabled);
    }
    if !profile.pae {
        return Err(Error::PaeDisabled);
    }
    if !profile.long_mode {
        return Err(Error::LongModeDisabled);
    }
    if !profile.write_protect {
        return Err(Error::WriteProtectDisabled);
    }
    if !profile.nx_supported {
        return Err(Error::NxUnsupported);
    }
    if !profile.nx_enabled {
        return Err(Error::NxDisabled);
    }
    if profile.five_level_paging {
        return Err(Error::FiveLevelPaging);
    }
    if profile.pcid_enabled {
        return Err(Error::PcidEnabled);
    }
    physical_mask(profile.physical_address_bits)?;
    Ok(())
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct Permissions {
    pub read: bool,
    pub write: bool,
    pub execute: bool,
}

impl Permissions {
    pub const NONE: Self = Self {
        read: false,
        write: false,
        execute: false,
    };
    pub const READ: Self = Self {
        read: true,
        write: false,
        execute: false,
    };
    pub const READ_EXECUTE: Self = Self {
        read: true,
        write: false,
        execute: true,
    };
    pub const READ_WRITE: Self = Self {
        read: true,
        write: true,
        execute: false,
    };
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct Mapping {
    pub virtual_offset: u32,
    pub byte_count: u32,
    pub permissions: Permissions,
}

impl Mapping {
    pub const EMPTY: Self = Self {
        virtual_offset: 0,
        byte_count: 0,
        permissions: Permissions::NONE,
    };
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct Request {
    pub physical_base: u64,
    pub virtual_base: u64,
    pub image_bytes: u32,
    pub page_count: u32,
    pub entry_virtual: u64,
    pub mapping_count: u8,
    pub mappings: [Mapping; MAX_MAPPINGS],
    pub physical_address_bits: u8,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct TableAddresses {
    pub original_root: u64,
    pub candidate_root: u64,
    pub pdpt: u64,
    pub page_directory: u64,
    pub page_table: u64,
}

impl TableAddresses {
    pub fn contiguous(original_root: u64, allocation_base: u64) -> Result<Self, Error> {
        let pdpt = allocation_base
            .checked_add(PAGE_SIZE)
            .ok_or(Error::TableAddress)?;
        let page_directory = pdpt.checked_add(PAGE_SIZE).ok_or(Error::TableAddress)?;
        let page_table = page_directory
            .checked_add(PAGE_SIZE)
            .ok_or(Error::TableAddress)?;
        Ok(Self {
            original_root,
            candidate_root: allocation_base,
            pdpt,
            page_directory,
            page_table,
        })
    }
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct Summary {
    pub pml4_index: u16,
    pub pdpt_index: u16,
    pub page_directory_index: u16,
    pub first_page_table_index: u16,
    pub mapped_page_count: u32,
    pub read_only_page_count: u32,
    pub read_execute_page_count: u32,
    pub read_write_page_count: u32,
    pub writable_executable_page_count: u32,
    pub leaf_fingerprint: u64,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct RetainedRequest {
    pub stack_physical_base: u64,
    pub stack_page_count: u32,
    pub handoff_physical_base: u64,
    pub handoff_capacity_bytes: u32,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct RetainedSummary {
    pub kernel: Summary,
    pub stack_first_page_table_index: u16,
    pub stack_page_count: u32,
    pub stack_bottom_virtual: u64,
    pub stack_top_virtual: u64,
    pub handoff_first_page_table_index: u16,
    pub handoff_page_count: u32,
    pub handoff_virtual_base: u64,
    pub guard_page_count: u32,
    pub total_mapped_page_count: u32,
    pub retained_leaf_fingerprint: u64,
}

fn physical_mask(bits: u8) -> Result<u64, Error> {
    if !(36..=52).contains(&bits) {
        return Err(Error::PhysicalAddressBits);
    }
    Ok(((1u64 << bits) - 1) & !(PAGE_SIZE - 1))
}

fn range_end(start: u64, byte_count: u64, error: Error) -> Result<u64, Error> {
    start.checked_add(byte_count).ok_or(error)
}

fn ranges_overlap(first: u64, first_bytes: u64, second: u64, second_bytes: u64) -> bool {
    let first_end = first.saturating_add(first_bytes);
    let second_end = second.saturating_add(second_bytes);
    first < second_end && second < first_end
}

pub const fn is_canonical_48(address: u64) -> bool {
    let upper = address >> 48;
    if address & (1 << 47) == 0 {
        upper == 0
    } else {
        upper == 0xffff
    }
}

const fn pml4_index(address: u64) -> usize {
    ((address >> 39) & 0x1ff) as usize
}

const fn pdpt_index(address: u64) -> usize {
    ((address >> 30) & 0x1ff) as usize
}

const fn page_directory_index(address: u64) -> usize {
    ((address >> 21) & 0x1ff) as usize
}

const fn page_table_index(address: u64) -> usize {
    ((address >> 12) & 0x1ff) as usize
}

fn fnv_u64(mut state: u64, value: u64) -> u64 {
    for byte in value.to_le_bytes() {
        state ^= u64::from(byte);
        state = state.wrapping_mul(FNV_PRIME);
    }
    state
}

fn permission_code(permissions: Permissions) -> u64 {
    u64::from(permissions.read)
        | (u64::from(permissions.write) << 1)
        | (u64::from(permissions.execute) << 2)
}

fn leaf_flags(permissions: Permissions) -> u64 {
    ENTRY_PRESENT
        | if permissions.write { ENTRY_WRITABLE } else { 0 }
        | if permissions.execute {
            0
        } else {
            ENTRY_NO_EXECUTE
        }
}

fn request_summary(request: &Request, addresses: TableAddresses) -> Result<Summary, Error> {
    let address_mask = physical_mask(request.physical_address_bits)?;
    let maximum_physical = 1u64 << request.physical_address_bits;
    if request.physical_base == 0
        || request.physical_base & (PAGE_SIZE - 1) != 0
        || range_end(
            request.physical_base,
            u64::from(request.image_bytes),
            Error::PhysicalAddress,
        )? > maximum_physical
    {
        return Err(Error::PhysicalAddress);
    }
    if request.virtual_base < MIN_VIRTUAL_BASE
        || request.virtual_base >= MAX_VIRTUAL_EXCLUSIVE
        || request.virtual_base & (WINDOW_BYTES - 1) != 0
        || !is_canonical_48(request.virtual_base)
    {
        return Err(Error::VirtualAddress);
    }
    if request.image_bytes == 0
        || u64::from(request.image_bytes) > WINDOW_BYTES
        || u64::from(request.image_bytes) & (PAGE_SIZE - 1) != 0
    {
        return Err(Error::ImageSize);
    }
    let expected_pages = u64::from(request.image_bytes) / PAGE_SIZE;
    if u64::from(request.page_count) != expected_pages {
        return Err(Error::PageCount);
    }
    let virtual_end = range_end(
        request.virtual_base,
        u64::from(request.image_bytes),
        Error::WindowOverflow,
    )?;
    if virtual_end > MAX_VIRTUAL_EXCLUSIVE
        || !is_canonical_48(virtual_end - 1)
        || page_directory_index(request.virtual_base) != page_directory_index(virtual_end - 1)
    {
        return Err(Error::WindowOverflow);
    }
    if request.mapping_count == 0 || usize::from(request.mapping_count) > MAX_MAPPINGS {
        return Err(Error::MappingCount);
    }
    if request.entry_virtual < request.virtual_base || request.entry_virtual >= virtual_end {
        return Err(Error::EntryPoint);
    }

    let table_values = [
        addresses.original_root,
        addresses.candidate_root,
        addresses.pdpt,
        addresses.page_directory,
        addresses.page_table,
    ];
    for value in table_values {
        if value == 0 || value & (PAGE_SIZE - 1) != 0 || value & !address_mask != 0 {
            return Err(Error::TableAddress);
        }
    }
    if addresses.pdpt != addresses.candidate_root + PAGE_SIZE
        || addresses.page_directory != addresses.pdpt + PAGE_SIZE
        || addresses.page_table != addresses.page_directory + PAGE_SIZE
    {
        return Err(Error::TableAddress);
    }
    for first in 0..table_values.len() {
        for second in first + 1..table_values.len() {
            if table_values[first] == table_values[second] {
                return Err(Error::TableOverlap);
            }
        }
    }
    if ranges_overlap(
        request.physical_base,
        u64::from(request.image_bytes),
        addresses.candidate_root,
        TABLE_PAGE_COUNT as u64 * PAGE_SIZE,
    ) {
        return Err(Error::TableOverlap);
    }

    let mut expected_offset = 0u64;
    let mut entry_executable = false;
    let mut read_only_page_count = 0u32;
    let mut read_execute_page_count = 0u32;
    let mut read_write_page_count = 0u32;
    let mut writable_executable_page_count = 0u32;
    let mut leaf_fingerprint = FNV_OFFSET;
    for mapping in request
        .mappings
        .iter()
        .take(usize::from(request.mapping_count))
    {
        if mapping.byte_count == 0
            || u64::from(mapping.virtual_offset) & (PAGE_SIZE - 1) != 0
            || u64::from(mapping.byte_count) & (PAGE_SIZE - 1) != 0
        {
            return Err(Error::MappingAlignment);
        }
        if u64::from(mapping.virtual_offset) != expected_offset {
            return Err(Error::MappingCoverage);
        }
        if !mapping.permissions.read {
            return Err(Error::Permission);
        }
        if mapping.permissions.write && mapping.permissions.execute {
            return Err(Error::WritableExecutable);
        }
        let mapping_end = expected_offset
            .checked_add(u64::from(mapping.byte_count))
            .ok_or(Error::MappingCoverage)?;
        if mapping_end > u64::from(request.image_bytes) {
            return Err(Error::MappingCoverage);
        }
        let mapping_virtual = request
            .virtual_base
            .checked_add(expected_offset)
            .ok_or(Error::VirtualAddress)?;
        let mapping_virtual_end = request
            .virtual_base
            .checked_add(mapping_end)
            .ok_or(Error::VirtualAddress)?;
        if request.entry_virtual >= mapping_virtual
            && request.entry_virtual < mapping_virtual_end
            && mapping.permissions.execute
        {
            entry_executable = true;
        }
        let mapping_pages = u32::try_from(u64::from(mapping.byte_count) / PAGE_SIZE)
            .map_err(|_| Error::PageCount)?;
        if mapping.permissions.write && mapping.permissions.execute {
            writable_executable_page_count += mapping_pages;
        } else if mapping.permissions.execute {
            read_execute_page_count += mapping_pages;
        } else if mapping.permissions.write {
            read_write_page_count += mapping_pages;
        } else {
            read_only_page_count += mapping_pages;
        }
        let first_page = expected_offset / PAGE_SIZE;
        for page in 0..u64::from(mapping_pages) {
            leaf_fingerprint = fnv_u64(leaf_fingerprint, first_page + page);
            leaf_fingerprint = fnv_u64(leaf_fingerprint, permission_code(mapping.permissions));
        }
        expected_offset = mapping_end;
    }
    if expected_offset != u64::from(request.image_bytes) {
        return Err(Error::MappingCoverage);
    }
    if !entry_executable {
        return Err(Error::EntryPoint);
    }
    Ok(Summary {
        pml4_index: pml4_index(request.virtual_base) as u16,
        pdpt_index: pdpt_index(request.virtual_base) as u16,
        page_directory_index: page_directory_index(request.virtual_base) as u16,
        first_page_table_index: page_table_index(request.virtual_base) as u16,
        mapped_page_count: request.page_count,
        read_only_page_count,
        read_execute_page_count,
        read_write_page_count,
        writable_executable_page_count,
        leaf_fingerprint,
    })
}

fn mapping_for_offset(request: &Request, offset: u64) -> Result<Permissions, Error> {
    for mapping in request
        .mappings
        .iter()
        .take(usize::from(request.mapping_count))
    {
        let start = u64::from(mapping.virtual_offset);
        let end = start + u64::from(mapping.byte_count);
        if offset >= start && offset < end {
            return Ok(mapping.permissions);
        }
    }
    Err(Error::MappingCoverage)
}

pub fn populate(
    request: &Request,
    addresses: TableAddresses,
    original_root: &[u64; TABLE_ENTRIES],
    candidate_root: &mut [u64; TABLE_ENTRIES],
    pdpt: &mut [u64; TABLE_ENTRIES],
    page_directory: &mut [u64; TABLE_ENTRIES],
    page_table: &mut [u64; TABLE_ENTRIES],
) -> Result<Summary, Error> {
    let summary = request_summary(request, addresses)?;
    let root_index = usize::from(summary.pml4_index);
    if original_root[root_index] != 0 {
        return Err(Error::RootSlotOccupied);
    }
    candidate_root.copy_from_slice(original_root);
    pdpt.fill(0);
    page_directory.fill(0);
    page_table.fill(0);
    candidate_root[root_index] = addresses.pdpt | PARENT_FLAGS;
    pdpt[usize::from(summary.pdpt_index)] = addresses.page_directory | PARENT_FLAGS;
    page_directory[usize::from(summary.page_directory_index)] = addresses.page_table | PARENT_FLAGS;
    let first_leaf = usize::from(summary.first_page_table_index);
    for page in 0..usize::try_from(request.page_count).map_err(|_| Error::PageCount)? {
        let offset = page as u64 * PAGE_SIZE;
        let permissions = mapping_for_offset(request, offset)?;
        page_table[first_leaf + page] = (request.physical_base + offset) | leaf_flags(permissions);
    }
    verify(
        request,
        addresses,
        original_root,
        candidate_root,
        pdpt,
        page_directory,
        page_table,
    )
}

pub fn verify(
    request: &Request,
    addresses: TableAddresses,
    original_root: &[u64; TABLE_ENTRIES],
    candidate_root: &[u64; TABLE_ENTRIES],
    pdpt: &[u64; TABLE_ENTRIES],
    page_directory: &[u64; TABLE_ENTRIES],
    page_table: &[u64; TABLE_ENTRIES],
) -> Result<Summary, Error> {
    let summary = request_summary(request, addresses)?;
    let root_index = usize::from(summary.pml4_index);
    if original_root[root_index] != 0 {
        return Err(Error::RootSlotOccupied);
    }
    for (index, observed) in candidate_root.iter().enumerate() {
        let expected = if index == root_index {
            addresses.pdpt | PARENT_FLAGS
        } else {
            original_root[index]
        };
        if *observed != expected {
            return Err(if index == root_index {
                Error::ParentEntry
            } else {
                Error::UnexpectedEntry
            });
        }
    }
    let pdpt_target = usize::from(summary.pdpt_index);
    let directory_target = usize::from(summary.page_directory_index);
    for (index, (observed_pdpt, observed_directory)) in
        pdpt.iter().zip(page_directory.iter()).enumerate()
    {
        let expected_pdpt = if index == pdpt_target {
            addresses.page_directory | PARENT_FLAGS
        } else {
            0
        };
        if *observed_pdpt != expected_pdpt {
            return Err(if index == pdpt_target {
                Error::ParentEntry
            } else {
                Error::UnexpectedEntry
            });
        }
        let expected_directory = if index == directory_target {
            addresses.page_table | PARENT_FLAGS
        } else {
            0
        };
        if *observed_directory != expected_directory {
            return Err(if index == directory_target {
                Error::ParentEntry
            } else {
                Error::UnexpectedEntry
            });
        }
    }
    let first_leaf = usize::from(summary.first_page_table_index);
    let page_count = usize::try_from(request.page_count).map_err(|_| Error::PageCount)?;
    for (index, observed) in page_table.iter().enumerate() {
        let expected = if index >= first_leaf && index < first_leaf + page_count {
            let offset = (index - first_leaf) as u64 * PAGE_SIZE;
            let permissions = mapping_for_offset(request, offset)?;
            (request.physical_base + offset) | leaf_flags(permissions)
        } else {
            0
        };
        if *observed != expected {
            return Err(if index >= first_leaf && index < first_leaf + page_count {
                Error::LeafEntry
            } else {
                Error::UnexpectedEntry
            });
        }
    }
    Ok(summary)
}

fn retained_summary(
    request: &Request,
    addresses: TableAddresses,
    retained: RetainedRequest,
) -> Result<RetainedSummary, Error> {
    let kernel = request_summary(request, addresses)?;
    if kernel.first_page_table_index != 0
        || usize::try_from(request.page_count).map_err(|_| Error::PageCount)? > STACK_GUARD_LOW_PAGE
        || retained.stack_physical_base == 0
        || retained.stack_physical_base & (PAGE_SIZE - 1) != 0
        || usize::try_from(retained.stack_page_count).map_err(|_| Error::RetainedRange)?
            != STACK_PAGE_COUNT
        || retained.handoff_physical_base == 0
        || retained.handoff_physical_base & (PAGE_SIZE - 1) != 0
        || u64::from(retained.handoff_capacity_bytes) != HANDOFF_CAPACITY_BYTES
    {
        return Err(Error::RetainedRange);
    }
    let maximum_physical = 1u64 << request.physical_address_bits;
    let kernel_bytes = u64::from(request.image_bytes);
    let table_bytes = TABLE_PAGE_COUNT as u64 * PAGE_SIZE;
    let stack_bytes = retained.stack_page_count as u64 * PAGE_SIZE;
    let handoff_bytes = u64::from(retained.handoff_capacity_bytes);
    for (start, byte_count) in [
        (retained.stack_physical_base, stack_bytes),
        (retained.handoff_physical_base, handoff_bytes),
    ] {
        if range_end(start, byte_count, Error::RetainedRange)? > maximum_physical {
            return Err(Error::RetainedRange);
        }
    }
    let ranges = [
        (request.physical_base, kernel_bytes),
        (addresses.candidate_root, table_bytes),
        (retained.stack_physical_base, stack_bytes),
        (retained.handoff_physical_base, handoff_bytes),
    ];
    for first in 0..ranges.len() {
        for second in first + 1..ranges.len() {
            if ranges_overlap(
                ranges[first].0,
                ranges[first].1,
                ranges[second].0,
                ranges[second].1,
            ) {
                return Err(Error::RetainedOverlap);
            }
        }
    }
    let stack_bottom_virtual = request
        .virtual_base
        .checked_add(STACK_FIRST_PAGE as u64 * PAGE_SIZE)
        .ok_or(Error::RetainedRange)?;
    let stack_top_virtual = stack_bottom_virtual
        .checked_add(stack_bytes)
        .ok_or(Error::RetainedRange)?;
    let handoff_virtual_base = request
        .virtual_base
        .checked_add(HANDOFF_FIRST_PAGE as u64 * PAGE_SIZE)
        .ok_or(Error::RetainedRange)?;
    let handoff_end = handoff_virtual_base
        .checked_add(handoff_bytes)
        .ok_or(Error::RetainedRange)?;
    if !is_canonical_48(stack_bottom_virtual)
        || !is_canonical_48(stack_top_virtual - 1)
        || !is_canonical_48(handoff_virtual_base)
        || !is_canonical_48(handoff_end - 1)
        || handoff_end > request.virtual_base + WINDOW_BYTES
        || STACK_FIRST_PAGE + STACK_PAGE_COUNT != STACK_GUARD_HIGH_PAGE
        || STACK_GUARD_HIGH_PAGE >= HANDOFF_FIRST_PAGE
        || HANDOFF_FIRST_PAGE + HANDOFF_PAGE_COUNT > TABLE_ENTRIES
    {
        return Err(Error::RetainedRange);
    }
    let mut fingerprint = FNV_OFFSET;
    for page in 0..STACK_PAGE_COUNT {
        fingerprint = fnv_u64(fingerprint, 1);
        fingerprint = fnv_u64(fingerprint, (STACK_FIRST_PAGE + page) as u64);
        fingerprint = fnv_u64(
            fingerprint,
            retained.stack_physical_base + page as u64 * PAGE_SIZE,
        );
        fingerprint = fnv_u64(fingerprint, permission_code(Permissions::READ_WRITE));
    }
    for page in 0..HANDOFF_PAGE_COUNT {
        fingerprint = fnv_u64(fingerprint, 2);
        fingerprint = fnv_u64(fingerprint, (HANDOFF_FIRST_PAGE + page) as u64);
        fingerprint = fnv_u64(
            fingerprint,
            retained.handoff_physical_base + page as u64 * PAGE_SIZE,
        );
        fingerprint = fnv_u64(fingerprint, permission_code(Permissions::READ));
    }
    Ok(RetainedSummary {
        kernel,
        stack_first_page_table_index: STACK_FIRST_PAGE as u16,
        stack_page_count: retained.stack_page_count,
        stack_bottom_virtual,
        stack_top_virtual,
        handoff_first_page_table_index: HANDOFF_FIRST_PAGE as u16,
        handoff_page_count: HANDOFF_PAGE_COUNT as u32,
        handoff_virtual_base,
        guard_page_count: 2,
        total_mapped_page_count: request.page_count
            + retained.stack_page_count
            + HANDOFF_PAGE_COUNT as u32,
        retained_leaf_fingerprint: fingerprint,
    })
}

fn retained_leaf(request: &Request, retained: RetainedRequest, index: usize) -> Result<u64, Error> {
    let first_kernel = page_table_index(request.virtual_base);
    let kernel_pages = usize::try_from(request.page_count).map_err(|_| Error::PageCount)?;
    if index >= first_kernel && index < first_kernel + kernel_pages {
        let page = index - first_kernel;
        let offset = page as u64 * PAGE_SIZE;
        let permissions = mapping_for_offset(request, offset)?;
        return Ok((request.physical_base + offset) | leaf_flags(permissions));
    }
    if (STACK_FIRST_PAGE..STACK_FIRST_PAGE + STACK_PAGE_COUNT).contains(&index) {
        let page = index - STACK_FIRST_PAGE;
        return Ok((retained.stack_physical_base + page as u64 * PAGE_SIZE)
            | leaf_flags(Permissions::READ_WRITE));
    }
    if (HANDOFF_FIRST_PAGE..HANDOFF_FIRST_PAGE + HANDOFF_PAGE_COUNT).contains(&index) {
        let page = index - HANDOFF_FIRST_PAGE;
        return Ok((retained.handoff_physical_base + page as u64 * PAGE_SIZE)
            | leaf_flags(Permissions::READ));
    }
    Ok(0)
}

#[allow(clippy::too_many_arguments)]
pub fn populate_retained(
    request: &Request,
    retained: RetainedRequest,
    addresses: TableAddresses,
    original_root: &[u64; TABLE_ENTRIES],
    candidate_root: &mut [u64; TABLE_ENTRIES],
    pdpt: &mut [u64; TABLE_ENTRIES],
    page_directory: &mut [u64; TABLE_ENTRIES],
    page_table: &mut [u64; TABLE_ENTRIES],
) -> Result<RetainedSummary, Error> {
    let summary = retained_summary(request, addresses, retained)?;
    populate(
        request,
        addresses,
        original_root,
        candidate_root,
        pdpt,
        page_directory,
        page_table,
    )?;
    for (index, entry) in page_table
        .iter_mut()
        .enumerate()
        .skip(STACK_FIRST_PAGE)
        .take(STACK_PAGE_COUNT)
    {
        *entry = retained_leaf(request, retained, index)?;
    }
    for (index, entry) in page_table
        .iter_mut()
        .enumerate()
        .skip(HANDOFF_FIRST_PAGE)
        .take(HANDOFF_PAGE_COUNT)
    {
        *entry = retained_leaf(request, retained, index)?;
    }
    let observed = verify_retained(
        request,
        retained,
        addresses,
        original_root,
        candidate_root,
        pdpt,
        page_directory,
        page_table,
    )?;
    if observed != summary {
        return Err(Error::LeafEntry);
    }
    Ok(summary)
}

#[allow(clippy::too_many_arguments)]
pub fn verify_retained(
    request: &Request,
    retained: RetainedRequest,
    addresses: TableAddresses,
    original_root: &[u64; TABLE_ENTRIES],
    candidate_root: &[u64; TABLE_ENTRIES],
    pdpt: &[u64; TABLE_ENTRIES],
    page_directory: &[u64; TABLE_ENTRIES],
    page_table: &[u64; TABLE_ENTRIES],
) -> Result<RetainedSummary, Error> {
    let summary = retained_summary(request, addresses, retained)?;
    let root_index = usize::from(summary.kernel.pml4_index);
    if original_root[root_index] != 0 {
        return Err(Error::RootSlotOccupied);
    }
    for (index, observed) in candidate_root.iter().enumerate() {
        let expected = if index == root_index {
            addresses.pdpt | PARENT_FLAGS
        } else {
            original_root[index]
        };
        if *observed != expected {
            return Err(if index == root_index {
                Error::ParentEntry
            } else {
                Error::UnexpectedEntry
            });
        }
    }
    let pdpt_target = usize::from(summary.kernel.pdpt_index);
    let directory_target = usize::from(summary.kernel.page_directory_index);
    for (index, (observed_pdpt, observed_directory)) in
        pdpt.iter().zip(page_directory.iter()).enumerate()
    {
        let expected_pdpt = if index == pdpt_target {
            addresses.page_directory | PARENT_FLAGS
        } else {
            0
        };
        let expected_directory = if index == directory_target {
            addresses.page_table | PARENT_FLAGS
        } else {
            0
        };
        if *observed_pdpt != expected_pdpt || *observed_directory != expected_directory {
            return Err(if index == pdpt_target || index == directory_target {
                Error::ParentEntry
            } else {
                Error::UnexpectedEntry
            });
        }
    }
    for (index, observed) in page_table.iter().enumerate() {
        let expected = retained_leaf(request, retained, index)?;
        if *observed != expected {
            return Err(
                if matches!(index, STACK_GUARD_LOW_PAGE | STACK_GUARD_HIGH_PAGE) {
                    Error::GuardPage
                } else if expected != 0 {
                    Error::LeafEntry
                } else {
                    Error::UnexpectedEntry
                },
            );
        }
    }
    Ok(summary)
}

pub trait TableReader {
    fn read_entry(&self, table_address: u64, index: usize) -> Result<u64, Error>;
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct CacheBits {
    pub pwt: bool,
    pub pcd: bool,
    pub pat: bool,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct Translation {
    pub physical_address: u64,
    pub page_size: u64,
    pub writable: bool,
    pub executable: bool,
    pub user: bool,
    pub cache: CacheBits,
}

fn entry_address(entry: u64, mask: u64) -> Result<u64, Error> {
    let address = entry & mask;
    if address == 0 || address & (PAGE_SIZE - 1) != 0 {
        return Err(Error::TranslationAddress);
    }
    Ok(address)
}

fn cache_bits(entry: u64, large: bool) -> CacheBits {
    CacheBits {
        pwt: entry & ENTRY_PWT != 0,
        pcd: entry & ENTRY_PCD != 0,
        pat: entry
            & if large {
                ENTRY_LARGE_PAT
            } else {
                ENTRY_PAGE_SIZE_OR_PAT
            }
            != 0,
    }
}

pub fn translate<R: TableReader>(
    reader: &R,
    root: u64,
    virtual_address: u64,
    physical_address_bits: u8,
) -> Result<Translation, Error> {
    if !is_canonical_48(virtual_address) {
        return Err(Error::VirtualAddress);
    }
    let mask = physical_mask(physical_address_bits)?;
    if root == 0 || root & !mask != 0 {
        return Err(Error::TranslationAddress);
    }
    let indices = [
        pml4_index(virtual_address),
        pdpt_index(virtual_address),
        page_directory_index(virtual_address),
        page_table_index(virtual_address),
    ];
    let mut table = root;
    let mut writable = true;
    let mut executable = true;
    let mut user = true;
    for (level, index) in indices.into_iter().enumerate() {
        let entry = reader.read_entry(table, index)?;
        if entry & ENTRY_PRESENT == 0 {
            return Err(Error::TranslationMissing);
        }
        writable &= entry & ENTRY_WRITABLE != 0;
        executable &= entry & ENTRY_NO_EXECUTE == 0;
        user &= entry & ENTRY_USER != 0;
        if level == 0 && entry & ENTRY_PAGE_SIZE_OR_PAT != 0 {
            return Err(Error::TranslationReserved);
        }
        if level == 1 && entry & ENTRY_PAGE_SIZE_OR_PAT != 0 {
            let page_size = 1024 * 1024 * 1024u64;
            let base = (entry & mask) & !(page_size - 1);
            return Ok(Translation {
                physical_address: base | (virtual_address & (page_size - 1)),
                page_size,
                writable,
                executable,
                user,
                cache: cache_bits(entry, true),
            });
        }
        if level == 2 && entry & ENTRY_PAGE_SIZE_OR_PAT != 0 {
            let page_size = WINDOW_BYTES;
            let base = (entry & mask) & !(page_size - 1);
            return Ok(Translation {
                physical_address: base | (virtual_address & (page_size - 1)),
                page_size,
                writable,
                executable,
                user,
                cache: cache_bits(entry, true),
            });
        }
        if level == 3 {
            let base = entry & mask;
            return Ok(Translation {
                physical_address: base | (virtual_address & (PAGE_SIZE - 1)),
                page_size: PAGE_SIZE,
                writable,
                executable,
                user,
                cache: cache_bits(entry, false),
            });
        }
        table = entry_address(entry, mask)?;
    }
    Err(Error::TranslationMissing)
}

pub fn verify_kernel_translations<R: TableReader>(
    reader: &R,
    root: u64,
    request: &Request,
) -> Result<Summary, Error> {
    let addresses = TableAddresses::contiguous(PAGE_SIZE, 2 * PAGE_SIZE)?;
    let mut summary = request_summary(request, addresses)?;
    let mut fingerprint = FNV_OFFSET;
    for page in 0..u64::from(request.page_count) {
        let offset = page * PAGE_SIZE;
        let permissions = mapping_for_offset(request, offset)?;
        let translation = translate(
            reader,
            root,
            request.virtual_base + offset,
            request.physical_address_bits,
        )?;
        if translation.page_size != PAGE_SIZE {
            return Err(Error::LargePageCollision);
        }
        if translation.physical_address != request.physical_base + offset
            || translation.writable != permissions.write
            || translation.executable != permissions.execute
            || translation.user
            || translation.cache
                != (CacheBits {
                    pwt: false,
                    pcd: false,
                    pat: false,
                })
        {
            return Err(Error::LeafEntry);
        }
        fingerprint = fnv_u64(fingerprint, page);
        fingerprint = fnv_u64(fingerprint, permission_code(permissions));
    }
    if fingerprint != summary.leaf_fingerprint {
        return Err(Error::LeafEntry);
    }
    summary.leaf_fingerprint = fingerprint;
    let entry = translate(
        reader,
        root,
        request.entry_virtual,
        request.physical_address_bits,
    )?;
    if !entry.executable || entry.writable || entry.user {
        return Err(Error::EntryPoint);
    }
    Ok(summary)
}

fn verify_retained_translation<R: TableReader>(
    reader: &R,
    root: u64,
    virtual_address: u64,
    physical_address: u64,
    writable: bool,
    physical_address_bits: u8,
) -> Result<(), Error> {
    let translation = translate(reader, root, virtual_address, physical_address_bits)?;
    if translation.physical_address != physical_address
        || translation.page_size != PAGE_SIZE
        || translation.writable != writable
        || translation.executable
        || translation.user
        || translation.cache
            != (CacheBits {
                pwt: false,
                pcd: false,
                pat: false,
            })
    {
        return Err(Error::LeafEntry);
    }
    Ok(())
}

pub fn verify_retained_translations<R: TableReader>(
    reader: &R,
    root: u64,
    request: &Request,
    retained: RetainedRequest,
    expected: RetainedSummary,
) -> Result<(), Error> {
    if verify_kernel_translations(reader, root, request)? != expected.kernel {
        return Err(Error::LeafEntry);
    }
    let stack_bytes = retained.stack_page_count as u64 * PAGE_SIZE;
    verify_retained_translation(
        reader,
        root,
        expected.stack_bottom_virtual,
        retained.stack_physical_base,
        true,
        request.physical_address_bits,
    )?;
    verify_retained_translation(
        reader,
        root,
        expected.stack_top_virtual - 1,
        retained.stack_physical_base + stack_bytes - 1,
        true,
        request.physical_address_bits,
    )?;
    verify_retained_translation(
        reader,
        root,
        expected.handoff_virtual_base,
        retained.handoff_physical_base,
        false,
        request.physical_address_bits,
    )?;
    verify_retained_translation(
        reader,
        root,
        expected.handoff_virtual_base + u64::from(retained.handoff_capacity_bytes) - 1,
        retained.handoff_physical_base + u64::from(retained.handoff_capacity_bytes) - 1,
        false,
        request.physical_address_bits,
    )?;
    for guard in [STACK_GUARD_LOW_PAGE, STACK_GUARD_HIGH_PAGE] {
        if translate(
            reader,
            root,
            request.virtual_base + guard as u64 * PAGE_SIZE,
            request.physical_address_bits,
        ) != Err(Error::TranslationMissing)
        {
            return Err(Error::GuardPage);
        }
    }
    Ok(())
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct FramebufferSnapshot {
    pub first: Translation,
    pub last: Translation,
}

pub fn snapshot_framebuffer<R: TableReader>(
    reader: &R,
    root: u64,
    physical_base: u64,
    byte_count: usize,
    physical_address_bits: u8,
) -> Result<FramebufferSnapshot, Error> {
    if physical_base == 0 || byte_count == 0 {
        return Err(Error::FramebufferRange);
    }
    let last = physical_base
        .checked_add(byte_count as u64 - 1)
        .ok_or(Error::FramebufferRange)?;
    if !is_canonical_48(physical_base) || !is_canonical_48(last) {
        return Err(Error::FramebufferRange);
    }
    let snapshot = FramebufferSnapshot {
        first: translate(reader, root, physical_base, physical_address_bits)?,
        last: translate(reader, root, last, physical_address_bits)?,
    };
    if snapshot.first.physical_address != physical_base || snapshot.last.physical_address != last {
        return Err(Error::FramebufferRange);
    }
    Ok(snapshot)
}

pub fn verify_framebuffer_preserved(
    original: FramebufferSnapshot,
    candidate: FramebufferSnapshot,
) -> Result<(), Error> {
    if original != candidate {
        return Err(Error::FramebufferDrift);
    }
    Ok(())
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum LifecycleState {
    Prepared,
    CandidateActive,
    Restored,
    Retained,
    Released,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct Lifecycle {
    original_cr3: u64,
    candidate_cr3: u64,
    state: LifecycleState,
}

impl Lifecycle {
    pub const fn new(original_cr3: u64, candidate_cr3: u64) -> Self {
        Self {
            original_cr3,
            candidate_cr3,
            state: LifecycleState::Prepared,
        }
    }

    pub const fn state(self) -> LifecycleState {
        self.state
    }

    pub fn observe_activation(&mut self, observed_cr3: u64) -> Result<(), Error> {
        if self.state != LifecycleState::Prepared || observed_cr3 != self.candidate_cr3 {
            return Err(Error::ActivationMismatch);
        }
        self.state = LifecycleState::CandidateActive;
        Ok(())
    }

    pub fn observe_rollback(&mut self, observed_cr3: u64) -> Result<(), Error> {
        if self.state != LifecycleState::CandidateActive || observed_cr3 != self.original_cr3 {
            return Err(Error::RollbackMismatch);
        }
        self.state = LifecycleState::Restored;
        Ok(())
    }

    pub const fn firmware_call_allowed(self) -> bool {
        matches!(
            self.state,
            LifecycleState::Prepared
                | LifecycleState::Restored
                | LifecycleState::Retained
                | LifecycleState::Released
        )
    }

    pub fn observe_retention(&mut self) -> Result<(), Error> {
        if self.state != LifecycleState::Restored {
            return Err(Error::RetentionOrder);
        }
        self.state = LifecycleState::Retained;
        Ok(())
    }

    pub fn observe_release(&mut self) -> Result<(), Error> {
        if !matches!(
            self.state,
            LifecycleState::Restored | LifecycleState::Retained
        ) {
            return Err(Error::ReleaseOrder);
        }
        self.state = LifecycleState::Released;
        Ok(())
    }
}

#[cfg(test)]
extern crate std;

#[cfg(test)]
mod tests {
    use super::*;
    use std::collections::BTreeMap;

    const PHYSICAL: u64 = 0x0200_0000;
    const VIRTUAL: u64 = MIN_VIRTUAL_BASE;
    const TABLE_BASE: u64 = 0x0300_0000;
    const ORIGINAL_ROOT: u64 = 0x0010_0000;

    fn profile() -> CpuProfile {
        CpuProfile {
            paging: true,
            pae: true,
            long_mode: true,
            write_protect: true,
            nx_supported: true,
            nx_enabled: true,
            five_level_paging: false,
            pcid_enabled: false,
            physical_address_bits: 48,
        }
    }

    fn request() -> Request {
        let mut mappings = [Mapping::EMPTY; MAX_MAPPINGS];
        mappings[0] = Mapping {
            virtual_offset: 0,
            byte_count: 0x8000,
            permissions: Permissions::READ,
        };
        mappings[1] = Mapping {
            virtual_offset: 0x8000,
            byte_count: 0x20000,
            permissions: Permissions::READ_EXECUTE,
        };
        mappings[2] = Mapping {
            virtual_offset: 0x28000,
            byte_count: 0x4000,
            permissions: Permissions::READ,
        };
        mappings[3] = Mapping {
            virtual_offset: 0x2c000,
            byte_count: 0x14000,
            permissions: Permissions::READ_WRITE,
        };
        Request {
            physical_base: PHYSICAL,
            virtual_base: VIRTUAL,
            image_bytes: 0x40000,
            page_count: 64,
            entry_virtual: VIRTUAL + 0x8000,
            mapping_count: 4,
            mappings,
            physical_address_bits: 48,
        }
    }

    fn addresses() -> TableAddresses {
        TableAddresses::contiguous(ORIGINAL_ROOT, TABLE_BASE).unwrap()
    }

    fn retained() -> RetainedRequest {
        RetainedRequest {
            stack_physical_base: 0x0400_0000,
            stack_page_count: STACK_PAGE_COUNT as u32,
            handoff_physical_base: 0x0500_0000,
            handoff_capacity_bytes: HANDOFF_CAPACITY_BYTES as u32,
        }
    }

    #[test]
    fn validates_required_cpu_profile() {
        assert_eq!(validate_cpu(profile()), Ok(()));
        let mut value = profile();
        value.nx_supported = false;
        assert_eq!(validate_cpu(value), Err(Error::NxUnsupported));
        let mut value = profile();
        value.nx_enabled = false;
        assert_eq!(validate_cpu(value), Err(Error::NxDisabled));
        let mut value = profile();
        value.write_protect = false;
        assert_eq!(validate_cpu(value), Err(Error::WriteProtectDisabled));
        let mut value = profile();
        value.five_level_paging = true;
        assert_eq!(validate_cpu(value), Err(Error::FiveLevelPaging));
        let mut value = profile();
        value.pcid_enabled = true;
        assert_eq!(validate_cpu(value), Err(Error::PcidEnabled));
    }

    #[test]
    fn builds_exact_wx_safe_product_window() {
        let original = [0u64; TABLE_ENTRIES];
        let mut root = [0u64; TABLE_ENTRIES];
        let mut pdpt = [0u64; TABLE_ENTRIES];
        let mut directory = [0u64; TABLE_ENTRIES];
        let mut table = [0u64; TABLE_ENTRIES];
        let summary = populate(
            &request(),
            addresses(),
            &original,
            &mut root,
            &mut pdpt,
            &mut directory,
            &mut table,
        )
        .unwrap();
        assert_eq!(summary.pml4_index, 511);
        assert_eq!(summary.pdpt_index, 510);
        assert_eq!(summary.page_directory_index, 0);
        assert_eq!(summary.first_page_table_index, 0);
        assert_eq!(summary.mapped_page_count, 64);
        assert_eq!(summary.read_only_page_count, 12);
        assert_eq!(summary.read_execute_page_count, 32);
        assert_eq!(summary.read_write_page_count, 20);
        assert_eq!(summary.writable_executable_page_count, 0);
        assert_eq!(root[511], addresses().pdpt | PARENT_FLAGS);
        assert_eq!(table[0], PHYSICAL | ENTRY_PRESENT | ENTRY_NO_EXECUTE);
        assert_eq!(table[8], (PHYSICAL + 8 * PAGE_SIZE) | ENTRY_PRESENT);
        assert_eq!(
            table[63],
            (PHYSICAL + 63 * PAGE_SIZE) | ENTRY_PRESENT | ENTRY_WRITABLE | ENTRY_NO_EXECUTE
        );
    }

    #[test]
    fn builds_retained_stack_guards_and_read_only_handoff() {
        let original = [0u64; TABLE_ENTRIES];
        let mut root = [0u64; TABLE_ENTRIES];
        let mut pdpt = [0u64; TABLE_ENTRIES];
        let mut directory = [0u64; TABLE_ENTRIES];
        let mut table = [0u64; TABLE_ENTRIES];
        let summary = populate_retained(
            &request(),
            retained(),
            addresses(),
            &original,
            &mut root,
            &mut pdpt,
            &mut directory,
            &mut table,
        )
        .unwrap();
        assert_eq!(summary.stack_page_count, STACK_PAGE_COUNT as u32);
        assert_eq!(summary.handoff_page_count, HANDOFF_PAGE_COUNT as u32);
        assert_eq!(summary.guard_page_count, 2);
        assert_eq!(summary.total_mapped_page_count, 334);
        assert_eq!(table[STACK_GUARD_LOW_PAGE], 0);
        assert_eq!(table[STACK_GUARD_HIGH_PAGE], 0);
        assert_eq!(
            table[STACK_FIRST_PAGE],
            retained().stack_physical_base | ENTRY_PRESENT | ENTRY_WRITABLE | ENTRY_NO_EXECUTE
        );
        assert_eq!(
            table[HANDOFF_FIRST_PAGE],
            retained().handoff_physical_base | ENTRY_PRESENT | ENTRY_NO_EXECUTE
        );
    }

    #[test]
    fn retained_layout_rejects_overlap_and_guard_mutation() {
        let mut overlap = retained();
        overlap.stack_physical_base = PHYSICAL;
        assert_eq!(
            retained_summary(&request(), addresses(), overlap),
            Err(Error::RetainedOverlap)
        );

        let original = [0u64; TABLE_ENTRIES];
        let mut root = [0u64; TABLE_ENTRIES];
        let mut pdpt = [0u64; TABLE_ENTRIES];
        let mut directory = [0u64; TABLE_ENTRIES];
        let mut table = [0u64; TABLE_ENTRIES];
        populate_retained(
            &request(),
            retained(),
            addresses(),
            &original,
            &mut root,
            &mut pdpt,
            &mut directory,
            &mut table,
        )
        .unwrap();
        table[STACK_GUARD_LOW_PAGE] = 0x0700_0000 | ENTRY_PRESENT | ENTRY_NO_EXECUTE;
        assert_eq!(
            verify_retained(
                &request(),
                retained(),
                addresses(),
                &original,
                &root,
                &pdpt,
                &directory,
                &table,
            ),
            Err(Error::GuardPage)
        );
    }

    #[test]
    fn rejects_occupied_root_slot() {
        let mut original = [0u64; TABLE_ENTRIES];
        original[511] = 0x4000 | PARENT_FLAGS;
        let mut root = [0u64; TABLE_ENTRIES];
        let mut pdpt = [0u64; TABLE_ENTRIES];
        let mut directory = [0u64; TABLE_ENTRIES];
        let mut table = [0u64; TABLE_ENTRIES];
        assert_eq!(
            populate(
                &request(),
                addresses(),
                &original,
                &mut root,
                &mut pdpt,
                &mut directory,
                &mut table,
            ),
            Err(Error::RootSlotOccupied)
        );
    }

    #[test]
    fn rejects_alignment_coverage_wx_and_entry_errors() {
        let mut value = request();
        value.mappings[1].virtual_offset += 1;
        assert_eq!(
            request_summary(&value, addresses()),
            Err(Error::MappingAlignment)
        );
        let mut value = request();
        value.mappings[1].virtual_offset += 0x1000;
        assert_eq!(
            request_summary(&value, addresses()),
            Err(Error::MappingCoverage)
        );
        let mut value = request();
        value.mappings[3].permissions.execute = true;
        assert_eq!(
            request_summary(&value, addresses()),
            Err(Error::WritableExecutable)
        );
        let mut value = request();
        value.entry_virtual = VIRTUAL + 0x28000;
        assert_eq!(request_summary(&value, addresses()), Err(Error::EntryPoint));
    }

    #[test]
    fn rejects_wrong_ranges_and_table_overlap() {
        let mut value = request();
        value.physical_base += 1;
        assert_eq!(
            request_summary(&value, addresses()),
            Err(Error::PhysicalAddress)
        );
        let mut value = request();
        value.virtual_base += PAGE_SIZE;
        assert_eq!(
            request_summary(&value, addresses()),
            Err(Error::VirtualAddress)
        );
        let overlapping = TableAddresses::contiguous(ORIGINAL_ROOT, PHYSICAL).unwrap();
        assert_eq!(
            request_summary(&request(), overlapping),
            Err(Error::TableOverlap)
        );
    }

    #[test]
    fn verifier_detects_leaf_and_parent_corruption() {
        let original = [0u64; TABLE_ENTRIES];
        let mut root = [0u64; TABLE_ENTRIES];
        let mut pdpt = [0u64; TABLE_ENTRIES];
        let mut directory = [0u64; TABLE_ENTRIES];
        let mut table = [0u64; TABLE_ENTRIES];
        populate(
            &request(),
            addresses(),
            &original,
            &mut root,
            &mut pdpt,
            &mut directory,
            &mut table,
        )
        .unwrap();
        table[1] |= ENTRY_WRITABLE;
        assert_eq!(
            verify(
                &request(),
                addresses(),
                &original,
                &root,
                &pdpt,
                &directory,
                &table,
            ),
            Err(Error::LeafEntry)
        );
        table[1] &= !ENTRY_WRITABLE;
        directory[0] |= ENTRY_PAGE_SIZE_OR_PAT;
        assert_eq!(
            verify(
                &request(),
                addresses(),
                &original,
                &root,
                &pdpt,
                &directory,
                &table,
            ),
            Err(Error::ParentEntry)
        );
    }

    struct Reader {
        tables: BTreeMap<u64, [u64; TABLE_ENTRIES]>,
    }

    impl TableReader for Reader {
        fn read_entry(&self, table_address: u64, index: usize) -> Result<u64, Error> {
            self.tables
                .get(&table_address)
                .map(|table| table[index])
                .ok_or(Error::TranslationAddress)
        }
    }

    fn candidate_reader() -> (Reader, Summary) {
        let original = [0u64; TABLE_ENTRIES];
        let mut root = [0u64; TABLE_ENTRIES];
        let mut pdpt = [0u64; TABLE_ENTRIES];
        let mut directory = [0u64; TABLE_ENTRIES];
        let mut table = [0u64; TABLE_ENTRIES];
        let summary = populate(
            &request(),
            addresses(),
            &original,
            &mut root,
            &mut pdpt,
            &mut directory,
            &mut table,
        )
        .unwrap();
        let mut tables = BTreeMap::new();
        tables.insert(addresses().candidate_root, root);
        tables.insert(addresses().pdpt, pdpt);
        tables.insert(addresses().page_directory, directory);
        tables.insert(addresses().page_table, table);
        (Reader { tables }, summary)
    }

    fn retained_reader() -> (Reader, RetainedSummary) {
        let original = [0u64; TABLE_ENTRIES];
        let mut root = [0u64; TABLE_ENTRIES];
        let mut pdpt = [0u64; TABLE_ENTRIES];
        let mut directory = [0u64; TABLE_ENTRIES];
        let mut table = [0u64; TABLE_ENTRIES];
        let summary = populate_retained(
            &request(),
            retained(),
            addresses(),
            &original,
            &mut root,
            &mut pdpt,
            &mut directory,
            &mut table,
        )
        .unwrap();
        let mut tables = BTreeMap::new();
        tables.insert(addresses().candidate_root, root);
        tables.insert(addresses().pdpt, pdpt);
        tables.insert(addresses().page_directory, directory);
        tables.insert(addresses().page_table, table);
        (Reader { tables }, summary)
    }

    #[test]
    fn independently_walks_every_kernel_leaf() {
        let (reader, expected) = candidate_reader();
        let observed =
            verify_kernel_translations(&reader, addresses().candidate_root, &request()).unwrap();
        assert_eq!(observed, expected);
        let text = translate(
            &reader,
            addresses().candidate_root,
            VIRTUAL + 8 * PAGE_SIZE,
            48,
        )
        .unwrap();
        assert_eq!(text.physical_address, PHYSICAL + 8 * PAGE_SIZE);
        assert!(text.executable);
        assert!(!text.writable);
        assert!(!text.user);
    }

    #[test]
    fn independently_walks_retained_ranges_and_guards() {
        let (reader, expected) = retained_reader();
        verify_retained_translations(
            &reader,
            addresses().candidate_root,
            &request(),
            retained(),
            expected,
        )
        .unwrap();
        let stack = translate(
            &reader,
            addresses().candidate_root,
            expected.stack_bottom_virtual,
            48,
        )
        .unwrap();
        assert!(stack.writable);
        assert!(!stack.executable);
        let handoff = translate(
            &reader,
            addresses().candidate_root,
            expected.handoff_virtual_base,
            48,
        )
        .unwrap();
        assert!(!handoff.writable);
        assert!(!handoff.executable);
    }

    #[test]
    fn detects_large_page_collision() {
        let (mut reader, _) = candidate_reader();
        reader.tables.get_mut(&addresses().page_directory).unwrap()[0] =
            PHYSICAL | PARENT_FLAGS | ENTRY_PAGE_SIZE_OR_PAT;
        assert_eq!(
            verify_kernel_translations(&reader, addresses().candidate_root, &request()),
            Err(Error::LargePageCollision)
        );
    }

    #[test]
    fn snapshots_and_compares_framebuffer_cache_policy() {
        let root = 0x1000;
        let pdpt = 0x2000;
        let directory = 0x3000;
        let framebuffer = 0x8000_0000;
        let mut root_table = [0u64; TABLE_ENTRIES];
        let mut pdpt_table = [0u64; TABLE_ENTRIES];
        let mut directory_table = [0u64; TABLE_ENTRIES];
        root_table[0] = pdpt | PARENT_FLAGS;
        pdpt_table[2] = directory | PARENT_FLAGS;
        directory_table[0] = framebuffer
            | ENTRY_PRESENT
            | ENTRY_WRITABLE
            | ENTRY_PAGE_SIZE_OR_PAT
            | ENTRY_PCD
            | ENTRY_LARGE_PAT
            | ENTRY_NO_EXECUTE;
        let mut tables = BTreeMap::new();
        tables.insert(root, root_table);
        tables.insert(pdpt, pdpt_table);
        tables.insert(directory, directory_table);
        let reader = Reader { tables };
        let first = snapshot_framebuffer(&reader, root, framebuffer, 0x1000, 48).unwrap();
        assert_eq!(first.first.page_size, WINDOW_BYTES);
        assert!(first.first.cache.pcd);
        assert!(first.first.cache.pat);
        assert_eq!(verify_framebuffer_preserved(first, first), Ok(()));
        let mut changed = first;
        changed.last.cache.pat = false;
        assert_eq!(
            verify_framebuffer_preserved(first, changed),
            Err(Error::FramebufferDrift)
        );
    }

    #[test]
    fn lifecycle_forbids_release_before_verified_rollback() {
        let mut lifecycle = Lifecycle::new(0x1000, 0x2000);
        assert!(lifecycle.firmware_call_allowed());
        assert_eq!(
            lifecycle.observe_activation(0x3000),
            Err(Error::ActivationMismatch)
        );
        lifecycle.observe_activation(0x2000).unwrap();
        assert!(!lifecycle.firmware_call_allowed());
        assert_eq!(lifecycle.observe_release(), Err(Error::ReleaseOrder));
        assert_eq!(
            lifecycle.observe_rollback(0x3000),
            Err(Error::RollbackMismatch)
        );
        lifecycle.observe_rollback(0x1000).unwrap();
        assert!(lifecycle.firmware_call_allowed());
        lifecycle.observe_release().unwrap();
        assert_eq!(lifecycle.state(), LifecycleState::Released);
    }

    #[test]
    fn lifecycle_retains_only_after_verified_rollback() {
        let mut lifecycle = Lifecycle::new(0x1000, 0x2000);
        assert_eq!(lifecycle.observe_retention(), Err(Error::RetentionOrder));
        lifecycle.observe_activation(0x2000).unwrap();
        lifecycle.observe_rollback(0x1000).unwrap();
        lifecycle.observe_retention().unwrap();
        assert_eq!(lifecycle.state(), LifecycleState::Retained);
        assert!(lifecycle.firmware_call_allowed());
        lifecycle.observe_release().unwrap();
        assert_eq!(lifecycle.state(), LifecycleState::Released);
    }
}
