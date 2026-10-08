//! Interrupt-side state for the exclusive development user/timer lease.
use super::*;
use poolekernel::user_entry::timer;
use poolekernel::user_entry::{
    ImageAdmission,
    preemption::{Budget, Layout, Observation, Sequence},
    privilege::{Error, Trap},
};

pub(super) struct Session {
    image: ImageAdmission,
    layout: Layout,
    budget: Budget,
    sequence: Option<Sequence>,
    start_counter: u64,
    fx: FxsaveArea,
}

fn hw<T>(result: Result<T, poolekernel::interrupt_time::Error>) -> Result<T, Error> {
    result.map_err(|_| Error::Hardware)
}

fn hardware() -> Result<crate::LiveInterruptHardware, Error> {
    if crate::IRQ_APIC_VIRTUAL.load(Ordering::Acquire) != timer::APIC_VIRTUAL
        || read_rflags() & (1 << 9) != 0
    {
        return Err(Error::Context);
    }
    Ok(crate::LiveInterruptHardware {
        local_apic_virtual: timer::APIC_VIRTUAL,
        hpet_virtual: timer::HPET_VIRTUAL,
    })
}

fn idle(h: &crate::LiveInterruptHardware) -> Result<(), Error> {
    if hw(h.in_service_count())? != 0 {
        return Err(Error::Hardware);
    }
    for bank in 0..8 {
        if hw(h.apic_read(0x200 + bank * 16))? != 0 {
            return Err(Error::Hardware);
        }
    }
    Ok(())
}

pub(super) fn arm_quantum(budget: Budget, suppress_local: bool) -> Result<u64, Error> {
    budget.validate()?;
    let mut h = hardware()?;
    idle(&h)?;
    if hw(h.hpet_read(0))? >> 32 != budget.period_fs
        || hw(h.apic_read(0x380))? != 0
        || hw(h.apic_read(0x390))? != 0
    {
        return Err(Error::Hardware);
    }
    let start = hw(h.hpet_read(0xf0))?;
    super::user_watchdog::arm(start).map_err(|_| Error::Hardware)?;
    let mask = if suppress_local { 1 << 16 } else { 0 };
    hw(h.apic_write(0x320, u32::from(crate::TIMER_VECTOR) | mask))?;
    hw(h.apic_write(0x380, budget.count))?;
    if hw(h.apic_read(0x320))? != u32::from(crate::TIMER_VECTOR) | mask
        || hw(h.apic_read(0x380))? != budget.count
    {
        return Err(Error::Hardware);
    }
    Ok(start)
}

pub(super) fn finish_quantum(budget: Budget, start: u64) -> Result<u64, Error> {
    let mut h = hardware()?;
    super::user_watchdog::stop().map_err(|_| Error::Hardware)?;
    let ticks = budget.elapsed(start, hw(h.hpet_read(0xf0))?)?;
    let vector = u32::from(crate::TIMER_VECTOR);
    if hw(h.in_service_count())? != 1
        || hw(h.apic_read(0x100 + u64::from(vector / 32) * 16))? != 1 << (vector % 32)
        || hw(h.apic_read(0x320))? != vector
        || hw(h.apic_read(0x390))? != 0
    {
        return Err(Error::Hardware);
    }
    hw(h.apic_write(0x320, vector | (1 << 16)))?;
    hw(h.apic_write(0x380, 0))?;
    if hw(h.apic_read(0x380))? != 0 || hw(h.apic_read(0x390))? != 0 {
        return Err(Error::Hardware);
    }
    hw(h.apic_write(0xb0, 0))?;
    // Pending owned backup delivery is drained by the retained timer owner.
    for bank in 0..8 {
        let allowed = if bank == 2 { 3 } else { 0 };
        if hw(h.apic_read(0x100 + bank * 16))? != 0
            || hw(h.apic_read(0x200 + bank * 16))? & !allowed != 0
            || hw(h.apic_read(0x180 + bank * 16))? & allowed != 0
        {
            return Err(Error::Hardware);
        }
    }
    Ok(ticks)
}

