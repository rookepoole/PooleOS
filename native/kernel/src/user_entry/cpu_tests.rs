use super::*;
use crate::user_entry::prepared::cpu::{Cpu, CpuImage, Error as CpuError, Snapshot, State};
use std::{cell::RefCell, rc::Rc};

struct Machine {
    snapshot: Snapshot,
    writes: std::vec::Vec<u64>,
    reads: usize,
    fail_read: Option<usize>,
    write_error: bool,
    suppress_write: bool,
    change_cpu_after_write: bool,
    change_cpu_on_read: Option<usize>,
}

struct Hardware(Rc<RefCell<Machine>>);

impl Cpu for Hardware {
    fn snapshot(&mut self) -> Result<Snapshot, CpuError> {
        let mut machine = self.0.borrow_mut();
        let index = machine.reads;
        machine.reads += 1;
        if machine.fail_read == Some(index) {
            return Err(CpuError::Hardware);
        }
        if machine.change_cpu_on_read == Some(index) {
            machine.snapshot.cpu_id += 1;
        }
        Ok(machine.snapshot)
    }

    fn write_root(&mut self, root: u64) -> Result<(), CpuError> {
        let mut machine = self.0.borrow_mut();
        machine.writes.push(root);
        if !machine.suppress_write {
            machine.snapshot.cr3 = root;
        }
        if machine.change_cpu_after_write {
            machine.snapshot.cpu_id += 1;
        }
        if machine.write_error {
            Err(CpuError::Hardware)
        } else {
            Ok(())
        }
    }
}

struct Setup {
    manager: PhysicalMemoryManager,
    memory: Memory,
    owner: CpuImage<Hardware>,
    machine: Rc<RefCell<Machine>>,
    handles: std::vec::Vec<AllocationHandle>,
    original: u64,
    candidate: u64,
}

fn setup() -> Setup {
    setup_with_timer(false)
}

fn setup_with_timer(timer: bool) -> Setup {
    let fixture = Fixture::new();
    let handles = fixture.handles();
    let core = fixture.core;
    let (manager, memory, prepared) = if timer {
        ready_timer(fixture)
    } else {
        ready(fixture)
    };
    let candidate = prepared.admission().unwrap().root_physical;
    let machine = Rc::new(RefCell::new(Machine {
        snapshot: Snapshot {
            cpu_id: 7,
            active_cpus: 1,
            cr0: 1 | (1 << 16) | (1 << 31),
            cr3: core.page_table_root_physical,
            cr4: 1 << 5,
            efer: (1 << 8) | (1 << 10) | (1 << 11),
            rflags: 2,
        },
        writes: std::vec::Vec::new(),
        reads: 0,
        fail_read: None,
        write_error: false,
        suppress_write: false,
        change_cpu_after_write: false,
        change_cpu_on_read: None,
    }));
    let owner = CpuImage::new(prepared, Hardware(Rc::clone(&machine)), core);
    Setup {
        manager,
        memory,
        owner,
        machine,
        handles,
        original: core.page_table_root_physical,
        candidate,
    }
}

#[test]
fn cpu_activation_and_retirement_keep_exact_ownership_until_flush_and_detach() {
    let mut s = setup();
    s.owner.activate(&s.manager, &mut s.memory).unwrap();
    assert_eq!(s.owner.state(), State::Active);
    retained(&mut s.manager, &s.handles);
    // Hardware A/D writes after activation must not defeat safe inactive cleanup.
    s.memory.pages.get_mut(&s.candidate).unwrap()[0] |= A;
    let stack_index = ((USER_WINDOW_START + 3 * PAGE_BYTES) >> 12 & 511) as usize;
    s.memory
        .pages
        .get_mut(&(s.candidate + 3 * PAGE_BYTES))
        .unwrap()[stack_index] |= A | D;
    let parts = s
        .owner
        .retire(&mut s.manager, &mut s.memory)
        .unwrap_or_else(|(e, _)| panic!("retire {e:?}"));
    assert_eq!(s.machine.borrow().writes, [s.candidate, s.original]);
    assert_eq!(s.memory.pages[&s.candidate][STACK_SLOT], 0);
    assert_eq!(s.memory.pages[&s.candidate][KERNEL_SLOT], 0);
    for h in s.handles {
        s.manager.validate_allocation(h).unwrap();
    }
    s.manager.free(parts.stack).unwrap();
    s.manager.free(parts.stack_tables).unwrap();
}

