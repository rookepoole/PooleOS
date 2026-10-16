//! Bounded emulated i8042 auxiliary transport. No device addresses from userspace.
#![forbid(unsafe_code)]
pub trait Ports {
    fn status(&mut self) -> u8;
    fn read(&mut self) -> u8;
    fn command(&mut self, value: u8);
    fn data(&mut self, value: u8);
}
const LIMIT: usize = 10000;
fn writable(p: &mut impl Ports) -> Result<(), ()> {
    for _ in 0..LIMIT {
        if p.status() & 2 == 0 {
            return Ok(());
        }
    }
    Err(())
}
fn aux(p: &mut impl Ports, byte: u8) -> Result<(), ()> {
    writable(p)?;
    p.command(0xd4);
    writable(p)?;
    p.data(byte);
    for _ in 0..LIMIT {
        let status = p.status();
        if status & 1 == 0 {
            continue;
        }
        let value = p.read();
        if status & 0xc0 != 0 {
            return Err(());
        }
        if status & 0x20 != 0 {
            return if value == 0xfa { Ok(()) } else { Err(()) };
        }
    }
    Err(())
}
/// Call once before admitting the console. Pending firmware input is discarded.
pub fn initialize(p: &mut impl Ports) -> Result<(), ()> {
    for _ in 0..64 {
        if p.status() & 1 == 0 {
            break;
        }
        let _ = p.read();
    }
    if p.status() & 1 != 0 {
        return Err(());
    }
    writable(p)?;
    p.command(0xa8);
    aux(p, 0xf6)?;
    aux(p, 0xf4)
}
/// 0..255 = keyboard, 256..511 = auxiliary byte, 512 = transport reset.
pub fn poll(p: &mut impl Ports) -> Option<u64> {
    let status = p.status();
    if status & 1 == 0 {
        return None;
    }
    let byte = p.read();
    Some(if status & 0xc0 != 0 {
        512
    } else {
        u64::from(byte) | if status & 0x20 != 0 { 256 } else { 0 }
    })
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::{collections::VecDeque, vec::Vec};
    struct Fake {
        input: VecDeque<(u8, u8)>,
        output: Vec<(bool, u8)>,
        busy: bool,
        ack: u8,
        reads: usize,
        polls: usize,
    }
    impl Fake {
        fn new() -> Self {
            Self {
                input: VecDeque::new(),
                output: Vec::new(),
                busy: false,
                ack: 0xfa,
                reads: 0,
                polls: 0,
            }
        }
    }
    impl Ports for Fake {
        fn status(&mut self) -> u8 {
            self.polls += 1;
            if self.busy {
                2
            } else {
                self.input.front().map_or(0, |v| v.0)
            }
        }
        fn read(&mut self) -> u8 {
            self.reads += 1;
            self.input.pop_front().unwrap().1
        }
        fn command(&mut self, v: u8) {
            self.output.push((true, v));
        }
        fn data(&mut self, v: u8) {
            self.output.push((false, v));
            self.input.push_back((0x21, self.ack));
        }
    }
    #[test]
    fn initialization_is_fixed_aux_only_and_acknowledged() {
        let mut p = Fake::new();
        initialize(&mut p).unwrap();
        assert_eq!(
            p.output,
            [
                (true, 0xa8),
                (true, 0xd4),
                (false, 0xf6),
                (true, 0xd4),
                (false, 0xf4)
            ]
        );
        assert_eq!(p.reads, 2);
    }
    #[test]
    fn busy_resend_and_flood_terminate_without_unbounded_retry() {
        let mut p = Fake::new();
        p.busy = true;
        assert!(initialize(&mut p).is_err());
        assert!(p.polls <= LIMIT + 2);
        assert!(p.output.is_empty());
        let mut p = Fake::new();
        p.ack = 0xfe;
        assert!(initialize(&mut p).is_err());
        assert_eq!(p.output.len(), 3);
        let mut p = Fake::new();
        p.input.extend(core::iter::repeat_n((1, 42), 65));
        assert!(initialize(&mut p).is_err());
        assert_eq!(p.reads, 64);
        assert!(p.output.is_empty());
    }
    #[test]
    fn polling_preserves_device_tags_and_errors_reset_both_decoders() {
        let mut p = Fake::new();
        p.input.extend([(1, 42), (0x21, 8), (0xe1, 255)]);
        assert_eq!(poll(&mut p), Some(42));
        assert_eq!(poll(&mut p), Some(264));
        assert_eq!(poll(&mut p), Some(512));
        assert_eq!(poll(&mut p), None);
        assert_eq!(p.reads, 3);
    }
}
