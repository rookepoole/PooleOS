use super::*;

struct Fake {
    regs: [u64; 35],
    writes: usize,
    fail: usize,
    lose_on_enable: bool,
}
impl Fake {
    fn new() -> Self {
        let mut s = Self {
            regs: [0; 35],
            writes: 0,
            fail: usize::MAX,
            lose_on_enable: false,
        };
        s.regs[0] = (10_000_000 << 32) | (1 << 13);
        s.regs[2] = 1;
        s.regs[0x100 / 8] = FSB_CAP | SIZE_CAP | (1 << 4);
        s.regs[0x108 / 8] = u64::MAX;
        s
    }
}
impl Hardware for Fake {
    fn read(&self, offset: u64) -> Result<u64, Error> {
        Ok(self.regs[offset as usize / 8])
    }
    fn write(&mut self, offset: u64, value: u64) -> Result<(), Error> {
        self.regs[offset as usize / 8] = value;
        self.writes += 1;
        if self.lose_on_enable && offset == CONFIG && value & ENABLE != 0 {
            self.regs[0xf0 / 8] = self.regs[COMPARE as usize / 8];
        }
        if self.writes == self.fail {
            Err(Error::Hardware)
        } else {
            Ok(())
        }
    }
}

#[test]
fn independent_deadline_routes_only_to_owned_physical_bsp_and_restores() {
    for id in [0, 1, 127, 254] {
        let mut h = Fake::new();
        let original = h.regs;
        let mut owner = Lease::prepare(&h, id).unwrap();
        owner.arm(&mut h, 0).unwrap();
        assert_eq!(
            h.regs[ROUTE as usize / 8],
            ((0xfee0_0000 | (u64::from(id) << 12)) << 32) | 65
        );
        assert!(owner.expired(&h, owner.deadline - 1).is_err());
        assert_eq!(owner.expired(&h, owner.deadline).unwrap(), owner.ticks);
        assert!(owner.arm(&mut h, 0).is_err());
        assert!(owner.restore_after_drain(&mut h).is_err());
        owner.stop(&mut h).unwrap();
        assert!(owner.expired(&h, owner.deadline).is_err());
        owner.restore_after_drain(&mut h).unwrap();
        assert_eq!(h.regs, original);
        assert!(owner.arm(&mut h, 0).is_err());
    }
}
#[test]
fn unsupported_or_already_owned_hardware_is_not_reprogrammed() {
    for case in 0..8 {
        let mut h = Fake::new();
        match case {
            0 => h.regs[0] &= !(1 << 13),
            1 => h.regs[0] = 1 << 13,
            2 => h.regs[2] = 3,
            3 => h.regs[CONFIG as usize / 8] &= !FSB_CAP,
            4 => h.regs[CONFIG as usize / 8] &= !SIZE_CAP,
            5 => h.regs[CONFIG as usize / 8] |= ENABLE,
            6 => h.regs[4] = 1,
            _ => (),
        }
        assert!(Lease::prepare(&h, if case == 7 { 255 } else { 0 }).is_err());
        assert_eq!(h.writes, 0);
    }
}
#[test]
fn every_after_effect_arm_stop_and_restore_error_retains_retryable_owner() {
    for fail in 1..=8 {
        let mut h = Fake::new();
        let original = h.regs;
        let mut owner = Lease::prepare(&h, 0).unwrap();
        h.fail = fail;
        let result = owner
            .arm(&mut h, 0)
            .and_then(|()| owner.stop(&mut h))
            .and_then(|()| owner.restore_after_drain(&mut h));
        assert!(result.is_err(), "{fail}");
        h.fail = usize::MAX;
        owner.stop(&mut h).unwrap();
        owner.restore_after_drain(&mut h).unwrap();
        assert_eq!(h.regs, original);
    }
}
#[test]
fn missed_deadline_overflow_regression_and_reconfigured_message_reject() {
    let mut h = Fake::new();
    let mut owner = Lease::prepare(&h, 0).unwrap();
    assert!(owner.arm(&mut h, u64::MAX).is_err());
    assert_eq!(h.writes, 0);
    owner.arm(&mut h, 0).unwrap();
    for offset in [0, CONFIG, COMPARE, ROUTE] {
        let index = offset as usize / 8;
        let saved = h.regs[index];
        h.regs[index] ^= if offset == 0 { 1 << 32 } else { 1 };
        assert!(owner.expired(&h, owner.deadline).is_err());
        h.regs[index] = saved;
    }
    assert!(owner.expired(&h, owner.deadline * 3).is_err());
    let mut h = Fake::new();
    let mut owner = Lease::prepare(&h, 0).unwrap();
    h.regs[0xf0 / 8] = owner.ticks;
    assert!(owner.arm(&mut h, 0).is_err());
    assert_eq!(h.regs[CONFIG as usize / 8] & ENABLE, 0);
    owner.stop(&mut h).unwrap();
    owner.restore_after_drain(&mut h).unwrap();
    let mut h = Fake::new();
    let original = h.regs;
    h.lose_on_enable = true;
    let mut owner = Lease::prepare(&h, 0).unwrap();
    assert!(owner.arm(&mut h, 0).is_err());
    assert_ne!(h.regs[CONFIG as usize / 8] & ENABLE, 0);
    assert!(owner.restore_after_drain(&mut h).is_err());
    owner.stop(&mut h).unwrap();
    owner.restore_after_drain(&mut h).unwrap();
    h.regs[0xf0 / 8] = original[0xf0 / 8];
    assert_eq!(h.regs, original);
}
