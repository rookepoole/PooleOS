# Native Physical Allocation Retention

Contract: PKRETAIN1. Cycle 153, N12.3,
`N12-CONCURRENCY-RECLAMATION-001`, existing
`ADD-N12-CONCURRENCY-RECLAMATION-001` and
`FLAG-N12-CONCURRENCY-RECLAMATION-001`.

Status: implemented and host-qualified; the existing four-CPU lock profile passes
two fresh boots. Dedicated retention/failure evidence and complete candidate
qualification remain pending. No N12 exit or production claim.

## Mechanism

PKPMM7 now records a nonzero retention identity in each explicitly retained
allocation. `retain_allocation` validates the complete live handle and rejects
already retained or metadata-excluded allocations. It returns a non-Copy,
non-Clone `RetainedAllocation` with private fields. A boot-lifetime atomic
namespace prevents equal allocation handles in different managers from releasing
each other's retention. The namespace never wraps or reissues an identity.

The three ordinary free APIs reject retained allocations before extent growth,
scrub writes, readback or allocator-accounting changes. `release_retention`
consumes the exact token, returns it intact on failure, and ends retention without
freeing the allocation. Existing page-table revocation and scrub/release
requirements still apply. Dropped or forgotten tokens leave their pages retained.
There is deliberately no destructor that guesses whether readers or CPUs stopped.
Rust allows destructors to be skipped, so ownership safety must survive this.
[Rust `mem::forget` documentation](https://doc.rust-lang.org/core/mem/fn.forget.html).

Relaxed atomic operations allocate identities only; they do not publish page
contents or serialize the allocator. Exclusive manager access and the existing
pool publication protocol remain required. Identity reservation uses checked
update rather than wrapping addition and is not a wait-free allocation claim.
[Rust atomic documentation](https://doc.rust-lang.org/stable/core/sync/atomic/type.AtomicU64.html).

Retention is separate from PKPMM7's metadata/ACPI `release_excluded` rule. It does
not remove ordinary retained frames from direct-map coverage. Both the stable
manager seal and external-ledger seal cover the new identity. Migration and
ledger growth transfer it with the allocation record. The retired bootstrap
manager cannot end retention after migration.

## Native Integration

The existing three-AP runtime retains each old probe frame before any AP starts.
Its online path checks all three allocator free APIs against copied handles and
requires unchanged allocator accounting. PKLOCK1 uses one of those retained
frames as its shared ticket-lock page.

The successful teardown order is now:

1. Accept every exact root/generation/target shootdown acknowledgement.
2. Record retirement authorization, without releasing frames.
3. Obtain all three stop acknowledgements and quiesced mailbox states.
4. Complete final INIT for all three APs and verify the complete parked mask.
5. End retention, scrub/read back/release the old frames, then record release.
6. Re-read final mailbox evidence and continue runtime validation and cleanup.

Clearing the extra lock PTEs alone does not establish remote TLB invalidation.
Final parking therefore precedes release even after the one-page shootdown
succeeds. Failure cleanup only attempts APs not already parked, and does not
reach release when the started and parked masks disagree. An unresolved failure
retains resources rather than manufacturing a quiescence receipt. This remains
one frozen development topology, not general SMP or hotplug.

Both three-AP startup loops record each attempted target before INIT/SIPI or
online polling. A missing online acknowledgement cannot prove that an AP never
started. Even that uncertain target must complete final INIT before cleanup
releases its resources. The partial rollback and normal startup paths use the
same conservative ordering; injected missing-ACK live evidence remains pending.

The PKLIFE1 harness moves a real table allocation's retention token into a task's
payload. It proves copied-handle free rejection while a reader remains, after
retirement, and after object reclamation until the returned token is consumed.
Only then does actual PKVM1 table release complete. This is a concrete composition
test, not mandatory retention in every `Resources::new` call.

## Evidence

The source-bound version 1.2 reclamation receipt records:

- 214 kernel unit tests in debug and optimized host profiles, including eight
  physical-retention tests and the prior 206 regression tests.
- 20 task-lifetime tests and 19 object-pool tests in each host profile.
- Five compile-fail borrowing tests, including token duplication and moving a
  token through a shared reference.
- Host and freestanding Clippy, formatting and an exact linked-kernel build.

The retention tests cover all three free APIs with no I/O effects, duplicate
retention, equal foreign-manager handles, lost tokens, manager moves, stale
generations, metadata exclusion, unchanged direct-map coverage, manager migration,
repeated ledger growth, integrity corruption and identity exhaustion. These are
contained allocator correctness tests, not target-hardware observations.

The PKENTRY1 candidate separately passes 214 host tests, 43 rejection controls,
and two matching clean linked/canonical builds. Its current canonical file is
517,784 bytes, with 1,304 relative relocations and a 589,824-byte, 144-page image.
Entry stays at `0xA000`; text ends at `0x71000`, RELRO at `0x7E000`, and the image
at `0x90000`. Build ID: `PKBUILD1-CYCLE153-N12-RETAIN-V001-0000000001`.
Candidate SHA-256:
`BDEECCB27B1B91406911F91169B9BF5F9DF0439BB39FA0E1882C07E1AF3B81EF`.

Two fresh four-vCPU PKLOCK1 boots pass 35 ordered markers, exact serial/debugcon
and PBP1 binding, all 30 existing control categories and 103 rejected cases.
This executes the changed allocator and stop/park path but is not a dedicated
retention oracle or closure of the reclamation requirement. The earlier boot
first rejected the old 143-page retained-map limit; a later run reached guest
PASS but was rejected by the host's stale build ID. Both failures are retained.
The final retained layout puts the low stack guard at page 144, preserves all
36 stack pages and both guards, and shifts subsequent slots by one page.

The initial host run rejected the old 15,376-byte manager size; the actual manager
is 15,632 bytes and remains inside its five-page guarded arena. A native compile
rejected an accidental copy of the now non-Copy AP resource; logging now borrows
it. Link failures exposed exhausted text/RELRO/BSS regions. The final one-page
expansion preserves distinct R/RX/RW loads and page-aligned RELRO. Failed logs are
retained privately; no protection or test was disabled.

The first full candidate gate completed with 80/105 checks passing and 25
failures, including the aggregate Doctor check (684/708). All 24 dependent
native profile checks rejected stale bindings; the canonical Python suite also
failed. This audit preceded the final startup-mask repair and is not evidence
for the final bytes. Its private report is
`outputs/cycle153-pending-replay-gate.json`. The current candidate still has no
aggregate pass; the source-bound entry/core and focused boot reruns do not waive
that requirement. Cycle 152 remains the last fully qualified main baseline.

The post-startup-repair lock rerun then failed before QEMU: the host probe
reported `QueueFull` with four participants. Inspection found stale `next` versus
newer `serving` sampling in raw and writer-ticket admission. Both paths now
recheck `next` before accepting an apparently full window, retrying changed
samples. Genuine capacity rejection is preserved. Two existing tests now also
exercise full capacity across wraparound and four-thread 8,192-acquisition runs
for each path. Debug and optimized tests and the exact linked build pass; this
library repair does not change the final canonical kernel digest above.
`FLAG-N12-CONCURRENCY-LOCKS-001` is reopened and N12.2 returns to partial pending
current-source profile and aggregate replay. The failed host log is retained as
`outputs/cycle153-locks-startup-final.log`; a retry alone is not the repair.

After that repair, `outputs/cycle153-locks-ticket-repair.json` passes the complete
existing focused lock profile, including two fresh four-CPU boots and all 103
rejection cases. Twenty additional executions of all ten lock tests in each
host profile pass: 400 test executions and 655,360 raw/writer acquisitions. This
repeat campaign exercises the real repaired implementation; it is not an
exhaustive scheduler or memory-model exploration. The canonical lock receipt is
still historical and is not replaced by this private candidate receipt. The
roadmap keeps the lock flag open until complete current-source aggregate replay.

## Remaining Work

- Reconcile every current image-dependent contract, oracle and readiness binding;
  replay all dependent native profiles, the canonical suite and the full gate.
  Cycle 152 receipts are historical evidence, not passing evidence for new bytes.
- Complete an independent retirement-order oracle, explicit live retention
  telemetry and two-run failure, timeout, offline, shutdown and rollback evidence.
- Make physical ownership mandatory in the task/address-space resource API and
  bind all table, data, stack and active-root allocations, not only opt-in tokens
  and the three old probe frames.
- Integrate reader pins with active-root retirement and real scheduler teardown.
  `release_retention` is a trusted mechanism API, not CPU-stop authorization.
- Preserve fail-closed leaks on lost ownership until a separately qualified
  recovery/reaper policy exists. No forgotten-token reclamation is implemented.

An allocator independently reconstructed over overlapping physical memory is
still a trusted-bootstrap error; token namespace separation does not establish
global uniqueness of the memory map. Retention is not a capability, secret,
hardware acknowledgement, DMA barrier, interrupt-safe or concurrent allocator.
There is no ring-3, general address-space switch, production transfer or ISO
promotion. The isolated Cycle 151 demo remains unchanged and uses old qualified
kernel bytes; it must not be silently rebuilt or relabeled as this candidate.
