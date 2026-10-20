//! Bounded user-space command policy over the authenticated PCS1 channel.
#![forbid(unsafe_code)]
use crate::console_ipc::{Channel, Error, Kind, Message, PAYLOAD};

pub const LINE_BYTES: usize = 64;
pub const BANNER: &[u8] = b"PooleOS native shell\r\n";
pub const PROMPT: &[u8] = b"PooleOS> ";

pub mod applications;
pub mod control;
pub mod files;
pub mod processes;

pub trait Commands {
    fn help(&self) -> &'static [u8];
    fn begin(&mut self, line: &[u8]) -> Result<bool, Error>;
    fn poll(&mut self) -> Result<bool, Error>;
    fn response(&self) -> &[u8];
    /// False keeps the command active after this output chunk is acknowledged.
    fn response_complete(&self) -> bool {
        true
    }
    fn close_allowed(&self) -> bool;
}
impl<P: Commands> Commands for &mut P {
    fn help(&self) -> &'static [u8] {
        (**self).help()
    }
    fn begin(&mut self, line: &[u8]) -> Result<bool, Error> {
        (**self).begin(line)
    }
    fn poll(&mut self) -> Result<bool, Error> {
        (**self).poll()
    }
    fn response(&self) -> &[u8] {
        (**self).response()
    }
    fn response_complete(&self) -> bool {
        (**self).response_complete()
    }
    fn close_allowed(&self) -> bool {
        (**self).close_allowed()
    }
}
pub struct Builtins;
impl Commands for Builtins {
    fn help(&self) -> &'static [u8] {
        b"help  version  echo TEXT  exit\r\n"
    }
    fn begin(&mut self, _: &[u8]) -> Result<bool, Error> {
        Ok(false)
    }
    fn poll(&mut self) -> Result<bool, Error> {
        Err(Error::Wire)
    }
    fn response(&self) -> &[u8] {
        &[]
    }
    fn close_allowed(&self) -> bool {
        true
    }
}

