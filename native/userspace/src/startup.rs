//! Independent user-side decoder. A startup handle is data, not authority.
#![forbid(unsafe_code)]

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum Role {
    Init,
    Counter,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct Boot {
    pub role: Role,
    pub receive: u64,
    pub send: u64,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum Error {
    Header,
    Layout,
    Role,
    Handle,
}

#[inline(always)]
fn word(bytes: &[u8], at: usize) -> Result<u64, Error> {
    let end = at.checked_add(8).ok_or(Error::Header)?;
    Ok(u64::from_le_bytes(
        bytes
            .get(at..end)
            .ok_or(Error::Header)?
            .try_into()
            .map_err(|_| Error::Header)?,
    ))
}

#[inline(always)]
fn handle(bytes: &[u8]) -> Result<u64, Error> {
    if bytes.len() != 16 {
        return Err(Error::Handle);
    }
    let mut value = 0u64;
    for &b in bytes {
        let digit = match b {
            b'0'..=b'9' => b - b'0',
            b'A'..=b'F' => b - b'A' + 10,
            _ => return Err(Error::Handle),
        };
        value = (value << 4) | u64::from(digit);
    }
    if value == 0 {
        return Err(Error::Handle);
    }
    Ok(value)
}

#[inline(always)]
fn arguments<const N: usize>(bytes: &[u8], version: u64) -> Result<[&[u8]; N], Error> {
    if version != 1
        || !(96..=512).contains(&bytes.len())
        || bytes.len() % 8 != 0
        || bytes.get(..8) != Some(b"PSTART1\0")
        || word(bytes, 8)? != bytes.len() as u64
        || N > 8
        || word(bytes, 16)? != N as u64
        || word(bytes, 24)? != 0
        || bytes[32 + N * 8..96].iter().any(|&b| b != 0)
    {
        return Err(Error::Header);
    }
    let mut args = [&[][..]; N];
    let mut cursor = 96;
    for (index, arg) in args.iter_mut().enumerate() {
        if word(bytes, 32 + index * 8)? != cursor as u64 {
            return Err(Error::Layout);
        }
        let tail = bytes.get(cursor..).ok_or(Error::Layout)?;
        let end = tail.iter().position(|&b| b == 0).ok_or(Error::Layout)?;
        *arg = tail.get(..end).ok_or(Error::Layout)?;
        cursor = cursor
            .checked_add(end)
            .and_then(|v| v.checked_add(1))
            .ok_or(Error::Layout)?;
    }
    if cursor.checked_add(7).ok_or(Error::Layout)? & !7 != bytes.len()
        || bytes
            .get(cursor..)
            .ok_or(Error::Layout)?
            .iter()
            .any(|&b| b != 0)
    {
        return Err(Error::Layout);
    }
    Ok(args)
}

#[inline(always)]
pub fn console(bytes: &[u8], version: u64) -> Result<u64, Error> {
    let args = arguments::<2>(bytes, version)?;
    if args[0] != b"console" {
        return Err(Error::Role);
    }
    handle(args[1])
}

#[inline(always)]
pub fn decode(bytes: &[u8], version: u64, expected: Role) -> Result<Boot, Error> {
    let args = arguments::<3>(bytes, version)?;
    let role = match args[0] {
        b"init" => Role::Init,
        b"counter" => Role::Counter,
        _ => return Err(Error::Role),
    };
    if role != expected {
        return Err(Error::Role);
    }
    let boot = Boot {
        role,
        receive: handle(args[1])?,
        send: handle(args[2])?,
    };
    if boot.receive == boot.send {
        return Err(Error::Handle);
    }
    Ok(boot)
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::vec::Vec;
    fn block(args: [&[u8]; 3]) -> Vec<u8> {
        let mut bytes = std::vec![0; 96];
        bytes[..8].copy_from_slice(b"PSTART1\0");
        bytes[16..24].copy_from_slice(&3u64.to_le_bytes());
        for (i, arg) in args.iter().enumerate() {
            let offset = bytes.len() as u64;
            bytes[32 + i * 8..40 + i * 8].copy_from_slice(&offset.to_le_bytes());
            bytes.extend_from_slice(arg);
            bytes.push(0);
        }
        bytes.resize((bytes.len() + 7) & !7, 0);
        let size = bytes.len() as u64;
        bytes[8..16].copy_from_slice(&size.to_le_bytes());
        bytes
    }
    fn valid() -> Vec<u8> {
        block([b"init", b"0000000100010001", b"0000000100010002"])
    }
    #[test]
    fn canonical_snapshot_owns_values_not_argument_references() {
        let mut bytes = valid();
        let boot = decode(&bytes, 1, Role::Init).unwrap();
        bytes.fill(0);
        assert_eq!(
            boot,
            Boot {
                role: Role::Init,
                receive: 0x100010001,
                send: 0x100010002
            }
        );
        assert!(
            decode(
                &block([b"counter", b"0000000100010001", b"0000000100010002"]),
                1,
                Role::Counter
            )
            .is_ok()
        );
    }
    #[test]
    fn rejects_header_version_size_and_unused_authority_slots() {
        let bytes = valid();
        for at in [0, 7, 8, 16, 24, 56, 95] {
            let mut bad = bytes.clone();
            bad[at] ^= 1;
            assert!(decode(&bad, 1, Role::Init).is_err(), "{at}");
        }
        for n in 0..bytes.len() {
            assert!(decode(&bytes[..n], 1, Role::Init).is_err());
        }
        for version in [0, 2, u64::MAX] {
            assert!(decode(&bytes, version, Role::Init).is_err());
        }
        assert!(decode(&[0; 520], 1, Role::Init).is_err());
    }
    #[test]
    fn rejects_overlapping_out_of_range_or_gapped_offsets() {
        for at in [32, 40, 48] {
            for offset in [0, 95, 97, 511, u64::MAX] {
                let mut bytes = valid();
                bytes[at..at + 8].copy_from_slice(&offset.to_le_bytes());
                assert!(decode(&bytes, 1, Role::Init).is_err(), "{at}/{offset}");
            }
        }
    }
    #[test]
    fn rejects_missing_terminator_nonzero_tail_and_extra_padding() {
        let mut bytes = valid();
        bytes[134..].fill(b'X');
        assert!(decode(&bytes, 1, Role::Init).is_err());
        let mut bytes = valid();
        *bytes.last_mut().unwrap() = 1;
        assert!(decode(&bytes, 1, Role::Init).is_err());
        let mut bytes = valid();
        bytes.extend_from_slice(&[0; 8]);
        let n = bytes.len() as u64;
        bytes[8..16].copy_from_slice(&n.to_le_bytes());
        assert!(decode(&bytes, 1, Role::Init).is_err());
    }
    #[test]
    fn roles_and_handles_do_not_accept_ambiguous_text() {
        assert!(decode(&valid(), 1, Role::Counter).is_err());
        for bad in [&b""[..], b"init2", b"Init"] {
            assert!(
                decode(
                    &block([bad, b"0000000100010001", b"0000000100010002"]),
                    1,
                    Role::Init
                )
                .is_err()
            );
        }
        for bad in [
            &b""[..],
            b"1",
            b"0000000000000000",
            b"000000010001000g",
            b"000000010001000a",
            b"0000000100010001",
        ] {
            assert!(decode(&block([b"init", b"0000000100010001", bad]), 1, Role::Init).is_err());
        }
    }
}
