# Owned Program Startup

PSTART1 is a development bootstrap mechanism for trusted, immutable,
position-independent built-in programs. It supplies copied argument data to an
owned user image. It is not a signature, executable-file parser, PINIT1 activation,
capability grant, user-directed spawn syscall, or the future init service.

## Program And Argument Contract

`Program::new` accepts 1 to 4096 code bytes and an entry offset strictly inside
those bytes. Entry into zero-filled tail is not admitted as the initial entry.
The caller supplies position-independent code; no relocation is performed.
`Program::image` checks arithmetic and existing PKUSER1 code/stack/guard geometry.
The immutable Rust borrow prevents safe caller mutation during construction;
the native exercise uses read-only linked code, not device-writable input.

`Arguments::new` snapshots up to eight byte-string arguments into at most 512
bytes. Embedded NUL is rejected; empty strings and zero arguments are allowed.
Argument data is bytes, not a UTF-8 or shell-escaping policy. Length arithmetic
and terminators are bounded. Reserved fields, unused slots and padding are zero.

The little-endian PSTART1 argument block contains:

| Offset | Meaning |
| --- | --- |
| 0 | Eight-byte magic `PSTART1` followed by NUL |
| 8 | Total block size, rounded to eight bytes |
| 16 | Argument count, 0 through 8 |
| 24 | Reserved zero word |
| 32 | Eight 64-bit offsets relative to the block; unused slots are zero |
| 96 | Packed NUL-terminated argument bytes and zero alignment padding |

The block is copied at the bottom of the one-page user stack. Initial RSP remains
at the existing aligned top, so this is data in the task's own RW/NX stack, not a
second mapping. Programs must copy arguments before stack use can overwrite them;
there is no separately protected argument page or general stack-growth policy.

Initial registers use the existing six-register startup convention: RDI is the
user virtual address of the block, RSI its byte size, RDX is version 1, and
RCX/R8/R9 are zero. Other GPR/FP state follows the existing sanitized entry path.
Offsets and user virtual addresses are never interpreted as kernel pointers or
capability authority. User mutation after entry changes only the task's data.

## Construction And Binding

`Construction::build_program` copies all code bytes at the code-page base and
the argument block into the owned stack before exposing mappings. It zeroes data
pages and checks physical write/readback. The original diagnostic build path
continues placing raw payload bytes at its selected aligned entry offset.

Successful preparation yields a `Startup` record bound to the exact complete
`ImageAdmission`, including root/generation, physical backing and initial frame.
The architectural adapter validates that binding before selecting initial
registers, and cannot replace startup data after install, execution or saved
state. Raw diagnostic arguments cannot override an installed startup record.

This record is metadata, not the memory owner or user authority. The existing
PreparedImage/CpuImage/Slot chain retains resources. Partial copy, readback,
mapping and preparation failures leave an explicit Construction owner for
scrub/retry. Native adapter setup errors retain the prepared image, not only an
error code. Atomic IPC/scheduler publication remains a separate PKADMIT1 step.

## Verification And Limits

Host tests cover exact code and argument copies, unaligned entry inside real
code, zero tails, argument snapshot independence, size/count/NUL boundaries,
changed admission fields, foreign allocator ownership, argument-write failures
including after-effect writes, and failed cleanup followed by retry.

Native generation-16 probes read `init`, `0`/`1` and `--verify` from their own
stack block, validate headers/offsets/strings, and return distinct statuses. The
final receipt, not this document, establishes execution counts and measured
runtime. Malformed program/image inputs are denied and all earlier containment,
IPC, deadline and sustained-dispatch controls remain required.

This does not implement PXABI1 file loading, signed PINIT1 service activation,
multi-page executable segments, relocations, service supervision, user spawn
authority or normal session boot. The PINIT1/PXABI1 trust gates remain closed.
Next: separate normal startup from diagnostics and add a separately built init
runtime with confined console/input, then shell/files/apps and optical ISO
interaction. Full robust microkernel, PooleGlyph/PDC and accessible PooleGlass
obligations remain after the bounded ISO milestone.
