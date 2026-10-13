//! Opt-in six-role demonstration catalogue, not production process policy.
#![forbid(unsafe_code)]
use crate::{
    capability_ipc::{Rights, admission::Step},
    scheduler_smp::TaskId,
    user_entry::startup::{Arguments, Error},
};

pub fn grants(shell: TaskId, files: TaskId) -> [Step; 2] {
    [
        Step::Inherit {
            source: shell,
            handle: 0x100010001,
            member: 0,
            rights: Rights::SEND,
        },
        Step::Inherit {
            source: files,
            handle: 0x100010001,
            member: 0,
            rights: Rights::SEND,
        },
    ]
}
fn hex(value: u64) -> [u8; 16] {
    let mut text = [b'0'; 16];
    for (i, byte) in text.iter_mut().enumerate() {
        let n = ((value >> ((15 - i) * 4)) & 15) as u8;
        *byte = if n < 10 { b'0' + n } else { b'a' + n - 10 };
    }
    text
}
/// Zero handles are placeholders only. The owned handoff installs actual grants
/// before a child becomes eligible for execution in the exclusive BSP dispatcher.
pub fn arguments(slot: u16, control: u64, files: u64) -> Result<Arguments, Error> {
    let role: &[u8] = match slot {
        4 => b"text-app",
        5 => b"numbers-app",
        _ => return Err(Error::Image),
    };
    if (control == 0) != (files == 0)
        || (control != 0
            && (control == files
                || [control, files]
                    .iter()
                    .any(|&h| h >> 32 == 0 || h & 0xffff0000 != 0x10000 || h & 0xffff == 0)))
    {
        return Err(Error::Image);
    }
    Arguments::new(&[
        role,
        &hex(control),
        b"0000000100000003",
        &hex(files),
        b"0000000100000001",
    ])
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn actual_handles_keep_placeholder_geometry_across_all_generations() {
        for slot in [4, 5] {
            let empty = arguments(slot, 0, 0).unwrap();
            for generation in [1u64, 2, u32::MAX as u64] {
                let control = (generation << 32) | 0x10001;
                let files = (generation << 32) | 0x10002;
                let bound = arguments(slot, control, files).unwrap();
                assert_eq!(empty.bytes().len(), bound.bytes().len());
                assert!(bound.bytes().windows(16).any(|b| b == hex(control)));
                assert!(bound.bytes().windows(16).any(|b| b == hex(files)));
                assert_ne!(empty.bytes(), bound.bytes());
            }
        }
    }
    #[test]
    fn catalogue_rejects_unknown_roles_partial_and_wrong_typed_grants() {
        for slot in [0, 3, 6, u16::MAX] {
            assert!(arguments(slot, 0, 0).is_err());
        }
        for (a, b) in [
            (0, 0x100010002),
            (0x100010001, 0),
            (0x100010001, 0x100010001),
            (0x10001, 0x100010002),
            (0x100020001, 0x100010002),
            (0x100010001, 0x100010000),
        ] {
            assert!(arguments(4, a, b).is_err());
        }
    }
    #[test]
    fn catalogue_has_only_send_inheritance_from_owned_service_endpoints() {
        let shell = TaskId::new(3, 1).unwrap();
        let files = TaskId::new(1, 1).unwrap();
        for (step, source) in grants(shell, files).into_iter().zip([shell, files]) {
            assert_eq!(
                step,
                Step::Inherit {
                    source,
                    handle: 0x100010001,
                    member: 0,
                    rights: Rights::SEND
                }
            );
        }
    }
}
