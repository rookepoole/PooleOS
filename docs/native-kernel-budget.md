# PKBUDGET1: Kernel Image Budget

The linked kernel declares used ends for RO, text, RELRO, initialized data and
BSS. The existing ELF canonicalizer still enforces load/relocation geometry and
W^X. PKBUDGET1 independently measures those declared boundaries and binds the
linked and canonical SHA256 identities. It is not a runtime or stack proof.

## Invariants

- Keep the existing entry at0xD000 and bootstrap reservation at208 pages.
- Keep the36-page guarded stack and its existing guard geometry.
- Page-round text, RELRO and BSS ends to actual use instead of fixed maxima.
- Require exactly one global zero-sized symbol for each of12 declared markers.
- Reject wrong types, ordering, page alignment, canonical-plan disagreement,
  excess whole-page padding, nonzero RO/text/RELRO padding and image overflow.
- Keep release size optimization `s`, overflow checks, aborting panic and no LTO.
- Every shared native product build runs the audit and emits kernel-budget.json.
- Keep diagnostic-only local storage behind a non-inlined function boundary so
  starting user space does not reserve that function's large local frame.

RO remains fixed to the entry ABI; its reported padding is not automatically
available to another segment. RELRO, text, BSS and per-profile margins are separate
constraints. Image headroom does not enlarge code pages, PMM records, IPC slots,
capability authority or stack space.

## Verification And Limits

Eight host tests include the202-page layout of a rejected compiler experiment:
its valid size arithmetic must never imply successful native execution. They
also cover inclusive208/209-page boundaries, malformed symbols, plan disagreement,
padding mutation and preservation of the compiler/build/diagnostic boundaries.
Synthetic parser outputs test composition, not independently validated ELF bytes.

Cycle269 replays default containment/unsigned denial, launch/restart and denied
authority, stop, six-process console/worker failure, and physical-memory diagnostics.
Actual ELF/disassembly inspection binds each measured profile. Entry frame size
excludes callees, asynchronous entry and other frames; full stack bounds remain
open. Other diagnostic profiles need current-candidate replay before canonical
qualification. No ISO, release or production acceptance follows from this audit.

[Cargo's official profile documentation](https://doc.rust-lang.org/cargo/reference/profiles.html)
describes `s` and `z` as size-oriented choices, not a guarantee of smaller output.
Our `z` experiment reduced bytes but changed stack frames enough to hit the guard.
The separated `z` build was inspected only and was not adopted. See
[Cycle269](checkpoints/cycle269-native-kernel-budget.md) for failures and evidence.
