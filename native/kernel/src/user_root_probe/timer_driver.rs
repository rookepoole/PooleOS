//! Exclusive one-BSP development timer lease under the owned candidate root.
use super::*;
use poolekernel::user_entry::timer::{self, Driver, Error as TimerError, Mappings, Observation};

static EXPECTED_ROOT: AtomicU64 = AtomicU64::new(0);
static OBSERVED_ROOT: AtomicU64 = AtomicU64::new(0);
const MASK: u32 = 1 << 16;
const LVT: [u64; 6] = [0x320, 0x330, 0x340, 0x350, 0x360, 0x370];
const POLL_LIMIT: u32 = 2_000_000;

mod drain;
pub use drain::{Probe, dispatch as dispatch_drain, proof as drain_proof};

fn hw<T>(result: Result<T, interrupt_time::Error>) -> Result<T, TimerError> {
    result.map_err(|_| TimerError::Hardware)
}

pub struct Timer {
    mappings: Mappings,
    topology: interrupt_time::MadtTopology,
    hpet: interrupt_time::HpetDescription,
    apic_base: u64,
    pat: u64,
    configured: bool,
    cmci: bool,
    hpet_config: u64,
    probe: Probe,
}

impl Timer {
    pub fn new(
        handoff: &Handoff<'_>,
        topology: interrupt_time::MadtTopology,
        hpet: interrupt_time::HpetDescription,
        bits: u8,
    ) -> Result<Self, TimerError> {
        let cpu = arch::x86_64::observe_apic_cpu();
        if !cpu.apic_supported || topology.enabled_processor_count != 1 {
            return Err(TimerError::Hardware);
        }
        // SAFETY: this private constructor runs at CPL0 after APIC/PAT CPUID checks.
        let apic_base = unsafe { arch::x86_64::read_local_apic_base() };
        let pat = unsafe { arch::x86_64::read_supported_pat() }.ok_or(TimerError::Pat)?;
        if apic_base & (APIC_BASE_ENABLE | APIC_BASE_X2APIC | interrupt_time::APIC_BASE_BSP)
            != APIC_BASE_ENABLE | interrupt_time::APIC_BASE_BSP
            || apic_base & interrupt_time::APIC_BASE_ADDRESS_MASK != topology.local_apic_address
        {
            return Err(TimerError::Hardware);
        }
        let mappings = Mappings::from_handoff(
            handoff,
            topology.local_apic_address,
            hpet.physical_address,
            bits,
            pat,
        )?;
        Ok(Self {
            mappings,
            topology,
            hpet,
            apic_base,
            pat,
            configured: false,
            cmci: false,
            hpet_config: 0,
            probe: Probe::None,
        })
    }

    pub fn mappings(&self) -> Mappings {
        self.mappings
    }

    pub fn set_probe(&mut self, probe: Probe) {
        self.probe = probe;
    }

    fn context(&self, root: u64, mappings: Mappings) -> Result<LiveInterruptHardware, TimerError> {
        // SAFETY: CpuImage serialized this private adapter on the BSP at CPL0.
        let valid = unsafe {
            arch::x86_64::read_cr3() == root
                && arch::x86_64::read_local_apic_base() == self.apic_base
                && arch::x86_64::read_supported_pat() == Some(self.pat)
        };
        if root == 0
            || mappings != self.mappings
            || !valid
            || arch::x86_64::read_rflags() & (1 << 9) != 0
        {
            return Err(TimerError::Context);
        }
        Ok(LiveInterruptHardware {
            local_apic_virtual: timer::APIC_VIRTUAL,
            hpet_virtual: timer::HPET_VIRTUAL,
        })
    }

    fn idle(hardware: &mut LiveInterruptHardware) -> Result<(), TimerError> {
        if hw(hardware.in_service_count())? != 0 {
            return Err(TimerError::Hardware);
        }
        for bank in 0..8 {
            if hw(hardware.apic_read(0x200 + bank * 16))? != 0 {
                return Err(TimerError::Hardware);
            }
        }
        Ok(())
    }

    fn mask_sources(&self, hardware: &mut LiveInterruptHardware) -> Result<(), TimerError> {
        for offset in LVT.into_iter().chain(self.cmci.then_some(0x2f0)) {
            let value = hw(hardware.apic_read(offset))?;
            hw(hardware.apic_write(offset, value | MASK))?;
            if hw(hardware.apic_read(offset))? & MASK == 0 {
                return Err(TimerError::Hardware);
            }
        }
        Ok(())
    }
}

