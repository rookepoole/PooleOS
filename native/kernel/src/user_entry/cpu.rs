//! Serialized single-BSP CR3 lifecycle with quarantined timer/user adapters.
//!
//! The hardware adapter is a trusted boundary, like PKVM3 ActiveHardware. A
//! passing mock proves the state machine, not execution or hardware retirement.

use super::{CoreRecord, DetachedImage, PhysicalMemoryManager, PreparedImage, TableMemory};
use crate::user_entry::privilege;
use crate::user_entry::timer;

pub const CONTRACT_ID: &str = "PKUSER3";
const CR0_REQUIRED: u64 = 1 | (1 << 16) | (1 << 31);
const CR4_PAE: u64 = 1 << 5;
const CR4_UNSUPPORTED: u64 = (1 << 7) | (1 << 12) | (1 << 17);
const EFER_REQUIRED: u64 = (1 << 8) | (1 << 10) | (1 << 11);

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct Snapshot {
    pub cpu_id: u32,
    pub active_cpus: u32,
    pub cr0: u64,
    pub cr3: u64,
    pub cr4: u64,
    pub efer: u64,
    pub rflags: u64,
}

impl Snapshot {
    fn supported(self) -> bool {
        self.active_cpus == 1
            && self.rflags & (1 << 9) == 0
            && self.cr0 & CR0_REQUIRED == CR0_REQUIRED
            && self.cr4 & CR4_PAE != 0
            && self.cr4 & CR4_UNSUPPORTED == 0
            && self.efer & EFER_REQUIRED == EFER_REQUIRED
    }

    fn same_context(self, other: Self) -> bool {
        self.supported()
            && self.cpu_id == other.cpu_id
            && self.cr0 == other.cr0
            && self.cr4 == other.cr4
            && self.efer == other.efer
    }
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum Error {
    Prepared(super::Error),
    State,
    Context,
    Root,
    Hardware,
    Timer(timer::Error),
    User(privilege::Error),
}

/// Implementations must truthfully observe this CPU and serialize all CR3,
/// paging-control, interrupt-state and root/boot-mapping ownership changes.
/// `write_root` must perform a real flushing MOV CR3 with PCIDE/PGE disabled.
/// Errors may occur after the write. No other CPU may use the candidate root.
/// Physical table access must be exclusive and `finish` must revoke only its
/// own temporary aliases, never mutate the audited persistent mappings.
pub trait Cpu {
    fn snapshot(&mut self) -> Result<Snapshot, Error>;
    fn write_root(&mut self, root: u64) -> Result<(), Error>;
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum State {
    Inactive,
    Uncertain,
    Active,
    Suspended,
    Restored,
}

/// Owns both the prepared resources and the serialized hardware adapter. There
/// is no path back to an inactive owner after possible CPU exposure. Dropping
/// this value keeps PMM retention live; it never frees potentially used pages.
///
/// ```compile_fail
/// use poolekernel::user_entry::prepared::cpu::{Cpu, CpuImage};
/// fn duplicate<H: Cpu>(owner: &CpuImage<H>) -> CpuImage<H> { owner.clone() }
/// ```
///
/// ```compile_fail
/// use poolekernel::user_entry::prepared::cpu::{Cpu, CpuImage};
/// fn bypass<H: Cpu>(owner: CpuImage<H>) { owner.abort(); }
/// ```
///
/// ```compile_fail
/// use poolekernel::user_entry::prepared::{PreparedImage, cpu::{Cpu, CpuImage}};
/// fn recover<H: Cpu>(owner: CpuImage<H>) -> PreparedImage { owner.prepared }
/// ```
pub struct CpuImage<H: Cpu> {
    prepared: PreparedImage,
    hardware: H,
    core: CoreRecord,
    context: Option<Snapshot>,
    state: State,
    timer_quiescent: bool,
    user_quiescent: bool,
}

impl<H: Cpu> CpuImage<H> {
    pub fn new(prepared: PreparedImage, hardware: H, core: CoreRecord) -> Self {
        Self {
            prepared,
            hardware,
            core,
            context: None,
            state: State::Inactive,
            timer_quiescent: true,
            user_quiescent: true,
        }
    }

    pub const fn state(&self) -> State {
        self.state
    }

    fn timer_context(&mut self) -> Result<timer::Mappings, Error> {
        if self.state != State::Active {
            return Err(Error::State);
        }
        let context = self.context.ok_or(Error::State)?;
        let current = self.hardware.snapshot()?;
        if !current.same_context(context)
            || current.cr3 != self.prepared.space.summary().root_physical
        {
            return Err(Error::Context);
        }
        self.prepared.timer.ok_or(Error::Timer(timer::Error::State))
    }

