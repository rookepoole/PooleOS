use poole_handoff::{CoreRecord, Handoff, PAGE_BYTES};

use crate::physical_memory::{AllocationHandle, PhysicalMemoryManager, Zone};
use crate::virtual_memory::{
    DIRECT_MAP_END_EXCLUSIVE, DIRECT_MAP_START, TableMemory, USER_WINDOW_START,
};

pub const CONTRACT_ID: &str = "PKVM2";
pub const TABLE_PAGE_COUNT: u64 = 8;
pub const MAPPED_OWNED_PAGE_COUNT: u64 = TABLE_PAGE_COUNT + 1;
pub const TABLE_OWNER: u16 = 0x0911;
pub const DATA_OWNER: u16 = 0x0912;
pub const BSP_CPU_ID: u32 = 0;

const TABLE_ENTRIES: usize = 512;
const ENTRY_PRESENT: u64 = 1 << 0;
const ENTRY_WRITABLE: u64 = 1 << 1;
const ENTRY_USER: u64 = 1 << 2;
const ENTRY_ACCESSED: u64 = 1 << 5;
const ENTRY_DIRTY: u64 = 1 << 6;
const ENTRY_PAGE_SIZE_OR_PAT: u64 = 1 << 7;
const ENTRY_NO_EXECUTE: u64 = 1 << 63;
const PHYSICAL_MASK_52: u64 = 0x000f_ffff_ffff_f000;
const ROOT_ADDRESS_MASK: u64 = PHYSICAL_MASK_52;
const USER_PARENT_FLAGS: u64 = ENTRY_PRESENT | ENTRY_WRITABLE | ENTRY_USER;
const DIRECT_PARENT_FLAGS: u64 = ENTRY_PRESENT | ENTRY_WRITABLE | ENTRY_NO_EXECUTE;
const USER_RW_NX_FLAGS: u64 = ENTRY_PRESENT | ENTRY_WRITABLE | ENTRY_USER | ENTRY_NO_EXECUTE;
const SUPERVISOR_RW_NX_FLAGS: u64 = ENTRY_PRESENT | ENTRY_WRITABLE | ENTRY_NO_EXECUTE;
const HARDWARE_LEAF_BITS: u64 = ENTRY_ACCESSED | ENTRY_DIRTY;
const STACK_PAGE_COUNT: u64 = 14;
const PROBE_VALUE: u8 = 0xa5;

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum Error {
    Pmm,
    TableAllocation,
    DataAllocation,
    AllocationContiguity,
    PhysicalAddress,
    AddressWidth,
    MemoryAccess,
    OriginalRoot,
    RootSlotOccupied,
    DirectMapRange,
    LargePage,
    TranslationMissing,
    RetainedKernel,
    RetainedStack,
    RetainedHandoff,
    GuardPage,
    TemporaryAlias,
    DirectMap,
    UserMapping,
    Permission,
    UserRootTransaction,
    DirectRootTransaction,
    UserHierarchyTransaction,
    DirectHierarchyTransaction,
    DirectLeafTransaction,
    ProtectTransaction,
    UserUnmapTransaction,
    DirectUnmapTransaction,
    TransactionRejected,
    RollbackFailed,
    InterruptState,
    CpuMismatch,
    Cr3Mismatch,
    ActivationMismatch,
    Lifecycle,
    InvalidationRequired,
    StaleReceipt,
    ProbeMismatch,
    ExerciseInvariant,
}

macro_rules! error_label {
    ($name:ident, $value:literal) => {
        #[used]
        #[unsafe(link_section = ".text.pkavm_labels")]
        static $name: [u8; $value.len()] = *$value;
    };
}

error_label!(LABEL_OWNERSHIP, b"ownership");
error_label!(LABEL_ADDRESS, b"address");
error_label!(LABEL_TABLE_ACCESS, b"table_access");
error_label!(LABEL_ORIGINAL_ROOT, b"original_root");
error_label!(LABEL_ROOT_SLOT_OCCUPIED, b"root_slot_occupied");
error_label!(LABEL_DIRECT_MAP, b"direct_map");
error_label!(LABEL_TRANSLATION, b"translation");
error_label!(LABEL_RETAINED_KERNEL, b"retained_kernel");
error_label!(LABEL_RETAINED_STACK, b"retained_stack");
error_label!(LABEL_RETAINED_HANDOFF, b"retained_handoff");
error_label!(LABEL_GUARD_PAGE, b"guard_page");
error_label!(LABEL_TEMPORARY_ALIAS, b"temporary_alias");
error_label!(LABEL_USER_MAPPING, b"user_mapping");
error_label!(LABEL_USER_ROOT_TRANSACTION, b"user_root_transaction");
error_label!(LABEL_DIRECT_ROOT_TRANSACTION, b"direct_root_transaction");
error_label!(
    LABEL_USER_HIERARCHY_TRANSACTION,
    b"user_hierarchy_transaction"
);
error_label!(
    LABEL_DIRECT_HIERARCHY_TRANSACTION,
    b"direct_hierarchy_transaction"
);
error_label!(LABEL_DIRECT_LEAF_TRANSACTION, b"direct_leaf_transaction");
error_label!(LABEL_PROTECT_TRANSACTION, b"protect_transaction");
error_label!(LABEL_USER_UNMAP_TRANSACTION, b"user_unmap_transaction");
error_label!(LABEL_DIRECT_UNMAP_TRANSACTION, b"direct_unmap_transaction");
error_label!(LABEL_TRANSACTION, b"transaction");
error_label!(LABEL_INTERRUPT_STATE, b"interrupt_state");
error_label!(LABEL_CPU_MISMATCH, b"cpu_mismatch");
error_label!(LABEL_CR3, b"cr3");
error_label!(LABEL_LIFECYCLE, b"lifecycle");
error_label!(LABEL_INVALIDATION, b"invalidation");
error_label!(LABEL_PROBE, b"probe");
error_label!(LABEL_EXERCISE, b"exercise_invariant");

