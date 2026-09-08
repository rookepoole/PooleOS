# Cycle 162: Active-Root Ownership

Status: pre-production development candidate; full dependency replay pending.
Phase: N12.3, `N12-CONCURRENCY-RECLAMATION-001` and its existing ADD/FLAG.
Prerequisite repair: N5.5/N5.8 PKMAP2 retained mapping geometry.

## Native Implementation

- PKVM3 initialization requires exclusive PMM access, checks both allocations
  before writing tables, audits the candidate, then acquires both retention
  tokens atomically. It cannot overwrite an already-retained root.
- Active table/data ownership is mandatory. Copied allocation handles cannot
  bypass invalidation or retirement checks by calling the allocator directly.
- Owner-authorized PMM freeing has no intermediate unretained state. Failed
  insertion, metadata validation or wrong-manager cleanup returns the token.
  Partial table zeroing and temporary-alias cleanup failures preserve ownership.
- The larger image moves the retained stack/handoff/reserved windows together.
  Both stack guards remain absent. The independent Python and Rust mapping
  implementations agree. A regression ties the diagnostic window to that layout.
- Live diagnostics count six allocator rejections across prepared, active,
  partially invalidated and restored states. The validator rejects a missing or
  altered count, missing runs, and contradictory recorded observations.

## Verified Scope

The kernel has 228 passing host tests in debug and release, including 16 PMM
retention cases and six new active-owner tests. The separate lifetime/pool
suite passes 24/19 tests in both modes, plus seven compile-fail checks. Host
and freestanding Clippy pass. PKMAP2 passes 14 Rust and 15 Python tests, and
its actual Rust probe agrees with the independent retained-map fingerprint
`6B62CD36C78A8111`.

PKENTRY1 passes two clean identical builds, independent Rust/Python loading,
43 malformed-image controls and host-path leakage checks. PKVM3 passes two
fresh headless QEMU/OVMF boots, 40 ordered markers and 48 negative controls.
Each boot observes six retained-free rejections, three local invalidations,
one generation-retirement receipt, exact root restoration, and zero allocated
pages after authorized cleanup. This is one BSP development profile only.

Kernel: 525,976 canonical bytes, 598,016 memory bytes (146 pages), 1,319
relocations; entry `0xA000`; RO `0..A000`, RX `A000..72000`, RELRO
`72000..80000`, RW `80000..92000`. Canonical SHA-256:
`D0AA3295F66AF02D48476BCEDC44D962A873E98FBA21F48A6753AA7BB9B24EA4`.

## Failure History

Two early test attempts missed required probe/protect steps; fixtures were
corrected without weakening kernel policy. The linker rejected text/RELRO
overflow, then a real boot rejected the expanded image at the old PKMAP2
144-page limit. The page-aligned layout and retained mapping were corrected.
One pre-boot source audit was over-sensitive to rustfmt line wrapping and was
corrected. A stale test SHA pin was replaced with the measured image identity.
Earlier successful pre-diagnostic boots are preserved but not added to the
final two-boot count. No old kernel receipt was relabeled as a new boot.

## Remaining Work

The selected native-gate projection passes 4/27 checks, with 23 changed-image
dependency receipts stale. Current PKENTRY1 and PKVM3 pass; unchanged PPOL1 and
PKERR1 remain valid. The actual pre-closeout candidate audit passes 81/105
gates, with 23 stale native checks plus the failed aggregate test gate.
Doctor passes 683/706 checks. This invocation supplied both bundle and replay
inputs but excluded optional PooleGlyph runtime checks; those two checks pass
separately and are not added to this audit's counts. Receipt SHA-256:
`09AB1890FF3095F9D332B139BFCE352B977C266F13D98A6CCC1CE2600B877407`.
This failed pre-closeout audit is not exact-final qualification. Chronological
dependency replay and a runtime-inclusive full gate still block merging.
Main remains the qualified Cycle 161 checkpoint, merged through PR #74.

Active allocation retention is not execution-stack ownership, a scheduler
retirement integration, a capability, manager-provenance isolation, general
SMP quiescence or scrub-before-reuse for the existing development data path.
N0 custody and N36 broader evidence review remain open. No phase or flag closes.
All 40 phases, 301 subphases, 57 ADD requirements, 94 flags (35 open), 20 gaps,
and 8,996 locked checklist requirements are preserved. PooleGlyph Phase 65 and
the owner's modified report are untouched. The frozen demo ISO is unchanged.

Next: `N5-SYMBOLS-SEMANTICS-001`, then dependent policy/loader/PooleBoot,
revalidation/transfer, CPU, physical-memory, IRQ/SMP and scheduler/lock replay
before the full exact-candidate gate and main merge. Continue N12.3 execution
stack and CPU-retirement ownership after that baseline is qualified.
