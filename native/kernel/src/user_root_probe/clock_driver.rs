//! One-BSP continuous clock epoch shared by serialized dispatch timer children.
use super::*;
use poolekernel::user_entry::timer::{self, Error as ClockError, Mappings, watchdog::Hardware};

struct Adapter(LiveInterruptHardware);
impl Hardware for Adapter {
    fn read(&self, offset: u64) -> Result<u64, ClockError> {
        self.0.hpet_read(offset).map_err(|_| ClockError::Hardware)
    }
    fn write(&mut self, offset: u64, value: u64) -> Result<(), ClockError> {
        self.0
            .hpet_write(offset, value)
            .map_err(|_| ClockError::Hardware)
    }
}
struct Owner {
    mappings: Mappings,
    kernel_root: u64,
    pat: u64,
    child: Option<u64>,
    enters: u64,
    leaves: u64,
}
static mut OWNER: Option<Owner> = None;

fn context(root: u64, pat: u64) -> Result<(), ClockError> {
    // SAFETY: private adapter invoked on the exclusive BSP at CPL0 only.
    if root == 0
        || unsafe { arch::x86_64::read_cr3() } != root
        || unsafe { arch::x86_64::read_supported_pat() } != Some(pat)
        || arch::x86_64::read_rflags() & ((1 << 9) | (1 << 10) | (1 << 18)) != 0
    {
        return Err(ClockError::Context);
    }
    Ok(())
}
fn hardware(task: bool) -> Adapter {
    Adapter(LiveInterruptHardware {
        local_apic_virtual: if task {
            timer::APIC_VIRTUAL
        } else {
            virtual_memory::LOCAL_APIC_MAP_START
        },
        hpet_virtual: if task {
            timer::HPET_VIRTUAL
        } else {
            virtual_memory::HPET_MAP_START
        },
    })
}

fn unmap_kernel(memory: &mut BootstrapTableMemory) -> Result<(), ClockError> {
    memory
        .uninstall_uncached_mmio()
        .map_err(|_| ClockError::Hardware)?;
    for (index, address) in [
        (
            poole_kmap::LOCAL_APIC_PAGE,
            virtual_memory::LOCAL_APIC_MAP_START,
        ),
        (poole_kmap::HPET_PAGE, virtual_memory::HPET_MAP_START),
    ] {
        // SAFETY: BootstrapTableMemory owns these retained, identity-mapped leaves.
        if unsafe { read_volatile(memory.indexed_leaf_pointer(index)) } != 0
            || poole_kmap::translate(
                &ActivePhysicalReader,
                memory.active_root,
                address,
                memory.physical_address_bits,
            ) != Err(poole_kmap::Error::TranslationMissing)
        {
            return Err(ClockError::Hardware);
        }
    }
    Ok(())
}

/// Trusted timer constructor already proved this exact task root and MMIO plan.
pub(super) fn enter(root: u64, mappings: Mappings) -> Result<(), ClockError> {
    let Some(o) = (unsafe { (&mut *(&raw mut OWNER)).as_mut() }) else {
        return Ok(());
    };
    context(root, o.pat)?;
    if o.child.is_some() || root == o.kernel_root || mappings != o.mappings {
        return Err(ClockError::State);
    }
    o.child = Some(root);
    unsafe { arch::x86_64::user_ipc::with_clock(|s| s.sample_clock(&hardware(true))) }?;
    o.enters = o.enters.checked_add(1).ok_or(ClockError::State)?;
    Ok(())
}

/// Called only after child source shutdown, interrupt drain and register restore.
pub(super) fn leave(root: u64, mappings: Mappings) -> Result<(), ClockError> {
    let Some(o) = (unsafe { (&mut *(&raw mut OWNER)).as_mut() }) else {
        return Ok(());
    };
    context(root, o.pat)?;
    if o.child != Some(root) || mappings != o.mappings || arch::x86_64::user_watchdog::owned() {
        return Err(ClockError::State);
    }
    unsafe { arch::x86_64::user_ipc::with_clock(|s| s.sample_clock(&hardware(true))) }?;
    o.leaves = o.leaves.checked_add(1).ok_or(ClockError::State)?;
    o.child = None;
    Ok(())
}

/// Called only after the syscall adapter has authenticated the complete frame.
pub(crate) fn syscall_sample(root: u64) -> Result<(), ClockError> {
    let Some(o) = (unsafe { (&*(&raw const OWNER)).as_ref() }) else {
        return Ok(());
    };
    context(root, o.pat)?;
    if o.child != Some(root) || root == o.kernel_root {
        return Err(ClockError::Context);
    }
    unsafe { arch::x86_64::user_ipc::with_clock(|s| s.sample_clock(&hardware(true))) }?;
    Ok(())
}

