//! Bounded supervisor MMIO layout and trusted timer-driver boundary.
#![forbid(unsafe_code)]

use crate::physical_memory::PhysicalMemoryManager;
use crate::virtual_memory::KERNEL_START;
use poole_handoff::{Handoff, MEMORY_ENTRY_BYTES, MEMORY_MMIO, PAGE_BYTES, RECORD_MEMORY_MAP};

pub mod clock;
pub mod drain;
pub mod watchdog;

pub const CONTRACT_ID: &str = "PKUSER4";
pub const APIC_SLOT: usize = 16;
pub const HPET_SLOT: usize = 18;
pub const APIC_VIRTUAL: u64 = KERNEL_START + APIC_SLOT as u64 * PAGE_BYTES;
pub const HPET_VIRTUAL: u64 = KERNEL_START + HPET_SLOT as u64 * PAGE_BYTES;
const FLAGS: u64 = 1 | 2 | (1 << 3) | (1 << 4) | (1 << 63);

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum Error {
    Address,
    Pat,
    Source,
    Alias,
    Hardware,
    Context,
    State,
}

/// An immutable mapping plan, not device authority. The platform adapter must
/// validate ACPI/APIC identity, own the devices exclusively, and serialize PAT
/// and memory-map state until the CPU owner has retired the mappings.
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct Mappings {
    apic: u64,
    hpet: u64,
}

impl Mappings {
    pub fn from_handoff(
        handoff: &Handoff<'_>,
        apic: u64,
        hpet: u64,
        bits: u8,
        pat: u64,
    ) -> Result<Self, Error> {
        let record = handoff.record(RECORD_MEMORY_MAP).ok_or(Error::Source)?;
        Self::checked(record.payload, apic, hpet, bits, pat)
    }

    fn checked(map: &[u8], apic: u64, hpet: u64, bits: u8, pat: u64) -> Result<Self, Error> {
        let mask = super::physical_mask(bits).map_err(|_| Error::Address)?;
        if apic == 0 || apic & !mask != 0 || hpet == 0 || hpet & !mask != 0 || apic == hpet {
            return Err(Error::Address);
        }
        // PWT=PCD=1, PAT=0 selects PAT entry 3. Never assume firmware's PAT.
        if (pat >> 24) & 0xff != 0 {
            return Err(Error::Pat);
        }
        if map.is_empty() || !map.len().is_multiple_of(MEMORY_ENTRY_BYTES) {
            return Err(Error::Source);
        }
        for entry in map.chunks_exact(MEMORY_ENTRY_BYTES) {
            let start = u64::from_le_bytes(entry[0..8].try_into().map_err(|_| Error::Source)?);
            let pages = u64::from_le_bytes(entry[8..16].try_into().map_err(|_| Error::Source)?);
            let bytes = pages.checked_mul(PAGE_BYTES).ok_or(Error::Source)?;
            let end = start.checked_add(bytes).ok_or(Error::Source)?;
            let kind = u32::from_le_bytes(entry[24..28].try_into().map_err(|_| Error::Source)?);
            if bytes == 0 || start & 4095 != 0 || bytes & 4095 != 0 {
                return Err(Error::Source);
            }
            for page in [apic, hpet] {
                if page < end && start < page + PAGE_BYTES && kind != MEMORY_MMIO {
                    return Err(Error::Alias);
                }
            }
        }
        Ok(Self { apic, hpet })
    }

    /// Recheck that these device pages do not alias allocator-admitted RAM.
    /// This does not grant device ownership or install a mapping.
    pub fn validate(&self, manager: &PhysicalMemoryManager, bits: u8) -> Result<(), Error> {
        let mask = super::physical_mask(bits).map_err(|_| Error::Address)?;
        if self.apic & !mask != 0 || self.hpet & !mask != 0 {
            return Err(Error::Address);
        }
        let manifest = manager
            .preview_direct_map_manifest()
            .map_err(|_| Error::Alias)?;
        for range in manifest.admitted_ranges() {
            for address in self.pages() {
                let page = address / PAGE_BYTES;
                if page >= range.start_page && page - range.start_page < range.page_count {
                    return Err(Error::Alias);
                }
            }
        }
        Ok(())
    }

