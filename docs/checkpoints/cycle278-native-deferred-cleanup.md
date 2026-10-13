# Cycle278: Native Scheduled Cleanup

Date: 2026-10-13. USI-3 lifecycle implementation on the path to a usable native
user-space integration ISO. Full robust microkernel development continues afterward.

## Implemented

`PCLEANUP2` keeps failed task destruction inside the original non-Clone slot owner.
An admitted task enters a non-wakeable reclamation wait. Retry attempts are bounded
and separated by actual independent dispatches; exhausted owners remain retained.
The native dispatcher services at most one due owner per iteration and continues
running unrelated services. Its bounded orphan scan can reclaim another child
while the first remains pending. Scheduler teardown and observer completion remain
behind successful physical reclamation. No new syscall or kernel shell is added.
See [mechanism and limits](../native-deferred-cleanup.md).

## Executed Evidence

- Kernel debug/release:540 tests each, seven new scheduler/cleanup tests. Eleven
  ownership compile-fail doctests and Rust formatting pass. Focused Python:12 tests.
- Six fresh native deferred-cleanup guests: suspended/prepared children, each with
  two normal builds and a denied-owner control. An initial erase failure and one
  deferred finish failure retain memory for192 independent dispatches before
  successful cleanup. Independent console/init/counter progress, prepared zero
  entry, frozen stopped counters and zero dead-observer completions are checked.
- Three ordinary shell and three prepared-stop guests pass with actual commands,
  restart and fault containment. Two default boots and unsigned denial also pass.
  Total15 qualified VMs. One earlier VM completed but its qualification failed a
  negative-test assumption; it is not included in the15 successful qualifications.
- Ten unchanged Cycle277 user-program ELF/code pairs are independently reverified.
  No user programs were rebuilt and no new user-host test run is claimed this cycle.
- Receipts bind881 execution inputs. Normal114 pages, instrumented profiles115,
  default208/208. Default RELRO padding120 bytes; text padding3026 bytes. Guarded
  stack36 pages; local dispatcher allocations49784/49800 bytes, not full stack proof.
- Thirty-eight generated build/media archives retain successful and failed inputs,
  verified member-by-member before removing only generated hot duplicates.

Public receipt: `runs/native-deferred-cleanup-readiness.json`, SHA256
`11A92A9E69D3C346449BF47DDF44CBFB00DB49A5B0928C7FD6B1182E6E30871A`.
Raw captures, QEMU logs, exact console bytes, screenshots, object files and archive
manifests remain in ignored evidence storage. Previous readiness receipts stay frozen.

The repaired metadata/oracle suite passes277 tests in56.841 seconds (57.921-second
capture), without source/owner-report drift. Log SHA256
`1DBC9A8404B764799548B32275D96D96AE2FAE3A1E5200AF888750412FC766A9`.
These overlapping checks are not the full canonical suite. The initial four-failure
metadata log is retained separately under SHA256
`C9D762776CCF3FEEAC0E58FB59E0CD0C38F90D531E3BD90F7DD514A3D251772D`.

## Failures Preserved

1. The first qualification rejected the new feature tuple before building. Four
   explicit development-only combinations were reviewed and added; arbitrary
   features remain rejected. No production/default opt-in changed.
2. One early guest completed correctly, but the negative-test generator replaced
   running-task ticks with999999, which could remain a valid monotonic value. That
   is not necessarily hostile evidence. Overflow mutations now provide an actual
   invalid case, with separate one-tick mutations during/after cleanup proving the
   stopped-counter freeze. Fresh final-source guests pass. Bounds were not enlarged.
3. The first277-test metadata replay found four failures from three stale Cycle277
   expectations: schema cycle, exact architecture-binding count and current
   qualification label. Update them to278,694 and the scoped cleanup result;
   preserve exact schema constraints and rerun. This was not a native-code failure.

## Progress And Remaining Gates

USI-3 remains partial. Exhaustion is host-tested only. Native live-parent deferred
completion/restart, multiple pending owners, exhaustion, waiting-child and claimed
request interleavings still need qualification before optical acceptance. There is
no all-idle retry clock, wall-time guarantee, automatic exhausted-owner recovery,
general service supervisor restart, partial allocator-commit injection, full stack
proof or wider SMP cleanup guarantee. Non-memory/readback errors remain fail-closed.

Next implement the read-only bundled-file service and real shell list/read commands
over capabilities, then two useful separately launched apps. Keep the six-process,
32 PMM-record,16384-byte RX and current mapping limits unless separately reviewed.
Do not count diagnostic roles or shell builtins as the two useful applications.
Then build and operate the actual optical ISO with the remaining recovery gates.

The owner checklist and PooleGlyph Phase65 checkpoint/conformance are unchanged.
No PooleGlyph changes or new ML-native generation claim: this uses conventional
Rust/compiler/assembler/linker tooling. All40 phases,301 subphases,8996 source
requirements,59 additions,98 flags (43 open) and20 gap groups remain represented.
1432 Python tests/694 architecture bindings are inventories. No phase or flag closes.

Full canonical/release qualification was not run; historical load/transfer
freshness failures are not asserted repaired. This is a draft development candidate,
not merge-qualified or production-ready. Useful apps0, bundled files false, new ISO0.
