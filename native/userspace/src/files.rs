//! PFILE1: immutable bundled files. No host paths, writable storage, or kernel policy.
#![forbid(unsafe_code)]
pub mod rpc;
pub const BYTES: usize = 64;
pub const PAYLOAD: usize = 40;
pub const LIST: u8 = 1;
pub const READ: u8 = 2;
pub const OK: u8 = 0;
pub const NOT_FOUND: u8 = 1;
pub const INVALID: u8 = 2;
pub const RANGE: u8 = 3;
pub const END: u8 = 4;
pub const VERSION: &[u8] = b"PooleOS native development / PFILE1\r\n";

/// Keep dynamic comparisons inside the flat program, without a libc import.
#[inline(always)]
pub fn same_bytes(a: &[u8], b: &[u8]) -> bool {
    a.len() == b.len() && a.iter().zip(b).fold(0u8, |diff, (&x, &y)| diff | (x ^ y)) == 0
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct Frame {
    pub op: u8,
    pub status: u8,
    pub sequence: u64,
    pub offset: u32,
    pub total: u32,
    pub len: u8,
    pub data: [u8; PAYLOAD],
}
impl Frame {
    #[inline(always)]
    pub const fn empty(op: u8, sequence: u64, offset: u32) -> Self {
        Self {
            op,
            status: OK,
            sequence,
            offset,
            total: 0,
            len: 0,
            data: [0; PAYLOAD],
        }
    }
    #[inline(always)]
    pub fn payload(&self) -> Option<&[u8]> {
        self.data.get(..usize::from(self.len))
    }
    #[inline(always)]
    pub fn encode(&self) -> [u8; BYTES] {
        let mut wire = [0; BYTES];
        wire[..4].copy_from_slice(b"PFI1");
        wire[4] = self.op;
        wire[5] = self.status;
        wire[6] = self.len;
        wire[8..16].copy_from_slice(&self.sequence.to_le_bytes());
        wire[16..20].copy_from_slice(&self.offset.to_le_bytes());
        wire[20..24].copy_from_slice(&self.total.to_le_bytes());
        wire[24..].copy_from_slice(&self.data);
        wire
    }
    #[inline(always)]
    pub fn decode(wire: &[u8]) -> Option<Self> {
        if wire.len() != BYTES
            || &wire[..4] != b"PFI1"
            || wire[7] != 0
            || !matches!(wire[4], LIST | READ)
            || wire[5] > END
            || usize::from(wire[6]) > PAYLOAD
            || wire[24 + usize::from(wire[6])..].iter().any(|&b| b != 0)
        {
            return None;
        }
        let sequence = u64::from_le_bytes(wire[8..16].try_into().ok()?);
        if sequence == 0 || sequence == u64::MAX {
            return None;
        }
        let mut frame = Self::empty(
            wire[4],
            sequence,
            u32::from_le_bytes(wire[16..20].try_into().ok()?),
        );
        frame.status = wire[5];
        frame.total = u32::from_le_bytes(wire[20..24].try_into().ok()?);
        frame.len = wire[6];
        frame.data.copy_from_slice(&wire[24..]);
        Some(frame)
    }
}

#[inline(always)]
pub fn valid_path(path: &[u8]) -> bool {
    (2..=PAYLOAD).contains(&path.len())
        && path[0] == b'/'
        && !path.windows(2).any(|p| p == b"..")
        && path
            .get(1..)
            .unwrap_or(&[])
            .iter()
            .all(|b| matches!(b, b'a'..=b'z' | b'0'..=b'9' | b'.' | b'_' | b'-'))
        && path.get(1).is_some_and(|&byte| byte != b'.')
}

// Explicit matches keep all bundle references local in relocation-free RX code.
#[inline(always)]
pub fn entry(index: u32) -> Option<(&'static [u8], &'static [u8])> {
    match index {
        0 => Some((b"/readme.txt", b"PooleOS native user-space integration\r\nThis immutable bundle is served by an isolated user process over capability IPC.\r\nNo host filesystem is mounted.\r\n")),
        1 => Some((b"/version.txt", VERSION)),
        2 => Some((b"/numbers.csv", b"value\r\n3\r\n5\r\n8\r\n13\r\n21\r\n")),
        3 => Some((b"/empty.txt", b"")),
        _ => None,
    }
}
pub const ENTRIES: u32 = 4;

/// Malformed requests get a bounded error; they do not terminate the service.
#[inline(always)]
pub fn answer(wire: &[u8]) -> Frame {
    let Some(request) = Frame::decode(wire) else {
        let mut error = Frame::empty(READ, 1, 0);
        error.status = INVALID;
        return error;
    };
    let mut reply = Frame::empty(request.op, request.sequence, request.offset);
    reply.status = INVALID;
    if request.status != OK || request.total != 0 {
        return reply;
    }
    let (data, total) = if request.op == LIST {
        if request.len != 0 {
            return reply;
        }
        match entry(request.offset) {
            Some((path, bytes)) => (path, bytes.len()),
            None => {
                reply.status = if request.offset == ENTRIES {
                    END
                } else {
                    RANGE
                };
                return reply;
            }
        }
    } else {
        let Some(path) = request.payload() else {
            return reply;
        };
        if !valid_path(path) {
            return reply;
        }
        let mut found = None;
        for index in 0..ENTRIES {
            if let Some((name, bytes)) = entry(index) {
                if same_bytes(name, path) {
                    found = Some(bytes);
                    break;
                }
            }
        }
        let Some(bytes) = found else {
            reply.status = NOT_FOUND;
            return reply;
        };
        let Some(tail) = bytes.get(request.offset as usize..) else {
            reply.status = RANGE;
            return reply;
        };
        (
            tail.get(..tail.len().min(PAYLOAD)).unwrap_or(&[]),
            bytes.len(),
        )
    };
    reply.status = OK;
    reply.total = total as u32;
    reply.len = data.len() as u8;
    for (i, &byte) in data.iter().enumerate() {
        let Some(to) = reply.data.get_mut(i) else {
            reply.status = INVALID;
            reply.len = 0;
            reply.total = 0;
            reply.data.fill(0);
            return reply;
        };
        *to = byte;
    }
    reply
}

#[cfg(test)]
mod tests;
