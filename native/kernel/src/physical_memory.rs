use poole_handoff::{
    CoreRecord, Handoff, MEMORY_ACPI_RECLAIMABLE, MEMORY_BOOT_RECLAIMABLE, MEMORY_ENTRY_BYTES,
    MEMORY_LOADER_RESERVED, MEMORY_USABLE, PAGE_BYTES, RECORD_MEMORY_MAP,
};

pub const CONTRACT_ID: &str = "PKPMM4";
pub const MAX_MEMORY_ENTRIES: usize = 256;
pub const MAX_FREE_EXTENTS: usize = 256;
pub const MAX_ALLOCATIONS: usize = 32;
pub const MAX_SCRUB_RECEIPTS: usize = 16;
pub const MAX_RECLAIM_RECEIPTS: usize = 2;
pub const MAX_RECLAIM_EXTENTS: usize = MAX_MEMORY_ENTRIES + 2;
pub const MEMORY_KIND_COUNT: usize = 12;
pub const DEFAULT_QUOTA_PAGES: u64 = 64;
pub const DMA_END_PAGE: u64 = 16 * 1024 * 1024 / PAGE_BYTES;
pub const DMA32_END_PAGE: u64 = 4 * 1024 * 1024 * 1024 / PAGE_BYTES;
pub const SCRUB_WORD_BYTES: u64 = 8;
pub const SCRUB_WORDS_PER_PAGE: usize = (PAGE_BYTES / SCRUB_WORD_BYTES) as usize;
pub const STALE_PATTERN: u64 = 0xA5A5_5A5A_C3C3_3C3C;
pub const METADATA_ARENA_PAGE_COUNT: u64 = 5;
pub const METADATA_GUARD_PAGE_COUNT: u64 = 2;
pub const METADATA_OWNER: u16 = 0x4D45;
pub const METADATA_MAGIC: u64 = u64::from_le_bytes(*b"PKPMMETA");
pub const METADATA_VERSION: u64 = 1;

