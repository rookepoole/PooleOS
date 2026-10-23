# Native Entered-Child Recovery

Contract PENTEREDRECOVERY1, Cycle314. Development-only N13/N14 qualification of
the microkernel task/job cleanup mechanism. Not a production or ISO profile.

The existing headless shell profile launches a measured worker, proves exact
nonce-bearing interaction, and executes an actual parent UD2. The kernel closes
the job, cancels the entered child, and denies premature release or completion.
Fault injection forces all three deferred attempts to fail. Dispatch offsets are
64, 192 and 448; a separate single recovery opportunity follows at 512. No retry
count, cooldown, authority, page budget or stack guard is widened.

Two explicit feature variants use the same production cleanup implementation:
`development-shell-orphan-recovery` permits the final attempt to succeed;
`development-shell-orphan-stuck` fails that attempt as well. Each has a separately
built denied-authority control. These variants imply the headless shell, not the
desktop. Mixed prepared-child or graphical feature requests are not admitted by
the qualification builder. Existing ordinary profiles remain unchanged.

Native PARKED/HELD assertions require exact task/generation, cancelled outcome,
nonzero calls and measured runtime, blocked-reclamation state, no pending or
unknown charge, and matching scheduler ticks and slice count. Successful cleanup
still passes the existing complete release and scheduler teardown path. Failed
recovery remains owned, cannot reenter, and does not rearm its write opportunity.

The independent validator binds owner death and every cleanup/recovery/job event
to surrounding scheduler samples. It rejects missing, duplicate, reordered,
overflowed, mismatched or substituted profiles. During persistence it requires
at least three post-attempt observations spanning 128 dispatches, unchanged
physical writes/pages/runtime/slices, no child completion or job drain, and
continued init/counter/console progress. Occupancy is not runnability: the retained
child remains in the occupied-slot mask but is blocked and must not accrue work.

Paired kernel and selected user-program builds, raw serial/debug logs, exact COM2
challenge bytes, media/manifest/boot transcript and current source bindings are
required for native evidence. Parser fixtures and COM2 output alone are not
native proof. Preserve the failed validator and build-admission experiments.

Limits: one real owner and one entered child, injected cleanup-memory failures,
bounded emulated dispatch windows. This is not general owner-death recovery,
multiple-owner fairness, partial allocator release, service restart, complete
capability/IPC revocation, all-path stack safety, SMP isolation or hardware
qualification. All N0-N39 gates and the eventual signed ISO objective remain.