    /// Open a bounded trusted-driver interrupt window. Device exposure is marked
    /// before any driver call; every path must verify shutdown before retirement.
    pub fn exercise_timer<T: timer::Driver>(
        &mut self,
        driver: &mut T,
    ) -> Result<timer::Observation, Error> {
        let mappings = self.timer_context()?;
        if !self.timer_quiescent || !self.user_quiescent {
            return Err(Error::Timer(timer::Error::State));
        }
        self.timer_quiescent = false;
        let root = self.prepared.space.summary().root_physical;
        let observation = driver.execute(root, mappings);
        self.quiesce_timer(driver)?;
        let observation = observation.map_err(Error::Timer)?;
        if observation.observed_root != root
            || observation.deliveries == 0
            || observation.deliveries != observation.eois
        {
            return Err(Error::Timer(timer::Error::Hardware));
        }
        Ok(observation)
    }

    /// Failed shutdown can be retried only on the same active CPU/root. This is
    /// not permission to restore CR3 while a pending interrupt still needs it.
    pub fn quiesce_timer<T: timer::Driver>(&mut self, driver: &mut T) -> Result<(), Error> {
        let mappings = self.timer_context()?;
        self.timer_quiescent = false;
        driver
            .quiesce(self.prepared.space.summary().root_physical, mappings)
            .map_err(Error::Timer)?;
        self.timer_context()?;
        self.timer_quiescent = true;
        Ok(())
    }

    fn user_context(&mut self) -> Result<crate::user_entry::ImageAdmission, Error> {
        if self.state != State::Active {
            return Err(Error::State);
        }
        let context = self.context.ok_or(Error::State)?;
        let current = self.hardware.snapshot()?;
        let image = self.prepared.admission().ok_or(Error::State)?;
        if !current.same_context(context) || current.cr3 != image.root_physical {
            return Err(Error::Context);
        }
        Ok(image)
    }

    pub fn exercise_user<D: privilege::Driver>(
        &mut self,
        driver: &mut D,
    ) -> Result<privilege::Observation, Error> {
        let image = self.user_context()?;
        if !self.timer_quiescent || !self.user_quiescent {
            return Err(Error::State);
        }
        self.user_quiescent = false;
        let result = driver.execute(image);
        self.quiesce_user(driver)?;
        let observation = result.map_err(Error::User)?;
        if observation.root != image.root_physical
            || observation.traps != privilege::TRAP_COUNT
            || observation.cpl != 3
            || !observation.restored
        {
            return Err(Error::User(privilege::Error::Hardware));
        }
        Ok(observation)
    }

    pub fn quiesce_user<D: privilege::Driver>(&mut self, driver: &mut D) -> Result<(), Error> {
        let image = self.user_context()?;
        self.user_quiescent = false;
        driver.quiesce(image.root_physical).map_err(Error::User)?;
        self.user_context()?;
        self.user_quiescent = true;
        Ok(())
    }

    pub(crate) fn exercise_task<D: crate::user_entry::task::Driver>(
        &mut self,
        id: crate::scheduler_smp::TaskId,
        driver: &mut D,
    ) -> Result<crate::user_entry::task::Outcome, Error> {
        let image = self.user_context()?;
        if !self.timer_quiescent || !self.user_quiescent {
            return Err(Error::State);
        }
        self.user_quiescent = false;
        let result = driver.execute(image, id);
        self.quiesce_task(driver)?;
        let outcome = result.map_err(Error::User)?;
        outcome
            .validate(id, image.root_physical)
            .map_err(Error::User)?;
        Ok(outcome)
    }

    pub(crate) fn quiesce_task<D: crate::user_entry::task::Driver>(
        &mut self,
        driver: &mut D,
    ) -> Result<(), Error> {
        if self.user_quiescent {
            return Ok(());
        }
        let image = self.user_context()?;
        driver.quiesce(image.root_physical).map_err(Error::User)?;
        self.user_context()?;
        self.user_quiescent = true;
        Ok(())
    }

    pub(crate) fn exercise_slice<D: crate::user_entry::task::SliceDriver>(
        &mut self,
        id: crate::scheduler_smp::TaskId,
        driver: &mut D,
    ) -> Result<crate::user_entry::task::Slice, Error> {
        let image = self.user_context()?;
        if !self.timer_quiescent || !self.user_quiescent {
            return Err(Error::State);
        }
        self.user_quiescent = false;
        let result = driver.execute_slice(image, id);
        self.quiesce_task(driver)?;
        let slice = result.map_err(Error::User)?;
        slice
            .validate(id, image.root_physical)
            .map_err(Error::User)?;
        Ok(slice)
    }