#[derive(Clone, Copy)]
enum Output {
    Static(&'static [u8]),
    Line { start: usize, end: usize },
    Command,
}
#[derive(Clone, Copy)]
enum Next {
    Read,
    Execute,
    Prompt,
    LineEnd,
    Close,
    Command,
}

pub struct Shell<P = Builtins> {
    commands: P,
    line: [u8; LINE_BYTES],
    len: usize,
    rejected: bool,
    skip_lf: bool,
    output: Output,
    cursor: usize,
    next: Next,
    sequence: u64,
    pending: Option<(Kind, usize)>,
    closed: bool,
}
impl Default for Shell {
    fn default() -> Self {
        Self::new()
    }
}
impl Shell {
    #[inline]
    pub const fn new() -> Self {
        Self::with_commands(Builtins)
    }
}
impl<P: Commands> Shell<P> {
    #[inline(always)]
    pub const fn with_commands(commands: P) -> Self {
        Self {
            commands,
            line: [0; LINE_BYTES],
            len: 0,
            rejected: false,
            skip_lf: false,
            output: Output::Static(BANNER),
            cursor: 0,
            next: Next::Prompt,
            sequence: 1,
            pending: None,
            closed: false,
        }
    }
    fn close(&mut self) {
        if self.commands.close_allowed() {
            self.text(b"Bye.\r\n", Next::Close);
        } else {
            self.text(
                b"Stop tasks and check status before exit.\r\n",
                Next::Prompt,
            );
        }
    }
    #[inline]
    fn emit(&mut self, output: Output, next: Next) {
        self.output = output;
        self.cursor = 0;
        self.next = next;
    }
    #[inline]
    fn text(&mut self, bytes: &'static [u8], next: Next) {
        self.emit(Output::Static(bytes), next);
    }
    #[inline]
    fn input(&mut self, byte: u8) -> Result<(), Error> {
        let skip = self.skip_lf && byte == b'\n';
        self.skip_lf = byte == b'\r';
        if skip {
            return Ok(());
        }
        match byte {
            b'\r' | b'\n' => self.text(b"\r\n", Next::Execute),
            3 => self.text(b"^C\r\n", Next::Prompt),
            4 if self.len == 0 && !self.rejected => self.close(),
            4 => {}
            8 | 127 if self.len != 0 => {
                self.len -= 1;
                self.text(b"\x08 \x08", Next::Read);
            }
            8 | 127 => {}
            32..=126 if self.len < LINE_BYTES && !self.rejected => {
                let start = self.len;
                *self.line.get_mut(start).ok_or(Error::Wire)? = byte;
                self.len = start.checked_add(1).ok_or(Error::Wire)?;
                self.emit(
                    Output::Line {
                        start,
                        end: self.len,
                    },
                    Next::Read,
                );
            }
            // An invalid/overlong line cannot execute a valid truncated prefix.
            _ => {
                self.rejected = true;
                self.text(b"\x07", Next::Read);
            }
        }
        Ok(())
    }
    #[inline]
    fn execute(&mut self) -> Result<(), Error> {
        if self.rejected {
            self.text(b"Invalid line.\r\n", Next::Prompt);
            return Ok(());
        }
        match self.line.get(..self.len).ok_or(Error::Wire)? {
            b"" => self.text(b"", Next::Prompt),
            b"help" => self.text(self.commands.help(), Next::Prompt),
            b"version" => self.text(
                b"PooleOS native development / PooleShell 0.1\r\n",
                Next::Prompt,
            ),
            b"exit" => self.close(),
            b"echo" => self.text(b"\r\n", Next::Prompt),
            line if line.starts_with(b"echo ") => self.emit(
                Output::Line {
                    start: 5,
                    end: self.len,
                },
                Next::LineEnd,
            ),
            line => {
                if self.commands.begin(line)? {
                    self.text(b"", Next::Command);
                } else {
                    self.text(b"Unknown command.\r\n", Next::Prompt);
                }
            }
        }
        Ok(())
    }
    /// At most one IPC operation per poll; false also covers peer backpressure.
    #[inline(never)]
    pub fn poll<C: Channel>(&mut self, channel: &mut C) -> Result<bool, Error> {
        if self.closed {
            return Ok(true);
        }
        if let Some((expected, bytes)) = self.pending {
            let Some(reply) = channel.receive()? else {
                return Ok(false);
            };
            if reply.sequence() != self.sequence || reply.kind() != expected {
                return Err(Error::Sequence);
            }
            self.sequence = self.sequence.checked_add(1).ok_or(Error::Sequence)?;
            self.pending = None;
            match expected {
                Kind::Written => self.cursor = self.cursor.checked_add(bytes).ok_or(Error::Wire)?,
                Kind::Input => self.input(*reply.payload().first().ok_or(Error::Wire)?)?,
                Kind::Closed => self.closed = true,
                _ => return Err(Error::Wire),
            }
            return Ok(self.closed);
        }
        let output = match self.output {
            Output::Static(bytes) => bytes,
            Output::Line { start, end } => self.line.get(start..end).ok_or(Error::Wire)?,
            Output::Command => self.commands.response(),
        };
        let (kind, response, data) = if self.cursor < output.len() {
            let end = output
                .len()
                .min(self.cursor.checked_add(PAYLOAD).ok_or(Error::Wire)?);
            (
                Kind::Write,
                Kind::Written,
                output.get(self.cursor..end).ok_or(Error::Wire)?,
            )
        } else {
            match self.next {
                Next::Read => (Kind::Read, Kind::Input, &[][..]),
                Next::Close => (Kind::Close, Kind::Closed, &[][..]),
                Next::Execute => {
                    self.execute()?;
                    return Ok(false);
                }
                Next::Prompt => {
                    self.len = 0;
                    self.rejected = false;
                    self.text(PROMPT, Next::Read);
                    return Ok(false);
                }
                Next::LineEnd => {
                    self.text(b"\r\n", Next::Prompt);
                    return Ok(false);
                }
                Next::Command => {
                    if self.commands.poll()? {
                        let next = if self.commands.response_complete() {
                            Next::Prompt
                        } else {
                            Next::Command
                        };
                        self.emit(Output::Command, next);
                    }
                    return Ok(false);
                }
            }
        };
        let request = Message::new(kind, self.sequence, data)?;
        if channel.send(request)? {
            self.pending = Some((response, data.len()));
        }
        Ok(false)
    }
}

#[cfg(test)]
mod tests;
