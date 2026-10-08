//! Never-exposed task construction. Errors retain an explicit retryable owner.
#![forbid(unsafe_code)]

use super::{
    InitialImage,
    prepared::{self, DetachedImage, PreparedImage},
    timer,
};
use crate::{
    physical_memory::{AllocationHandle, PhysicalMemoryManager, RetainedAllocation, Zone},
    reclamation::task_lifetimes::{STACK_OWNER, STACK_PAGE_COUNT},
    virtual_memory::{self as vm, AddressSpace, CachePolicy, Permissions, TableMemory},
};
use poole_handoff::{CoreRecord, PAGE_BYTES};

pub const CONTRACT_ID: &str = "PKUSER11";
const SHAPES: [(u64, u16); 5] = [
    (vm::TABLE_PAGE_COUNT, vm::TABLE_OWNER),
    (1, vm::DATA_OWNER),
    (1, vm::DATA_OWNER),
    (STACK_PAGE_COUNT, STACK_OWNER),
    (prepared::STACK_TABLE_PAGES, prepared::STACK_TABLE_OWNER),
];

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum Error {
    State,
    Allocation,
    Ownership,
    Layout,
    Memory,
    Readback,
    Mapping,
    Preparation,
}

#[derive(Clone, Copy, Eq, PartialEq)]
enum State {
    Allocating,
    Building,
    Discarding,
    Transferred,
}

/// Owns all partial allocations without publishing a root. Cleanup is explicit
/// and fallible: dropping this owner deliberately leaves its pages retained.
///
/// ```compile_fail
/// use poolekernel::user_entry::spawn::Construction;
/// fn duplicate(value: &Construction) -> Construction { value.clone() }
/// ```
#[must_use = "failed construction must be rolled back or retained for retry"]
pub struct Construction {
    retained: [Option<RetainedAllocation>; 5],
    state: State,
}

impl Default for Construction {
    fn default() -> Self {
        Self::new()
    }
}
impl Construction {
    pub fn new() -> Self {
        Self {
            retained: core::array::from_fn(|_| None),
            state: State::Allocating,
        }
    }
    pub fn handles(&self) -> [Option<AllocationHandle>; 5] {
        self.retained
            .each_ref()
            .map(|r| r.as_ref().map(RetainedAllocation::handle))
    }
    /// A failed allocation preserves the preceding allocations and closes
    /// construction. It does not leak an unretained last allocation.
    pub fn allocate_next(&mut self, manager: &mut PhysicalMemoryManager) -> Result<(), Error> {
        if self.state != State::Allocating {
            return Err(Error::State);
        }
        manager
            .validate_retentions(&self.retained)
            .map_err(|_| Error::Ownership)?;
        let index = self
            .retained
            .iter()
            .position(Option::is_none)
            .ok_or(Error::State)?;
        let (pages, owner) = SHAPES[index];
        match manager.allocate_retained(Zone::Dma32, pages, owner) {
            Ok(token) => {
                self.retained[index] = Some(token);
                Ok(())
            }
            Err(_) => {
                self.state = State::Discarding;
                Err(Error::Allocation)
            }
        }
    }

