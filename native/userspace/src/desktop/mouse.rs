//! Translated three-byte PS/2 stream policy. No device access in user space.
#![forbid(unsafe_code)]

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct Motion {
    pub dx: i16,
    pub dy: i16,
    pub buttons: u8,
}
pub struct Mouse {
    bytes: [u8; 3],
    used: usize,
}
impl Mouse {
    pub const fn new() -> Self {
        Self {
            bytes: [0; 3],
            used: 0,
        }
    }
    #[inline]
    pub fn reset(&mut self) {
        self.used = 0;
    }
    #[inline]
    pub fn feed(&mut self, byte: u8) -> Option<Motion> {
        if self.used == 0 && byte & 8 == 0 {
            return None;
        }
        *self.bytes.get_mut(self.used)? = byte;
        self.used += 1;
        if self.used != 3 {
            return None;
        }
        self.used = 0;
        let flags = self.bytes[0];
        if flags & 0xc0 != 0 {
            return Some(Motion {
                dx: 0,
                dy: 0,
                buttons: 0,
            });
        }
        let dx = i16::from(self.bytes[1]) - if flags & 0x10 != 0 { 256 } else { 0 };
        let dy = i16::from(self.bytes[2]) - if flags & 0x20 != 0 { 256 } else { 0 };
        Some(Motion {
            dx,
            dy: -dy,
            buttons: flags & 7,
        })
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn packet_sign_bits_not_byte_sign_and_screen_y_are_authoritative() {
        for (packet, expected) in [
            ([8, 200, 1], (200, -1, 0)),
            ([0x39, 0xff, 0xfe], (-1, 2, 1)),
            ([0x1a, 0, 0], (-256, 0, 2)),
        ] {
            let mut m = Mouse::new();
            assert_eq!(m.feed(packet[0]), None);
            assert_eq!(m.feed(packet[1]), None);
            assert_eq!(
                m.feed(packet[2]),
                Some(Motion {
                    dx: expected.0,
                    dy: expected.1,
                    buttons: expected.2
                })
            );
        }
    }
    #[test]
    fn invalid_header_overflow_and_transport_reset_cannot_leave_drag_held() {
        let mut m = Mouse::new();
        assert_eq!(m.feed(0), None);
        assert_eq!(m.feed(0xc9), None);
        assert_eq!(m.feed(255), None);
        assert_eq!(
            m.feed(255),
            Some(Motion {
                dx: 0,
                dy: 0,
                buttons: 0
            })
        );
        m.feed(9);
        m.reset();
        m.feed(8);
        m.feed(4);
        assert_eq!(
            m.feed(5),
            Some(Motion {
                dx: 4,
                dy: -5,
                buttons: 0
            })
        );
    }
}
