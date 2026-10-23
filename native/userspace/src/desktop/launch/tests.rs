use super::*;
use crate::{
    console::Registers,
    console_ipc::{Kind, Message},
    session_control::{Channel, Frame, Request, rpc::Exchange},
};
use std::{collections::VecDeque, vec::Vec};

#[derive(Default)]
struct Link {
    input: VecDeque<Exchange>,
    sent: Vec<Exchange>,
    blocked: bool,
}
impl Channel for Link {
    fn receive(&mut self) -> Result<Option<Exchange>, Error> {
        Ok(self.input.pop_front())
    }
    fn send(&mut self, value: Exchange) -> Result<bool, Error> {
        self.sent.push(value);
        Ok(!self.blocked)
    }
}
struct Port;
impl Registers for Port {
    fn read(&mut self, _: u8) -> Result<u8, DeviceError> {
        panic!("control read terminal data")
    }
    fn write(&mut self, _: u8, _: u8) -> Result<(), DeviceError> {
        panic!("control wrote terminal data")
    }
}
fn manager() -> Manager {
    Manager::new(640, 480).unwrap()
}
fn motion(buttons: u8) -> Motion {
    Motion {
        dx: 0,
        dy: 0,
        buttons,
    }
}
fn ready() -> (Server, Link) {
    let mut s = Server::new();
    let mut link = Link::default();
    link.input
        .push_back(Exchange::Console(Message::new(Kind::Read, 1, &[]).unwrap()));
    assert_eq!(s.poll(&mut Port, &mut link), Ok(false));
    (s, link)
}
fn sent(c: &mut Controls, s: &mut Server, link: &mut Link) -> Request {
    assert_eq!(c.advance(s), Ok(true));
    assert_eq!(s.poll(&mut Port, link), Ok(false));
    let Exchange::Control(Frame::Request(request)) = *link.sent.last().unwrap() else {
        panic!()
    };
    request
}
fn finish(c: &mut Controls, s: &mut Server, link: &mut Link, reply: Reply) {
    link.input.push_back(Exchange::Control(Frame::Reply(reply)));
    assert_eq!(s.poll(&mut Port, link), Ok(false));
    assert_eq!(c.advance(s), Ok(false));
    assert_eq!(s.poll(&mut Port, link), Ok(false));
    assert_eq!(c.advance(s), Ok(true));
}

#[test]
fn pointer_requires_fresh_unquarantined_single_button_and_never_queues_a_backlog() {
    let mut c = Controls::new();
    let mut m = manager();
    m.x = 200;
    m.y = 456;
    assert!(!c.pointer(motion(3), &mut m, true).unwrap());
    assert!(!c.pointer(motion(1), &mut m, true).unwrap());
    c.pointer(motion(0), &mut m, true).unwrap();
    assert!(!c.pointer(motion(1), &mut m, false).unwrap());
    assert!(!c.pointer(motion(1), &mut m, true).unwrap());
    c.pointer(motion(0), &mut m, true).unwrap();
    assert!(c.pointer(motion(1), &mut m, true).unwrap());
    let before = c.phase;
    assert_eq!(m.focus, Some(0));
    assert!(!m.available[1] && !m.visible[1]);
    assert!(!c.pointer(motion(1), &mut m, true).unwrap());
    m.x = 360;
    c.pointer(motion(0), &mut m, true).unwrap();
    assert!(!c.pointer(motion(1), &mut m, true).unwrap());
    assert_eq!(c.phase, before);
    assert_eq!(c.last(), Some(App::Text));
}

