//! US translated set-1 keyboard policy; modifiers and escape sequences stay in CPL3.
#[derive(Default)]
pub struct Keyboard {
    shifts: u8,
    controls: u8,
    caps: bool,
    caps_down: bool,
    extended: bool,
    pause: u8,
}
impl Keyboard {
    #[inline]
    pub const fn new() -> Self {
        Self {
            shifts: 0,
            controls: 0,
            caps: false,
            caps_down: false,
            extended: false,
            pause: 0,
        }
    }
    #[inline]
    pub fn feed(&mut self, code: u8) -> Option<u8> {
        if self.pause > 0 {
            self.pause -= 1;
            return None;
        }
        if code == 0xe1 {
            self.pause = 5;
            self.extended = false;
            return None;
        }
        if code == 0xe0 {
            self.extended = true;
            return None;
        }
        let extended = self.extended;
        self.extended = false;
        let up = code & 0x80 != 0;
        let key = code & 0x7f;
        if key == 0x1d {
            let bit = if extended { 2 } else { 1 };
            if up {
                self.controls &= !bit;
            } else {
                self.controls |= bit;
            }
            return None;
        }
        if !extended && matches!(key, 0x2a | 0x36) {
            let bit = if key == 0x2a { 1 } else { 2 };
            if up {
                self.shifts &= !bit;
            } else {
                self.shifts |= bit;
            }
            return None;
        }
        if !extended && key == 0x3a {
            if !up && !self.caps_down {
                self.caps = !self.caps;
            }
            self.caps_down = !up;
            return None;
        }
        if up || extended && !matches!(key, 0x1c | 0x35) {
            return None;
        }
        let byte = match key {
            0x02..=0x0d => b"1234567890-="[(key - 2) as usize],
            0x10..=0x1b => b"qwertyuiop[]"[(key - 0x10) as usize],
            0x1e..=0x29 => b"asdfghjkl;'`"[(key - 0x1e) as usize],
            0x2b => b'\\',
            0x2c..=0x35 => b"zxcvbnm,./"[(key - 0x2c) as usize],
            0x0e => 8,
            0x1c => b'\r',
            0x39 => b' ',
            _ => return None,
        };
        if self.controls != 0 {
            return match byte {
                b'a'..=b'z' => Some(byte.wrapping_sub(b'a').wrapping_add(1)),
                _ => None,
            };
        }
        if byte.is_ascii_lowercase() {
            return Some(if (self.shifts != 0) ^ self.caps {
                byte.to_ascii_uppercase()
            } else {
                byte
            });
        }
        if self.shifts != 0 {
            if let Some(i) = b"1234567890-=[];'`\\,./".iter().position(|b| *b == byte) {
                return Some(b"!@#$%^&*()_+{}:\"~|<>?"[i]);
            }
        }
        Some(byte)
    }
    #[inline]
    pub fn focus_reset(&mut self) {
        self.shifts = 0;
        self.controls = 0;
        self.extended = false;
        self.pause = 0;
    }
    #[inline]
    pub fn cancel_prefix(&mut self) {
        self.extended = false;
        self.pause = 0;
    }
}
#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn decodes_real_commands_and_releases_without_duplicate_input() {
        let mut k = Keyboard::new();
        let out: std::vec::Vec<_> = [0x26, 0xa6, 0x1f, 0x9f, 0x1c, 0x9c]
            .into_iter()
            .filter_map(|b| k.feed(b))
            .collect();
        assert_eq!(out, b"ls\r");
    }
    #[test]
    fn independent_shifts_caps_repeat_and_ctrl_are_scoped() {
        let mut k = Keyboard::new();
        k.feed(0x2a);
        k.feed(0x36);
        k.feed(0xaa);
        assert_eq!(k.feed(0x1e), Some(b'A'));
        k.feed(0xb6);
        assert_eq!(k.feed(0x1e), Some(b'a'));
        k.feed(0x3a);
        k.feed(0x3a);
        assert_eq!(k.feed(0x1e), Some(b'A'));
        k.feed(0x2a);
        assert_eq!(k.feed(0x1e), Some(b'a'));
        assert_eq!(k.feed(0x02), Some(b'!'));
        k.feed(0x1d);
        assert_eq!(k.feed(0x2e), Some(3));
        k.feed(0x9d);
        assert_eq!(k.feed(0x1e), Some(b'a'));
    }
    #[test]
    fn extended_fake_shifts_pause_mouse_like_codes_and_ack_do_not_type() {
        let mut k = Keyboard::new();
        for b in [
            0xe0, 0x2a, 0xe0, 0x37, 0xe0, 0xb7, 0xe0, 0xaa, 0xe1, 0x1d, 0x45, 0xe1, 0x9d, 0xc5,
            0xfa, 0xfe, 0,
        ] {
            assert_eq!(k.feed(b), None);
        }
        assert_eq!(k.feed(0x1e), Some(b'a'));
        assert_eq!(k.feed(0xe0), None);
        assert_eq!(k.feed(0x1c), Some(b'\r'));
    }
}