/// Dropping this owner never silently restores hardware or revokes live mappings.
pub(super) struct Session {
    memory: BootstrapTableMemory,
    root: u64,
    pat: u64,
    idle_ns: u64,
    intervals: u64,
}
impl Session {
    pub(super) fn start(
        handoff: &Handoff<'_>,
        core: CoreRecord,
        bits: u8,
        manager: &PhysicalMemoryManager,
        topology: interrupt_time::MadtTopology,
        hpet: interrupt_time::HpetDescription,
    ) -> Result<Self, ClockError> {
        if unsafe { (&*(&raw const OWNER)).is_some() }
            || arch::x86_64::user::active()
            || arch::x86_64::user_watchdog::owned()
            || IRQ_APIC_VIRTUAL.load(Ordering::Acquire) != 0
        {
            return Err(ClockError::State);
        }
        let timer = timer_driver::Timer::new(handoff, topology, hpet, bits)?;
        let mappings = timer.mappings();
        mappings.validate(manager, bits)?;
        let pat = unsafe { arch::x86_64::read_supported_pat() }.ok_or(ClockError::Pat)?;
        context(core.page_table_root_physical, pat)?;
        let mut memory = BootstrapTableMemory::new(core.page_table_root_physical, bits)
            .map_err(|_| ClockError::Context)?;
        let [apic, hpet] = mappings.pages();
        memory
            .install_uncached_mmio(apic, hpet)
            .map_err(|_| ClockError::Hardware)?;
        let mut h = hardware(false);
        // Publish before effects. A failed start retains OWNER and its MMIO mapping;
        // this diagnostic halts rather than releasing potentially active hardware.
        unsafe {
            write_volatile(
                &raw mut OWNER,
                Some(Owner {
                    mappings,
                    kernel_root: core.page_table_root_physical,
                    pat,
                    child: None,
                    enters: 0,
                    leaves: 0,
                }),
            );
        }
        unsafe {
            arch::x86_64::user_ipc::with_clock(|s| {
                s.prepare_clock(&h)?;
                s.start_clock(&mut h)
            })
        }?;
        // Task construction/revalidation admits the original boot supervisor map.
        // Keep the clock running, but revoke these aliases before either boundary.
        unmap_kernel(&mut memory)?;
        Ok(Self {
            memory,
            root: core.page_table_root_physical,
            pat,
            idle_ns: 0,
            intervals: 0,
        })
    }
    fn map_kernel(&mut self) -> Result<(), ClockError> {
        context(self.root, self.pat)?;
        let o = unsafe { (&*(&raw const OWNER)).as_ref() }.ok_or(ClockError::State)?;
        if o.kernel_root != self.root || o.child.is_some() || arch::x86_64::user::active() {
            return Err(ClockError::State);
        }
        let [apic, hpet] = o.mappings.pages();
        self.memory
            .install_uncached_mmio(apic, hpet)
            .map_err(|_| ClockError::Hardware)?;
        Ok(())
    }
    fn sample(&mut self) -> Result<u64, ClockError> {
        context(self.root, self.pat)?;
        let o = unsafe { (&mut *(&raw mut OWNER)).as_mut() }.ok_or(ClockError::State)?;
        if o.kernel_root != self.root
            || o.child.is_some()
            || arch::x86_64::user::active()
            || self.memory.mmio_physical != o.mappings.pages().map(Some)
        {
            return Err(ClockError::State);
        }
        unsafe { arch::x86_64::user_ipc::with_clock(|s| s.sample_clock(&hardware(false))) }
    }
    pub(super) fn idle_interval(&mut self) -> Result<(), ClockError> {
        self.map_kernel()?;
        let start = self.sample()?;
        for _ in 0..2_000_000 {
            let elapsed = self
                .sample()?
                .checked_sub(start)
                .ok_or(ClockError::Hardware)?;
            if elapsed >= 1_000_000 {
                self.idle_ns = self.idle_ns.checked_add(elapsed).ok_or(ClockError::State)?;
                self.intervals += 1;
                unmap_kernel(&mut self.memory)?;
                return Ok(());
            }
            core::hint::spin_loop();
        }
        Err(ClockError::Hardware)
    }
    pub(super) fn finish(&mut self, serial: &mut Com1, debugcon: &mut DebugCon) -> Result<(), u64> {
        self.finish_mode(false, serial, debugcon)
    }
    /// All tasks are parked; bounded polling is diagnostic idle, not power-efficient sleep.
    pub(super) fn expire_idle(&mut self) -> Result<u64, ClockError> {
        self.map_kernel()?;
        let before = unsafe { arch::x86_64::user_ipc::with_clock(|s| s.clock_observation()) }?
            .0
            .expired;
        for _ in 0..2_000_000 {
            let now = self.sample()?;
            let count = unsafe { arch::x86_64::user_ipc::with_clock(|s| s.clock_observation()) }?
                .0
                .expired;
            if count > before {
                unmap_kernel(&mut self.memory)?;
                self.intervals += 1;
                return Ok(now);
            }
            core::hint::spin_loop();
        }
        Err(ClockError::Hardware)
    }
    pub(super) fn finish_deadlines(
        &mut self,
        serial: &mut Com1,
        debugcon: &mut DebugCon,
    ) -> Result<(), u64> {
        self.finish_mode(true, serial, debugcon)
    }
    fn finish_mode(
        &mut self,
        deadlines: bool,
        serial: &mut Com1,
        debugcon: &mut DebugCon,
    ) -> Result<(), u64> {
        self.map_kernel().map_err(|_| 1u64)?;
        let elapsed = self.sample().map_err(|_| 2u64)?;
        if IRQ_APIC_VIRTUAL.load(Ordering::Acquire) != 0
            || arch::x86_64::user_watchdog::owned()
            || !unsafe { arch::x86_64::user_ipc::empty() }.map_err(|_| 3u64)?
        {
            return Err(3);
        }
        let o = unsafe { (&mut *(&raw mut OWNER)).as_mut() }.ok_or(4u64)?;
        let (observation, (origin, last, period, samples)) =
            unsafe { arch::x86_64::user_ipc::with_clock(|s| s.clock_observation()) }
                .map_err(|_| 4u64)?;
        let expected = if deadlines { 10 } else { 12 };
        if o.enters != expected
            || o.leaves != expected
            || self.intervals != if deadlines { 2 } else { 4 }
            || elapsed < self.idle_ns
            || (!deadlines && self.idle_ns < 4_000_000)
            || observation.failed
            || observation.epoch != if deadlines { 2 } else { 1 }
            || observation.expired != if deadlines { 2 } else { 0 }
        {
            let mut log = EarlyLogger::new(BootSink {
                serial,
                debugcon,
                ring: &EARLY_RING,
            });
            log.write_str("POOLEOS:KERNEL:USER-CLOCK DENIED");
            for (label, value) in [
                (" enters=", o.enters),
                (" leaves=", o.leaves),
                (" intervals=", self.intervals),
                (" elapsed=", elapsed),
                (" idle=", self.idle_ns),
            ] {
                log.write_str(label);
                log.write_decimal_u64(value);
            }
            log.write_str("\n");
            return Err(5);
        }
        let mut h = hardware(false);
        // A child lease is gone only after both APIC ISR and IRR are empty.
        for bank in 0..8 {
            for base in [0x100, 0x200] {
                if h.0.apic_read(base + bank * 16).map_err(|_| 6u64)? != 0 {
                    return Err(7);
                }
            }
        }
        unsafe { arch::x86_64::user_ipc::with_clock(|s| s.release_clock(&mut h)) }
            .map_err(|_| 8u64)?;
        unmap_kernel(&mut self.memory).map_err(|_| 9u64)?;
        // TableMemory::finish requires a live temporary RAM alias to revoke.
        // This MMIO-only owner created none: replay the complete empty-region
        // constructor instead, including the temporary, metadata and ledger slots.
        let _ = BootstrapTableMemory::new(self.root, self.memory.physical_address_bits)
            .map_err(|_| 10u64)?;
        if self.memory.mmio_pte_writes != if deadlines { 16 } else { 24 } {
            return Err(11);
        }
        unsafe { write_volatile(&raw mut OWNER, None) };
        let mut log = EarlyLogger::new(BootSink {
            serial,
            debugcon,
            ring: &EARLY_RING,
        });
        log.write_str(if deadlines {
            "POOLEOS:KERNEL:USER-DEADLINE-CLOCK PASS contract=PKIPC5"
        } else {
            "POOLEOS:KERNEL:USER-CLOCK PASS contract=PKCLOCK1"
        });
        for (label, value) in [
            (" origin=", origin),
            (" last=", last),
            (" period_fs=", period),
            (" elapsed_ns=", elapsed),
            (" samples=", samples),
            (" idle_ns=", self.idle_ns),
        ] {
            log.write_str(label);
            log.write_decimal_u64(value);
        }
        log.write_str(if deadlines {
            " enters=10 leaves=10 idle_expiries=2 epoch=2 expired=2 config_restored=1 counter_reset=0 mmio_writes=16 mapping_windows=4 mapping_revoked=4 guards=3 clock=hpet64 scope=one_bsp timed_ipc=1 production=0\n"
        } else {
            " enters=12 leaves=12 idle_intervals=4 config_restored=1 counter_reset=0 mmio_writes=24 mapping_windows=6 mapping_revoked=6 guards=3 clock=hpet64 scope=one_bsp timed_ipc=0 production=0\n"
        });
        Ok(())
    }
}
