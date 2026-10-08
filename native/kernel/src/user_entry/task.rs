//! Owned single-BSP task termination. TaskId is scoped identity, not capability authority.
#![forbid(unsafe_code)]

use super::{
    ImageAdmission,
    prepared::{
        DetachedImage,
        cpu::{Cpu, CpuImage},
    },
    privilege, syscall,
};
use crate::{
    physical_memory::PhysicalMemoryManager, scheduler_smp::TaskId, virtual_memory::TableMemory,
};

pub const CONTRACT_ID: &str = "PKUSER8";

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct Fault {
    pub vector: u64,
    pub error: u64,
    pub instruction: u64,
    pub address: u64,
}
impl Fault {
    fn valid(self) -> bool {
        match self.vector {
            0 | 1 | 3 | 4 | 5 | 6 | 16 | 17 | 19 => self.error == 0 && self.address == 0,
            11 | 12 | 13 => self.error <= 0xffff && self.address == 0,
            // Reserved page-table bits or unsupported fault classes are kernel failures.
            14 => self.error & 4 != 0 && self.error & !0x17 == 0,
            _ => false,
        }
    }
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum Reason {
    Exit(u32),
    Fault(Fault),
    InvalidReturn {
        vector: u64,
        violation: syscall::ReturnViolation,
    },
    Cancelled,
    CallLimit,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct Outcome {
    pub id: TaskId,
    pub root: u64,
    pub reason: Reason,
    pub syscalls: u32,
}
impl Outcome {
    pub(crate) fn validate(self, id: TaskId, root: u64) -> Result<(), privilege::Error> {
        if self.id != id
            || self.root != root
            || self.syscalls > 64
            || match self.reason {
                Reason::Exit(_) => self.syscalls == 0,
                Reason::Fault(f) => !f.valid(),
                Reason::InvalidReturn { vector, .. } => !matches!(vector, 64 | syscall::VECTOR),
                Reason::Cancelled => false,
                Reason::CallLimit => self.syscalls != 64,
            }
        {
            return Err(privilege::Error::Hardware);
        }
        Ok(())
    }
}

/// Pure trap lifecycle. No transition out of a terminal outcome exists.
pub struct Run {
    image: ImageAdmission,
    id: TaskId,
    calls: u32,
    outcome: Option<Outcome>,
}
impl Run {
    pub fn new(image: ImageAdmission, id: TaskId) -> Result<Self, privilege::Error> {
        TaskId::new(id.slot, id.generation).map_err(|_| privilege::Error::State)?;
        if image.root_physical == 0 || image.root_physical & 4095 != 0 || image.root_generation == 0
        {
            return Err(privilege::Error::Context);
        }
        Ok(Self {
            image,
            id,
            calls: 0,
            outcome: None,
        })
    }
    pub fn call(&mut self, trap: &privilege::Trap) -> Result<bool, privilege::Error> {
        if !self.resume(trap, syscall::VECTOR)? {
            return Ok(false);
        }
        if self.calls == 64 {
            self.finish(Reason::CallLimit)?;
            return Ok(false);
        }
        self.calls += 1;
        Ok(true)
    }
    pub fn preempt(&mut self, trap: &privilege::Trap) -> Result<bool, privilege::Error> {
        self.resume(trap, 64)
    }
    fn resume(&mut self, trap: &privilege::Trap, vector: u64) -> Result<bool, privilege::Error> {
        if self.outcome.is_some() {
            return Err(privilege::Error::State);
        }
        if trap.vector != vector || trap.error != 0 {
            return Err(privilege::Error::Frame);
        }
        if let Some(violation) = syscall::return_violation(self.image, trap)? {
            self.finish(Reason::InvalidReturn { vector, violation })?;
            return Ok(false);
        }
        Ok(true)
    }
    pub fn exit(&mut self, code: u32) -> Result<Outcome, privilege::Error> {
        if self.calls == 0 {
            return Err(privilege::Error::State);
        }
        self.finish(Reason::Exit(code))
    }
    pub fn fault(&mut self, t: &privilege::Trap) -> Result<Outcome, privilege::Error> {
        syscall::entry_frame(self.image, t)?;
        let fault = Fault {
            vector: t.vector,
            error: t.error,
            instruction: t.rip,
            address: if t.vector == 14 { t.cr2 } else { 0 },
        };
        if !fault.valid() {
            return Err(privilege::Error::Fault);
        }
        // Faulting user RIP/RSP may be invalid. Never IRET back to this frame.
        self.finish(Reason::Fault(fault))
    }
    fn finish(&mut self, reason: Reason) -> Result<Outcome, privilege::Error> {
        if self.outcome.is_some() {
            return Err(privilege::Error::State);
        }
        let outcome = Outcome {
            id: self.id,
            root: self.image.root_physical,
            reason,
            syscalls: self.calls,
        };
        self.outcome = Some(outcome);
        Ok(outcome)
    }
    pub const fn outcome(&self) -> Option<Outcome> {
        self.outcome
    }
    pub const fn calls(&self) -> u32 {
        self.calls
    }
    pub fn matches(&self, image: ImageAdmission, id: TaskId) -> bool {
        self.image == image && self.id == id && self.outcome.is_none()
    }
}

/// Trusted architectural adapter. Errors may follow CPU effects. Quiescence
/// revokes all entry/timer/descriptor references before returning at CPL0/IF0.
pub trait Driver {
    fn execute(&mut self, image: ImageAdmission, id: TaskId) -> Result<Outcome, privilege::Error>;
    fn quiesce(&mut self, root: u64) -> Result<(), privilege::Error>;
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum Event {
    Preempted {
        ticks: u64,
        syscalls: u32,
        progress: u64,
    },
    Terminated(Outcome),
}
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct Slice {
    pub id: TaskId,
    pub root: u64,
    pub event: Event,
}
impl Slice {
    pub(crate) fn validate(self, id: TaskId, root: u64) -> Result<(), privilege::Error> {
        if self.id != id || self.root != root {
            return Err(privilege::Error::Hardware);
        }
        match self.event {
            Event::Preempted {
                ticks, syscalls, ..
            } if ticks > 0 && syscalls <= 64 => Ok(()),
            Event::Terminated(o) => o.validate(id, root),
            _ => Err(privilege::Error::Hardware),
        }
    }
}
/// A quantum returns only after saving its private user state. The same owner
/// must quiesce devices and entry references before the CPU can be suspended.
pub trait SliceDriver: Driver {
    fn execute_slice(
        &mut self,
        image: ImageAdmission,
        id: TaskId,
    ) -> Result<Slice, privilege::Error>;
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum State {
    Prepared,
    Active,
    Suspended,
    Quarantined,
    Terminated,
}
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum Error {
    Identity,
    Exhausted,
    Occupied,
    Missing,
    State,
    Cpu(super::prepared::cpu::Error),
}

struct Owned<H: Cpu, D: Driver> {
    id: TaskId,
    cpu: Option<CpuImage<H>>,
    driver: D,
    state: State,
    outcome: Option<Outcome>,
    last_slice: Option<Slice>,
}

/// A persistent slot owns the exact CPU image and its cleanup adapter. It
/// increments generations only on successful insertion and never wraps. Slot
/// identifiers are namespace-local diagnostics, not transferable authority.
/// Reaping detaches resources; the returned owner must still scrub/release them.
/// Dropping the slot keeps PMM retention rather than inventing quiescence.
///
/// ```compile_fail
/// use poolekernel::user_entry::{task::{Slot, Driver}, prepared::cpu::Cpu};
/// fn duplicate<H: Cpu,D: Driver>(s: &Slot<H,D>) -> Slot<H,D> { s.clone() }
/// ```
/// ```compile_fail
/// use poolekernel::user_entry::{task::{Slot, Driver}, prepared::cpu::Cpu};
/// fn bypass<H: Cpu,D: Driver>(s: &mut Slot<H,D>) { s.owned.take(); }
/// ```
pub struct Slot<H: Cpu, D: Driver> {
    slot: u8,
    generation: u32,
    owned: Option<Owned<H, D>>,
}
impl<H: Cpu, D: Driver> Slot<H, D> {
    pub fn new(slot: u8) -> Result<Self, Error> {
        TaskId::new(slot, 1).map_err(|_| Error::Identity)?;
        Ok(Self {
            slot,
            generation: 0,
            owned: None,
        })
    }
    fn next_id(&self) -> Result<TaskId, Error> {
        let generation = self.generation.checked_add(1).ok_or(Error::Exhausted)?;
        TaskId::new(self.slot, generation).map_err(|_| Error::Identity)
    }
    #[allow(clippy::result_large_err)]
    pub fn insert(
        &mut self,
        cpu: CpuImage<H>,
        driver: D,
    ) -> Result<TaskId, (Error, CpuImage<H>, D)> {
        let admit = if self.owned.is_some() {
            Err(Error::Occupied)
        } else if cpu.state() != super::prepared::cpu::State::Inactive {
            Err(Error::State)
        } else {
            self.next_id()
        };
        let id = match admit {
            Ok(id) => id,
            Err(e) => return Err((e, cpu, driver)),
        };
        self.generation = id.generation;
        self.owned = Some(Owned {
            id,
            cpu: Some(cpu),
            driver,
            state: State::Prepared,
            outcome: None,
            last_slice: None,
        });
        Ok(id)
    }
    fn owned(&self, id: TaskId) -> Result<&Owned<H, D>, Error> {
        let task = self.owned.as_ref().ok_or(Error::Missing)?;
        if task.id != id {
            return Err(Error::Identity);
        }
        Ok(task)
    }
    fn owned_mut(&mut self, id: TaskId) -> Result<&mut Owned<H, D>, Error> {
        self.owned(id)?;
        self.owned.as_mut().ok_or(Error::Missing)
    }
    pub fn state(&self, id: TaskId) -> Result<State, Error> {
        Ok(self.owned(id)?.state)
    }
    pub fn outcome(&self, id: TaskId) -> Result<Outcome, Error> {
        let task = self.owned(id)?;
        if task.state != State::Terminated {
            return Err(Error::State);
        }
        task.outcome.ok_or(Error::State)
    }
    pub fn activate<M: TableMemory>(
        &mut self,
        id: TaskId,
        manager: &PhysicalMemoryManager,
        memory: &mut M,
    ) -> Result<(), Error> {
        let task = self.owned_mut(id)?;
        if !matches!(task.state, State::Prepared | State::Suspended) {
            return Err(Error::State);
        }
        task.state = State::Quarantined;
        task.cpu
            .as_mut()
            .ok_or(Error::State)?
            .activate(manager, memory)
            .map_err(Error::Cpu)?;
        task.state = State::Active;
        Ok(())
    }
    pub fn run(&mut self, id: TaskId) -> Result<Outcome, Error> {
        let task = self.owned_mut(id)?;
        if task.state != State::Active {
            return Err(Error::State);
        }
        task.state = State::Quarantined;
        let outcome = task
            .cpu
            .as_mut()
            .ok_or(Error::State)?
            .exercise_task(id, &mut task.driver)
            .map_err(Error::Cpu)?;
        task.outcome = Some(outcome);
        task.state = State::Terminated;
        Ok(outcome)
    }
    pub fn reap<M: TableMemory>(
        &mut self,
        id: TaskId,
        manager: &mut PhysicalMemoryManager,
        memory: &mut M,
    ) -> Result<(DetachedImage, Outcome), Error> {
        let outcome = self.outcome(id)?;
        let parts = self.detach(id, manager, memory)?;
        Ok((parts, outcome))
    }
    /// Cancel before entry, or recover a failed architectural operation. This
    /// never fabricates an application exit status or restarts the task.
    pub fn abandon<M: TableMemory>(
        &mut self,
        id: TaskId,
        manager: &mut PhysicalMemoryManager,
        memory: &mut M,
    ) -> Result<DetachedImage, Error> {
        let task = self.owned_mut(id)?;
        if !matches!(task.state, State::Prepared | State::Quarantined) {
            return Err(Error::State);
        }
        task.state = State::Quarantined;
        task.cpu
            .as_mut()
            .ok_or(Error::State)?
            .quiesce_task(&mut task.driver)
            .map_err(Error::Cpu)?;
        self.detach(id, manager, memory)
    }
    fn detach<M: TableMemory>(
        &mut self,
        id: TaskId,
        manager: &mut PhysicalMemoryManager,
        memory: &mut M,
    ) -> Result<DetachedImage, Error> {
        let task = self.owned_mut(id)?;
        let cpu = task.cpu.take().ok_or(Error::State)?;
        match cpu.retire(manager, memory) {
            Ok(parts) => {
                self.owned = None;
                Ok(parts)
            }
            Err((e, cpu)) => {
                task.cpu = Some(cpu);
                Err(Error::Cpu(e))
            }
        }
    }
}

impl<H: Cpu, D: SliceDriver> Slot<H, D> {
    pub fn run_slice(&mut self, id: TaskId) -> Result<Slice, Error> {
        let task = self.owned_mut(id)?;
        if task.state != State::Active {
            return Err(Error::State);
        }
        task.state = State::Quarantined;
        let cpu = task.cpu.as_mut().ok_or(Error::State)?;
        let slice = cpu
            .exercise_slice(id, &mut task.driver)
            .map_err(Error::Cpu)?;
        match slice.event {
            Event::Preempted { .. } => {
                cpu.suspend().map_err(Error::Cpu)?;
                task.state = State::Suspended;
            }
            Event::Terminated(outcome) => {
                task.outcome = Some(outcome);
                task.state = State::Terminated;
            }
        }
        task.last_slice = Some(slice);
        Ok(slice)
    }

    /// Kernel-side cancellation of an already quiescent suspended task. TaskId
    /// is identity only; a future user request still requires capability checks.
    pub fn cancel_suspended(&mut self, id: TaskId) -> Result<Outcome, Error> {
        let task = self.owned_mut(id)?;
        if task.state != State::Suspended {
            return Err(Error::State);
        }
        let slice = task.last_slice.ok_or(Error::State)?;
        let Event::Preempted { syscalls, .. } = slice.event else {
            return Err(Error::State);
        };
        let outcome = Outcome {
            id,
            root: slice.root,
            reason: Reason::Cancelled,
            syscalls,
        };
        task.outcome = Some(outcome);
        task.state = State::Terminated;
        Ok(outcome)
    }
}

#[cfg(test)]
mod tests {
    use super::super::{INITIAL_RFLAGS, InitialReturnFrame};
    use super::*;
    fn image() -> ImageAdmission {
        ImageAdmission {
            root_physical: 0x100000,
            root_generation: 1,
            code_physical: 0x200000,
            stack_physical: 0x210000,
            initial_frame: InitialReturnFrame {
                rip: 0x40000010,
                cs: 0x33,
                rsp: 0x40004000,
                ss: 0x2b,
                rflags: INITIAL_RFLAGS,
            },
        }
    }
    fn trap() -> privilege::Trap {
        let f = image().initial_frame;
        privilege::Trap {
            root: image().root_physical,
            vector: syscall::VECTOR,
            error: 0,
            rip: f.rip,
            cs: f.cs,
            flags: f.rflags,
            rsp: f.rsp,
            ss: f.ss,
            cr2: 0,
            handler_stack: super::super::prepared::STACK_TOP - privilege::FRAME_BYTES,
            depth: 1,
            registers: [0; 15],
        }
    }
    fn run() -> Run {
        Run::new(image(), TaskId::new(0, 1).unwrap()).unwrap()
    }
    #[test]
    fn malformed_syscall_state_terminates_only_the_owner() {
        for case in 0..6 {
            let mut t = trap();
            match case {
                0 => t.rsp = 0xffff_ffff_8000_0000,
                1 => t.rsp = 0x8000_0000_0000,
                2 => t.rip = (t.rip & !4095) + 4096,
                3 => t.flags |= 1 << 14,
                4 => t.flags |= 1 << 18,
                _ => t.flags |= 1 << 8,
            }
            let mut r = run();
            assert_eq!(r.call(&t), Ok(false), "case {case}");
            assert!(r.outcome().is_some());
            assert!(r.call(&trap()).is_err());
            assert_eq!(r.calls(), 0);
            let expected = match case {
                0 | 1 => syscall::ReturnViolation::Stack,
                2 => syscall::ReturnViolation::Instruction,
                _ => syscall::ReturnViolation::Flags,
            };
            let outcome = r.outcome().unwrap();
            assert_eq!(
                outcome.reason,
                Reason::InvalidReturn {
                    vector: syscall::VECTOR,
                    violation: expected
                }
            );
            outcome.validate(outcome.id, outcome.root).unwrap();
            let mut peer = run();
            assert_eq!(peer.call(&trap()), Ok(true));
            assert_eq!(peer.exit(84).unwrap().reason, Reason::Exit(84));
        }
    }
    #[test]
    fn malformed_preempt_state_never_becomes_a_resumable_context() {
        for case in 0..5 {
            let mut t = trap();
            t.vector = 64;
            let mut r = run();
            assert_eq!(r.preempt(&t), Ok(true));
            match case {
                0 => t.rsp = u64::MAX,
                1 => t.rsp = image().initial_frame.rsp - 4097,
                2 => t.rip = 0x8000_0000_0000,
                3 => t.flags |= 1 << 18,
                _ => t.flags |= 1 << 14,
            }
            assert_eq!(r.preempt(&t), Ok(false));
            let o = r.outcome().unwrap();
            o.validate(o.id, o.root).unwrap();
            assert!(matches!(o.reason, Reason::InvalidReturn { vector: 64, .. }));
            assert!(r.preempt(&t).is_err());
            assert!(r.exit(0).is_err());
            assert_eq!(r.calls(), 0);
        }
    }
    #[test]
    fn bad_user_state_cannot_mask_untrusted_entry_envelope_or_event() {
        for vector in [64, syscall::VECTOR] {
            for case in 0..7 {
                let mut t = trap();
                t.vector = vector;
                t.rsp = u64::MAX;
                t.flags |= 1 << 18;
                match case {
                    0 => t.root += 4096,
                    1 => t.depth = 2,
                    2 => t.cs = 8,
                    3 => t.ss = 16,
                    4 => t.handler_stack -= 8,
                    5 => t.error = 1,
                    _ => t.vector = 8,
                }
                let mut r = run();
                assert!(
                    if vector == 64 {
                        r.preempt(&t)
                    } else {
                        r.call(&t)
                    }
                    .is_err()
                );
                assert_eq!(r.outcome(), None);
                assert_eq!(r.calls(), 0);
            }
        }
    }
    #[test]
    fn ordinary_exception_table_rejects_system_events_and_forged_errors() {
        for vector in 0..32 {
            let mut t = trap();
            t.vector = vector;
            if vector == 14 {
                t.error = 4;
            }
            let admitted = matches!(
                vector,
                0 | 1 | 3 | 4 | 5 | 6 | 11 | 12 | 13 | 14 | 16 | 17 | 19
            );
            assert_eq!(run().fault(&t).is_ok(), admitted, "vector {vector}");
            t.error = 0x10000;
            assert!(run().fault(&t).is_err());
        }
        let mut t = trap();
        t.rsp = u64::MAX;
        let mut r = run();
        r.call(&t).unwrap();
        let mut o = r.outcome().unwrap();
        o.reason = Reason::InvalidReturn {
            vector: 8,
            violation: syscall::ReturnViolation::Stack,
        };
        assert!(o.validate(o.id, o.root).is_err());
    }
    #[test]
    fn terminal_outcome_cannot_resume_or_change_and_rejected_calls_do_not_count() {
        let mut run = run();
        assert!(run.exit(0).is_err());
        let mut t = trap();
        t.root += 4096;
        assert!(run.call(&t).is_err());
        run.call(&trap()).unwrap();
        let o = run.exit(42).unwrap();
        assert_eq!((o.reason, o.syscalls), (Reason::Exit(42), 1));
        assert!(run.call(&trap()).is_err());
        assert!(run.exit(0).is_err());
        t = trap();
        t.vector = 6;
        assert!(run.fault(&t).is_err());
        assert_eq!(run.outcome(), Some(o));
    }
    #[test]
    fn user_faults_terminate_but_kernel_reserved_or_foreign_frames_reject() {
        for (vector, error) in [
            (6, 0),
            (13, 0),
            (13, 0xffff),
            (14, 4),
            (14, 5),
            (14, 6),
            (14, 7),
            (14, 20),
            (14, 21),
        ] {
            let mut t = trap();
            t.vector = vector;
            t.error = error;
            // Faulting programs may have unusable return addresses and stacks.
            t.rip = 0x800000000000;
            t.rsp = u64::MAX;
            t.cr2 = u64::MAX;
            let o = run().fault(&t).unwrap();
            assert!(matches!(o.reason, Reason::Fault(_)));
            o.validate(o.id, o.root).unwrap();
        }
        for case in 0..10 {
            let mut t = trap();
            t.vector = 14;
            t.error = 5;
            match case {
                0 => t.root += 4096,
                1 => t.depth = 2,
                2 => t.cs = 8,
                3 => t.ss = 16,
                4 => t.handler_stack -= 8,
                5 => t.error = 1,
                6 => t.error |= 8,
                7 => t.error |= 32,
                8 => t.vector = 8,
                _ => {
                    t.vector = 6;
                    t.error = 1;
                }
            }
            let mut r = run();
            assert!(r.fault(&t).is_err());
            assert_eq!(r.outcome(), None);
        }
    }
    struct Never;
    impl Cpu for Never {
        fn snapshot(
            &mut self,
        ) -> Result<super::super::prepared::cpu::Snapshot, super::super::prepared::cpu::Error>
        {
            unreachable!()
        }
        fn write_root(&mut self, _: u64) -> Result<(), super::super::prepared::cpu::Error> {
            unreachable!()
        }
    }
    impl Driver for Never {
        fn execute(&mut self, _: ImageAdmission, _: TaskId) -> Result<Outcome, privilege::Error> {
            unreachable!()
        }
        fn quiesce(&mut self, _: u64) -> Result<(), privilege::Error> {
            unreachable!()
        }
    }
    #[test]
    fn generation_and_call_counters_never_wrap_or_acquire_authority() {
        assert!(Slot::<Never, Never>::new(8).is_err());
        let mut slot = Slot::<Never, Never>::new(0).unwrap();
        assert_eq!(slot.next_id().unwrap().generation, 1);
        slot.generation = u32::MAX - 1;
        assert_eq!(slot.next_id().unwrap().generation, u32::MAX);
        slot.generation = u32::MAX;
        assert_eq!(slot.next_id(), Err(Error::Exhausted));
        let mut r = run();
        for _ in 0..64 {
            r.call(&trap()).unwrap();
        }
        assert_eq!(r.call(&trap()), Ok(false));
        assert_eq!(r.outcome().unwrap().reason, Reason::CallLimit);
        assert_eq!(r.outcome().unwrap().syscalls, 64);
        assert!(r.exit(0).is_err());
    }
}
