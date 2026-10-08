//! Exclusive HPET comparator lease for a second, fixed xAPIC delivery source.
#![forbid(unsafe_code)]

use super::Error;

pub const CONTRACT_ID: &str = "PKUSER14";
pub const VECTOR: u8 = 65;
pub const DEADLINE_NS: u64 = 50_000_000;
const ENABLE: u64 = 1 << 2;
const FSB: u64 = 1 << 14;
const FSB_CAP: u64 = 1 << 15;
const SIZE_CAP: u64 = 1 << 5;
const CONFIG: u64 = 0x100;
const COMPARE: u64 = 0x108;
const ROUTE: u64 = 0x110;
const MODE: u64 = (1 << 1) | ENABLE | (1 << 3) | (1 << 6) | (1 << 8) | FSB;

/// The platform owns the exact UC HPET page and serializes all access at IF0.
/// Writes may take effect before returning an error. No arbitrary MSI address
/// is accepted: the lease derives a physical, edge, fixed-vector xAPIC message.
pub trait Hardware {
    fn read(&self, offset: u64) -> Result<u64, Error>;
    fn write(&mut self, offset: u64, value: u64) -> Result<(), Error>;
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
enum State {
    Ready,
    Arming,
    Armed,
    Stopped,
    Restoring,
    Restored,
}

/// Non-copyable persistent owner. Publish it before arm; retain it after errors.
pub struct Lease {
    original_config: u64,
    original_compare: u64,
    original_route: u64,
    route: u64,
    period: u64,
    ticks: u64,
    start: u64,
    deadline: u64,
    state: State,
}
impl Lease {
    pub fn prepare<H: Hardware>(h: &H, apic_id: u8) -> Result<Self, Error> {
        let capabilities = h.read(0)?;
        let period = capabilities >> 32;
        let config = h.read(CONFIG)?;
        if apic_id == 255
            || capabilities & (1 << 13) == 0
            || !(100_000..=100_000_000).contains(&period)
            || h.read(0x10)? & 3 != 1
            || config & (FSB_CAP | SIZE_CAP) != FSB_CAP | SIZE_CAP
            || config & ENABLE != 0
            || h.read(0x20)? != 0
        {
            return Err(Error::Hardware);
        }
        Ok(Self {
            original_config: config,
            original_compare: h.read(COMPARE)?,
            original_route: h.read(ROUTE)?,
            route: ((0xfee0_0000u64 | (u64::from(apic_id) << 12)) << 32) | u64::from(VECTOR),
            period,
            ticks: (DEADLINE_NS * 1_000_000).div_ceil(period),
            start: 0,
            deadline: 0,
            state: State::Ready,
        })
    }

    fn stopped_config(&self) -> u64 {
        (self.original_config & !MODE) | FSB
    }
    fn write_checked<H: Hardware>(h: &mut H, offset: u64, value: u64) -> Result<(), Error> {
        h.write(offset, value)?;
        if h.read(offset)? != value {
            return Err(Error::Hardware);
        }
        Ok(())
    }
    pub fn arm<H: Hardware>(&mut self, h: &mut H, start: u64) -> Result<(), Error> {
        if self.state != State::Ready {
            return Err(Error::State);
        }
        let deadline = start.checked_add(self.ticks).ok_or(Error::Hardware)?;
        self.start = start;
        self.deadline = deadline;
        self.state = State::Arming;
        Self::write_checked(h, CONFIG, self.stopped_config())?;
        Self::write_checked(h, ROUTE, self.route)?;
        Self::write_checked(h, COMPARE, deadline)?;
        // Reject a deadline lost while programming instead of waiting a wrap.
        let now = h.read(0xf0)?;
        if now < start || now >= deadline || h.read(0)? >> 32 != self.period {
            return Err(Error::Hardware);
        }
        Self::write_checked(h, CONFIG, self.stopped_config() | ENABLE)?;
        let enabled_at = h.read(0xf0)?;
        if enabled_at < now || enabled_at >= deadline {
            return Err(Error::Hardware);
        }
        self.state = State::Armed;
        Ok(())
    }
    pub fn expired<H: Hardware>(&self, h: &H, now: u64) -> Result<u64, Error> {
        let elapsed = now.checked_sub(self.start).ok_or(Error::Hardware)?;
        if self.state != State::Armed
            || now < self.deadline
            || elapsed > 100_000_000_000_000u64.div_ceil(self.period)
            || h.read(0)? >> 32 != self.period
            || h.read(CONFIG)? != self.stopped_config() | ENABLE
            || h.read(ROUTE)? != self.route
            || h.read(COMPARE)? != self.deadline
        {
            return Err(Error::Hardware);
        }
        Ok(elapsed)
    }
    /// Disables production of new messages. The caller must still drain APIC
    /// pending/in-service work before restore, detachment or memory release.
    pub fn stop<H: Hardware>(&mut self, h: &mut H) -> Result<(), Error> {
        if matches!(self.state, State::Ready | State::Restored) {
            return Ok(());
        }
        self.state = State::Arming;
        Self::write_checked(h, CONFIG, self.stopped_config())?;
        self.state = State::Stopped;
        Ok(())
    }
    /// Requires a platform proof that both owned vectors have drained at IF0.
    pub fn restore_after_drain<H: Hardware>(&mut self, h: &mut H) -> Result<(), Error> {
        if matches!(self.state, State::Ready | State::Restored) {
            return Ok(());
        }
        if !matches!(self.state, State::Stopped | State::Restoring) {
            return Err(Error::State);
        }
        if h.read(CONFIG)? & ENABLE != 0 {
            return Err(Error::Hardware);
        }
        self.state = State::Restoring;
        Self::write_checked(h, ROUTE, self.original_route)?;
        Self::write_checked(h, COMPARE, self.original_compare)?;
        Self::write_checked(h, CONFIG, self.original_config)?;
        self.state = State::Restored;
        Ok(())
    }
}

#[cfg(test)]
mod tests;
