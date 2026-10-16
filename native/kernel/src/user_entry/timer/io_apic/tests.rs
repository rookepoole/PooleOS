use super::*;
struct Fake {
    regs: [u32; 256],
    writes: usize,
    fail: usize,
}
impl Fake {
    fn new() -> Self {
        let mut s = Self {
            regs: [0; 256],
            writes: 0,
            fail: usize::MAX,
        };
        s.regs[1] = 0x170020;
        for n in 0..24 {
            s.regs[0x10 + 2 * n] = MASK;
        }
        s
    }
}
impl Hardware for Fake {
    fn read(&self, i: u8) -> Result<u32, Error> {
        Ok(self.regs[i as usize])
    }
    fn write(&mut self, i: u8, v: u32) -> Result<(), Error> {
        self.regs[i as usize] = v;
        self.writes += 1;
        if self.writes == self.fail {
            Err(Error::Hardware)
        } else {
            Ok(())
        }
    }
}
fn description() -> IoApic {
    IoApic {
        id: 0,
        physical_address: 0xfec00000,
        global_interrupt_base: 0,
    }
}
#[test]
fn exact_edge_route_and_original_registers_are_restored() {
    for destination in [0, 1, 127, 254] {
        let mut h = Fake::new();
        let original = h.regs;
        let mut l = Lease::prepare(&h, description(), destination, u32::MAX, 0).unwrap();
        assert_eq!(l.gsi(), 23);
        assert_eq!(h.writes, 0);
        l.arm(&mut h).unwrap();
        l.validate(&h).unwrap();
        assert_eq!(h.regs[0x3e], 65);
        assert_eq!(h.regs[0x3f], u32::from(destination) << 24);
        assert!(l.arm(&mut h).is_err());
        assert!(l.restore_after_drain(&mut h).is_err());
        l.stop(&mut h).unwrap();
        assert!(l.validate(&h).is_err());
        l.restore_after_drain(&mut h).unwrap();
        assert_eq!(h.regs, original);
    }
}
#[test]
fn every_after_effect_error_preserves_retryable_route_owner() {
    for fail in 1..=6 {
        let mut h = Fake::new();
        let original = h.regs;
        let mut l = Lease::prepare(&h, description(), 0, u32::MAX, 0).unwrap();
        h.fail = fail;
        assert!(
            l.arm(&mut h)
                .and_then(|()| l.stop(&mut h))
                .and_then(|()| l.restore_after_drain(&mut h))
                .is_err()
        );
        h.fail = usize::MAX;
        l.stop(&mut h).unwrap();
        l.restore_after_drain(&mut h).unwrap();
        assert_eq!(h.regs, original);
    }
}
#[test]
fn topology_capabilities_exclusions_and_foreign_routes_are_respected() {
    let mut h = Fake::new();
    assert_eq!(
        Lease::prepare(&h, description(), 0, u32::MAX, 1 << 23)
            .unwrap()
            .gsi(),
        22
    );
    assert!(Lease::prepare(&h, description(), 0, 0xffff, 0).is_err());
    assert!(Lease::prepare(&h, description(), 255, u32::MAX, 0).is_err());
    for bad in [
        IoApic {
            id: 16,
            ..description()
        },
        IoApic {
            global_interrupt_base: 32,
            ..description()
        },
    ] {
        assert!(Lease::prepare(&h, bad, 0, u32::MAX, 0).is_err());
    }
    for version in [0, 0x170010, 0x170120, 0x780020, 0xff170020] {
        h.regs[1] = version;
        assert!(Lease::prepare(&h, description(), 0, u32::MAX, 0).is_err());
    }
    h = Fake::new();
    for pin in 16..24 {
        h.regs[0x10 + 2 * pin] |= 66;
    }
    assert!(Lease::prepare(&h, description(), 0, u32::MAX, 0).is_err());
    assert_eq!(h.writes, 0);
}

#[test]
fn reset_identity_initialization_and_every_after_effect_failure_restore() {
    let description = IoApic {
        id: 1,
        ..description()
    };
    for fail in 1..=9 {
        let mut h = Fake::new();
        let original = h.regs;
        let mut l = Lease::prepare(&h, description, 0, u32::MAX, 0).unwrap();
        h.fail = fail;
        let result = l
            .arm(&mut h)
            .and_then(|()| {
                l.validate(&h)?;
                assert_eq!(h.regs[0], 1 << 24);
                l.stop(&mut h)
            })
            .and_then(|()| l.restore_after_drain(&mut h));
        assert_eq!(result.is_ok(), fail == 9);
        h.fail = usize::MAX;
        l.stop(&mut h).unwrap();
        l.restore_after_drain(&mut h).unwrap();
        assert_eq!(h.regs, original);
    }
}

#[test]
fn identity_initialization_rejects_active_controller_and_late_mutations() {
    let description = IoApic {
        id: 1,
        ..description()
    };
    for pin in 0..24 {
        let mut h = Fake::new();
        h.regs[0x10 + 2 * pin] |= 67;
        assert!(Lease::prepare(&h, description, 0, u32::MAX, 0).is_err());
        h.regs[0x10 + 2 * pin] = MASK;
        let mut l = Lease::prepare(&h, description, 0, u32::MAX, 0).unwrap();
        h.regs[0x11 + 2 * pin] = 1 << 24;
        assert!(l.arm(&mut h).is_err());
        assert_eq!(h.writes, 0);
    }
    for id in [1, 2 << 24, 1 << 28, u32::MAX] {
        let mut h = Fake::new();
        h.regs[0] = id;
        assert!(Lease::prepare(&h, description, 0, u32::MAX, 0).is_err());
    }
    let mut h = Fake::new();
    let mut l = Lease::prepare(&h, description, 0, u32::MAX, 0).unwrap();
    h.regs[1] ^= 1;
    assert!(l.arm(&mut h).is_err());
    assert_eq!(h.writes, 0);
}
#[test]
fn route_change_before_arm_or_during_ownership_fails_closed() {
    let mut h = Fake::new();
    let mut l = Lease::prepare(&h, description(), 0, u32::MAX, 0).unwrap();
    h.regs[0x3e] |= 67;
    assert!(l.arm(&mut h).is_err());
    assert_eq!(h.writes, 0);
    h.regs[0x3e] = MASK;
    l.arm(&mut h).unwrap();
    for (index, bit) in [(0x3e, 1), (0x3e, 1 << 15), (0x3e, 1 << 14), (0x3f, 1 << 24)] {
        h.regs[index] ^= bit;
        assert!(l.validate(&h).is_err());
        h.regs[index] ^= bit;
    }
    l.stop(&mut h).unwrap();
    l.restore_after_drain(&mut h).unwrap();
}
