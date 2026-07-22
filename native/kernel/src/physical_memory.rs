use poole_handoff::{
    CoreRecord, Handoff, MEMORY_BOOT_RECLAIMABLE, MEMORY_ENTRY_BYTES, MEMORY_LOADER_RESERVED,
    MEMORY_USABLE, PAGE_BYTES, RECORD_MEMORY_MAP,
};

pub const CONTRACT_ID: &str = "PKPMM1";
pub const MAX_MEMORY_ENTRIES: usize = 256;
pub const MAX_FREE_EXTENTS: usize = 256;
pub const MAX_ALLOCATIONS: usize = 32;
pub const MEMORY_KIND_COUNT: usize = 12;
pub const DEFAULT_QUOTA_PAGES: u64 = 64;
pub const DMA_END_PAGE: u64 = 16 * 1024 * 1024 / PAGE_BYTES;
pub const DMA32_END_PAGE: u64 = 4 * 1024 * 1024 * 1024 / PAGE_BYTES;

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
#[repr(u8)]
pub enum Zone {
    Dma = 0,
    Dma32 = 1,
    Normal = 2,
}

impl Zone {
    pub const fn label(self) -> &'static str {
        match self {
            Self::Dma => "dma",
            Self::Dma32 => "dma32",
            Self::Normal => "normal",
        }
    }

    const fn index(self) -> usize {
        self as usize
    }
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct AllocationHandle {
    slot: u8,
    pub generation: u64,
    pub start_page: u64,
    pub page_count: u64,
    pub zone: Zone,
    pub owner: u16,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum PhysicalMemoryError {
    MissingMap,
    EntryCount,
    EntryShape,
    EntryValue,
    EntryOrder,
    AddressRange,
    SourceKind,
    ExtentCapacity,
    AllocationCapacity,
    Quota,
    Unavailable,
    ZeroAllocation,
    InvalidOwner,
    StaleHandle,
    CoreOwnership,
    ExerciseInvariant,
}

impl PhysicalMemoryError {
    pub const fn label(self) -> &'static str {
        match self {
            Self::MissingMap => "missing_map",
            Self::EntryCount => "entry_count",
            Self::EntryShape => "entry_shape",
            Self::EntryValue => "entry_value",
            Self::EntryOrder => "entry_order",
            Self::AddressRange => "address_range",
            Self::SourceKind => "source_kind",
            Self::ExtentCapacity => "extent_capacity",
            Self::AllocationCapacity => "allocation_capacity",
            Self::Quota => "quota",
            Self::Unavailable => "unavailable",
            Self::ZeroAllocation => "zero_allocation",
            Self::InvalidOwner => "invalid_owner",
            Self::StaleHandle => "stale_handle",
            Self::CoreOwnership => "core_ownership",
            Self::ExerciseInvariant => "exercise_invariant",
        }
    }
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
struct Extent {
    start_page: u64,
    page_count: u64,
    zone: Zone,
}

const EMPTY_EXTENT: Extent = Extent {
    start_page: 0,
    page_count: 0,
    zone: Zone::Dma,
};

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
struct Allocation {
    active: bool,
    generation: u64,
    start_page: u64,
    page_count: u64,
    zone: Zone,
    owner: u16,
    metadata_poisoned: bool,
}

const EMPTY_ALLOCATION: Allocation = Allocation {
    active: false,
    generation: 0,
    start_page: 0,
    page_count: 0,
    zone: Zone::Dma,
    owner: 0,
    metadata_poisoned: false,
};

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct PhysicalMemorySummary {
    pub memory_entry_count: usize,
    pub source_pages: [u64; MEMORY_KIND_COUNT],
    pub source_usable_pages: [u64; 3],
    pub managed_pages: [u64; 3],
    pub null_guard_pages: u64,
    pub free_extent_count: usize,
    pub largest_free_pages: [u64; 3],
    pub allocated_pages: u64,
    pub allocation_count: u64,
    pub free_count: u64,
    pub rejected_double_frees: u64,
    pub rejected_quota_requests: u64,
    pub rejected_unavailable_requests: u64,
    pub metadata_poison_events: u64,
    pub coalesce_events: u64,
}

pub struct PhysicalMemoryManager {
    free: [Extent; MAX_FREE_EXTENTS],
    free_count: usize,
    allocations: [Allocation; MAX_ALLOCATIONS],
    memory_entry_count: usize,
    source_pages: [u64; MEMORY_KIND_COUNT],
    source_usable_pages: [u64; 3],
    managed_pages: [u64; 3],
    null_guard_pages: u64,
    quota_pages: u64,
    allocated_pages: u64,
    next_generation: u64,
    allocation_count: u64,
    free_operation_count: u64,
    rejected_double_frees: u64,
    rejected_quota_requests: u64,
    rejected_unavailable_requests: u64,
    metadata_poison_events: u64,
    coalesce_events: u64,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct PhysicalMemoryProof {
    pub initial: PhysicalMemorySummary,
    pub final_state: PhysicalMemorySummary,
    pub dma_start_page: u64,
    pub dma32_start_page: u64,
}

#[inline(never)]
pub fn run_profile(
    handoff: &Handoff<'_>,
    core: CoreRecord,
) -> Result<PhysicalMemoryProof, PhysicalMemoryError> {
    let mut manager = PhysicalMemoryManager::from_handoff(handoff, core, DEFAULT_QUOTA_PAGES)?;
    let initial = manager.summary();
    let dma = manager.allocate(Zone::Dma, 3, 1)?;
    let dma32 = manager.allocate(Zone::Dma32, 8, 2)?;
    let quota_rejected = manager
        .allocate(Zone::Dma32, DEFAULT_QUOTA_PAGES, 3)
        .is_err();
    let unavailable_rejected = manager.allocate(Zone::Normal, 1, 3).is_err();
    manager.free(dma)?;
    let double_free_rejected = manager.free(dma).is_err();
    manager.free(dma32)?;
    let final_state = manager.summary();
    if !quota_rejected
        || !unavailable_rejected
        || !double_free_rejected
        || final_state.allocated_pages != 0
        || final_state.free_extent_count != initial.free_extent_count
        || final_state.largest_free_pages != initial.largest_free_pages
    {
        return Err(PhysicalMemoryError::ExerciseInvariant);
    }
    Ok(PhysicalMemoryProof {
        initial,
        final_state,
        dma_start_page: dma.start_page,
        dma32_start_page: dma32.start_page,
    })
}

fn read_u32(bytes: &[u8], offset: usize) -> Result<u32, PhysicalMemoryError> {
    let value = bytes
        .get(offset..offset + 4)
        .ok_or(PhysicalMemoryError::EntryShape)?;
    Ok(u32::from_le_bytes([value[0], value[1], value[2], value[3]]))
}

fn read_u64(bytes: &[u8], offset: usize) -> Result<u64, PhysicalMemoryError> {
    let value = bytes
        .get(offset..offset + 8)
        .ok_or(PhysicalMemoryError::EntryShape)?;
    Ok(u64::from_le_bytes([
        value[0], value[1], value[2], value[3], value[4], value[5], value[6], value[7],
    ]))
}

const fn source_matches_kind(source: u32, kind: u32) -> bool {
    matches!(
        (source, kind),
        (0 | 13 | 15, 0)
            | (1 | 2, MEMORY_LOADER_RESERVED)
            | (3 | 4, MEMORY_BOOT_RECLAIMABLE)
            | (5, 3)
            | (6, 4)
            | (7, MEMORY_USABLE)
            | (8, 9)
            | (9, 5)
            | (10, 6)
            | (11 | 12, 7)
            | (14, 8)
    )
}

const fn zone_for_page(page: u64) -> Zone {
    if page < DMA_END_PAGE {
        Zone::Dma
    } else if page < DMA32_END_PAGE {
        Zone::Dma32
    } else {
        Zone::Normal
    }
}

const fn zone_end_page(zone: Zone) -> u64 {
    match zone {
        Zone::Dma => DMA_END_PAGE,
        Zone::Dma32 => DMA32_END_PAGE,
        Zone::Normal => u64::MAX,
    }
}

impl PhysicalMemoryManager {
    fn empty(quota_pages: u64) -> Self {
        Self {
            free: [EMPTY_EXTENT; MAX_FREE_EXTENTS],
            free_count: 0,
            allocations: [EMPTY_ALLOCATION; MAX_ALLOCATIONS],
            memory_entry_count: 0,
            source_pages: [0; MEMORY_KIND_COUNT],
            source_usable_pages: [0; 3],
            managed_pages: [0; 3],
            null_guard_pages: 0,
            quota_pages,
            allocated_pages: 0,
            next_generation: 1,
            allocation_count: 0,
            free_operation_count: 0,
            rejected_double_frees: 0,
            rejected_quota_requests: 0,
            rejected_unavailable_requests: 0,
            metadata_poison_events: 0,
            coalesce_events: 0,
        }
    }

    pub fn from_handoff(
        handoff: &Handoff<'_>,
        core: CoreRecord,
        quota_pages: u64,
    ) -> Result<Self, PhysicalMemoryError> {
        let record = handoff
            .record(RECORD_MEMORY_MAP)
            .ok_or(PhysicalMemoryError::MissingMap)?;
        let count = record.descriptor.element_count;
        if count == 0 || count > MAX_MEMORY_ENTRIES {
            return Err(PhysicalMemoryError::EntryCount);
        }
        if record.descriptor.element_size != MEMORY_ENTRY_BYTES
            || record.payload.len() != count * MEMORY_ENTRY_BYTES
        {
            return Err(PhysicalMemoryError::EntryShape);
        }
        let mut manager = Self::empty(quota_pages);
        manager.memory_entry_count = count;
        let mut previous_end = 0u64;
        for index in 0..count {
            let base = index * MEMORY_ENTRY_BYTES;
            let start = read_u64(record.payload, base)?;
            let pages = read_u64(record.payload, base + 8)?;
            let kind = read_u32(record.payload, base + 24)?;
            let source = read_u32(record.payload, base + 28)?;
            let reserved = read_u64(record.payload, base + 32)?;
            if !start.is_multiple_of(PAGE_BYTES) || pages == 0 || kind as usize >= MEMORY_KIND_COUNT
            {
                return Err(PhysicalMemoryError::EntryValue);
            }
            if reserved != 0 || !source_matches_kind(source, kind) {
                return Err(PhysicalMemoryError::SourceKind);
            }
            let bytes = pages
                .checked_mul(PAGE_BYTES)
                .ok_or(PhysicalMemoryError::AddressRange)?;
            let end = start
                .checked_add(bytes)
                .ok_or(PhysicalMemoryError::AddressRange)?;
            if index != 0 && start < previous_end {
                return Err(PhysicalMemoryError::EntryOrder);
            }
            previous_end = end;
            manager.source_pages[kind as usize] = manager.source_pages[kind as usize]
                .checked_add(pages)
                .ok_or(PhysicalMemoryError::AddressRange)?;
            if kind == MEMORY_USABLE {
                manager.append_usable(start / PAGE_BYTES, pages)?;
            }
        }
        manager.audit_core_ownership(record.payload, core)?;
        Ok(manager)
    }

    fn append_usable(
        &mut self,
        mut start_page: u64,
        mut pages: u64,
    ) -> Result<(), PhysicalMemoryError> {
        while pages != 0 {
            let zone = zone_for_page(start_page);
            let zone_end = zone_end_page(zone);
            let available = zone_end.saturating_sub(start_page);
            let take = pages.min(available);
            if take == 0 {
                return Err(PhysicalMemoryError::AddressRange);
            }
            self.source_usable_pages[zone.index()] = self.source_usable_pages[zone.index()]
                .checked_add(take)
                .ok_or(PhysicalMemoryError::AddressRange)?;
            let mut managed_start = start_page;
            let mut managed_pages = take;
            if managed_start == 0 {
                managed_start = 1;
                managed_pages -= 1;
                self.null_guard_pages = 1;
            }
            if managed_pages != 0 {
                self.append_free_extent(Extent {
                    start_page: managed_start,
                    page_count: managed_pages,
                    zone,
                })?;
                self.managed_pages[zone.index()] = self.managed_pages[zone.index()]
                    .checked_add(managed_pages)
                    .ok_or(PhysicalMemoryError::AddressRange)?;
            }
            start_page = start_page
                .checked_add(take)
                .ok_or(PhysicalMemoryError::AddressRange)?;
            pages -= take;
        }
        Ok(())
    }

    fn append_free_extent(&mut self, extent: Extent) -> Result<(), PhysicalMemoryError> {
        if self.free_count != 0 {
            let previous = &mut self.free[self.free_count - 1];
            if previous.zone == extent.zone
                && previous.start_page.checked_add(previous.page_count) == Some(extent.start_page)
            {
                previous.page_count = previous
                    .page_count
                    .checked_add(extent.page_count)
                    .ok_or(PhysicalMemoryError::AddressRange)?;
                return Ok(());
            }
        }
        if self.free_count == MAX_FREE_EXTENTS {
            return Err(PhysicalMemoryError::ExtentCapacity);
        }
        self.free[self.free_count] = extent;
        self.free_count += 1;
        Ok(())
    }

    fn audit_core_ownership(
        &self,
        payload: &[u8],
        core: CoreRecord,
    ) -> Result<(), PhysicalMemoryError> {
        if !range_has_kind(
            payload,
            core.kernel_physical_base,
            core.kernel_physical_size,
            MEMORY_LOADER_RESERVED,
        )? || !range_has_kind(
            payload,
            core.handoff_physical_base,
            core.handoff_byte_count,
            MEMORY_LOADER_RESERVED,
        )? || !range_has_kind(
            payload,
            core.page_table_root_physical,
            PAGE_BYTES,
            MEMORY_LOADER_RESERVED,
        )? {
            return Err(PhysicalMemoryError::CoreOwnership);
        }
        Ok(())
    }

    pub fn allocate(
        &mut self,
        zone: Zone,
        pages: u64,
        owner: u16,
    ) -> Result<AllocationHandle, PhysicalMemoryError> {
        if pages == 0 {
            return Err(PhysicalMemoryError::ZeroAllocation);
        }
        if owner == 0 {
            return Err(PhysicalMemoryError::InvalidOwner);
        }
        if self.allocated_pages.checked_add(pages).is_none()
            || self.allocated_pages + pages > self.quota_pages
        {
            self.rejected_quota_requests += 1;
            return Err(PhysicalMemoryError::Quota);
        }
        let slot = self
            .allocations
            .iter()
            .position(|item| !item.active)
            .ok_or(PhysicalMemoryError::AllocationCapacity)?;
        let extent_index = match self.free[..self.free_count]
            .iter()
            .position(|item| item.zone == zone && item.page_count >= pages)
        {
            Some(value) => value,
            None => {
                self.rejected_unavailable_requests += 1;
                return Err(PhysicalMemoryError::Unavailable);
            }
        };
        let start_page = self.free[extent_index].start_page;
        self.free[extent_index].start_page += pages;
        self.free[extent_index].page_count -= pages;
        if self.free[extent_index].page_count == 0 {
            self.remove_free_extent(extent_index);
        }
        let generation = self.next_generation;
        self.next_generation = self
            .next_generation
            .checked_add(1)
            .ok_or(PhysicalMemoryError::AddressRange)?;
        self.allocations[slot] = Allocation {
            active: true,
            generation,
            start_page,
            page_count: pages,
            zone,
            owner,
            metadata_poisoned: false,
        };
        self.allocated_pages += pages;
        self.allocation_count += 1;
        Ok(AllocationHandle {
            slot: slot as u8,
            generation,
            start_page,
            page_count: pages,
            zone,
            owner,
        })
    }

    pub fn free(&mut self, handle: AllocationHandle) -> Result<(), PhysicalMemoryError> {
        let slot = usize::from(handle.slot);
        let allocation = self
            .allocations
            .get(slot)
            .copied()
            .ok_or(PhysicalMemoryError::StaleHandle)?;
        if !allocation.active
            || allocation.generation != handle.generation
            || allocation.start_page != handle.start_page
            || allocation.page_count != handle.page_count
            || allocation.zone != handle.zone
            || allocation.owner != handle.owner
        {
            self.rejected_double_frees += 1;
            return Err(PhysicalMemoryError::StaleHandle);
        }
        self.insert_and_coalesce(Extent {
            start_page: allocation.start_page,
            page_count: allocation.page_count,
            zone: allocation.zone,
        })?;
        self.allocations[slot].active = false;
        self.allocations[slot].metadata_poisoned = true;
        self.allocated_pages -= allocation.page_count;
        self.free_operation_count += 1;
        self.metadata_poison_events += 1;
        Ok(())
    }

    fn remove_free_extent(&mut self, index: usize) {
        for item in index..self.free_count - 1 {
            self.free[item] = self.free[item + 1];
        }
        self.free_count -= 1;
        self.free[self.free_count] = EMPTY_EXTENT;
    }

    fn insert_and_coalesce(&mut self, extent: Extent) -> Result<(), PhysicalMemoryError> {
        let mut index = 0;
        while index < self.free_count && self.free[index].start_page < extent.start_page {
            index += 1;
        }
        let merge_previous = index > 0 && can_coalesce(self.free[index - 1], extent);
        let merge_next = index < self.free_count && can_coalesce(extent, self.free[index]);
        if merge_previous && merge_next {
            let page_count = self.free[index - 1]
                .page_count
                .checked_add(extent.page_count)
                .and_then(|value| value.checked_add(self.free[index].page_count))
                .ok_or(PhysicalMemoryError::AddressRange)?;
            self.free[index - 1].page_count = page_count;
            self.remove_free_extent(index);
            self.coalesce_events += 2;
            return Ok(());
        }
        if merge_previous {
            self.free[index - 1].page_count = self.free[index - 1]
                .page_count
                .checked_add(extent.page_count)
                .ok_or(PhysicalMemoryError::AddressRange)?;
            self.coalesce_events += 1;
            return Ok(());
        }
        if merge_next {
            self.free[index].start_page = extent.start_page;
            self.free[index].page_count = extent
                .page_count
                .checked_add(self.free[index].page_count)
                .ok_or(PhysicalMemoryError::AddressRange)?;
            self.coalesce_events += 1;
            return Ok(());
        }
        if self.free_count == MAX_FREE_EXTENTS {
            return Err(PhysicalMemoryError::ExtentCapacity);
        }
        for item in (index..self.free_count).rev() {
            self.free[item + 1] = self.free[item];
        }
        self.free[index] = extent;
        self.free_count += 1;
        Ok(())
    }

    pub fn summary(&self) -> PhysicalMemorySummary {
        let mut largest = [0u64; 3];
        for extent in &self.free[..self.free_count] {
            largest[extent.zone.index()] = largest[extent.zone.index()].max(extent.page_count);
        }
        PhysicalMemorySummary {
            memory_entry_count: self.memory_entry_count,
            source_pages: self.source_pages,
            source_usable_pages: self.source_usable_pages,
            managed_pages: self.managed_pages,
            null_guard_pages: self.null_guard_pages,
            free_extent_count: self.free_count,
            largest_free_pages: largest,
            allocated_pages: self.allocated_pages,
            allocation_count: self.allocation_count,
            free_count: self.free_operation_count,
            rejected_double_frees: self.rejected_double_frees,
            rejected_quota_requests: self.rejected_quota_requests,
            rejected_unavailable_requests: self.rejected_unavailable_requests,
            metadata_poison_events: self.metadata_poison_events,
            coalesce_events: self.coalesce_events,
        }
    }
}

fn can_coalesce(first: Extent, second: Extent) -> bool {
    first.zone as u8 == second.zone as u8
        && first.start_page.checked_add(first.page_count) == Some(second.start_page)
}

fn range_has_kind(
    payload: &[u8],
    start: u64,
    bytes: u64,
    expected_kind: u32,
) -> Result<bool, PhysicalMemoryError> {
    if bytes == 0 || !start.is_multiple_of(PAGE_BYTES) {
        return Ok(false);
    }
    let end = start
        .checked_add(bytes)
        .ok_or(PhysicalMemoryError::AddressRange)?;
    let mut covered = start;
    for base in (0..payload.len()).step_by(MEMORY_ENTRY_BYTES) {
        let entry_start = read_u64(payload, base)?;
        let pages = read_u64(payload, base + 8)?;
        let kind = read_u32(payload, base + 24)?;
        let entry_end = entry_start
            .checked_add(
                pages
                    .checked_mul(PAGE_BYTES)
                    .ok_or(PhysicalMemoryError::AddressRange)?,
            )
            .ok_or(PhysicalMemoryError::AddressRange)?;
        if entry_end <= covered || entry_start > covered {
            continue;
        }
        if kind != expected_kind {
            return Ok(false);
        }
        covered = entry_end.min(end);
        if covered == end {
            return Ok(true);
        }
    }
    Ok(false)
}

#[cfg(test)]
mod tests {
    extern crate std;

    use super::*;
    use poole_handoff::{
        BOOT_SERVICES_EXITED, DEVELOPMENT_MODE, Encoder, RECORD_ARRAY, RECORD_CORE,
        RECORD_REQUIRED, encoded_size,
    };
    use std::vec;
    use std::vec::Vec;

    fn put_u32(value: &mut [u8], offset: usize, item: u32) {
        value[offset..offset + 4].copy_from_slice(&item.to_le_bytes());
    }

    fn put_u64(value: &mut [u8], offset: usize, item: u64) {
        value[offset..offset + 8].copy_from_slice(&item.to_le_bytes());
    }

    fn entry(start: u64, pages: u64, kind: u32, source: u32) -> [u8; MEMORY_ENTRY_BYTES] {
        let mut value = [0u8; MEMORY_ENTRY_BYTES];
        put_u64(&mut value, 0, start);
        put_u64(&mut value, 8, pages);
        put_u64(&mut value, 16, 0xf);
        put_u32(&mut value, 24, kind);
        put_u32(&mut value, 28, source);
        value
    }

    fn fixture() -> (Vec<u8>, CoreRecord) {
        let mut core = [0u8; 128];
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
        put_u64(&mut core, 80, 4096);
        put_u32(&mut core, 104, 0);
        put_u32(&mut core, 108, 3);
        put_u32(&mut core, 112, 1);
        put_u32(&mut core, 116, 1);
        put_u32(&mut core, 120, 0x0002_0046);
        let entries = [
            entry(0, 4096, MEMORY_USABLE, 7),
            entry(0x0100_0000, 4096, MEMORY_USABLE, 7),
            entry(0x0200_0000, 96, MEMORY_LOADER_RESERVED, 2),
            entry(0x0206_0000, 32, MEMORY_BOOT_RECLAIMABLE, 4),
            entry(0x1_0000_0000, 128, MEMORY_USABLE, 7),
        ];
        let mut memory = Vec::new();
        for value in entries {
            memory.extend_from_slice(&value);
        }
        let total = encoded_size(2, &[128, memory.len()]).unwrap();
        put_u64(&mut core, 80, total as u64);
        let mut output = vec![0u8; total];
        let mut encoder = Encoder::new(&mut output, 2, 0, 0).unwrap();
        encoder
            .push(RECORD_CORE, 1, RECORD_REQUIRED, 128, 1, &core)
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
        let bytes = encoder.finish().unwrap().to_vec();
        let parsed_core = poole_handoff::decode(&bytes).unwrap().core().unwrap();
        (bytes, parsed_core)
    }

    #[test]
    fn classifies_zones_and_preserves_nonusable_ranges() {
        let (bytes, core) = fixture();
        let handoff = poole_handoff::decode(&bytes).unwrap();
        let manager = PhysicalMemoryManager::from_handoff(&handoff, core, 64).unwrap();
        let summary = manager.summary();
        assert_eq!(summary.source_usable_pages, [4096, 4096, 128]);
        assert_eq!(summary.managed_pages, [4095, 4096, 128]);
        assert_eq!(summary.source_pages[MEMORY_BOOT_RECLAIMABLE as usize], 32);
        assert_eq!(summary.source_pages[MEMORY_LOADER_RESERVED as usize], 96);
        assert_eq!(summary.null_guard_pages, 1);
    }

    #[test]
    fn allocates_frees_coalesces_and_rejects_stale_handles() {
        let (bytes, core) = fixture();
        let handoff = poole_handoff::decode(&bytes).unwrap();
        let mut manager = PhysicalMemoryManager::from_handoff(&handoff, core, 64).unwrap();
        let before = manager.summary();
        let first = manager.allocate(Zone::Dma, 3, 1).unwrap();
        let second = manager.allocate(Zone::Dma32, 8, 2).unwrap();
        assert_eq!(first.start_page, 1);
        assert_eq!(second.start_page, DMA_END_PAGE);
        manager.free(first).unwrap();
        assert_eq!(manager.free(first), Err(PhysicalMemoryError::StaleHandle));
        manager.free(second).unwrap();
        let after = manager.summary();
        assert_eq!(after.allocated_pages, 0);
        assert_eq!(after.free_extent_count, before.free_extent_count);
        assert_eq!(after.metadata_poison_events, 2);
        assert_eq!(after.rejected_double_frees, 1);
        assert_eq!(after.coalesce_events, 2);
    }

    #[test]
    fn fails_closed_on_quota_owner_and_unavailable_zone() {
        let (bytes, core) = fixture();
        let handoff = poole_handoff::decode(&bytes).unwrap();
        let mut manager = PhysicalMemoryManager::from_handoff(&handoff, core, 1000).unwrap();
        assert_eq!(
            manager.allocate(Zone::Dma, 0, 1),
            Err(PhysicalMemoryError::ZeroAllocation)
        );
        assert_eq!(
            manager.allocate(Zone::Dma, 1, 0),
            Err(PhysicalMemoryError::InvalidOwner)
        );
        assert_eq!(
            manager.allocate(Zone::Dma, 1001, 1),
            Err(PhysicalMemoryError::Quota)
        );
        let normal = manager.allocate(Zone::Normal, 1, 1).unwrap();
        assert_eq!(
            manager.allocate(Zone::Normal, 129, 1),
            Err(PhysicalMemoryError::Unavailable)
        );
        manager.free(normal).unwrap();
        assert_eq!(manager.summary().rejected_quota_requests, 1);
        assert_eq!(manager.summary().rejected_unavailable_requests, 1);
    }

    #[test]
    fn full_extent_table_still_accepts_an_adjacent_free() {
        let mut manager = PhysicalMemoryManager::empty(64);
        for index in 0..MAX_FREE_EXTENTS {
            manager.free[index] = Extent {
                start_page: 1 + (index as u64 * 2),
                page_count: 1,
                zone: Zone::Dma,
            };
        }
        manager.free_count = MAX_FREE_EXTENTS;
        manager.allocations[0] = Allocation {
            active: true,
            generation: 1,
            start_page: 512,
            page_count: 1,
            zone: Zone::Dma,
            owner: 7,
            metadata_poisoned: false,
        };
        manager.allocated_pages = 1;
        let handle = AllocationHandle {
            slot: 0,
            generation: 1,
            start_page: 512,
            page_count: 1,
            zone: Zone::Dma,
            owner: 7,
        };

        manager.free(handle).unwrap();

        assert_eq!(manager.free_count, MAX_FREE_EXTENTS);
        assert_eq!(manager.free[MAX_FREE_EXTENTS - 1].page_count, 2);
        assert_eq!(manager.allocated_pages, 0);
        assert!(manager.allocations[0].metadata_poisoned);
    }

    #[test]
    fn failed_extent_reinsertion_preserves_live_allocation() {
        let mut manager = PhysicalMemoryManager::empty(64);
        for index in 0..MAX_FREE_EXTENTS {
            manager.free[index] = Extent {
                start_page: 1 + (index as u64 * 2),
                page_count: 1,
                zone: Zone::Dma,
            };
        }
        manager.free_count = MAX_FREE_EXTENTS;
        manager.allocations[0] = Allocation {
            active: true,
            generation: 1,
            start_page: 700,
            page_count: 1,
            zone: Zone::Dma,
            owner: 7,
            metadata_poisoned: false,
        };
        manager.allocated_pages = 1;
        let handle = AllocationHandle {
            slot: 0,
            generation: 1,
            start_page: 700,
            page_count: 1,
            zone: Zone::Dma,
            owner: 7,
        };

        assert_eq!(
            manager.free(handle),
            Err(PhysicalMemoryError::ExtentCapacity)
        );
        assert!(manager.allocations[0].active);
        assert!(!manager.allocations[0].metadata_poisoned);
        assert_eq!(manager.allocated_pages, 1);
        assert_eq!(manager.free_operation_count, 0);
        assert_eq!(manager.metadata_poison_events, 0);
    }
}