impl Timer {
    fn configure(
        &mut self,
        root: u64,
        mappings: Mappings,
        interval_ns: u64,
    ) -> Result<
        (
            LiveInterruptHardware,
            poolekernel::user_entry::preemption::Budget,
        ),
        TimerError,
    > {
        let mut hardware = self.context(root, mappings)?;
        if self.configured || EXPECTED_ROOT.load(Ordering::Acquire) != 0 {
            return Err(TimerError::State);
        }
        let id = hw(hardware.apic_read(0x20))?;
        let version = hw(hardware.apic_read(0x30))?;
        let discovery = hw(validate_apic_discovery(
            &self.topology,
            arch::x86_64::observe_apic_cpu(),
            self.apic_base,
            id,
            version,
        ))?;
        if !discovery.bsp
            || !discovery.globally_enabled
            || !(5..=6).contains(&discovery.max_lvt_entry)
        {
            return Err(TimerError::Hardware);
        }
        self.cmci = discovery.max_lvt_entry == 6;
        Self::idle(&mut hardware)?;
        let capabilities = hw(hardware.hpet_read(0))?;
        let period = capabilities >> 32;
        let counter64 = capabilities & (1 << 13) != 0;
        if !(100_000..=100_000_000).contains(&period)
            || counter64 != self.hpet.counter_64_bit_capable
        {
            return Err(TimerError::Hardware);
        }
        self.hpet_config = hw(hardware.hpet_read(0x10))?;
        if self.hpet_config & 2 != 0 {
            return Err(TimerError::Hardware);
        }
        for index in 0..=((capabilities >> 8) & 31) {
            if hw(hardware.hpet_read(0x100 + index * 0x20))? & 4 != 0 {
                return Err(TimerError::Hardware);
            }
        }
        // Mark effects before the first write; errors must still pass quiescence.
        self.configured = true;
        super::clock_driver::enter(root, mappings)?;
        if self.topology.pcat_compatible {
            // SAFETY: validated MADT PCAT_COMPAT, single BSP, no concurrent PIC owner.
            unsafe { arch::x86_64::mask_legacy_pic() }.map_err(|_| TimerError::Hardware)?;
        }
        self.mask_sources(&mut hardware)?;
        hw(hardware.apic_write(0x320, u32::from(TIMER_VECTOR) | MASK))?;
        hw(hardware.apic_write(0x80, 0))?;
        hw(hardware.apic_write(0xf0, u32::from(SPURIOUS_VECTOR) | (1 << 8)))?;
        hw(hardware.apic_write(0x3e0, 3))?;
        hw(hardware.hpet_write(0x10, self.hpet_config | 1))?;
        if hw(hardware.hpet_read(0x10))? != self.hpet_config | 1 {
            return Err(TimerError::Hardware);
        }
        let counter_mask = if counter64 {
            u64::MAX
        } else {
            u64::from(u32::MAX)
        };
        let start = hw(hardware.hpet_read(0xf0))? & counter_mask;
        hw(hardware.apic_write(0x380, u32::MAX))?;
        let target = 10_000_000_000_000u64.div_ceil(period);
        let mut elapsed = 0;
        for _ in 0..POLL_LIMIT {
            elapsed = hw(hardware.hpet_read(0xf0))?.wrapping_sub(start) & counter_mask;
            if elapsed >= target {
                break;
            }
            core::hint::spin_loop();
        }
        if elapsed < target {
            return Err(TimerError::Hardware);
        }
        let current = hw(hardware.apic_read(0x390))?;
        hw(hardware.apic_write(0x380, 0))?;
        let calibration = hw(calibrate_apic_timer(u32::MAX, current, elapsed, period))?;
        let count = hw(timer_initial_count(
            calibration.apic_ticks_per_second,
            interval_ns,
        ))?;
        IRQ_TIMER_DELIVERIES.store(0, Ordering::Release);
        IRQ_EOI_COUNT.store(0, Ordering::Release);
        IRQ_ERROR_COUNT.store(0, Ordering::Release);
        IRQ_SPURIOUS_COUNT.store(0, Ordering::Release);
        OBSERVED_ROOT.store(0, Ordering::Release);
        EXPECTED_ROOT.store(root, Ordering::Release);
        IRQ_APIC_VIRTUAL.store(timer::APIC_VIRTUAL, Ordering::Release);
        Ok((
            hardware,
            poolekernel::user_entry::preemption::Budget {
                count,
                period_fs: period,
                counter_mask,
            },
        ))
    }
}

