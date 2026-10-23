//! Retryable whole-image destruction after CPU/root and device quiescence.
#![forbid(unsafe_code)]

use super::prepared::OWNED_COUNT;
use crate::physical_memory::{AllocationHandle, PhysicalMemoryManager, RetainedAllocation};
use crate::virtual_memory::{TABLE_ENTRIES, TableMemory};
use poole_handoff::PAGE_BYTES;

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum Error {
    Ownership,
    Memory,
    Readback,
}

/// Only the CPU lifecycle can transfer these tokens after a flushing restoration.
/// The private root is never shared with another CPU. Destroying its owned tables
/// does not follow their links or write into the boot-owned kernel subtree.
/// Dropping this object retains, rather than frees, unfinished allocations.
///
/// ```compile_fail
/// use poolekernel::user_entry::retirement::RetiredImage;
/// fn duplicate(image: &RetiredImage) -> RetiredImage { image.clone() }
/// ```
#[must_use = "retired image must be reclaimed or retained for retry"]
pub struct RetiredImage {
    retained: [Option<RetainedAllocation>; OWNED_COUNT],
}

impl RetiredImage {
    pub(super) fn new(retained: [Option<RetainedAllocation>; OWNED_COUNT]) -> Self {
        Self { retained }
    }

    pub fn remaining_pages(&self) -> u64 {
        self.retained
            .iter()
            .flatten()
            .map(|r| r.handle().page_count)
            .sum()
    }

    /// Errors preserve every still-live token. No allocation is freed until all
    /// remaining pages have been zeroed, read back and the adapter has finished.
    /// A retry never touches an allocation already freed by an earlier attempt.
    pub fn reclaim<M: TableMemory>(
        &mut self,
        manager: &mut PhysicalMemoryManager,
        memory: &mut M,
    ) -> Result<(), Error> {
        manager
            .validate_retentions(&self.retained)
            .map_err(|_| Error::Ownership)?;
        for token in self.retained.iter().flatten() {
            erase(memory, token.handle())?;
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

fn erase<M: TableMemory>(memory: &mut M, handle: AllocationHandle) -> Result<(), Error> {
    let end = handle
        .start_page
        .checked_add(handle.page_count)
        .ok_or(Error::Ownership)?;
    for page in handle.start_page..end {
        let address = page.checked_mul(PAGE_BYTES).ok_or(Error::Ownership)?;
        memory.prepare_page(address).map_err(|_| Error::Memory)?;
        for index in 0..TABLE_ENTRIES {
            memory
                .write_entry(address, index, 0)
                .map_err(|_| Error::Memory)?;
            if memory
                .read_entry(address, index)
                .map_err(|_| Error::Memory)?
                != 0
            {
                return Err(Error::Readback);
            }
        }
    }
    Ok(())
}
