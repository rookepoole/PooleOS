//! Single-owner calibration reuse within one unchanged BSP/root/device lifetime.
#![forbid(unsafe_code)]
use super::Error;
use crate::interrupt_time::calibrate_apic_timer;

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct Key {
    pub root: u64,
    pub apic_id: u32,
    pub apic_version: u32,
    pub hpet_capabilities: u64,
}

/// Not transferable across CPU/device/power lifetimes. The adapter must re-read
/// identity and program the same APIC divider before every lookup. This does not
/// detect physical frequency drift, migration or suspend; those are unsupported.
pub struct Cache {
    sample: Option<(Key, u64)>,
}
impl Default for Cache {
    fn default() -> Self {
        Self::new()
    }
}
impl Cache {
    pub const fn new() -> Self {
        Self { sample: None }
    }
    pub fn lookup(&self, key: Key) -> Result<Option<u64>, Error> {
        if key.root == 0
            || key.root & 4095 != 0
            || !(100_000..=100_000_000).contains(&(key.hpet_capabilities >> 32))
        {
            return Err(Error::Hardware);
        }
        match self.sample {
            None => Ok(None),
            Some((bound, frequency)) if bound == key => Ok(Some(frequency)),
            Some(_) => Err(Error::Context),
        }
    }
    pub fn record(
        &mut self,
        key: Key,
        initial: u32,
        current: u32,
        ticks: u64,
    ) -> Result<u64, Error> {
        if self.lookup(key)?.is_some() {
            return Err(Error::State);
        }
        let calibrated = calibrate_apic_timer(initial, current, ticks, key.hpet_capabilities >> 32)
            .map_err(|_| Error::Hardware)?;
        self.sample = Some((key, calibrated.apic_ticks_per_second));
        Ok(calibrated.apic_ticks_per_second)
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    fn key() -> Key {
        Key {
            root: 0x100000,
            apic_id: 0,
            apic_version: 0x50014,
            hpet_capabilities: (10_000_000 << 32) | 0x2000,
        }
    }
    #[test]
    fn record_once_and_reuse_without_new_sample() {
        let mut c = Cache::new();
        assert_eq!(c.lookup(key()), Ok(None));
        let f = c
            .record(key(), u32::MAX, u32::MAX - 10000, 1_000_000)
            .unwrap();
        assert_eq!(f, 1_000_000);
        for _ in 0..1024 {
            assert_eq!(c.lookup(key()), Ok(Some(f)));
        }
        assert_eq!(
            c.record(key(), u32::MAX, u32::MAX - 20000, 1_000_000),
            Err(Error::State)
        );
        assert_eq!(c.lookup(key()), Ok(Some(f)));
    }
    #[test]
    fn identity_change_cannot_reuse_or_replace_sample() {
        let mut c = Cache::new();
        c.record(key(), u32::MAX, u32::MAX - 10000, 1_000_000)
            .unwrap();
        for altered in [
            Key {
                root: 0x200000,
                ..key()
            },
            Key {
                apic_id: 1 << 24,
                ..key()
            },
            Key {
                apic_version: 0x60014,
                ..key()
            },
            Key {
                hpet_capabilities: (20_000_000 << 32) | 0x2000,
                ..key()
            },
            Key {
                hpet_capabilities: 10_000_000 << 32,
                ..key()
            },
        ] {
            assert_eq!(c.lookup(altered), Err(Error::Context));
            assert_eq!(
                c.record(altered, u32::MAX, u32::MAX - 10000, 1_000_000),
                Err(Error::Context)
            );
        }
        assert_eq!(c.lookup(key()), Ok(Some(1_000_000)));
    }
    #[test]
    fn invalid_measurements_leave_cache_empty() {
        for (current, ticks) in [
            (u32::MAX, 1_000_000),
            (u32::MAX - 1, 0),
            (u32::MAX - 1, 1),
            (u32::MAX - 10000, u64::MAX),
            (0, 1_000_000),
        ] {
            let mut c = Cache::new();
            assert_eq!(
                c.record(key(), u32::MAX, current, ticks),
                Err(Error::Hardware)
            );
            assert_eq!(c.lookup(key()), Ok(None));
        }
    }
    #[test]
    fn invalid_root_or_period_never_admitted() {
        for altered in [
            Key { root: 0, ..key() },
            Key {
                root: 0x100001,
                ..key()
            },
            Key {
                hpet_capabilities: 0,
                ..key()
            },
        ] {
            let mut c = Cache::new();
            assert_eq!(c.lookup(altered), Err(Error::Hardware));
            assert_eq!(
                c.record(altered, u32::MAX, u32::MAX - 10000, 1_000_000),
                Err(Error::Hardware)
            );
        }
    }
    #[test]
    fn new_owner_requires_its_own_measurement() {
        let mut first = Cache::new();
        first
            .record(key(), u32::MAX, u32::MAX - 10000, 1_000_000)
            .unwrap();
        assert_eq!(Cache::new().lookup(key()), Ok(None));
    }
}
