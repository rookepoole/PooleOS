//! Bounded shutdown of the exclusively owned one-shot local-APIC timer.
#![forbid(unsafe_code)]

use super::Error;
use crate::interrupt_time::TIMER_VECTOR;

pub const CONTRACT_ID: &str = "PKUSER12";
pub const WINDOW_LIMIT: u32 = 32;
pub const MASK: u32 = 1 << 16;
pub const SENDING: u32 = 1 << 12;

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct Snapshot {
    pub irr: [u32; 8],
    pub isr: [u32; 8],
    pub tmr: [u32; 8],
    pub lvt: u32,
    pub initial: u32,
    pub current: u32,
    pub deliveries: u32,
    pub eois: u32,
}
impl Snapshot {
    pub fn validate(self, in_handler: bool) -> Result<(), Error> {
        self.validate_owned(in_handler.then_some(TIMER_VECTOR), false)
    }
    pub fn validate_owned(self, handler: Option<u8>, backup_owned: bool) -> Result<(), Error> {
        let bank = usize::from(TIMER_VECTOR / 32);
        let bit = (1 << (TIMER_VECTOR % 32))
            | if backup_owned {
                1 << (super::watchdog::VECTOR % 32)
            } else {
                0
            };
        if handler
            .is_some_and(|v| v != TIMER_VECTOR && !(backup_owned && v == super::watchdog::VECTOR))
        {
            return Err(Error::Hardware);
        }
        if self.lvt & !SENDING != u32::from(TIMER_VECTOR) | MASK
            || self.initial != 0
            || self.current != 0
            || self.tmr[bank] & bit != 0
            || self.deliveries != self.eois
        {
            return Err(Error::Hardware);
        }
        for i in 0..8 {
            let allowed = if i == bank { bit } else { 0 };
            let expected_isr = handler
                .filter(|v| usize::from(v / 32) == i)
                .map_or(0, |v| 1 << (v % 32));
            if self.irr[i] & !allowed != 0 || self.isr[i] != expected_isr {
                return Err(Error::Hardware);
            }
        }
        Ok(())
    }
    fn pending(self) -> bool {
        self.irr.iter().any(|v| *v != 0) || self.lvt & SENDING != 0
    }
}

/// Trusted sole-BSP adapter. Root, descriptors, mappings and stacks stay owned.
/// Every operation enters/exits with IF clear. Only `window` may briefly enable
/// IF, with a kernel-only authenticated handler that EOIs exactly the timer.
/// No method may re-arm a source. Errors can follow hardware effects; callers
/// must retain their entire CPU/device owner and retry, never detach on error.
pub trait Hardware {
    fn stop(&mut self) -> Result<(), Error>;
    fn snapshot(&mut self) -> Result<Snapshot, Error>;
    fn window(&mut self) -> Result<(), Error>;
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct Receipt {
    pub windows: u32,
    pub deliveries: u32,
}

pub fn quiesce<H: Hardware>(h: &mut H) -> Result<Receipt, Error> {
    quiesce_owned(h, false)
}
pub fn quiesce_owned<H: Hardware>(h: &mut H, backup_owned: bool) -> Result<Receipt, Error> {
    h.stop()?;
    let first = h.snapshot()?;
    first.validate_owned(None, backup_owned)?;
    let mut last = first.deliveries;
    for windows in 1..=WINDOW_LIMIT {
        // Open even after an empty first snapshot: a just-accepted interrupt may
        // still be reaching IRR. Device stop/readback remains a prerequisite.
        h.window()?;
        let now = h.snapshot()?;
        now.validate_owned(None, backup_owned)?;
        if now.deliveries < last
            || now.deliveries - first.deliveries > if backup_owned { 4 } else { 2 }
        {
            return Err(Error::Hardware);
        }
        last = now.deliveries;
        if !now.pending() {
            return Ok(Receipt {
                windows,
                deliveries: last - first.deliveries,
            });
        }
    }
    Err(Error::Hardware)
}

#[cfg(test)]
mod tests;
