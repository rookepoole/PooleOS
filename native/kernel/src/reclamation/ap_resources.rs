//! PKAPOWN1: retained execution resources for the existing three-AP profile.
//! Allocator ownership is enforced; hardware quiescence is an unsafe boundary.

use crate::physical_memory::{
    AllocationHandle, MetadataArenaAccess, PhysicalMemoryError, PhysicalMemoryManager,
    PhysicalPageAccess, RetainedAllocation, ScrubReceipt, Zone,
};
use crate::{smp_ipi, smp_runtime};

pub const CONTRACT_ID: &str = "PKAPOWN1";

fn target_mask(apic_id: u32) -> Result<u64, Error> {
    smp_ipi::local_target_mask(apic_id)
        .filter(|mask| mask & smp_ipi::TARGET_CPU_MASK != 0)
        .ok_or(Error::Target)
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum Part {
    Runtime,
    OldFrame,
    NewFrame,
}

impl Part {
    const fn index(self) -> usize {
        match self {
            Self::Runtime => 0,
            Self::OldFrame => 1,
            Self::NewFrame => 2,
        }
    }
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum State {
    Prepared,
    MayExecute,
    Parked,
    Releasing,
    Released,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum Error {
    Target,
    Layout,
    State,
    ParkMask,
    Released,
    PhysicalMemory(PhysicalMemoryError),
}

/// Owns the runtime allocation (RSP0/IST stacks included) and both data frames.
/// Loss of this object retains every still-owned allocation, even with forget.
/// Copyable handles remain diagnostic identifiers, not release authority.
///
/// ```compile_fail
/// use poolekernel::reclamation::ap_resources::ApResources;
/// fn copy(owner: &ApResources) -> ApResources { owner.clone() }
/// ```
///
/// ```compile_fail
/// use poolekernel::reclamation::ap_resources::ApResources;
/// fn invent_park(owner: &mut ApResources) { owner.confirm_parked(14).unwrap(); }
/// ```
pub struct ApResources {
    target_apic_id: u32,
    handles: [AllocationHandle; 3],
    retained: [Option<RetainedAllocation>; 3],
    receipts: [Option<ScrubReceipt>; 3],
    possible_cpu_mask: u64,
    state: State,
}

impl ApResources {
    /// Admission is atomic across all three allocations; failure retains none.
    pub fn new(
        manager: &mut PhysicalMemoryManager,
        target_apic_id: u32,
        runtime: AllocationHandle,
        old_frame: AllocationHandle,
        new_frame: AllocationHandle,
    ) -> Result<Self, Error> {
        target_mask(target_apic_id)?;
        smp_runtime::ResourceLayout::new(runtime.start_page, runtime.page_count)
            .map_err(|_| Error::Layout)?;
        let handles = [runtime, old_frame, new_frame];
        if handles.iter().any(|handle| handle.zone != Zone::Dma)
            || old_frame.page_count != 1
            || new_frame.page_count != 1
        {
            return Err(Error::Layout);
        }
        let retained = manager
            .retain_allocations(handles.map(Some))
            .map_err(Error::PhysicalMemory)?;
        Ok(Self {
            target_apic_id,
            handles,
            retained,
            receipts: [None; 3],
            possible_cpu_mask: 0,
            state: State::Prepared,
        })
    }

    pub const fn target_apic_id(&self) -> u32 {
        self.target_apic_id
    }

    pub const fn handle(&self, part: Part) -> AllocationHandle {
        self.handles[part.index()]
    }

    pub const fn state(&self) -> State {
        self.state
    }

    pub const fn possible_cpu_mask(&self) -> u64 {
        self.possible_cpu_mask
    }

    pub const fn release_receipt(&self, part: Part) -> Option<ScrubReceipt> {
        self.receipts[part.index()]
    }

    /// Call for every potentially shared region before attempting CPU startup.
    /// Even a failed startup must remain in this mask until confirmed parked.
    pub fn expose_to_cpu(&mut self, target_apic_id: u32) -> Result<(), Error> {
        let mask = target_mask(target_apic_id)?;
        if !matches!(self.state, State::Prepared | State::MayExecute) {
            return Err(Error::State);
        }
        self.possible_cpu_mask |= mask;
        self.state = State::MayExecute;
        Ok(())
    }

    /// # Safety
    /// Every CPU in the exact mask must have completed the platform's final
    /// stop/park sequence and be unable to resume or access these resources.
    /// A mailbox, scheduler Dead state, timeout or omitted ACK is insufficient.
    /// All CPUs that could use shared aliases must have been exposed above.
    pub unsafe fn confirm_parked(&mut self, parked_mask: u64) -> Result<(), Error> {
        if parked_mask != self.possible_cpu_mask {
            return Err(Error::ParkMask);
        }
        if matches!(self.state, State::Prepared | State::MayExecute) {
            self.state = State::Parked;
        }
        Ok(())
    }

    pub fn release_scrubbed<A: PhysicalPageAccess>(
        &mut self,
        part: Part,
        manager: &mut PhysicalMemoryManager,
        access: &mut A,
    ) -> Result<ScrubReceipt, Error> {
        self.release_with(part, |token| manager.free_retained_scrubbed(token, access))
    }

    pub fn release_scrubbed_automatic<A: MetadataArenaAccess>(
        &mut self,
        part: Part,
        manager: &mut PhysicalMemoryManager,
        access: &mut A,
    ) -> Result<ScrubReceipt, Error> {
        self.release_with(part, |token| {
            manager
                .free_retained_scrubbed_automatic(token, access)
                .map(|(receipt, _)| receipt)
        })
    }

    fn release_with<F>(&mut self, part: Part, release: F) -> Result<ScrubReceipt, Error>
    where
        F: FnOnce(
            RetainedAllocation,
        ) -> Result<ScrubReceipt, (PhysicalMemoryError, RetainedAllocation)>,
    {
        if self.state == State::MayExecute {
            return Err(Error::State);
        }
        let index = part.index();
        let token = self.retained[index].take().ok_or(Error::Released)?;
        // A partial scrub also closes startup: retry cleanup, never execute it.
        self.state = State::Releasing;
        match release(token) {
            Ok(receipt) => {
                self.receipts[index] = Some(receipt);
                if self.retained.iter().all(Option::is_none) {
                    self.state = State::Released;
                }
                Ok(receipt)
            }
            Err((error, token)) => {
                self.retained[index] = Some(token);
                Err(Error::PhysicalMemory(error))
            }
        }
    }
}