#[test]
fn taskbar_restore_has_no_launch_effect_and_right_click_only_inspects() {
    let mut c = Controls::new();
    let mut m = manager();
    m.show(1).unwrap();
    m.visible[1] = false;
    m.focus = Some(0);
    assert!(c.activate(1, false, &mut m).unwrap());
    assert!(m.visible[1]);
    assert_eq!(m.focus, Some(1));
    assert_eq!(c.phase, Phase::Idle);
    m.x = 200;
    m.y = 456;
    assert!(c.pointer(motion(2), &mut m, true).unwrap());
    assert_eq!(
        c.phase,
        Phase::Queued(Intent {
            app: App::Text,
            action: Action::Inspect,
            generation: 0
        })
    );
    assert!(c.activate(3, false, &mut m).is_err());
}

#[test]
fn function_keys_are_edge_triggered_prefix_aware_and_modifier_safe() {
    let mut keys = Keys::new();
    assert_eq!(keys.feed(0x3c, true), (true, Some((1, false))));
    assert_eq!(keys.feed(0x3c, true), (true, None));
    keys.feed(0xbc, true);
    keys.feed(0x2a, true);
    assert_eq!(keys.feed(0x3c, true), (true, Some((1, true))));
    keys.feed(0xbc, true);
    keys.feed(0xaa, true);
    keys.feed(0xe0, true);
    assert_eq!(keys.feed(0x3c, true), (false, None));
    for modifier in [0x1d, 0x38] {
        keys.feed(modifier, true);
        assert_eq!(keys.feed(0x3d, true), (true, None));
        keys.feed(0xbd, true);
        keys.feed(modifier | 0x80, true);
    }
    keys.feed(0xe1, true);
    for code in [0x3c, 0xbc, 0x3d, 0xbd, 0] {
        assert_eq!(keys.feed(code, true), (false, None));
    }
    assert_eq!(keys.feed(0x3d, true), (true, Some((2, false))));
}

#[test]
fn reset_requires_key_release_and_preserves_known_held_modifiers() {
    let mut keys = Keys::new();
    keys.feed(0x38, true);
    keys.reset();
    assert_eq!(keys.feed(0x3c, true), (true, None));
    keys.feed(0xbc, true);
    assert_eq!(keys.feed(0x3c, true), (true, None));
    keys.feed(0xbc, true);
    keys.feed(0xb8, true);
    assert_eq!(keys.feed(0x3c, true), (true, Some((1, false))));
    keys.feed(0xbc, true);
    assert_eq!(keys.feed(0x3d, false), (true, None));
    assert_eq!(keys.feed(0x3d, true), (true, None));
    keys.feed(0xbd, false);
    assert_eq!(keys.feed(0x3d, true), (true, Some((2, false))));
}

#[test]
fn real_server_keeps_intent_and_generation_until_the_bound_ack_is_sent() {
    let mut c = Controls::new();
    c.activate(1, false, &mut manager()).unwrap();
    let mut s = Server::new();
    for _ in 0..4 {
        assert_eq!(c.advance(&mut s), Ok(false));
    }
    assert_eq!(c.label(App::Text), b"queued");
    let (mut s, mut link) = ready();
    link.blocked = true;
    let request = sent(&mut c, &mut s, &mut link);
    assert_eq!(request.generation, 0);
    for _ in 0..4 {
        s.poll(&mut Port, &mut link).unwrap();
        assert!(!c.advance(&mut s).unwrap());
    }
    assert_eq!(c.generations, [0, 0]);
    link.blocked = false;
    s.poll(&mut Port, &mut link).unwrap();
    let reply = Reply::new(request, Status::Admitted, 1).unwrap();
    link.input.push_back(Exchange::Control(Frame::Reply(reply)));
    s.poll(&mut Port, &mut link).unwrap();
    link.blocked = true;
    for _ in 0..4 {
        s.poll(&mut Port, &mut link).unwrap();
        assert!(!c.advance(&mut s).unwrap());
    }
    assert_eq!(c.generations, [0, 0]);
    assert_eq!(c.label(App::Text), b"pending");
    link.blocked = false;
    s.poll(&mut Port, &mut link).unwrap();
    assert!(c.advance(&mut s).unwrap());
    assert_eq!(c.generations, [1, 0]);
    assert_eq!(c.label(App::Text), b"admitted");
    for _ in 0..4 {
        assert!(!c.advance(&mut s).unwrap());
    }
}

