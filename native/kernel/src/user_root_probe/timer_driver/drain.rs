//! Kernel-only delivery window. User descriptors and the exact root remain owned.
use super::*;
use core::sync::atomic::AtomicU32;
use poolekernel::user_entry::timer::drain::{self as policy, Hardware, Snapshot};

static DRAIN_ROOT: AtomicU64 = AtomicU64::new(0);
static WINDOW_RSP: AtomicU64 = AtomicU64::new(0);
static DELIVERIES: AtomicU32 = AtomicU32::new(0);
static EOIS: AtomicU32 = AtomicU32::new(0);
static PENDING_CASES: AtomicU32 = AtomicU32::new(0);
static LATE_CASES: AtomicU32 = AtomicU32::new(0);
static FAILURES: AtomicU32 = AtomicU32::new(0);
static RETRIES: AtomicU32 = AtomicU32::new(0);

#[derive(Clone, Copy, Eq, PartialEq)]
pub enum Probe {
    None,
    Pending,
    Late,
    FailOnce,
    Retry,
}

fn snapshot(h: &LiveInterruptHardware) -> Result<Snapshot, TimerError> {
    let mut s = Snapshot {
        irr: [0; 8],
        isr: [0; 8],
        tmr: [0; 8],
        lvt: hw(h.apic_read(0x320))?,
        initial: hw(h.apic_read(0x380))?,
        current: hw(h.apic_read(0x390))?,
        deliveries: DELIVERIES.load(Ordering::Acquire),
        eois: EOIS.load(Ordering::Acquire),
    };
    for i in 0..8 {
        s.irr[i] = hw(h.apic_read(0x200 + i as u64 * 16))?;
        s.isr[i] = hw(h.apic_read(0x100 + i as u64 * 16))?;
        s.tmr[i] = hw(h.apic_read(0x180 + i as u64 * 16))?;
    }
    Ok(s)
}

// Native fault injection uses an actual one-shot timer with IF0, never a forged
// transcript or fabricated IRR/ISR register. Only development peers request it.
fn force_pending(h: &mut LiveInterruptHardware) -> Result<(), TimerError> {
    Timer::idle(h)?;
    hw(h.apic_write(0x320, u32::from(TIMER_VECTOR)))?;
    hw(h.apic_write(0x380, 1))?;
    for _ in 0..POLL_LIMIT {
        if hw(h.apic_read(0x200 + u64::from(TIMER_VECTOR / 32) * 16))? & (1 << (TIMER_VECTOR % 32))
            != 0
        {
            return Ok(());
        }
        core::hint::spin_loop();
    }
    Err(TimerError::Hardware)
}

struct Adapter<'a> {
    timer: &'a Timer,
    root: u64,
    hw: &'a mut LiveInterruptHardware,
    fail: bool,
}
impl Hardware for Adapter<'_> {
    fn stop(&mut self) -> Result<(), TimerError> {
        self.timer.mask_sources(self.hw)?;
        hw(self.hw.apic_write(0x380, 0))?;
        Ok(())
    }
    fn snapshot(&mut self) -> Result<Snapshot, TimerError> {
        snapshot(self.hw)
    }
    fn window(&mut self) -> Result<(), TimerError> {
        if self.fail {
            return Err(TimerError::Hardware);
        }
        self.timer.context(self.root, self.timer.mappings)?;
        if TRAP_DEPTH.load(Ordering::Acquire) != 0
            || EXPECTED_ROOT.load(Ordering::Acquire) != self.root
            || IRQ_APIC_VIRTUAL.load(Ordering::Acquire) != timer::APIC_VIRTUAL
            || DRAIN_ROOT.load(Ordering::Acquire) != 0
        {
            return Err(TimerError::Context);
        }
        DRAIN_ROOT.store(self.root, Ordering::Release);
        // SAFETY: stopped/masked exclusive timer, exact retained root, kernel
        // stack and IDT still attached. The dispatcher admits only this window.
        unsafe {
            poole_user_timer_drain_window(WINDOW_RSP.as_ptr());
        }
        DRAIN_ROOT.store(0, Ordering::Release);
        WINDOW_RSP.store(0, Ordering::Release);
        self.timer.context(self.root, self.timer.mappings)?;
        if TRAP_DEPTH.load(Ordering::Acquire) != 0 {
            return Err(TimerError::Context);
        }
        Ok(())
    }
}

