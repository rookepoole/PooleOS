use super::*;
use core::cell::Cell;

struct Device {
    registers: [u64; 512],
    operations: Cell<usize>,
    fail: Option<usize>,
    writes: std::vec::Vec<(u64, u64)>,
}
impl Device {
    fn new(config: u64) -> Self {
        let mut registers = [0; 512];
        registers[0] = (10_000_000 << 32) | (1 << 13) | (2 << 8) | 1;
        registers[2] = config;
        registers[0xf0 / 8] = 100;
        Self {
            registers,
            operations: Cell::new(0),
            fail: None,
            writes: std::vec::Vec::new(),
        }
    }
    fn step(&self) -> Result<(), Error> {
        let n = self.operations.get();
        self.operations.set(n + 1);
        if self.fail == Some(n) {
            Err(Error::Hardware)
        } else {
            Ok(())
        }
    }
    fn inject(&mut self, offset: usize) {
        self.fail = Some(self.operations.get() + offset);
    }
}
impl Hardware for Device {
    fn read(&self, offset: u64) -> Result<u64, Error> {
        self.step()?;
        Ok(self.registers[offset as usize / 8])
    }
    fn write(&mut self, offset: u64, value: u64) -> Result<(), Error> {
        // The hostile device reports failure after the register has changed.
        self.registers[offset as usize / 8] = value;
        self.writes.push((offset, value));
        self.step()
    }
}
fn running(config: u64) -> (Device, Lease) {
    let mut d = Device::new(config);
    let mut l = Lease::prepare(&d).unwrap();
    l.start(&mut d).unwrap();
    (d, l)
}

#[test]
fn continuous_epoch_counts_idle_and_preserves_original_register_bits() {
    for config in [0, 1, 0x5500, 0x5501] {
        let (mut d, mut l) = running(config);
        assert_eq!(l.sample(&d), Ok(0));
        for raw in [101, 101, 1000, 1_000_000] {
            d.registers[0xf0 / 8] = raw;
            assert_eq!(l.sample(&d), Ok((raw - 100) * 10));
        }
        assert_eq!(l.observation(), (100, 1_000_000, 10_000_000, 5));
        l.release(&mut d).unwrap();
        assert_eq!(d.writes, [(0x10, config | 1), (0x10, config)]);
        assert_eq!(d.registers[0xf0 / 8], 1_000_000);
        assert_eq!(l.sample(&d), Err(Error::State));
        assert_eq!(l.start(&mut d), Err(Error::State));
        assert_eq!(l.release(&mut d), Err(Error::State));
    }
}

#[test]
fn unsupported_width_period_revision_and_active_sources_reject_before_effects() {
    for (index, value) in [
        (0, 0),
        (0, (10_000_000 << 32) | 1),
        (0, (99_999 << 32) | (1 << 13) | 1),
        (0, (100_000_001 << 32) | (1 << 13) | 1),
        (0, (10_000_000 << 32) | (1 << 13)),
        (2, 2),
        (4, 1),
        (0x100 / 8, 4),
        (0x120 / 8, 4),
        (0x140 / 8, 4),
    ] {
        let mut d = Device::new(0);
        d.registers[index] = value;
        assert!(Lease::prepare(&d).is_err());
        assert!(d.writes.is_empty());
    }
    let mut d = Device::new(0);
    d.registers[0] |= 31 << 8;
    d.registers[(0x100 + 31 * 0x20) / 8] = 4;
    assert!(Lease::prepare(&d).is_err());
}

