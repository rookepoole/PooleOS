//! Bounded PS/2 policy: retain keys, process every transition, coalesce only paint.
#![forbid(unsafe_code)]
use super::{keyboard::Keyboard, mouse::Mouse, windows::Manager};
use crate::console::Error;

pub const CAPACITY: usize = 64;
pub const DRAIN_LIMIT: usize = 32;

#[derive(Clone, Copy, Debug, Default, Eq, PartialEq)]
pub struct Stats {
    pub received: u32,
    pub delivered: u32,
    pub dropped: u32,
    pub overruns: u32,
    pub resets: u32,
}

pub struct Input<'a> {
    keyboard: Keyboard,
    mouse: Mouse,
    keys: &'a mut [u8; CAPACITY],
    head: usize,
    len: usize,
    cancel: bool,
    discard_line: bool,
    stats: Stats,
}
pub trait Device {
    fn next(&mut self) -> Result<Option<u64>, Error>;
}
pub struct Update {
    pub old_pointer: (u16, u16),
    pub pointer_changed: bool,
    pub scene_changed: bool,
}
impl<'a> Input<'a> {
    #[inline(always)]
    pub fn new(keys: &'a mut [u8; CAPACITY]) -> Self {
        for key in keys.iter_mut() {
            *key = core::hint::black_box(0);
        }
        Self {
            keyboard: Keyboard::new(),
            mouse: Mouse::new(),
            keys,
            head: 0,
            len: 0,
            cancel: false,
            discard_line: false,
            stats: Stats::default(),
        }
    }
    pub fn stats(&self) -> Stats {
        self.stats
    }
    #[inline]
    pub fn ready(&self) -> bool {
        self.cancel || self.len != 0
    }
    #[inline]
    pub fn pop(&mut self) -> Option<u8> {
        if self.cancel {
            self.cancel = false;
            return Some(3);
        }
        if self.len == 0 {
            return None;
        }
        let key = *self.keys.get(self.head)?;
        self.head = self.head.wrapping_add(1) % CAPACITY;
        self.len -= 1;
        self.stats.delivered = self.stats.delivered.saturating_add(1);
        Some(key)
    }
    #[inline]
    pub fn clear_focus(&mut self) {
        self.stats.dropped = self.stats.dropped.saturating_add(self.len as u32);
        self.head = 0;
        self.len = 0;
    }
    #[inline]
    pub fn focus_boundary(
        &mut self,
        input: &mut super::application_input::Queues,
        old: Option<usize>,
    ) {
        if old == Some(0) && self.len != 0 {
            self.cancel = true;
            self.discard_line = true;
        }
        self.clear_focus();
        self.keyboard.focus_reset();
        input.focus_lost(old);
    }
    #[inline]
    fn key(&mut self, byte: u8, focused: bool) {
        self.stats.received = self.stats.received.saturating_add(1);
        if !focused || self.discard_line {
            self.stats.dropped = self.stats.dropped.saturating_add(1);
            if focused && matches!(byte, b'\r' | b'\n') {
                self.discard_line = false;
            }
            return;
        }
        if self.len == CAPACITY {
            self.clear_focus();
            self.stats.dropped = self.stats.dropped.saturating_add(1);
            self.stats.overruns = self.stats.overruns.saturating_add(1);
            self.cancel = true;
            self.discard_line = !matches!(byte, b'\r' | b'\n');
            return;
        }
        let at = self.head.wrapping_add(self.len) % CAPACITY;
        if let Some(out) = self.keys.get_mut(at) {
            *out = byte;
            self.len = self.len.saturating_add(1);
        }
    }
    #[inline(always)]
    pub fn poll(
        &mut self,
        manager: &mut Manager,
        device: &mut impl Device,
    ) -> Result<Update, Error> {
        self.poll_mode::<false>(manager, device, None)
    }
    #[inline(always)]
    pub fn poll_mode<const APPS: bool>(
        &mut self,
        manager: &mut Manager,
        device: &mut impl Device,
        mut apps: Option<&mut super::application_input::Queues>,
    ) -> Result<Update, Error> {
        if APPS && apps.is_none() {
            return Err(Error::Transport);
        }
        let old_pointer = (manager.x, manager.y);
        let windows = manager.windows;
        let focus = manager.focus;
        let visible = manager.visible;
        let order = manager.order;
        for _ in 0..DRAIN_LIMIT {
            let Some(value) = device.next()? else {
                break;
            };
            match value {
                0..=255 => {
                    if APPS
                        && !apps
                            .as_mut()
                            .ok_or(Error::Transport)?
                            .fence
                            .feed(value as u8)
                    {
                        self.keyboard.cancel_prefix();
                        continue;
                    }
                    if let Some(key) = self.keyboard.feed(value as u8) {
                        self.key(key, manager.focus == Some(0) && manager.visible[0]);
                        if APPS {
                            if let Some(i) = manager.focus.filter(|&i| {
                                i > 0 && manager.visible.get(i).copied().unwrap_or(false)
                            }) {
                                apps.as_mut().ok_or(Error::Transport)?.push(i - 1, key);
                            }
                        }
                    }
                }
                256..=511 => {
                    if let Some(motion) = self.mouse.feed((value - 256) as u8) {
                        let old_focus = manager.focus;
                        manager.motion(motion);
                        if old_focus != manager.focus {
                            if APPS {
                                self.focus_boundary(
                                    apps.as_mut().ok_or(Error::Transport)?,
                                    old_focus,
                                );
                            } else {
                                self.clear_focus();
                            }
                        }
                    }
                }
                512 => {
                    self.keyboard = Keyboard::new();
                    self.mouse.reset();
                    manager.reset_input();
                    self.clear_focus();
                    self.cancel = true;
                    self.discard_line = true;
                    self.stats.resets = self.stats.resets.saturating_add(1);
                    if APPS {
                        apps.as_mut().ok_or(Error::Transport)?.reset();
                    }
                }
                _ => return Err(Error::Transport),
            }
        }
        Ok(Update {
            old_pointer,
            pointer_changed: old_pointer != (manager.x, manager.y),
            scene_changed: windows != manager.windows
                || focus != manager.focus
                || visible != manager.visible
                || order
                    .iter()
                    .zip(manager.order.iter())
                    .any(|(&a, &b)| core::hint::black_box(a) != b),
        })
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::{collections::VecDeque, vec::Vec};
    struct Fake {
        bytes: VecDeque<u64>,
        polls: usize,
    }
    impl Device for Fake {
        fn next(&mut self) -> Result<Option<u64>, Error> {
            self.polls += 1;
            Ok(self.bytes.pop_front())
        }
    }
    fn feed(input: &mut Input, manager: &mut Manager, bytes: &[u64]) -> Update {
        let mut device = Fake {
            bytes: bytes.iter().copied().collect(),
            polls: 0,
        };
        let result = input.poll(manager, &mut device).unwrap();
        assert!(device.polls <= DRAIN_LIMIT);
        result
    }
    #[test]
    fn fifo_wraps_without_replacing_unread_keys() {
        let mut storage = [0; CAPACITY];
        let mut input = Input::new(&mut storage);
        for round in 0..8 {
            for n in 0..40 {
                input.key(b' ' + ((round + n) % 80) as u8, true);
            }
            for n in 0..40 {
                assert_eq!(input.pop(), Some(b' ' + ((round + n) % 80) as u8));
            }
            assert!(!input.ready());
        }
        assert_eq!(input.stats().received, 320);
        assert_eq!(input.stats().delivered, 320);
        assert_eq!(input.stats().dropped, 0);
    }
    #[test]
    fn overflow_cancels_instead_of_executing_a_truncated_command() {
        let mut storage = [0; CAPACITY];
        let mut input = Input::new(&mut storage);
        for _ in 0..CAPACITY {
            input.key(b'a', true);
        }
        input.key(b'b', true);
        assert_eq!(input.pop(), Some(3));
        input.key(b'c', true);
        input.key(b'\r', true);
        assert_eq!(input.pop(), None);
        for &b in b"ls\r" {
            input.key(b, true);
        }
        assert_eq!(
            (0..3).filter_map(|_| input.pop()).collect::<Vec<_>>(),
            b"ls\r"
        );
        assert_eq!(input.stats().overruns, 1);
        assert_eq!(input.stats().dropped, 67);
        assert_eq!(
            input.stats().received,
            input.stats().delivered + input.stats().dropped
        );
    }
    #[test]
    fn overflow_on_delimiter_and_focus_clear_preserve_pending_cancel() {
        let mut storage = [0; CAPACITY];
        let mut input = Input::new(&mut storage);
        for _ in 0..CAPACITY {
            input.key(b'a', true);
        }
        input.key(b'\r', true);
        input.clear_focus();
        input.key(b'z', false);
        input.key(b'l', true);
        assert_eq!(input.pop(), Some(3));
        assert_eq!(input.pop(), Some(b'l'));
        assert_eq!(input.stats().dropped, 66);
    }
    #[test]
    fn raw_flood_is_bounded_and_keyboard_breaks_never_duplicate() {
        let mut storage = [0; CAPACITY];
        let mut input = Input::new(&mut storage);
        let mut manager = Manager::new(1280, 800).unwrap();
        let mut device = Fake {
            bytes: [0x1e, 0x9e].repeat(40).into(),
            polls: 0,
        };
        let update = input.poll(&mut manager, &mut device).unwrap();
        assert_eq!(device.polls, DRAIN_LIMIT);
        assert_eq!(device.bytes.len(), 48);
        assert!(!update.pointer_changed && !update.scene_changed);
        for _ in 0..16 {
            assert_eq!(input.pop(), Some(b'a'));
        }
        assert_eq!(input.pop(), None);
    }
    #[test]
    fn every_button_transition_is_processed_before_coalesced_paint() {
        let mut storage = [0; CAPACITY];
        let mut input = Input::new(&mut storage);
        let mut manager = Manager::new(1280, 800).unwrap();
        manager.show(1).unwrap();
        manager.focus = Some(0);
        manager.x = 1060;
        manager.y = 84;
        feed(&mut input, &mut manager, &[0x1e, 0x9e]);
        let update = feed(
            &mut input,
            &mut manager,
            &[265, 256, 256, 313, 216 + 256, 224 + 256, 264, 256, 256],
        );
        assert!(update.scene_changed && update.pointer_changed);
        assert_eq!((manager.windows[1].x, manager.windows[1].y), (920, 104));
        assert_eq!(manager.focus, Some(1));
        assert_eq!(input.pop(), None);
        assert_eq!(input.stats().dropped, 1);
        let before = manager.windows[1];
        feed(&mut input, &mut manager, &[264, 266, 256]);
        assert_eq!(manager.windows[1], before);
    }
    #[test]
    fn reset_clears_partial_packets_keys_modifiers_and_drag_capture() {
        let mut storage = [0; CAPACITY];
        let mut input = Input::new(&mut storage);
        let mut manager = Manager::new(1280, 800).unwrap();
        feed(&mut input, &mut manager, &[0x2a, 0x1e, 265, 512]);
        assert_eq!(input.pop(), Some(3));
        assert_eq!(input.pop(), None);
        feed(&mut input, &mut manager, &[0x1e, 0x1c, 0x1e]);
        assert_eq!(input.pop(), Some(b'a'));
        assert_eq!(input.pop(), None);
        assert_eq!(input.stats().resets, 1);
        assert_eq!(input.stats().dropped, 3);
        let mut bad = Fake {
            bytes: [513].into(),
            polls: 0,
        };
        assert!(input.poll(&mut manager, &mut bad).is_err());
    }

    #[test]
    fn real_device_focus_routes_app_keys_without_terminal_leak_or_held_shift() {
        use crate::desktop::{
            application_input::{INPUT, Queues, RESET},
            surfaces::{Frame, OPEN, Surfaces},
        };
        let mut storage = [0; CAPACITY];
        let mut input = Input::new(&mut storage);
        let mut cells = [0; 384];
        let mut surfaces = Surfaces::new(&mut cells);
        let a = surfaces.apply(4, 1, Frame::new(OPEN, 1, 0)).0.handle;
        let b = surfaces.apply(5, 1, Frame::new(OPEN, 1, 0)).0.handle;
        let mut queues = Queues::new();
        queues.sync(&surfaces);
        let mut manager = Manager::new(1280, 800).unwrap();
        manager.show(1).unwrap();
        manager.show(2).unwrap();
        manager.focus = Some(1);
        let mut device = Fake {
            bytes: [0x2a, 0x1e].into(),
            polls: 0,
        };
        input
            .poll_mode::<true>(&mut manager, &mut device, Some(&mut queues))
            .unwrap();
        assert_eq!(input.pop(), None);
        manager.x = 1060;
        manager.y = 304;
        device.bytes = [
            265, 256, 256, 264, 256, 256, 0x1e, 0x30, 0xb0, 0x9e, 0xaa, 0x1e, 0x9e,
        ]
        .into();
        device.polls = 0;
        input
            .poll_mode::<true>(&mut manager, &mut device, Some(&mut queues))
            .unwrap();
        assert_eq!(manager.focus, Some(2));
        assert!(device.polls <= DRAIN_LIMIT);
        assert_eq!(input.pop(), None);
        let (mut reply, index) = surfaces.input_request(5, 1, Frame::new(INPUT, 2, b));
        queues.drain(index.unwrap(), &surfaces, &mut reply);
        assert_eq!(&reply.data[..usize::from(reply.len)], b"ba");
        let (mut reply, index) = surfaces.input_request(4, 1, Frame::new(INPUT, 2, a));
        queues.drain(index.unwrap(), &surfaces, &mut reply);
        assert_eq!((reply.offset, reply.len), (RESET, 0));
    }

    #[test]
    fn input_profile_requires_queues_and_keeps_raw_drain_bound() {
        use crate::desktop::application_input::Queues;
        let mut storage = [0; CAPACITY];
        let mut input = Input::new(&mut storage);
        let mut manager = Manager::new(1280, 800).unwrap();
        let mut device = Fake {
            bytes: [0x1e, 0x9e].repeat(40).into(),
            polls: 0,
        };
        assert!(
            input
                .poll_mode::<true>(&mut manager, &mut device, None)
                .is_err()
        );
        assert_eq!(device.polls, 0);
        let mut queues = Queues::new();
        input
            .poll_mode::<true>(&mut manager, &mut device, Some(&mut queues))
            .unwrap();
        assert_eq!(device.polls, DRAIN_LIMIT);
        assert_eq!(device.bytes.len(), 48);
        for _ in 0..16 {
            assert_eq!(input.pop(), Some(b'a'));
        }
        assert_eq!(input.pop(), None);
    }

    #[test]
    fn terminal_unclaimed_keys_cancel_only_terminal_draft_on_focus_loss() {
        use crate::desktop::application_input::Queues;
        let mut storage = [0; CAPACITY];
        let mut input = Input::new(&mut storage);
        let mut queues = Queues::new();
        let mut manager = Manager::new(1280, 800).unwrap();
        manager.show(1).unwrap();
        manager.focus = Some(0);
        manager.x = 1060;
        manager.y = 84;
        let mut device = Fake {
            bytes: [0x1e, 0x9e, 265, 256, 256, 264, 256, 256].into(),
            polls: 0,
        };
        input
            .poll_mode::<true>(&mut manager, &mut device, Some(&mut queues))
            .unwrap();
        assert_eq!(manager.focus, Some(1));
        assert_eq!(input.pop(), Some(3));
        assert_eq!(input.pop(), None);
        input.key(b'z', false);
        input.key(b'x', true);
        input.key(b'\r', true);
        input.key(b'n', true);
        assert_eq!(input.pop(), Some(b'n'));
        assert_eq!(input.pop(), None);
    }
}
