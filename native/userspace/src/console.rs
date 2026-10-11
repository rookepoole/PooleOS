//! Polled 16550 policy and one-byte echo queue, entirely in user space.
#![forbid(unsafe_code)]

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum Error {
    Transport,
    Hardware,
}

pub trait Registers {
    fn read(&mut self, offset: u8) -> Result<u8, Error>;
    fn write(&mut self, offset: u8, value: u8) -> Result<(), Error>;
}

pub fn configure(port: &mut impl Registers) -> Result<(), Error> {
    // DLAB must be clear before disabling interrupts, then set only for divisor.
    for (offset, value) in [
        (3, 3),
        (1, 0),
        (3, 0x83),
        (0, 1),
        (1, 0),
        (3, 3),
        (2, 7),
        (4, 3),
        (7, 0x5a),
    ] {
        port.write(offset, value)?;
    }
    if port.read(7)? != 0x5a {
        return Err(Error::Hardware);
    }
    port.write(7, 0xa5)?;
    if port.read(7)? != 0xa5 || port.read(3)? != 3 || port.read(1)? != 0 {
        return Err(Error::Hardware);
    }
    Ok(())
}

fn status(port: &mut impl Registers) -> Result<u8, Error> {
    let value = port.read(5)?;
    if value & 0x9e != 0 {
        return Err(Error::Hardware);
    }
    Ok(value)
}

/// A busy transmitter never spins in the kernel. Caller owns retry policy.
pub fn send(port: &mut impl Registers, byte: u8) -> Result<bool, Error> {
    if status(port)? & 0x20 == 0 {
        return Ok(false);
    }
    port.write(0, byte)?;
    Ok(true)
}