#[test]
fn stale_result_refreshes_only_attempt_sequence_without_automatic_retry() {
    let mut c = Controls::new();
    let mut m = manager();
    c.activate(1, false, &mut m).unwrap();
    let (mut s, mut link) = ready();
    let request = sent(&mut c, &mut s, &mut link);
    finish(
        &mut c,
        &mut s,
        &mut link,
        Reply::new(request, Status::Stale, 9).unwrap(),
    );
    assert_eq!(c.generations, [9, 0]);
    assert!(!m.available[1]);
    assert_eq!(c.label(App::Text), b"changed");
    assert!(!c.advance(&mut s).unwrap());
    c.activate(1, false, &mut m).unwrap();
    assert_eq!(
        c.phase,
        Phase::Queued(Intent {
            app: App::Text,
            action: Action::Start,
            generation: 9
        })
    );
}

#[test]
fn every_status_remains_a_control_result_not_surface_or_task_identity() {
    for status in [
        Status::Admitted,
        Status::Running,
        Status::StopPending,
        Status::StopClaimed,
        Status::Retiring,
        Status::Absent,
        Status::Terminal,
        Status::Denied,
        Status::LaunchFailed,
        Status::Stale,
        Status::Exhausted,
        Status::Busy,
    ] {
        let mut c = Controls::new();
        let m = &mut manager();
        c.generations[1] = if status == Status::Exhausted {
            u32::MAX
        } else {
            4
        };
        c.activate(2, false, m).unwrap();
        let (mut s, mut link) = ready();
        let request = sent(&mut c, &mut s, &mut link);
        let generation = match status {
            Status::Admitted | Status::LaunchFailed | Status::Stale => 5,
            Status::Exhausted => u32::MAX,
            _ => 4,
        };
        finish(
            &mut c,
            &mut s,
            &mut link,
            Reply::new(request, status, generation).unwrap(),
        );
        assert_eq!(c.generations[1], generation);
        assert_eq!(c.phase, Phase::Idle);
        assert!(!m.available[2] && !m.visible[2]);
        assert!(!c.label(App::Numbers).is_empty());
        assert!(c.label(App::Numbers).len() <= 13);
    }
}

#[test]
fn decreasing_sequence_or_mismatched_result_poison_the_controller() {
    for kind in 0..3 {
        let mut c = Controls::new();
        c.generations[0] = 3;
        c.activate(1, false, &mut manager()).unwrap();
        let (mut s, mut link) = ready();
        let request = sent(&mut c, &mut s, &mut link);
        let Phase::Sent(mut intent) = c.phase else {
            panic!()
        };
        if kind == 1 {
            intent.app = App::Numbers;
        }
        if kind == 2 {
            intent.action = Action::Inspect;
        }
        c.phase = Phase::Sent(intent);
        let reply = Reply::new(
            request,
            if kind == 0 {
                Status::Stale
            } else {
                Status::Running
            },
            if kind == 0 { 2 } else { 3 },
        )
        .unwrap();
        link.input.push_back(Exchange::Control(Frame::Reply(reply)));
        s.poll(&mut Port, &mut link).unwrap();
        s.poll(&mut Port, &mut link).unwrap();
        assert!(c.advance(&mut s).is_err());
        assert_eq!(c.phase, Phase::Failed);
        assert!(c.activate(1, false, &mut manager()).is_err());
        assert_eq!(c.generations, [3, 0]);
    }
}

