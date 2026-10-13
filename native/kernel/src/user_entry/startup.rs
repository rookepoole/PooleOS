//! Development bootstrap data, not executable trust or capability authority.
#![forbid(unsafe_code)]

use super::{ImageAdmission, InitialImage, MAX_CODE_PAGES};
use poole_handoff::PAGE_BYTES;

pub const CONTRACT_ID: &str = "PSTART1";
pub const MAGIC: [u8; 8] = *b"PSTART1\0";
pub const VERSION: u64 = 1;
pub const MAX_ARGUMENTS: usize = 8;
pub const MAX_BYTES: usize = 512;
pub const HEADER_BYTES: usize = 32 + MAX_ARGUMENTS * 8;

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum Error {
    Program,
    Arguments,
    Image,
}

/// Immutable trusted built-in code. This is not an ELF/PXABI1 parser or signature.
/// The caller must supply position-independent code; no relocations are applied.
pub struct Program<'a> {
    code: &'a [u8],
    entry_offset: usize,
}
impl<'a> Program<'a> {
    pub fn new(code: &'a [u8], entry_offset: usize) -> Result<Self, Error> {
        if code.is_empty()
            || code.len() > (MAX_CODE_PAGES * PAGE_BYTES) as usize
            || entry_offset >= code.len()
        {
            return Err(Error::Program);
        }
        Ok(Self { code, entry_offset })
    }
    pub fn code(&self) -> &[u8] {
        self.code
    }
    pub fn code_pages(&self) -> u64 {
        self.code.len().div_ceil(PAGE_BYTES as usize) as u64
    }
    pub fn image(&self, code_page: u64, stack_page: u64) -> Result<InitialImage, Error> {
        let image = InitialImage {
            code_page,
            code_pages: self.code_pages(),
            entry: code_page
                .checked_add(self.entry_offset as u64)
                .ok_or(Error::Image)?,
            stack_page,
        };
        image.validate().map_err(|_| Error::Image)?;
        Ok(image)
    }
}

/// Owned argument snapshot. Offset strings, zero reserved fields and zero padding
/// contain no host pointers. User modification after entry cannot confer authority.
pub struct Arguments {
    bytes: [u8; MAX_BYTES],
    len: usize,
}
impl Arguments {
    pub fn new(arguments: &[&[u8]]) -> Result<Self, Error> {
        if arguments.len() > MAX_ARGUMENTS {
            return Err(Error::Arguments);
        }
        let mut result = Self {
            bytes: [0; MAX_BYTES],
            len: HEADER_BYTES,
        };
        result.bytes[..8].copy_from_slice(&MAGIC);
        result.bytes[16..24].copy_from_slice(&(arguments.len() as u64).to_le_bytes());
        for (i, argument) in arguments.iter().enumerate() {
            if argument.contains(&0) {
                return Err(Error::Arguments);
            }
            let end = result
                .len
                .checked_add(argument.len())
                .and_then(|v| v.checked_add(1))
                .filter(|&v| v <= MAX_BYTES)
                .ok_or(Error::Arguments)?;
            result.bytes[32 + i * 8..40 + i * 8]
                .copy_from_slice(&(result.len as u64).to_le_bytes());
            result.bytes[result.len..end - 1].copy_from_slice(argument);
            result.len = end;
        }
        result.len = (result.len + 7) & !7;
        result.bytes[8..16].copy_from_slice(&(result.len as u64).to_le_bytes());
        Ok(result)
    }
    pub fn bytes(&self) -> &[u8] {
        &self.bytes[..self.len]
    }
}