#[test]
fn unsupported_cpu_contexts_and_nonexact_roots_never_write_cr3() {
    for case in 0..12 {
        let mut s = setup();
        {
            let mut m = s.machine.borrow_mut();
            match case {
                0 => m.snapshot.active_cpus = 2,
                1 => m.snapshot.rflags |= 1 << 9,
                2 => m.snapshot.cr0 &= !1,
                3 => m.snapshot.cr0 &= !(1 << 16),
                4 => m.snapshot.cr0 &= !(1 << 31),
                5 => m.snapshot.cr4 &= !(1 << 5),
                6 => m.snapshot.cr4 |= 1 << 7,
                7 => m.snapshot.cr4 |= 1 << 12,
                8 => m.snapshot.cr4 |= 1 << 17,
                9 => m.snapshot.efer &= !(1 << 11),
                10 => m.snapshot.cr3 |= 8,
                _ => m.snapshot.cr3 = s.candidate,
            }
        }
        assert!(
            s.owner.activate(&s.manager, &mut s.memory).is_err(),
            "{case}"
        );
        assert_eq!(s.owner.state(), State::Inactive);
        assert!(s.machine.borrow().writes.is_empty());
        retained(&mut s.manager, &s.handles);
    }
}

#[test]
fn fresh_mapping_and_manager_replay_precede_any_cpu_exposure() {
    for case in 0..4 {
        let mut s = setup();
        match case {
            0 => s.memory.pages.get_mut(&s.candidate).unwrap()[77] = 0x700003,
            1 => {
                s.memory
                    .pages
                    .get_mut(&(s.original + 3 * PAGE_BYTES))
                    .unwrap()[0] |= W
            }
            2 => s.memory.fail_finish = true,
            _ => s.memory.fail_read = Some(s.memory.reads),
        }
        assert!(s.owner.activate(&s.manager, &mut s.memory).is_err());
        assert!(s.machine.borrow().writes.is_empty());
        retained(&mut s.manager, &s.handles);
    }
    let mut s = setup();
    let foreign = Fixture::new();
    assert_eq!(
        s.owner.activate(&foreign.manager, &mut s.memory),
        Err(CpuError::Prepared(Error::Ownership))
    );
    assert!(s.machine.borrow().writes.is_empty());
}

#[test]
fn context_is_sampled_again_after_mapping_audit() {
    let mut s = setup();
    s.machine.borrow_mut().change_cpu_on_read = Some(1);
    assert_eq!(
        s.owner.activate(&s.manager, &mut s.memory),
        Err(CpuError::Context)
    );
    assert!(s.machine.borrow().writes.is_empty());
    assert_eq!(s.owner.state(), State::Inactive);
}

#[test]
fn failed_cr3_writes_with_or_without_effect_stay_quarantined_until_new_flush() {
    for effect in [false, true] {
        let mut s = setup();
        s.machine.borrow_mut().write_error = true;
        s.machine.borrow_mut().suppress_write = !effect;
        assert_eq!(
            s.owner.activate(&s.manager, &mut s.memory),
            Err(CpuError::Hardware)
        );
        assert_eq!(s.owner.state(), State::Uncertain);
        retained(&mut s.manager, &s.handles);
        s.machine.borrow_mut().write_error = false;
        s.machine.borrow_mut().suppress_write = false;
        s.owner
            .retire(&mut s.manager, &mut s.memory)
            .unwrap_or_else(|(e, _)| panic!("recovery {e:?}"));
        assert_eq!(s.machine.borrow().writes, [s.candidate, s.original]);
    }
}

#[test]
fn failed_readback_and_silent_noop_do_not_create_active_or_releasable_owners() {
    for case in 0..3 {
        let mut s = setup();
        match case {
            0 => s.machine.borrow_mut().suppress_write = true,
            1 => s.machine.borrow_mut().fail_read = Some(2),
            _ => s.machine.borrow_mut().change_cpu_after_write = true,
        }
        assert!(s.owner.activate(&s.manager, &mut s.memory).is_err());
        assert_eq!(s.owner.state(), State::Uncertain);
        drop(s.owner);
        retained(&mut s.manager, &s.handles);
    }
}

#[test]
fn second_activation_is_rejected_before_touching_hardware() {
    let mut s = setup();
    s.owner.activate(&s.manager, &mut s.memory).unwrap();
    let reads = s.machine.borrow().reads;
    assert_eq!(
        s.owner.activate(&s.manager, &mut s.memory),
        Err(CpuError::State)
    );
    assert_eq!(s.machine.borrow().reads, reads);
    assert_eq!(s.machine.borrow().writes, [s.candidate]);
}

