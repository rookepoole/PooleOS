# Native Launch Quota Recovery

Cycle311 extends the existing native rollback path with a separate
`development-launch-quota` diagnostic. It depends on the complete launch-failure
desktop profile. The qualifier requires both `--launch-failure` and
`--launch-quota`; the ordinary preview rejects either diagnostic flag.

## Mechanism

On Numbers attempt2, the trusted dispatcher grants one temporary Inspect-only
process lease from the launch parent to init. The other application already
holds the parent's other lease. Inspection must work, termination must deny,
and an additional grant must return Quota at the unchanged two-lease owner limit.
The temporary handle is never delivered to userspace.
The feature-gated library helper derives the owner only from the validated
launch permit; the linked binary cannot construct or inspect private `Caller`
identity. No ordinary-profile caller API is widened.

The native admission path installs three attenuated child endpoint grants and
then encounters the real process-grant quota. It rolls back the child table
without scheduler mutation or observer replacement. The rejected prepared image
never runs. PRESSURE, REJECT(reason2), and RELIEF must be contiguous with identical
dispatch boundaries and exact task/owner/target/handle identity. The temporary
lease is explicitly revoked and subsequent inspect/terminate operations deny.

Image ownership and the launch permit remain retained through deferred physical
reclamation. Only after cleanup may the shell observe failure. Explicit attempt3
retries with fresh task and capability generations. Its process handle is
generation3 because pressure consumed generation2; its observer is generation2
because rejected admission did not commit it. All three endpoint generations
are3. Text's separate Denied control retains its older two-grant rollback pattern.
The oracle must not conflate these distinct generation domains.

## Boundaries

This is a process-lease quota challenge, not physical-memory OOM, arbitrary
resource pressure, owner-death recovery, cleanup exhaustion or a general retry
policy. The pressure helper exists only in the opt-in diagnostic kernel.
Invariant failures remain fail-stop. Ordinary and historical Denied profiles
stay separate; historical receipts are not rebound to current sources.

Required evidence includes hostile identity/order/limit/generation mutations,
paired kernel bytes, fresh native quota and ordinary boot controls, useful file
work, peer survival, exact raw logs/transcripts and actual graphical failure and
retry pixels. A replacement preview still requires the complete QEMU/VirtualBox
matrix and immutable source/runtime-pinned launcher package. Preserve Cycle308.
Every remaining N0-N39 microkernel, PooleGlyph/PDC, PooleGlass, persistence,
standalone boot, hardware, signing, merge and production gate remains applicable.