const fn label_text(bytes: &'static [u8]) -> &'static str {
    // SAFETY: every caller supplies one ASCII byte string declared immediately above.
    unsafe { core::str::from_utf8_unchecked(bytes) }
}

impl Error {
    pub const fn label(self) -> &'static str {
        match self {
            Self::Pmm | Self::TableAllocation | Self::DataAllocation => {
                label_text(&LABEL_OWNERSHIP)
            }
            Self::AllocationContiguity | Self::PhysicalAddress | Self::AddressWidth => {
                label_text(&LABEL_ADDRESS)
            }
            Self::MemoryAccess => label_text(&LABEL_TABLE_ACCESS),
            Self::OriginalRoot => label_text(&LABEL_ORIGINAL_ROOT),
            Self::RootSlotOccupied => label_text(&LABEL_ROOT_SLOT_OCCUPIED),
            Self::DirectMapRange | Self::DirectMap => label_text(&LABEL_DIRECT_MAP),
            Self::LargePage | Self::TranslationMissing => label_text(&LABEL_TRANSLATION),
            Self::RetainedKernel => label_text(&LABEL_RETAINED_KERNEL),
            Self::RetainedStack => label_text(&LABEL_RETAINED_STACK),
            Self::RetainedHandoff => label_text(&LABEL_RETAINED_HANDOFF),
            Self::GuardPage => label_text(&LABEL_GUARD_PAGE),
            Self::TemporaryAlias => label_text(&LABEL_TEMPORARY_ALIAS),
            Self::UserMapping | Self::Permission => label_text(&LABEL_USER_MAPPING),
            Self::UserRootTransaction => label_text(&LABEL_USER_ROOT_TRANSACTION),
            Self::DirectRootTransaction => label_text(&LABEL_DIRECT_ROOT_TRANSACTION),
            Self::UserHierarchyTransaction => label_text(&LABEL_USER_HIERARCHY_TRANSACTION),
            Self::DirectHierarchyTransaction => label_text(&LABEL_DIRECT_HIERARCHY_TRANSACTION),
            Self::DirectLeafTransaction => label_text(&LABEL_DIRECT_LEAF_TRANSACTION),
            Self::ProtectTransaction => label_text(&LABEL_PROTECT_TRANSACTION),
            Self::UserUnmapTransaction => label_text(&LABEL_USER_UNMAP_TRANSACTION),
            Self::DirectUnmapTransaction => label_text(&LABEL_DIRECT_UNMAP_TRANSACTION),
            Self::TransactionRejected | Self::RollbackFailed => label_text(&LABEL_TRANSACTION),
            Self::InterruptState => label_text(&LABEL_INTERRUPT_STATE),
            Self::CpuMismatch => label_text(&LABEL_CPU_MISMATCH),
            Self::Cr3Mismatch | Self::ActivationMismatch => label_text(&LABEL_CR3),
            Self::Lifecycle => label_text(&LABEL_LIFECYCLE),
            Self::InvalidationRequired | Self::StaleReceipt => label_text(&LABEL_INVALIDATION),
            Self::ProbeMismatch => label_text(&LABEL_PROBE),
            Self::ExerciseInvariant => label_text(&LABEL_EXERCISE),
        }
    }
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct Translation {
    pub physical_address: u64,
    pub writable: bool,
    pub executable: bool,
    pub user: bool,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
enum Lifecycle {
    Prepared,
    Active,
    Restored,
    Released,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
enum ReceiptKind {
    Protect,
    UserUnmap,
    DirectUnmap,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct InvalidationReceipt {
    sequence: u64,
    root_physical: u64,
    root_generation: u64,
    virtual_address: u64,
    cpu_id: u32,
    kind: ReceiptKind,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct Summary {
    pub original_root: u64,
    pub candidate_root: u64,
    pub table_generation: u64,
    pub data_physical: u64,
    pub data_generation: u64,
    pub direct_map_first: u64,
    pub direct_map_last: u64,
    pub mapped_owned_pages: u64,
    pub cr3_writes: u64,
    pub local_invalidations: u64,
    pub active_receipts: u64,
    pub activation_rollbacks: u64,
    pub data_released: bool,
    pub tables_released: bool,
    pub root_active: bool,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct ActiveVirtualMemoryProof {
    pub summary: Summary,
    pub protected_translation: Translation,
    pub probe_value: u8,
    pub premature_reuse_rejected: bool,
    pub release_while_active_rejected: bool,
    pub physical_write_count: u64,
    pub temporary_pte_write_count: u64,
    pub bootstrap_invalidation_count: u64,
    pub final_allocated_pages: u64,
    pub final_allocation_count: u64,
    pub final_free_count: u64,
}

pub trait ActiveHardware {
    fn interrupts_disabled(&mut self) -> bool;
    fn cpu_id(&mut self) -> u32;
    fn read_cr3(&mut self) -> u64;
    fn write_cr3(&mut self, value: u64) -> Result<(), Error>;
    fn invalidate_page(&mut self, virtual_address: u64) -> Result<(), Error>;
    fn read_u64(&mut self, virtual_address: u64) -> Result<u64, Error>;
    fn write_u64(&mut self, virtual_address: u64, value: u64) -> Result<(), Error>;
    fn read_u8(&mut self, virtual_address: u64) -> Result<u8, Error>;
    fn write_u8(&mut self, virtual_address: u64, value: u8) -> Result<(), Error>;
}

fn physical_address(handle: AllocationHandle) -> Result<u64, Error> {
    handle
        .start_page
        .checked_mul(PAGE_BYTES)
        .filter(|address| *address != 0 && *address & !PHYSICAL_MASK_52 == 0)
        .ok_or(Error::PhysicalAddress)
}

const fn indices(address: u64) -> [usize; 4] {
    [
        ((address >> 39) & 0x1ff) as usize,
        ((address >> 30) & 0x1ff) as usize,
        ((address >> 21) & 0x1ff) as usize,
        ((address >> 12) & 0x1ff) as usize,
    ]
}

fn direct_address(physical: u64) -> Result<u64, Error> {
    DIRECT_MAP_START
        .checked_add(physical)
        .filter(|address| *address < DIRECT_MAP_END_EXCLUSIVE)
        .ok_or(Error::DirectMapRange)
}

fn read_entry<M: TableMemory>(memory: &mut M, table: u64, index: usize) -> Result<u64, Error> {
    memory
        .read_entry(table, index)
        .map_err(|_| Error::MemoryAccess)
}

fn write_entry<M: TableMemory>(
    memory: &mut M,
    table: u64,
    index: usize,
    value: u64,
) -> Result<(), Error> {
    memory
        .write_entry(table, index, value)
        .map_err(|_| Error::MemoryAccess)
}

fn replace_entry<M: TableMemory>(
    memory: &mut M,
    table: u64,
    index: usize,
    expected: u64,
    replacement: u64,
) -> Result<(), Error> {
    if read_entry(memory, table, index)? != expected {
        return Err(Error::TransactionRejected);
    }
    let write_succeeded = write_entry(memory, table, index, replacement).is_ok();
    let verified = write_succeeded && read_entry(memory, table, index) == Ok(replacement);
    if verified {
        return Ok(());
    }
    if write_entry(memory, table, index, expected).is_err()
        || read_entry(memory, table, index) != Ok(expected)
    {
        return Err(Error::RollbackFailed);
    }
    Err(Error::TransactionRejected)
}

fn translate<M: TableMemory>(
    memory: &mut M,
    root: u64,
    virtual_address: u64,
    physical_address_bits: u8,
) -> Result<Translation, Error> {
    if !(36..=52).contains(&physical_address_bits) {
        return Err(Error::AddressWidth);
    }
    let mask = ((1u64 << physical_address_bits) - 1) & PHYSICAL_MASK_52;
    let mut table = root;
    let mut writable = true;
    let mut executable = true;
    let mut user = true;
    for (level, index) in indices(virtual_address).into_iter().enumerate() {
        let entry = read_entry(memory, table, index)?;
        if entry & ENTRY_PRESENT == 0 {
            return Err(Error::TranslationMissing);
        }
        if level < 3 && entry & ENTRY_PAGE_SIZE_OR_PAT != 0 {
            return Err(Error::LargePage);
        }
        writable &= entry & ENTRY_WRITABLE != 0;
        executable &= entry & ENTRY_NO_EXECUTE == 0;
        user &= entry & ENTRY_USER != 0;
        if level == 3 {
            return Ok(Translation {
                physical_address: (entry & mask) | (virtual_address & (PAGE_BYTES - 1)),
                writable,
                executable,
                user,
            });
        }
        table = entry & mask;
        if table == 0 {
            return Err(Error::TranslationMissing);
        }
    }
    Err(Error::TranslationMissing)
}

fn require_missing<M: TableMemory>(
    memory: &mut M,
    root: u64,
    virtual_address: u64,
    physical_address_bits: u8,
    error: Error,
) -> Result<(), Error> {
    match translate(memory, root, virtual_address, physical_address_bits) {
        Err(Error::TranslationMissing) => Ok(()),
        _ => Err(error),
    }
}

pub struct ActiveAddressSpace {
    table_allocation: AllocationHandle,
    data_allocation: AllocationHandle,
    tables: [u64; TABLE_PAGE_COUNT as usize],
    original_cr3: u64,
    lifecycle: Lifecycle,
    next_receipt: u64,
    cr3_writes: u64,
    local_invalidations: u64,
    active_receipts: u64,
    activation_rollbacks: u64,
    data_released: bool,
    tables_released: bool,
}

impl ActiveAddressSpace {
    pub fn initialize<M: TableMemory>(
        manager: &PhysicalMemoryManager,
        table_allocation: AllocationHandle,
        data_allocation: AllocationHandle,
        memory: &mut M,
        original_cr3: u64,
        core: CoreRecord,
        physical_address_bits: u8,
    ) -> Result<Self, Error> {
        manager
            .validate_allocation(table_allocation)
            .map_err(|_| Error::Pmm)?;
        manager
            .validate_allocation(data_allocation)
            .map_err(|_| Error::Pmm)?;
        if table_allocation.page_count != TABLE_PAGE_COUNT
            || table_allocation.owner != TABLE_OWNER
            || table_allocation.zone != Zone::Dma32
        {
            return Err(Error::TableAllocation);
        }
        if data_allocation.page_count != 1
            || data_allocation.owner != DATA_OWNER
            || data_allocation.zone != Zone::Dma32
        {
            return Err(Error::DataAllocation);
        }
        if !(36..=52).contains(&physical_address_bits) {
            return Err(Error::AddressWidth);
        }
        let root = physical_address(table_allocation)?;
        let data = physical_address(data_allocation)?;
        if data != root + TABLE_PAGE_COUNT * PAGE_BYTES {
            return Err(Error::AllocationContiguity);
        }
        if original_cr3 & ROOT_ADDRESS_MASK != core.page_table_root_physical
            || core.page_table_root_physical == 0
        {
            return Err(Error::OriginalRoot);
        }
        let tables = core::array::from_fn(|index| root + index as u64 * PAGE_BYTES);
        let first_direct = direct_address(root)?;
        let last_direct = direct_address(data + PAGE_BYTES - 1)?;
        let first_indices = indices(first_direct);
        let last_indices = indices(last_direct);
        if first_indices[0] != last_indices[0]
            || first_indices[1] != last_indices[1]
            || last_indices[2] < first_indices[2]
            || last_indices[2] - first_indices[2] > 1
        {
            return Err(Error::DirectMapRange);
        }

        for table in tables {
            memory
                .prepare_page(table)
                .map_err(|_| Error::MemoryAccess)?;
            for index in 0..TABLE_ENTRIES {
                write_entry(memory, table, index, 0)?;
            }
        }
        let original_root = core.page_table_root_physical;
        for index in 0..TABLE_ENTRIES {
            let inherited = read_entry(memory, original_root, index)?;
            write_entry(memory, tables[0], index, inherited)?;
        }

        let user_slot = indices(USER_WINDOW_START)[0];
        let direct_slot = first_indices[0];
        if read_entry(memory, original_root, direct_slot)? != 0 {
            return Err(Error::RootSlotOccupied);
        }
        let inherited_user = read_entry(memory, tables[0], user_slot)?;
        replace_entry(
            memory,
            tables[0],
            user_slot,
            inherited_user,
            tables[1] | USER_PARENT_FLAGS,
        )
        .map_err(|_| Error::UserRootTransaction)?;
        replace_entry(
            memory,
            tables[0],
            direct_slot,
            0,
            tables[4] | DIRECT_PARENT_FLAGS,
        )
        .map_err(|_| Error::DirectRootTransaction)?;

        let user_indices = indices(USER_WINDOW_START);
        replace_entry(
            memory,
            tables[1],
            user_indices[1],
            0,
            tables[2] | USER_PARENT_FLAGS,
        )
        .map_err(|_| Error::UserHierarchyTransaction)?;
        replace_entry(
            memory,
            tables[2],
            user_indices[2],
            0,
            tables[3] | USER_PARENT_FLAGS,
        )
        .map_err(|_| Error::UserHierarchyTransaction)?;
        replace_entry(
            memory,
            tables[3],
            user_indices[3],
            0,
            data | USER_RW_NX_FLAGS,
        )
        .map_err(|_| Error::UserHierarchyTransaction)?;

        replace_entry(
            memory,
            tables[4],
            first_indices[1],
            0,
            tables[5] | DIRECT_PARENT_FLAGS,
        )
        .map_err(|_| Error::DirectHierarchyTransaction)?;
        for directory_offset in 0..=(last_indices[2] - first_indices[2]) {
            replace_entry(
                memory,
                tables[5],
                first_indices[2] + directory_offset,
                0,
                tables[6 + directory_offset] | DIRECT_PARENT_FLAGS,
            )
            .map_err(|_| Error::DirectHierarchyTransaction)?;
        }
        for page in 0..MAPPED_OWNED_PAGE_COUNT {
            let physical = root + page * PAGE_BYTES;
            let direct = direct_address(physical)?;
            let direct_indices = indices(direct);
            let directory_offset = direct_indices[2] - first_indices[2];
            replace_entry(
                memory,
                tables[6 + directory_offset],
                direct_indices[3],
                0,
                physical | SUPERVISOR_RW_NX_FLAGS,
            )
            .map_err(|_| Error::DirectLeafTransaction)?;
        }

        let space = Self {
            table_allocation,
            data_allocation,
            tables,
            original_cr3,
            lifecycle: Lifecycle::Prepared,
            next_receipt: 1,
            cr3_writes: 0,
            local_invalidations: 0,
            active_receipts: 0,
            activation_rollbacks: 0,
            data_released: false,
            tables_released: false,
        };
        space.audit(memory, core, physical_address_bits)?;
        Ok(space)
    }

    fn audit<M: TableMemory>(
        &self,
        memory: &mut M,
        core: CoreRecord,
        physical_address_bits: u8,
    ) -> Result<(), Error> {
        let original_root = core.page_table_root_physical;
        let candidate_root = self.tables[0];
        let user_slot = indices(USER_WINDOW_START)[0];
        let direct_slot = indices(DIRECT_MAP_START)[0];
        for index in 0..TABLE_ENTRIES {
            let original = read_entry(memory, original_root, index)?;
            let expected = if index == user_slot {
                self.tables[1] | USER_PARENT_FLAGS
            } else if index == direct_slot {
                self.tables[4] | DIRECT_PARENT_FLAGS
            } else {
                original
            };
            if read_entry(memory, candidate_root, index)? != expected {
                return Err(Error::RetainedKernel);
            }
        }

        let kernel_pages = core.kernel_physical_size.div_ceil(PAGE_BYTES);
        for page in 0..kernel_pages {
            let virtual_address = core.kernel_virtual_base + page * PAGE_BYTES;
            let original = translate(
                memory,
                original_root,
                virtual_address,
                physical_address_bits,
            )
            .map_err(|_| Error::RetainedKernel)?;
            let candidate = translate(
                memory,
                candidate_root,
                virtual_address,
                physical_address_bits,
            )
            .map_err(|_| Error::RetainedKernel)?;
            if original != candidate
                || candidate.physical_address != core.kernel_physical_base + page * PAGE_BYTES
                || candidate.user
                || (candidate.writable && candidate.executable)
            {
                return Err(Error::RetainedKernel);
            }
        }
        let entry = translate(
            memory,
            candidate_root,
            core.kernel_entry_virtual,
            physical_address_bits,
        )
        .map_err(|_| Error::RetainedKernel)?;
        if entry.writable || !entry.executable || entry.user {
            return Err(Error::RetainedKernel);
        }

        let stack_bottom = core
            .initial_stack_top_virtual
            .checked_sub(STACK_PAGE_COUNT * PAGE_BYTES)
            .ok_or(Error::RetainedStack)?;
        for address in [stack_bottom, core.initial_stack_top_virtual - 1] {
            let original = translate(memory, original_root, address, physical_address_bits)
                .map_err(|_| Error::RetainedStack)?;
            let candidate = translate(memory, candidate_root, address, physical_address_bits)
                .map_err(|_| Error::RetainedStack)?;
            if original != candidate
                || !candidate.writable
                || candidate.executable
                || candidate.user
            {
                return Err(Error::RetainedStack);
            }
        }
        require_missing(
            memory,
            candidate_root,
            stack_bottom - PAGE_BYTES,
            physical_address_bits,
            Error::GuardPage,
        )?;
        require_missing(
            memory,
            candidate_root,
            core.initial_stack_top_virtual,
            physical_address_bits,
            Error::GuardPage,
        )?;

        let handoff_last = core
            .handoff_virtual_base
            .checked_add(core.handoff_byte_count)
            .and_then(|value| value.checked_sub(1))
            .ok_or(Error::RetainedHandoff)?;
        for (virtual_address, physical_address) in [
            (core.handoff_virtual_base, core.handoff_physical_base),
            (
                handoff_last,
                core.handoff_physical_base + core.handoff_byte_count - 1,
            ),
        ] {
            let original = translate(
                memory,
                original_root,
                virtual_address,
                physical_address_bits,
            )
            .map_err(|_| Error::RetainedHandoff)?;
            let candidate = translate(
                memory,
                candidate_root,
                virtual_address,
                physical_address_bits,
            )
            .map_err(|_| Error::RetainedHandoff)?;
            if original != candidate
                || candidate.physical_address != physical_address
                || candidate.writable
                || candidate.executable
                || candidate.user
            {
                return Err(Error::RetainedHandoff);
            }
        }
        let root = self.tables[0];
        for page in 0..MAPPED_OWNED_PAGE_COUNT {
            let physical = root + page * PAGE_BYTES;
            let translation = translate(
                memory,
                candidate_root,
                direct_address(physical)?,
                physical_address_bits,
            )
            .map_err(|_| Error::DirectMap)?;
            if translation.physical_address != physical
                || !translation.writable
                || translation.executable
                || translation.user
            {
                return Err(Error::DirectMap);
            }
        }
        let user = translate(
            memory,
            candidate_root,
            USER_WINDOW_START,
            physical_address_bits,
        )
        .map_err(|_| Error::UserMapping)?;
        if user.physical_address != physical_address(self.data_allocation)?
            || !user.writable
            || user.executable
            || !user.user
        {
            return Err(Error::UserMapping);
        }
        Ok(())
    }

    fn require_active<H: ActiveHardware>(&self, hardware: &mut H) -> Result<u32, Error> {
        if self.lifecycle != Lifecycle::Active {
            return Err(Error::Lifecycle);
        }
        if !hardware.interrupts_disabled() {
            return Err(Error::InterruptState);
        }
        let cpu_id = hardware.cpu_id();
        if cpu_id != BSP_CPU_ID {
            return Err(Error::CpuMismatch);
        }
        if hardware.read_cr3() & ROOT_ADDRESS_MASK != self.tables[0] {
            return Err(Error::Cr3Mismatch);
        }
        Ok(cpu_id)
    }

    pub fn activate<H: ActiveHardware>(&mut self, hardware: &mut H) -> Result<(), Error> {
        if self.lifecycle != Lifecycle::Prepared {
            return Err(Error::Lifecycle);
        }
        if !hardware.interrupts_disabled() {
            return Err(Error::InterruptState);
        }
        if hardware.cpu_id() != BSP_CPU_ID {
            return Err(Error::CpuMismatch);
        }
        if hardware.read_cr3() != self.original_cr3 {
            return Err(Error::Cr3Mismatch);
        }
        hardware.write_cr3(self.tables[0])?;
        if hardware.read_cr3() & ROOT_ADDRESS_MASK != self.tables[0] {
            hardware.write_cr3(self.original_cr3)?;
            if hardware.read_cr3() != self.original_cr3 {
                return Err(Error::RollbackFailed);
            }
            self.activation_rollbacks += 1;
            return Err(Error::ActivationMismatch);
        }
        self.cr3_writes += 1;
        self.lifecycle = Lifecycle::Active;
        Ok(())
    }

    fn active_replace<H: ActiveHardware>(
        hardware: &mut H,
        table_virtual: u64,
        index: usize,
        expected: u64,
        replacement: u64,
    ) -> Result<(), Error> {
        let address = table_virtual
            .checked_add(index as u64 * core::mem::size_of::<u64>() as u64)
            .ok_or(Error::MemoryAccess)?;
        if hardware.read_u64(address)? != expected {
            return Err(Error::TransactionRejected);
        }
        let write_succeeded = hardware.write_u64(address, replacement).is_ok();
        let verified = write_succeeded && hardware.read_u64(address) == Ok(replacement);
        if verified {
            return Ok(());
        }
        if hardware.write_u64(address, expected).is_err()
            || hardware.read_u64(address) != Ok(expected)
        {
            return Err(Error::RollbackFailed);
        }
        Err(Error::TransactionRejected)
    }

    fn observed_active_leaf<H: ActiveHardware>(
        hardware: &mut H,
        table_virtual: u64,
        index: usize,
        expected_policy: u64,
    ) -> Result<u64, Error> {
        let address = table_virtual
            .checked_add(index as u64 * core::mem::size_of::<u64>() as u64)
            .ok_or(Error::MemoryAccess)?;
        let observed = hardware.read_u64(address)?;
        if observed & !HARDWARE_LEAF_BITS != expected_policy {
            return Err(Error::TransactionRejected);
        }
        Ok(observed)
    }

    fn invalidate<H: ActiveHardware>(
        &mut self,
        hardware: &mut H,
        virtual_address: u64,
        cpu_id: u32,
        kind: ReceiptKind,
    ) -> Result<InvalidationReceipt, Error> {
        hardware.invalidate_page(virtual_address)?;
        if hardware.read_cr3() & ROOT_ADDRESS_MASK != self.tables[0] || hardware.cpu_id() != cpu_id
        {
            return Err(Error::StaleReceipt);
        }
        let receipt = InvalidationReceipt {
            sequence: self.next_receipt,
            root_physical: self.tables[0],
            root_generation: self.table_allocation.generation,
            virtual_address,
            cpu_id,
            kind,
        };
        self.next_receipt = self
            .next_receipt
            .checked_add(1)
            .ok_or(Error::StaleReceipt)?;
        self.local_invalidations += 1;
        self.active_receipts += 1;
        Ok(receipt)
    }

    pub fn write_probe<H: ActiveHardware>(&self, hardware: &mut H) -> Result<u8, Error> {
        self.require_active(hardware)?;
        hardware.write_u8(USER_WINDOW_START, PROBE_VALUE)?;
        let observed = hardware.read_u8(USER_WINDOW_START)?;
        if observed != PROBE_VALUE {
            return Err(Error::ProbeMismatch);
        }
        Ok(observed)
    }

    pub fn protect_user<H: ActiveHardware>(
        &mut self,
        hardware: &mut H,
    ) -> Result<(InvalidationReceipt, Translation), Error> {
        let cpu_id = self.require_active(hardware)?;
        let data = physical_address(self.data_allocation)?;
        let leaf_index = indices(USER_WINDOW_START)[3];
        let table_virtual = direct_address(self.tables[3])?;
        let observed = Self::observed_active_leaf(
            hardware,
            table_virtual,
            leaf_index,
            data | USER_RW_NX_FLAGS,
        )
        .map_err(|_| Error::ProtectTransaction)?;
        Self::active_replace(
            hardware,
            table_virtual,
            leaf_index,
            observed,
            data | ENTRY_PRESENT | ENTRY_USER | (observed & HARDWARE_LEAF_BITS),
        )
        .map_err(|_| Error::ProtectTransaction)?;
        let receipt = self.invalidate(hardware, USER_WINDOW_START, cpu_id, ReceiptKind::Protect)?;
        let value = hardware.read_u64(direct_address(self.tables[3])? + leaf_index as u64 * 8)?;
        let translation = Translation {
            physical_address: value & PHYSICAL_MASK_52,
            writable: value & ENTRY_WRITABLE != 0,
            executable: value & ENTRY_NO_EXECUTE == 0,
            user: value & ENTRY_USER != 0,
        };
        if translation.physical_address != data
            || translation.writable
            || !translation.executable
            || !translation.user
            || hardware.read_u8(USER_WINDOW_START)? != PROBE_VALUE
        {
            return Err(Error::Permission);
        }
        Ok((receipt, translation))
    }

    pub fn begin_user_unmap<H: ActiveHardware>(
        &mut self,
        hardware: &mut H,
    ) -> Result<InvalidationReceipt, Error> {
        let cpu_id = self.require_active(hardware)?;
        let leaf_index = indices(USER_WINDOW_START)[3];
        let data = physical_address(self.data_allocation)?;
        let table_virtual = direct_address(self.tables[3])?;
        let observed = Self::observed_active_leaf(
            hardware,
            table_virtual,
            leaf_index,
            data | ENTRY_PRESENT | ENTRY_USER,
        )
        .map_err(|_| Error::UserUnmapTransaction)?;
        Self::active_replace(hardware, table_virtual, leaf_index, observed, 0)
            .map_err(|_| Error::UserUnmapTransaction)?;
        self.invalidate(hardware, USER_WINDOW_START, cpu_id, ReceiptKind::UserUnmap)
    }

    pub fn revoke_data_direct_map<H: ActiveHardware>(
        &mut self,
        hardware: &mut H,
    ) -> Result<InvalidationReceipt, Error> {
        let cpu_id = self.require_active(hardware)?;
        let data = physical_address(self.data_allocation)?;
        let direct = direct_address(data)?;
        let direct_indices = indices(direct);
        let first_directory = indices(direct_address(self.tables[0])?)[2];
        let directory_offset = direct_indices[2]
            .checked_sub(first_directory)
            .filter(|offset| *offset <= 1)
            .ok_or(Error::DirectMapRange)?;
        let table_virtual = direct_address(self.tables[6 + directory_offset])?;
        let observed = Self::observed_active_leaf(
            hardware,
            table_virtual,
            direct_indices[3],
            data | SUPERVISOR_RW_NX_FLAGS,
        )
        .map_err(|_| Error::DirectUnmapTransaction)?;
        Self::active_replace(hardware, table_virtual, direct_indices[3], observed, 0)
            .map_err(|_| Error::DirectUnmapTransaction)?;
        self.invalidate(hardware, direct, cpu_id, ReceiptKind::DirectUnmap)
    }

    pub fn complete_data_release<H: ActiveHardware>(
        &mut self,
        manager: &mut PhysicalMemoryManager,
        hardware: &mut H,
        user: InvalidationReceipt,
        direct: Option<InvalidationReceipt>,
    ) -> Result<(), Error> {
        let cpu_id = self.require_active(hardware)?;
        let direct = direct.ok_or(Error::InvalidationRequired)?;
        let expected_root = self.tables[0];
        let expected_generation = self.table_allocation.generation;
        let data_direct = direct_address(physical_address(self.data_allocation)?)?;
        if user.kind != ReceiptKind::UserUnmap
            || user.virtual_address != USER_WINDOW_START
            || direct.kind != ReceiptKind::DirectUnmap
            || direct.virtual_address != data_direct
            || user.root_physical != expected_root
            || direct.root_physical != expected_root
            || user.root_generation != expected_generation
            || direct.root_generation != expected_generation
            || user.cpu_id != cpu_id
            || direct.cpu_id != cpu_id
            || user.sequence >= direct.sequence
        {
            return Err(Error::StaleReceipt);
        }
        manager.free(self.data_allocation).map_err(|_| Error::Pmm)?;
        self.data_released = true;
        Ok(())
    }

    pub fn restore<H: ActiveHardware>(&mut self, hardware: &mut H) -> Result<(), Error> {
        self.require_active(hardware)?;
        if !self.data_released {
            return Err(Error::Lifecycle);
        }
        hardware.write_cr3(self.original_cr3)?;
        if hardware.read_cr3() != self.original_cr3 {
            return Err(Error::RollbackFailed);
        }
        self.cr3_writes += 1;
        self.lifecycle = Lifecycle::Restored;
        Ok(())
    }

    pub fn release_tables<M: TableMemory>(
        &mut self,
        manager: &mut PhysicalMemoryManager,
        memory: &mut M,
    ) -> Result<(), Error> {
        if self.lifecycle != Lifecycle::Restored || !self.data_released || self.tables_released {
            return Err(Error::Lifecycle);
        }
        for table in self.tables {
            for index in 0..TABLE_ENTRIES {
                write_entry(memory, table, index, 0)?;
            }
        }
        memory.finish().map_err(|_| Error::MemoryAccess)?;
        manager
            .free(self.table_allocation)
            .map_err(|_| Error::Pmm)?;
        self.tables_released = true;
        self.lifecycle = Lifecycle::Released;
        Ok(())
    }

    pub fn summary(&self) -> Summary {
        let data = physical_address(self.data_allocation).unwrap_or(0);
        Summary {
            original_root: self.original_cr3 & ROOT_ADDRESS_MASK,
            candidate_root: self.tables[0],
            table_generation: self.table_allocation.generation,
            data_physical: data,
            data_generation: self.data_allocation.generation,
            direct_map_first: direct_address(self.tables[0]).unwrap_or(0),
            direct_map_last: direct_address(data + PAGE_BYTES - 1).unwrap_or(0),
            mapped_owned_pages: MAPPED_OWNED_PAGE_COUNT,
            cr3_writes: self.cr3_writes,
            local_invalidations: self.local_invalidations,
            active_receipts: self.active_receipts,
            activation_rollbacks: self.activation_rollbacks,
            data_released: self.data_released,
            tables_released: self.tables_released,
            root_active: self.lifecycle == Lifecycle::Active,
        }
    }
}

#[inline(never)]
pub fn run_profile<M: TableMemory, H: ActiveHardware>(
    handoff: &Handoff<'_>,
    core: CoreRecord,
    original_cr3: u64,
    physical_address_bits: u8,
    memory: &mut M,
    hardware: &mut H,
) -> Result<ActiveVirtualMemoryProof, Error> {
    let mut manager =
        PhysicalMemoryManager::from_handoff(handoff, core, 24).map_err(|_| Error::Pmm)?;
    let tables = manager
        .allocate(Zone::Dma32, TABLE_PAGE_COUNT, TABLE_OWNER)
        .map_err(|_| Error::TableAllocation)?;
    let data = manager
        .allocate(Zone::Dma32, 1, DATA_OWNER)
        .map_err(|_| Error::DataAllocation)?;
    let mut space = ActiveAddressSpace::initialize(
        &manager,
        tables,
        data,
        memory,
        original_cr3,
        core,
        physical_address_bits,
    )?;
    memory.finish().map_err(|_| Error::MemoryAccess)?;
    space.activate(hardware)?;
    let probe_value = space.write_probe(hardware)?;
    let (_protect_receipt, protected_translation) = space.protect_user(hardware)?;
    let user_receipt = space.begin_user_unmap(hardware)?;
    let premature_reuse_rejected =
        space.complete_data_release(&mut manager, hardware, user_receipt, None)
            == Err(Error::InvalidationRequired);
    let direct_receipt = space.revoke_data_direct_map(hardware)?;
    space.complete_data_release(&mut manager, hardware, user_receipt, Some(direct_receipt))?;
    let release_while_active_rejected =
        space.release_tables(&mut manager, memory) == Err(Error::Lifecycle);
    space.restore(hardware)?;
    space.release_tables(&mut manager, memory)?;
    let summary = space.summary();
    let final_pmm = manager.summary();
    if probe_value != PROBE_VALUE
        || !premature_reuse_rejected
        || !release_while_active_rejected
        || protected_translation.writable
        || !protected_translation.executable
        || !protected_translation.user
        || summary.cr3_writes != 2
        || summary.local_invalidations != 3
        || summary.active_receipts != 3
        || !summary.data_released
        || !summary.tables_released
        || summary.root_active
        || final_pmm.allocated_pages != 0
    {
        return Err(Error::ExerciseInvariant);
    }
    Ok(ActiveVirtualMemoryProof {
        summary,
        protected_translation,
        probe_value,
        premature_reuse_rejected,
        release_while_active_rejected,
        physical_write_count: memory.physical_write_count(),
        temporary_pte_write_count: memory.temporary_pte_write_count(),
        bootstrap_invalidation_count: memory.hardware_invalidation_count(),
        final_allocated_pages: final_pmm.allocated_pages,
        final_allocation_count: final_pmm.allocation_count,
        final_free_count: final_pmm.free_count,
    })
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::virtual_memory;
    use std::collections::BTreeMap;

    const ORIGINAL_ROOT: u64 = 0x0300_0000;
    const KERNEL_VIRTUAL: u64 = 0xffff_ffff_8000_0000;
    const KERNEL_PHYSICAL: u64 = 0x0020_0000;

    struct Memory {
        pages: BTreeMap<u64, [u64; TABLE_ENTRIES]>,
        writes: u64,
        reject_next_write: bool,
    }

    impl Memory {
        fn fixture() -> (Self, CoreRecord) {
            let mut pages = BTreeMap::new();
            for page in 0..4 {
                pages.insert(ORIGINAL_ROOT + page * PAGE_BYTES, [0; TABLE_ENTRIES]);
            }
            let pml4 = ORIGINAL_ROOT;
            let pdpt = ORIGINAL_ROOT + PAGE_BYTES;
            let directory = ORIGINAL_ROOT + 2 * PAGE_BYTES;
            let leaf = ORIGINAL_ROOT + 3 * PAGE_BYTES;
            pages.get_mut(&pml4).unwrap()[511] = pdpt | ENTRY_PRESENT | ENTRY_WRITABLE;
            pages.get_mut(&pdpt).unwrap()[510] = directory | ENTRY_PRESENT | ENTRY_WRITABLE;
            pages.get_mut(&directory).unwrap()[0] = leaf | ENTRY_PRESENT | ENTRY_WRITABLE;
            for page in 0..4usize {
                pages.get_mut(&leaf).unwrap()[page] =
                    KERNEL_PHYSICAL + page as u64 * PAGE_BYTES | ENTRY_PRESENT;
            }
            let stack_top = KERNEL_VIRTUAL + 79 * PAGE_BYTES;
            for page in 65..79usize {
                pages.get_mut(&leaf).unwrap()[page] =
                    0x0040_0000 + (page - 65) as u64 * PAGE_BYTES | SUPERVISOR_RW_NX_FLAGS;
            }
            pages.get_mut(&leaf).unwrap()[80] = 0x0050_0000 | ENTRY_PRESENT | ENTRY_NO_EXECUTE;
            let core = CoreRecord {
                boot_flags: 0,
                kernel_physical_base: KERNEL_PHYSICAL,
                kernel_physical_size: 4 * PAGE_BYTES,
                kernel_virtual_base: KERNEL_VIRTUAL,
                kernel_virtual_size: 4 * PAGE_BYTES,
                kernel_entry_virtual: KERNEL_VIRTUAL,
                initial_stack_top_virtual: stack_top,
                page_table_root_physical: ORIGINAL_ROOT,
                handoff_physical_base: 0x0050_0000,
                handoff_virtual_base: KERNEL_VIRTUAL + 80 * PAGE_BYTES,
                handoff_byte_count: PAGE_BYTES,
                uefi_system_table_physical: 0,
                uefi_runtime_services_physical: 0,
                boot_attempt: 0,
                boot_attempt_limit: 0,
                boot_slot: 0,
                selected_entry: 0,
                uefi_revision: 0,
            };
            (
                Self {
                    pages,
                    writes: 0,
                    reject_next_write: false,
                },
                core,
            )
        }

        fn ensure(&mut self, physical: u64) {
            self.pages.entry(physical).or_insert([0; TABLE_ENTRIES]);
        }
    }

    impl TableMemory for Memory {
        fn prepare_page(&mut self, physical_address: u64) -> Result<(), virtual_memory::Error> {
            self.ensure(physical_address);
            Ok(())
        }

        fn read_entry(
            &mut self,
            table_address: u64,
            index: usize,
        ) -> Result<u64, virtual_memory::Error> {
            self.pages
                .get(&table_address)
                .and_then(|page| page.get(index))
                .copied()
                .ok_or(virtual_memory::Error::MemoryAccess)
        }

        fn write_entry(
            &mut self,
            table_address: u64,
            index: usize,
            value: u64,
        ) -> Result<(), virtual_memory::Error> {
            if self.reject_next_write {
                self.reject_next_write = false;
                return Err(virtual_memory::Error::MemoryAccess);
            }
            let entry = self
                .pages
                .get_mut(&table_address)
                .and_then(|page| page.get_mut(index))
                .ok_or(virtual_memory::Error::MemoryAccess)?;
            *entry = value;
            self.writes += 1;
            Ok(())
        }

        fn finish(&mut self) -> Result<(), virtual_memory::Error> {
            Ok(())
        }

        fn physical_write_count(&self) -> u64 {
            self.writes
        }

        fn temporary_pte_write_count(&self) -> u64 {
            0
        }

        fn hardware_invalidation_count(&self) -> u64 {
            0
        }
    }

    struct Hardware<'a> {
        memory: &'a mut Memory,
        cr3: u64,
        candidate: u64,
        cpu_id: u32,
        interrupts_disabled: bool,
        reject_candidate_readback: bool,
        reject_next_table_write: bool,
        invalidations: std::vec::Vec<u64>,
        probe: u8,
    }

    impl ActiveHardware for Hardware<'_> {
        fn interrupts_disabled(&mut self) -> bool {
            self.interrupts_disabled
        }

        fn cpu_id(&mut self) -> u32 {
            self.cpu_id
        }

        fn read_cr3(&mut self) -> u64 {
            if self.reject_candidate_readback && self.cr3 == self.candidate {
                self.cr3 + PAGE_BYTES
            } else {
                self.cr3
            }
        }

        fn write_cr3(&mut self, value: u64) -> Result<(), Error> {
            self.cr3 = value;
            Ok(())
        }

        fn invalidate_page(&mut self, virtual_address: u64) -> Result<(), Error> {
            self.invalidations.push(virtual_address);
            Ok(())
        }

        fn read_u64(&mut self, virtual_address: u64) -> Result<u64, Error> {
            let offset = virtual_address
                .checked_sub(DIRECT_MAP_START)
                .ok_or(Error::MemoryAccess)?;
            let table = offset & !(PAGE_BYTES - 1);
            let index = ((offset & (PAGE_BYTES - 1)) / 8) as usize;
            self.memory
                .read_entry(table, index)
                .map_err(|_| Error::MemoryAccess)
        }

        fn write_u64(&mut self, virtual_address: u64, value: u64) -> Result<(), Error> {
            if self.reject_next_table_write {
                self.reject_next_table_write = false;
                return Err(Error::MemoryAccess);
            }
            let offset = virtual_address
                .checked_sub(DIRECT_MAP_START)
                .ok_or(Error::MemoryAccess)?;
            let table = offset & !(PAGE_BYTES - 1);
            let index = ((offset & (PAGE_BYTES - 1)) / 8) as usize;
            self.memory
                .write_entry(table, index, value)
                .map_err(|_| Error::MemoryAccess)
        }

        fn read_u8(&mut self, virtual_address: u64) -> Result<u8, Error> {
            if virtual_address != USER_WINDOW_START {
                return Err(Error::MemoryAccess);
            }
            Ok(self.probe)
        }

        fn write_u8(&mut self, virtual_address: u64, value: u8) -> Result<(), Error> {
            if virtual_address != USER_WINDOW_START {
                return Err(Error::MemoryAccess);
            }
            self.probe = value;
            Ok(())
        }
    }

    fn prepared() -> (
        PhysicalMemoryManager,
        ActiveAddressSpace,
        Memory,
        CoreRecord,
    ) {
        let (mut memory, core) = Memory::fixture();
        let mut manager = PhysicalMemoryManager::test_manager(4096, 128, 24);
        let tables = manager
            .allocate(Zone::Dma32, TABLE_PAGE_COUNT, TABLE_OWNER)
            .unwrap();
        let data = manager.allocate(Zone::Dma32, 1, DATA_OWNER).unwrap();
        let space = ActiveAddressSpace::initialize(
            &manager,
            tables,
            data,
            &mut memory,
            ORIGINAL_ROOT,
            core,
            48,
        )
        .unwrap();
        (manager, space, memory, core)
    }

    #[test]
    fn candidate_preserves_retained_mappings_and_owns_bounded_direct_map() {
        let (_manager, space, mut memory, core) = prepared();
        space.audit(&mut memory, core, 48).unwrap();
        let summary = space.summary();
        assert_eq!(MAPPED_OWNED_PAGE_COUNT, summary.mapped_owned_pages);
        assert_eq!(
            summary.candidate_root,
            summary.data_physical - 8 * PAGE_BYTES
        );
    }

    #[test]
    fn activation_readback_failure_restores_exact_original_cr3() {
        let (_manager, mut space, mut memory, _core) = prepared();
        let candidate = space.summary().candidate_root;
        let mut hardware = Hardware {
            memory: &mut memory,
            cr3: ORIGINAL_ROOT,
            candidate,
            cpu_id: BSP_CPU_ID,
            interrupts_disabled: true,
            reject_candidate_readback: true,
            reject_next_table_write: false,
            invalidations: std::vec::Vec::new(),
            probe: 0,
        };
        assert_eq!(
            space.activate(&mut hardware),
            Err(Error::ActivationMismatch)
        );
        assert_eq!(hardware.cr3, ORIGINAL_ROOT);
        assert_eq!(space.summary().activation_rollbacks, 1);
        assert!(!space.summary().root_active);
    }

    #[test]
    fn active_mutation_requires_exact_root_cpu_and_interrupt_state() {
        let (_manager, mut space, mut memory, _core) = prepared();
        let candidate = space.summary().candidate_root;
        let mut hardware = Hardware {
            memory: &mut memory,
            cr3: ORIGINAL_ROOT,
            candidate,
            cpu_id: BSP_CPU_ID,
            interrupts_disabled: true,
            reject_candidate_readback: false,
            reject_next_table_write: false,
            invalidations: std::vec::Vec::new(),
            probe: 0,
        };
        space.activate(&mut hardware).unwrap();
        hardware.cpu_id = 1;
        assert_eq!(space.write_probe(&mut hardware), Err(Error::CpuMismatch));
        hardware.cpu_id = BSP_CPU_ID;
        hardware.interrupts_disabled = false;
        assert_eq!(space.write_probe(&mut hardware), Err(Error::InterruptState));
        hardware.interrupts_disabled = true;
        hardware.cr3 = ORIGINAL_ROOT;
        assert_eq!(space.write_probe(&mut hardware), Err(Error::Cr3Mismatch));
    }

    #[test]
    fn active_receipts_withhold_reuse_until_both_aliases_are_invalidated() {
        let (mut manager, mut space, mut memory, _core) = prepared();
        let candidate = space.summary().candidate_root;
        let mut hardware = Hardware {
            memory: &mut memory,
            cr3: ORIGINAL_ROOT,
            candidate,
            cpu_id: BSP_CPU_ID,
            interrupts_disabled: true,
            reject_candidate_readback: false,
            reject_next_table_write: false,
            invalidations: std::vec::Vec::new(),
            probe: 0,
        };
        space.activate(&mut hardware).unwrap();
        space.write_probe(&mut hardware).unwrap();
        hardware.memory.pages.get_mut(&space.tables[3]).unwrap()[indices(USER_WINDOW_START)[3]] |=
            HARDWARE_LEAF_BITS;
        space.protect_user(&mut hardware).unwrap();
        let user = space.begin_user_unmap(&mut hardware).unwrap();
        assert_eq!(
            space.complete_data_release(&mut manager, &mut hardware, user, None),
            Err(Error::InvalidationRequired)
        );
        let direct = space.revoke_data_direct_map(&mut hardware).unwrap();
        space
            .complete_data_release(&mut manager, &mut hardware, user, Some(direct))
            .unwrap();
        assert_eq!(hardware.invalidations.len(), 3);
        space.restore(&mut hardware).unwrap();
        drop(hardware);
        space.release_tables(&mut manager, &mut memory).unwrap();
        assert_eq!(manager.summary().allocated_pages, 0);
    }

    #[test]
    fn active_leaf_write_failure_rolls_back_without_minting_receipt() {
        let (_manager, mut space, mut memory, _core) = prepared();
        let candidate = space.summary().candidate_root;
        let mut hardware = Hardware {
            memory: &mut memory,
            cr3: ORIGINAL_ROOT,
            candidate,
            cpu_id: BSP_CPU_ID,
            interrupts_disabled: true,
            reject_candidate_readback: false,
            reject_next_table_write: false,
            invalidations: std::vec::Vec::new(),
            probe: 0,
        };
        space.activate(&mut hardware).unwrap();
        hardware.reject_next_table_write = true;
        assert_eq!(
            space.protect_user(&mut hardware),
            Err(Error::ProtectTransaction)
        );
        assert!(hardware.invalidations.is_empty());
        assert_eq!(space.summary().active_receipts, 0);
    }

    #[test]
    fn occupied_direct_root_slot_fails_closed() {
        let (mut memory, core) = Memory::fixture();
        memory.pages.get_mut(&ORIGINAL_ROOT).unwrap()[indices(DIRECT_MAP_START)[0]] =
            0x0400_0000 | ENTRY_PRESENT;
        let mut manager = PhysicalMemoryManager::test_manager(4096, 128, 24);
        let tables = manager
            .allocate(Zone::Dma32, TABLE_PAGE_COUNT, TABLE_OWNER)
            .unwrap();
        let data = manager.allocate(Zone::Dma32, 1, DATA_OWNER).unwrap();
        assert!(matches!(
            ActiveAddressSpace::initialize(
                &manager,
                tables,
                data,
                &mut memory,
                ORIGINAL_ROOT,
                core,
                48,
            ),
            Err(Error::RootSlotOccupied)
        ));
    }
}