pub(super) fn quiesce(
    t: &mut Timer,
    root: u64,
    h: &mut LiveInterruptHardware,
) -> Result<(), TimerError> {
    let probe = t.probe;
    match probe {
        Probe::Pending | Probe::FailOnce => force_pending(h)?,
        Probe::Late => {
            Timer::idle(h)?;
            // Observe empty IRR first, then let a real timer arrive before stop.
            force_pending(h)?;
        }
        _ => (),
    }
    if probe == Probe::FailOnce {
        t.probe = Probe::Retry;
    }
    let result = policy::quiesce(&mut Adapter {
        timer: t,
        root,
        hw: h,
        fail: probe == Probe::FailOnce,
    });
    if probe == Probe::FailOnce {
        let state = snapshot(h)?;
        state.validate(false)?;
        if result.is_ok() || state.irr.iter().all(|v| *v == 0) {
            return Err(TimerError::State);
        }
        FAILURES.fetch_add(1, Ordering::AcqRel);
        return Err(TimerError::Hardware);
    }
    let result = result?;
    if probe != Probe::None {
        if result.deliveries != 1 {
            return Err(TimerError::Hardware);
        }
        match probe {
            Probe::Pending => {
                PENDING_CASES.fetch_add(1, Ordering::AcqRel);
            }
            Probe::Late => {
                LATE_CASES.fetch_add(1, Ordering::AcqRel);
            }
            Probe::Retry => {
                RETRIES.fetch_add(1, Ordering::AcqRel);
            }
            _ => return Err(TimerError::State),
        }
        t.probe = Probe::None;
    }
    Ok(())
}

pub fn proof() -> Result<u32, TimerError> {
    let deliveries = DELIVERIES.load(Ordering::Acquire);
    if PENDING_CASES.load(Ordering::Acquire) != 1
        || LATE_CASES.load(Ordering::Acquire) != 1
        || FAILURES.load(Ordering::Acquire) != 1
        || RETRIES.load(Ordering::Acquire) != 1
        || deliveries < 3
        || deliveries != EOIS.load(Ordering::Acquire)
        || DRAIN_ROOT.load(Ordering::Acquire) != 0
        || WINDOW_RSP.load(Ordering::Acquire) != 0
        || EXPECTED_ROOT.load(Ordering::Acquire) != 0
        || IRQ_APIC_VIRTUAL.load(Ordering::Acquire) != 0
    {
        return Err(TimerError::State);
    }
    Ok(deliveries)
}

pub fn dispatch(frame: &TrapFrame, depth: u32) -> bool {
    let root = DRAIN_ROOT.load(Ordering::Acquire);
    if root == 0 {
        return false;
    }
    let start = &raw const poole_user_timer_drain_start as u64;
    let end = &raw const poole_user_timer_drain_end as u64;
    let rsp = WINDOW_RSP.load(Ordering::Acquire);
    let frame_address = frame as *const TrapFrame as u64;
    let stack_ok = if arch::x86_64::user::active() {
        frame_address.checked_add(core::mem::size_of::<TrapFrame>() as u64) == Some(rsp & !15)
    } else {
        frame_address >= IST1_BOTTOM.load(Ordering::Acquire)
            && frame_address
                .checked_add(core::mem::size_of::<TrapFrame>() as u64)
                .is_some_and(|v| v <= IST1_TOP.load(Ordering::Acquire))
    };
    if depth != 1
        || frame.vector != u64::from(TIMER_VECTOR)
        || frame.error_code != 0
        || frame.code_selector != u64::from(poolekernel::KERNEL_CODE_SELECTOR)
        || frame.data_selector != u64::from(poolekernel::KERNEL_DATA_SELECTOR)
        || frame.rflags & 0x202 != 0x202
        || frame.rflags & ((1 << 14) | (1 << 17) | (1 << 18)) != 0
        || frame.rip < start
        || frame.rip > end
        || rsp == 0
        || frame.rsp != rsp
        || !stack_ok
        || unsafe { arch::x86_64::read_cr3() } != root
        || EXPECTED_ROOT.load(Ordering::Acquire) != root
        || IRQ_APIC_VIRTUAL.load(Ordering::Acquire) != timer::APIC_VIRTUAL
        || arch::x86_64::read_rflags() & (1 << 9) != 0
    {
        poole_kernel_emergency_panic(PanicCode::UserRoot as u32);
    }
    let mut h = LiveInterruptHardware {
        local_apic_virtual: timer::APIC_VIRTUAL,
        hpet_virtual: timer::HPET_VIRTUAL,
    };
    if snapshot(&h).and_then(|s| s.validate(true)).is_err() {
        poole_kernel_emergency_panic(PanicCode::UserRoot as u32);
    }
    if hw(h.apic_write(0xb0, 0)).is_err() {
        poole_kernel_emergency_panic(PanicCode::UserRoot as u32);
    }
    for counter in [&DELIVERIES, &EOIS, &IRQ_TIMER_DELIVERIES, &IRQ_EOI_COUNT] {
        if counter.fetch_add(1, Ordering::AcqRel) == u32::MAX {
            poole_kernel_emergency_panic(PanicCode::UserRoot as u32);
        }
    }
    TRAP_DEPTH.store(0, Ordering::Release);
    true
}

unsafe extern "C" {
    fn poole_user_timer_drain_window(rsp: *mut u64);
    static poole_user_timer_drain_start: u8;
    static poole_user_timer_drain_end: u8;
}
core::arch::global_asm!(
    r#"
    .section .text
    .global poole_user_timer_drain_window
poole_user_timer_drain_window:
    mov [rdi], rsp
    sti
    nop
    .global poole_user_timer_drain_start
poole_user_timer_drain_start:
    nop
    nop
    .global poole_user_timer_drain_end
poole_user_timer_drain_end:
    cli
    ret
"#
);
