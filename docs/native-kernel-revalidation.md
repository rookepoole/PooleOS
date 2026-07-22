# PKREVAL1 Exact Retained-Byte Revalidation

PKREVAL1 is the bounded PooleKernel consumer for the loader-to-kernel trust
boundary required by `ADD-BOOT-011` and `ADD-BOOT-012`. It does not accept a
PooleBoot parser summary as authority. It reconstructs the development trust
decision from the exact immutable bytes named by the final PBP1 handoff.

The machine-readable contract is
`specs/native-kernel-revalidation-contract.json`. The qualification receipt is
`runs/native-kernel-revalidation-readiness.json`.

## Retained input profile

PBLIVE3 keeps the PBP1 1.0 loaded-artifact entry layout and extends its
canonical profile from seven to ten roles:

| Role | Input | PBP1 size meaning |
| --- | --- | --- |
| 1 | loaded PooleKernel image | mapped image allocation bytes |
| 2-7 | six exact PBART1 files | exact file bytes |
| 9 | exact PSM1 system manifest | exact file bytes |
| 10 | exact PBTP1 policy snapshot | 320 exact bytes |
| 11 | exact PBTS1 state snapshot | 256 exact bytes |

Role 8 remains reserved for a future crash kernel. Every non-kernel descriptor
contains a page-aligned physical locator, the exact file length rather than
page padding, and SHA-256 over those exact bytes. The profile is strictly
ordered and rejects missing, duplicate, writable, executable, overflowing, or
overlapping inputs.

PooleBoot reads PSM1, PBTP1, and PBTS1 into bounded source pools, allocates
final `EFI_LOADER_DATA` pages, zeroes page padding, copies the exact bytes, and
reparses from the final pages before freeing the source pools. Every failure
path releases all completed and partially completed retained allocations.
PKMAP2 checks identity translation for the first and last byte of each retained
allocation before preserving the loader mappings through `ExitBootServices`.

## Kernel order

PooleKernel performs the following allocation-free sequence before any future
capability or action gate:

1. Decode PBP1 and require `BOOT_SERVICES_EXITED`.
2. Validate the exact ten-role locator, flag, length, and overlap profile.
3. Form retained slices only after every bounded locator check passes.
4. Recompute each exact file SHA-256 and compare it with PBP1.
5. Reparse PSM1 and bind the selected slot, kernel digest and image size, and
   all six PBART1 roles, exact lengths, and digests.
6. Reparse the six PBART1 envelopes and all six inner PINIT1, PREC1, PSYM1,
   PMCU1, PFWM1, and PPOL1 contracts.
7. Reconstruct the domain-separated retained-set digest.
8. Reparse PBTP1 and PBTS1 and reconstruct the fourteen PBTRUST1 bindings from
   independently observed PSM1, kernel, and retained-set values.
9. Require the exact `pbtrust_policy_unsigned` development denial and zero
   authority grants, authorized actions, and state writes.

`revalidate_development_from_handoff` is explicitly unsafe because Rust cannot
prove that physical addresses supplied by firmware are mapped. Its caller must
provide the PKENTRY1/PBMAP2 immutable identity-mapping precondition. The safe
verifier used by host qualification executes the same checks with separately
owned byte slices.

## Qualification

The pinned single-host qualifier builds PooleKernel for
`x86_64-unknown-none`, PooleBoot for `x86_64-unknown-uefi`, and a host probe from
the same `no_std` verifier. Rust and an independent Python oracle must agree on
the canonical nine-file result through 19 Rust tests, 8 Python tests, 36
targeted hostile controls, and 32,768
deterministic post-loader mutations spanning every retained role. All mutation
cases must reject at the exact-file digest boundary; controls also cover source
truncation, role reordering, locator substitution, writable/executable flags,
range overlap, missing `ExitBootServices`, summary-size substitution,
summary-digest substitution, and attempts to repair only the outer PBP1
digest.

The receipt binds the eight upstream PINIT1, PREC1, PSYM1, PMCU1, PFWM1,
PPOL1, PBTRUST1/PBSTATE1, and PSM1 readiness ledgers used to form the canonical
retained bundle. Refreshing any one of those ledgers makes PKREVAL1 stale until
this qualifier is rerun.

## Boundary

The final PBTS1 bytes are still an ESP development candidate. They are not a
PBSTATE1-selected authenticated, monotonic, writable persistent-state
snapshot. No signature is generated or verified, no capability is created,
and no lifecycle, recovery, symbol, microcode, firmware, policy, or state-write
action is authorized.

This standalone qualifier does not transfer control. The separate `PKXFER1`
receipt proves the opt-in QEMU-only transfer and live guest execution of this
same revalidation path; default PooleBoot still stops before transfer.
The default firmware run proves production of retained exact bytes and the
final PBP1 ownership description, while this standalone receipt proves the
compiled PooleKernel consumer. PKXFER1 separately proves live execution only
for the unsigned QEMU development profile. Neither receipt proves target
firmware, physical hardware, a second builder, authenticated persistent state,
capability creation, a signed ISO, installation, recovery, N5 exit, N6 exit, or
production readiness.

PKTRAP1 separately proves the bounded BSP-only descriptor and deliberate-fault
slice, while PKCPU1 separately proves the bounded qemu64 read-only CPU-policy
slice. PKERR1 separately freezes a pure exact-target rejection policy while
leaving direct errata and numeric microcode-floor authority open. PKXSTATE1 and
PKXEXC1 separately prove bounded one-BSP x87/SSE ownership and exception
delivery/recovery, while PKMSR1 separately proves bounded read-only privileged-
MSR policy observation. Cycle 125 separately closes the bounded PKPMM1
physical-page foundation, Cycle 126 closes the bounded PKVM1 inactive
virtual-memory foundation, and Cycle 127 closes the bounded one-BSP PKVM2
candidate-root activation, direct-map, exact CR3 restoration, and local
invalidation-receipt move. The next owner-independent move is
`N9-PMM-SCRUB-001` without target, scheduler, SMP, userspace, heap, pager, or
production promotion.
