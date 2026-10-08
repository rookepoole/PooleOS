# Cycle 245: Transactional User Construction

Date: 2026-10-08. Outcome: verified development progress, not production-ready.
USI-1 / N9, N13.1-2,6 / `N13-USER-ENTRY-LIVE-001`.
Entering commit: `7266729f823f0d5ece60eaed8e20b7061d77d68d` on
`agent/userspace-integration-iso`. Qualified main remains Cycle233.

## Implemented

[PKUSER11](../native-user-construction.md) retains every task-construction
allocation, validates exact owner tokens, copies payloads and constructs mappings,
transfers retention into the prepared image, and explicitly retries failed cleanup.
Both native task constructors use it. A discovered stack-guard fault was repaired
by separating constructor/installation frames, not weakening stack guards or quotas.
No PooleGlyph ABI, public spawn ABI or capability authority change occurs.

## Qualification

- 751 exact unchanged native/build/oracle bindings.
- 356 debug kernel +106 user-release +24 VM-release +8 compile-fail +10 boot-exit
  =504 Rust test executions;34 Python oracle tests, formatting, freestanding
  compilation and two incompatible-feature build denials pass.
- Two fresh headless QEMU/OVMF TCG guests with read-only virtual media and fresh
  vars; no guest network or host acceleration; exact serial/debugcon agreement.
- Each55-marker guest passes one real quota failure after five allocated pages,
  six post-write construction failures, six cleanup quarantines and six retries.
  All83 construction pages are scrubbed/read back/released before peer completion.
- Existing14 survival cases,140 dispatches,113 preemptions,56 post-stop quanta
  and291 CR3 writes remain. Total512 released pages,235 scrubbed data pages and
  one retained ACPI page.507 altered-evidence controls reject per guest.
- A third ordinary unsigned boot still denies kernel execution.
- Kernel646968 bytes,177 pages, entry0xB000, within unchanged192-page image cap.
  SHA256 `3CC7704CD01464D666D773966C9752D5F9C8CF0C9E308F45E6A8B3E9017358BD`.
- Receipt `runs/native-user-entry-readiness.json`, SHA256
  `AC96D028977F357C41318AB2CF33E761B0552E82FAB30B5637835681A6CE8346`.
- Final capture253.593seconds, source/owner unchanged; log
  `1A429C8BABE82D02E27D7623E76120CF00843E37E466C47C6162C07BE3333FF3`.

## Failures Preserved

1. `nativefirst`:58.172s, link text ended0x8BB0E beyond0x88000; log
   `CFB19E15D9590472BA1FDBE431A752781C5274AB8B400865CF62AEF0F891C971`.
2. `nativesecond`:107.719s, native user-root panic before peer completion; log
   `8B11AF8A1275BBE8FEB84E368775060729B35615531D5902D2754918165491C9`.
3. `diagnostic`:8.797s, diagnostic used nonexistent `Com1::new`; compilation
   rejected it. Corrected to the existing fatal-path initializer. Log
   `94F527AC23BE0D19C5C78F671AD3CEC95CA8EC8E12FDC85C6A35A67DE153FA7A`.
4. `diagnosticsecond`:37.907s, reproduced the kernel stack-guard #PF(2).
   Capture log `456EF52C896113D09322D0FC3F70269477EF4FE00DE31DE42168529DB9A5D69C`;
   raw debugcon `4B1030BC7F197C749D69C00B61C0201FE4A79178CD1D98C4685A8FD7D4868552`.
5. `nativethird`:54.157s, repaired/diagnostic text ended0x8C56E beyond0x8C000;
   one additional page was reserved. Log
   `E5C5AA0E311CF37B80C34FB23A9A6BE3938323F1F62A60EE2A6023D4A984B583`.
6. `nativefourth`:79.250s, passed construction after the stack repair but failed
   rollback-test stage120. Capture log matches the generic second-run error log;
   the distinct raw guest output remains in its own directory.
