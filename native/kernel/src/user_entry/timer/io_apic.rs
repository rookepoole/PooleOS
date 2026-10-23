//! Exclusive non-legacy, edge-triggered HPET route with retained rollback.
#![forbid(unsafe_code)]

use super::{Error, watchdog::VECTOR};
use crate::interrupt_time::IoApic;
const MASK: u32 = 1 << 16;

/// The adapter serializes the selector/window pair at IF0 on the sole BSP.
/// Writes may take effect before returning an error.
pub trait Hardware {
    fn read(&self, index: u8) -> Result<u32, Error>;
    fn write(&mut self, index: u8, value: u32) -> Result<(), Error>;
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
enum State {
    Ready,
    Programming,
    Armed,
    Stopped,
    Restoring,
    Restored,
}

/// Non-copyable route ownership. Publish before arm and retain after errors.
pub struct Lease {
    gsi: u8,
    index: u8,
    destination: u32,
    original_low: u32,
    original_high: u32,
    original_id: u32,
    desired_id: u32,
    version: u32,
    state: State,
}

impl Lease {
    pub fn prepare<H: Hardware>(
        h: &H,
        description: IoApic,
        apic_id: u8,
        routes: u32,
        excluded: u32,
    ) -> Result<Self, Error> {
        let original_id = h.read(0)?;
        let desired_id = u32::from(description.id) << 24;
        if apic_id == 255
            || description.id > 15
            || description.global_interrupt_base > 31
            || (original_id != desired_id && original_id != 0)
        {
            return Err(Error::Hardware);
        }
        let version = h.read(1)?;
        let last = (version >> 16) & 255;
        if !matches!(version & 255, 0x11 | 0x20) || version & !0x00ff_00ff != 0 || last > 119 {
            return Err(Error::Hardware);
        }
        if original_id != desired_id {
            Self::pristine(h, last)?;
        }
        for gsi in (16..32u8).rev() {
            let global = u32::from(gsi);
            if routes & !excluded & (1 << gsi) == 0 || global < description.global_interrupt_base {
                continue;
            }
            let pin = global - description.global_interrupt_base;
            if pin > last {
                continue;
            }
            let index = (0x10 + 2 * pin) as u8;
            let low = h.read(index)?;
            let high = h.read(index + 1)?;
            // Only pristine masked entries can be borrowed; never steal a route.
            if low == MASK && high == 0 {
                return Ok(Self {
                    gsi,
                    index,
                    destination: u32::from(apic_id) << 24,
                    original_low: low,
                    original_high: high,
                    original_id,
                    desired_id,
                    version,
                    state: State::Ready,
                });
            }
        }
        Err(Error::Hardware)
    }
    pub const fn gsi(&self) -> u8 {
        self.gsi
    }
    fn pristine<H: Hardware>(h: &H, last: u32) -> Result<(), Error> {
        // Reset-ID initialization is limited to an otherwise unused controller.
        for pin in 0..=last {
            let index = (0x10 + 2 * pin) as u8;
            if h.read(index)? != MASK || h.read(index + 1)? != 0 {
                return Err(Error::Hardware);
            }
        }
        Ok(())
    }
    fn write<H: Hardware>(h: &mut H, index: u8, value: u32) -> Result<(), Error> {
        h.write(index, value)?;
        if h.read(index)? != value {
            return Err(Error::Hardware);
        }
        Ok(())
    }
    pub fn arm<H: Hardware>(&mut self, h: &mut H) -> Result<(), Error> {
        if self.state != State::Ready {
            return Err(Error::State);
        }
        if h.read(0)? != self.original_id
            || h.read(1)? != self.version
            || h.read(self.index)? != self.original_low
            || h.read(self.index + 1)? != self.original_high
        {
            return Err(Error::Hardware);
        }
        if self.original_id != self.desired_id {
            Self::pristine(h, (self.version >> 16) & 255)?;
        }
        self.state = State::Programming;
        if self.original_id != self.desired_id {
            Self::write(h, 0, self.desired_id)?;
        }
        Self::write(h, self.index, MASK | u32::from(VECTOR))?;
        Self::write(h, self.index + 1, self.destination)?;
        Self::write(h, self.index, u32::from(VECTOR))?;
        self.state = State::Armed;
        Ok(())
    }
    pub fn validate<H: Hardware>(&self, h: &H) -> Result<(), Error> {
        if self.state != State::Armed
            || h.read(0)? != self.desired_id
            || h.read(1)? != self.version
            || h.read(self.index)? != u32::from(VECTOR)
            || h.read(self.index + 1)? != self.destination
        {
            return Err(Error::Hardware);
        }
        Ok(())
    }
    /// Source production must be stopped before masking this delivery route.
    pub fn stop<H: Hardware>(&mut self, h: &mut H) -> Result<(), Error> {
        if matches!(self.state, State::Ready | State::Restored) {
            return Ok(());
        }
        self.state = State::Programming;
        Self::write(h, self.index, MASK | u32::from(VECTOR))?;
        self.state = State::Stopped;
        Ok(())
    }
    /// The platform must first prove the owned edge vector drained at IF0.
    pub fn restore_after_drain<H: Hardware>(&mut self, h: &mut H) -> Result<(), Error> {
        if matches!(self.state, State::Ready | State::Restored) {
            return Ok(());
        }
        if !matches!(self.state, State::Stopped | State::Restoring)
            || h.read(self.index)? & MASK == 0
        {
            return Err(Error::State);
        }
        self.state = State::Restoring;
        Self::write(h, self.index + 1, self.original_high)?;
        Self::write(h, self.index, self.original_low)?;
        if self.original_id != self.desired_id {
            Self::write(h, 0, self.original_id)?;
        }
        self.state = State::Restored;
        Ok(())
    }
}

#[cfg(test)]
mod tests;
