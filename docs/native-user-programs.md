# Separately Built User Programs

PUSERBIN1 is a development build/extraction contract for original PooleOS
user-space programs. It is not PXABI1 admission, a signature, a general loader
or PINIT1 activation. Compilation and host tests do not prove native execution.

## Programs

PooleInit implements the first service-control loop: request counter startup,
validate its ready response, then issue strictly sequenced advances and validate
reported values. PooleCounter owns its state and responds through IPC. There is
no shell, console, host API, I/O-port access, heap allocator or kernel dependency.
Neither program launches children or restarts failed services yet.

The standalone Cargo workspace builds both programs from shared user-side Rust
source, independently of the kernel. This deliberately avoids adding dependencies
to the kernel or changing its existing qualified startup path. The shared runtime
is not a kernel implementation reused in user mode.

## Startup And Calls

The assembly entry clears RBP and calls Rust with the initial aligned stack,
giving the Rust callee the expected return-address alignment. PSTART1 supplies
RDI/RSI/RDX as block address/length/version. This development runtime requires the
existing block at0x40003000 and96..512 bytes; only the kernel's mapped-stack contract
justifies dereferencing it. Numeric checks alone are not a mapping proof.

The independent decoder requires the canonical header, three packed arguments,
zero reserved fields/unused offsets/padding and no overlaps, holes or extra blocks.
Arguments are role (init or counter), receive handle and send handle. Handles use
exactly16 uppercase hexadecimal digits, nonzero and distinct. The decoder returns
owned numeric values before entering the service loop; it retains no argument
references. Handle text does not grant authority. Kernel capability tables must
authenticate the caller and enforce rights independently.

PSABI1 version1 send/receive/wait/exit use the existing register convention.
Copy-capable inline assembly has a compiler memory clobber; RCX/R11 and result
registers are explicit. On Again, wait for advisory readable/writable readiness
and retry the actual operation. Other errors terminate the process explicitly.

## Service Protocol

PSVC1 has32-byte messages: eight-byte magic PSVC1 plus three NUL bytes, then
little-endian64-bit kind, sequence and value. Start/Ready use sequence/value0.
Advance uses the next sequence and value1; Value returns that sequence as value.
Unexpected kinds, replay, gaps, invalid values and sequence exhaustion reject.
Counter state commits only after successful response transmission. Transport
failure exits; this is not a durable retry or restart protocol.

There are15 host tests for startup boundaries, independent snapshots, malformed
headers/offsets/handles, exact wire shape, ordered progress, failure-before-commit,
replay, wrong replies and overflow. Debug/release runs overlap. Native IPC,
preemption, stack/FP preservation and death recovery still require integration.

## Artifact Rules

The linker enforces entry0, at most4096 code bytes and no writable/GOT/dynamic/
relocation data. Programs use PIC code generation, checked arithmetic, no red zone
and abort-on-panic. Bounds are checked explicitly rather than disabling checks;
failure-report formatting paths are excluded by returning errors. Small public
runtime functions are inline-capable so cross-crate GOT calls are not required.
LTO is off, matching the existing toolchain strategy.

The independent Python inspector requires ELF64/x86-64, one RX PT_LOAD, exact
file/memory size, one allocated .text section, bounded section tables and entry
initialization. It extracts exactly that segment; it does not certify arbitrary
machine-code semantics. Object relocations must be local PC-relative references.
The current artifact pins code independently of the stripped ELF container.

Qualification builds twice in separate target directories, compares complete
ELF and extracted bytes directly, hashes source and compiler/linker/sysroot inputs
before/after, and retains failures. This is conventional Rust/LLVM compilation,
not direct PooleGlyph machine-language generation or production signing.

Run the workspace Python runtime with:
```powershell
python -B tools/qualify_native_user_programs.py --work-dir outputs/user-program-qualification
```
Use a new work directory each time. Outputs are not automatically executed.

## Next Integration

Provide the exact built code bytes to owned PSTART1 construction, grant authentic
receive/send capabilities through atomic admission and run both programs in a
separate normal-session boot path. Prove bidirectional progress under real CPL3
preemption, malformed startup denial and peer death/recovery. Keep diagnostic
fault injection out of normal startup, but retain its separate qualification.
Then add confined console/input, efficient idle, shell/files/apps and actual
interactive optical ISO acceptance. General executable trust, signed service
activation, supervision and the complete robust microkernel remain open.