#[derive(Default)]
pub struct Echo {
    pending: Option<u8>,
    closing: bool,
}
impl Echo {
    pub const fn new() -> Self {
        Self {
            pending: None,
            closing: false,
        }
    }
    /// One bounded poll; Ctrl-D closes after queued output and hardware drain.
    /// Backpressure never overwrites the pending byte or consumes another input.
    pub fn poll(&mut self, port: &mut impl Registers) -> Result<bool, Error> {
        let state = status(port)?;
        if let Some(byte) = self.pending {
            if state & 0x20 != 0 {
                port.write(0, byte)?;
                self.pending = None;
            }
        } else if self.closing {
            return Ok(state & 0x40 != 0);
        } else if state & 1 != 0 {
            let byte = port.read(0)?;
            if byte == 4 {
                self.closing = true;
            } else {
                self.pending = Some(byte);
            }
        }
        Ok(false)
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::{collections::VecDeque, vec::Vec};
    struct Device {
        registers: [u8; 8],
        writes: Vec<(u8, u8)>,
        reads: Vec<u8>,
        rx: VecDeque<u8>,
        fail: bool,
    }
    impl Device {
        fn new() -> Self {
            Self {
                registers: [0; 8],
                writes: Vec::new(),
                reads: Vec::new(),
                rx: VecDeque::new(),
                fail: false,
            }
        }
    }
    impl Registers for Device {
        fn read(&mut self, offset: u8) -> Result<u8, Error> {
            if self.fail {
                return Err(Error::Transport);
            }
            self.reads.push(offset);
            if offset == 0 {
                self.rx.pop_front().ok_or(Error::Hardware)
            } else {
                Ok(self.registers[usize::from(offset)])
            }
        }
        fn write(&mut self, offset: u8, value: u8) -> Result<(), Error> {
            if self.fail {
                return Err(Error::Transport);
            }
            self.writes.push((offset, value));
            self.registers[usize::from(offset)] = value;
            Ok(())
        }
    }
    #[test]
    fn console_configuration_is_polled_and_dlab_ordered() {
        let mut d = Device::new();
        configure(&mut d).unwrap();
        assert_eq!(
            d.writes,
            [
                (3, 3),
                (1, 0),
                (3, 131),
                (0, 1),
                (1, 0),
                (3, 3),
                (2, 7),
                (4, 3),
                (7, 90),
                (7, 165)
            ]
        );
        assert_eq!(d.reads, [7, 7, 3, 1]);
    }
    #[test]
    fn console_backpressure_preserves_byte_and_does_not_consume_next_input() {
        let mut d = Device::new();
        let mut echo = Echo::new();
        d.rx.extend([b'a', b'b']);
        d.registers[5] = 1;
        assert!(!echo.poll(&mut d).unwrap());
        for _ in 0..20 {
            assert!(!echo.poll(&mut d).unwrap());
        }
        assert_eq!(d.rx.len(), 1);
        assert!(d.writes.is_empty());
        d.registers[5] = 0x21;
        assert!(!echo.poll(&mut d).unwrap());
        assert_eq!(d.writes, [(0, b'a')]);
        assert!(!echo.poll(&mut d).unwrap());
        assert!(!echo.poll(&mut d).unwrap());
        assert_eq!(d.writes, [(0, b'a'), (0, b'b')]);
    }
    #[test]
    fn console_eot_waits_for_hardware_drain_and_never_echoes_control_byte() {
        let mut d = Device::new();
        let mut echo = Echo::new();
        d.rx.push_back(4);
        d.registers[5] = 0x21;
        assert!(!echo.poll(&mut d).unwrap());
        assert!(!echo.poll(&mut d).unwrap());
        d.registers[5] = 0x60;
        assert!(echo.poll(&mut d).unwrap());
        assert!(d.writes.is_empty());
        assert_eq!(d.reads.iter().filter(|&&r| r == 0).count(), 1);
    }
    #[test]
    fn console_errors_do_not_silently_echo_corrupt_or_lost_bytes() {
        for error in [2, 4, 8, 16, 128, 255] {
            let mut d = Device::new();
            d.registers[5] = error;
            assert_eq!(Echo::new().poll(&mut d), Err(Error::Hardware));
            assert_eq!(send(&mut d, b'x'), Err(Error::Hardware));
            assert!(d.writes.is_empty());
        }
        let mut d = Device::new();
        d.fail = true;
        assert_eq!(configure(&mut d), Err(Error::Transport));
        assert_eq!(Echo::new().poll(&mut d), Err(Error::Transport));
    }
    #[test]
    fn console_send_is_bounded_and_busy_transmitter_has_no_write() {
        let mut d = Device::new();
        assert!(!send(&mut d, 255).unwrap());
        assert_eq!(d.reads, [5]);
        assert!(d.writes.is_empty());
        d.registers[5] = 0x20;
        assert!(send(&mut d, 255).unwrap());
        assert_eq!(d.writes, [(0, 255)]);
    }
    #[test]
    fn console_startup_requires_exact_role_count_layout_and_nonzero_handle() {
        let mut b = std::vec![0; 128];
        b[..8].copy_from_slice(b"PSTART1\0");
        for (at, v) in [(8, 128u64), (16, 2), (32, 96), (40, 104)] {
            b[at..at + 8].copy_from_slice(&v.to_le_bytes());
        }
        b[96..104].copy_from_slice(b"console\0");
        b[104..120].copy_from_slice(b"0000000100040001");
        assert_eq!(crate::startup::console(&b, 1), Ok(0x100040001));
        for n in 0..b.len() {
            assert!(crate::startup::console(&b[..n], 1).is_err());
        }
        for at in [0, 8, 16, 24, 32, 40, 48, 56, 88, 96, 120, 127] {
            let mut bad = b.clone();
            bad[at] ^= 1;
            assert!(crate::startup::console(&bad, 1).is_err(), "{at}");
        }
        assert!(crate::startup::console(&b, 0).is_err());
        b[104..120].fill(b'0');
        assert!(crate::startup::console(&b, 1).is_err());
    }
}
