# Native User Console

Cycle 262 implementation contract, 2026-10-11. Status: bounded native echo and
default-regression qualification pass; see the [checkpoint](checkpoints/cycle262-native-user-console.md).
The invariants below were frozen before implementation. This is an unsigned emulator
development profile, not production hardware authority or an integration ISO.

## Scope and Alternatives

USI-3 needs input/output before an interactive shell. Choose a separately compiled
PooleConsole driver using a confined COM2 byte-port capability. The existing
PooleInit/PooleCounter IPC pair continues in separate roots. A kernel shell would
violate the microkernel boundary. Direct user IOPL is too broad. Virtio console
remains the scalable driver path but requires PCI/queue/DMA authority not yet
qualified. A framebuffer/keyboard driver also needs additional device ownership.
Keep those work items open; do not treat a serial echo service as a desktop.

## Frozen Invariants

- UC1: only explicit development-console builds expose PSABI1 operations 15/16.
  Ordinary unsigned boot remains denied. Existing default diagnostics stay intact.
- UC2: authenticate task identity, root and root generation against the exclusive
  BSP capability owner before any port effect. Only one COM2 owner exists. Handles
  have a separate type tag and nonwrapping generation. Detach revokes authority
  before memory is freed; failed admission consumes issued generations.
- UC3: offsets 0..7 only, byte values only, no user pointers, one in/out instruction
  per successful operation, no kernel polling. No COM1/debugcon/raw-port choice,
  delegation, IRQ/DMA permission, IOPL grant or writable I/O bitmap.
- UC4: writes allow data/scratch bytes, IER/DLM=0, FCR in {0,1,7}, LCR in {3,131},
  MCR in {0,3}. Status writes, IRQ enabling, break, loopback and DMA mode reject
  before hardware access. Trusted quiescence establishes interrupt-disabled state
  after admission/before dispatch, and again after device-owner revocation.
- UC5: driver policy and bounded buffering execute at CPL3 in independently built
  user code. Scheduling budgets, root restoration, runtime accounting and owned
  reap remain active. Console termination does not cancel the independent pair.
- UC6: host input and user output use a separate local COM2 channel. Untrusted
  bytes never qualify kernel markers. Two fresh boots use different host inputs;
  malformed startup authority must fail without affecting the surviving pair.
- UC7: two independent program/kernel builds must match; bind exact inputs and
  capture failures. No stale receipt is relabeled current. Fixed kernel bounds
  and guest timeouts may not be raised merely to make qualification pass.

Verification: hostile host tests for authority/ABI/register policy, bounded
driver model tests, native input/output and termination observations, original
profile regression, exact-source receipts and publication-boundary checks. A
failed/unrun tier remains explicitly unqualified. No phase closure is implied.

## ABI and Resource Lifecycle

Operations 15 (read8) and 16 (write8): RSI=capability, RDX=register offset,
R10=0/read or byte/write; RDI=1; R8/R9=0. Return RAX=status and RDX=read byte
or zero. Type tag 4, slot 1, high 32 bits generation. The only resource maps
to 0x2f8..0x2ff. Admission has no hardware effects. Before first entry the
trusted adapter clears DLAB, IER and MCR and resets FIFOs. The user driver sets
its baud divisor and performs all transmit/receive polling. Revocation prevents
further calls; quiescence resets FIFOs before any potential future owner.

The 16550 register layout and DLAB/interrupt controls are checked against
[TI TL16C550C Rev. I, section 7.7](https://www.ti.com/lit/ds/symlink/tl16c550c.pdf).
Emulator chardev configuration follows the
[QEMU invocation reference](https://www.qemu.org/docs/master/system/invocation.html).
The restricted policy above is PooleOS's design, not a hardware certification.

The first guest exposed OVMF terminal controls on COM2 before native entry.
Capture retains this prefix, bounded to 4096 bytes and restricted to the observed
ESC[2J, ESC[01;01H and ESC[=3h tokens, the two exact fixed-profile BdsDxe boot
messages, and PooleBoot's fixed UEFI proof-of-life line. The second attempt
exposed those text messages; the prior qualified COM1 log and boot source confirm
them. Unknown text/control bytes fail. Partial
tokens are allowed only while receiving, never in final acceptance. Application
output after this prefix must equal the full user banner and independent host
input byte-for-byte. Bad-handle runs must emit zero application bytes. This
classification does not make the control prefix trusted kernel evidence.

## Remaining Integration Work

Three images consume39 PMM pages before console exit and26 afterward. Only the
console feature raises the task-image quota from32 to48; the default remains32.
Kernel image geometry remains205/208 pages and the guarded stack stays36 pages.
No kernel layout, timer, dispatch or guest time bound was enlarged for acceptance.

Device waits/efficient idle, supervised driver restart, user-space console IPC,
shell, read-only bundled files, two usable applications, framebuffer/input seats,
optical ISO qualification and full signed production admission remain open.
The complete robust microkernel, PooleGlyph/PDC and accessible PooleGlass remain
required after the integration ISO milestone.
