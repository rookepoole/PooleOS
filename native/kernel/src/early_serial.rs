//! Bounded fixed-UART loopback probe, independent of privileged port access.
#![forbid(unsafe_code)]

pub const READY_POLLS: usize = 4096;
const DATA_READY: u8 = 1;
const RECEIVE_ERRORS: u8 = 0x1e;
const SENTINEL: u8 = 0xae;

/// The platform adapter owns one fixed early UART; offsets are register indices.
pub trait Registers {
    fn read(&mut self, offset: u16) -> u8;
    fn write(&mut self, offset: u16, value: u8);
}

pub fn probe(io: &mut impl Registers) -> bool {
    for (offset, value) in [
        (1, 0x00),
        (3, 0x80),
        (0, 0x03),
        (1, 0x00),
        (3, 0x03),
        (2, 0xc7),
        (4, 0x1e),
        (0, SENTINEL),
    ] {
        io.write(offset, value);
    }
    let mut available = false;
    // Loopback reception can complete later than the transmit-register write.
    for _ in 0..READY_POLLS {
        let status = io.read(5);
        if status & RECEIVE_ERRORS != 0 {
            break;
        }
        if status & DATA_READY != 0 {
            available = io.read(0) == SENTINEL;
            break;
        }
        core::hint::spin_loop();
    }
    // Even a failed probe must leave the owned UART out of loopback mode.
    io.write(4, 0x0f);
    available
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::vec::Vec;

    struct Fake {
        ready_after: usize,
        status: u8,
        byte: u8,
        polls: usize,
        reads: usize,
        writes: Vec<(u16, u8)>,
    }
    impl Fake {
        fn new(ready_after: usize) -> Self {
            Self {
                ready_after,
                status: 0x61,
                byte: SENTINEL,
                polls: 0,
                reads: 0,
                writes: Vec::new(),
            }
        }
        fn restored(&self) {
            assert_eq!(
                self.writes,
                [
                    (1, 0),
                    (3, 0x80),
                    (0, 3),
                    (1, 0),
                    (3, 3),
                    (2, 0xc7),
                    (4, 0x1e),
                    (0, SENTINEL),
                    (4, 0x0f),
                ]
            );
        }
    }
    impl Registers for Fake {
        fn read(&mut self, offset: u16) -> u8 {
            match offset {
                5 => {
                    self.polls += 1;
                    if self.polls > self.ready_after {
                        self.status
                    } else {
                        0x60
                    }
                }
                0 => {
                    assert!(self.polls > self.ready_after);
                    self.reads += 1;
                    self.byte
                }
                _ => panic!("unexpected register read"),
            }
        }
        fn write(&mut self, offset: u16, value: u8) {
            self.writes.push((offset, value));
        }
    }

    #[test]
    fn immediate_loopback_requires_one_status_and_one_data_read() {
        let mut io = Fake::new(0);
        assert!(probe(&mut io));
        assert_eq!((io.polls, io.reads), (1, 1));
        io.restored();
    }
    #[test]
    fn delayed_loopback_does_not_read_data_before_ready() {
        let mut io = Fake::new(7);
        assert!(probe(&mut io));
        assert_eq!((io.polls, io.reads), (8, 1));
        io.restored();
    }
    #[test]
    fn last_allowed_poll_can_succeed() {
        let mut io = Fake::new(READY_POLLS - 1);
        assert!(probe(&mut io));
        assert_eq!((io.polls, io.reads), (READY_POLLS, 1));
        io.restored();
    }
    #[test]
    fn deadline_never_reads_unready_data_and_exits_loopback() {
        let mut io = Fake::new(READY_POLLS);
        assert!(!probe(&mut io));
        assert_eq!((io.polls, io.reads), (READY_POLLS, 0));
        io.restored();
    }
    #[test]
    fn floating_bus_is_not_presence() {
        let mut io = Fake::new(0);
        io.status = 0xff;
        assert!(!probe(&mut io));
        assert_eq!((io.polls, io.reads), (1, 0));
        io.restored();
    }
    #[test]
    fn receive_errors_reject_even_a_matching_sentinel() {
        for error in [2, 4, 8, 16] {
            let mut io = Fake::new(0);
            io.status |= error;
            assert!(!probe(&mut io));
            assert_eq!(io.reads, 0);
            io.restored();
        }
    }
    #[test]
    fn wrong_data_rejects_and_restores_normal_mode() {
        let mut io = Fake::new(0);
        io.byte = 0;
        assert!(!probe(&mut io));
        assert_eq!((io.polls, io.reads), (1, 1));
        io.restored();
    }
}
