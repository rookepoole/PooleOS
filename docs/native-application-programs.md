# Native Application Programs

Cycle280, PAPP1. Two freestanding binaries and a bounded user-space job/file engine.
Host tests and exact builds pass. Native launch grants, file-service app access,
shell commands and guest execution are not yet implemented or qualified.

## Workloads

PooleText reports byte count, ASCII word count and LF count. Space, tab, CR and LF
separate words; printable ASCII and those three control bytes are accepted. Other
control bytes and non-ASCII bytes reject. Lines count LF bytes, not an inferred
unterminated final line. Chunk boundaries do not change the result.

PooleNumbers reports row count, signed64-bit sum and signed32-bit minimum/maximum.
Input is a strict single column, optionally headed by exact lowercase `value`.
Rows contain optional minus followed by1..10 decimal digits within signed32-bit
range. LF and CRLF separators are accepted, including a split CRLF; a final
unterminated value is accepted. A bare terminal CR, blank row, repeated header,
space, plus, comma, quotes, decimal point, exponent, overflow or arbitrary text
rejects. This is not a general CSV implementation. Empty/header-only input returns
four zeros; count0 disambiguates the absent extrema.

Files are bounded to4096 bytes and numeric datasets to256 rows. Counters/arithmetic
are checked; errors do not expose partial successful summaries. No heap, dynamic
linker, writable segment, kernel dependency or host filesystem access is added.
Actual file availability remains the PFILE1 server's immutable four-entry bundle.

## PAPP1 Contract

Every message is exactly64 bytes, little-endian:

| Offset | Bytes | Meaning |
| --- | --- | --- |
| 0 | 4 | `PAP1` |
| 4 | 1 | READY1, RUN2, RESULT3, ACK4, FAULT5 |
| 5 | 1 | Text1 or Numbers2 |
| 6 | 1 | OK0, BAD_PATH1, NOT_FOUND2, INVALID_DATA3, LIMIT4, UNAVAILABLE5 |
| 7 | 1 | Payload length0..40 |
| 8 | 8 | Job sequence, neither zero nor u64::MAX |
| 16 | 8 | Reserved zero bytes |
| 24 | 40 | Payload, unused bytes zero |

READY/ACK/FAULT require OK and no payload. RUN requires OK and carries the path;
invalid path semantics produce BAD_PATH before any file syscall. Successful RESULT
has exactly32 payload bytes containing four signed64-bit words. Text uses
`bytes, words, LF count, 0`; numbers uses `count, sum, min, max`. Error RESULT
has a nonzero status and no payload. Unknown phases/kinds/statuses, malformed
lengths, sequence0/MAX, reserved fields and nonzero padding reject.

The application sends READY as a tracked request to its control endpoint. The
authenticated shell replies RUN/path or explicit FAULT. The app then reads PFILE1
chunks directly through its separately granted file endpoint, computes locally,
and sends RESULT as a tracked request. Only the matching ACK completes that job
and advances the sequence. FAULT reaches a CPL3 invalid instruction in the native
adapter; host tests observe the request without executing that instruction.

Each poll makes at most one syscall. Backpressure preserves pending state. Control
replies require the exact kernel sender, zero reply token,96-byte envelope, payload
size, kind, phase and current job sequence. File replies additionally require stable
size, positive progress until EOF and exact offsets through the existing client.
Path/not-found/data/limit/file-revocation errors become structured results and allow
another job. Invalid transport/identity/sequence or peer loss is terminal, not
silently retried. A completed result stays pending until acknowledged. There is
no new timeout/efficient-idle guarantee or general service recovery claim.

## Startup And Integration Boundary

PSTART1 supplies five arguments: `text-app` or `numbers-app`, control endpoint,
control peer, file endpoint, file peer. Handles are distinct nonzero generation-
bound endpoint types; peers must be valid and distinct. Startup data describes
authority but cannot create it. The native caller must actually map the startup
block; the shared adapter's numeric checks do not prove mapping on their own.

Next use the existing trusted launch transaction to install only SEND grants for
control/file traffic, retain generation changes across restart, and return actual
handles in the startup block. Extend the file server's exact current0/3 client
policy explicitly for admitted apps. The shell must multiplex requests by actual
kernel sender and current child generation, retain bounded reply tokens, validate
result ranges before formatting, and invalidate pending jobs on stop/fault/death.
No guessing child handles, payload identity, fixed answers or kernel computation
may replace those paths. Preserve six owners and reviewed resource limits.

Use the existing `qualify_native_user_programs.py` tool for two independent builds.
PooleText5877 and PooleNumbers5884 bytes each occupy two RX pages below16384 bytes.
The full15-program set has no forbidden final relocations/imports/writable segments;
all13 older programs match prior ELF/code bytes directly. This does not prove new
native execution. Actual varied-input shell jobs, simultaneous app survival,
stop/restart, authority denial and contained faults must be exercised on fresh
guests before app/ISO acceptance. Full robust microkernel work continues afterward.
