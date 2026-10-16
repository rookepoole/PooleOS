# Native Local Console: PDISPLAY1

Cycle293 development profile, not a completed desktop or production driver.
`development-desktop` explicitly includes the existing native application profile.
Default kernel and serial profiles retain their existing ABI and linker layout.

## Ownership And Transport

The admitted console process derives a nontransferable display/input child token
from its existing exclusive console lease. Every operation authenticates the
actual task, generation, root and root generation. Another task, a forged root,
the UART token in place of the child, and revoked/stale tokens are denied.
The child is not an IPC handle or arbitrary port/MMIO authority.

PSABI1 version1 uses value-only development requests:

| Number | Operation | Arguments and result |
| --- | --- | --- |
| 21 | Open child | UART token; zero remaining fields; returns child token |
| 22 | Dimensions | Child; zero fields; width in low32 and height in high32 |
| 23 | Solid rectangle | Child; four16-bit x/y/width/height fields; RRGGBB color |
| 24 | Monochrome tile | Same rectangle; two24-bit colors; r8 holds an8x8 mask |
| 25 | Keyboard poll | Child; zero fields; raw translated set-1 byte or Again |

All r9 fields remain zero. Only24 may use r8 for these requests. Empty,
out-of-bounds or oversized rectangles and reserved color bits reject. At most
4096 pixels per command and32 queued commands are admitted; full returns Again.
Monochrome tiles are at most8x8; bit y*8+x chooses foreground/background.
No user pointer or physical framebuffer address crosses this ABI.

The retained GOP surface accepts PBP1 RGB1/BGR2, not raw firmware enum numbers.
Geometry is320..4096 by200..2160, stride and byte span are checked, and the
physical identity range must pass existing kernel validation. Bitmask format3
is deliberately unsupported. Kernel command execution occurs only in the exact
retained boot CR3 with interrupts disabled. It runs after slice event handling:
terminated tasks restore their root during retirement, not during run_slice.
Already accepted immutable commands drain before another task dispatches, even
when the owner has exited; no reference into retired task memory is retained.

The backend is exclusive BSP-only, polled, bounded development mediation. It is
not an SMP-safe production display server, isolated GPU driver, time-accounted
compositor, DMA interface or multi-client surface protocol.

## Native Process

`PooleDesktopConsole` is an independently built, position-independent CPL3 image.
It paints the framebuffer and polls the VM keyboard through the child capability.
The existing PCS1 service, shell, file service, Text and Numbers remain separate
native programs. It is not a kernel shell, host-rendered terminal or web mockup.

Rendering policy, the original5x7 ASCII font, cell state, scrolling, cursor and
US keyboard decoding live in user space. The viewport is bounded at80x24 cells;
smaller display modes reduce its dimensions. Scrolling repaints only changed
cells. Stack-backed storage is initialized in place and borrowed, avoiding libc,
allocation, writable ELF data, unresolved imports and implicit memcpy dependencies.
The verified program uses 7964 code bytes/two pages. Desktop kernel layout uses
0x15000 read-only capacity, 124 image pages of the unchanged 208-page reserve,
and the unchanged 36 guarded stack pages.

Keyboard input reads only i8042 status/data ports in the emulated, firmware-
initialized translated set-1 profile. There are no controller reset, A20 or
arbitrary port writes. Auxiliary bytes are discarded; parity/timeout resets
user-space modifiers. Shift, Caps Lock, Ctrl-letter decoding, Enter and Backspace
are supported. This does not establish physical PS/2, USB/HID, virtio-input,
pointer input, international layouts or interrupt-driven input support.

COM2 must still exist: it carries a serial mirror and a qualification oracle.
The visible launcher configures it automatically. Keyboard qualification injects
device scancodes and observes COM2 output only; it never sends serial input.

## Verification And Boundaries

The boot splash keeps its original pixel oracle. This terminal uses a separate
bounded RGB/PPM oracle for geometry, channel order, title, background, visible
ink and a single cursor, plus actual screenshot inspection. VirtualBox PNG
inspection uses the existing bundled Pillow 12.3.0; no image library is in the OS.
Host tests cover capability revocation, syscall fields, geometry, pixel bounds,
queue pressure/order, font/keyboard state, terminal editing and scrolling.

Native scenarios require exact dynamic command responses, six-role 4096-dispatch
progress, file waits, fault/restart and final retirement. VirtualBox checks also
require identical runtime/source/ISO hashes and confirmed owned-VM cleanup.
The GUI may briefly retain a registration lock after poweroff: cleanup retries
only that exact error, at most 8 attempts with 0.5s waits, rechecking UUID/name/
config/state each time. Other errors or changed ownership retain the VM and fail.
Each control command retains its 30s timeout; no frontend is forcibly killed.

Outstanding: isolated input/display services, per-client surfaces/quotas, pointer
and focus routing, compositor/windows, driver/display restart, Unicode/shaping,
PTYs/scrollback/interruptible jobs, persistent data, and accessible PooleGlass.
The known VirtualBox default-diagnostic stage117 and actual watchdog delivery
remain independent open gates. No signing, production layout, main merge,
hardware acceptance or full canonical qualification is implied.

Primary implementation references: the repository PBP1 contract in
`native/handoff/src/lib.rs` and firmware translation in
`native/boot/src/livehandoff.rs`; QEMU's
[i8042 model](https://raw.githubusercontent.com/qemu/qemu/master/hw/input/pckbd.c)
and [PS/2 model](https://raw.githubusercontent.com/qemu/qemu/master/hw/input/ps2.c).