    #[allow(clippy::too_many_arguments)]
    pub fn build<M: TableMemory>(
        &mut self,
        manager: &mut PhysicalMemoryManager,
        memory: &mut M,
        payload: &[u8],
        image: InitialImage,
        core: CoreRecord,
        bits: u8,
        timer: Option<timer::Mappings>,
    ) -> Result<PreparedImage, Error> {
        if self.state != State::Allocating || self.retained.iter().any(Option::is_none) {
            return Err(Error::State);
        }
        manager
            .validate_retentions(&self.retained)
            .map_err(|_| Error::Ownership)?;
        self.state = State::Building;
        let [tables, code, stack, entry_stack, entry_tables] = self.handles().map(Option::unwrap);
        image.validate().map_err(|_| Error::Layout)?;
        let offset = usize::try_from(image.entry - image.code_page).map_err(|_| Error::Layout)?;
        if payload.is_empty() || offset % 8 != 0 || payload.len() > PAGE_BYTES as usize - offset {
            return Err(Error::Layout);
        }
        for handle in [code, stack, entry_stack] {
            erase(memory, handle)?;
        }
        for (index, chunk) in payload.chunks(8).enumerate() {
            let mut word = [0; 8];
            word[..chunk.len()].copy_from_slice(chunk);
            checked_write(
                memory,
                code.start_page * PAGE_BYTES,
                offset / 8 + index,
                u64::from_le_bytes(word),
            )?;
        }
        let mut space =
            AddressSpace::initialize(manager, tables, memory).map_err(|_| Error::Mapping)?;
        for (address, frame, permissions) in [
            (image.code_page, code, Permissions::USER_RX),
            (image.stack_page, stack, Permissions::USER_RW),
        ] {
            space
                .map(
                    manager,
                    memory,
                    address,
                    frame,
                    permissions,
                    CachePolicy::WriteBack,
                )
                .map_err(|_| Error::Mapping)?;
        }
        let mut retained = core::array::from_fn(|_| None);
        for (source, destination) in [0, 1, 2, vm::MAX_FRAMES + 1, vm::MAX_FRAMES + 2]
            .into_iter()
            .enumerate()
        {
            retained[destination] = self.retained[source].take();
        }
        match PreparedImage::prepare_retained(
            DetachedImage {
                space,
                stack: entry_stack,
                stack_tables: entry_tables,
            },
            retained,
            manager,
            memory,
            image,
            core,
            bits,
            timer,
        ) {
            Ok(prepared) => {
                self.state = State::Transferred;
                Ok(prepared)
            }
            Err((_, mut retained)) => {
                for (destination, source) in [0, 1, 2, vm::MAX_FRAMES + 1, vm::MAX_FRAMES + 2]
                    .into_iter()
                    .enumerate()
                {
                    self.retained[destination] = retained[source].take();
                }
                Err(Error::Preparation)
            }
        }
    }

    /// Never-active roots need no TLB shootdown. Erase and read back the ENTIRE
    /// owned batch, then finish access, before freeing its first page. A failed
    /// free keeps its exact token; retry visits only the still-owned allocations.
    pub fn abort<M: TableMemory>(
        &mut self,
        manager: &mut PhysicalMemoryManager,
        memory: &mut M,
    ) -> Result<(), Error> {
        if self.state == State::Transferred {
            return Err(Error::State);
        }
        manager
            .validate_retentions(&self.retained)
            .map_err(|_| Error::Ownership)?;
        self.state = State::Discarding;
        for handle in self.handles().into_iter().flatten() {
            erase(memory, handle)?;
        }
        memory.finish().map_err(|_| Error::Memory)?;
        for member in &mut self.retained {
            if let Some(token) = member.take() {
                if let Err((_, token)) = manager.free_retained(token) {
                    *member = Some(token);
                    return Err(Error::Ownership);
                }
            }
        }
        Ok(())
    }
}

fn checked_write<M: TableMemory>(
    memory: &mut M,
    page: u64,
    index: usize,
    value: u64,
) -> Result<(), Error> {
    memory
        .write_entry(page, index, value)
        .map_err(|_| Error::Memory)?;
    if memory.read_entry(page, index).map_err(|_| Error::Memory)? != value {
        return Err(Error::Readback);
    }
    Ok(())
}
fn erase<M: TableMemory>(memory: &mut M, handle: AllocationHandle) -> Result<(), Error> {
    for page in handle.start_page..handle.start_page + handle.page_count {
        let page = page * PAGE_BYTES;
        memory.prepare_page(page).map_err(|_| Error::Memory)?;
        for index in 0..vm::TABLE_ENTRIES {
            checked_write(memory, page, index, 0)?;
        }
    }
    Ok(())
}