/// Bound startup metadata, not an ownership token. Only construction creates it;
/// the existing CpuImage/Slot retains the actual memory and execution authority.
#[derive(Clone, Copy)]
pub struct Startup {
    image: ImageAdmission,
    byte_count: usize,
}
impl Startup {
    pub(super) fn bind(image: ImageAdmission, arguments: &Arguments) -> Self {
        Self {
            image,
            byte_count: arguments.len,
        }
    }
    pub fn registers(&self, image: ImageAdmission) -> Result<[u64; 6], Error> {
        if image != self.image {
            return Err(Error::Image);
        }
        Ok([
            image.initial_frame.rsp - PAGE_BYTES,
            self.byte_count as u64,
            VERSION,
            0,
            0,
            0,
        ])
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::virtual_memory::USER_WINDOW_START as BASE;

    #[test]
    fn program_entry_must_be_inside_code_and_image_geometry_is_checked() {
        for (size, entry) in [(0, 0), (16385, 0), (8, 8), (8, usize::MAX)] {
            assert!(Program::new(&[0x90; 16385][..size], entry).is_err());
        }
        let bytes = [0x90; 4096];
        let p = Program::new(&bytes, 4095).unwrap();
        assert_eq!(
            p.image(BASE, BASE + 3 * PAGE_BYTES).unwrap().entry,
            BASE + 4095
        );
        assert!(p.image(u64::MAX, BASE).is_err());
        assert!(p.image(BASE + 1, BASE + 3 * PAGE_BYTES).is_err());
        assert!(p.image(BASE, BASE).is_err());
    }

    #[test]
    fn program_page_rounding_is_bounded_and_does_not_consume_stack_guards() {
        let bytes = [0x90; (MAX_CODE_PAGES * PAGE_BYTES) as usize];
        for length in [4096, 4097, 8192, 8193, bytes.len()] {
            let p = Program::new(&bytes[..length], length - 1).unwrap();
            let expected = (length as u64).div_ceil(PAGE_BYTES);
            assert_eq!(p.code_pages(), expected);
            let image = p
                .image(BASE + 16 * PAGE_BYTES, BASE + 3 * PAGE_BYTES)
                .unwrap();
            assert_eq!(image.code_pages, expected);
            assert_eq!(
                image.code_end().unwrap(),
                BASE + (16 + expected) * PAGE_BYTES
            );
            if expected > 2 {
                assert!(p.image(BASE, BASE + 3 * PAGE_BYTES).is_err());
            }
        }
    }

    #[test]
    fn arguments_are_owned_offsets_with_zero_tail_and_no_source_alias() {
        let mut source = *b"init";
        let args = Arguments::new(&[&source, b"0", b"--verify"]).unwrap();
        source.fill(b'X');
        let bytes = args.bytes();
        assert_eq!(bytes.len(), 112);
        assert_eq!(&bytes[..8], &MAGIC);
        assert_eq!(&bytes[96..], b"init\x000\0--verify\0");
        for (at, value) in [
            (8, 112u64),
            (16, 3),
            (24, 0),
            (32, 96),
            (40, 101),
            (48, 103),
        ] {
            assert_eq!(&bytes[at..at + 8], &value.to_le_bytes());
        }
        assert!(bytes[56..96].iter().all(|&b| b == 0));
        let empty = Arguments::new(&[]).unwrap();
        assert_eq!(empty.bytes().len(), HEADER_BYTES);
        assert!(empty.bytes()[16..].iter().all(|&b| b == 0));
        let one = Arguments::new(&[b"a"]).unwrap();
        assert!(one.bytes()[98..].iter().all(|&b| b == 0));
    }

    #[test]
    fn argument_count_nul_and_exact_capacity_boundaries_are_enforced() {
        assert!(Arguments::new(&[b"" as &[u8]; 9]).is_err());
        assert!(Arguments::new(&[b"a\0b"]).is_err());
        let maximum = [b'a'; MAX_BYTES - HEADER_BYTES - 1];
        assert_eq!(
            Arguments::new(&[&maximum]).unwrap().bytes().len(),
            MAX_BYTES
        );
        assert!(Arguments::new(&[&maximum, b""]).is_err());
        assert!(Arguments::new(&[&[b'a'; MAX_BYTES]]).is_err());
        assert!(Arguments::new(&[b"" as &[u8]; MAX_ARGUMENTS]).is_ok());
    }
}
