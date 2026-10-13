# Native Command Shell

PSHELL1, development-only, Cycle270. PooleShell is an independently compiled
original Rust user program, not PooleGlyph-generated code or a kernel interpreter.
Its PSTART1 role is the existing `console-client` transport role. It has no UART
port grant: all terminal traffic goes through the separate PooleConsoleService
using authenticated PCS1/PRPC1 requests. No kernel source changes are needed.

## Behavior

- `help`, `version`, `echo TEXT`, and `exit` are actual user-space builtins.
- Exact ASCII command tokens; no leading-space trimming, quoting, expansion,
  pipelines, completion, history, or scripting is implied.
- A line holds at most64 printable ASCII bytes. CR/LF submit; CRLF submits once.
- Backspace/delete edit. Ctrl-C discards the line. Ctrl-D closes only an empty,
  valid line; otherwise it is ignored and does not execute partial input.
- Overflow, tab, escape, NUL, other unsupported controls, or non-ASCII input
  reject the entire line until submission or Ctrl-C. Backspace does not clear
  that rejection. A valid truncated prefix is never executed.
- Output is chunked into at most16-byte console messages. Each poll performs at
  most one IPC operation. Send/receive backpressure preserves request state.
- Replies must match kind and nonwrapping sequence. Close waits for the console
  drain/close reply before exit0. Revocation exits163; other protocol errors161,
  startup160, panic162. The kernel's existing retirement frees owned resources.

The serial terminal is the current input/output surface. No local keyboard,
graphical terminal, display shell, filesystem, application launch UI, or optical
ISO session is provided by this increment. Builtins are not the two useful apps.

## Build And Admission

Cycle273 update: the bounded loader/extractor now permits up to four RX pages.
Eight programs reproduce with60 user tests per profile. The3569-byte shell itself
is unchanged; its interactive guest evidence below remains Cycle270, not a fresh
shell replay. See [multipage evidence](checkpoints/cycle273-bounded-multipage-executables.md).
The following build measurements describe the historical shell introduction.

`tools/qualify_native_user_programs.py` builds seven binaries twice, checks literal
ELF/code equality, and runs58 runtime tests in both debug/release. Shell code is
3569 bytes within the unchanged4096-byte RX page. No writable data, imports,
dynamic loading or absolute runtime relocations are admitted. A non-inlined poll
boundary avoids duplicating protocol code in the startup function. Explicit
checked accesses avoid compiler panic dependencies without unchecked memory.

The ELF extractor now permits exactly RX section flags6 or22. The extra flag16
is SHF_MERGE propagated from constants; it does not grant write permission. Entry
size remains0; all other flags and program-header permissions remain strict.
Object auditing resolves each relocation's actual local symbol and read-only
section, instead of assuming local symbol names start with `.text.`/`.rodata.`.
Undefined/global, writable, out-of-range and absolute targets remain rejected.
This follows LLD's flag-union behavior in its
[output-section implementation](https://raw.githubusercontent.com/llvm/llvm-project/main/lld/ELF/OutputSections.cpp).
The inspected pinned compiler's actual bytes, not that upstream reference alone,
establish this build's behavior.

## Qualification

`tools/qualify_native_shell.py --work-dir outputs/<fresh-name> --program-dir
outputs/<qualified-program-build>` produces development VM captures, not an ISO.
Two independent normal kernels must be byte-equal; the denied-peer kernel must
differ. The build gate still checks208 reserved image pages,36 guarded stack
pages and W^X. Current shell profiles occupy113 image pages.

Each guest has a120-second bound, no guest network or host filesystem share,
fresh OVMF variables and read-only generated media. Host challenges are selected
after compilation. One input byte at a time is acknowledged by exact output;
two live observations precede input, and two retired observations plus at least
512 dispatches are required. COM2 bytes, including forged kernel-looking text,
never become COM1/debugcon kernel evidence. Transfer/media bindings and hostile
marker mutations are independently rechecked.

The reused PSESSION4 marker summary alone retains `shell=false`: kernel scheduling
markers cannot prove command semantics. PSHELL1 adds exact independently built
program identity and fresh challenge input/output before claiming a native shell.

Next: connect genuine application lifecycle/status requests and a user-space
read-only bundled-file service, then two useful separate applications and optical
ISO acceptance. Multipage executable admission, trust, robust supervisor/cleanup,
idle, full stack bounds and the complete production microkernel remain open.
