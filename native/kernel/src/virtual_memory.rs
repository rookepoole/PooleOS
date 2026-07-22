use poole_handoff::{CoreRecord, Handoff, PAGE_BYTES};

use crate::physical_memory::{AllocationHandle, PhysicalMemoryManager, Zone};

pub const CONTRACT_ID: &str = "PKVM1";
pub const TABLE_PAGE_COUNT: u64 = 4;
pub const TABLE_ENTRIES: usize = 512;
pub const MAX_MAPPINGS: usize = 8;
pub const MAX_FRAMES: usize = 4;
pub const MAX_PENDING_INVALIDATIONS: usize = 8;
pub const TABLE_OWNER: u16 = 0x0901;
pub const DATA_OWNER: u16 = 0x0902;

pub const NULL_GUARD_END: u64 = 0x0000_0000_0001_0000;
pub const USER_END_EXCLUSIVE: u64 = 0x0000_8000_0000_0000;
pub const KERNEL_START: u64 = 0xffff_8000_0000_0000;
pub const DIRECT_MAP_START: u64 = 0xffff_9000_0000_0000;
pub const DIRECT_MAP_END_EXCLUSIVE: u64 = 0xffff_d000_0000_0000;
pub const TEMPORARY_MAP_START: u64 = 0xffff_ffff_8015_0000;
pub const TEMPORARY_MAP_END_EXCLUSIVE: u64 = TEMPORARY_MAP_START + PAGE_BYTES;
pub const KERNEL_IMAGE_START: u64 = 0xffff_ffff_8000_0000;
pub const KERNEL_IMAGE_END_EXCLUSIVE: u64 = 0xffff_ffff_c000_0000;
pub const USER_WINDOW_START: u64 = 0x0000_0000_4000_0000;
pub const USER_WINDOW_END_EXCLUSIVE: u64 = USER_WINDOW_START + 2 * 1024 * 1024;

