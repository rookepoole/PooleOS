# Cycle 166: AP Ownership Branch Checkpoint

Status date: 2026-09-08
Status: unfinished source backup; not merge-qualified or production-ready.
Phase: N12.3, `ADD-N12-CONCURRENCY-RECLAMATION-001`.
Flag: `FLAG-N12-CONCURRENCY-RECLAMATION-001` remains open.
Branch: `agent/n12-ap-execution-ownership`.

## Main Is Already Backed Up

Qualified Cycles 162-165 merged through
[PR #75](https://github.com/rookepoole/PooleOS/pull/75) at
`2026-09-08T07:17:58Z`. Main commit:
`6f9399c3cd70ebef2f7610f8b6fdb40ae262e27f`.
Tested and merged tree:
`c20156f18d2727f7e3c1df73ac05ad8126b9f470`.

The exact-final run passed 105/105 canonical gates, 708/708 Doctor checks and
the full Python suite with 924 discovered tests. All 1,519 tracked files were
unchanged during qualification; publication found zero violations. The
[public qualification receipt](https://github.com/rookepoole/PooleOS/pull/75#issuecomment-5580926148)
binds this result. Its local canonical receipt SHA-256 is
`621EFC831F7FB4F29990D2E27CD26FC6BB78B6AE11453FAB856BF7615B7DED34`.

Earlier Cycle 165 documents describe the pre-merge stage and must be read as
historical. This successful result does not transfer to the changed Cycle 166
kernel. Old remote branches are retained; branch names alone do not establish
that a checkpoint has not been incorporated by a squash or stacked PR.

## Implemented, Not Yet Live-Qualified

- `reclamation/ap_resources.rs` adds a non-copyable `ApResources` owner for
  the existing 32-page AP runtime region, including execution/exception stacks,
  and both one-page data allocations. Group admission retains all or none.
- Each owner tracks every CPU that might access its shared regions. The actual
  three-AP startup path records exposure before attempting startup, including
  uncertain starts and the partial-start rollback path.
- Release rejects a potentially executing owner. Exact-mask park confirmation
  is an unsafe hardware boundary, not a safe mailbox/timeout assertion. Current
  call sites use the existing final INIT sequence; broader hardware validity
  and independently observed execution behavior still need review/evidence.
- PMM owner-authorized scrubbed release retains the token through ledger growth,
  zeroing, readback and allocator commit, returning it on failure. Cleanup may
  retry; a partial scrub cannot transition back to execution. Owner loss keeps
  unfinished allocations retained.
- The live AP allocation/release code now uses this owner instead of retaining
  only the old data frame. This is actual kernel-path integration, but it has
  not yet been exercised in a fresh guest boot.

## Bounded Verification

All commands use the existing pinned toolchain, offline and locked dependencies.
Raw logs and local build products remain ignored and are not public media.

| Check | Result |
|---|---|
| Kernel library, debug | 243 passed |
| Kernel library, release | 243 passed |
| Compile-fail documentation tests | 9 passed |
| Host library Clippy, warnings denied | Pass |
| Freestanding binary Clippy, warnings denied | Pass |
| Cargo formatting check | Pass |
| Freestanding release link | Pass after unused-field repair |
| Fresh changed-image guest execution | Not run |
| Changed-image dependency/release qualification | Pending |

The added unit tests comprise eleven AP-owner tests and four PMM retained-scrub
tests. They cover atomic admission, copied-handle release denial, exact shared
CPU masks, partial startup, missing park confirmation, owner loss, wrong PMM,
scrub/write/readback faults, metadata migration/growth, receipt capacity and
cleanup retry. Nine documentation tests include two new compile-fail ownership
checks. Host tests use simulated physical access and do not prove hardware
quiescence or native execution of these new paths.

The first freestanding build failed because integration made the duplicate
`SmpIpiApResource.allocation` field unused under `deny(warnings)`. Removing the
duplicate field repaired the build; both the failed log and successful rerun
are preserved locally. The owner retains diagnostic allocation handles.

The preliminary linked product still uses the old build identity. It is a
compile/link diagnostic, not a newly canonicalized kernel or ISO. Existing
Cycle 165 image hashes and 228-test receipt pins must not be used to qualify it.

## Remaining Merge Blockers

1. Extend the actual live copied-free controls to the runtime and new data
   frame, with independent receipt validation. Review all park, partial-start,
   cleanup and retry paths; final INIT remains an explicit trusted boundary.
2. Assign a distinct kernel identity and measure canonical bytes, sections,
   mappings and relocations. Change acceptance pins only from measured output.
3. Update owner/source/test bindings and replay the changed-image native
   dependencies with fresh bounded headless emulator evidence.
4. Reconcile the roadmap generator, schema, machine ledger, architecture
   bindings, readiness artifacts, charter status and focused regression tests.
   Their current Cycle 165 data is historical for this work-in-progress branch.
5. Freeze the exact candidate and pass runtime-inclusive canonical qualification,
   publication-boundary scanning, release gate and all applicable GitHub checks
   and review conditions before marking the PR ready or merging.

No phase, subphase, ADD requirement or flag closes. N0 custody, general task
execution-stack ownership, broader CPU retirement, VM data-frame hygiene and
wider receipt coverage remain open. PooleGlyph and the separate frozen demo ISO
are untouched. No keys, signing, tags, releases, firmware or physical media are
part of this backup.

Next native move: finish the live ownership controls and measured kernel
identity under the existing N12.3 requirement, then qualify dependencies in
order. Main remains on the already qualified Cycle 165 checkpoint meanwhile.
