//! Continuous HPET counter ownership, independent of any task's CPU quantum.
#![forbid(unsafe_code)]

use super::{Error, watchdog::Hardware};

pub const CONTRACT_ID: &str = "PKCLOCK1";
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
enum State {
    Prepared,
    Starting,
    Running,
    Poisoned,
    Restoring,
    Restored,
}

/// Publish before `start`; never drop a lease with uncertain device effects.
/// The adapter exclusively owns the global configuration and counter. A child
/// comparator owner may temporarily arm interrupts but may not stop/reset this
/// counter, and must drain/restore before this owner can release the device.
///
/// ```compile_fail
/// use poolekernel::user_entry::timer::clock::Lease;
/// fn duplicate(owner: &Lease) -> Lease { owner.clone() }
/// ```
pub struct Lease {
    capabilities: u64,
    original_config: u64,
    origin: u64,
    last: u64,
    samples: u64,
    state: State,
}

impl Lease {
    pub fn prepare(h: &impl Hardware) -> Result<Self, Error> {
        let capabilities = h.read(0)?;
        let config = h.read(0x10)?;
        if capabilities & (1 << 13) == 0
            || capabilities & 0xff == 0
            || !(100_000..=100_000_000).contains(&(capabilities >> 32))
            || config & 2 != 0
        {
            return Err(Error::Hardware);
        }
        Self::idle(h, capabilities)?;
        Ok(Self {
            capabilities,
            original_config: config,
            origin: 0,
            last: 0,
            samples: 0,
            state: State::Prepared,
        })
    }

    fn idle(h: &impl Hardware, capabilities: u64) -> Result<(), Error> {
        if h.read(0x20)? != 0 {
            return Err(Error::Hardware);
        }
        for i in 0..=((capabilities >> 8) & 31) {
            if h.read(0x100 + i * 0x20)? & 4 != 0 {
                return Err(Error::Hardware);
            }
        }
        Ok(())
    }

    pub fn start(&mut self, h: &mut impl Hardware) -> Result<(), Error> {
        if self.state != State::Prepared {
            return Err(Error::State);
        }
        if h.read(0)? != self.capabilities || h.read(0x10)? != self.original_config {
            return Err(Error::Hardware);
        }
        Self::idle(h, self.capabilities)?;
        self.state = State::Starting;
        h.write(0x10, self.original_config | 1)?;
        if h.read(0x10)? != self.original_config | 1 {
            return Err(Error::Hardware);
        }
        let raw = h.read(0xf0)?;
        self.origin = raw;
        self.last = raw;
        self.state = State::Running;
        Ok(())
    }

    /// Repeated values are legal below counter resolution. Never fabricate time
    /// after an uncertain read; recovery requires ending this entire epoch.
    pub fn sample(&mut self, h: &impl Hardware) -> Result<u64, Error> {
        if self.state != State::Running {
            return Err(Error::State);
        }
        self.state = State::Poisoned;
        if h.read(0)? != self.capabilities || h.read(0x10)? != self.original_config | 1 {
            return Err(Error::Hardware);
        }
        let raw = h.read(0xf0)?;
        if raw < self.last {
            return Err(Error::Hardware);
        }
        let nanos = u128::from(raw - self.origin) * u128::from(self.capabilities >> 32) / 1_000_000;
        let nanos = u64::try_from(nanos).map_err(|_| Error::Hardware)?;
        let samples = self.samples.checked_add(1).ok_or(Error::State)?;
        self.last = raw;
        self.samples = samples;
        self.state = State::Running;
        Ok(nanos)
    }

    /// Caller must also prove no pending/in-service child interrupt can execute.
    /// On failure retain the owner and mapping. Retry may restore a prior failed
    /// write, but cannot make a poisoned epoch usable for time again.
    pub fn release(&mut self, h: &mut impl Hardware) -> Result<(), Error> {
        if self.state == State::Restored {
            return Err(Error::State);
        }
        self.state = State::Restoring;
        if h.read(0)? != self.capabilities {
            return Err(Error::Hardware);
        }
        let config = h.read(0x10)?;
        if config != self.original_config && config != self.original_config | 1 {
            return Err(Error::Hardware);
        }
        Self::idle(h, self.capabilities)?;
        h.write(0x10, self.original_config)?;
        if h.read(0x10)? != self.original_config {
            return Err(Error::Hardware);
        }
        self.state = State::Restored;
        Ok(())
    }

    pub const fn observation(&self) -> (u64, u64, u64, u64) {
        (
            self.origin,
            self.last,
            self.capabilities >> 32,
            self.samples,
        )
    }
}

#[cfg(test)]
mod tests;
