//! Bounded address policy for the development-only original-root access adapter.
//! This is not an allocation capability or proof of live identity translation.

use super::{physical_mask, prepared};
use crate::physical_memory::{AllocationHandle, PhysicalMemoryManager, Zone};
use crate::reclamation::task_lifetimes::{STACK_OWNER, STACK_PAGE_COUNT};
use crate::virtual_memory::{self as vm, Error};
use poole_handoff::PAGE_BYTES;

pub struct Access {
    root: u64,
    owned: [AllocationHandle; 5],
}

impl Access {
    pub fn new(
        manager: &PhysicalMemoryManager,
        root: u64,
        bits: u8,
        owned: [AllocationHandle; 5],
    ) -> Result<Self, Error> {
        let mask = physical_mask(bits).map_err(|_| Error::MemoryAccess)?;
        let boot_end = root
            .checked_add(5 * PAGE_BYTES)
            .ok_or(Error::MemoryAccess)?;
        if root == 0 || root & !mask != 0 || (boot_end - PAGE_BYTES) & !mask != 0 {
            return Err(Error::MemoryAccess);
        }
        let shapes = [
            (vm::TABLE_OWNER, vm::TABLE_PAGE_COUNT),
            (vm::DATA_OWNER, 1),
            (vm::DATA_OWNER, 1),
            (STACK_OWNER, STACK_PAGE_COUNT),
            (prepared::STACK_TABLE_OWNER, prepared::STACK_TABLE_PAGES),
        ];
        for (i, h) in owned.iter().enumerate() {
            manager
                .validate_allocation(*h)
                .map_err(|_| Error::Ownership)?;
            let start = h
                .start_page
                .checked_mul(PAGE_BYTES)
                .ok_or(Error::MemoryAccess)?;
            let end = h
                .start_page
                .checked_add(h.page_count)
                .and_then(|p| p.checked_mul(PAGE_BYTES))
                .ok_or(Error::MemoryAccess)?;
            if (h.owner, h.page_count) != shapes[i]
                || h.zone != Zone::Dma32
                || start == 0
                || start & !mask != 0
                || (end - PAGE_BYTES) & !mask != 0
                || (start < boot_end && root < end)
            {
                return Err(Error::Ownership);
            }
            for prior in &owned[..i] {
                if h.start_page < prior.start_page + prior.page_count
                    && prior.start_page < h.start_page + h.page_count
                {
                    return Err(Error::Ownership);
                }
            }
        }
        Ok(Self { root, owned })
    }

    /// Caller still proves current CPU state, exact identity/cache translation,
    /// serialized access and live ownership before dereferencing this address.
    pub fn address(
        &self,
        current_root: u64,
        table: u64,
        index: usize,
        write: bool,
    ) -> Result<u64, Error> {
        if current_root != self.root
            || !table.is_multiple_of(PAGE_BYTES)
            || index >= vm::TABLE_ENTRIES
        {
            return Err(Error::MemoryAccess);
        }
        let owned = self.owned.iter().any(|h| {
            let start = h.start_page * PAGE_BYTES;
            (start..start + h.page_count * PAGE_BYTES).contains(&table)
        });
        let boot_read = !write && (self.root..self.root + 5 * PAGE_BYTES).contains(&table);
        if !owned && !boot_read {
            return Err(Error::MemoryAccess);
        }
        table
            .checked_add(index as u64 * 8)
            .ok_or(Error::MemoryAccess)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn fixture() -> (PhysicalMemoryManager, [AllocationHandle; 5]) {
        let mut p = PhysicalMemoryManager::test_manager(4096, 64, 32);
        let owned = [
            p.allocate(Zone::Dma32, 4, vm::TABLE_OWNER).unwrap(),
            p.allocate(Zone::Dma32, 1, vm::DATA_OWNER).unwrap(),
            p.allocate(Zone::Dma32, 1, vm::DATA_OWNER).unwrap(),
            p.allocate(Zone::Dma32, 4, STACK_OWNER).unwrap(),
            p.allocate(Zone::Dma32, 3, prepared::STACK_TABLE_OWNER)
                .unwrap(),
        ];
        (p, owned)
    }

    #[test]
    fn exact_owned_pages_and_read_only_boot_pages_are_bounded() {
        let (p, owned) = fixture();
        let a = Access::new(&p, 0x100000, 36, owned).unwrap();
        for h in owned {
            for page in h.start_page..h.start_page + h.page_count {
                for index in [0, 511] {
                    assert_eq!(
                        a.address(0x100000, page * PAGE_BYTES, index, true),
                        Ok(page * PAGE_BYTES + index as u64 * 8)
                    );
                }
            }
        }
        for page in 0..5 {
            let table = 0x100000 + page * PAGE_BYTES;
            assert!(a.address(0x100000, table, 511, false).is_ok());
            assert_eq!(
                a.address(0x100000, table, 0, true),
                Err(Error::MemoryAccess)
            );
        }
    }

    #[test]
    fn other_roots_unowned_pages_and_overflow_indices_are_denied() {
        let (p, owned) = fixture();
        let a = Access::new(&p, 0x100000, 36, owned).unwrap();
        for (root, table, index) in [
            (0x100008, 0x100000, 0),
            (0x200000, 0x100000, 0),
            (0x100000, 0x105000, 0),
            (0x100000, 0x100001, 0),
            (0x100000, 0x100000, 512),
            (0x100000, u64::MAX, usize::MAX),
        ] {
            assert_eq!(
                a.address(root, table, index, false),
                Err(Error::MemoryAccess)
            );
        }
    }

    #[test]
    fn stale_duplicate_wrong_shape_and_boot_alias_handles_are_denied() {
        let (mut p, owned) = fixture();
        let mut changed = owned;
        changed[2] = changed[1];
        assert!(Access::new(&p, 0x100000, 36, changed).is_err());
        changed = owned;
        changed.swap(0, 3);
        assert!(Access::new(&p, 0x100000, 36, changed).is_err());
        assert!(Access::new(&p, owned[0].start_page * PAGE_BYTES, 36, owned).is_err());
        p.free(owned[1]).unwrap();
        assert!(Access::new(&p, 0x100000, 36, owned).is_err());
    }

    #[test]
    fn invalid_physical_width_and_root_shapes_are_denied() {
        let (p, owned) = fixture();
        for (root, bits) in [
            (0, 36),
            (0x100001, 36),
            (1 << 36, 36),
            ((1 << 36) - PAGE_BYTES, 36),
            (0x100000, 35),
            (0x100000, 53),
        ] {
            assert!(Access::new(&p, root, bits, owned).is_err());
        }
    }
}