impl Driver for Timer {
    fn execute(&mut self, root: u64, mappings: Mappings) -> Result<Observation, TimerError> {
        let (mut hardware, budget) = self.configure(root, mappings, 1_000_000)?;
        let poolekernel::user_entry::preemption::Budget {
            count,
            period_fs: period,
            counter_mask,
        } = budget;
        for expected in 1..=3 {
            let start = hw(hardware.hpet_read(0xf0))?;
            hw(hardware.apic_write(0x320, u32::from(TIMER_VECTOR)))?;
            hw(hardware.apic_write(0x380, count))?;
            for _ in 0..POLL_LIMIT {
                // SAFETY: exact candidate root, kernel IDT/IST, masked other LVT/PIC
                // sources, no AP/DMA. Soft-float kernel code does not use SIMD state.
                // No HLT: both stopped HPET and missing timer have bounded failure.
                unsafe {
                    core::arch::asm!("sti", "nop", "nop", "cli", options(nostack));
                }
                if IRQ_TIMER_DELIVERIES.load(Ordering::Acquire) >= expected {
                    break;
                }
                let elapsed = hw(hardware.hpet_read(0xf0))?.wrapping_sub(start) & counter_mask;
                if elapsed >= 100_000_000_000_000u64.div_ceil(period) {
                    break;
                }
            }
            hw(hardware.apic_write(0x320, u32::from(TIMER_VECTOR) | MASK))?;
            hw(hardware.apic_write(0x380, 0))?;
            if IRQ_TIMER_DELIVERIES.load(Ordering::Acquire) != expected
                || IRQ_EOI_COUNT.load(Ordering::Acquire) != expected
            {
                return Err(TimerError::Hardware);
            }
        }
        Ok(Observation {
            deliveries: IRQ_TIMER_DELIVERIES.load(Ordering::Acquire),
            eois: IRQ_EOI_COUNT.load(Ordering::Acquire),
            observed_root: OBSERVED_ROOT.load(Ordering::Acquire),
        })
    }

    fn quiesce(&mut self, root: u64, mappings: Mappings) -> Result<(), TimerError> {
        let mut hardware = self.context(root, mappings)?;
        if !self.configured {
            return Ok(());
        }
        drain::quiesce(self, root, &mut hardware)?;
        arch::x86_64::user_watchdog::restore_after_drain()?;
        if TRAP_DEPTH.load(Ordering::Acquire) != 0
            || IRQ_TIMER_DELIVERIES.load(Ordering::Acquire) != IRQ_EOI_COUNT.load(Ordering::Acquire)
            || IRQ_ERROR_COUNT.load(Ordering::Acquire) != 0
            || IRQ_SPURIOUS_COUNT.load(Ordering::Acquire) != 0
        {
            return Err(TimerError::Hardware);
        }
        let svr = hw(hardware.apic_read(0xf0))? & !(1 << 8);
        hw(hardware.apic_write(0xf0, svr))?;
        hw(hardware.hpet_write(0x10, self.hpet_config))?;
        if hw(hardware.apic_read(0xf0))? != svr || hw(hardware.hpet_read(0x10))? != self.hpet_config
        {
            return Err(TimerError::Hardware);
        }
        Self::idle(&mut hardware)?;
        super::clock_driver::leave(root, mappings)?;
        EXPECTED_ROOT.store(0, Ordering::Release);
        IRQ_APIC_VIRTUAL.store(0, Ordering::Release);
        self.configured = false;
        Ok(())
    }
}

/// This combined trusted driver owns user and device exposure under CpuImage's
/// user quarantine. Device shutdown must precede private-stack detachment.
pub struct UserRun<'a> {
    pub entry: &'a mut arch::x86_64::user::Entry,
    pub timer: &'a mut Timer,
    pub result: Option<poolekernel::user_entry::preemption::Observation>,
    pub calls: Option<arch::x86_64::user::CallObservation>,
}

