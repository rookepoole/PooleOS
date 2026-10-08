//! Sole-BSP HPET comparator ownership; never shares a live lease across roots.
use super::*;
use poolekernel::user_entry::timer::{
    self, Error,
    watchdog::{Hardware, Lease, VECTOR},
};

struct Owned {
    root: u64,
    lease: Lease,
    stopped: bool,
}
static mut OWNER: Option<Owned> = None;
static ARMS: AtomicU64 = AtomicU64::new(0);
static FIRES: AtomicU64 = AtomicU64::new(0);
static STOPS: AtomicU64 = AtomicU64::new(0);
static RESTORES: AtomicU64 = AtomicU64::new(0);

struct Adapter(crate::LiveInterruptHardware);
impl Hardware for Adapter {
    fn read(&self, offset: u64) -> Result<u64, Error> {
        self.0.hpet_read(offset).map_err(|_| Error::Hardware)
    }
    fn write(&mut self, offset: u64, value: u64) -> Result<(), Error> {
        self.0
            .hpet_write(offset, value)
            .map_err(|_| Error::Hardware)
    }
}
fn hardware(root: u64) -> Result<Adapter, Error> {
    if root == 0
        || unsafe { read_cr3() } != root
        || read_rflags() & (1 << 9) != 0
        || crate::IRQ_APIC_VIRTUAL.load(Ordering::Acquire) != timer::APIC_VIRTUAL
    {
        return Err(Error::Context);
    }
    Ok(Adapter(crate::LiveInterruptHardware {
        local_apic_virtual: timer::APIC_VIRTUAL,
        hpet_virtual: timer::HPET_VIRTUAL,
    }))
}
pub fn owned() -> bool {
    // SAFETY: only the serialized BSP at IF0 reads the live device owner.
    unsafe { (&*(&raw const OWNER)).is_some() }
}
pub(super) fn arm(start: u64) -> Result<(), Error> {
    let root = unsafe { read_cr3() };
    let mut h = hardware(root)?;
    if owned() {
        return Err(Error::State);
    }
    let id = h.0.apic_read(0x20).map_err(|_| Error::Hardware)?;
    if id & 0x00ff_ffff != 0 {
        return Err(Error::Hardware);
    }
    let lease = Lease::prepare(&h, (id >> 24) as u8)?;
    // Publish before device effects; error paths retain the original registers.
    unsafe {
        write_volatile(
            &raw mut OWNER,
            Some(Owned {
                root,
                lease,
                stopped: false,
            }),
        );
    }
    unsafe { (&mut *(&raw mut OWNER)).as_mut() }
        .ok_or(Error::State)?
        .lease
        .arm(&mut h, start)?;
    ARMS.fetch_add(1, Ordering::AcqRel);
    Ok(())
}
pub(super) fn expired(now: u64) -> Result<u64, Error> {
    let owner = unsafe { (&*(&raw const OWNER)).as_ref() }.ok_or(Error::State)?;
    let h = hardware(owner.root)?;
    let ticks = owner.lease.expired(&h, now)?;
    FIRES.fetch_add(1, Ordering::AcqRel);
    Ok(ticks)
}
pub fn stop() -> Result<(), Error> {
    let Some(owner) = (unsafe { (&mut *(&raw mut OWNER)).as_mut() }) else {
        return Ok(());
    };
    let mut h = hardware(owner.root)?;
    owner.lease.stop(&mut h)?;
    if !owner.stopped {
        owner.stopped = true;
        STOPS.fetch_add(1, Ordering::AcqRel);
    }
    Ok(())
}
pub fn restore_after_drain() -> Result<(), Error> {
    let Some(owner) = (unsafe { (&mut *(&raw mut OWNER)).as_mut() }) else {
        return Ok(());
    };
    let mut h = hardware(owner.root)?;
    for bank in 0..8 {
        for offset in [0x100, 0x200] {
            if h.0
                .apic_read(offset + bank * 16)
                .map_err(|_| Error::Hardware)?
                != 0
            {
                return Err(Error::Hardware);
            }
        }
    }
    if !owner.stopped {
        return Err(Error::State);
    }
    owner.lease.restore_after_drain(&mut h)?;
    unsafe {
        write_volatile(&raw mut OWNER, None);
    }
    RESTORES.fetch_add(1, Ordering::AcqRel);
    Ok(())
}
pub fn proof() -> Result<[u64; 4], Error> {
    if owned() || read_rflags() & (1 << 9) != 0 {
        return Err(Error::State);
    }
    Ok([
        ARMS.load(Ordering::Acquire),
        FIRES.load(Ordering::Acquire),
        STOPS.load(Ordering::Acquire),
        RESTORES.load(Ordering::Acquire),
    ])
}
pub(super) fn finish(
    budget: poolekernel::user_entry::preemption::Budget,
    start: u64,
) -> Result<u64, poolekernel::user_entry::privilege::Error> {
    use poolekernel::user_entry::privilege::Error as UserError;
    let mut h = hardware(unsafe { read_cr3() }).map_err(|_| UserError::Hardware)?;
    let now = h.read(0xf0).map_err(|_| UserError::Hardware)?;
    let ticks = expired(now).map_err(|_| UserError::Hardware)?;
    if ticks != budget.elapsed(start, now)?
        || h.0.in_service_count().map_err(|_| UserError::Hardware)? != 1
        || h.0
            .apic_read(0x100 + u64::from(VECTOR / 32) * 16)
            .map_err(|_| UserError::Hardware)?
            != 1 << (VECTOR % 32)
    {
        return Err(UserError::Hardware);
    }
    stop().map_err(|_| UserError::Hardware)?;
    for (offset, value) in [
        (0x320, u32::from(crate::TIMER_VECTOR) | (1 << 16)),
        (0x380, 0),
    ] {
        h.0.apic_write(offset, value)
            .map_err(|_| UserError::Hardware)?;
        if h.0.apic_read(offset).map_err(|_| UserError::Hardware)? != value {
            return Err(UserError::Hardware);
        }
    }
    h.0.apic_write(0xb0, 0).map_err(|_| UserError::Hardware)?;
    crate::IRQ_TIMER_DELIVERIES.fetch_add(1, Ordering::AcqRel);
    crate::IRQ_EOI_COUNT.fetch_add(1, Ordering::AcqRel);
    Ok(ticks)
}