pub(super) fn terminal_ticks(budget: Budget, start: u64) -> Result<u64, Error> {
    let h = hardware()?;
    if hw(h.hpet_read(0))? >> 32 != budget.period_fs {
        return Err(Error::Hardware);
    }
    budget.partial_elapsed(start, hw(h.hpet_read(0xf0))?)
}

impl Session {
    pub(super) fn new(
        image: ImageAdmission,
        layout: Layout,
        budget: Budget,
    ) -> Result<Self, Error> {
        Ok(Self {
            image,
            layout,
            budget: budget.validate()?,
            sequence: None,
            start_counter: 0,
            fx: FxsaveArea([0; 512]),
        })
    }

    fn arm(&mut self) -> Result<(), Error> {
        let mut h = hardware()?;
        idle(&h)?;
        if hw(h.hpet_read(0))? >> 32 != self.budget.period_fs
            || hw(h.apic_read(0x380))? != 0
            || hw(h.apic_read(0x390))? != 0
        {
            return Err(Error::Hardware);
        }
        self.start_counter = hw(h.hpet_read(0xf0))?;
        hw(h.apic_write(0x320, u32::from(crate::TIMER_VECTOR)))?;
        hw(h.apic_write(0x380, self.budget.count))?;
        Ok(())
    }

    pub(super) fn start(&mut self, t: &Trap) -> Result<u64, Error> {
        if self.sequence.is_some() || unsafe { read_cr3() } != self.image.root_physical {
            return Err(Error::State);
        }
        self.sequence = Some(Sequence::new(self.image, self.layout, t.registers)?);
        // SAFETY: private aligned storage under the existing enabled legacy-FP lease.
        unsafe {
            fxsave_area(self.fx.0.as_mut_ptr());
        }
        self.arm()?;
        Ok(self.image.initial_frame.rip + self.layout.increment)
    }

    pub(super) fn interrupt(&mut self, t: &Trap) -> Result<bool, Error> {
        let mut h = hardware()?;
        self.budget
            .elapsed(self.start_counter, hw(h.hpet_read(0xf0))?)?;
        let vector = u32::from(crate::TIMER_VECTOR);
        if hw(h.in_service_count())? != 1
            || hw(h.apic_read(0x100 + u64::from(vector / 32) * 16))? != 1 << (vector % 32)
            || hw(h.apic_read(0x320))? != vector
            || hw(h.apic_read(0x390))? != 0
        {
            return Err(Error::Hardware);
        }
        let mut observed = FxsaveArea([0; 512]);
        // SAFETY: the soft-float interrupt handler never acquires an FP owner.
        unsafe {
            fxsave_area(observed.0.as_mut_ptr());
        }
        if observed.0[..416] != self.fx.0[..416] {
            return Err(Error::Registers);
        }
        let terminal = self.sequence.as_mut().ok_or(Error::State)?.accept(t)?;
        hw(h.apic_write(0x320, vector | (1 << 16)))?;
        hw(h.apic_write(0x380, 0))?;
        if hw(h.apic_read(0x380))? != 0 || hw(h.apic_read(0x390))? != 0 {
            return Err(Error::Hardware);
        }
        hw(h.apic_write(0xb0, 0))?;
        idle(&h)?;
        let count = self.observation()?.deliveries;
        if crate::IRQ_TIMER_DELIVERIES.fetch_add(1, Ordering::AcqRel) != count - 1
            || crate::IRQ_EOI_COUNT.fetch_add(1, Ordering::AcqRel) != count - 1
        {
            return Err(Error::Hardware);
        }
        if !terminal {
            self.arm()?;
        }
        Ok(terminal)
    }

    pub(super) fn observation(&self) -> Result<Observation, Error> {
        self.sequence
            .as_ref()
            .map(Sequence::observation)
            .ok_or(Error::State)
    }

    pub(super) fn shutdown_verified(&self) -> bool {
        // The owning timer driver must revoke its dispatch authority before GDT/TSS detachment.
        crate::IRQ_APIC_VIRTUAL.load(Ordering::Acquire) == 0
            && crate::IRQ_TIMER_DELIVERIES.load(Ordering::Acquire)
                == crate::IRQ_EOI_COUNT.load(Ordering::Acquire)
    }
}
