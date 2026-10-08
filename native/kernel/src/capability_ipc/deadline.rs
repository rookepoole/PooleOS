//! Clock and request epochs belong to the same persistent IPC owner.
//! The exclusive adapter must sample before IPC effects and while all tasks wait.
use super::*;
use crate::user_entry::timer::{Error as ClockError, clock::Lease, watchdog::Hardware};

pub const CONTRACT_ID: &str = "PKIPC5";
pub const MAX_TIMEOUT_NS: u64 = 1_000_000_000;

#[derive(Debug, Eq, PartialEq)]
pub(super) struct Clock {
    pub(super) generation: u64,
    lease: Option<Lease>,
    now: Option<u64>,
    failed: bool,
    pub(super) expired: u64,
}
impl Clock {
    pub(super) const EMPTY: Self = Self {
        generation: 0,
        lease: None,
        now: None,
        failed: false,
        expired: 0,
    };
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct Observation {
    pub epoch: u64,
    pub now_ns: Option<u64>,
    pub expired: u64,
    pub failed: bool,
}

impl Space {
    /// No device writes here. Publish ownership before start can affect hardware.
    pub fn prepare_clock(&mut self, h: &impl Hardware) -> Result<(), ClockError> {
        if self.clock.lease.is_some() {
            return Err(ClockError::State);
        }
        let generation = self
            .clock
            .generation
            .checked_add(1)
            .ok_or(ClockError::State)?;
        let lease = Lease::prepare(h)?;
        self.clock = Clock {
            generation,
            lease: Some(lease),
            now: None,
            failed: false,
            expired: 0,
        };
        Ok(())
    }
    pub fn start_clock(&mut self, h: &mut impl Hardware) -> Result<(), ClockError> {
        if self.clock.failed {
            return Err(ClockError::State);
        }
        let result = self.clock.lease.as_mut().ok_or(ClockError::State)?.start(h);
        if result.is_err() {
            self.poison_clock();
        }
        result
    }
    fn poison_clock(&mut self) {
        self.clock.failed = true;
        self.expire_requests(self.clock.generation, None);
    }
    /// Hardware uncertainty terminates pending timed requests, never invents time.
    /// The failed lease remains owned until explicit hardware restoration succeeds.
    pub fn sample_clock(&mut self, h: &impl Hardware) -> Result<u64, ClockError> {
        if self.clock.failed {
            return Err(ClockError::State);
        }
        let result = self
            .clock
            .lease
            .as_mut()
            .ok_or(ClockError::State)?
            .sample(h);
        match result {
            Ok(now) => {
                self.clock.now = Some(now);
                let expired = u64::from(self.expire_requests(self.clock.generation, Some(now)));
                let Some(total) = self.clock.expired.checked_add(expired) else {
                    self.poison_clock();
                    return Err(ClockError::State);
                };
                self.clock.expired = total;
                Ok(now)
            }
            Err(e) => {
                self.poison_clock();
                Err(e)
            }
        }
    }
    /// Pending deadlines prevent closure. Completion records survive epoch change.
    pub fn release_clock(&mut self, h: &mut impl Hardware) -> Result<(), ClockError> {
        if self.pending_deadlines() {
            return Err(ClockError::State);
        }
        self.clock.failed = true;
        self.clock
            .lease
            .as_mut()
            .ok_or(ClockError::State)?
            .release(h)?;
        self.clock.lease = None;
        self.clock.now = None;
        Ok(())
    }
    pub fn clock_observation(&self) -> Result<(Observation, (u64, u64, u64, u64)), ClockError> {
        Ok((
            Observation {
                epoch: self.clock.generation,
                now_ns: self.clock.now,
                expired: self.clock.expired,
                failed: self.clock.failed,
            },
            self.clock
                .lease
                .as_ref()
                .ok_or(ClockError::State)?
                .observation(),
        ))
    }
    pub(super) fn deadline_after(&self, timeout_ns: u64) -> Result<(u64, u64), Status> {
        if timeout_ns == 0 || timeout_ns > MAX_TIMEOUT_NS {
            return Err(Status::Arguments);
        }
        if self.clock.lease.is_none() || self.clock.failed {
            return Err(Status::ClockUnavailable);
        }
        let now = self.clock.now.ok_or(Status::ClockUnavailable)?;
        Ok((
            self.clock.generation,
            now.checked_add(timeout_ns).ok_or(Status::Arguments)?,
        ))
    }
}
