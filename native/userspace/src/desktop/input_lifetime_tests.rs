use super::*;
use crate::desktop::application_input::Queues;
use std::collections::VecDeque;

struct Stream {
    bytes: VecDeque<u64>,
    polls: usize,
}
impl Device for Stream {
    fn next(&mut self) -> Result<Option<u64>, Error> {
        self.polls += 1;
        Ok(self.bytes.pop_front())
    }
}
fn feed(input: &mut Input, manager: &mut Manager, queues: &mut Queues, bytes: &[u64]) {
    let mut stream = Stream {
        bytes: bytes.iter().copied().collect(),
        polls: 0,
    };
    input
        .poll_mode::<true>(manager, &mut stream, Some(queues))
        .unwrap();
    assert!(stream.polls <= DRAIN_LIMIT);
    assert!(stream.bytes.is_empty());
}

#[test]
fn retired_focus_does_not_deliver_unread_controller_keys_to_terminal() {
    let mut storage = [0; CAPACITY];
    let mut input = Input::new(&mut storage);
    let mut queues = Queues::new();
    let mut manager = Manager::new(1024, 768).unwrap();
    manager.show(1).unwrap();
    let old = manager.focus;
    manager.close(1).unwrap();
    input.lifetime_boundary(&mut queues, &mut manager, old);
    feed(&mut input, &mut manager, &mut queues, &[0x1e, 0x9e]);
    assert_eq!(input.pop(), None);
    assert_eq!(manager.focus, None);
}

const CLICK: [u64; 9] = [264, 256, 256, 265, 256, 256, 264, 256, 256];

#[test]
fn drain_quota_is_not_quiescence_and_quarantined_clicks_cannot_take_focus() {
    let mut storage = [0; CAPACITY];
    let mut input = Input::new(&mut storage);
    let mut queues = Queues::new();
    let mut manager = Manager::new(1024, 768).unwrap();
    manager.x = 24;
    manager.y = 56;
    let rect = manager.windows[0];
    input.lifetime_boundary(&mut queues, &mut manager, Some(1));
    let mut stream = Stream {
        bytes: [0x1e].repeat(DRAIN_LIMIT).into(),
        polls: 0,
    };
    input
        .poll_mode::<true>(&mut manager, &mut stream, Some(&mut queues))
        .unwrap();
    assert_eq!(stream.polls, DRAIN_LIMIT);
    assert!(queues.quarantined);
    feed(&mut input, &mut manager, &mut queues, &CLICK);
    assert!(!queues.quarantined);
    assert_eq!(manager.focus, None);
    assert_eq!(manager.windows[0], rect);
    assert_eq!(input.pop(), None);
    feed(&mut input, &mut manager, &mut queues, &CLICK);
    assert_eq!(manager.focus, Some(0));
    feed(
        &mut input,
        &mut manager,
        &mut queues,
        &[0x1e, 0x9e, 0x1e, 0x9e],
    );
    assert_eq!(input.pop(), Some(b'a'));
    assert_eq!(input.pop(), None);
}

#[test]
fn held_drag_cannot_transfer_to_survivor_and_fresh_press_recovers() {
    use crate::desktop::mouse::Motion;
    let mut storage = [0; CAPACITY];
    let mut input = Input::new(&mut storage);
    let mut queues = Queues::new();
    let mut manager = Manager::new(1024, 768).unwrap();
    manager.show(1).unwrap();
    manager.x = manager.windows[1].x + 8;
    manager.y = manager.windows[1].y + 8;
    manager.motion(Motion {
        dx: 0,
        dy: 0,
        buttons: 1,
    });
    manager.close(1).unwrap();
    input.lifetime_boundary(&mut queues, &mut manager, Some(1));
    manager.x = 24;
    manager.y = 56;
    let rect = manager.windows[0];
    feed(&mut input, &mut manager, &mut queues, &[265, 266, 256]);
    assert_eq!(manager.windows[0], rect);
    assert_eq!(manager.focus, None);
    feed(&mut input, &mut manager, &mut queues, &[265, 266, 256]);
    assert_eq!(manager.windows[0], rect);
    assert_eq!(manager.focus, None);
    feed(&mut input, &mut manager, &mut queues, &CLICK);
    assert_eq!(manager.focus, Some(0));
}

