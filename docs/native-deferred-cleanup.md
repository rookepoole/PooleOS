# Scheduled Retained Cleanup

Contract `PCLEANUP2`, Cycle278, 2026-10-13. Development-only single-BSP integration.
This advances USI-3 toward usable files/apps/ISO without closing a production phase.

## Ownership And Scheduling

A task enters deferred cleanup only after authority revocation and quiescent CPU
retirement have transferred its original retained allocations into the non-Clone
task slot. Its terminal outcome and settled runtime remain immutable. A prepared
image may be unadmitted, or have one uncharged scheduler selection with no entry.
Mismatched generations, unsettled/unknown accounting, foreign/offline CPUs and
lock ownership reject before scheduling changes. An admitted task is blocked with
`WaitKind::Reclamation`; ordinary event, IPC and lock wake paths cannot resume it.
The trusted supervisor must not tear down that scheduler identity prematurely.

The slot, not an independent queue, owns retry state. The initial failed attempt
is followed by delays of64,128,256 actual scheduler dispatches, at most three
deferred whole-image attempts. Deadlines use checked arithmetic. Each dispatcher
iteration scans six owners round-robin and services at most one due owner before
the next user dispatch. Exhaustion retains pages and job membership indefinitely;
it does not report success, free memory or reopen the slot. There is no automatic
reset or escalation policy yet. This is not wall-time backoff or all-idle recovery.

Success requires erasing/read-checking retained pages and releasing the original
allocation tokens. Only then does the supervisor tear down the scheduler task and
publish completion, if a live observer remains. Job membership clears only on
successful cleanup. The orphan scan is bounded and skips pending owners, so one
failed child cannot prevent cancellation of another child.

The ordinary native integration defers memory-access/readback cleanup errors.
Revocation/quiescence/ownership-accounting failures remain fail-closed. Partial
allocator commits are not qualified and are not represented as a full-page retry.
The older immediate-injection profile remains a separate regression control.

## Qualification

Six fresh QEMU/OVMF guests use actual shell UD2 and prepared/suspended children.
Each injects an initial erase error, waits64 independent dispatches, injects a
finish error, waits128 more and successfully reclaims the child. The unused sibling
is reclaimed meanwhile. Init, counter and console keep progressing. The stopped
child's counters remain frozen; memory ownership and ordinary-free/early-completion
denials are checked. Prepared children never enter user mode. A denied factory
control is included in each three-guest group. Actual COM2 input uses fresh nonces;
kernel evidence comes from matching COM1/debugcon and exact image/media bindings.

Host tests cover exhaustion, no extra erase after exhaustion, retained job members,
unadmitted and admitted tasks, runtime preservation, no ordinary wake/reuse,
foreign/stale/offline rejection and independent progress. They are not native
evidence for exhaustion, multiple simultaneously pending owners, live-parent
completion/restart, waiting orphans, pending permits or wider SMP interleavings.
No full stack, hard real-time or general supervisor recovery guarantee is claimed.

See [checkpoint](checkpoints/cycle278-native-deferred-cleanup.md) and
`runs/native-deferred-cleanup-readiness.json`. Next build the user-space read-only
file service, then useful apps. Keep these remaining controls in optical acceptance;
continue the complete robust microkernel after the usable integration ISO.