#[test]
fn failed_restoration_and_postrestore_readback_never_detach_pages() {
    for case in 0..4 {
        let mut s = setup();
        s.owner.activate(&s.manager, &mut s.memory).unwrap();
        let writes = s.memory.writes;
        match case {
            0 => s.machine.borrow_mut().write_error = true,
            1 => s.machine.borrow_mut().suppress_write = true,
            2 => {
                let n = s.machine.borrow().reads;
                s.machine.borrow_mut().fail_read = Some(n + 1);
            }
            _ => s.machine.borrow_mut().change_cpu_after_write = true,
        }
        let (_, owner) = s.owner.retire(&mut s.manager, &mut s.memory).err().unwrap();
        assert_eq!(owner.state(), State::Uncertain);
        assert_eq!(s.memory.writes, writes);
        retained(&mut s.manager, &s.handles);
    }
}

#[test]
fn restoration_retry_flushes_even_when_original_root_is_already_observed() {
    let mut s = setup();
    s.owner.activate(&s.manager, &mut s.memory).unwrap();
    s.machine.borrow_mut().write_error = true;
    let (_, owner) = s.owner.retire(&mut s.manager, &mut s.memory).err().unwrap();
    assert_eq!(s.machine.borrow().snapshot.cr3, s.original);
    retained(&mut s.manager, &s.handles);
    s.machine.borrow_mut().write_error = false;
    owner
        .retire(&mut s.manager, &mut s.memory)
        .unwrap_or_else(|(e, _)| panic!("retry {e:?}"));
    assert_eq!(
        s.machine.borrow().writes,
        [s.candidate, s.original, s.original]
    );
}

#[test]
fn foreign_manager_cpu_migration_mode_changes_and_unknown_root_prevent_cleanup() {
    for case in 0..5 {
        let mut s = setup();
        s.owner.activate(&s.manager, &mut s.memory).unwrap();
        let writes = s.memory.writes;
        let mut foreign = Fixture::new();
        match case {
            0 => s.machine.borrow_mut().snapshot.cpu_id += 1,
            1 => s.machine.borrow_mut().snapshot.active_cpus = 2,
            2 => s.machine.borrow_mut().snapshot.cr4 |= 1 << 7,
            3 => s.machine.borrow_mut().snapshot.cr3 = 0x99000,
            _ => (),
        }
        let manager = if case == 4 {
            &mut foreign.manager
        } else {
            &mut s.manager
        };
        let (_, owner) = s.owner.retire(manager, &mut s.memory).err().unwrap();
        assert_eq!(owner.state(), State::Active);
        assert_eq!(s.machine.borrow().writes, [s.candidate]);
        assert_eq!(s.memory.writes, writes);
        retained(&mut s.manager, &s.handles);
    }
}

#[test]
fn postrestore_detachment_failure_keeps_tokens_and_retries_with_fresh_flush() {
    let mut s = setup();
    s.owner.activate(&s.manager, &mut s.memory).unwrap();
    s.memory.fail_write = Some(s.memory.writes);
    let (_, owner) = s.owner.retire(&mut s.manager, &mut s.memory).err().unwrap();
    assert_eq!(owner.state(), State::Restored);
    retained(&mut s.manager, &s.handles);
    s.memory.fail_write = None;
    owner
        .retire(&mut s.manager, &mut s.memory)
        .unwrap_or_else(|(e, _)| panic!("cleanup retry {e:?}"));
    assert_eq!(
        s.machine.borrow().writes,
        [s.candidate, s.original, s.original]
    );
}

#[test]
fn never_exposed_owner_can_detach_without_inventing_a_cpu_flush() {
    let mut s = setup();
    s.owner
        .retire(&mut s.manager, &mut s.memory)
        .unwrap_or_else(|(e, _)| panic!("cancel {e:?}"));
    assert!(s.machine.borrow().writes.is_empty());
    assert_eq!(s.machine.borrow().reads, 0);
}

struct TimerDriver {
    machine: Rc<RefCell<Machine>>,
    execute_error: bool,
    stop_error: bool,
    change_context: bool,
    malformed: u8,
    calls: std::vec::Vec<&'static str>,
}

impl TimerDriver {
    fn new(s: &Setup) -> Self {
        Self {
            machine: Rc::clone(&s.machine),
            execute_error: false,
            stop_error: false,
            change_context: false,
            malformed: 0,
            calls: std::vec::Vec::new(),
        }
    }
}

impl crate::user_entry::timer::Driver for TimerDriver {
    fn execute(
        &mut self,
        root: u64,
        mappings: timer::Mappings,
    ) -> Result<timer::Observation, timer::Error> {
        assert_eq!(mappings, timer::Mappings::fixture());
        assert_eq!(self.machine.borrow().snapshot.cr3, root);
        self.calls.push("execute");
        if self.execute_error {
            return Err(timer::Error::Hardware);
        }
        Ok(timer::Observation {
            observed_root: root + u64::from(self.malformed == 1),
            deliveries: if self.malformed == 2 { 0 } else { 3 },
            eois: if self.malformed == 3 { 2 } else { 3 },
        })
    }
    fn quiesce(&mut self, root: u64, _: timer::Mappings) -> Result<(), timer::Error> {
        assert_eq!(self.machine.borrow().snapshot.cr3, root);
        self.calls.push("stop");
        if self.change_context {
            self.machine.borrow_mut().snapshot.cpu_id += 1;
        }
        if self.stop_error {
            Err(timer::Error::Hardware)
        } else {
            Ok(())
        }
    }
}