#[test]
fn every_prepare_and_start_hardware_failure_retains_recoverable_ownership() {
    let d = Device::new(0);
    Lease::prepare(&d).unwrap();
    for i in 0..d.operations.get() {
        let mut d = Device::new(0);
        d.inject(i);
        assert!(Lease::prepare(&d).is_err());
        assert!(d.writes.is_empty());
    }
    let mut d = Device::new(0);
    let mut l = Lease::prepare(&d).unwrap();
    let before = d.operations.get();
    l.start(&mut d).unwrap();
    for i in 0..d.operations.get() - before {
        let mut d = Device::new(0);
        let mut l = Lease::prepare(&d).unwrap();
        d.inject(i);
        assert!(l.start(&mut d).is_err());
        assert!(l.sample(&d).is_err());
        d.fail = None;
        l.release(&mut d).unwrap();
        assert_eq!(d.registers[2], 0);
        assert_eq!(d.registers[0xf0 / 8], 100);
    }
}

#[test]
fn every_sample_hardware_failure_poison_is_sticky_until_release() {
    for i in 0..3 {
        let (mut d, mut l) = running(0);
        d.inject(i);
        assert!(l.sample(&d).is_err());
        d.fail = None;
        d.registers[0xf0 / 8] += 100;
        assert_eq!(l.sample(&d), Err(Error::State));
        assert_eq!(l.observation().3, 0);
        l.release(&mut d).unwrap();
    }
}

#[test]
fn regression_overflow_and_configuration_change_never_fabricate_time() {
    for (index, value) in [
        (0xf0 / 8, 99),
        (0xf0 / 8, u64::MAX),
        (2, 0),
        (2, 3),
        (0, (20_000_000 << 32) | (1 << 13) | (2 << 8) | 1),
    ] {
        let (mut d, mut l) = running(0);
        d.registers[index] = value;
        assert!(l.sample(&d).is_err());
        assert_eq!(l.sample(&d), Err(Error::State));
        assert_eq!(l.observation(), (100, 100, 10_000_000, 0));
    }
    let (mut d, mut l) = running(0);
    l.samples = u64::MAX;
    d.registers[0xf0 / 8] += 1;
    assert_eq!(l.sample(&d), Err(Error::State));
    assert_eq!(l.last, 100);
}

#[test]
fn every_release_hardware_failure_keeps_owner_for_retry() {
    let (mut d, mut l) = running(0);
    let before = d.operations.get();
    l.release(&mut d).unwrap();
    for i in 0..d.operations.get() - before {
        let (mut d, mut l) = running(0);
        d.inject(i);
        assert!(l.release(&mut d).is_err());
        d.fail = None;
        assert_eq!(l.sample(&d), Err(Error::State));
        l.release(&mut d).unwrap();
        assert_eq!(d.registers[2], 0);
        assert_eq!(l.state, State::Restored);
    }
}

#[test]
fn active_child_blocks_release_without_stopping_counter() {
    for index in [4, 0x100 / 8, 0x120 / 8, 0x140 / 8] {
        let (mut d, mut l) = running(0);
        d.registers[index] = if index == 4 { 1 } else { 4 };
        assert!(l.release(&mut d).is_err());
        assert_eq!(d.writes.len(), 1);
        assert_eq!(d.registers[2], 1);
        d.registers[index] = 0;
        l.release(&mut d).unwrap();
    }
}

#[test]
fn absolute_conversion_retains_subnanosecond_fraction_and_checks_wrap() {
    let mut d = Device::new(0);
    d.registers[0] = (100_001 << 32) | (1 << 13) | 1;
    let mut l = Lease::prepare(&d).unwrap();
    l.start(&mut d).unwrap();
    for i in 0..100 {
        d.registers[0xf0 / 8] = 100 + i;
        assert_eq!(l.sample(&d), Ok(i * 100_001 / 1_000_000));
    }
    let mut d = Device::new(0);
    d.registers[0xf0 / 8] = u64::MAX - 1;
    let mut l = Lease::prepare(&d).unwrap();
    l.start(&mut d).unwrap();
    d.registers[0xf0 / 8] = u64::MAX;
    assert_eq!(l.sample(&d), Ok(10));
    d.registers[0xf0 / 8] = 0;
    assert!(l.sample(&d).is_err());
}
