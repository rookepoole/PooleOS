# Cycle280: Application Programs

Date: 2026-10-13. Previous turn classified as progress: Cycle279 implemented native
read-only files and was committed/pushed. This cycle implements the two application
programs needed next, without promoting compiled-only evidence to native execution.

## Built

PooleText counts bytes, ASCII words and LF bytes. PooleNumbers computes row count,
sum, minimum and maximum for bounded signed-i32 single-column files. The shared
application engine receives authenticated PAPP1 jobs, reads PFILE1 chunks, computes
in user space, and retains results until acknowledged. Its state machine handles
backpressure, repeated jobs and file-revocation errors with at most one syscall
per poll; malformed transport, changed identity or sequence fails closed.
[Protocol and next integration](../native-application-programs.md).

There are no kernel changes, app launch grants, new file-server app permissions or
shell app commands in this checkpoint. Two application binaries are compiled;
useful native application count remains0. No new VM run or ISO is claimed.

## Verification

-110 user tests pass in debug and release,17 new: six parser/accumulator tests,
  two wire tests, eight job/file state-machine tests and one startup-role test.
- Coverage includes every text chunk size, split CRLF and signed extremes,
  malformed rows/control characters, inclusive file/row limits, poisoned states,
 64 independently evaluated varied integer datasets, changed data, exact job
  results, one syscall per poll, missing files, denied/revoked file authority,
  stalled/changing file responses, forged control replies, ACK/replay boundaries,
  sequence exhaustion and authenticated deliberate-fault requests.
- All15 program ELF/code pairs rebuild independently and match byte-for-byte.
  PooleText5877 bytes and PooleNumbers5884 bytes each fit two RX pages. No final
  imports, relocations or writable segments; object references remain local and
  relative. All13 prior programs are directly compared with preserved Cycle279
  ELF/code bytes and match. No new kernel or guest test is inferred from this.
- Five generated build/host archives, including the failed first build, are
  preserved with member-by-member verification. Exact ELF snapshots and raw logs
  remain in ignored evidence storage. Previous readiness receipts are unchanged.

Public receipt `runs/native-app-programs-readiness.json`, SHA256
`BBF22C1F0EC97E1DEF89D99AA95601A45E44D5E65F62D5F7B08FACAF02EAFFD7`.
The program qualifier's embedded Cycle274 label is historical; the enclosing
receipt/capture establishes Cycle280. It binds57 current program-source inputs.

The metadata/oracle suite passes283 tests in57.870 seconds (58.937-second capture)
with no source or owner-report drift. Log SHA256
`5F4525427DDC16BC428E1BD26C955A038AE3D00DD18D670C7C09C88FA90EFBE0`.
These overlapping tests are not full canonical execution. Final staged-file
verification also checks archive members, actual program pairs and old binaries,
source binding, unchanged owner inputs/old receipts and the publication boundary.

## Failure Preserved

The first build passed110 tests in both profiles, then the freestanding linker
rejected imported memcpy and overflow-panic helpers. Inlining the aggregate-return
boundaries and using checked counters removed those dependencies without relaxing
linker/object restrictions. A fresh independently rebuilt pair passes. The failed
capture log SHA256 is
`6E7FADDE0203F5BB0534FF5F259007EAB6676BC99284E0A8AD41526C8A778AF3`;
the passing capture log SHA256 is
`1C6F1AB86BAAC81225D9A3AD8A2BEF4E27DBFCAAAE05EA7E071CDE864E20D324`.

## Next Move And Boundaries

Integrate generation-bound control/file grants transactionally at launch, extend
file-service client authorization and implement shell application command/result
multiplexing. Verify actual changed-input results, repeated jobs, both apps alive,
stop/restart, stale authority and one app fault while the other and shell survive.
Preserve six roles,32 PMM records,16384-byte RX and existing mapping limits unless
separately reviewed. Complete stack/resource impact must be measured in the native
build, not inferred from these compiled programs.

Then close the remaining native file/cleanup controls for sustained optical ISO
acceptance. General supervision, efficient idle, full stack bounds, trust, SMP,
PooleGlyph/PDC and accessible PooleGlass remain obligations after the usable milestone.

The owner checklist, PooleGlyph Phase65 checkpoint ZIP and conformance report were
re-read/rehashed and unchanged. Phase66 CoreIR metadata audit remains its next step;
no PooleGlyph files changed or ML-native generation claimed. Conventional Rust,
assembler and linker tooling is used. All40 phases301 subphases8996 requirements59
additions98 flags43 open20 gap groups remain; no phase or flag closes.1438 Python
tests/720 architecture bindings are inventories. Full canonical/release gates were
not run; historical load/transfer freshness gaps remain. No merge qualification,
production readiness or new ISO follows from this application-program checkpoint.
