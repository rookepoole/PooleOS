//! Bounded user-space command policy over the authenticated PCS1 channel.
#![forbid(unsafe_code)]
use crate::console_ipc::{Channel, Error, Kind, Message, PAYLOAD};

pub const LINE_BYTES: usize = 64;
pub const BANNER: &[u8] = b"PooleOS native shell\r\n";
pub const PROMPT: &[u8] = b"PooleOS> ";

#[derive(Clone, Copy)]
enum Output {
    Static(&'static [u8]),
    Line { start: usize, end: usize },
}
#[derive(Clone, Copy)]
enum Next {
    Read,
    Execute,
    Prompt,
    LineEnd,
    Close,
}

pub struct Shell {
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
        Self {
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
            4 if self.len == 0 && !self.rejected => self.text(b"Bye.\r\n", Next::Close),
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
            b"help" => self.text(b"help  version  echo TEXT  exit\r\n", Next::Prompt),
            b"version" => self.text(
                b"PooleOS native development / PooleShell 0.1\r\n",
                Next::Prompt,
            ),
            b"exit" => self.text(b"Bye.\r\n", Next::Close),
            b"echo" => self.text(b"\r\n", Next::Prompt),
            line if line.starts_with(b"echo ") => self.emit(
                Output::Line {
                    start: 5,
                    end: self.len,
                },
                Next::LineEnd,
            ),
            _ => self.text(b"Unknown command.\r\n", Next::Prompt),
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
