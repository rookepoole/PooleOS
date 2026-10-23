# Native Launch Admission Rollback

Cycle309 advances N13/N14 isolation and lifecycle ownership, with N27/N29
desktop consumers. This is native microkernel development, not a new boot
screen, a complete desktop, or a production release.

## Ownership Contract

The interactive dispatcher preserves the capability layer's admission result.
Only atomic `Denied` and `Quota` rejections enter recovery. Plan, scheduler,
identity, ownership and cleanup invariant failures remain fail-stop.

On recoverable rejection, the dispatcher verifies an unchanged scheduler
summary, a still-valid exclusive launch permit, and the exact unentered prepared
image. Prepared cancellation must produce zero syscalls and no CR3 switch.
The image remains owned by its task slot and parent job. Reclamation never
manufactures process completion or tears down an unadmitted scheduler member.

The failed launch result is published only after the exact image is reclaimed
and the slot is missing. Recoverable cleanup failure retains both the image and
the noncopyable launch permit across dispatches. Other tasks can progress, but
no replacement launch can claim that slot. Owner death revokes the factory;
eventual cleanup must not resurrect a reply to the dead owner.

No automatic retry is added. The existing user-space launcher consumes the
failed result; a new command or gesture is required for a new attempt.
Attempt sequence, task generation, endpoint-handle generation, parent process
handle and window observer identity remain separate authority domains.
Task generation and attempt sequence coincide in this prepared-image scenario;
future failures before image creation must not generalize that coincidence.

## Native Diagnostic

`development-launch-failure` is opt-in and requires the launch-desktop profile.
It rejects each application's second admission using a stale third inherited
surface grant after two valid grants have been installed. The capability layer
must roll those partial effects back. Text reclaims immediately; Numbers also
encounters one injected retirement-memory failure, retaining its image for the
existing dispatch-separated cleanup worker. A third explicit launch must admit
a fresh image and perform useful file-backed work.

This profile is diagnostic-only and is rejected by ordinary preview selection.
The independent oracle tracks allocations, zero entry, scheduler progress,
failure publication order, all identity generations and subsequent reclamation.
The paired-image, stale-file and unsigned-boot controls remain enabled.
Synthetic parser fixtures are never native evidence.

## Remaining Work

- Recover construction failures before admission, including quarantined images.
- Define recovery for startup-handoff errors after admission has committed.
  That boundary still fails closed with owners retained; it is not covered by
  the pre-commit admission rollback implemented here.
- Exercise real native quota-exhaustion admission rejection; this cycle's native
  fault injection is `Denied`, while host tests cover quota rollback/classification.
- Exercise rejected-admission cleanup exhaustion and owner death in native guests.
- Exercise GUI-visible failure acknowledgement and fresh gestures in both emulators.
- Recover the window service with explicit generation-bound endpoint rebinding.
- Requalify the complete source-bound desktop matrix before selecting a new ISO.
- Package a versioned, source-pinned preview launcher so later development does
  not strand a previously qualified demo. Verify its immutable source/runtime
  manifest; do not bypass current-workspace receipt checks.
- Prove all-path stack bounds; implement COM2-independent startup, persistence,
  event-driven waits, accessibility, remaining microkernel services, PooleGlyph
  and PDC gates.

The Cycle308 preview pointer, ISO copies and all historical evidence are retained.
They are historical builds after source changes, not current-source qualification.
See [cycle evidence and next move](checkpoints/cycle309-native-launch-rollback.md).