const FNV_OFFSET: u64 = 0xCBF2_9CE4_8422_2325;
const FNV_PRIME: u64 = 0x0000_0100_0000_01B3;

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
#[repr(u8)]
pub enum ScrubKind {
    Allocation = 1,
    Release = 2,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct ScrubReceipt {
    pub sequence: u64,
    pub kind: ScrubKind,
    pub generation: u64,
    pub start_page: u64,
    pub page_count: u64,
    pub owner: u16,
    pub zeroed_bytes: u64,
    pub verified_bytes: u64,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
#[repr(u8)]
pub enum ReclaimClass {
    BootServices = 1,
    Acpi = 2,
}

impl ReclaimClass {
    const fn index(self) -> usize {
        self as usize - 1
    }

    const fn source_kind(self) -> u32 {
        match self {
            Self::BootServices => MEMORY_BOOT_RECLAIMABLE,
            Self::Acpi => MEMORY_ACPI_RECLAIMABLE,
        }
    }

    const fn required_stage(self) -> ReclaimStage {
        match self {
            Self::BootServices => ReclaimStage::PostExitBootServices,
            Self::Acpi => ReclaimStage::AcpiTablesReleased,
        }
    }
}

#[derive(Clone, Copy, Debug, Eq, PartialEq, Ord, PartialOrd)]
#[repr(u8)]
pub enum ReclaimStage {
    PreExitBootServices = 0,
    PostExitBootServices = 1,
    AcpiTablesReleased = 2,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct ReclaimReceipt {
    pub sequence: u64,
    pub class: ReclaimClass,
    pub required_stage: ReclaimStage,
    pub observed_stage: ReclaimStage,
    pub source_record_count: u64,
    pub range_count: u64,
    pub page_count: u64,
    pub pages_by_zone: [u64; 3],
    pub pre_free_extent_count: u64,
    pub post_free_extent_count: u64,
    pub zeroed_bytes: u64,
    pub verified_bytes: u64,
    pub range_checksum: u64,
    pub receipt_checksum: u64,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct ReclaimOutcome {
    pub receipt: ReclaimReceipt,
    pub newly_reclaimed: bool,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum PageAccessError {
    Access,
}

pub trait PhysicalPageAccess {
    fn write_word(
        &mut self,
        physical_address: u64,
        word_index: usize,
        value: u64,
    ) -> Result<(), PageAccessError>;

    fn read_word(
        &mut self,
        physical_address: u64,
        word_index: usize,
    ) -> Result<u64, PageAccessError>;
}

pub trait MetadataArenaAccess: PhysicalPageAccess {
    fn install_metadata_arena(
        &mut self,
        physical_address: u64,
        page_count: u64,
    ) -> Result<u64, PageAccessError>;

    fn finalize_metadata_handoff(
        &mut self,
        virtual_address: u64,
        manager_byte_count: u64,
    ) -> Result<(), PageAccessError>;

    fn uninstall_metadata_arena(
        &mut self,
        virtual_address: u64,
        page_count: u64,
    ) -> Result<(), PageAccessError>;
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
    ScrubAccess,
    ScrubVerification,
    ReceiptCapacity,
    MetadataCapacity,
    MetadataState,
    MetadataMapping,
    MetadataCorruption,
    MetadataOwnership,
    MetadataHandoff,
    ReclaimTiming,
    ReclaimCapacity,
    ReclaimOwnership,
    ReclaimUnavailable,
    ExerciseInvariant,
}

macro_rules! pmm_label {
    ($name:ident, $value:literal) => {
        #[used]
        #[unsafe(link_section = ".text.pkpmm_labels")]
        static $name: [u8; $value.len()] = *$value;
    };
}

pmm_label!(PMM_LABEL_MISSING_MAP, b"missing_map");
pmm_label!(PMM_LABEL_ENTRY_COUNT, b"entry_count");
pmm_label!(PMM_LABEL_ENTRY_SHAPE, b"entry_shape");
pmm_label!(PMM_LABEL_ENTRY_VALUE, b"entry_value");
pmm_label!(PMM_LABEL_ENTRY_ORDER, b"entry_order");
pmm_label!(PMM_LABEL_ADDRESS_RANGE, b"address_range");
pmm_label!(PMM_LABEL_SOURCE_KIND, b"source_kind");
pmm_label!(PMM_LABEL_EXTENT_CAPACITY, b"extent_capacity");
pmm_label!(PMM_LABEL_ALLOCATION_CAPACITY, b"allocation_capacity");
pmm_label!(PMM_LABEL_QUOTA, b"quota");
pmm_label!(PMM_LABEL_UNAVAILABLE, b"unavailable");
pmm_label!(PMM_LABEL_ZERO_ALLOCATION, b"zero_allocation");
pmm_label!(PMM_LABEL_INVALID_OWNER, b"invalid_owner");
pmm_label!(PMM_LABEL_STALE_HANDLE, b"stale_handle");
pmm_label!(PMM_LABEL_CORE_OWNERSHIP, b"core_ownership");
pmm_label!(PMM_LABEL_SCRUB_ACCESS, b"scrub_access");
pmm_label!(PMM_LABEL_SCRUB_VERIFICATION, b"scrub_verification");
pmm_label!(PMM_LABEL_RECEIPT_CAPACITY, b"receipt_capacity");
pmm_label!(PMM_LABEL_METADATA_CAPACITY, b"metadata_capacity");
pmm_label!(PMM_LABEL_METADATA_STATE, b"metadata_state");
pmm_label!(PMM_LABEL_METADATA_MAPPING, b"metadata_mapping");
pmm_label!(PMM_LABEL_METADATA_CORRUPTION, b"metadata_corruption");
pmm_label!(PMM_LABEL_METADATA_OWNERSHIP, b"metadata_ownership");
pmm_label!(PMM_LABEL_METADATA_HANDOFF, b"metadata_handoff");
pmm_label!(PMM_LABEL_RECLAIM_TIMING, b"reclaim_timing");
pmm_label!(PMM_LABEL_RECLAIM_CAPACITY, b"reclaim_capacity");
pmm_label!(PMM_LABEL_RECLAIM_OWNERSHIP, b"reclaim_ownership");
pmm_label!(PMM_LABEL_RECLAIM_UNAVAILABLE, b"reclaim_unavailable");
pmm_label!(PMM_LABEL_EXERCISE_INVARIANT, b"exercise_invariant");

const fn pmm_label_text(bytes: &'static [u8]) -> &'static str {
    // SAFETY: every caller passes an ASCII byte string declared immediately above.
    unsafe { core::str::from_utf8_unchecked(bytes) }
}

impl PhysicalMemoryError {
    pub const fn label(self) -> &'static str {
        match self {
            Self::MissingMap => pmm_label_text(&PMM_LABEL_MISSING_MAP),
            Self::EntryCount => pmm_label_text(&PMM_LABEL_ENTRY_COUNT),
            Self::EntryShape => pmm_label_text(&PMM_LABEL_ENTRY_SHAPE),
            Self::EntryValue => pmm_label_text(&PMM_LABEL_ENTRY_VALUE),
            Self::EntryOrder => pmm_label_text(&PMM_LABEL_ENTRY_ORDER),
            Self::AddressRange => pmm_label_text(&PMM_LABEL_ADDRESS_RANGE),
            Self::SourceKind => pmm_label_text(&PMM_LABEL_SOURCE_KIND),
            Self::ExtentCapacity => pmm_label_text(&PMM_LABEL_EXTENT_CAPACITY),
            Self::AllocationCapacity => pmm_label_text(&PMM_LABEL_ALLOCATION_CAPACITY),
            Self::Quota => pmm_label_text(&PMM_LABEL_QUOTA),
            Self::Unavailable => pmm_label_text(&PMM_LABEL_UNAVAILABLE),
            Self::ZeroAllocation => pmm_label_text(&PMM_LABEL_ZERO_ALLOCATION),
            Self::InvalidOwner => pmm_label_text(&PMM_LABEL_INVALID_OWNER),
            Self::StaleHandle => pmm_label_text(&PMM_LABEL_STALE_HANDLE),
            Self::CoreOwnership => pmm_label_text(&PMM_LABEL_CORE_OWNERSHIP),
            Self::ScrubAccess => pmm_label_text(&PMM_LABEL_SCRUB_ACCESS),
            Self::ScrubVerification => pmm_label_text(&PMM_LABEL_SCRUB_VERIFICATION),
            Self::ReceiptCapacity => pmm_label_text(&PMM_LABEL_RECEIPT_CAPACITY),
            Self::MetadataCapacity => pmm_label_text(&PMM_LABEL_METADATA_CAPACITY),
            Self::MetadataState => pmm_label_text(&PMM_LABEL_METADATA_STATE),
            Self::MetadataMapping => pmm_label_text(&PMM_LABEL_METADATA_MAPPING),
            Self::MetadataCorruption => pmm_label_text(&PMM_LABEL_METADATA_CORRUPTION),
            Self::MetadataOwnership => pmm_label_text(&PMM_LABEL_METADATA_OWNERSHIP),
            Self::MetadataHandoff => pmm_label_text(&PMM_LABEL_METADATA_HANDOFF),
            Self::ReclaimTiming => pmm_label_text(&PMM_LABEL_RECLAIM_TIMING),
            Self::ReclaimCapacity => pmm_label_text(&PMM_LABEL_RECLAIM_CAPACITY),
            Self::ReclaimOwnership => pmm_label_text(&PMM_LABEL_RECLAIM_OWNERSHIP),
            Self::ReclaimUnavailable => pmm_label_text(&PMM_LABEL_RECLAIM_UNAVAILABLE),
            Self::ExerciseInvariant => pmm_label_text(&PMM_LABEL_EXERCISE_INVARIANT),
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
struct SourceRecord {
    start_page: u64,
    page_count: u64,
    kind: u32,
    source: u32,
}

const EMPTY_SOURCE_RECORD: SourceRecord = SourceRecord {
    start_page: 0,
    page_count: 0,
    kind: 0,
    source: 0,
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
    release_excluded: bool,
}

const EMPTY_ALLOCATION: Allocation = Allocation {
    active: false,
    generation: 0,
    start_page: 0,
    page_count: 0,
    zone: Zone::Dma,
    owner: 0,
    metadata_poisoned: false,
    release_excluded: false,
};

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
#[repr(u64)]
enum MetadataLifecycle {
    Bootstrap = 0,
    Prepared = 1,
    Mapped = 2,
    Retired = 3,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
struct MetadataHeader {
    magic: u64,
    version: u64,
    manager_byte_count: u64,
    arena_page_count: u64,
    physical_start_page: u64,
    virtual_start: u64,
    generation: u64,
    owner: u16,
    logical_checksum: u64,
}

const EMPTY_METADATA_HEADER: MetadataHeader = MetadataHeader {
    magic: 0,
    version: 0,
    manager_byte_count: 0,
    arena_page_count: 0,
    physical_start_page: 0,
    virtual_start: 0,
    generation: 0,
    owner: 0,
    logical_checksum: 0,
};

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
struct AllocationPlan {
    slot: usize,
    extent_index: usize,
    generation: u64,
    start_page: u64,
    page_count: u64,
    zone: Zone,
    owner: u16,
}

#[derive(Clone, Copy)]
struct ReclaimPlan {
    stage: ReclaimStage,
    range_count: usize,
    free_count_after: usize,
    source_record_count: u64,
    pages_by_zone: [u64; 3],
    page_count: u64,
    managed_after: [u64; 3],
    coalesce_events_after: u64,
    scrub_zeroed_bytes_after: u64,
    scrub_verified_bytes_after: u64,
    reclaim_scrub_pages_after: u64,
    reclaim_operations_after: u64,
    next_reclaim_sequence_after: u64,
    range_checksum: u64,
}

#[derive(Clone, Copy)]
struct ReclaimCursor {
    next_record: usize,
    split_start_page: u64,
    split_remaining: u64,
    pending: Option<Extent>,
}

impl ReclaimCursor {
    const fn empty() -> Self {
        Self {
            next_record: 0,
            split_start_page: 0,
            split_remaining: 0,
            pending: None,
        }
    }
}

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
    pub allocation_scrub_pages: u64,
    pub release_scrub_pages: u64,
    pub scrub_zeroed_bytes: u64,
    pub scrub_verified_bytes: u64,
    pub scrub_receipt_count: u64,
    pub scrub_failures: u64,
    pub source_record_count: usize,
    pub receipt_ledger_count: usize,
    pub metadata_arena_pages: u64,
    pub metadata_release_rejections: u64,
    pub metadata_migration_rollbacks: u64,
    pub metadata_mapped: bool,
    pub reclaim_stage: ReclaimStage,
    pub reclaim_operations: u64,
    pub reclaim_receipt_count: u64,
    pub reclaim_scrub_pages: u64,
    pub reclaimed_pages: [u64; 2],
    pub reclaim_timing_rejections: u64,
    pub reclaim_capacity_rejections: u64,
    pub reclaim_ownership_rejections: u64,
    pub reclaim_rollbacks: u64,
}

pub struct PhysicalMemoryManager {
    free: [Extent; MAX_FREE_EXTENTS],
    free_count: usize,
    allocations: [Allocation; MAX_ALLOCATIONS],
    source_records: [SourceRecord; MAX_MEMORY_ENTRIES],
    scrub_receipts: [Option<ScrubReceipt>; MAX_SCRUB_RECEIPTS],
    receipt_ledger_count: usize,
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
    next_scrub_sequence: u64,
    allocation_scrub_pages: u64,
    release_scrub_pages: u64,
    scrub_zeroed_bytes: u64,
    scrub_verified_bytes: u64,
    scrub_receipt_count: u64,
    scrub_failures: u64,
    metadata_header: MetadataHeader,
    metadata_lifecycle: MetadataLifecycle,
    metadata_release_rejections: u64,
    metadata_migration_rollbacks: u64,
    reclaim_stage: ReclaimStage,
    reclaim_receipts: [Option<ReclaimReceipt>; MAX_RECLAIM_RECEIPTS],
    reclaim_receipt_count: usize,
    next_reclaim_sequence: u64,
    reclaim_operations: u64,
    reclaim_scrub_pages: u64,
    reclaimed_pages: [u64; MAX_RECLAIM_RECEIPTS],
    reclaim_timing_rejections: u64,
    reclaim_capacity_rejections: u64,
    reclaim_ownership_rejections: u64,
    reclaim_rollbacks: u64,
}

const METADATA_ARENA_BYTE_CAPACITY: usize =
    METADATA_ARENA_PAGE_COUNT as usize * PAGE_BYTES as usize;

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct MetadataArenaReceipt {
    pub physical_start_page: u64,
    pub virtual_start: u64,
    pub page_count: u64,
    pub guard_page_count: u64,
    pub generation: u64,
    pub owner: u16,
    pub manager_byte_count: u64,
    pub source_record_count: u64,
    pub free_extent_count: u64,
    pub allocation_record_count: u64,
    pub receipt_ledger_count: u64,
    pub logical_checksum: u64,
    pub mapping_count: u64,
    pub release_excluded: bool,
    pub integrity_verified: bool,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
struct MetadataMigration {
    manager_address: u64,
    allocation: AllocationHandle,
    receipt: MetadataArenaReceipt,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct PhysicalMemoryProof {
    pub initial: PhysicalMemorySummary,
    pub final_state: PhysicalMemorySummary,
    pub start_page: u64,
    pub first_generation: u64,
    pub reuse_generation: u64,
    pub stale_pattern: u64,
    pub stale_pattern_absent: bool,
    pub receipts: [ScrubReceipt; 4],
    pub metadata: MetadataArenaReceipt,
    pub metadata_release_rejected: bool,
    pub metadata_integrity_verified: bool,
    pub final_metadata_checksum: u64,
    pub boot_reclaim: ReclaimReceipt,
    pub boot_reclaim_idempotent: bool,
    pub acpi_early_rejected: bool,
}

#[inline(never)]
pub fn run_profile<A: MetadataArenaAccess>(
    handoff: &Handoff<'_>,
    core: CoreRecord,
    access: &mut A,
) -> Result<PhysicalMemoryProof, PhysicalMemoryError> {
    let mut bootstrap = PhysicalMemoryManager::from_handoff(handoff, core, DEFAULT_QUOTA_PAGES)?;
    let migration = bootstrap.migrate_to_metadata(access)?;
    // SAFETY: migrate_to_metadata copied, sealed, and validated a complete manager
    // object in an installed mapping that remains live for this profile.
    let manager =
        unsafe { &mut *(migration.manager_address as usize as *mut PhysicalMemoryManager) };
    let initial = manager.summary();
    let metadata_release_rejected = manager.free_scrubbed(migration.allocation, access)
        == Err(PhysicalMemoryError::MetadataOwnership);
    manager.advance_reclaim_stage(ReclaimStage::PostExitBootServices)?;
    let boot_reclaim = manager.reclaim_held(ReclaimClass::BootServices, access)?;
    let boot_reclaim_repeat = manager.reclaim_held(ReclaimClass::BootServices, access)?;
    let boot_reclaim_idempotent =
        !boot_reclaim_repeat.newly_reclaimed && boot_reclaim_repeat.receipt == boot_reclaim.receipt;
    let acpi_early_rejected =
        manager.reclaim_held(ReclaimClass::Acpi, access) == Err(PhysicalMemoryError::ReclaimTiming);
    let (first, allocation_receipt) = manager.allocate_scrubbed(Zone::Dma32, 2, 1, access)?;
    let quota_rejected = manager
        .allocate_scrubbed(Zone::Dma32, DEFAULT_QUOTA_PAGES, 3, access)
        .is_err();
    let unavailable_rejected = manager
        .allocate_scrubbed(Zone::Normal, 1, 3, access)
        .is_err();
    fill_and_verify(access, first, STALE_PATTERN)?;
    let release_receipt = manager.free_scrubbed(first, access)?;
    let double_free_rejected = manager.free_scrubbed(first, access).is_err();
    let (reused, reuse_allocation_receipt) =
        manager.allocate_scrubbed(Zone::Dma32, 2, 2, access)?;
    let stale_pattern_absent = verify_words(access, reused, 0)?;
    let reuse_release_receipt = manager.free_scrubbed(reused, access)?;
    let metadata_integrity_verified = manager.verify_metadata_integrity().is_ok();
    let final_state = manager.summary();
    if !metadata_release_rejected
        || !metadata_integrity_verified
        || !boot_reclaim.newly_reclaimed
        || !boot_reclaim_idempotent
        || !acpi_early_rejected
        || boot_reclaim.receipt.class != ReclaimClass::BootServices
        || boot_reclaim.receipt.required_stage != ReclaimStage::PostExitBootServices
        || boot_reclaim.receipt.observed_stage != ReclaimStage::PostExitBootServices
        || boot_reclaim.receipt.page_count != initial.source_pages[MEMORY_BOOT_RECLAIMABLE as usize]
        || boot_reclaim.receipt.zeroed_bytes != boot_reclaim.receipt.page_count * PAGE_BYTES
        || boot_reclaim.receipt.verified_bytes != boot_reclaim.receipt.zeroed_bytes
        || boot_reclaim.receipt.range_checksum == 0
        || boot_reclaim.receipt.receipt_checksum == 0
        || !quota_rejected
        || !unavailable_rejected
        || !double_free_rejected
        || reused.start_page != first.start_page
        || reused.generation <= first.generation
        || !stale_pattern_absent
        || [
            allocation_receipt,
            release_receipt,
            reuse_allocation_receipt,
            reuse_release_receipt,
        ]
        .iter()
        .enumerate()
        .any(|(index, receipt)| receipt.sequence != index as u64 + 2)
        || final_state.allocated_pages != METADATA_ARENA_PAGE_COUNT
        || final_state.free_extent_count != boot_reclaim.receipt.post_free_extent_count as usize
        || final_state.allocation_scrub_pages != METADATA_ARENA_PAGE_COUNT + 4
        || final_state.release_scrub_pages != 4
        || final_state.reclaim_scrub_pages != boot_reclaim.receipt.page_count
        || final_state.scrub_zeroed_bytes
            != (METADATA_ARENA_PAGE_COUNT + 8 + boot_reclaim.receipt.page_count) * PAGE_BYTES
        || final_state.scrub_verified_bytes != final_state.scrub_zeroed_bytes
        || final_state.scrub_receipt_count != 5
        || final_state.receipt_ledger_count != 5
        || final_state.scrub_failures != 0
        || final_state.source_record_count != initial.memory_entry_count
        || final_state.metadata_arena_pages != METADATA_ARENA_PAGE_COUNT
        || final_state.metadata_release_rejections != 1
        || !final_state.metadata_mapped
        || final_state.reclaim_stage != ReclaimStage::PostExitBootServices
        || final_state.reclaim_operations != 1
        || final_state.reclaim_receipt_count != 1
        || final_state.reclaimed_pages
            != [initial.source_pages[MEMORY_BOOT_RECLAIMABLE as usize], 0]
        || final_state.reclaim_timing_rejections != 1
        || final_state.reclaim_capacity_rejections != 0
        || final_state.reclaim_ownership_rejections != 0
        || final_state.reclaim_rollbacks != 0
    {
        return Err(PhysicalMemoryError::ExerciseInvariant);
    }
    Ok(PhysicalMemoryProof {
        initial,
        final_state,
        start_page: first.start_page,
        first_generation: first.generation,
        reuse_generation: reused.generation,
        stale_pattern: STALE_PATTERN,
        stale_pattern_absent,
        receipts: [
            allocation_receipt,
            release_receipt,
            reuse_allocation_receipt,
            reuse_release_receipt,
        ],
        metadata: migration.receipt,
        metadata_release_rejected,
        metadata_integrity_verified,
        final_metadata_checksum: manager.metadata_header.logical_checksum,
        boot_reclaim: boot_reclaim.receipt,
        boot_reclaim_idempotent,
        acpi_early_rejected,
    })
}

fn fill_and_verify<A: PhysicalPageAccess>(
    access: &mut A,
    handle: AllocationHandle,
    pattern: u64,
) -> Result<(), PhysicalMemoryError> {
    for page_offset in 0..handle.page_count {
        let page = handle
            .start_page
            .checked_add(page_offset)
            .ok_or(PhysicalMemoryError::AddressRange)?;
        let physical = page
            .checked_mul(PAGE_BYTES)
            .ok_or(PhysicalMemoryError::AddressRange)?;
        for word_index in 0..SCRUB_WORDS_PER_PAGE {
            access
                .write_word(physical, word_index, pattern)
                .map_err(|_| PhysicalMemoryError::ScrubAccess)?;
        }
    }
    if !verify_words(access, handle, pattern)? {
        return Err(PhysicalMemoryError::ScrubVerification);
    }
    Ok(())
}

fn verify_words<A: PhysicalPageAccess>(
    access: &mut A,
    handle: AllocationHandle,
    expected: u64,
) -> Result<bool, PhysicalMemoryError> {
    for page_offset in 0..handle.page_count {
        let page = handle
            .start_page
            .checked_add(page_offset)
            .ok_or(PhysicalMemoryError::AddressRange)?;
        let physical = page
            .checked_mul(PAGE_BYTES)
            .ok_or(PhysicalMemoryError::AddressRange)?;
        for word_index in 0..SCRUB_WORDS_PER_PAGE {
            if access
                .read_word(physical, word_index)
                .map_err(|_| PhysicalMemoryError::ScrubAccess)?
                != expected
            {
                return Ok(false);
            }
        }
    }
    Ok(true)
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

fn fnv_u64(mut state: u64, value: u64) -> u64 {
    for byte in value.to_le_bytes() {
        state ^= u64::from(byte);
        state = state.wrapping_mul(FNV_PRIME);
    }
    state
}

const fn zone_code(zone: Zone) -> u64 {
    zone as u8 as u64
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
            source_records: [EMPTY_SOURCE_RECORD; MAX_MEMORY_ENTRIES],
            scrub_receipts: [None; MAX_SCRUB_RECEIPTS],
            receipt_ledger_count: 0,
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
            next_scrub_sequence: 1,
            allocation_scrub_pages: 0,
            release_scrub_pages: 0,
            scrub_zeroed_bytes: 0,
            scrub_verified_bytes: 0,
            scrub_receipt_count: 0,
            scrub_failures: 0,
            metadata_header: EMPTY_METADATA_HEADER,
            metadata_lifecycle: MetadataLifecycle::Bootstrap,
            metadata_release_rejections: 0,
            metadata_migration_rollbacks: 0,
            reclaim_stage: ReclaimStage::PreExitBootServices,
            reclaim_receipts: [None; MAX_RECLAIM_RECEIPTS],
            reclaim_receipt_count: 0,
            next_reclaim_sequence: 1,
            reclaim_operations: 0,
            reclaim_scrub_pages: 0,
            reclaimed_pages: [0; MAX_RECLAIM_RECEIPTS],
            reclaim_timing_rejections: 0,
            reclaim_capacity_rejections: 0,
            reclaim_ownership_rejections: 0,
            reclaim_rollbacks: 0,
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
            manager.source_records[index] = SourceRecord {
                start_page: start / PAGE_BYTES,
                page_count: pages,
                kind,
                source,
            };
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

    fn logical_checksum(&self) -> u64 {
        let mut state = FNV_OFFSET;
        for value in [
            self.metadata_header.magic,
            self.metadata_header.version,
            self.metadata_header.manager_byte_count,
            self.metadata_header.arena_page_count,
            self.metadata_header.physical_start_page,
            self.metadata_header.virtual_start,
            self.metadata_header.generation,
            u64::from(self.metadata_header.owner),
            self.metadata_lifecycle as u64,
            self.free_count as u64,
            self.receipt_ledger_count as u64,
            self.memory_entry_count as u64,
            self.null_guard_pages,
            self.quota_pages,
            self.allocated_pages,
            self.next_generation,
            self.allocation_count,
            self.free_operation_count,
            self.rejected_double_frees,
            self.rejected_quota_requests,
            self.rejected_unavailable_requests,
            self.metadata_poison_events,
            self.coalesce_events,
            self.next_scrub_sequence,
            self.allocation_scrub_pages,
            self.release_scrub_pages,
            self.scrub_zeroed_bytes,
            self.scrub_verified_bytes,
            self.scrub_receipt_count,
            self.scrub_failures,
            self.metadata_release_rejections,
            self.metadata_migration_rollbacks,
            self.reclaim_stage as u64,
            self.reclaim_receipt_count as u64,
            self.next_reclaim_sequence,
            self.reclaim_operations,
            self.reclaim_scrub_pages,
            self.reclaim_timing_rejections,
            self.reclaim_capacity_rejections,
            self.reclaim_ownership_rejections,
            self.reclaim_rollbacks,
        ] {
            state = fnv_u64(state, value);
        }
        for extent in self.free {
            for value in [extent.start_page, extent.page_count, zone_code(extent.zone)] {
                state = fnv_u64(state, value);
            }
        }
        for allocation in self.allocations {
            for value in [
                u64::from(allocation.active),
                allocation.generation,
                allocation.start_page,
                allocation.page_count,
                zone_code(allocation.zone),
                u64::from(allocation.owner),
                u64::from(allocation.metadata_poisoned),
                u64::from(allocation.release_excluded),
            ] {
                state = fnv_u64(state, value);
            }
        }
        for record in self.source_records {
            for value in [
                record.start_page,
                record.page_count,
                u64::from(record.kind),
                u64::from(record.source),
            ] {
                state = fnv_u64(state, value);
            }
        }
        for receipt in self.scrub_receipts {
            state = fnv_u64(state, u64::from(receipt.is_some()));
            if let Some(receipt) = receipt {
                for value in [
                    receipt.sequence,
                    receipt.kind as u8 as u64,
                    receipt.generation,
                    receipt.start_page,
                    receipt.page_count,
                    u64::from(receipt.owner),
                    receipt.zeroed_bytes,
                    receipt.verified_bytes,
                ] {
                    state = fnv_u64(state, value);
                }
            }
        }
        for receipt in self.reclaim_receipts {
            state = fnv_u64(state, u64::from(receipt.is_some()));
            if let Some(receipt) = receipt {
                for value in [
                    receipt.sequence,
                    receipt.class as u8 as u64,
                    receipt.required_stage as u8 as u64,
                    receipt.observed_stage as u8 as u64,
                    receipt.source_record_count,
                    receipt.range_count,
                    receipt.page_count,
                    receipt.pre_free_extent_count,
                    receipt.post_free_extent_count,
                    receipt.zeroed_bytes,
                    receipt.verified_bytes,
                    receipt.range_checksum,
                    receipt.receipt_checksum,
                ] {
                    state = fnv_u64(state, value);
                }
                for value in receipt.pages_by_zone {
                    state = fnv_u64(state, value);
                }
            }
        }
        for value in self.source_pages {
            state = fnv_u64(state, value);
        }
        for value in self.source_usable_pages {
            state = fnv_u64(state, value);
        }
        for value in self.managed_pages {
            state = fnv_u64(state, value);
        }
        for value in self.reclaimed_pages {
            state = fnv_u64(state, value);
        }
        state
    }

    fn seal_metadata_integrity(&mut self) {
        if self.metadata_lifecycle == MetadataLifecycle::Mapped {
            self.metadata_header.logical_checksum = self.logical_checksum();
        }
    }

    pub fn verify_metadata_integrity(&self) -> Result<(), PhysicalMemoryError> {
        if self.metadata_lifecycle != MetadataLifecycle::Mapped
            || self.metadata_header.magic != METADATA_MAGIC
            || self.metadata_header.version != METADATA_VERSION
            || self.metadata_header.manager_byte_count != core::mem::size_of::<Self>() as u64
            || self.metadata_header.arena_page_count != METADATA_ARENA_PAGE_COUNT
            || self.metadata_header.owner != METADATA_OWNER
            || self.metadata_header.virtual_start == 0
            || !self
                .metadata_header
                .virtual_start
                .is_multiple_of(PAGE_BYTES)
            || self.metadata_header.logical_checksum != self.logical_checksum()
        {
            return Err(PhysicalMemoryError::MetadataCorruption);
        }
        Ok(())
    }

    fn require_operational(&self) -> Result<(), PhysicalMemoryError> {
        match self.metadata_lifecycle {
            MetadataLifecycle::Bootstrap => Ok(()),
            MetadataLifecycle::Mapped => self.verify_metadata_integrity(),
            MetadataLifecycle::Prepared | MetadataLifecycle::Retired => {
                Err(PhysicalMemoryError::MetadataState)
            }
        }
    }

    fn rollback_metadata_reservation<A: PhysicalPageAccess>(
        &mut self,
        handle: AllocationHandle,
        access: &mut A,
    ) -> Result<(), PhysicalMemoryError> {
        let slot = usize::from(handle.slot);
        if self.allocations.get(slot).map(|item| item.release_excluded) != Some(true) {
            return Err(PhysicalMemoryError::MetadataState);
        }
        self.allocations[slot].release_excluded = false;
        self.metadata_lifecycle = MetadataLifecycle::Bootstrap;
        self.metadata_header = EMPTY_METADATA_HEADER;
        self.metadata_migration_rollbacks = self.metadata_migration_rollbacks.saturating_add(1);
        self.free_scrubbed(handle, access)?;
        Ok(())
    }

    fn migrate_to_metadata<A: MetadataArenaAccess>(
        &mut self,
        access: &mut A,
    ) -> Result<MetadataMigration, PhysicalMemoryError> {
        let manager_byte_count = core::mem::size_of::<Self>();
        if manager_byte_count == 0 || manager_byte_count > METADATA_ARENA_BYTE_CAPACITY {
            return Err(PhysicalMemoryError::MetadataCapacity);
        }
        self.require_operational()?;
        let (allocation, _) = self.allocate_scrubbed(
            Zone::Dma32,
            METADATA_ARENA_PAGE_COUNT,
            METADATA_OWNER,
            access,
        )?;
        let slot = usize::from(allocation.slot);
        self.allocations[slot].release_excluded = true;
        self.metadata_lifecycle = MetadataLifecycle::Prepared;
        self.metadata_header = MetadataHeader {
            magic: METADATA_MAGIC,
            version: METADATA_VERSION,
            manager_byte_count: manager_byte_count as u64,
            arena_page_count: METADATA_ARENA_PAGE_COUNT,
            physical_start_page: allocation.start_page,
            virtual_start: 0,
            generation: allocation.generation,
            owner: allocation.owner,
            logical_checksum: 0,
        };
        let physical_address = allocation
            .start_page
            .checked_mul(PAGE_BYTES)
            .ok_or(PhysicalMemoryError::AddressRange)?;
        let virtual_address =
            match access.install_metadata_arena(physical_address, METADATA_ARENA_PAGE_COUNT) {
                Ok(value) => value,
                Err(_) => {
                    self.rollback_metadata_reservation(allocation, access)?;
                    return Err(PhysicalMemoryError::MetadataMapping);
                }
            };
        let destination_end = virtual_address
            .checked_add(manager_byte_count as u64)
            .ok_or(PhysicalMemoryError::AddressRange)?;
        let arena_end = virtual_address
            .checked_add(METADATA_ARENA_PAGE_COUNT * PAGE_BYTES)
            .ok_or(PhysicalMemoryError::AddressRange)?;
        let source_start = self as *const Self as usize as u64;
        let source_end = source_start
            .checked_add(manager_byte_count as u64)
            .ok_or(PhysicalMemoryError::AddressRange)?;
        if virtual_address == 0
            || !virtual_address.is_multiple_of(PAGE_BYTES)
            || destination_end > arena_end
            || (virtual_address < source_end && source_start < destination_end)
        {
            access
                .uninstall_metadata_arena(virtual_address, METADATA_ARENA_PAGE_COUNT)
                .map_err(|_| PhysicalMemoryError::MetadataMapping)?;
            self.rollback_metadata_reservation(allocation, access)?;
            return Err(PhysicalMemoryError::MetadataHandoff);
        }
        self.metadata_header.virtual_start = virtual_address;
        let mapped_pointer = virtual_address as usize as *mut Self;
        // SAFETY: the architecture adapter returns a page-aligned, non-overlapping,
        // writable mapping whose capacity is checked above. Self has no Drop fields.
        unsafe { core::ptr::copy_nonoverlapping(self as *const Self, mapped_pointer, 1) };
        let validation = {
            // SAFETY: the complete manager object was copied into the validated mapping.
            let mapped = unsafe { &mut *mapped_pointer };
            mapped.metadata_lifecycle = MetadataLifecycle::Mapped;
            mapped.seal_metadata_integrity();
            access
                .finalize_metadata_handoff(virtual_address, manager_byte_count as u64)
                .map_err(|_| PhysicalMemoryError::MetadataHandoff)
                .and_then(|()| mapped.verify_metadata_integrity())
        };
        if let Err(error) = validation {
            access
                .uninstall_metadata_arena(virtual_address, METADATA_ARENA_PAGE_COUNT)
                .map_err(|_| PhysicalMemoryError::MetadataMapping)?;
            self.rollback_metadata_reservation(allocation, access)?;
            return Err(error);
        }
        // SAFETY: validation above proves the mapped manager header and logical seal.
        let mapped = unsafe { &mut *mapped_pointer };
        let active_allocations = mapped.allocations.iter().filter(|item| item.active).count();
        let receipt = MetadataArenaReceipt {
            physical_start_page: allocation.start_page,
            virtual_start: virtual_address,
            page_count: METADATA_ARENA_PAGE_COUNT,
            guard_page_count: METADATA_GUARD_PAGE_COUNT,
            generation: allocation.generation,
            owner: allocation.owner,
            manager_byte_count: manager_byte_count as u64,
            source_record_count: mapped.memory_entry_count as u64,
            free_extent_count: mapped.free_count as u64,
            allocation_record_count: active_allocations as u64,
            receipt_ledger_count: mapped.receipt_ledger_count as u64,
            logical_checksum: mapped.metadata_header.logical_checksum,
            mapping_count: METADATA_ARENA_PAGE_COUNT,
            release_excluded: mapped.allocations[slot].release_excluded,
            integrity_verified: true,
        };
        self.metadata_lifecycle = MetadataLifecycle::Retired;
        Ok(MetadataMigration {
            manager_address: virtual_address,
            allocation,
            receipt,
        })
    }

    pub fn advance_reclaim_stage(
        &mut self,
        stage: ReclaimStage,
    ) -> Result<(), PhysicalMemoryError> {
        self.require_operational()?;
        let result = if stage == self.reclaim_stage {
            Ok(())
        } else if matches!(
            (self.reclaim_stage, stage),
            (
                ReclaimStage::PreExitBootServices,
                ReclaimStage::PostExitBootServices
            ) | (
                ReclaimStage::PostExitBootServices,
                ReclaimStage::AcpiTablesReleased
            )
        ) {
            self.reclaim_stage = stage;
            Ok(())
        } else {
            self.reclaim_timing_rejections = self.reclaim_timing_rejections.saturating_add(1);
            Err(PhysicalMemoryError::ReclaimTiming)
        };
        self.seal_metadata_integrity();
        result
    }

    pub fn reclaim_held<A: PhysicalPageAccess>(
        &mut self,
        class: ReclaimClass,
        access: &mut A,
    ) -> Result<ReclaimOutcome, PhysicalMemoryError> {
        self.require_operational()?;
        let class_index = class.index();
        if let Some(receipt) = self.reclaim_receipts[class_index] {
            return Ok(ReclaimOutcome {
                receipt,
                newly_reclaimed: false,
            });
        }
        if self.reclaim_stage < class.required_stage() {
            self.reclaim_timing_rejections = self.reclaim_timing_rejections.saturating_add(1);
            self.seal_metadata_integrity();
            return Err(PhysicalMemoryError::ReclaimTiming);
        }
        let plan = match self.plan_reclaim(class) {
            Ok(value) => value,
            Err(error) => {
                self.seal_metadata_integrity();
                return Err(error);
            }
        };
        let target_kind = class.source_kind();
        let mut scrub_cursor = ReclaimCursor::empty();
        while let Some(extent) = self.next_reclaim_extent(target_kind, &mut scrub_cursor)? {
            if let Err(error) = self.scrub_extent(access, extent) {
                self.reclaim_rollbacks = self.reclaim_rollbacks.saturating_add(1);
                self.seal_metadata_integrity();
                return Err(error);
            }
        }
        let byte_count = plan
            .page_count
            .checked_mul(PAGE_BYTES)
            .ok_or(PhysicalMemoryError::AddressRange)?;
        let mut receipt = ReclaimReceipt {
            sequence: self.next_reclaim_sequence,
            class,
            required_stage: class.required_stage(),
            observed_stage: plan.stage,
            source_record_count: plan.source_record_count,
            range_count: plan.range_count as u64,
            page_count: plan.page_count,
            pages_by_zone: plan.pages_by_zone,
            pre_free_extent_count: self.free_count as u64,
            post_free_extent_count: plan.free_count_after as u64,
            zeroed_bytes: byte_count,
            verified_bytes: byte_count,
            range_checksum: plan.range_checksum,
            receipt_checksum: 0,
        };
        receipt.receipt_checksum = reclaim_receipt_checksum(receipt);
        let mut commit_cursor = ReclaimCursor::empty();
        while let Some(extent) = self.next_reclaim_extent(target_kind, &mut commit_cursor)? {
            self.commit_preflighted_extent(extent);
        }
        self.free_count = plan.free_count_after;
        self.coalesce_events = plan.coalesce_events_after;
        self.managed_pages = plan.managed_after;
        self.scrub_zeroed_bytes = plan.scrub_zeroed_bytes_after;
        self.scrub_verified_bytes = plan.scrub_verified_bytes_after;
        self.reclaim_scrub_pages = plan.reclaim_scrub_pages_after;
        self.reclaim_operations = plan.reclaim_operations_after;
        self.next_reclaim_sequence = plan.next_reclaim_sequence_after;
        self.reclaimed_pages[class_index] = plan.page_count;
        self.reclaim_receipts[class_index] = Some(receipt);
        self.reclaim_receipt_count += 1;
        self.seal_metadata_integrity();
        Ok(ReclaimOutcome {
            receipt,
            newly_reclaimed: true,
        })
    }

    fn plan_reclaim(&mut self, class: ReclaimClass) -> Result<ReclaimPlan, PhysicalMemoryError> {
        if self.reclaim_receipt_count == MAX_RECLAIM_RECEIPTS {
            self.reclaim_capacity_rejections = self.reclaim_capacity_rejections.saturating_add(1);
            return Err(PhysicalMemoryError::ReclaimCapacity);
        }
        let mut source_record_count = 0u64;
        let mut range_checksum = fnv_u64(FNV_OFFSET, class as u8 as u64);
        range_checksum = fnv_u64(range_checksum, self.reclaim_stage as u8 as u64);
        let target_kind = class.source_kind();
        for record_index in 0..self.memory_entry_count {
            let record = self.source_records[record_index];
            if record.kind != target_kind {
                continue;
            }
            source_record_count = source_record_count
                .checked_add(1)
                .ok_or(PhysicalMemoryError::AddressRange)?;
            for value in [
                record.start_page,
                record.page_count,
                u64::from(record.kind),
                u64::from(record.source),
            ] {
                range_checksum = fnv_u64(range_checksum, value);
            }
        }
        let mut range_count = 0usize;
        let mut pages_by_zone = [0u64; 3];
        let mut page_count = 0u64;
        let mut free_count_after = self.free_count;
        let mut coalesce_delta = 0u64;
        let mut cursor = ReclaimCursor::empty();
        while let Some(extent) = self.next_reclaim_extent(target_kind, &mut cursor)? {
            range_count = range_count
                .checked_add(1)
                .ok_or(PhysicalMemoryError::AddressRange)?;
            if range_count > MAX_RECLAIM_EXTENTS {
                self.reclaim_capacity_rejections =
                    self.reclaim_capacity_rejections.saturating_add(1);
                return Err(PhysicalMemoryError::ReclaimCapacity);
            }
            if self.reclaim_extent_overlaps_retained(extent, target_kind)? {
                self.reclaim_ownership_rejections =
                    self.reclaim_ownership_rejections.saturating_add(1);
                return Err(PhysicalMemoryError::ReclaimOwnership);
            }
            let zone_index = extent.zone.index();
            pages_by_zone[zone_index] = pages_by_zone[zone_index]
                .checked_add(extent.page_count)
                .ok_or(PhysicalMemoryError::AddressRange)?;
            page_count = page_count
                .checked_add(extent.page_count)
                .ok_or(PhysicalMemoryError::AddressRange)?;
            let extent_end = extent
                .start_page
                .checked_add(extent.page_count)
                .ok_or(PhysicalMemoryError::AddressRange)?;
            let mut merge_previous = false;
            let mut merge_next = false;
            for free in &self.free[..self.free_count] {
                let free_end = free
                    .start_page
                    .checked_add(free.page_count)
                    .ok_or(PhysicalMemoryError::AddressRange)?;
                if extent.start_page < free_end && free.start_page < extent_end {
                    self.reclaim_ownership_rejections =
                        self.reclaim_ownership_rejections.saturating_add(1);
                    return Err(PhysicalMemoryError::ReclaimOwnership);
                }
                if free.zone == extent.zone && free_end == extent.start_page {
                    merge_previous = true;
                }
                if free.zone == extent.zone && extent_end == free.start_page {
                    merge_next = true;
                }
            }
            if merge_previous && merge_next {
                free_count_after = free_count_after
                    .checked_sub(1)
                    .ok_or(PhysicalMemoryError::AddressRange)?;
                coalesce_delta = coalesce_delta
                    .checked_add(2)
                    .ok_or(PhysicalMemoryError::AddressRange)?;
            } else if merge_previous || merge_next {
                coalesce_delta = coalesce_delta
                    .checked_add(1)
                    .ok_or(PhysicalMemoryError::AddressRange)?;
            } else {
                free_count_after = free_count_after
                    .checked_add(1)
                    .ok_or(PhysicalMemoryError::AddressRange)?;
                if free_count_after > MAX_FREE_EXTENTS {
                    self.reclaim_capacity_rejections =
                        self.reclaim_capacity_rejections.saturating_add(1);
                    return Err(PhysicalMemoryError::ReclaimCapacity);
                }
            }
        }
        if page_count == 0 {
            return Err(PhysicalMemoryError::ReclaimUnavailable);
        }
        let mut managed_after = self.managed_pages;
        for zone in 0..managed_after.len() {
            managed_after[zone] = managed_after[zone]
                .checked_add(pages_by_zone[zone])
                .ok_or(PhysicalMemoryError::AddressRange)?;
        }
        let byte_count = page_count
            .checked_mul(PAGE_BYTES)
            .ok_or(PhysicalMemoryError::AddressRange)?;
        Ok(ReclaimPlan {
            stage: self.reclaim_stage,
            range_count,
            free_count_after,
            source_record_count,
            pages_by_zone,
            page_count,
            managed_after,
            coalesce_events_after: self
                .coalesce_events
                .checked_add(coalesce_delta)
                .ok_or(PhysicalMemoryError::AddressRange)?,
            scrub_zeroed_bytes_after: self
                .scrub_zeroed_bytes
                .checked_add(byte_count)
                .ok_or(PhysicalMemoryError::AddressRange)?,
            scrub_verified_bytes_after: self
                .scrub_verified_bytes
                .checked_add(byte_count)
                .ok_or(PhysicalMemoryError::AddressRange)?,
            reclaim_scrub_pages_after: self
                .reclaim_scrub_pages
                .checked_add(page_count)
                .ok_or(PhysicalMemoryError::AddressRange)?,
            reclaim_operations_after: self
                .reclaim_operations
                .checked_add(1)
                .ok_or(PhysicalMemoryError::AddressRange)?,
            next_reclaim_sequence_after: self
                .next_reclaim_sequence
                .checked_add(1)
                .ok_or(PhysicalMemoryError::AddressRange)?,
            range_checksum,
        })
    }

    fn next_reclaim_extent(
        &self,
        target_kind: u32,
        cursor: &mut ReclaimCursor,
    ) -> Result<Option<Extent>, PhysicalMemoryError> {
        loop {
            let next = if cursor.split_remaining != 0 {
                let zone = zone_for_page(cursor.split_start_page);
                let take = cursor
                    .split_remaining
                    .min(zone_end_page(zone).saturating_sub(cursor.split_start_page));
                if take == 0 {
                    return Err(PhysicalMemoryError::AddressRange);
                }
                let extent = Extent {
                    start_page: cursor.split_start_page,
                    page_count: take,
                    zone,
                };
                cursor.split_start_page = cursor
                    .split_start_page
                    .checked_add(take)
                    .ok_or(PhysicalMemoryError::AddressRange)?;
                cursor.split_remaining -= take;
                Some(extent)
            } else {
                let mut record = None;
                while cursor.next_record < self.memory_entry_count {
                    let candidate = self.source_records[cursor.next_record];
                    cursor.next_record += 1;
                    if candidate.kind == target_kind {
                        record = Some(candidate);
                        break;
                    }
                }
                if let Some(record) = record {
                    cursor.split_start_page = record.start_page;
                    cursor.split_remaining = record.page_count;
                    continue;
                }
                None
            };
            match (cursor.pending, next) {
                (None, None) => return Ok(None),
                (Some(pending), None) => {
                    cursor.pending = None;
                    return Ok(Some(pending));
                }
                (None, Some(extent)) => cursor.pending = Some(extent),
                (Some(mut pending), Some(extent)) if can_coalesce(pending, extent) => {
                    pending.page_count = pending
                        .page_count
                        .checked_add(extent.page_count)
                        .ok_or(PhysicalMemoryError::AddressRange)?;
                    cursor.pending = Some(pending);
                }
                (Some(pending), Some(extent)) => {
                    cursor.pending = Some(extent);
                    return Ok(Some(pending));
                }
            }
        }
    }

    fn commit_preflighted_extent(&mut self, extent: Extent) {
        let mut index = 0;
        while index < self.free_count && self.free[index].start_page < extent.start_page {
            index += 1;
        }
        let merge_previous = index > 0 && can_coalesce(self.free[index - 1], extent);
        let merge_next = index < self.free_count && can_coalesce(extent, self.free[index]);
        if merge_previous && merge_next {
            self.free[index - 1].page_count = self.free[index - 1]
                .page_count
                .wrapping_add(extent.page_count)
                .wrapping_add(self.free[index].page_count);
            self.remove_free_extent(index);
            self.coalesce_events = self.coalesce_events.wrapping_add(2);
        } else if merge_previous {
            self.free[index - 1].page_count = self.free[index - 1]
                .page_count
                .wrapping_add(extent.page_count);
            self.coalesce_events = self.coalesce_events.wrapping_add(1);
        } else if merge_next {
            self.free[index].start_page = extent.start_page;
            self.free[index].page_count =
                extent.page_count.wrapping_add(self.free[index].page_count);
            self.coalesce_events = self.coalesce_events.wrapping_add(1);
        } else {
            for item in (index..self.free_count).rev() {
                self.free[item + 1] = self.free[item];
            }
            self.free[index] = extent;
            self.free_count += 1;
        }
    }

    fn reclaim_extent_overlaps_retained(
        &self,
        extent: Extent,
        target_kind: u32,
    ) -> Result<bool, PhysicalMemoryError> {
        for allocation in self.allocations.iter().filter(|item| item.active) {
            if ranges_overlap(
                extent.start_page,
                extent.page_count,
                allocation.start_page,
                allocation.page_count,
            )? {
                return Ok(true);
            }
        }
        for record in self.source_records[..self.memory_entry_count]
            .iter()
            .filter(|item| item.kind != target_kind)
        {
            if ranges_overlap(
                extent.start_page,
                extent.page_count,
                record.start_page,
                record.page_count,
            )? {
                return Ok(true);
            }
        }
        Ok(false)
    }

    fn scrub_extent<A: PhysicalPageAccess>(
        &mut self,
        access: &mut A,
        extent: Extent,
    ) -> Result<(), PhysicalMemoryError> {
        for page_offset in 0..extent.page_count {
            let page = extent
                .start_page
                .checked_add(page_offset)
                .ok_or(PhysicalMemoryError::AddressRange)?;
            let physical = page
                .checked_mul(PAGE_BYTES)
                .ok_or(PhysicalMemoryError::AddressRange)?;
            for word_index in 0..SCRUB_WORDS_PER_PAGE {
                if access.write_word(physical, word_index, 0).is_err() {
                    self.scrub_failures = self.scrub_failures.saturating_add(1);
                    return Err(PhysicalMemoryError::ScrubAccess);
                }
            }
            for word_index in 0..SCRUB_WORDS_PER_PAGE {
                let value = match access.read_word(physical, word_index) {
                    Ok(value) => value,
                    Err(_) => {
                        self.scrub_failures = self.scrub_failures.saturating_add(1);
                        return Err(PhysicalMemoryError::ScrubAccess);
                    }
                };
                if value != 0 {
                    self.scrub_failures = self.scrub_failures.saturating_add(1);
                    return Err(PhysicalMemoryError::ScrubVerification);
                }
            }
        }
        Ok(())
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

    fn plan_allocation(
        &mut self,
        zone: Zone,
        pages: u64,
        owner: u16,
    ) -> Result<AllocationPlan, PhysicalMemoryError> {
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
        self.next_generation
            .checked_add(1)
            .ok_or(PhysicalMemoryError::AddressRange)?;
        self.allocation_count
            .checked_add(1)
            .ok_or(PhysicalMemoryError::AddressRange)?;
        Ok(AllocationPlan {
            slot,
            extent_index,
            generation: self.next_generation,
            start_page,
            page_count: pages,
            zone,
            owner,
        })
    }

    fn commit_allocation(&mut self, plan: AllocationPlan) -> AllocationHandle {
        let extent_index = plan.extent_index;
        let pages = plan.page_count;
        self.free[extent_index].start_page += pages;
        self.free[extent_index].page_count -= pages;
        if self.free[extent_index].page_count == 0 {
            self.remove_free_extent(extent_index);
        }
        self.next_generation += 1;
        self.allocations[plan.slot] = Allocation {
            active: true,
            generation: plan.generation,
            start_page: plan.start_page,
            page_count: pages,
            zone: plan.zone,
            owner: plan.owner,
            metadata_poisoned: false,
            release_excluded: false,
        };
        self.allocated_pages += pages;
        self.allocation_count += 1;
        AllocationHandle {
            slot: plan.slot as u8,
            generation: plan.generation,
            start_page: plan.start_page,
            page_count: pages,
            zone: plan.zone,
            owner: plan.owner,
        }
    }

    pub fn allocate(
        &mut self,
        zone: Zone,
        pages: u64,
        owner: u16,
    ) -> Result<AllocationHandle, PhysicalMemoryError> {
        self.require_operational()?;
        let result = self
            .plan_allocation(zone, pages, owner)
            .map(|plan| self.commit_allocation(plan));
        self.seal_metadata_integrity();
        result
    }

    pub fn allocate_scrubbed<A: PhysicalPageAccess>(
        &mut self,
        zone: Zone,
        pages: u64,
        owner: u16,
        access: &mut A,
    ) -> Result<(AllocationHandle, ScrubReceipt), PhysicalMemoryError> {
        self.require_operational()?;
        let result = (|| {
            let plan = self.plan_allocation(zone, pages, owner)?;
            let receipt = self.scrub_range(
                access,
                ScrubKind::Allocation,
                plan.generation,
                plan.start_page,
                plan.page_count,
                plan.owner,
            )?;
            let handle = self.commit_allocation(plan);
            Ok((handle, receipt))
        })();
        self.seal_metadata_integrity();
        result
    }

    fn validate_allocation_inner(
        &self,
        handle: AllocationHandle,
    ) -> Result<(), PhysicalMemoryError> {
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
            return Err(PhysicalMemoryError::StaleHandle);
        }
        Ok(())
    }

    pub fn validate_allocation(&self, handle: AllocationHandle) -> Result<(), PhysicalMemoryError> {
        self.require_operational()?;
        self.validate_allocation_inner(handle)
    }

    pub fn free(&mut self, handle: AllocationHandle) -> Result<(), PhysicalMemoryError> {
        self.require_operational()?;
        let result = (|| {
            if self.validate_allocation_inner(handle).is_err() {
                self.rejected_double_frees += 1;
                return Err(PhysicalMemoryError::StaleHandle);
            }
            let slot = usize::from(handle.slot);
            let allocation = self.allocations[slot];
            if allocation.release_excluded {
                self.metadata_release_rejections += 1;
                return Err(PhysicalMemoryError::MetadataOwnership);
            }
            let extent = Extent {
                start_page: allocation.start_page,
                page_count: allocation.page_count,
                zone: allocation.zone,
            };
            self.insert_and_coalesce(extent)?;
            self.commit_free(slot, allocation);
            Ok(())
        })();
        self.seal_metadata_integrity();
        result
    }

    pub fn free_scrubbed<A: PhysicalPageAccess>(
        &mut self,
        handle: AllocationHandle,
        access: &mut A,
    ) -> Result<ScrubReceipt, PhysicalMemoryError> {
        self.require_operational()?;
        let result = (|| {
            if self.validate_allocation_inner(handle).is_err() {
                self.rejected_double_frees += 1;
                return Err(PhysicalMemoryError::StaleHandle);
            }
            let slot = usize::from(handle.slot);
            let allocation = self.allocations[slot];
            if allocation.release_excluded {
                self.metadata_release_rejections += 1;
                return Err(PhysicalMemoryError::MetadataOwnership);
            }
            let extent = Extent {
                start_page: allocation.start_page,
                page_count: allocation.page_count,
                zone: allocation.zone,
            };
            self.preflight_insert(extent)?;
            let receipt = self.scrub_range(
                access,
                ScrubKind::Release,
                allocation.generation,
                allocation.start_page,
                allocation.page_count,
                allocation.owner,
            )?;
            self.insert_and_coalesce(extent)?;
            self.commit_free(slot, allocation);
            Ok(receipt)
        })();
        self.seal_metadata_integrity();
        result
    }

    fn commit_free(&mut self, slot: usize, allocation: Allocation) {
        self.allocations[slot].active = false;
        self.allocations[slot].metadata_poisoned = true;
        self.allocated_pages -= allocation.page_count;
        self.free_operation_count += 1;
        self.metadata_poison_events += 1;
    }

    fn scrub_range<A: PhysicalPageAccess>(
        &mut self,
        access: &mut A,
        kind: ScrubKind,
        generation: u64,
        start_page: u64,
        page_count: u64,
        owner: u16,
    ) -> Result<ScrubReceipt, PhysicalMemoryError> {
        let byte_count = page_count
            .checked_mul(PAGE_BYTES)
            .ok_or(PhysicalMemoryError::AddressRange)?;
        let next_sequence = self
            .next_scrub_sequence
            .checked_add(1)
            .ok_or(PhysicalMemoryError::AddressRange)?;
        let next_receipt_count = self
            .scrub_receipt_count
            .checked_add(1)
            .ok_or(PhysicalMemoryError::AddressRange)?;
        if self.receipt_ledger_count == MAX_SCRUB_RECEIPTS {
            return Err(PhysicalMemoryError::ReceiptCapacity);
        }
        let next_zeroed = self
            .scrub_zeroed_bytes
            .checked_add(byte_count)
            .ok_or(PhysicalMemoryError::AddressRange)?;
        let next_verified = self
            .scrub_verified_bytes
            .checked_add(byte_count)
            .ok_or(PhysicalMemoryError::AddressRange)?;
        let next_kind_pages = match kind {
            ScrubKind::Allocation => self.allocation_scrub_pages.checked_add(page_count),
            ScrubKind::Release => self.release_scrub_pages.checked_add(page_count),
        }
        .ok_or(PhysicalMemoryError::AddressRange)?;
        for page_offset in 0..page_count {
            let page = start_page
                .checked_add(page_offset)
                .ok_or(PhysicalMemoryError::AddressRange)?;
            let physical = page
                .checked_mul(PAGE_BYTES)
                .ok_or(PhysicalMemoryError::AddressRange)?;
            for word_index in 0..SCRUB_WORDS_PER_PAGE {
                if access.write_word(physical, word_index, 0).is_err() {
                    self.scrub_failures = self.scrub_failures.saturating_add(1);
                    return Err(PhysicalMemoryError::ScrubAccess);
                }
            }
            for word_index in 0..SCRUB_WORDS_PER_PAGE {
                let value = match access.read_word(physical, word_index) {
                    Ok(value) => value,
                    Err(_) => {
                        self.scrub_failures = self.scrub_failures.saturating_add(1);
                        return Err(PhysicalMemoryError::ScrubAccess);
                    }
                };
                if value != 0 {
                    self.scrub_failures = self.scrub_failures.saturating_add(1);
                    return Err(PhysicalMemoryError::ScrubVerification);
                }
            }
        }
        let receipt = ScrubReceipt {
            sequence: self.next_scrub_sequence,
            kind,
            generation,
            start_page,
            page_count,
            owner,
            zeroed_bytes: byte_count,
            verified_bytes: byte_count,
        };
        self.next_scrub_sequence = next_sequence;
        self.scrub_receipt_count = next_receipt_count;
        self.scrub_receipts[self.receipt_ledger_count] = Some(receipt);
        self.receipt_ledger_count += 1;
        self.scrub_zeroed_bytes = next_zeroed;
        self.scrub_verified_bytes = next_verified;
        match kind {
            ScrubKind::Allocation => self.allocation_scrub_pages = next_kind_pages,
            ScrubKind::Release => self.release_scrub_pages = next_kind_pages,
        }
        Ok(receipt)
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

    fn preflight_insert(&self, extent: Extent) -> Result<(), PhysicalMemoryError> {
        let mut index = 0;
        while index < self.free_count && self.free[index].start_page < extent.start_page {
            index += 1;
        }
        let merge_previous = index > 0 && can_coalesce(self.free[index - 1], extent);
        let merge_next = index < self.free_count && can_coalesce(extent, self.free[index]);
        if merge_previous {
            self.free[index - 1]
                .page_count
                .checked_add(extent.page_count)
                .and_then(|value| {
                    if merge_next {
                        value.checked_add(self.free[index].page_count)
                    } else {
                        Some(value)
                    }
                })
                .ok_or(PhysicalMemoryError::AddressRange)?;
        } else if merge_next {
            extent
                .page_count
                .checked_add(self.free[index].page_count)
                .ok_or(PhysicalMemoryError::AddressRange)?;
        } else if self.free_count == MAX_FREE_EXTENTS {
            return Err(PhysicalMemoryError::ExtentCapacity);
        }
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
            allocation_scrub_pages: self.allocation_scrub_pages,
            release_scrub_pages: self.release_scrub_pages,
            scrub_zeroed_bytes: self.scrub_zeroed_bytes,
            scrub_verified_bytes: self.scrub_verified_bytes,
            scrub_receipt_count: self.scrub_receipt_count,
            scrub_failures: self.scrub_failures,
            source_record_count: self.memory_entry_count,
            receipt_ledger_count: self.receipt_ledger_count,
            metadata_arena_pages: if self.metadata_lifecycle == MetadataLifecycle::Mapped {
                self.metadata_header.arena_page_count
            } else {
                0
            },
            metadata_release_rejections: self.metadata_release_rejections,
            metadata_migration_rollbacks: self.metadata_migration_rollbacks,
            metadata_mapped: self.metadata_lifecycle == MetadataLifecycle::Mapped,
            reclaim_stage: self.reclaim_stage,
            reclaim_operations: self.reclaim_operations,
            reclaim_receipt_count: self.reclaim_receipt_count as u64,
            reclaim_scrub_pages: self.reclaim_scrub_pages,
            reclaimed_pages: self.reclaimed_pages,
            reclaim_timing_rejections: self.reclaim_timing_rejections,
            reclaim_capacity_rejections: self.reclaim_capacity_rejections,
            reclaim_ownership_rejections: self.reclaim_ownership_rejections,
            reclaim_rollbacks: self.reclaim_rollbacks,
        }
    }

    #[cfg(test)]
    pub(crate) fn test_manager(start_page: u64, page_count: u64, quota_pages: u64) -> Self {
        let mut manager = Self::empty(quota_pages);
        manager
            .append_usable(start_page, page_count)
            .expect("test extent must be valid");
        manager
    }
}

fn can_coalesce(first: Extent, second: Extent) -> bool {
    first.zone as u8 == second.zone as u8
        && first.start_page.checked_add(first.page_count) == Some(second.start_page)
}

fn ranges_overlap(
    first_start: u64,
    first_pages: u64,
    second_start: u64,
    second_pages: u64,
) -> Result<bool, PhysicalMemoryError> {
    let first_end = first_start
        .checked_add(first_pages)
        .ok_or(PhysicalMemoryError::AddressRange)?;
    let second_end = second_start
        .checked_add(second_pages)
        .ok_or(PhysicalMemoryError::AddressRange)?;
    Ok(first_start < second_end && second_start < first_end)
}

fn reclaim_receipt_checksum(receipt: ReclaimReceipt) -> u64 {
    let mut state = FNV_OFFSET;
    for value in [
        receipt.sequence,
        receipt.class as u8 as u64,
        receipt.required_stage as u8 as u64,
        receipt.observed_stage as u8 as u64,
        receipt.source_record_count,
        receipt.range_count,
        receipt.page_count,
        receipt.pre_free_extent_count,
        receipt.post_free_extent_count,
        receipt.zeroed_bytes,
        receipt.verified_bytes,
        receipt.range_checksum,
    ] {
        state = fnv_u64(state, value);
    }
    for value in receipt.pages_by_zone {
        state = fnv_u64(state, value);
    }
    state
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
    use std::alloc::{Layout, alloc_zeroed, dealloc};
    use std::ptr::null_mut;
    use std::vec;
    use std::vec::Vec;

    struct FakePageAccess {
        start_page: u64,
        words: Vec<u64>,
        fail_write: Option<(u64, usize)>,
        fail_read: Option<(u64, usize)>,
        drop_write: Option<(u64, usize)>,
        write_count: u64,
        arena_pointer: *mut u8,
        fail_install: bool,
        corrupt_handoff: bool,
        arena_installed: bool,
        uninstall_count: u64,
    }

    impl FakePageAccess {
        fn new(start_page: u64, page_count: u64, fill: u64) -> Self {
            Self {
                start_page,
                words: vec![fill; page_count as usize * SCRUB_WORDS_PER_PAGE],
                fail_write: None,
                fail_read: None,
                drop_write: None,
                write_count: 0,
                arena_pointer: null_mut(),
                fail_install: false,
                corrupt_handoff: false,
                arena_installed: false,
                uninstall_count: 0,
            }
        }

        fn index(
            &self,
            physical_address: u64,
            word_index: usize,
        ) -> Result<usize, PageAccessError> {
            if !physical_address.is_multiple_of(PAGE_BYTES) || word_index >= SCRUB_WORDS_PER_PAGE {
                return Err(PageAccessError::Access);
            }
            let page = physical_address / PAGE_BYTES;
            let offset = page
                .checked_sub(self.start_page)
                .ok_or(PageAccessError::Access)?;
            let index = offset as usize * SCRUB_WORDS_PER_PAGE + word_index;
            if index >= self.words.len() {
                return Err(PageAccessError::Access);
            }
            Ok(index)
        }
    }

    impl Drop for FakePageAccess {
        fn drop(&mut self) {
            if !self.arena_pointer.is_null() {
                let layout =
                    Layout::from_size_align(METADATA_ARENA_BYTE_CAPACITY, PAGE_BYTES as usize)
                        .unwrap();
                // SAFETY: arena_pointer was allocated once with this exact layout.
                unsafe { dealloc(self.arena_pointer, layout) };
            }
        }
    }

    impl PhysicalPageAccess for FakePageAccess {
        fn write_word(
            &mut self,
            physical_address: u64,
            word_index: usize,
            value: u64,
        ) -> Result<(), PageAccessError> {
            let page = physical_address / PAGE_BYTES;
            if self.fail_write == Some((page, word_index)) {
                return Err(PageAccessError::Access);
            }
            let index = self.index(physical_address, word_index)?;
            self.write_count += 1;
            if self.drop_write != Some((page, word_index)) {
                self.words[index] = value;
            }
            Ok(())
        }

        fn read_word(
            &mut self,
            physical_address: u64,
            word_index: usize,
        ) -> Result<u64, PageAccessError> {
            let page = physical_address / PAGE_BYTES;
            if self.fail_read == Some((page, word_index)) {
                return Err(PageAccessError::Access);
            }
            let index = self.index(physical_address, word_index)?;
            Ok(self.words[index])
        }
    }

    impl MetadataArenaAccess for FakePageAccess {
        fn install_metadata_arena(
            &mut self,
            _physical_address: u64,
            page_count: u64,
        ) -> Result<u64, PageAccessError> {
            if self.fail_install || self.arena_installed || page_count != METADATA_ARENA_PAGE_COUNT
            {
                return Err(PageAccessError::Access);
            }
            if self.arena_pointer.is_null() {
                let layout =
                    Layout::from_size_align(METADATA_ARENA_BYTE_CAPACITY, PAGE_BYTES as usize)
                        .map_err(|_| PageAccessError::Access)?;
                // SAFETY: the validated layout is nonzero and page aligned.
                self.arena_pointer = unsafe { alloc_zeroed(layout) };
                if self.arena_pointer.is_null() {
                    return Err(PageAccessError::Access);
                }
            }
            self.arena_installed = true;
            Ok(self.arena_pointer as usize as u64)
        }

        fn finalize_metadata_handoff(
            &mut self,
            virtual_address: u64,
            manager_byte_count: u64,
        ) -> Result<(), PageAccessError> {
            if !self.arena_installed
                || virtual_address != self.arena_pointer as usize as u64
                || manager_byte_count != core::mem::size_of::<PhysicalMemoryManager>() as u64
            {
                return Err(PageAccessError::Access);
            }
            if self.corrupt_handoff {
                // SAFETY: install_metadata_arena returned storage for a complete manager,
                // and migrate_to_metadata copied that manager before this callback.
                let manager =
                    unsafe { &mut *(virtual_address as usize as *mut PhysicalMemoryManager) };
                manager.free[0].page_count ^= 1;
            }
            Ok(())
        }

        fn uninstall_metadata_arena(
            &mut self,
            virtual_address: u64,
            page_count: u64,
        ) -> Result<(), PageAccessError> {
            if !self.arena_installed
                || virtual_address != self.arena_pointer as usize as u64
                || page_count != METADATA_ARENA_PAGE_COUNT
            {
                return Err(PageAccessError::Access);
            }
            self.arena_installed = false;
            self.uninstall_count += 1;
            Ok(())
        }
    }

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

    fn reclaim_fixture() -> (Vec<u8>, CoreRecord) {
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
            entry(0x0208_0000, 4, MEMORY_ACPI_RECLAIMABLE, 9),
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
    fn manager_fits_the_guarded_metadata_arena() {
        assert_eq!(14928, core::mem::size_of::<PhysicalMemoryManager>());
        assert!(14928 <= METADATA_ARENA_BYTE_CAPACITY);
        assert!(core::mem::size_of::<ReclaimPlan>() <= 160);
        assert!(core::mem::size_of::<ReclaimCursor>() <= 64);
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
    fn held_classes_require_monotonic_lifecycle_and_reclaim_idempotently() {
        let (bytes, core) = reclaim_fixture();
        let handoff = poole_handoff::decode(&bytes).unwrap();
        let mut manager = PhysicalMemoryManager::from_handoff(&handoff, core, 64).unwrap();
        let boot_page = 0x0206_0000 / PAGE_BYTES;
        let mut access = FakePageAccess::new(boot_page, 36, STALE_PATTERN);
        assert_eq!(
            manager.reclaim_held(ReclaimClass::BootServices, &mut access),
            Err(PhysicalMemoryError::ReclaimTiming)
        );
        assert_eq!(
            manager.advance_reclaim_stage(ReclaimStage::AcpiTablesReleased),
            Err(PhysicalMemoryError::ReclaimTiming)
        );
        assert_eq!(0, access.write_count);
        manager
            .advance_reclaim_stage(ReclaimStage::PostExitBootServices)
            .unwrap();
        let boot = manager
            .reclaim_held(ReclaimClass::BootServices, &mut access)
            .unwrap();
        assert!(boot.newly_reclaimed);
        assert_eq!(32, boot.receipt.page_count);
        assert_eq!([0, 32, 0], boot.receipt.pages_by_zone);
        assert_eq!(1, boot.receipt.source_record_count);
        assert_eq!(1, boot.receipt.range_count);
        assert_ne!(0, boot.receipt.range_checksum);
        assert_eq!(
            boot.receipt.receipt_checksum,
            reclaim_receipt_checksum(boot.receipt)
        );
        assert!(
            access.words[..32 * SCRUB_WORDS_PER_PAGE]
                .iter()
                .all(|word| *word == 0)
        );
        assert!(
            access.words[32 * SCRUB_WORDS_PER_PAGE..]
                .iter()
                .all(|word| *word == STALE_PATTERN)
        );
        let writes_after_boot = access.write_count;
        let repeated = manager
            .reclaim_held(ReclaimClass::BootServices, &mut access)
            .unwrap();
        assert!(!repeated.newly_reclaimed);
        assert_eq!(boot.receipt, repeated.receipt);
        assert_eq!(writes_after_boot, access.write_count);
        assert_eq!(
            manager.reclaim_held(ReclaimClass::Acpi, &mut access),
            Err(PhysicalMemoryError::ReclaimTiming)
        );
        manager
            .advance_reclaim_stage(ReclaimStage::AcpiTablesReleased)
            .unwrap();
        let acpi = manager
            .reclaim_held(ReclaimClass::Acpi, &mut access)
            .unwrap();
        assert!(acpi.newly_reclaimed);
        assert_eq!(4, acpi.receipt.page_count);
        assert_eq!([0, 4, 0], acpi.receipt.pages_by_zone);
        assert!(access.words.iter().all(|word| *word == 0));
        let summary = manager.summary();
        assert_eq!(ReclaimStage::AcpiTablesReleased, summary.reclaim_stage);
        assert_eq!(2, summary.reclaim_operations);
        assert_eq!(2, summary.reclaim_receipt_count);
        assert_eq!(36, summary.reclaim_scrub_pages);
        assert_eq!([32, 4], summary.reclaimed_pages);
        assert_eq!(3, summary.reclaim_timing_rejections);
        assert_eq!([4095, 4132, 128], summary.managed_pages);
    }

    #[test]
    fn mapped_manager_reclaims_boot_services_and_preserves_its_seal() {
        let (bytes, core) = reclaim_fixture();
        let handoff = poole_handoff::decode(&bytes).unwrap();
        let mut bootstrap = PhysicalMemoryManager::from_handoff(&handoff, core, 64).unwrap();
        let acpi_end_page = 0x0208_4000 / PAGE_BYTES;
        let mut access =
            FakePageAccess::new(DMA_END_PAGE, acpi_end_page - DMA_END_PAGE, STALE_PATTERN);
        let migration = bootstrap.migrate_to_metadata(&mut access).unwrap();
        // SAFETY: migration returned a sealed manager in the fake page-aligned arena.
        let manager =
            unsafe { &mut *(migration.manager_address as usize as *mut PhysicalMemoryManager) };
        manager
            .advance_reclaim_stage(ReclaimStage::PostExitBootServices)
            .unwrap();
        let outcome = manager
            .reclaim_held(ReclaimClass::BootServices, &mut access)
            .unwrap();
        assert!(outcome.newly_reclaimed);
        assert_eq!(32, outcome.receipt.page_count);
        assert_eq!(Ok(()), manager.verify_metadata_integrity());
        assert_eq!(1, manager.summary().reclaim_operations);
        assert_eq!(METADATA_ARENA_PAGE_COUNT, manager.summary().allocated_pages);
    }

    #[test]
    fn reclaim_scrub_fault_preserves_held_ownership_and_receipt_sequence() {
        let (bytes, core) = reclaim_fixture();
        let handoff = poole_handoff::decode(&bytes).unwrap();
        let mut manager = PhysicalMemoryManager::from_handoff(&handoff, core, 64).unwrap();
        manager
            .advance_reclaim_stage(ReclaimStage::PostExitBootServices)
            .unwrap();
        let boot_page = 0x0206_0000 / PAGE_BYTES;
        let mut access = FakePageAccess::new(boot_page, 32, STALE_PATTERN);
        access.fail_write = Some((boot_page + 1, 0));
        let before = manager.summary();
        assert_eq!(
            manager.reclaim_held(ReclaimClass::BootServices, &mut access),
            Err(PhysicalMemoryError::ScrubAccess)
        );
        let failed = manager.summary();
        assert_eq!(before.free_extent_count, failed.free_extent_count);
        assert_eq!(before.managed_pages, failed.managed_pages);
        assert_eq!(0, failed.reclaim_operations);
        assert_eq!(0, failed.reclaim_receipt_count);
        assert_eq!([0, 0], failed.reclaimed_pages);
        assert_eq!(1, failed.reclaim_rollbacks);
        assert_eq!(1, failed.scrub_failures);
        access.fail_write = None;
        let recovered = manager
            .reclaim_held(ReclaimClass::BootServices, &mut access)
            .unwrap();
        assert_eq!(1, recovered.receipt.sequence);
        assert_eq!(32, recovered.receipt.page_count);
    }

    #[test]
    fn reclaim_capacity_and_retained_overlap_fail_before_physical_writes() {
        let mut capacity = PhysicalMemoryManager::empty(64);
        for index in 0..MAX_FREE_EXTENTS {
            capacity.free[index] = Extent {
                start_page: 1 + index as u64 * 2,
                page_count: 1,
                zone: Zone::Dma,
            };
        }
        capacity.free_count = MAX_FREE_EXTENTS;
        capacity.memory_entry_count = 1;
        capacity.source_records[0] = SourceRecord {
            start_page: 700,
            page_count: 1,
            kind: MEMORY_BOOT_RECLAIMABLE,
            source: 4,
        };
        capacity.source_pages[MEMORY_BOOT_RECLAIMABLE as usize] = 1;
        capacity
            .advance_reclaim_stage(ReclaimStage::PostExitBootServices)
            .unwrap();
        let mut capacity_access = FakePageAccess::new(700, 1, STALE_PATTERN);
        assert_eq!(
            capacity.reclaim_held(ReclaimClass::BootServices, &mut capacity_access),
            Err(PhysicalMemoryError::ReclaimCapacity)
        );
        assert_eq!(0, capacity_access.write_count);
        assert_eq!(1, capacity.summary().reclaim_capacity_rejections);

        let mut overlap = PhysicalMemoryManager::empty(64);
        overlap.memory_entry_count = 2;
        overlap.source_records[0] = SourceRecord {
            start_page: 700,
            page_count: 1,
            kind: MEMORY_BOOT_RECLAIMABLE,
            source: 4,
        };
        overlap.source_records[1] = SourceRecord {
            start_page: 700,
            page_count: 1,
            kind: MEMORY_LOADER_RESERVED,
            source: 2,
        };
        overlap
            .advance_reclaim_stage(ReclaimStage::PostExitBootServices)
            .unwrap();
        let mut overlap_access = FakePageAccess::new(700, 1, STALE_PATTERN);
        assert_eq!(
            overlap.reclaim_held(ReclaimClass::BootServices, &mut overlap_access),
            Err(PhysicalMemoryError::ReclaimOwnership)
        );
        assert_eq!(0, overlap_access.write_count);
        assert_eq!(1, overlap.summary().reclaim_ownership_rejections);
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
            release_excluded: false,
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
            release_excluded: false,
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

    #[test]
    fn metadata_arena_migrates_full_ledgers_and_excludes_release() {
        let (bytes, core) = fixture();
        let handoff = poole_handoff::decode(&bytes).unwrap();
        let mut bootstrap = PhysicalMemoryManager::from_handoff(&handoff, core, 64).unwrap();
        let mut access = FakePageAccess::new(DMA_END_PAGE, 64, STALE_PATTERN);
        let migration = bootstrap.migrate_to_metadata(&mut access).unwrap();
        assert_eq!(
            bootstrap.allocate(Zone::Dma32, 1, 1),
            Err(PhysicalMemoryError::MetadataState)
        );
        // SAFETY: migration returned a sealed manager in the fake page-aligned arena.
        let manager =
            unsafe { &mut *(migration.manager_address as usize as *mut PhysicalMemoryManager) };
        assert_eq!(Ok(()), manager.verify_metadata_integrity());
        assert_eq!(5, manager.memory_entry_count);
        assert_eq!(
            5,
            manager
                .source_records
                .iter()
                .filter(|item| item.page_count != 0)
                .count()
        );
        assert_eq!(1, manager.receipt_ledger_count);
        assert_eq!(
            Some(ScrubKind::Allocation),
            manager.scrub_receipts[0].map(|item| item.kind)
        );
        assert_eq!(METADATA_ARENA_PAGE_COUNT, manager.summary().allocated_pages);
        assert_eq!(METADATA_ARENA_PAGE_COUNT, migration.receipt.page_count);
        assert_eq!(
            METADATA_GUARD_PAGE_COUNT,
            migration.receipt.guard_page_count
        );
        assert_eq!(METADATA_OWNER, migration.receipt.owner);
        assert!(migration.receipt.release_excluded);
        assert!(migration.receipt.integrity_verified);
        assert_eq!(
            manager.free_scrubbed(migration.allocation, &mut access),
            Err(PhysicalMemoryError::MetadataOwnership)
        );
        assert_eq!(1, manager.summary().metadata_release_rejections);
        assert_eq!(Ok(()), manager.verify_metadata_integrity());
    }

    #[test]
    fn metadata_mapping_failure_rolls_back_reserved_pages() {
        let (bytes, core) = fixture();
        let handoff = poole_handoff::decode(&bytes).unwrap();
        let mut manager = PhysicalMemoryManager::from_handoff(&handoff, core, 64).unwrap();
        let before = manager.summary();
        let mut access = FakePageAccess::new(DMA_END_PAGE, 64, STALE_PATTERN);
        access.fail_install = true;
        assert_eq!(
            manager.migrate_to_metadata(&mut access),
            Err(PhysicalMemoryError::MetadataMapping)
        );
        let after = manager.summary();
        assert_eq!(0, after.allocated_pages);
        assert_eq!(before.free_extent_count, after.free_extent_count);
        assert_eq!(before.largest_free_pages, after.largest_free_pages);
        assert_eq!(1, after.metadata_migration_rollbacks);
        assert_eq!(2, after.receipt_ledger_count);
        assert!(!access.arena_installed);
    }

    #[test]
    fn metadata_handoff_corruption_unmaps_and_rolls_back() {
        let (bytes, core) = fixture();
        let handoff = poole_handoff::decode(&bytes).unwrap();
        let mut manager = PhysicalMemoryManager::from_handoff(&handoff, core, 64).unwrap();
        let before = manager.summary();
        let mut access = FakePageAccess::new(DMA_END_PAGE, 64, STALE_PATTERN);
        access.corrupt_handoff = true;
        assert_eq!(
            manager.migrate_to_metadata(&mut access),
            Err(PhysicalMemoryError::MetadataCorruption)
        );
        let after = manager.summary();
        assert_eq!(0, after.allocated_pages);
        assert_eq!(before.largest_free_pages, after.largest_free_pages);
        assert_eq!(1, after.metadata_migration_rollbacks);
        assert_eq!(1, access.uninstall_count);
        assert!(!access.arena_installed);
    }

    #[test]
    fn mapped_metadata_corruption_rejects_the_next_operation() {
        let (bytes, core) = fixture();
        let handoff = poole_handoff::decode(&bytes).unwrap();
        let mut bootstrap = PhysicalMemoryManager::from_handoff(&handoff, core, 64).unwrap();
        let mut access = FakePageAccess::new(DMA_END_PAGE, 64, STALE_PATTERN);
        let migration = bootstrap.migrate_to_metadata(&mut access).unwrap();
        // SAFETY: migration returned a sealed manager in the fake page-aligned arena.
        let manager =
            unsafe { &mut *(migration.manager_address as usize as *mut PhysicalMemoryManager) };
        manager.free[0].page_count ^= 1;
        assert_eq!(
            manager.allocate(Zone::Dma32, 1, 1),
            Err(PhysicalMemoryError::MetadataCorruption)
        );
        assert_eq!(
            manager.verify_metadata_integrity(),
            Err(PhysicalMemoryError::MetadataCorruption)
        );
    }

    #[test]
    fn scrubbed_lifecycle_removes_stale_pattern_before_generation_reuse() {
        let start = DMA_END_PAGE;
        let mut manager = PhysicalMemoryManager::test_manager(start, 4, 64);
        let mut access = FakePageAccess::new(start, 4, STALE_PATTERN);
        let (first, first_receipt) = manager
            .allocate_scrubbed(Zone::Dma32, 2, 1, &mut access)
            .unwrap();
        assert_eq!(ScrubKind::Allocation, first_receipt.kind);
        assert_eq!(1, first_receipt.sequence);
        assert!(
            access.words[..2 * SCRUB_WORDS_PER_PAGE]
                .iter()
                .all(|word| *word == 0)
        );
        for word in &mut access.words[..2 * SCRUB_WORDS_PER_PAGE] {
            *word = STALE_PATTERN;
        }
        let release = manager.free_scrubbed(first, &mut access).unwrap();
        assert_eq!(ScrubKind::Release, release.kind);
        assert_eq!(2, release.sequence);
        let (reused, reuse_receipt) = manager
            .allocate_scrubbed(Zone::Dma32, 2, 2, &mut access)
            .unwrap();
        assert_eq!(first.start_page, reused.start_page);
        assert!(reused.generation > first.generation);
        assert_eq!(3, reuse_receipt.sequence);
        assert!(
            access.words[..2 * SCRUB_WORDS_PER_PAGE]
                .iter()
                .all(|word| *word == 0)
        );
        let final_release = manager.free_scrubbed(reused, &mut access).unwrap();
        assert_eq!(4, final_release.sequence);
        let summary = manager.summary();
        assert_eq!(4, summary.allocation_scrub_pages);
        assert_eq!(4, summary.release_scrub_pages);
        assert_eq!(8 * PAGE_BYTES, summary.scrub_zeroed_bytes);
        assert_eq!(summary.scrub_zeroed_bytes, summary.scrub_verified_bytes);
        assert_eq!(4, summary.scrub_receipt_count);
        assert_eq!(0, summary.scrub_failures);
    }

    #[test]
    fn partial_allocation_scrub_failure_preserves_allocator_ownership_state() {
        let start = DMA_END_PAGE;
        let mut manager = PhysicalMemoryManager::test_manager(start, 4, 64);
        let before = manager.summary();
        let mut access = FakePageAccess::new(start, 4, STALE_PATTERN);
        access.fail_write = Some((start + 1, 0));
        assert_eq!(
            manager.allocate_scrubbed(Zone::Dma32, 2, 1, &mut access),
            Err(PhysicalMemoryError::ScrubAccess)
        );
        let failed = manager.summary();
        assert_eq!(before.allocated_pages, failed.allocated_pages);
        assert_eq!(before.free_extent_count, failed.free_extent_count);
        assert_eq!(before.largest_free_pages, failed.largest_free_pages);
        assert_eq!(0, failed.allocation_count);
        assert_eq!(0, failed.scrub_receipt_count);
        assert_eq!(1, failed.scrub_failures);
        access.fail_write = None;
        let (handle, receipt) = manager
            .allocate_scrubbed(Zone::Dma32, 2, 1, &mut access)
            .unwrap();
        assert_eq!(start, handle.start_page);
        assert_eq!(1, handle.generation);
        assert_eq!(1, receipt.sequence);
    }

    #[test]
    fn release_verification_failure_keeps_the_handle_live() {
        let start = DMA_END_PAGE;
        let mut manager = PhysicalMemoryManager::test_manager(start, 2, 64);
        let mut access = FakePageAccess::new(start, 2, STALE_PATTERN);
        let (handle, _) = manager
            .allocate_scrubbed(Zone::Dma32, 1, 1, &mut access)
            .unwrap();
        access.words[0] = STALE_PATTERN;
        access.drop_write = Some((start, 0));
        assert_eq!(
            manager.free_scrubbed(handle, &mut access),
            Err(PhysicalMemoryError::ScrubVerification)
        );
        assert_eq!(Ok(()), manager.validate_allocation(handle));
        let summary = manager.summary();
        assert_eq!(1, summary.allocated_pages);
        assert_eq!(0, summary.free_count);
        assert_eq!(1, summary.scrub_receipt_count);
        assert_eq!(1, summary.scrub_failures);
    }

    #[test]
    fn scrubbed_free_preflights_extent_capacity_before_content_writes() {
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
            release_excluded: false,
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
        let mut access = FakePageAccess::new(700, 1, STALE_PATTERN);
        assert_eq!(
            manager.free_scrubbed(handle, &mut access),
            Err(PhysicalMemoryError::ExtentCapacity)
        );
        assert_eq!(0, access.write_count);
        assert_eq!(Ok(()), manager.validate_allocation(handle));
        assert_eq!(0, manager.summary().scrub_receipt_count);
    }
}