7. `diagnosticthird`:39.000s, stage12001 isolated the initial allocation failure:
   the test incorrectly requested three full tasks inside a32-page quota. Its
   generic capture log matches diagnosticsecond, but raw guest output is separate.
   The quota was retained. This case now verifies actual five-page rollback;
   full13-page failure cases run after one task exits, with the survivor suspended.

All failed captures report unchanged source/owner inputs and non-passing status.
The final complete focused suite and fresh guests reran after every source fix.
The90/45-second guest bounds are external limits, not independent kernel watchdogs.

## Boundaries And Next Move

No interactive session or optical ISO yet. N12/N13 remain partial; no phase or
flag closes. Plan2.148.0-native-user-construction keeps40 phases,301 subphases,
8996 requirements,59 additions,97 flags/42 open and20 gaps. Construction coverage
is bounded; general admission and persistent quarantine/slot-commit recovery stay
open. N3.7 whole-program stack reports/high-water and trap nesting are explicitly
required after the observed stack regression.

Next: pending/late timer shutdown recovery and terminal accounting, then capability
IPC, confined services, shell/apps and optical ISO. Independent missing-IRQ recovery,
native #SS/general exception delivery, XSAVE/SMAP/SMP/async and hardware remain open.
Image177pages/entry0xB000 requires product-contract migration and fresh replay.
Full exact-candidate gates remain pending; no merge/release/promotion is claimed.
Full robust microkernel, PooleGlyph/PDC/PooleGlass development remains required.

## Conservation

Frozen Cycle244 receipt: `tests/fixtures/cycle244-user-entry-readiness.json`,
SHA256 `3D6D3860572C99A08B6E0322D61C92BADBC9D0D71ED513D40DAB06AEE6891271`.
Execution ledger: `65155E981FA217BD9D78218A4E0C0537A574D613ED9FB3E1EBD16511B6A1EA5D`.
Live PooleGlyph Phase65 checkpoint/manifest inspected; Phase66 remains next.
No language/IR/package/VM/ABI/policy/conformance/IP change or new promotion.
Owner report unchanged: `F75E4836FAA9DDD59BA62648FE9542415F2119B659A583FB3F5959F2F5CAE87B`.
Checkpoint ZIP: `F3CCEB701CF76274D9464A0958BF6106888FB34F3C0BFBD55DE4ACE03C427ABC`.
Locked master: `A8C94719FAF9428C1F133010BA2603C0270C4E1EFD7327AF8EAB9C8C362ABB3D`.
No owner action is required for the next engineering step. Metadata verification
is recorded below; post-recording conservation and Git-index publication captures
are retained in the local cycle handoff rather than made self-referential.

## Metadata Verification

Initial metadata run: 125 of127 tests pass; two stale source-inventory expectations
still named465 architecture bindings and61 kernel Rust files. Updated these exact
counts to471 and64 for the six added evidence/source records and three Rust files.
No assertion was removed or relaxed. Failed run51.444s, capture52.297s, log
`DAA440C655B89A15B877A264B976091F38BEFEC39F3B8F5DEF2A5BC8D46F4561`.
Source and owner report stayed unchanged during capture.

Second metadata run:126 of127 tests pass. The following exact-set assertion also
needed the three new Rust paths explicitly listed as absent from the historical
entry receipt. That historical receipt remains unchanged and stale. Failed
run51.017s, capture51.860s, log
`B7DE7EDD1E686A15EF0EDDAFEA25746D6D7AECAC5209C32D7DA7EE8D519347EC`.
Source and owner report again stayed unchanged during capture.

Final metadata run:127/127 pass in51.230s, capture52.078s, log
`709C0B1335F553D6C3267FC7DD194E0DE23A005DDF4D2C6DEFEC820F33D321BB`.
No source/owner changes during capture. Current architecture inventory is471
bindings; Python discovery finds1282 tests with zero import errors, not a full
1282-test execution. All751 qualified native/build/oracle bindings remain exact.

Read-only gate projection:2/27 native profiles and5/27 static source closures
remain current;25/22 respectively are stale. Firmware remains current, boot-trust
and ELF prerequisite evidence stale. This inspection creates no guest execution
or replacement execution ledger and does not qualify a merge.
