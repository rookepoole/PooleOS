//! x86-64 PSABI1 adapter. No host runtime, I/O ports or kernel implementation link.
use crate::{
    protocol::{self, Message},
    service::{Channel, Error},
    startup::{self, Boot, Role},
};
use core::arch::asm;

/// The native PSTART1 entry contract must supply a live readable argument block.
/// Numeric bounds reject bad metadata; they do not independently prove mapping.
#[inline]
pub unsafe fn boot(
    address: u64,
    bytes: u64,
    version: u64,
    role: Role,
) -> Result<Boot, startup::Error> {
    if address != 0x40003000 || !(96..=512).contains(&bytes) {
        return Err(startup::Error::Header);
    }
    // SAFETY: caller is the PSTART1 entry shim; kernel owns/mapped this stack block.
    let block = unsafe { core::slice::from_raw_parts(address as *const u8, bytes as usize) };
    startup::decode(block, version, role)
}

/// The kernel may copy through address, so this must not use nomem/readonly.
#[inline(always)]
unsafe fn call(number: u64, handle: u64, address: u64, bytes: u64) -> (u64, u64) {
    let status: u64;
    let value: u64;
    unsafe {
        asm!("syscall",
            inlateout("rax") number => status,
            in("rdi") 1u64, in("rsi") handle,
            inlateout("rdx") address => value, in("r10") bytes,
            in("r8") 0u64, in("r9") 0u64,
            lateout("rcx") _, lateout("r11") _,
            options(nostack));
    }
    (status, value)
}

#[inline]
pub fn exit(code: u32) -> ! {
    // SAFETY: PSABI1 Exit copies no user buffer and has no capability side effect.
    unsafe {
        call(2, u64::from(code), 0, 0);
        asm!("ud2", options(noreturn));
    }
}

pub struct Ipc {
    receive: u64,
    send: u64,
}
impl Ipc {
    #[inline]
    pub fn new(boot: Boot) -> Self {
        Self {
            receive: boot.receive,
            send: boot.send,
        }
    }
    #[inline(always)]
    fn transfer(&mut self, wire: &mut [u8; protocol::BYTES], send: bool) -> Result<(), Error> {
        let handle = if send { self.send } else { self.receive };
        loop {
            // SAFETY: wire remains live and exclusively borrowed across the synchronous
            // kernel copy; a suspended call retains the same owned user stack.
            let (status, value) = unsafe {
                call(
                    if send { 3 } else { 4 },
                    handle,
                    wire.as_mut_ptr() as u64,
                    protocol::BYTES as u64,
                )
            };
            match status {
                0 if value == protocol::BYTES as u64 => return Ok(()),
                6 => {
                    // Readiness is advisory; retry the operation after every wakeup.
                    let (status, value) = unsafe { call(5, handle, u64::from(send), 0) };
                    if status != 0 || value != 0 {
                        return Err(Error::Transport);
                    }
                }
                _ => return Err(Error::Transport),
            }
        }
    }
}
impl Channel for Ipc {
    #[inline]
    fn send(&mut self, message: Message) -> Result<(), Error> {
        self.transfer(&mut message.encode(), true)
    }
    #[inline]
    fn receive(&mut self) -> Result<Message, Error> {
        let mut wire = [0; protocol::BYTES];
        self.transfer(&mut wire, false)?;
        Message::decode(&wire).map_err(Error::Protocol)
    }
}

/// Single assembly entry keeps the Rust function's stack at the SysV alignment.
#[macro_export]
macro_rules! entry {
    ($main:path) => {
        core::arch::global_asm!(
            ".section .text.start,\"ax\",@progbits",
            ".global _start",
            "_start:",
            "xor ebp, ebp",
            "call {main}",
            "ud2",
            main = sym $main,
        );
    };
}
