//! Bounded fixed-UART probe and retained transmission, without port privileges.
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

pub const TRANSMIT_CAPACITY: usize = 1024;
const TRANSMIT_READY: u8 = 1 << 5;

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct TransmitStatus {
    pub available: bool,
    pub pending: usize,
    pub transmitted: u64,
    pub timeouts: u64,
    pub rejected: u64,
    pub saturated: bool,
}

/// One exclusive writer; no allocation, overwrite or retry after a stream gap.
pub struct Transmitter {
    bytes: [u8; TRANSMIT_CAPACITY],
    head: usize,
    status: TransmitStatus,
    blocked: bool,
}

impl Transmitter {
    pub const fn new(available: bool) -> Self {
        Self {
            bytes: [0; TRANSMIT_CAPACITY],
            head: 0,
            status: TransmitStatus {
                available,
                pending: 0,
                transmitted: 0,
                timeouts: 0,
                rejected: 0,
                saturated: false,
            },
            blocked: false,
        }
    }

    pub const fn status(&self) -> TransmitStatus {
        self.status
    }

    pub fn write_byte(&mut self, io: &mut impl Registers, byte: u8) {
        if !self.status.available || self.status.saturated {
            self.status.rejected = self.status.rejected.saturating_add(1);
            return;
        }
        if self.status.pending == TRANSMIT_CAPACITY {
            self.status.saturated = true;
            self.status.rejected = self.status.rejected.saturating_add(1);
            return;
        }
        let tail = (self.head + self.status.pending) % TRANSMIT_CAPACITY;
        self.bytes[tail] = byte;
        self.status.pending += 1;
        // Backlog appends do not multiply the polling allowance per byte.
        // A record boundary or an explicit scheduler drain retries delivery.
        if !self.blocked || byte == b'\n' {
            self.flush(io);
        }
    }

    /// At most READY_POLLS status reads total, regardless of backlog length.
    pub fn flush(&mut self, io: &mut impl Registers) {
        if !self.status.available || self.status.pending == 0 {
            return;
        }
        for _ in 0..READY_POLLS {
            let status = io.read(5);
            // A floating/disconnected bus is not permission to write.
            if status != 0xff && status & TRANSMIT_READY != 0 {
                io.write(0, self.bytes[self.head]);
                self.head = (self.head + 1) % TRANSMIT_CAPACITY;
                self.status.pending -= 1;
                self.status.transmitted = self.status.transmitted.saturating_add(1);
                if self.status.pending == 0 {
                    self.blocked = false;
                    return;
                }
            } else {
                core::hint::spin_loop();
            }
        }
        self.blocked = true;
        self.status.timeouts = self.status.timeouts.saturating_add(1);
    }
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

    #[test]
    fn transmit_recovers_ordered_bytes_after_one_bounded_busy_interval() {
        struct BusyThenReady {
            reads: usize,
            output: Vec<u8>,
        }
        impl Registers for BusyThenReady {
            fn read(&mut self, offset: u16) -> u8 {
                assert_eq!(offset, 5);
                self.reads += 1;
                if self.reads <= READY_POLLS { 0 } else { 0x20 }
            }
            fn write(&mut self, offset: u16, value: u8) {
                assert_eq!(offset, 0);
                assert!(self.reads > READY_POLLS);
                self.output.push(value);
            }
        }
        let mut io = BusyThenReady {
            reads: 0,
            output: Vec::new(),
        };
        let mut tx = Transmitter::new(true);
        tx.write_byte(&mut io, b'A');
        assert_eq!(io.reads, READY_POLLS);
        assert!(io.output.is_empty());
        tx.write_byte(&mut io, b'B');
        tx.write_byte(&mut io, b'\n');
        assert_eq!(io.output, b"AB\n");
    }

    struct TxIo {
        reads: usize,
        busy: usize,
        status: u8,
        output: Vec<u8>,
        ready: bool,
    }
    impl TxIo {
        fn new(busy: usize) -> Self {
            Self {
                reads: 0,
                busy,
                status: 0x20,
                output: Vec::new(),
                ready: false,
            }
        }
    }
    impl Registers for TxIo {
        fn read(&mut self, offset: u16) -> u8 {
            assert_eq!(offset, 5);
            self.reads += 1;
            self.ready = self.reads > self.busy && self.status != 0xff && self.status & 0x20 != 0;
            if self.reads > self.busy {
                self.status
            } else {
                0
            }
        }
        fn write(&mut self, offset: u16, value: u8) {
            assert_eq!(offset, 0);
            assert!(self.ready, "unready write");
            self.ready = false;
            self.output.push(value);
        }
    }

    #[test]
    fn healthy_transmission_costs_one_status_read_per_byte() {
        let mut io = TxIo::new(0);
        let mut tx = Transmitter::new(true);
        for byte in b"one\r\ntwo\r\n" {
            tx.write_byte(&mut io, *byte);
        }
        assert_eq!(io.output, b"one\r\ntwo\r\n");
        assert_eq!(io.reads, io.output.len());
        assert_eq!(tx.status().pending, 0);
        assert_eq!(tx.status().timeouts, 0);
    }