    /// Flush back to the scheduler root without detaching or releasing any hold.
    /// Failure leaves an uncertain owner that cannot resume until safely retired.
    pub(crate) fn suspend(&mut self) -> Result<(), Error> {
        self.user_context()?;
        if !self.timer_quiescent || !self.user_quiescent {
            return Err(Error::State);
        }
        let context = self.context.ok_or(Error::State)?;
        self.state = State::Uncertain;
        self.hardware.write_root(context.cr3)?;
        let current = self.hardware.snapshot()?;
        if !current.same_context(context) || current.cr3 != context.cr3 {
            return Err(Error::Context);
        }
        self.state = State::Suspended;
        Ok(())
    }

    /// Re-audit ownership and all mappings immediately before the first write.
    /// The adapter must also prove the executing code, stack, data and exception
    /// paths survive both roots. This operation does not initialize user state.
    pub fn activate<M: TableMemory>(
        &mut self,
        manager: &PhysicalMemoryManager,
        memory: &mut M,
    ) -> Result<(), Error> {
        if !matches!(self.state, State::Inactive | State::Suspended) {
            return Err(Error::State);
        }
        let before = self.hardware.snapshot()?;
        if !before.supported() {
            return Err(Error::Context);
        }
        if self.state == State::Suspended && !before.same_context(self.context.ok_or(Error::State)?)
        {
            return Err(Error::Context);
        }
        let original = self.core.page_table_root_physical;
        let mask = super::physical_mask(self.prepared.bits)
            .map_err(|e| Error::Prepared(super::Error::Image(e)))?;
        if original == 0 || original & !mask != 0 || before.cr3 != original {
            return Err(Error::Root);
        }
        let image = self
            .prepared
            .revalidate(manager, memory, self.core)
            .map_err(Error::Prepared)?;
        let current = self.hardware.snapshot()?;
        if !current.same_context(before) || current.cr3 != original {
            return Err(Error::Context);
        }
        // Mark exposure BEFORE entering the adapter: even Err may follow MOV CR3.
        self.context = Some(before);
        self.state = State::Uncertain;
        self.hardware.write_root(image.root_physical)?;
        let after = self.hardware.snapshot()?;
        if !after.same_context(before) || after.cr3 != image.root_physical {
            return Err(Error::Context);
        }
        self.state = State::Active;
        Ok(())
    }

    /// Every potentially exposed path requires a fresh flushing restoration,
    /// including retries and an observed original CR3 after a failed write.
    /// Only then may inactive cleanup detach edges and release retention. The
    /// adapter is consumed, not returned with obsolete root-switch authority.
    #[allow(clippy::result_large_err)]
    pub fn retire<M: TableMemory>(
        mut self,
        manager: &mut PhysicalMemoryManager,
        memory: &mut M,
    ) -> Result<DetachedImage, (Error, Self)> {
        if !self.user_quiescent {
            return Err((Error::User(privilege::Error::State), self));
        }
        if !self.timer_quiescent {
            return Err((Error::Timer(timer::Error::State), self));
        }
        if self.state != State::Inactive {
            let restoration = (|| {
                manager
                    .validate_retentions(&self.prepared.retained)
                    .map_err(|_| Error::Prepared(super::Error::Ownership))?;
                let context = self.context.ok_or(Error::State)?;
                let current = self.hardware.snapshot()?;
                let candidate = self.prepared.space.summary().root_physical;
                if !current.same_context(context) {
                    return Err(Error::Context);
                }
                if current.cr3 != context.cr3 && current.cr3 != candidate {
                    return Err(Error::Root);
                }
                self.state = State::Uncertain;
                self.hardware.write_root(context.cr3)?;
                let after = self.hardware.snapshot()?;
                if !after.same_context(context) || after.cr3 != context.cr3 {
                    return Err(Error::Context);
                }
                self.state = State::Restored;
                Ok(())
            })();
            if let Err(error) = restoration {
                return Err((error, self));
            }
        }
        match self.prepared.abort(manager, memory) {
            Ok(parts) => Ok(parts),
            Err((error, prepared)) => {
                self.prepared = prepared;
                Err((Error::Prepared(error), self))
            }
        }
    }
}
