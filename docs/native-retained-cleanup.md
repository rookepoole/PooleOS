# Retained Terminal Cleanup

Contract: `PRECLAIM1`. Cycle 275, 2026-10-13. Development-only, single-BSP
terminal-task reclamation; not general asynchronous recovery or SMP retirement.

## Ownership And Ordering

`Slot::reclaim` requires the exact terminal task generation and settled slice
accounting. Driver authority is revoked first. `CpuImage::retire_owned` restores
and reads back the original CPU/root context, including a fresh flushing CR3
write on retry after possible exposure. Failure preserves the CPU owner in the
slot. Success transfers the original allocator retention tokens directly into
`RetiredImage`; it never temporarily releases and reacquires retention.

The slot enters `Reclaiming`. It keeps the terminal outcome but cannot run,
activate, accept a replacement task, or use prepared abandonment. Every remaining
allocation token is validated before any write. The reclaimer erases and reads
back every word of every owned allocation, including code, stack and private
page tables. It never follows page-table links into boot-owned structures.
`finish` must succeed before allocator release begins. Successfully released
members are removed; a failed member and all unreleased members retain ownership.
A retry cannot write an already freed allocation. Dropping an incomplete owner
leaks retained pages safely; it is not successful cleanup.

Only successful reclamation empties the slot. The native interactive dispatcher
then tears down the scheduler task, checks the page count, and publishes the
generation-bound `PCOMP1` result. Terminal execution is not cleanup completion.

## Executed Controls

Eight new kernel tests cover normal and duplicate retirement, stale generations,
slot reuse, pending accounting, revocation, after-effect CR3 restore, wrong memory
manager, finish failure, owner drop, and one-to-four-page code allocations.
The page-boundary campaign executes 78 erase/readback failure cases across all
13 image pages, first/last words and three failure mechanisms. Ten compile-fail
ownership checks pass. Kernel tests pass 520 per debug/release profile.

`tools/qualify_native_shell_process.py --cleanup-retry` selects only the explicit
development feature. The native adapter injects one after-effect zero-write
failure, corrupt write, read failure or finish failure per selected child
generation. Before its one immediate retry it checks 13 retained pages, five
ordinary-free denials, unchanged allocator count, denied reentry, and denied early
process completion. `PRECLAIM1` records must be followed by the exact matching
retirement; the independent oracle also requires the complete `PSHELLPROC1`
interaction, identities, outcomes and fault survival. Negative transcript
mutations are oracle tests, not additional guest execution.

Three injected guests execute ten failures, 50 ordinary-free denials and ten
early-completion denials. Three non-injected shell guests also pass. Two current
default diagnostic boots and ordinary unsigned-boot denial pass separately.
See [the checkpoint](checkpoints/cycle275-retained-terminal-cleanup.md) and
`runs/native-retained-cleanup-readiness.json` for exact source and binary bindings.

## Remaining Boundaries

- The native retry is immediate and controlled. Unexpected failure still halts
  fail-closed with retained ownership; no asynchronous retry queue is implemented.
- Prepared-child abandonment uses the earlier path and needs migration plus a
  native prepared-stop test. Owner death, orphans and supervisor recovery remain.
- Partial allocator-commit failure handling exists but has not been fault-injected.
- The 51,384-byte interactive local frame is measured disassembly, not a full
  call-chain/interrupt stack proof. The guarded stack remains 36 pages.
- Default image capacity remains 208 pages, with only 120 RELRO padding bytes.
  No PMM, mapping, RX-code, stack or bootstrap limit was enlarged.
- No useful apps, bundled-file service, local keyboard/display, sustained optical
  ISO acceptance, production trust, canonical requalification or release follows.

Next: close prepared/owner-death cleanup boundaries, then read-only files and two
useful separately launched applications, then the usable integration ISO. The
complete robust microkernel and Production Goal Charter remain required afterward.
