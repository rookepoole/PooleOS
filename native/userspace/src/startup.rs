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
pub fn supervisor(bytes: &[u8], version: u64) -> Result<(u64, u32), Error> {
    let args = arguments::<3>(bytes, version)?;
    if args[0] != b"supervisor" {
        return Err(Error::Role);
    }
    let limit = handle(args[2])?;
    if !(1..=16).contains(&limit) {
        return Err(Error::Layout);
    }
    Ok((handle(args[1])?, limit as u32))
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct ConsoleIpcBoot {
    pub port: Option<u64>,
    pub receive: u64,
    pub send: u64,
    pub peer: crate::console_ipc::Peer,
}

#[inline(always)]
pub fn control_shell(bytes: &[u8], version: u64) -> Result<(ConsoleIpcBoot, [u64; 2]), Error> {
    let args = arguments::<6>(bytes, version)?;
    if args[0] != b"control-shell" {
        return Err(Error::Role);
    }
    let receive = handle(args[1])?;
    let send = handle(args[2])?;
    if receive == send {
        return Err(Error::Handle);
    }
    Ok((
        ConsoleIpcBoot {
            port: None,
            receive,
            send,
            peer: crate::console_ipc::Peer::from_packed(handle(args[3])?)
                .map_err(|_| Error::Handle)?,
        },
        [handle(args[4])?, handle(args[5])?],
    ))
}

#[derive(Clone, Copy)]
pub struct FileShellBoot {
    pub console: ConsoleIpcBoot,
    pub factories: [u64; 2],
    pub endpoint: u64,
    pub peer: u64,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct ApplicationBoot {
    pub control: u64,
    pub control_peer: u64,
    pub files: u64,
    pub file_peer: u64,
}
#[inline(always)]
pub fn application(
    bytes: &[u8],
    version: u64,
    kind: crate::apps::Kind,
) -> Result<ApplicationBoot, Error> {
    let args = arguments::<5>(bytes, version)?;
    application_args(args, kind)
}
#[inline(always)]
pub fn window_application(
    bytes: &[u8],
    version: u64,
    kind: crate::apps::Kind,
) -> Result<(ApplicationBoot, u64), Error> {
    let args = arguments::<6>(bytes, version)?;
    let boot = application_args([args[0], args[1], args[2], args[3], args[4]], kind)?;
    let surface = handle(args[5])?;
    if surface == boot.control
        || surface == boot.files
        || surface >> 32 == 0
        || surface & 0xffff0000 != 0x10000
        || surface & 0xffff == 0
    {
        return Err(Error::Handle);
    }
    Ok((boot, surface))
}
#[inline(always)]
fn application_args(args: [&[u8]; 5], kind: crate::apps::Kind) -> Result<ApplicationBoot, Error> {
    let role: &[u8] = match kind {
        crate::apps::Kind::Text => b"text-app",
        crate::apps::Kind::Numbers => b"numbers-app",
    };
    if !crate::files::same_bytes(args[0], role) {
        return Err(Error::Role);
    }
    let boot = ApplicationBoot {
        control: handle(args[1])?,
        control_peer: peer(args[2])?,
        files: handle(args[3])?,
        file_peer: peer(args[4])?,
    };
    if boot.control == boot.files
        || boot.control_peer == boot.file_peer
        || [boot.control, boot.files]
            .iter()
            .any(|&h| h >> 32 == 0 || h & 0xffff0000 != 1 << 16 || h & 0xffff == 0)
    {
        return Err(Error::Handle);
    }
    Ok(boot)
}
#[inline(always)]
fn peer(bytes: &[u8]) -> Result<u64, Error> {
    let value = handle(bytes)?;
    crate::console_ipc::Peer::from_packed(value).map_err(|_| Error::Handle)?;
    Ok(value)
}
#[inline(always)]
pub fn file_shell(bytes: &[u8], version: u64) -> Result<FileShellBoot, Error> {
    file_shell_role(bytes, version, b"file-shell")
}
#[inline(always)]
pub fn application_shell(bytes: &[u8], version: u64) -> Result<FileShellBoot, Error> {
    file_shell_role(bytes, version, b"app-shell")
}
#[inline(always)]
pub fn launch_shell(bytes: &[u8], version: u64) -> Result<FileShellBoot, Error> {
    file_shell_role(bytes, version, b"launch-shell")
}
#[inline(always)]
fn file_shell_role(bytes: &[u8], version: u64, role: &[u8]) -> Result<FileShellBoot, Error> {
    let args = arguments::<8>(bytes, version)?;
    if !crate::files::same_bytes(args[0], role) {
        return Err(Error::Role);
    }
    let receive = handle(args[1])?;
    let send = handle(args[2])?;
    let endpoint = handle(args[6])?;
    if receive == send || endpoint == receive || endpoint == send {
        return Err(Error::Handle);
    }
    Ok(FileShellBoot {
        console: ConsoleIpcBoot {
            port: None,
            receive,
            send,
            peer: crate::console_ipc::Peer::from_packed(peer(args[3])?)
                .map_err(|_| Error::Handle)?,
        },
        factories: [handle(args[4])?, handle(args[5])?],
        endpoint,
        peer: peer(args[7])?,
    })
}
#[inline(always)]
pub fn file_init(bytes: &[u8], version: u64) -> Result<(u64, u64), Error> {
    let args = arguments::<3>(bytes, version)?;
    if args[0] != b"file-init" {
        return Err(Error::Role);
    }
    Ok((handle(args[1])?, peer(args[2])?))
}
#[inline(always)]
pub fn file_server(bytes: &[u8], version: u64) -> Result<(u64, [u64; 2]), Error> {
    file_server_role(bytes, version, b"file-service")
}
#[inline(always)]
pub fn application_file_server(bytes: &[u8], version: u64) -> Result<(u64, [u64; 2]), Error> {
    file_server_role(bytes, version, b"app-file-service")
}
#[inline(always)]
fn file_server_role(bytes: &[u8], version: u64, role: &[u8]) -> Result<(u64, [u64; 2]), Error> {
    let args = arguments::<4>(bytes, version)?;
    if !crate::files::same_bytes(args[0], role) {
        return Err(Error::Role);
    }
    let peers = [peer(args[2])?, peer(args[3])?];
    if peers[0] == peers[1] {
        return Err(Error::Handle);
    }
    Ok((handle(args[1])?, peers))
}

#[inline(always)]
pub fn diagnostic(bytes: &[u8], version: u64) -> Result<bool, Error> {
    match arguments::<1>(bytes, version)?[0] {
        b"worker" => Ok(false),
        b"fault" => Ok(true),
        _ => Err(Error::Role),
    }
}
#[inline(always)]
pub fn console_ipc(bytes: &[u8], version: u64, server: bool) -> Result<ConsoleIpcBoot, Error> {
    let (port, receive, send, peer) = if server {
        let args = arguments::<5>(bytes, version)?;
        if args[0] != b"console-service" {
            return Err(Error::Role);
        }
        (
            Some(handle(args[1])?),
            handle(args[2])?,
            handle(args[3])?,
            handle(args[4])?,
        )
    } else {
        let args = arguments::<4>(bytes, version)?;
        if args[0] != b"console-client" {
            return Err(Error::Role);
        }
        (None, handle(args[1])?, handle(args[2])?, handle(args[3])?)
    };
    if receive == send {
        return Err(Error::Handle);
    }
    Ok(ConsoleIpcBoot {
        port,
        receive,
        send,
        peer: crate::console_ipc::Peer::from_packed(peer).map_err(|_| Error::Handle)?,
    })
}
#[inline(always)]
pub fn window_console(bytes: &[u8], version: u64) -> Result<(ConsoleIpcBoot, u64), Error> {
    let a = arguments::<6>(bytes, version)?;
    if a[0] != b"window-console" {
        return Err(Error::Role);
    }
    let port = handle(a[1])?;
    let receive = handle(a[2])?;
    let send = handle(a[3])?;
    let surface = handle(a[5])?;
    if port != 0x100040001
        || receive != 0x100010001
        || send != 0x100010002
        || surface != 0x100010003
    {
        return Err(Error::Handle);
    }
    Ok((
        ConsoleIpcBoot {
            port: Some(port),
            receive,
            send,
            peer: crate::console_ipc::Peer::from_packed(peer(a[4])?).map_err(|_| Error::Handle)?,
        },
        surface,
    ))
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
    #[test]
    fn launch_shell_requires_distinct_opt_in_role_and_existing_capability_layout() {
        let args: [&[u8]; 8] = [
            b"launch-shell",
            b"0000000100010001",
            b"0000000100010002",
            b"0000000100000002",
            b"0000000100060001",
            b"0000000100060002",
            b"0000000100010003",
            b"0000000100000001",
        ];
        let boot = launch_shell(&block(args), 1).unwrap();
        assert_eq!(boot.factories, [0x100060001, 0x100060002]);
        assert_eq!(boot.console.send, 0x100010002);
        assert!(application_shell(&block(args), 1).is_err());
        assert!(launch_shell(&block(args), 2).is_err());
        for index in [0, 2, 3, 6, 7] {
            let mut bad = args;
            bad[index] = match index {
                0 => b"app-shell",
                2 | 6 => args[1],
                _ => b"0000000000000001",
            };
            assert!(launch_shell(&block(bad), 1).is_err());
        }
    }
    #[test]
    fn window_application_startup_requires_third_typed_distinct_endpoint() {
        let a: [&[u8]; 6] = [
            b"text-app",
            b"0000000100010001",
            b"0000000100000003",
            b"0000000100010002",
            b"0000000100000001",
            b"0000000100010003",
        ];
        assert_eq!(
            window_application(&block(a), 1, crate::apps::Kind::Text)
                .unwrap()
                .1,
            0x100010003
        );
        assert!(application(&block(a), 1, crate::apps::Kind::Text).is_err());
        for bad in [
            b"0000000100010001",
            b"0000000100010002",
            b"0000000100080001",
            b"0000000000010003",
        ] {
            let mut b = a;
            b[5] = bad;
            assert!(window_application(&block(b), 1, crate::apps::Kind::Text).is_err());
        }
        assert!(window_application(&block(a), 2, crate::apps::Kind::Text).is_err());
    }
    #[test]
    fn window_console_startup_does_not_accept_legacy_roles_or_mixed_channels() {
        let a: [&[u8]; 6] = [
            b"window-console",
            b"0000000100040001",
            b"0000000100010001",
            b"0000000100010002",
            b"0000000100000003",
            b"0000000100010003",
        ];
        assert!(window_console(&block(a), 1).is_ok());
        assert!(console_ipc(&block(a), 1, true).is_err());
        for i in [1, 2, 3, 5] {
            let mut b = a;
            b[i] = b"0000000200010003";
            assert!(window_console(&block(b), 1).is_err());
        }
        let mut b = a;
        b[0] = b"console-service";
        assert!(window_console(&block(b), 1).is_err());
    }
    use std::vec::Vec;
    fn block<const N: usize>(args: [&[u8]; N]) -> Vec<u8> {
        let mut bytes = std::vec![0; 96];
        bytes[..8].copy_from_slice(b"PSTART1\0");
        bytes[16..24].copy_from_slice(&(N as u64).to_le_bytes());
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
    fn application_startup_requires_role_and_distinct_typed_channels() {
        let args: [&[u8]; 5] = [
            b"text-app",
            b"0000000200010001",
            b"0000000100000003",
            b"0000000200010002",
            b"0000000100000001",
        ];
        let boot = application(&block(args), 1, crate::apps::Kind::Text).unwrap();
        assert_eq!(boot.control, 0x200010001);
        assert_eq!(boot.files, 0x200010002);
        assert!(application(&block(args), 2, crate::apps::Kind::Text).is_err());
        assert!(application(&block(args), 1, crate::apps::Kind::Numbers).is_err());
        for (index, value) in [
            (3, args[1]),
            (4, args[2]),
            (1, b"0000000100060001"),
            (2, b"0000000000000003"),
            (3, b"0000000100010000"),
        ] {
            let mut bad = args;
            bad[index] = value;
            assert!(application(&block(bad), 1, crate::apps::Kind::Text).is_err());
        }
        let mut numbers = args;
        numbers[0] = b"numbers-app";
        assert!(application(&block(numbers), 1, crate::apps::Kind::Numbers).is_ok());
        assert!(application(&block([args[0]]), 1, crate::apps::Kind::Text).is_err());
    }
    #[test]
    fn application_service_roles_cannot_be_confused_with_legacy_file_roles() {
        let args: [&[u8]; 8] = [
            b"app-shell",
            b"0000000100010001",
            b"0000000100010002",
            b"0000000100000002",
            b"0000000100060001",
            b"0000000100060002",
            b"0000000100010003",
            b"0000000100000001",
        ];
        assert!(application_shell(&block(args), 1).is_ok());
        assert!(file_shell(&block(args), 1).is_err());
        assert!(application_shell(&block(args), 2).is_err());
        for i in [0, 6, 7] {
            let mut bad = args;
            bad[i] = match i {
                0 => b"file-shell",
                6 => args[1],
                _ => b"0000000000000001",
            };
            assert!(application_shell(&block(bad), 1).is_err());
        }
        let args: [&[u8]; 4] = [
            b"app-file-service",
            b"0000000100010001",
            b"0000000100000000",
            b"0000000100000003",
        ];
        assert!(application_file_server(&block(args), 1).is_ok());
        assert!(file_server(&block(args), 1).is_err());
        assert!(application_file_server(&block(args), 2).is_err());
        let mut bad = args;
        bad[3] = bad[2];
        assert!(application_file_server(&block(bad), 1).is_err());
    }
    #[test]
    fn file_roles_require_exact_counts_peers_and_separate_channels() {
        let args: [&[u8]; 8] = [
            b"file-shell",
            b"0000000100010001",
            b"0000000100010002",
            b"0000000100000002",
            b"0000000100060001",
            b"0000000100060002",
            b"0000000100010003",
            b"0000000100000001",
        ];
        let boot = file_shell(&block(args), 1).unwrap();
        assert_eq!(boot.endpoint, 0x100010003);
        assert_eq!(boot.peer, 0x100000001);
        for index in [1, 2] {
            let mut bad = args;
            bad[6] = bad[index];
            assert!(file_shell(&block(bad), 1).is_err());
        }
        let mut bad = args;
        bad[7] = b"0000000000000001";
        assert!(file_shell(&block(bad), 1).is_err());
        assert!(file_shell(&block(args), 2).is_err());
        assert!(file_shell(&block([args[0], args[1]]), 1).is_err());
        assert_eq!(
            file_init(
                &block([b"file-init", b"0000000100010001", b"0000000100000001"]),
                1
            ),
            Ok((0x100010001, 0x100000001))
        );
        assert_eq!(
            file_server(
                &block([
                    b"file-service",
                    b"0000000100010001",
                    b"0000000100000000",
                    b"0000000100000003"
                ]),
                1
            ),
            Ok((0x100010001, [0x100000000, 0x100000003]))
        );
        assert!(
            file_server(
                &block([
                    b"file-service",
                    b"0000000100010001",
                    b"0000000100000000",
                    b"0000000100000000"
                ]),
                1
            )
            .is_err()
        );
    }
    #[test]
    fn control_shell_has_exact_separate_console_and_factory_arguments() {
        let args: [&[u8]; 6] = [
            b"control-shell",
            b"0000000100010001",
            b"0000000100010002",
            b"0000000100000002",
            b"0000000100060001",
            b"0000000100060002",
        ];
        let bytes = block(args);
        let (boot, factories) = control_shell(&bytes, 1).unwrap();
        assert_eq!(boot.port, None);
        assert_eq!((boot.receive, boot.send), (0x100010001, 0x100010002));
        assert_eq!(factories, [0x100060001, 0x100060002]);
        for n in 0..bytes.len() {
            assert!(control_shell(&bytes[..n], 1).is_err());
        }
        for index in 0..6 {
            let mut bad = args;
            bad[index] = b"invalid";
            assert!(control_shell(&block(bad), 1).is_err());
        }
        let mut bad = args;
        bad[2] = args[1];
        assert!(control_shell(&block(bad), 1).is_err());
        assert!(control_shell(&bytes, 2).is_err());
        assert!(console_ipc(&bytes, 1, false).is_err());
    }
    #[test]
    fn diagnostic_roles_are_exact_and_grant_no_handles() {
        assert_eq!(diagnostic(&block([&b"worker"[..]]), 1), Ok(false));
        assert_eq!(diagnostic(&block([&b"fault"[..]]), 1), Ok(true));
        for role in [&b""[..], b"Fault", b"worker ", b"fault2"] {
            assert!(diagnostic(&block([role]), 1).is_err());
        }
        assert!(diagnostic(&block([&b"worker"[..], b"authority"]), 1).is_err());
        assert!(diagnostic(&block([&b"worker"[..]]), 0).is_err());
    }
    #[test]
    fn supervisor_policy_is_copied_and_bounded_without_minting_authority() {
        let mut bytes = block([b"supervisor", b"0000000100060001", b"0000000000000002"]);
        assert_eq!(supervisor(&bytes, 1), Ok((0x100060001, 2)));
        bytes.fill(0);
        assert!(supervisor(&bytes, 1).is_err());
        for n in [
            b"0000000000000000",
            b"0000000000000011",
            b"FFFFFFFFFFFFFFFF",
        ] {
            assert!(supervisor(&block([b"supervisor", b"0000000100060001", n]), 1).is_err());
        }
        assert!(supervisor(&valid(), 1).is_err());
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