#[test]
fn queued_modifiers_and_partial_prefixes_are_fenced_until_break() {
    let mut storage = [0; CAPACITY];
    let mut input = Input::new(&mut storage);
    let mut queues = Queues::new();
    let mut manager = Manager::new(1024, 768).unwrap();
    manager.x = 24;
    manager.y = 56;
    input.lifetime_boundary(&mut queues, &mut manager, Some(1));
    feed(&mut input, &mut manager, &mut queues, &[0x2a, 0x1e, 0xe0]);
    feed(&mut input, &mut manager, &mut queues, &CLICK);
    feed(
        &mut input,
        &mut manager,
        &mut queues,
        &[0x1c, 0x1e, 0x2a, 0x30, 0xb0],
    );
    assert_eq!(input.pop(), Some(b'b'));
    assert_eq!(input.pop(), None);
    feed(
        &mut input,
        &mut manager,
        &mut queues,
        &[0x9e, 0xaa, 0x2a, 0x1e, 0x9e, 0xaa],
    );
    assert_eq!(input.pop(), Some(b'A'));
    assert_eq!(input.pop(), None);
}

#[test]
fn partial_mouse_packet_cannot_become_click_through_after_quiescence() {
    let mut storage = [0; CAPACITY];
    let mut input = Input::new(&mut storage);
    let mut queues = Queues::new();
    let mut manager = Manager::new(1024, 768).unwrap();
    manager.x = 24;
    manager.y = 56;
    let rect = manager.windows[0];
    input.lifetime_boundary(&mut queues, &mut manager, Some(1));
    feed(&mut input, &mut manager, &mut queues, &[265]);
    feed(&mut input, &mut manager, &mut queues, &[266, 256]);
    assert_eq!(manager.focus, None);
    assert_eq!(manager.windows[0], rect);
    feed(&mut input, &mut manager, &mut queues, &CLICK);
    assert_eq!(manager.focus, Some(0));
}

#[test]
fn reset_cancels_then_quarantines_remaining_batch_without_implicit_focus() {
    let mut storage = [0; CAPACITY];
    let mut input = Input::new(&mut storage);
    let mut queues = Queues::new();
    let mut manager = Manager::new(1024, 768).unwrap();
    manager.x = 24;
    manager.y = 56;
    feed(
        &mut input,
        &mut manager,
        &mut queues,
        &[0x30, 512, 0x1e, 0x9e],
    );
    assert_eq!(input.pop(), Some(3));
    assert_eq!(input.pop(), None);
    assert_eq!(manager.focus, None);
    assert_eq!(input.stats().resets, 1);
    feed(&mut input, &mut manager, &mut queues, &CLICK);
    feed(
        &mut input,
        &mut manager,
        &mut queues,
        &[0x1c, 0x9c, 0x1e, 0x9e],
    );
    assert_eq!(input.pop(), Some(b'a'));
    assert_eq!(input.pop(), None);
}

#[test]
fn device_error_does_not_end_quarantine_or_grant_fresh_input() {
    struct Broken;
    impl Device for Broken {
        fn next(&mut self) -> Result<Option<u64>, Error> {
            Err(Error::Transport)
        }
    }
    let mut storage = [0; CAPACITY];
    let mut input = Input::new(&mut storage);
    let mut queues = Queues::new();
    let mut manager = Manager::new(1024, 768).unwrap();
    input.lifetime_boundary(&mut queues, &mut manager, Some(1));
    assert!(
        input
            .poll_mode::<true>(&mut manager, &mut Broken, Some(&mut queues))
            .is_err()
    );
    assert!(queues.quarantined);
    // Even an erroneous caller's focus assignment cannot drain stale bytes.
    manager.focus = Some(0);
    feed(&mut input, &mut manager, &mut queues, &[0x1e, 0x9e]);
    assert_eq!(input.pop(), None);
}

#[test]
fn replacement_clears_only_its_queue_and_requires_new_focus() {
    use crate::desktop::surfaces::{Frame, OPEN, Surfaces};
    let mut storage = [0; CAPACITY];
    let mut cells = [0; 384];
    let mut input = Input::new(&mut storage);
    let mut queues = Queues::new();
    let mut surfaces = Surfaces::new(&mut cells);
    surfaces.apply(4, 1, Frame::new(OPEN, 1, 0));
    surfaces.apply(5, 1, Frame::new(OPEN, 1, 0));
    queues.sync(&surfaces);
    queues.push(0, b'x');
    queues.push(1, b'9');
    let mut manager = Manager::new(1024, 768).unwrap();
    manager.show(2).unwrap();
    manager.show(1).unwrap();
    surfaces.apply(4, 2, Frame::new(OPEN, 1, 0));
    assert_eq!(queues.sync(&surfaces), 1);
    input.lifetime_boundary(&mut queues, &mut manager, Some(1));
    feed(&mut input, &mut manager, &mut queues, &[0x1e, 0x9e]);
    assert_eq!(manager.focus, None);
    let mut first = Frame::new(super::super::application_input::INPUT, 2, 0);
    queues.drain(0, &surfaces, &mut first);
    assert_eq!((first.offset, first.len), (0, 0));
    let mut second = Frame::new(super::super::application_input::INPUT, 2, 0);
    queues.drain(1, &surfaces, &mut second);
    assert_eq!((second.offset, second.len, second.data[0]), (0, 1, b'9'));
}
