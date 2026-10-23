//! Sole-BSP HPET comparator ownership; never shares a live lease across roots.
use super::*;
use poolekernel::user_entry::timer::{
    self, Error, io_apic,
    watchdog::{self, Hardware, Lease, VECTOR},
};

struct Owned {
    root: u64,
    lease: Lease,
    stopped: bool,
    route: Option<io_apic::Lease>,
}
static mut OWNER: Option<Owned> = None;
#[derive(Clone, Copy)]
struct RouteContext {
    root: u64,
    description: poolekernel::interrupt_time::IoApic,
    excluded: u32,
}
static mut ROUTE_CONTEXT: Option<RouteContext> = None;
static ROUTED_ARMS: AtomicU64 = AtomicU64::new(0);
static ROUTED_RESTORES: AtomicU64 = AtomicU64::new(0);
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

struct IoAdapter;
impl io_apic::Hardware for IoAdapter {
    fn read(&self, index: u8) -> Result<u32, Error> {
        // Sole BSP/IF0 owns this UC mapping and the selector/window transaction.
        unsafe {
            let select = timer::IO_APIC_VIRTUAL as *mut u32;
            let original = read_volatile(select);
            write_volatile(select, u32::from(index));
            let value = read_volatile((timer::IO_APIC_VIRTUAL + 0x10) as *const u32);
            write_volatile(select, original);
            Ok(value)
        }
    }
    fn write(&mut self, index: u8, value: u32) -> Result<(), Error> {
        unsafe {
            let select = timer::IO_APIC_VIRTUAL as *mut u32;
            let original = read_volatile(select);
            write_volatile(select, u32::from(index));
            write_volatile((timer::IO_APIC_VIRTUAL + 0x10) as *mut u32, value);
            write_volatile(select, original);
        }
        Ok(())
    }
}

pub fn configure_route(
    root: u64,
    description: Option<poolekernel::interrupt_time::IoApic>,
    excluded: u32,
) -> Result<(), Error> {
    hardware(root)?;
    if owned() || unsafe { (&*(&raw const ROUTE_CONTEXT)).is_some() } {
        return Err(Error::State);
    }
    unsafe {
        write_volatile(
            &raw mut ROUTE_CONTEXT,
            description.map(|description| RouteContext {
                root,
                description,
                excluded,
            }),
        );
    }
    Ok(())
}
pub fn release_route(root: u64) -> Result<(), Error> {
    if owned() || unsafe { (&*(&raw const ROUTE_CONTEXT)).is_some_and(|c| c.root != root) } {
        return Err(Error::State);
    }
    unsafe {
        write_volatile(&raw mut ROUTE_CONTEXT, None);
    }
    Ok(())
}
fn io_hardware(root: u64) -> Result<(IoAdapter, RouteContext), Error> {
    hardware(root)?;
    let context = unsafe { *(&raw const ROUTE_CONTEXT) }.ok_or(Error::Context)?;
    if context.root != root {
        return Err(Error::Context);
    }
    Ok((IoAdapter, context))
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
    fn stage<T>(number: u64, result: Result<T, Error>) -> Result<T, Error> {
        result.inspect_err(|error| {
            super::user::report_failure("watchdog-route", number, *error as u64)
        })
    }
    let root = unsafe { read_cr3() };
    let mut h = hardware(root)?;
    if owned() {
        return Err(Error::State);
    }
    let id = h.0.apic_read(0x20).map_err(|_| Error::Hardware)?;
    if id & 0x00ff_ffff != 0 {
        return Err(Error::Hardware);
    }
    let route = if watchdog::supports_fsb(&h)? {
        None
    } else {
        let (io, context) = stage(1, io_hardware(root))?;
        let prepared = io_apic::Lease::prepare(
            &io,
            context.description,
            (id >> 24) as u8,
            watchdog::interrupt_routes(&h)?,
            context.excluded,
        );
        if prepared.is_err() {
            use io_apic::Hardware as _;
            super::user::report_failure(
                "ioapic-id",
                u64::from(context.description.id),
                u64::from(io.read(0)?),
            );
            super::user::report_failure(
                "ioapic-version",
                u64::from(context.description.global_interrupt_base),
                u64::from(io.read(1)?),
            );
            super::user::report_failure(
                "ioapic-routes",
                u64::from(context.excluded),
                u64::from(watchdog::interrupt_routes(&h)?),
            );
        }
        Some(stage(2, prepared)?)
    };
    let lease = match &route {
        None => Lease::prepare(&h, (id >> 24) as u8)?,
        Some(route) => stage(3, Lease::prepare_io_apic(&h, route.gsi()))?,
    };
    // Publish before device effects; error paths retain the original registers.
    unsafe {
        write_volatile(
            &raw mut OWNER,
            Some(Owned {
                root,
                lease,
                stopped: false,
                route,
            }),
        );
    }
    let owner = unsafe { (&mut *(&raw mut OWNER)).as_mut() }.ok_or(Error::State)?;
    if let Some(route) = &mut owner.route {
        stage(4, route.arm(&mut io_hardware(root)?.0))?;
    }
    stage(5, owner.lease.arm(&mut h, start))?;
    if owner.route.is_some() {
        ROUTED_ARMS.fetch_add(1, Ordering::AcqRel);
    }
    ARMS.fetch_add(1, Ordering::AcqRel);
    Ok(())
}
pub(super) fn expired(now: u64) -> Result<u64, Error> {
    let owner = unsafe { (&*(&raw const OWNER)).as_ref() }.ok_or(Error::State)?;
    let h = hardware(owner.root)?;
    if let Some(route) = &owner.route {
        route.validate(&io_hardware(owner.root)?.0)?;
    }
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
    if let Some(route) = &mut owner.route {
        route.stop(&mut io_hardware(owner.root)?.0)?;
    }
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
    if let Some(route) = &mut owner.route {
        route.restore_after_drain(&mut io_hardware(owner.root)?.0)?;
        ROUTED_RESTORES.fetch_add(1, Ordering::AcqRel);
    }
    unsafe {
        write_volatile(&raw mut OWNER, None);
    }
    RESTORES.fetch_add(1, Ordering::AcqRel);
    Ok(())
}
pub fn proof() -> Result<[u64; 4], Error> {
    routed_proof()?;
    Ok([
        ARMS.load(Ordering::Acquire),
        FIRES.load(Ordering::Acquire),
        STOPS.load(Ordering::Acquire),
        RESTORES.load(Ordering::Acquire),
    ])
}
pub fn routed_proof() -> Result<[u64; 2], Error> {
    if owned()
        || unsafe { (&*(&raw const ROUTE_CONTEXT)).is_some() }
        || read_rflags() & (1 << 9) != 0
    {
        return Err(Error::State);
    }
    Ok([
        ROUTED_ARMS.load(Ordering::Acquire),
        ROUTED_RESTORES.load(Ordering::Acquire),
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