#[test]
fn device_reset_cancels_unsent_intent_but_never_denies_an_inflight_effect() {
    let mut c = Controls::new();
    c.activate(1, false, &mut manager()).unwrap();
    c.reset_input();
    assert_eq!(c.phase, Phase::Idle);
    assert_eq!(c.label(App::Text), b"cancelled");
    let (mut s, mut link) = ready();
    assert!(!c.advance(&mut s).unwrap());
    c.activate(2, false, &mut manager()).unwrap();
    let request = sent(&mut c, &mut s, &mut link);
    c.reset_input();
    assert!(matches!(c.phase, Phase::Sent(_)));
    finish(
        &mut c,
        &mut s,
        &mut link,
        Reply::new(request, Status::LaunchFailed, 1).unwrap(),
    );
    assert_eq!(c.label(App::Numbers), b"launch failed");
}

#[test]
fn real_input_routes_controls_without_terminal_text_or_quarantine_click_through() {
    use crate::desktop::{
        application_input::Queues,
        input::{Device, Input},
    };
    struct DeviceBytes(VecDeque<u64>, usize);
    impl Device for DeviceBytes {
        fn next(&mut self) -> Result<Option<u64>, DeviceError> {
            self.1 += 1;
            Ok(self.0.pop_front())
        }
    }
    let mut cells = [0; 64];
    let mut input = Input::new(&mut cells);
    let mut queues = Queues::new();
    let mut c = Controls::new();
    let mut m = manager();
    queues.quarantined = true;
    let mut device = DeviceBytes([0x3c, 0x3c].into(), 0);
    input
        .poll_launch(&mut m, &mut device, &mut queues, &mut c)
        .unwrap();
    assert_eq!(c.phase, Phase::Idle);
    device.0 = [0x3c, 0xbc, 0x3c, 0x3c].into();
    let update = input
        .poll_launch(&mut m, &mut device, &mut queues, &mut c)
        .unwrap();
    assert!(update.scene_changed);
    assert_eq!(c.last(), Some(App::Text));
    assert_eq!(input.pop(), None);
    assert_eq!(m.focus, Some(0));
    assert!(device.1 < 32);
    device.0 = [512].into();
    input
        .poll_launch(&mut m, &mut device, &mut queues, &mut c)
        .unwrap();
    assert_eq!(c.phase, Phase::Idle);
    assert_eq!(c.label(App::Text), b"cancelled");
}

#[test]
fn launch_composition_fits_smallest_viewport_and_keeps_status_domains_separate() {
    use crate::desktop::{Canvas, Terminal, compositor, surfaces::Surfaces};
    struct Bounds;
    impl Canvas for Bounds {
        fn fill(&mut self, x: u16, y: u16, w: u16, h: u16, _: u32) -> Result<(), DeviceError> {
            assert!(
                w > 0
                    && h > 0
                    && u32::from(x) + u32::from(w) <= 640
                    && u32::from(y) + u32::from(h) <= 480
            );
            Ok(())
        }
        fn tile(
            &mut self,
            x: u16,
            y: u16,
            w: u16,
            h: u16,
            _: u64,
            _: u32,
            _: u32,
        ) -> Result<(), DeviceError> {
            assert!(w <= 8 && h <= 8);
            self.fill(x, y, w, h, 0)
        }
    }
    let mut m = manager();
    let mut terminal_cells = [0; 1920];
    let mut app_cells = [0; 384];
    let mut t = Terminal::window(&mut terminal_cells);
    t.relocate(24, 84);
    let s = Surfaces::new(&mut app_cells);
    let mut c = Controls::new();
    c.last = Some(App::Numbers);
    c.results[1] = Some(Status::LaunchFailed);
    assert!(144 + (9 + c.label(App::Numbers).len() + 13) * 12 <= 640);
    compositor::paint_launch(&m, &t, &s, &mut Bounds, m.bounds, &c).unwrap();
    m.show(2).unwrap();
    compositor::paint_launch(&m, &t, &s, &mut Bounds, m.bounds, &c).unwrap();
    assert_eq!(c.generations, [0, 0]);
    assert_eq!(c.label(App::Numbers), b"launch failed");
}