impl poolekernel::user_entry::privilege::Driver for UserRun<'_> {
    fn execute(
        &mut self,
        image: poolekernel::user_entry::ImageAdmission,
    ) -> Result<
        poolekernel::user_entry::privilege::Observation,
        poolekernel::user_entry::privilege::Error,
    > {
        use poolekernel::user_entry::privilege::Error;
        self.result = None;
        self.calls = None;
        let (_, budget) = self
            .timer
            .configure(image.root_physical, self.timer.mappings, 10_000_000)
            .map_err(|_| Error::Hardware)?;
        self.entry.set_timer_budget(budget)?;
        let result = self.entry.execute(image)?;
        self.result = Some(self.entry.preemption_observation()?);
        self.calls = Some(self.entry.syscall_observation()?);
        Ok(result)
    }

    fn quiesce(&mut self, root: u64) -> Result<(), poolekernel::user_entry::privilege::Error> {
        self.timer
            .quiesce(root, self.timer.mappings)
            .map_err(|_| poolekernel::user_entry::privilege::Error::Hardware)?;
        self.entry.quiesce(root)
    }
}

pub fn dispatch_timer(frame: &TrapFrame, depth: u32) {
    let expected = EXPECTED_ROOT.load(Ordering::Acquire);
    // SAFETY: this dispatch is reached only by a CPL0 interrupt gate.
    let observed = unsafe { arch::x86_64::read_cr3() };
    if expected == 0 || observed != expected || frame.vector != u64::from(TIMER_VECTOR) {
        // SAFETY: fatal sole-BSP diagnostic, IF0; no other serial writer resumes.
        let mut serial = unsafe { Com1::initialize() };
        let mut debugcon = DebugCon::new();
        let mut log = EarlyLogger::new(BootSink {
            serial: &mut serial,
            debugcon: &mut debugcon,
            ring: &EARLY_RING,
        });
        log.write_str("POOLEOS:KERNEL:USER-ROOT-TRAP DENIED");
        for (label, value) in [
            (" vector=", frame.vector),
            (" error=", frame.error_code),
            (" rip=", frame.rip),
            (" rsp=", frame.rsp),
            (" cr2=", arch::x86_64::read_cr2()),
            (" observed_root=", observed),
            (" expected_root=", expected),
        ] {
            log.write_str(label);
            log.write_hex_u64(value);
        }
        log.write_str("\n");
        poole_kernel_emergency_panic(PanicCode::UserRoot as u32);
    }
    OBSERVED_ROOT.store(observed, Ordering::Release);
    dispatch_interrupt_time(frame, depth);
}

/// Owns timer and saved task state together; never detaches entry before device shutdown.
pub struct PeerRun {
    pub entry: arch::x86_64::user::PeerEntry,
    pub timer: Timer,
}
impl poolekernel::user_entry::task::Driver for PeerRun {
    fn revoke(
        &mut self,
        id: poolekernel::scheduler_smp::TaskId,
    ) -> Result<(), poolekernel::user_entry::privilege::Error> {
        poolekernel::user_entry::task::Driver::revoke(&mut self.entry, id)
    }
    fn execute(
        &mut self,
        _: poolekernel::user_entry::ImageAdmission,
        _: poolekernel::scheduler_smp::TaskId,
    ) -> Result<poolekernel::user_entry::task::Outcome, poolekernel::user_entry::privilege::Error>
    {
        Err(poolekernel::user_entry::privilege::Error::State)
    }
    fn quiesce(&mut self, root: u64) -> Result<(), poolekernel::user_entry::privilege::Error> {
        self.timer
            .quiesce(root, self.timer.mappings)
            .map_err(|_| poolekernel::user_entry::privilege::Error::Hardware)?;
        poolekernel::user_entry::task::Driver::quiesce(&mut self.entry, root)
    }
}
impl poolekernel::user_entry::task::SliceDriver for PeerRun {
    fn complete_wait(
        &mut self,
        id: poolekernel::scheduler_smp::TaskId,
        ticket: poolekernel::capability_ipc::wait::Ticket,
        status: poolekernel::user_entry::syscall::Status,
    ) -> Result<(), poolekernel::user_entry::privilege::Error> {
        poolekernel::user_entry::task::SliceDriver::complete_wait(
            &mut self.entry,
            id,
            ticket,
            status,
        )
    }
    fn execute_slice(
        &mut self,
        image: poolekernel::user_entry::ImageAdmission,
        id: poolekernel::scheduler_smp::TaskId,
    ) -> Result<poolekernel::user_entry::task::Slice, poolekernel::user_entry::privilege::Error>
    {
        let (_, budget) = self
            .timer
            .configure(image.root_physical, self.timer.mappings, 10_000_000)
            .map_err(|_| poolekernel::user_entry::privilege::Error::Hardware)?;
        self.entry.set_budget(budget)?;
        poolekernel::user_entry::task::SliceDriver::execute_slice(&mut self.entry, image, id)
    }
}
