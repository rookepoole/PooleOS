//! Allocation-level retention; not a hardware-quiescence or capability proof.

#![forbid(unsafe_code)]

use core::sync::atomic::{AtomicU64, Ordering};

use super::{AllocationHandle, PhysicalMemoryError as Error, PhysicalMemoryManager};

// One boot-lifetime namespace across all managers. Zero is never issued, and
// exhaustion permanently closes admission instead of recycling identities.
static NEXT_RETENTION_ID: AtomicU64 = AtomicU64::new(1);

fn reserve_identity(next: &AtomicU64) -> Result<u64, Error> {
    next.fetch_update(Ordering::Relaxed, Ordering::Relaxed, |value| {
        value.checked_add(1)
    })
    .map_err(|_| Error::RetentionExhausted)
}

/// Exclusive authority to end one allocation's retention, independent of its
/// copyable diagnostic handle. Dropping or forgetting this value retains pages.
/// It is not a capability, CPU acknowledgement, or permission to destroy aliases.
///
/// ```compile_fail
/// use poolekernel::physical_memory::RetainedAllocation;
/// fn duplicate(value: &RetainedAllocation) -> RetainedAllocation {
///     value.clone()
/// }
/// ```
///
/// ```compile_fail
/// use poolekernel::physical_memory::{PhysicalMemoryManager, RetainedAllocation};
/// fn borrowed_release(manager: &mut PhysicalMemoryManager, value: &RetainedAllocation) {
///     let _ = manager.release_retention(*value);
/// }
/// ```
#[derive(Debug)]
#[must_use = "dropping the token permanently retains the allocation"]
pub struct RetainedAllocation {
    handle: AllocationHandle,
    identity: u64,
}

impl RetainedAllocation {
    pub const fn handle(&self) -> AllocationHandle {
        self.handle
    }
}

impl PhysicalMemoryManager {
    /// Retain a currently live ordinary allocation. All free entry points reject
    /// even a previously copied handle until this exact token is consumed.
    pub fn retain_allocation(
        &mut self,
        handle: AllocationHandle,
    ) -> Result<RetainedAllocation, Error> {
        self.require_operational()?;
        self.validate_allocation_inner(handle)?;
        let slot = usize::from(handle.slot);
        let allocation = self.allocation_entries()[slot];
        if allocation.release_excluded {
            return Err(Error::MetadataOwnership);
        }
        if allocation.retention_id != 0 {
            return Err(Error::AllocationRetained);
        }
        let identity = reserve_identity(&NEXT_RETENTION_ID)?;
        self.allocation_entries_mut()[slot].retention_id = identity;
        self.seal_metadata_integrity();
        Ok(RetainedAllocation { handle, identity })
    }

    /// End retention without freeing or touching physical memory. The caller
    /// must first revoke every reader and hardware alias. The allocation stays
    /// live; existing scrub/release APIs still apply. Errors return the token.
    pub fn release_retention(
        &mut self,
        retained: RetainedAllocation,
    ) -> Result<AllocationHandle, (Error, RetainedAllocation)> {
        let validate = (|| {
            self.require_operational()?;
            self.validate_allocation_inner(retained.handle)?;
            let allocation = self.allocation_entries()[usize::from(retained.handle.slot)];
            if allocation.retention_id != retained.identity || retained.identity == 0 {
                return Err(Error::RetentionIdentity);
            }
            if allocation.release_excluded {
                return Err(Error::MetadataOwnership);
            }
            Ok(())
        })();
        if let Err(error) = validate {
            return Err((error, retained));
        }
        self.allocation_entries_mut()[usize::from(retained.handle.slot)].retention_id = 0;
        self.seal_metadata_integrity();
        Ok(retained.handle)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn identity_exhaustion_never_wraps_or_reissues() {
        let next = AtomicU64::new(u64::MAX - 1);
        assert_eq!(reserve_identity(&next), Ok(u64::MAX - 1));
        for _ in 0..3 {
            assert_eq!(reserve_identity(&next), Err(Error::RetentionExhausted));
        }
        assert_eq!(next.load(Ordering::Relaxed), u64::MAX);
    }
}
