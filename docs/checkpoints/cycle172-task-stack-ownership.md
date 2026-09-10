# Cycle 172: Inactive Task-Stack Ownership

Status date: 2026-09-09
Status: draft cloud checkpoint; full audit failed at 9c111e2; source-binding repair awaits receipt and full-candidate requalification.
Selected move: `N12-CONCURRENCY-RECLAMATION-001`, N12.3 with N12.7 context ownership dependencies.

## Cloud Baseline

Cycles 166-171 are already merged through
[PR #76](https://github.com/rookepoole/PooleOS/pull/76). Main commit
`8006c7be3a8fdbe314fa049f7161285f4def03cb` has tree
`1499017b20234037b55663b413cb9469a696260d`, matching the qualified source.
The exact-source final run passed 105 runtime-inclusive canonical gates and
708 Doctor checks, including bundle and replay inputs. Its report SHA-256 is
`4F140A6AFD8EB92B65C6F3A2083D77C023E94B1FAB10BDDE7E4B27CC69F9F077`.
That is historical evidence for those bytes, not a full pass for Cycle 172.
Retained checkpoint branches preserve original development history.

This draft uses `agent/n12-task-stack-ownership`. A cloud backup may precede
merge qualification; the standing merge gates are not bypassed.

## Implementation

`PKLIFE1` resources now require an explicit four-page `PKSTACK1` inactive-stack
allocation, with owner label `0x1701`. The existing allocator atomically retains
the stack together with the actual address-space tables and bound frames.
Rejected construction returns every original input without partial retention.

`InactiveStack` is non-Copy and holds a private retention token. A copied
allocation handle is diagnostic identity, not allocator release authority.
Reclaiming task resources returns an exclusive stack owner that stays retained
until explicit zeroing, readback verification and scrub-receipt commit succeed.
Failure preserves the owner for retry; dropping or forgetting it retains pages.
The scheduler binding rejects overlapping stack ranges, including allocations
from distinct manager namespaces. No unsafe code is added to this module.

This is a prepared/inactive task-resource profile. It does not install guarded
stack mappings, construct or activate an architectural context, establish CPU
quiescence, or add a live guest selector. Those integration steps remain open.

## Measured Evidence

The source-bound 17-stage reclamation core qualifier passes:

- 34 task-lifecycle tests per debug/optimized profile, including ten new stack cases.
- 19 reclamation-pool tests per profile.
- 243 kernel regressions per profile, including 20 physical-retention and 11 AP-resource cases.
- Eleven compile-fail ownership/borrow tests, format, host and freestanding Clippy, and linked-kernel build.
- Ten Python core-receipt tests pass on the current source, including 40 missing,
  duplicate, failed and ignored stack-test evidence rejection cases.

Public core receipt:
`runs/native-kernel-reclamation-core-readiness.json`, schema 1.5, SHA-256
`AFD1ABBE7EB217A132C0D9596004EC20AB2910CC23AEBD64D52E55EE645EF1D5`.
It binds source and stage-log hashes and explicitly sets live stack verification,
cross-CPU quiescence, N12.3 completion and production readiness to false.

Rebuilding produced the unchanged 530,072-byte canonical kernel, SHA-256
`8A2DA65C86B09F7BCF2D5ACDB90029A5B7B7361581BA841ADC3B62AEE168B625`.
This generic ownership code is not exercised by the existing live selector.
There are zero new Cycle 172 QEMU boots; prior boot evidence is not relabeled.

## Failure History And Limits

The initial focused regression reproduced the missing stack-retention behavior:
an ordinary copied-handle free succeeded while the task resource was retained.
The failing log SHA-256 is
`B115813E452A2E030565219A19EBAB0D91E96A6E6E07263461D6BC8E7AA63B12`.

The first implementation suite passed 32 cases and failed one: the 128-task
recycle test exhausted the allocator's existing 16-entry scrub-receipt ledger.
Failing log SHA-256:
`E677DE1335AF081D0B565DF62A92B4D7A09976C0DE2017E8848F713E418642C3`.
The repaired recycle test retains one scheduler/pool across 128 generations,
but uses a fresh fully drained manager per eight-task batch. It does not prove
128 scrub releases in a single manager. A separate boundary test performs 16
successful releases and verifies the seventeenth retains its owner and performs
no physical writes. Automatic receipt growth is not added or claimed here.

Fault cases cover first, partial and final-word writes and reads, corrupted
readback, stale handles, incorrect owner/size, retention conflict, wrong-manager
release, overlap, dropped/forgotten owners and receipt-capacity exhaustion.
Successful stack release verifies all 16,384 bytes, with 2,048 writes and reads.

## Why This Is Not Merged Yet

The backup check of the roadmap and architecture suite ran 23 tests: 20 passed,
three failed because the frozen Cycle 171 ledger/source bindings do not match
the new receipt and source. The core receipt itself validates against the new
source. No failing check is waived or presented as a full-suite pass.

The resumed qualification cycle reconciles those bindings, updates the current
contract/API documentation and preserves Cycle 171's projection/ownership
records byte-for-byte as named history. The new host-only stack record binds
schema 1.5, exact counts, receipt capacity and explicit non-claims. A regression
checks that record against the actual core receipt and keeps both existing
N12 reclamation and N36 evidence-coverage flags open.

Before the full audit, the reconciled focused suite passed 34/34 tests, including
the expanded roadmap and architecture checks. All 27 selected native checks
passed; 945 Python tests were discovered and all 232 architecture source bindings
validated. These are historical measurements for the pre-repair source, not
current qualification of the later repair. These were
not a full canonical pass. The locked 40 phases, 301 subphases, 57 added
requirements, 94 flags with 35 open, 20 gaps and 8,996 checklist requirements
are conserved. PooleGlyph remains Phase 65 with Phase 66 next and its existing
owner-modified generated report unchanged.

The initial patch assembly for long historical gap strings was rejected before
any edit because it repeated a file target; the grouped patch succeeded without
discarding history. No source or validation boundary was silently relaxed.

### Full Audit Failure And Repair Backup

The runtime-inclusive, bundle/replay audit of commit
`9c111e282372290d93a853240d4ef361b6666584`, tree
`bae7e532e48a1a3ba9a912f9452824c3a18a764c`, finished with exit 1 after
741.281 seconds: 104/105 canonical gates and 707/708 Doctor checks passed.
The failed Doctor gate was `pooleos:unittest`. Source and the owner's PooleGlyph
report remained unchanged during that run. Failed report SHA-256:
`D5AF0E1BCA6C6278ED9E506DB2EBBA1E464AED74177DDC73C8EF30B977D52DD4`.

A fail-fast diagnostic stopped at test 322 on kernel-entry exact reproduction:
the raw linked ELF grew from 7,024,792 to 7,025,584 bytes while the canonical
530,072-byte boot image remained unchanged. The old source-binding list omitted
24 of the kernel crate's 38 Rust sources, including `reclamation/task_lifetimes.rs`.
Diagnostic log SHA-256:
`90E44BA2AD6BD810F73D163DE3A7E6565AA6F85C8EF2F0ADF3B7FE2AC19BD0CD`.

The backed-up repair adds deterministic, unique binding of every Rust source
under `native/kernel/src`. Two new regression methods first failed and now
pass, including per-source digest mutation rejection across all 38 files.
Those two methods and ten reclamation-core tests pass together (12/12).
Focused log SHA-256:
`3B2AA3D3DCA39244AA0E28E31303853C18D659D0EE85D8F6F4A0062383F12633`.
No recorded artifact hash or reproduction assertion is relaxed to force a pass.

The post-repair selected projection passes 24/27 checks. Kernel-entry, symbols
and SMP IPI checks correctly reject stale entry/source evidence. All 17 existing
core stage-log hashes still match, and the core source receipt validates.
There are 947 discovered Python tests, not a measured full-suite pass.
The generated roadmap/architecture records remain the earlier pre-audit snapshot
and must be reconciled after the repair; their old 27/27 result is not current.
Raw logs, scratch files and workstation-specific paths remain private.

Before merging this draft:

1. Completed: reconcile Cycle 172 progress authorities, source bindings, schemas,
   documentation and measured test-count expectations; preserve historical
   Cycle 171 exact-final qualification separately from the current candidate.
2. Completed for this checkpoint: conserve checklist, phase, ADD, flag and
   non-promotion boundaries and record open stack mapping, CPU-retirement and
   receipt-growth follow-ups. This does not complete those implementation tasks.
3. Regenerate kernel-entry evidence and its exact linked/canonical artifacts;
   replay affected dependencies, reconcile generated progress/source bindings,
   and run full source-frozen canonical qualification with runtime, bundle and
   replay inputs. Do not inherit Cycle 171 or the earlier partial Cycle 172
   results. Preserve the failed full audit and rerun after repair.
4. Pass the exact-index publication scan and current required GitHub checks,
   clean-merge and review conditions before marking ready and merging.

No key/signing, governance, firmware, host-driver, physical-media, PooleGlyph,
frozen demo ISO, phase-completion or production-promotion change is made here.
Raw scratch logs and local work paths are not included in this cloud backup.