const ENTRY_PRESENT: u64 = 1 << 0;
const ENTRY_WRITABLE: u64 = 1 << 1;
const ENTRY_USER: u64 = 1 << 2;
const ENTRY_PWT: u64 = 1 << 3;
const ENTRY_PCD: u64 = 1 << 4;
const ENTRY_LARGE_OR_PAT: u64 = 1 << 7;
const ENTRY_NO_EXECUTE: u64 = 1 << 63;
const PHYSICAL_MASK_52: u64 = 0x000f_ffff_ffff_f000;
const PARENT_FLAGS: u64 = ENTRY_PRESENT | ENTRY_WRITABLE | ENTRY_USER;

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum Region {
    NullGuard,
    User,
    NonCanonical,
    Kernel,
    DirectMap,
    TemporaryMap,
    KernelImage,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum Error {
    Pmm,
    TableAllocation,
    DataAllocation,
    Address,
    UnsupportedRegion,
    Permission,
    PhysicalAddress,
    MemoryAccess,
    BootstrapRoot,
    BootstrapRetainedIdentity,
    BootstrapLeafOccupied,
    BootstrapTargetAddress,
    BootstrapLeafState,
    BootstrapTranslation,
    BootstrapRevocation,
    ParentEntry,
    AlreadyMapped,
    MappingMissing,
    MappingCapacity,
    FrameCapacity,
    CacheAlias,
    Ownership,
    TransactionRejected,
    RollbackFailed,
    PendingCapacity,
    InvalidationRequired,
    StaleInvalidation,
    ActiveRootUnsupported,
    ReleaseBusy,
    ExerciseInvariant,
}

macro_rules! vm_label {
    ($name:ident, $value:literal) => {
        #[used]
        #[unsafe(link_section = ".text.pkvm_labels")]
        static $name: [u8; $value.len()] = *$value;
    };
}

vm_label!(VM_LABEL_OWNERSHIP, b"ownership");
vm_label!(VM_LABEL_ADDRESS, b"address");
vm_label!(VM_LABEL_PROTECTION, b"protection");
vm_label!(VM_LABEL_TABLE_ACCESS, b"table_access");
vm_label!(VM_LABEL_BOOTSTRAP_ROOT, b"bootstrap_root");
vm_label!(
    VM_LABEL_BOOTSTRAP_RETAINED_IDENTITY,
    b"bootstrap_retained_identity"
);
vm_label!(VM_LABEL_BOOTSTRAP_LEAF_OCCUPIED, b"bootstrap_leaf_occupied");
vm_label!(
    VM_LABEL_BOOTSTRAP_TARGET_ADDRESS,
    b"bootstrap_target_address"
);
vm_label!(VM_LABEL_BOOTSTRAP_LEAF_STATE, b"bootstrap_leaf_state");
vm_label!(VM_LABEL_BOOTSTRAP_TRANSLATION, b"bootstrap_translation");
vm_label!(VM_LABEL_BOOTSTRAP_REVOCATION, b"bootstrap_revocation");
vm_label!(VM_LABEL_MAPPING_STATE, b"mapping_state");
vm_label!(VM_LABEL_CAPACITY, b"capacity");
vm_label!(VM_LABEL_TRANSACTION, b"transaction");
vm_label!(VM_LABEL_INVALIDATION, b"invalidation");
vm_label!(VM_LABEL_LIFECYCLE, b"lifecycle");
vm_label!(VM_LABEL_EXERCISE, b"exercise_invariant");

const fn vm_label_text(bytes: &'static [u8]) -> &'static str {
    // SAFETY: every caller passes an ASCII byte string declared immediately above.
    unsafe { core::str::from_utf8_unchecked(bytes) }
}

impl Error {
    pub const fn label(self) -> &'static str {
        match self {
            Self::Pmm | Self::TableAllocation | Self::DataAllocation | Self::Ownership => {
                vm_label_text(&VM_LABEL_OWNERSHIP)
            }
            Self::Address | Self::UnsupportedRegion | Self::PhysicalAddress => {
                vm_label_text(&VM_LABEL_ADDRESS)
            }
            Self::Permission | Self::CacheAlias => vm_label_text(&VM_LABEL_PROTECTION),
            Self::MemoryAccess | Self::ParentEntry => vm_label_text(&VM_LABEL_TABLE_ACCESS),
            Self::BootstrapRoot => vm_label_text(&VM_LABEL_BOOTSTRAP_ROOT),
            Self::BootstrapRetainedIdentity => vm_label_text(&VM_LABEL_BOOTSTRAP_RETAINED_IDENTITY),
            Self::BootstrapLeafOccupied => vm_label_text(&VM_LABEL_BOOTSTRAP_LEAF_OCCUPIED),
            Self::BootstrapTargetAddress => vm_label_text(&VM_LABEL_BOOTSTRAP_TARGET_ADDRESS),
            Self::BootstrapLeafState => vm_label_text(&VM_LABEL_BOOTSTRAP_LEAF_STATE),
            Self::BootstrapTranslation => vm_label_text(&VM_LABEL_BOOTSTRAP_TRANSLATION),
            Self::BootstrapRevocation => vm_label_text(&VM_LABEL_BOOTSTRAP_REVOCATION),
            Self::AlreadyMapped | Self::MappingMissing => vm_label_text(&VM_LABEL_MAPPING_STATE),
            Self::MappingCapacity | Self::FrameCapacity | Self::PendingCapacity => {
                vm_label_text(&VM_LABEL_CAPACITY)
            }
            Self::TransactionRejected | Self::RollbackFailed => {
                vm_label_text(&VM_LABEL_TRANSACTION)
            }
            Self::InvalidationRequired | Self::StaleInvalidation => {
                vm_label_text(&VM_LABEL_INVALIDATION)
            }
            Self::ActiveRootUnsupported | Self::ReleaseBusy => vm_label_text(&VM_LABEL_LIFECYCLE),
            Self::ExerciseInvariant => vm_label_text(&VM_LABEL_EXERCISE),
        }
    }
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct Permissions {
    pub read: bool,
    pub write: bool,
    pub execute: bool,
    pub user: bool,
}

impl Permissions {
    pub const USER_RW: Self = Self {
        read: true,
        write: true,
        execute: false,
        user: true,
    };

    pub const USER_RX: Self = Self {
        read: true,
        write: false,
        execute: true,
        user: true,
    };

    const fn valid(self) -> bool {
        self.read && !(self.write && self.execute) && self.user
    }
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum CachePolicy {
    WriteBack,
    Uncacheable,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct Translation {
    pub physical_address: u64,
    pub permissions: Permissions,
    pub cache: CachePolicy,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct InvalidationToken {
    sequence: u64,
    root_generation: u64,
    virtual_address: u64,
    frame_generation: u64,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
struct MappingRecord {
    virtual_address: u64,
    frame: AllocationHandle,
    permissions: Permissions,
    cache: CachePolicy,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
struct FrameRecord {
    frame: AllocationHandle,
    cache: CachePolicy,
    mapping_count: u8,
    pending_count: u8,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
struct PendingInvalidation {
    token: InvalidationToken,
    frame: AllocationHandle,
    acknowledged: bool,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct Summary {
    pub root_physical: u64,
    pub root_generation: u64,
    pub table_pages: u64,
    pub active_mappings: usize,
    pub bound_frames: usize,
    pub pending_invalidations: usize,
    pub map_operations: u64,
    pub protect_operations: u64,
    pub unmap_operations: u64,
    pub invalidation_receipts: u64,
    pub released_frames: u64,
    pub root_active: bool,
    pub root_released: bool,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct VirtualMemoryProof {
    pub root_physical: u64,
    pub table_generation: u64,
    pub data_physical: u64,
    pub data_generation: u64,
    pub mapped_translation: Translation,
    pub protected_translation: Translation,
    pub cache_alias_rejected: bool,
    pub writable_executable_rejected: bool,
    pub premature_reuse_rejected: bool,
    pub final_space: Summary,
    pub physical_write_count: u64,
    pub temporary_pte_write_count: u64,
    pub hardware_invalidation_count: u64,
    pub final_allocated_pages: u64,
    pub final_allocation_count: u64,
    pub final_free_count: u64,
}

pub trait TableMemory {
    fn prepare_page(&mut self, physical_address: u64) -> Result<(), Error>;
    fn read_entry(&mut self, table_address: u64, index: usize) -> Result<u64, Error>;
    fn write_entry(&mut self, table_address: u64, index: usize, value: u64) -> Result<(), Error>;
    fn finish(&mut self) -> Result<(), Error>;
    fn physical_write_count(&self) -> u64;
    fn temporary_pte_write_count(&self) -> u64;
    fn hardware_invalidation_count(&self) -> u64;
}

pub const fn is_canonical_48(address: u64) -> bool {
    let upper = address >> 48;
    upper == if address & (1 << 47) == 0 { 0 } else { 0xffff }
}

pub const fn classify(address: u64) -> Region {
    if !is_canonical_48(address) {
        Region::NonCanonical
    } else if address < NULL_GUARD_END {
        Region::NullGuard
    } else if address < USER_END_EXCLUSIVE {
        Region::User
    } else if address >= TEMPORARY_MAP_START && address < TEMPORARY_MAP_END_EXCLUSIVE {
        Region::TemporaryMap
    } else if address >= KERNEL_IMAGE_START && address < KERNEL_IMAGE_END_EXCLUSIVE {
        Region::KernelImage
    } else if address >= DIRECT_MAP_START && address < DIRECT_MAP_END_EXCLUSIVE {
        Region::DirectMap
    } else {
        Region::Kernel
    }
}

const fn table_indices(address: u64) -> [usize; 4] {
    [
        ((address >> 39) & 0x1ff) as usize,
        ((address >> 30) & 0x1ff) as usize,
        ((address >> 21) & 0x1ff) as usize,
        ((address >> 12) & 0x1ff) as usize,
    ]
}

fn physical_address(handle: AllocationHandle) -> Result<u64, Error> {
    handle
        .start_page
        .checked_mul(PAGE_BYTES)
        .filter(|address| *address != 0 && *address & !PHYSICAL_MASK_52 == 0)
        .ok_or(Error::PhysicalAddress)
}

fn leaf_entry(
    frame: AllocationHandle,
    permissions: Permissions,
    cache: CachePolicy,
) -> Result<u64, Error> {
    if !permissions.valid() || frame.page_count != 1 || frame.owner == 0 {
        return Err(Error::Permission);
    }
    let mut value = physical_address(frame)? | ENTRY_PRESENT | ENTRY_USER;
    if permissions.write {
        value |= ENTRY_WRITABLE;
    }
    if !permissions.execute {
        value |= ENTRY_NO_EXECUTE;
    }
    if cache == CachePolicy::Uncacheable {
        value |= ENTRY_PWT | ENTRY_PCD;
    }
    Ok(value)
}

fn decode_leaf(value: u64, virtual_address: u64) -> Result<Translation, Error> {
    if value & ENTRY_PRESENT == 0 || value & ENTRY_LARGE_OR_PAT != 0 {
        return Err(Error::MappingMissing);
    }
    Ok(Translation {
        physical_address: (value & PHYSICAL_MASK_52) | (virtual_address & (PAGE_BYTES - 1)),
        permissions: Permissions {
            read: true,
            write: value & ENTRY_WRITABLE != 0,
            execute: value & ENTRY_NO_EXECUTE == 0,
            user: value & ENTRY_USER != 0,
        },
        cache: if value & (ENTRY_PWT | ENTRY_PCD) == ENTRY_PWT | ENTRY_PCD {
            CachePolicy::Uncacheable
        } else if value & (ENTRY_PWT | ENTRY_PCD) == 0 {
            CachePolicy::WriteBack
        } else {
            return Err(Error::MemoryAccess);
        },
    })
}

fn replace_entry<M: TableMemory>(
    memory: &mut M,
    table: u64,
    index: usize,
    expected: u64,
    replacement: u64,
) -> Result<(), Error> {
    if memory.read_entry(table, index)? != expected {
        return Err(Error::TransactionRejected);
    }
    let write_succeeded = memory.write_entry(table, index, replacement).is_ok();
    let verified = write_succeeded && memory.read_entry(table, index) == Ok(replacement);
    if verified {
        return Ok(());
    }
    if memory.write_entry(table, index, expected).is_err()
        || memory.read_entry(table, index) != Ok(expected)
    {
        return Err(Error::RollbackFailed);
    }
    Err(Error::TransactionRejected)
}

pub struct AddressSpace {
    table_allocation: AllocationHandle,
    tables: [u64; 4],
    mappings: [Option<MappingRecord>; MAX_MAPPINGS],
    frames: [Option<FrameRecord>; MAX_FRAMES],
    pending: [Option<PendingInvalidation>; MAX_PENDING_INVALIDATIONS],
    next_invalidation: u64,
    map_operations: u64,
    protect_operations: u64,
    unmap_operations: u64,
    invalidation_receipts: u64,
    released_frames: u64,
    active: bool,
    released: bool,
}

impl AddressSpace {
    pub fn initialize<M: TableMemory>(
        manager: &PhysicalMemoryManager,
        table_allocation: AllocationHandle,
        memory: &mut M,
    ) -> Result<Self, Error> {
        manager
            .validate_allocation(table_allocation)
            .map_err(|_| Error::Pmm)?;
        if table_allocation.page_count != TABLE_PAGE_COUNT
            || table_allocation.owner != TABLE_OWNER
            || table_allocation.zone != Zone::Dma32
        {
            return Err(Error::TableAllocation);
        }
        let root = physical_address(table_allocation)?;
        let tables = [
            root,
            root + PAGE_BYTES,
            root + 2 * PAGE_BYTES,
            root + 3 * PAGE_BYTES,
        ];
        for table in tables {
            memory.prepare_page(table)?;
            for index in 0..TABLE_ENTRIES {
                memory.write_entry(table, index, 0)?;
            }
            for index in 0..TABLE_ENTRIES {
                if memory.read_entry(table, index)? != 0 {
                    return Err(Error::MemoryAccess);
                }
            }
        }
        let indices = table_indices(USER_WINDOW_START);
        replace_entry(memory, tables[0], indices[0], 0, tables[1] | PARENT_FLAGS)?;
        replace_entry(memory, tables[1], indices[1], 0, tables[2] | PARENT_FLAGS)?;
        replace_entry(memory, tables[2], indices[2], 0, tables[3] | PARENT_FLAGS)?;
        Ok(Self {
            table_allocation,
            tables,
            mappings: [None; MAX_MAPPINGS],
            frames: [None; MAX_FRAMES],
            pending: [None; MAX_PENDING_INVALIDATIONS],
            next_invalidation: 1,
            map_operations: 0,
            protect_operations: 0,
            unmap_operations: 0,
            invalidation_receipts: 0,
            released_frames: 0,
            active: false,
            released: false,
        })
    }

    fn validate_virtual(address: u64) -> Result<(), Error> {
        if !address.is_multiple_of(PAGE_BYTES) || !is_canonical_48(address) {
            return Err(Error::Address);
        }
        if classify(address) != Region::User
            || !(USER_WINDOW_START..USER_WINDOW_END_EXCLUSIVE).contains(&address)
        {
            return Err(Error::UnsupportedRegion);
        }
        Ok(())
    }

    fn mapping_index(&self, address: u64) -> Option<usize> {
        self.mappings
            .iter()
            .position(|item| item.is_some_and(|mapping| mapping.virtual_address == address))
    }

    fn frame_index(&self, frame: AllocationHandle) -> Option<usize> {
        self.frames
            .iter()
            .position(|item| item.is_some_and(|binding| binding.frame == frame))
    }

    pub fn map<M: TableMemory>(
        &mut self,
        manager: &PhysicalMemoryManager,
        memory: &mut M,
        virtual_address: u64,
        frame: AllocationHandle,
        permissions: Permissions,
        cache: CachePolicy,
    ) -> Result<(), Error> {
        if self.released {
            return Err(Error::ReleaseBusy);
        }
        Self::validate_virtual(virtual_address)?;
        manager.validate_allocation(frame).map_err(|_| Error::Pmm)?;
        if frame.page_count != 1 || frame.owner != DATA_OWNER {
            return Err(Error::DataAllocation);
        }
        if self.mapping_index(virtual_address).is_some() {
            return Err(Error::AlreadyMapped);
        }
        let mapping_slot = self
            .mappings
            .iter()
            .position(Option::is_none)
            .ok_or(Error::MappingCapacity)?;
        let existing_frame = self.frame_index(frame);
        if let Some(index) = existing_frame {
            if self.frames[index].ok_or(Error::Ownership)?.cache != cache {
                return Err(Error::CacheAlias);
            }
        } else {
            if self.frames.iter().flatten().any(|binding| {
                binding.frame.start_page == frame.start_page
                    && binding.frame.generation != frame.generation
            }) {
                return Err(Error::Ownership);
            }
            if self.frames.iter().all(Option::is_some) {
                return Err(Error::FrameCapacity);
            }
        }
        let value = leaf_entry(frame, permissions, cache)?;
        let leaf_index = table_indices(virtual_address)[3];
        replace_entry(memory, self.tables[3], leaf_index, 0, value)?;
        self.mappings[mapping_slot] = Some(MappingRecord {
            virtual_address,
            frame,
            permissions,
            cache,
        });
        if let Some(index) = existing_frame {
            let mut binding = self.frames[index].ok_or(Error::Ownership)?;
            binding.mapping_count = binding
                .mapping_count
                .checked_add(1)
                .ok_or(Error::FrameCapacity)?;
            self.frames[index] = Some(binding);
        } else {
            let index = self
                .frames
                .iter()
                .position(Option::is_none)
                .ok_or(Error::FrameCapacity)?;
            self.frames[index] = Some(FrameRecord {
                frame,
                cache,
                mapping_count: 1,
                pending_count: 0,
            });
        }
        self.map_operations += 1;
        Ok(())
    }

    pub fn protect<M: TableMemory>(
        &mut self,
        memory: &mut M,
        virtual_address: u64,
        permissions: Permissions,
    ) -> Result<(), Error> {
        Self::validate_virtual(virtual_address)?;
        let index = self
            .mapping_index(virtual_address)
            .ok_or(Error::MappingMissing)?;
        let mut mapping = self.mappings[index].ok_or(Error::MappingMissing)?;
        let previous = leaf_entry(mapping.frame, mapping.permissions, mapping.cache)?;
        let replacement = leaf_entry(mapping.frame, permissions, mapping.cache)?;
        replace_entry(
            memory,
            self.tables[3],
            table_indices(virtual_address)[3],
            previous,
            replacement,
        )?;
        mapping.permissions = permissions;
        self.mappings[index] = Some(mapping);
        self.protect_operations += 1;
        Ok(())
    }

    pub fn translate<M: TableMemory>(
        &self,
        memory: &mut M,
        virtual_address: u64,
    ) -> Result<Translation, Error> {
        Self::validate_virtual(virtual_address & !(PAGE_BYTES - 1))?;
        let indices = table_indices(virtual_address);
        for (level, table) in self.tables[..3].iter().enumerate() {
            let expected = self.tables[level + 1] | PARENT_FLAGS;
            if memory.read_entry(*table, indices[level])? != expected {
                return Err(Error::ParentEntry);
            }
        }
        decode_leaf(
            memory.read_entry(self.tables[3], indices[3])?,
            virtual_address,
        )
    }

    pub fn begin_unmap<M: TableMemory>(
        &mut self,
        memory: &mut M,
        virtual_address: u64,
    ) -> Result<InvalidationToken, Error> {
        Self::validate_virtual(virtual_address)?;
        let mapping_index = self
            .mapping_index(virtual_address)
            .ok_or(Error::MappingMissing)?;
        let pending_index = self
            .pending
            .iter()
            .position(Option::is_none)
            .ok_or(Error::PendingCapacity)?;
        let mapping = self.mappings[mapping_index].ok_or(Error::MappingMissing)?;
        let frame_index = self.frame_index(mapping.frame).ok_or(Error::Ownership)?;
        let mut binding = self.frames[frame_index].ok_or(Error::Ownership)?;
        let previous = leaf_entry(mapping.frame, mapping.permissions, mapping.cache)?;
        replace_entry(
            memory,
            self.tables[3],
            table_indices(virtual_address)[3],
            previous,
            0,
        )?;
        let token = InvalidationToken {
            sequence: self.next_invalidation,
            root_generation: self.table_allocation.generation,
            virtual_address,
            frame_generation: mapping.frame.generation,
        };
        self.next_invalidation = self
            .next_invalidation
            .checked_add(1)
            .ok_or(Error::PendingCapacity)?;
        binding.mapping_count = binding
            .mapping_count
            .checked_sub(1)
            .ok_or(Error::Ownership)?;
        binding.pending_count = binding
            .pending_count
            .checked_add(1)
            .ok_or(Error::PendingCapacity)?;
        self.frames[frame_index] = Some(binding);
        self.mappings[mapping_index] = None;
        self.pending[pending_index] = Some(PendingInvalidation {
            token,
            frame: mapping.frame,
            acknowledged: false,
        });
        self.unmap_operations += 1;
        Ok(token)
    }

    pub fn acknowledge_inactive(&mut self, token: InvalidationToken) -> Result<(), Error> {
        if self.active {
            return Err(Error::ActiveRootUnsupported);
        }
        let index = self
            .pending
            .iter()
            .position(|item| item.is_some_and(|pending| pending.token == token))
            .ok_or(Error::StaleInvalidation)?;
        let mut pending = self.pending[index].ok_or(Error::StaleInvalidation)?;
        if pending.acknowledged || token.root_generation != self.table_allocation.generation {
            return Err(Error::StaleInvalidation);
        }
        pending.acknowledged = true;
        self.pending[index] = Some(pending);
        self.invalidation_receipts += 1;
        Ok(())
    }

    pub fn complete_unmap(
        &mut self,
        manager: &mut PhysicalMemoryManager,
        token: InvalidationToken,
    ) -> Result<bool, Error> {
        let pending_index = self
            .pending
            .iter()
            .position(|item| item.is_some_and(|pending| pending.token == token))
            .ok_or(Error::StaleInvalidation)?;
        let pending = self.pending[pending_index].ok_or(Error::StaleInvalidation)?;
        if !pending.acknowledged {
            return Err(Error::InvalidationRequired);
        }
        let frame_index = self.frame_index(pending.frame).ok_or(Error::Ownership)?;
        let mut binding = self.frames[frame_index].ok_or(Error::Ownership)?;
        let release = binding.mapping_count == 0 && binding.pending_count == 1;
        if release {
            manager.free(binding.frame).map_err(|_| Error::Pmm)?;
        }
        binding.pending_count = binding
            .pending_count
            .checked_sub(1)
            .ok_or(Error::Ownership)?;
        self.pending[pending_index] = None;
        if release {
            self.frames[frame_index] = None;
            self.released_frames += 1;
        } else {
            self.frames[frame_index] = Some(binding);
        }
        Ok(release)
    }

    pub fn release<M: TableMemory>(
        &mut self,
        manager: &mut PhysicalMemoryManager,
        memory: &mut M,
    ) -> Result<(), Error> {
        if self.active
            || self.released
            || self.mappings.iter().any(Option::is_some)
            || self.frames.iter().any(Option::is_some)
            || self.pending.iter().any(Option::is_some)
        {
            return Err(Error::ReleaseBusy);
        }
        for table in self.tables {
            for index in 0..TABLE_ENTRIES {
                memory.write_entry(table, index, 0)?;
            }
        }
        memory.finish()?;
        manager
            .free(self.table_allocation)
            .map_err(|_| Error::Pmm)?;
        self.released = true;
        self.released_frames += TABLE_PAGE_COUNT;
        Ok(())
    }

    pub fn summary(&self) -> Summary {
        Summary {
            root_physical: self.tables[0],
            root_generation: self.table_allocation.generation,
            table_pages: TABLE_PAGE_COUNT,
            active_mappings: self.mappings.iter().flatten().count(),
            bound_frames: self.frames.iter().flatten().count(),
            pending_invalidations: self.pending.iter().flatten().count(),
            map_operations: self.map_operations,
            protect_operations: self.protect_operations,
            unmap_operations: self.unmap_operations,
            invalidation_receipts: self.invalidation_receipts,
            released_frames: self.released_frames,
            root_active: self.active,
            root_released: self.released,
        }
    }
}

#[inline(never)]
pub fn run_profile<M: TableMemory>(
    handoff: &Handoff<'_>,
    core: CoreRecord,
    memory: &mut M,
) -> Result<VirtualMemoryProof, Error> {
    let mut manager =
        PhysicalMemoryManager::from_handoff(handoff, core, 16).map_err(|_| Error::Pmm)?;
    let tables = manager
        .allocate(Zone::Dma32, TABLE_PAGE_COUNT, TABLE_OWNER)
        .map_err(|_| Error::TableAllocation)?;
    let data = manager
        .allocate(Zone::Dma32, 1, DATA_OWNER)
        .map_err(|_| Error::DataAllocation)?;
    let mut space = AddressSpace::initialize(&manager, tables, memory)?;
    space.map(
        &manager,
        memory,
        USER_WINDOW_START,
        data,
        Permissions::USER_RW,
        CachePolicy::WriteBack,
    )?;
    let mapped_translation = space.translate(memory, USER_WINDOW_START)?;
    space.map(
        &manager,
        memory,
        USER_WINDOW_START + PAGE_BYTES,
        data,
        Permissions::USER_RW,
        CachePolicy::WriteBack,
    )?;
    let cache_alias_rejected = space.map(
        &manager,
        memory,
        USER_WINDOW_START + 2 * PAGE_BYTES,
        data,
        Permissions::USER_RW,
        CachePolicy::Uncacheable,
    ) == Err(Error::CacheAlias);
    let writable_executable_rejected = space.map(
        &manager,
        memory,
        USER_WINDOW_START + 2 * PAGE_BYTES,
        data,
        Permissions {
            read: true,
            write: true,
            execute: true,
            user: true,
        },
        CachePolicy::WriteBack,
    ) == Err(Error::Permission);
    space.protect(memory, USER_WINDOW_START, Permissions::USER_RX)?;
    let protected_translation = space.translate(memory, USER_WINDOW_START)?;
    let first = space.begin_unmap(memory, USER_WINDOW_START)?;
    space.acknowledge_inactive(first)?;
    if space.complete_unmap(&mut manager, first)? {
        return Err(Error::ExerciseInvariant);
    }
    let second = space.begin_unmap(memory, USER_WINDOW_START + PAGE_BYTES)?;
    let premature_reuse_rejected =
        space.complete_unmap(&mut manager, second) == Err(Error::InvalidationRequired);
    space.acknowledge_inactive(second)?;
    if !space.complete_unmap(&mut manager, second)? {
        return Err(Error::ExerciseInvariant);
    }
    space.release(&mut manager, memory)?;
    let final_space = space.summary();
    let final_pmm = manager.summary();
    if !cache_alias_rejected
        || !writable_executable_rejected
        || !premature_reuse_rejected
        || mapped_translation.physical_address != physical_address(data)?
        || mapped_translation.permissions != Permissions::USER_RW
        || protected_translation.permissions != Permissions::USER_RX
        || final_space.active_mappings != 0
        || final_space.bound_frames != 0
        || final_space.pending_invalidations != 0
        || final_space.map_operations != 2
        || final_space.protect_operations != 1
        || final_space.unmap_operations != 2
        || final_space.invalidation_receipts != 2
        || final_space.released_frames != 5
        || !final_space.root_released
        || final_pmm.allocated_pages != 0
    {
        return Err(Error::ExerciseInvariant);
    }
    Ok(VirtualMemoryProof {
        root_physical: physical_address(tables)?,
        table_generation: tables.generation,
        data_physical: physical_address(data)?,
        data_generation: data.generation,
        mapped_translation,
        protected_translation,
        cache_alias_rejected,
        writable_executable_rejected,
        premature_reuse_rejected,
        final_space,
        physical_write_count: memory.physical_write_count(),
        temporary_pte_write_count: memory.temporary_pte_write_count(),
        hardware_invalidation_count: memory.hardware_invalidation_count(),
        final_allocated_pages: final_pmm.allocated_pages,
        final_allocation_count: final_pmm.allocation_count,
        final_free_count: final_pmm.free_count,
    })
}

#[cfg(test)]
mod tests {
    use super::*;

    struct Memory {
        base: u64,
        entries: [[u64; TABLE_ENTRIES]; TABLE_PAGE_COUNT as usize],
        writes: u64,
        reject_next_write: bool,
    }

    impl Memory {
        fn new(base: u64) -> Self {
            Self {
                base,
                entries: [[0; TABLE_ENTRIES]; TABLE_PAGE_COUNT as usize],
                writes: 0,
                reject_next_write: false,
            }
        }

        fn location(&self, table: u64, index: usize) -> Result<(usize, usize), Error> {
            if table < self.base
                || !(table - self.base).is_multiple_of(PAGE_BYTES)
                || index >= TABLE_ENTRIES
            {
                return Err(Error::MemoryAccess);
            }
            let page = ((table - self.base) / PAGE_BYTES) as usize;
            if page >= self.entries.len() {
                return Err(Error::MemoryAccess);
            }
            Ok((page, index))
        }
    }

    impl TableMemory for Memory {
        fn prepare_page(&mut self, physical_address: u64) -> Result<(), Error> {
            self.location(physical_address, 0).map(|_| ())
        }

        fn read_entry(&mut self, table_address: u64, index: usize) -> Result<u64, Error> {
            let (page, entry) = self.location(table_address, index)?;
            Ok(self.entries[page][entry])
        }

        fn write_entry(
            &mut self,
            table_address: u64,
            index: usize,
            value: u64,
        ) -> Result<(), Error> {
            let (page, entry) = self.location(table_address, index)?;
            if self.reject_next_write {
                self.reject_next_write = false;
                return Err(Error::MemoryAccess);
            }
            self.entries[page][entry] = value;
            self.writes += 1;
            Ok(())
        }

        fn physical_write_count(&self) -> u64 {
            self.writes
        }

        fn finish(&mut self) -> Result<(), Error> {
            Ok(())
        }

        fn temporary_pte_write_count(&self) -> u64 {
            0
        }

        fn hardware_invalidation_count(&self) -> u64 {
            0
        }
    }

    fn fixture() -> (
        PhysicalMemoryManager,
        AllocationHandle,
        AllocationHandle,
        Memory,
    ) {
        let mut manager = PhysicalMemoryManager::test_manager(4096, 64, 16);
        let tables = manager
            .allocate(Zone::Dma32, TABLE_PAGE_COUNT, TABLE_OWNER)
            .unwrap();
        let data = manager.allocate(Zone::Dma32, 1, DATA_OWNER).unwrap();
        let memory = Memory::new(physical_address(tables).unwrap());
        (manager, tables, data, memory)
    }

    #[test]
    fn freezes_canonical_layout_bands() {
        assert_eq!(classify(0), Region::NullGuard);
        assert_eq!(classify(NULL_GUARD_END), Region::User);
        assert_eq!(classify(USER_END_EXCLUSIVE), Region::NonCanonical);
        assert_eq!(classify(KERNEL_START), Region::Kernel);
        assert_eq!(classify(DIRECT_MAP_START), Region::DirectMap);
        assert_eq!(classify(TEMPORARY_MAP_START), Region::TemporaryMap);
        assert_eq!(classify(KERNEL_IMAGE_START), Region::KernelImage);
    }

    #[test]
    fn materializes_walkable_four_level_entries() {
        let (manager, tables, data, mut memory) = fixture();
        let mut space = AddressSpace::initialize(&manager, tables, &mut memory).unwrap();
        space
            .map(
                &manager,
                &mut memory,
                USER_WINDOW_START,
                data,
                Permissions::USER_RW,
                CachePolicy::WriteBack,
            )
            .unwrap();
        assert_eq!(
            space
                .translate(&mut memory, USER_WINDOW_START + 17)
                .unwrap(),
            Translation {
                physical_address: physical_address(data).unwrap() + 17,
                permissions: Permissions::USER_RW,
                cache: CachePolicy::WriteBack,
            }
        );
    }

    #[test]
    fn rejects_noncanonical_guard_kernel_wx_and_stale_ownership() {
        let (mut manager, tables, data, mut memory) = fixture();
        let stale = data;
        manager.free(data).unwrap();
        let replacement = manager.allocate(Zone::Dma32, 1, DATA_OWNER).unwrap();
        let mut space = AddressSpace::initialize(&manager, tables, &mut memory).unwrap();
        for address in [0, USER_END_EXCLUSIVE, KERNEL_IMAGE_START] {
            assert!(
                space
                    .map(
                        &manager,
                        &mut memory,
                        address,
                        replacement,
                        Permissions::USER_RW,
                        CachePolicy::WriteBack,
                    )
                    .is_err()
            );
        }
        assert_eq!(
            space.map(
                &manager,
                &mut memory,
                USER_WINDOW_START,
                stale,
                Permissions::USER_RW,
                CachePolicy::WriteBack,
            ),
            Err(Error::Pmm)
        );
        assert_eq!(
            space.map(
                &manager,
                &mut memory,
                USER_WINDOW_START,
                replacement,
                Permissions {
                    read: true,
                    write: true,
                    execute: true,
                    user: true,
                },
                CachePolicy::WriteBack,
            ),
            Err(Error::Permission)
        );
    }

    #[test]
    fn rejects_mixed_cache_alias_without_touching_the_second_leaf() {
        let (manager, tables, data, mut memory) = fixture();
        let mut space = AddressSpace::initialize(&manager, tables, &mut memory).unwrap();
        space
            .map(
                &manager,
                &mut memory,
                USER_WINDOW_START,
                data,
                Permissions::USER_RW,
                CachePolicy::WriteBack,
            )
            .unwrap();
        assert_eq!(
            space.map(
                &manager,
                &mut memory,
                USER_WINDOW_START + PAGE_BYTES,
                data,
                Permissions::USER_RW,
                CachePolicy::Uncacheable,
            ),
            Err(Error::CacheAlias)
        );
        assert_eq!(
            space.translate(&mut memory, USER_WINDOW_START + PAGE_BYTES),
            Err(Error::MappingMissing)
        );
    }

    #[test]
    fn failed_protect_rolls_back_the_exact_leaf() {
        let (manager, tables, data, mut memory) = fixture();
        let mut space = AddressSpace::initialize(&manager, tables, &mut memory).unwrap();
        space
            .map(
                &manager,
                &mut memory,
                USER_WINDOW_START,
                data,
                Permissions::USER_RW,
                CachePolicy::WriteBack,
            )
            .unwrap();
        memory.reject_next_write = true;
        assert_eq!(
            space.protect(&mut memory, USER_WINDOW_START, Permissions::USER_RX),
            Err(Error::TransactionRejected)
        );
        assert_eq!(
            space
                .translate(&mut memory, USER_WINDOW_START)
                .unwrap()
                .permissions,
            Permissions::USER_RW
        );
    }

    #[test]
    fn frame_reuse_waits_for_every_alias_and_receipt() {
        let (mut manager, tables, data, mut memory) = fixture();
        let mut space = AddressSpace::initialize(&manager, tables, &mut memory).unwrap();
        for address in [USER_WINDOW_START, USER_WINDOW_START + PAGE_BYTES] {
            space
                .map(
                    &manager,
                    &mut memory,
                    address,
                    data,
                    Permissions::USER_RW,
                    CachePolicy::WriteBack,
                )
                .unwrap();
        }
        let first = space.begin_unmap(&mut memory, USER_WINDOW_START).unwrap();
        space.acknowledge_inactive(first).unwrap();
        assert!(!space.complete_unmap(&mut manager, first).unwrap());
        assert!(manager.validate_allocation(data).is_ok());
        let second = space
            .begin_unmap(&mut memory, USER_WINDOW_START + PAGE_BYTES)
            .unwrap();
        assert_eq!(
            space.complete_unmap(&mut manager, second),
            Err(Error::InvalidationRequired)
        );
        space.acknowledge_inactive(second).unwrap();
        assert!(space.complete_unmap(&mut manager, second).unwrap());
        assert!(manager.validate_allocation(data).is_err());
        assert_eq!(
            space.acknowledge_inactive(second),
            Err(Error::StaleInvalidation)
        );
        space.release(&mut manager, &mut memory).unwrap();
        assert_eq!(manager.summary().allocated_pages, 0);
    }
}