    pub const fn pages(self) -> [u64; 2] {
        [self.apic, self.hpet]
    }
    pub(crate) fn leaf(self, index: usize) -> Option<u64> {
        match index {
            APIC_SLOT => Some(self.apic | FLAGS),
            HPET_SLOT => Some(self.hpet | FLAGS),
            _ => None,
        }
    }

    #[cfg(test)]
    pub(crate) fn fixture() -> Self {
        Self {
            apic: 0xfee0_0000,
            hpet: 0xfed0_0000,
        }
    }
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct Observation {
    pub deliveries: u32,
    pub eois: u32,
    pub observed_root: u64,
}

/// Trusted privileged adapter, with the same exclusive one-BSP lease as Cpu.
/// Both methods must return with IF clear. Failure may follow device effects.
/// `quiesce` must observe the exact root/layout, stop the timer, mask all sources,
/// drain/deny pending and in-service work, and verify shutdown before success.
/// An adapter must not re-arm devices outside this owning lifecycle.
pub trait Driver {
    fn execute(&mut self, root: u64, mappings: Mappings) -> Result<Observation, Error>;
    fn quiesce(&mut self, root: u64, mappings: Mappings) -> Result<(), Error>;
}

#[cfg(test)]
mod tests {
    use super::*;
    fn map(start: u64, pages: u64, kind: u32) -> [u8; MEMORY_ENTRY_BYTES] {
        let mut data = [0; MEMORY_ENTRY_BYTES];
        data[..8].copy_from_slice(&start.to_le_bytes());
        data[8..16].copy_from_slice(&pages.to_le_bytes());
        data[24..28].copy_from_slice(&kind.to_le_bytes());
        data
    }
    #[test]
    fn exact_layout_has_supervisor_nx_uc_leaves_and_absent_guards() {
        let m = Mappings::checked(&map(0, 1, 1), 0xfee0_0000, 0xfed0_0000, 36, 0).unwrap();
        assert_eq!(m.leaf(APIC_SLOT), Some(0xfee0_0000 | FLAGS));
        assert_eq!(m.leaf(HPET_SLOT), Some(0xfed0_0000 | FLAGS));
        for i in [0, 5, 15, 17, 19, 511] {
            assert_eq!(m.leaf(i), None);
        }
        assert_eq!(FLAGS & ((1 << 2) | (1 << 7) | (1 << 8)), 0);
    }
    #[test]
    fn malformed_addresses_and_non_uc_pat_reject() {
        let bytes = map(0, 1, 1);
        for (a, h, b, p) in [
            (0, 0xfed0_0000, 36, 0),
            (1, 0xfed0_0000, 36, 0),
            (0xfee0_0000, 0xfee0_0000, 36, 0),
            (1 << 40, 0xfed0_0000, 36, 0),
            (0xfee0_0000, 0xfed0_0000, 35, 0),
            (0xfee0_0000, 0xfed0_0000, 36, 6 << 24),
        ] {
            assert!(Mappings::checked(&bytes, a, h, b, p).is_err());
        }
    }
    #[test]
    fn source_ram_alias_and_malformed_source_reject() {
        for kind in 0..=9 {
            let result =
                Mappings::checked(&map(0xfee0_0000, 1, kind), 0xfee0_0000, 0xfed0_0000, 36, 0);
            assert_eq!(result.is_ok(), kind == MEMORY_MMIO);
        }
        for bytes in [
            &[][..],
            &[0; 39][..],
            &map(0, 0, 1)[..],
            &map(u64::MAX - 4095, 8192, 7)[..],
        ] {
            assert!(Mappings::checked(bytes, 0xfee0_0000, 0xfed0_0000, 36, 0).is_err());
        }
    }
    #[test]
    fn allocator_ram_alias_rejects_even_with_different_boot_plan() {
        let manager = PhysicalMemoryManager::test_manager(0xfee0_0000 / PAGE_BYTES, 64, 32);
        assert_eq!(
            Mappings::fixture().validate(&manager, 36),
            Err(Error::Alias)
        );
    }
}
