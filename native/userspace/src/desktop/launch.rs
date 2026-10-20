//! Bounded window intents. Process authority and attempt numbering stay in the shell.
#![forbid(unsafe_code)]
use super::{mouse::Motion, windows::Manager};
use crate::{
    console::Error as DeviceError,
    console_ipc::{Error, control::Server},
    session_control::{Action, App, Reply, Status},
};

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
struct Intent {
    app: App,
    action: Action,
    generation: u32,
}
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
enum Phase {
    Idle,
    Queued(Intent),
    Sent(Intent),
    Failed,
}

pub struct Controls {
    generations: [u32; 2],
    results: [Option<Status>; 2],
    phase: Phase,
    last: Option<App>,
    cancelled: Option<App>,
    buttons: u8,
    keys: Keys,
}
impl Default for Controls {
    fn default() -> Self {
        Self::new()
    }
}
impl Controls {
    #[inline(always)]
    pub const fn new() -> Self {
        Self {
            generations: [0; 2],
            results: [None; 2],
            phase: Phase::Idle,
            last: None,
            cancelled: None,
            buttons: 0,
            keys: Keys::new(),
        }
    }
    /// A fresh gesture may restore a surface or queue one typed request.
    #[inline]
    pub fn activate(
        &mut self,
        index: usize,
        inspect: bool,
        manager: &mut Manager,
    ) -> Result<bool, DeviceError> {
        if index >= 3 || matches!(self.phase, Phase::Failed) {
            return Err(DeviceError::Transport);
        }
        if !inspect && manager.available[index] {
            manager.show(index)?;
            return Ok(true);
        }
        if index == 0 || self.phase != Phase::Idle {
            return Ok(false);
        }
        let app = if index == 1 { App::Text } else { App::Numbers };
        self.last = Some(app);
        self.cancelled = None;
        self.phase = Phase::Queued(Intent {
            app,
            action: if inspect {
                Action::Inspect
            } else {
                Action::Start
            },
            generation: self.generations[app.index()],
        });
        Ok(true)
    }
    /// Observe releases even while quarantined; a held press never becomes fresh.
    #[inline]
    pub fn pointer(
        &mut self,
        motion: Motion,
        manager: &mut Manager,
        allowed: bool,
    ) -> Result<bool, DeviceError> {
        let pressed = motion.buttons & 3;
        let fresh = pressed & !self.buttons;
        self.buttons = pressed;
        if !allowed || manager.y < manager.bounds.h.saturating_sub(32) {
            return Ok(false);
        }
        let index = usize::from(manager.x / 160);
        if index >= 3 || fresh == 0 {
            return Ok(false);
        }
        // Simultaneous buttons cannot choose an effectful action.
        if pressed == 2 && fresh == 2 {
            self.activate(index, true, manager)
        } else if pressed == 1 && fresh == 1 && !manager.available[index] {
            self.activate(index, false, manager)
        } else {
            Ok(false)
        }
    }
    #[inline]
    pub fn key(
        &mut self,
        code: u8,
        manager: &mut Manager,
        allowed: bool,
    ) -> Result<(bool, bool), DeviceError> {
        let (consumed, action) = self.keys.feed(code, allowed);
        let changed = if let Some((index, inspect)) = action {
            self.activate(index, inspect, manager)?
        } else {
            false
        };
        Ok((consumed, changed))
    }
    #[inline]
    pub fn reset_input(&mut self) {
        self.buttons = 3;
        self.keys.reset();
        if let Phase::Queued(intent) = self.phase {
            self.cancelled = Some(intent.app);
            self.phase = Phase::Idle;
        }
    }
    /// Only the real session server can supply the acknowledged result.
    #[inline]
    pub fn advance(&mut self, server: &mut Server) -> Result<bool, Error> {
        let result = match self.phase {
            Phase::Idle => Ok(false),
            Phase::Queued(intent) => server
                .request(intent.app, intent.action, intent.generation)
                .map(|accepted| {
                    if accepted {
                        self.phase = Phase::Sent(intent);
                    }
                    accepted
                }),
            Phase::Sent(intent) => match server.take_result() {
                None => Ok(false),
                Some(reply) => self.complete(intent, reply).map(|()| true),
            },
            Phase::Failed => Err(Error::Transport),
        };
        if result.is_err() {
            self.phase = Phase::Failed;
        }
        result
    }
    #[inline]
    fn complete(&mut self, intent: Intent, reply: Reply) -> Result<(), Error> {
        let request = reply.request();
        if request.app != intent.app
            || request.action != intent.action
            || request.generation != intent.generation
            || reply.generation() < self.generations[intent.app.index()]
        {
            return Err(Error::Sequence);
        }
        self.generations[intent.app.index()] = reply.generation();
        self.results[intent.app.index()] = Some(reply.status());
        self.phase = Phase::Idle;
        Ok(())
    }
    #[inline]
    pub fn last(&self) -> Option<App> {
        self.last
    }
    /// Last control result; surface presence is rendered separately.
    #[inline]
    pub fn label(&self, app: App) -> &'static [u8] {
        match self.phase {
            Phase::Queued(i) if i.app == app => return b"queued",
            Phase::Sent(i) if i.app == app => return b"pending",
            Phase::Failed => return b"disconnected",
            _ => {}
        }
        if self.cancelled == Some(app) {
            return b"cancelled";
        }
        match self.results[app.index()] {
            None => b"idle",
            Some(Status::Admitted) => b"admitted",
            Some(Status::Running) => b"running",
            Some(Status::StopPending | Status::StopClaimed) => b"stopping",
            Some(Status::Retiring) => b"retiring",
            Some(Status::Absent) => b"absent",
            Some(Status::Terminal) => b"stopped",
            Some(Status::Denied) => b"denied",
            Some(Status::LaunchFailed) => b"launch failed",
            Some(Status::Stale) => b"changed",
            Some(Status::Exhausted) => b"exhausted",
            Some(Status::Busy) => b"busy",
        }
    }
}

