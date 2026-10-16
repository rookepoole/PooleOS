# Native Bundled-File Service

Cycle279, PFILE1. A bounded user-space service for the integration ISO lane, not
a general filesystem, disk driver, VFS, installer or production storage claim.

## Execution And Authority

PooleFiles is separately compiled, relocation/import-free native code executed at
ring3 in its own address space. Four immutable public entries live in its executable
rodata: `/readme.txt`, `/version.txt`, `/numbers.csv` and `/empty.txt`. No host file
is mounted or copied at runtime. There is no write operation or disk authority.
PooleFileShell extends the existing shell/process client; PooleFileInit polls the
version entry through IPC. That health poll is not general service supervision.

The six-owner layout and32 PMM-record capacity remain unchanged:

| Owner | Role | Granted Authority |
| --- | --- | --- |
| 0 | File init | SEND to files1 |
| 1 | File service | Own receive endpoint; kernel-reported client allowlist0/3 |
| 2 | Console service | Own endpoint, SEND to shell3, console I/O grant |
| 3 | File shell | Own endpoint, SEND to console2, SEND to files1; existing process factories |
| 4/5 | Diagnostic children | Existing bounded lifecycle roles; not useful apps |

The eight-step files/console admission is atomic; any failure rolls back.
Clients receive neither file endpoint ownership nor transfer authority. The
file service has no console-port grant. No syscall is added: PFILE1 uses the
existing PSABI1 tracked request/completion10/11 and receive/reply7/8 operations.
Kernel-provided peer identity and reply authority are checked, not payload claims.

## Wire Contract

All integers are little-endian. The payload is exactly64 bytes:

| Offset | Bytes | Field |
| --- | --- | --- |
| 0 | 4 | `PFI1` magic |
| 4 | 1 | Operation: LIST1 or READ2 |
| 5 | 1 | Status: OK0, NOT_FOUND1, INVALID2, RANGE3, END4 |
| 6 | 1 | Used payload bytes,0..40 |
| 7 | 1 | Reserved, must be zero |
| 8 | 8 | Sequence; neither zero nor u64::MAX |
| 16 | 4 | List index or read offset |
| 20 | 4 | Total file bytes; zero in requests |
| 24 | 40 | Payload with zero unused padding |

LIST has an empty request payload. Its reply contains the entry path and total
file size. Index4 returns END; greater indices return RANGE. READ supplies a
canonical flat absolute path and byte offset. A reply contains at most40 bytes,
the unchanged offset and total size. Exact EOF returns OK with zero bytes;
beyond EOF returns RANGE. A valid absent path returns NOT_FOUND.

Paths are2..40 bytes: leading slash, lowercase ASCII letters, digits, dot,
underscore or hyphen. The first filename byte cannot be dot; any `..`, nested
slash, NUL, percent escape, uppercase or host-path syntax is rejected. There is
no normalization, traversal, writable namespace or implicit host interpretation.
Malformed requests receive a bounded INVALID response; when decoding fails it
uses READ/sequence1/offset0 rather than trusting unusable fields.

The client permits one pending tracked request, validates the exact96-byte
completion envelope, kernel peer, zero reply token, operation, sequence and offset.
The server performs one syscall per poll. A dequeued plain message has no reply
authority and is dropped. A denied reply after requester disappearance is dropped
without stopping service to unrelated clients; nonzero malformed kernel tokens
or transport inconsistencies fail closed. These exceptional paths have host tests;
native malformed/untracked/requester-death injection remains open.

## Shell Behavior

The native serial shell accepts `ls`, `ls /` and `cat /PATH` alongside the existing
process/status/fault commands. Reads stream through the ordinary console protocol;
the next file chunk is requested only after console acknowledgement. The prompt
returns after the complete response, including empty files. This is actual user
input and native service traffic, not a replayed transcript or kernel interpreter.

The shell independently bounds listings to8 entries and files to1024 bytes,
requires positive progress until EOF and a stable total length, and rejects
terminal control bytes except CR, LF and tab. These client limits do not imply
larger server storage. Revoked/stale file authority reports
`File service unavailable.` while console and process commands remain usable.

## Build And Verification

Use `tools/qualify_native_user_programs.py` to build the explicit13-program set
twice and validate flat ELF/code pairs. Then use
`tools/qualify_native_shell_process.py --files` with fresh workspace output and
program directories as specified by its CLI. The file profile cannot combine
with cleanup/prepared/owner-death fault profiles. Both normal and stale-file-handle
profiles are explicit development-only feature tuples; arbitrary tuples reject.

The file kernel's measured read-only overflow required an explicit0xE000 RO/entry
layout. Default and other profiles retain0xD000. The shared total kernel budget
remains208 pages, guarded stack36, user RX16384 bytes. The native image is115
pages; the49640-byte dispatcher local frame is not a full call-chain/interrupt
stack proof. Default kernel remains208/208 with120 bytes of RELRO padding.

Two fresh normal guests and a stale-handle control execute real multichunk reads,
empty/missing/invalid paths, repeated reads and directory listing while a worker
runs. Existing child exit/stop/restart/fault controls remain live. A `FILES` role
marker precedes the legacy `PSHELLPROC1 START` record. Only this explicit profile
interprets the positional legacy `counter_bytes` field as file-service bytes;
the oracle records the alias and verifies actual program sizes and peer roots.
COM2 supplies interaction bytes, never kernel proof. COM1/debugcon/transfer logs,
nonce challenges, exact output, private roots and hostile-marker controls are
verified independently. The fresh file handle is the only authority intentionally
made stale in the third guest; process factories remain valid.

See [Cycle279 evidence](checkpoints/cycle279-native-files.md). Conventional Rust,
assembler and linker tooling produced these programs, not new PooleGlyph-native
generation. Two useful apps, general supervisor recovery, local input/display,
sustained optical ISO acceptance and full canonical qualification remain open.
The complete robust microkernel, PooleGlyph/PDC and PooleGlass remain the goal.
