//! Streaming ls/cat commands. Output is acknowledged before the next file chunk.
use super::{Commands, Error};
use crate::{
    console_ipc::rpc::Calls,
    files::{self, Frame, rpc::Client},
};
pub struct Files<C> {
    client: Client<C>,
    path: [u8; files::PAYLOAD],
    len: u8,
    op: u8,
    offset: u32,
    total: Option<u32>,
    sequence: u64,
    pending: bool,
    complete: bool,
    output: [u8; files::PAYLOAD + 2],
    bytes: usize,
}
impl<C: Calls> Files<C> {
    #[inline(always)]
    pub const fn new(client: Client<C>) -> Self {
        Self {
            client,
            path: [0; files::PAYLOAD],
            len: 0,
            op: 0,
            offset: 0,
            total: None,
            sequence: 1,
            pending: false,
            complete: true,
            output: [0; files::PAYLOAD + 2],
            bytes: 0,
        }
    }
    #[inline(never)]
    fn put(&mut self, byte: u8) -> Result<(), Error> {
        *self.output.get_mut(self.bytes).ok_or(Error::Wire)? = byte;
        self.bytes = self.bytes.checked_add(1).ok_or(Error::Wire)?;
        Ok(())
    }
    fn text(&mut self, text: &[u8]) -> Result<bool, Error> {
        self.bytes = 0;
        self.complete = true;
        for &byte in text {
            self.put(byte)?;
        }
        Ok(true)
    }
    fn receive(&mut self, reply: Frame) -> Result<bool, Error> {
        self.bytes = 0;
        if reply.status != files::OK {
            if reply.total != 0 || reply.len != 0 {
                return Err(Error::Wire);
            }
            return match reply.status {
                files::END if self.op == files::LIST => self.text(b""),
                files::NOT_FOUND if self.op == files::READ => self.text(b"File not found.\r\n"),
                files::INVALID | files::RANGE => self.text(b"Invalid file request.\r\n"),
                _ => Err(Error::Wire),
            };
        }
        let data = reply.payload().ok_or(Error::Wire)?;
        if self.op == files::LIST {
            if !files::valid_path(data) {
                return Err(Error::Wire);
            }
            // Bounded protocol: listing cannot keep the shell busy forever.
            if self.offset >= 8 {
                return Err(Error::Wire);
            }
            self.offset = self.offset.checked_add(1).ok_or(Error::Wire)?;
        } else {
            if reply.total > 1024 || self.total.is_some_and(|total| total != reply.total) {
                return Err(Error::Wire);
            }
            self.total = Some(reply.total);
            let end = self
                .offset
                .checked_add(u32::from(reply.len))
                .ok_or(Error::Wire)?;
            if end > reply.total
                || (reply.len == 0 && end != reply.total)
                || data
                    .iter()
                    .any(|b| !matches!(b, 32..=126 | b'\r' | b'\n' | b'\t'))
            {
                return Err(Error::Wire);
            }
            self.offset = end;
            self.complete = end == reply.total;
        }
        for &byte in data {
            self.put(byte)?;
        }
        if self.op == files::LIST {
            self.put(b'\r')?;
            self.put(b'\n')?;
        }
        Ok(true)
    }
}
impl<C: Calls> Commands for Files<C> {
    fn help(&self) -> &'static [u8] {
        b"ls  cat /PATH\r\n"
    }
    fn begin(&mut self, line: &[u8]) -> Result<bool, Error> {
        if !self.complete || self.pending {
            return Err(Error::Sequence);
        }
        let path = if matches!(line, b"ls" | b"ls /") {
            self.op = files::LIST;
            &[][..]
        } else if let Some(path) = line.strip_prefix(b"cat ") {
            self.op = files::READ;
            path
        } else {
            return Ok(false);
        };
        self.bytes = 0;
        self.offset = 0;
        self.total = None;
        self.path.fill(0);
        self.len = 0;
        if self.op == files::READ && !files::valid_path(path) {
            self.text(b"Invalid path.\r\n")?;
            self.op = 0;
            return Ok(true);
        }
        for (i, &byte) in path.iter().enumerate() {
            *self.path.get_mut(i).ok_or(Error::Wire)? = byte;
        }
        self.len = path.len() as u8;
        self.complete = false;
        Ok(true)
    }
    fn poll(&mut self) -> Result<bool, Error> {
        if self.op == 0 {
            return Ok(true);
        }
        if !self.pending {
            let mut request = Frame::empty(self.op, self.sequence, self.offset);
            request.len = self.len;
            for (to, from) in request.data.iter_mut().zip(self.path.iter()) {
                *to = *from;
            }
            match self.client.start(&request) {
                Ok(sent) => {
                    self.pending = sent;
                    Ok(false)
                }
                Err(Error::Revoked) => self.text(b"File service unavailable.\r\n"),
                Err(error) => Err(error),
            }
        } else {
            match self.client.finish() {
                Ok(Some(reply)) => {
                    self.pending = false;
                    self.sequence = self
                        .sequence
                        .checked_add(1)
                        .filter(|&n| n < u64::MAX)
                        .ok_or(Error::Sequence)?;
                    self.receive(reply)
                }
                Ok(None) => Ok(false),
                Err(Error::Revoked) => {
                    self.pending = false;
                    self.text(b"File service unavailable.\r\n")
                }
                Err(error) => Err(error),
            }
        }
    }
    fn response(&self) -> &[u8] {
        self.output.get(..self.bytes).unwrap_or(&[])
    }
    fn response_complete(&self) -> bool {
        self.complete
    }
    fn close_allowed(&self) -> bool {
        self.complete && !self.pending
    }
}
#[cfg(test)]
mod tests;