#[test]
fn timer_success_shutdown_precedes_root_restore_and_leaf_cleanup() {
    let mut s = setup_with_timer(true);
    let mut driver = TimerDriver::new(&s);
    s.owner.activate(&s.manager, &mut s.memory).unwrap();
    assert_eq!(s.owner.exercise_timer(&mut driver).unwrap().deliveries, 3);
    assert_eq!(driver.calls, ["execute", "stop"]);
    retained(&mut s.manager, &s.handles);
    let parts = s
        .owner
        .retire(&mut s.manager, &mut s.memory)
        .unwrap_or_else(|(e, _)| panic!("{e:?}"));
    for page in parts.stack_tables.start_page..parts.stack_tables.start_page + 3 {
        assert_eq!(s.memory.pages[&(page * PAGE_BYTES)], [0; 512]);
    }
    assert_eq!(s.machine.borrow().writes, [s.candidate, s.original]);
}

#[test]
fn failed_timer_execution_still_runs_verified_shutdown() {
    let mut s = setup_with_timer(true);
    let mut driver = TimerDriver::new(&s);
    driver.execute_error = true;
    s.owner.activate(&s.manager, &mut s.memory).unwrap();
    assert_eq!(
        s.owner.exercise_timer(&mut driver),
        Err(CpuError::Timer(timer::Error::Hardware))
    );
    assert_eq!(driver.calls, ["execute", "stop"]);
    assert!(s.owner.retire(&mut s.manager, &mut s.memory).is_ok());
}

#[test]
fn failed_shutdown_prevents_cr3_restore_and_all_memory_release_until_retry() {
    for execute_error in [false, true] {
        let mut s = setup_with_timer(true);
        let mut driver = TimerDriver::new(&s);
        driver.execute_error = execute_error;
        driver.stop_error = true;
        s.owner.activate(&s.manager, &mut s.memory).unwrap();
        assert!(s.owner.exercise_timer(&mut driver).is_err());
        let writes = s.memory.writes;
        let (error, mut owner) = s.owner.retire(&mut s.manager, &mut s.memory).err().unwrap();
        assert_eq!(error, CpuError::Timer(timer::Error::State));
        assert_eq!(s.machine.borrow().writes, [s.candidate]);
        assert_eq!(s.memory.writes, writes);
        retained(&mut s.manager, &s.handles);
        assert!(owner.exercise_timer(&mut driver).is_err());
        assert_eq!(driver.calls, ["execute", "stop"]);
        driver.stop_error = false;
        owner.quiesce_timer(&mut driver).unwrap();
        assert!(owner.retire(&mut s.manager, &mut s.memory).is_ok());
    }
}

#[test]
fn context_drift_during_shutdown_never_admits_retirement() {
    let mut s = setup_with_timer(true);
    let mut driver = TimerDriver::new(&s);
    driver.change_context = true;
    s.owner.activate(&s.manager, &mut s.memory).unwrap();
    assert_eq!(s.owner.exercise_timer(&mut driver), Err(CpuError::Context));
    assert!(s.owner.retire(&mut s.manager, &mut s.memory).is_err());
    assert_eq!(s.machine.borrow().writes, [s.candidate]);
    retained(&mut s.manager, &s.handles);
}

#[test]
fn malformed_timer_observations_fail_even_after_safe_shutdown() {
    for malformed in 1..=3 {
        let mut s = setup_with_timer(true);
        let mut driver = TimerDriver::new(&s);
        driver.malformed = malformed;
        s.owner.activate(&s.manager, &mut s.memory).unwrap();
        assert_eq!(
            s.owner.exercise_timer(&mut driver),
            Err(CpuError::Timer(timer::Error::Hardware))
        );
        assert_eq!(driver.calls, ["execute", "stop"]);
        assert!(s.owner.retire(&mut s.manager, &mut s.memory).is_ok());
    }
}

#[test]
fn timer_requires_active_mapped_owner_without_touching_driver() {
    for mapped in [false, true] {
        let mut s = setup_with_timer(mapped);
        let mut driver = TimerDriver::new(&s);
        assert!(s.owner.exercise_timer(&mut driver).is_err());
        if !mapped {
            s.owner.activate(&s.manager, &mut s.memory).unwrap();
            assert!(s.owner.exercise_timer(&mut driver).is_err());
        }
        assert!(driver.calls.is_empty());
    }
}