    #[test]
    fn absent_device_never_touches_registers() {
        let mut io = TxIo::new(0);
        let mut tx = Transmitter::new(false);
        for byte in b"absent\n" {
            tx.write_byte(&mut io, *byte);
        }
        tx.flush(&mut io);
        assert_eq!(io.reads, 0);
        assert!(io.output.is_empty());
        assert_eq!(tx.status().rejected, 7);
        assert!(!tx.status().saturated);
    }

    #[test]
    fn ready_on_last_poll_succeeds_without_timeout() {
        let mut io = TxIo::new(READY_POLLS - 1);
        let mut tx = Transmitter::new(true);
        tx.write_byte(&mut io, b'x');
        assert_eq!(io.reads, READY_POLLS);
        assert_eq!(io.output, b"x");
        assert_eq!(tx.status().timeouts, 0);
    }

    #[test]
    fn backlog_appends_do_not_spin_again_until_boundary_or_explicit_flush() {
        let mut io = TxIo::new(usize::MAX);
        let mut tx = Transmitter::new(true);
        for _ in 0..100 {
            tx.write_byte(&mut io, b'x');
        }
        assert_eq!(io.reads, READY_POLLS);
        tx.write_byte(&mut io, b'\n');
        assert_eq!(io.reads, READY_POLLS * 2);
        tx.flush(&mut io);
        assert_eq!(io.reads, READY_POLLS * 3);
        assert_eq!(tx.status().pending, 101);
        assert_eq!(tx.status().timeouts, 3);
        assert!(io.output.is_empty());
    }

    #[test]
    fn one_drain_budget_includes_all_backlog_bytes() {
        let mut io = TxIo::new(usize::MAX);
        let mut tx = Transmitter::new(true);
        for _ in 0..100 {
            tx.write_byte(&mut io, b'x');
        }
        io.busy = io.reads + READY_POLLS - 2;
        tx.flush(&mut io);
        assert_eq!(io.reads, READY_POLLS * 2);
        assert_eq!(io.output, b"xx");
        assert_eq!(tx.status().pending, 98);
        tx.flush(&mut io);
        assert_eq!(io.reads, READY_POLLS * 2 + 98);
        assert_eq!(tx.status().transmitted, 100);
        assert_eq!(tx.status().pending, 0);
    }

    #[test]
    fn saturation_is_sticky_and_never_manufactures_a_record_after_loss() {
        let mut io = TxIo::new(usize::MAX);
        let mut tx = Transmitter::new(true);
        for _ in 0..TRANSMIT_CAPACITY {
            tx.write_byte(&mut io, b'x');
        }
        assert!(!tx.status().saturated);
        tx.write_byte(&mut io, b'!');
        assert!(tx.status().saturated);
        assert_eq!(tx.status().rejected, 1);
        io.busy = 0;
        tx.flush(&mut io);
        assert_eq!(io.output, std::vec![b'x'; TRANSMIT_CAPACITY]);
        for byte in b"POOLEOS:FALSE-PASS\n" {
            tx.write_byte(&mut io, *byte);
        }
        tx.flush(&mut io);
        assert_eq!(io.output.len(), TRANSMIT_CAPACITY);
        assert_eq!(
            tx.status().rejected,
            1 + b"POOLEOS:FALSE-PASS\n".len() as u64
        );
        assert!(tx.status().saturated);
    }

    #[test]
    fn wrapped_fifo_preserves_every_byte_across_repeated_busy_intervals() {
        let mut io = TxIo::new(0);
        let mut tx = Transmitter::new(true);
        let mut expected = Vec::new();
        for round in 0..40 {
            io.busy = io.reads + READY_POLLS;
            for i in 0..137 {
                let byte = 32 + ((i + round) % 90) as u8;
                expected.push(byte);
                tx.write_byte(&mut io, byte);
            }
            tx.flush(&mut io);
            assert_eq!(io.output, expected);
            assert_eq!(tx.status().pending, 0);
        }
        assert_eq!(tx.status().timeouts, 40);
        assert_eq!(tx.status().rejected, 0);
    }

    #[test]
    fn empty_flush_has_no_io_and_floating_bus_cannot_accept_a_byte() {
        let mut io = TxIo::new(0);
        let mut tx = Transmitter::new(true);
        tx.flush(&mut io);
        assert_eq!(io.reads, 0);
        io.status = 0xff;
        tx.write_byte(&mut io, b'x');
        assert_eq!(io.reads, READY_POLLS);
        assert!(io.output.is_empty());
        io.status = 0x20;
        tx.flush(&mut io);
        assert_eq!(io.output, b"x");
    }

    #[test]
    fn counters_saturate_instead_of_wrapping() {
        let mut io = TxIo::new(usize::MAX);
        let mut tx = Transmitter::new(true);
        tx.status.timeouts = u64::MAX;
        tx.write_byte(&mut io, b'x');
        assert_eq!(tx.status().timeouts, u64::MAX);
        tx.status.transmitted = u64::MAX;
        io.busy = 0;
        tx.flush(&mut io);
        assert_eq!(tx.status().transmitted, u64::MAX);
        tx.status.saturated = true;
        tx.status.rejected = u64::MAX;
        tx.write_byte(&mut io, b'y');
        assert_eq!(tx.status().rejected, u64::MAX);
    }

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
