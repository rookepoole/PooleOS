use poolekernel::ByteSink;

const COM1_BASE: u16 = 0x03f8;
const DEBUGCON_PORT: u16 = 0x0402;
const TRANSMIT_READY: u8 = 1 << 5;
const MAX_READY_POLLS: usize = 4096;

pub struct Com1 {
    available: bool,
}

impl Com1 {
    /// Initializes the fixed legacy COM1 candidate with a bounded loopback test.
    ///
    /// # Safety
    ///
    /// The caller must execute at a privilege level permitted to access x86 I/O ports.
    pub unsafe fn initialize() -> Self {
        // SAFETY: the caller owns the privileged fixed-port probe for this early boundary.
        unsafe {
            outb(COM1_BASE + 1, 0x00);
            outb(COM1_BASE + 3, 0x80);
            outb(COM1_BASE, 0x03);
            outb(COM1_BASE + 1, 0x00);
            outb(COM1_BASE + 3, 0x03);
            outb(COM1_BASE + 2, 0xc7);
            outb(COM1_BASE + 4, 0x1e);
            outb(COM1_BASE, 0xae);
        }
        // SAFETY: this reads only the fixed loopback register configured above.
        let available = unsafe { inb(COM1_BASE) == 0xae };
        if available {
            // SAFETY: restore normal modem-control output for the same fixed UART.
            unsafe { outb(COM1_BASE + 4, 0x0f) };
        }
        Self { available }
    }

    pub const fn available(&self) -> bool {
        self.available
    }
}

impl ByteSink for Com1 {
    fn write_byte(&mut self, byte: u8) {
        if !self.available {
            return;
        }
        for _ in 0..MAX_READY_POLLS {
            // SAFETY: availability was established by the bounded fixed-port probe.
            if unsafe { inb(COM1_BASE + 5) } & TRANSMIT_READY != 0 {
                // SAFETY: the UART reports that its transmit register is ready.
                unsafe { outb(COM1_BASE, byte) };
                return;
            }
            core::hint::spin_loop();
        }
        self.available = false;
    }
}

pub struct DebugCon;

impl DebugCon {
    pub const fn new() -> Self {
        Self
    }
}

impl ByteSink for DebugCon {
    fn write_byte(&mut self, byte: u8) {
        // SAFETY: PKXFER1's QEMU-only profile reserves this fixed debugcon port.
        unsafe { outb(DEBUGCON_PORT, byte) };
    }
}

pub fn halt_forever() -> ! {
    loop {
        // SAFETY: the terminal kernel state intentionally disables interrupts and halts.
        unsafe { core::arch::asm!("cli", "hlt", options(nomem, nostack)) };
    }
}

unsafe fn outb(port: u16, value: u8) {
    // SAFETY: the caller supplies a port for which it owns the privileged I/O operation.
    unsafe {
        core::arch::asm!(
            "out dx, al",
            in("dx") port,
            in("al") value,
            options(nomem, nostack, preserves_flags),
        )
    };
}

unsafe fn inb(port: u16) -> u8 {
    let value: u8;
    // SAFETY: the caller supplies a port for which it owns the privileged I/O operation.
    unsafe {
        core::arch::asm!(
            "in al, dx",
            in("dx") port,
            lateout("al") value,
            options(nomem, nostack, preserves_flags),
        )
    };
    value
}
