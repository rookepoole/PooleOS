use super::*;

struct Fake {
    state: Snapshot,
    windows: u32,
    stops: u32,
    late: bool,
    missing: bool,
    fail_stop: bool,
    fail_read: bool,
    fail_window: bool,
    fail_after_delivery: bool,
}
impl Fake {
    fn new() -> Self {
        Self {
            state: Snapshot {
                irr: [0; 8],
                isr: [0; 8],
                tmr: [0; 8],
                lvt: u32::from(TIMER_VECTOR),
                initial: 12,
                current: 9,
                deliveries: 7,
                eois: 7,
            },
            windows: 0,
            stops: 0,
            late: false,
            missing: false,
            fail_stop: false,
            fail_read: false,
            fail_window: false,
            fail_after_delivery: false,
        }
    }
    fn pending(&mut self) {
        self.state.irr[usize::from(TIMER_VECTOR / 32)] |= 1 << (TIMER_VECTOR % 32);
    }
}
impl Hardware for Fake {
    fn stop(&mut self) -> Result<(), Error> {
        self.stops += 1;
        self.state.lvt |= MASK;
        self.state.initial = 0;
        self.state.current = 0;
        if self.fail_stop {
            Err(Error::Hardware)
        } else {
            Ok(())
        }
    }
    fn snapshot(&mut self) -> Result<Snapshot, Error> {
        if self.fail_read {
            Err(Error::Hardware)
        } else {
            Ok(self.state)
        }
    }
    fn window(&mut self) -> Result<(), Error> {
        self.windows += 1;
        if self.fail_window {
            return Err(Error::Hardware);
        }
        if self.late {
            self.pending();
            self.late = false;
        }
        if self.state.pending() && !self.missing {
            let bank = usize::from(TIMER_VECTOR / 32);
            let bit = 1 << (TIMER_VECTOR % 32);
            self.state.irr[bank] &= !bit;
            self.state.isr[bank] |= bit;
            self.state.validate(true)?;
            self.state.deliveries += 1;
            self.state.isr[bank] &= !bit;
            self.state.eois += 1;
            self.state.lvt &= !SENDING;
            if self.fail_after_delivery {
                return Err(Error::Hardware);
            }
        }
        Ok(())
    }
}

#[test]
fn idle_pending_and_late_delivery_shutdown_without_rearming() {
    for case in 0..3 {
        let mut h = Fake::new();
        if case == 1 {
            h.pending();
        }
        h.late = case == 2;
        assert_eq!(
            quiesce(&mut h),
            Ok(Receipt {
                windows: 1,
                deliveries: u32::from(case != 0)
            })
        );
        assert_eq!(h.stops, 1);
        assert_eq!(h.state.initial, 0);
        assert_eq!(h.state.current, 0);
        assert_eq!(h.state.irr, [0; 8]);
        assert_eq!(h.state.isr, [0; 8]);
    }
}
#[test]
fn foreign_pending_or_in_service_and_unowned_timer_isr_never_open_a_window() {
    for vector in 0..256 {
        for isr in [false, true] {
            if vector == usize::from(TIMER_VECTOR) && !isr {
                continue;
            }
            let mut h = Fake::new();
            let bank = if isr {
                &mut h.state.isr
            } else {
                &mut h.state.irr
            };
            bank[vector / 32] |= 1 << (vector % 32);
            assert_eq!(quiesce(&mut h), Err(Error::Hardware));
            assert_eq!(h.windows, 0);
            assert_eq!(h.state.eois, 7);
        }
    }
}
#[test]
fn missing_delivery_and_sending_status_are_bounded_and_retryable() {
    for sending in [false, true] {
        let mut h = Fake::new();
        if sending {
            h.state.lvt |= SENDING;
        } else {
            h.pending();
        }
        h.missing = true;
        assert_eq!(quiesce(&mut h), Err(Error::Hardware));
        assert_eq!(h.windows, WINDOW_LIMIT);
        assert!(h.state.pending());
        h.missing = false;
        // SENDING alone does not prove an ISR: materialize it before delivery.
        if sending {
            h.pending();
        }
        assert_eq!(quiesce(&mut h).unwrap().deliveries, 1);
    }
}
#[test]
fn after_effect_failures_keep_pending_or_completed_state_for_retry() {
    for case in 0..4 {
        let mut h = Fake::new();
        h.pending();
        h.fail_stop = case == 0;
        h.fail_read = case == 1;
        h.fail_window = case == 2;
        h.fail_after_delivery = case == 3;
        assert_eq!(quiesce(&mut h), Err(Error::Hardware));
        assert_eq!(h.state.initial, 0);
        assert_eq!(h.state.deliveries, h.state.eois);
        h.fail_stop = false;
        h.fail_read = false;
        h.fail_window = false;
        h.fail_after_delivery = false;
        assert_eq!(quiesce(&mut h).unwrap().deliveries, u32::from(case != 3));
        assert_eq!(h.state.deliveries, 8);
    }
}
#[test]
fn snapshot_rejects_unsafe_device_state_and_ambiguous_acknowledgement() {
    let mut h = Fake::new();
    h.stop().unwrap();
    for case in 0..7 {
        let mut s = h.state;
        match case {
            0 => s.lvt &= !MASK,
            1 => s.lvt |= 1 << 17,
            2 => s.initial = 1,
            3 => s.current = 1,
            4 => s.tmr[usize::from(TIMER_VECTOR / 32)] = 1 << (TIMER_VECTOR % 32),
            5 => s.deliveries += 1,
            _ => s.eois += 1,
        }
        assert_eq!(s.validate(false), Err(Error::Hardware));
    }
    assert_eq!(h.state.validate(true), Err(Error::Hardware));
}