struct Keys {
    held: u8,
    modifiers: u8,
    extended: bool,
    pause: u8,
}
impl Keys {
    const fn new() -> Self {
        Self {
            held: 0,
            modifiers: 0,
            extended: false,
            pause: 0,
        }
    }
    fn reset(&mut self) {
        // A reset is not evidence that any previously held key was released.
        self.held = 7;
        self.extended = false;
        self.pause = 0;
    }
    #[inline]
    fn feed(&mut self, code: u8, allowed: bool) -> (bool, Option<(usize, bool)>) {
        if self.pause != 0 {
            self.pause -= 1;
            return (false, None);
        }
        if code == 0xe1 {
            self.pause = 5;
            self.extended = false;
            return (false, None);
        }
        if code == 0xe0 {
            self.extended = true;
            return (false, None);
        }
        let extended = core::mem::replace(&mut self.extended, false);
        let key = code & 0x7f;
        let released = code & 0x80 != 0;
        let modifier = match (extended, key) {
            (false, 0x2a) => 1,
            (false, 0x36) => 2,
            (false, 0x1d) => 4,
            (true, 0x1d) => 8,
            (false, 0x38) => 16,
            (true, 0x38) => 32,
            _ => 0,
        };
        if released {
            self.modifiers &= !modifier;
        } else {
            self.modifiers |= modifier;
        }
        if extended || !(0x3b..=0x3d).contains(&key) {
            return (false, None);
        }
        let index = usize::from(key - 0x3b);
        let bit = 1 << index;
        let fresh = self.held & bit == 0;
        if released {
            self.held &= !bit;
        } else {
            self.held |= bit;
        }
        let action = if allowed && !released && fresh && self.modifiers & !3 == 0 {
            Some((index, self.modifiers & 3 != 0))
        } else {
            None
        };
        (true, action)
    }
}

#[cfg(test)]
mod tests;
