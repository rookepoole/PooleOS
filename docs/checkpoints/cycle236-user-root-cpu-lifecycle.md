# Cycle 236: User Root CPU Lifecycle

Date: 2026-10-07. Status: pre-production, host-tested implementation.
Binding: USI-1, N9/N12/N13.3, `N13-USER-ENTRY-LIVE-001`.
Entry evidence: Cycle 235 owned prepared root, PMM retention and guarded entry
stack. Flag `FLAG-N13-USERSPACE-ISO-001` remains open. No phase or item closes.

## Implementation

`native/kernel/src/user_entry/cpu.rs` implements PKUSER3. `CpuImage` consumes
both a prepared image and its serialized CPU adapter. It does not expose the
underlying address space, inactive abort, retention tokens or a clone. Ownership
remains with the object on every error; dropping it deliberately retains pages.

Activation requires fresh PMM retention validation, full user/supervisor/entry
stack mapping replay, and CPU snapshots before and after the replay. The narrow
profile requires one CPU, IF clear, long mode, paging, write protection, NX and
four-level PAE paging, with PCIDE/PGE/LA57 disabled. The original CR3 must match
exactly, including low bits. CPU identity and paging-control state must agree.

The object becomes `Uncertain` before the hardware write, since an adapter error
can occur after MOV CR3. Failed writes, mismatched readback and observation errors
cannot produce an active or releasable owner. An uncertain/active/restored owner
must perform a fresh flushing restoration on the same CPU before detachment.
An already-observed original root is not proof of a flush. Failed restoration,
CPU migration, mode changes, unexpected roots and foreign managers retain all
pages. Detachment failure also retains the object and supports retry, with a new
flush. Never-exposed owners can cancel without inventing hardware retirement.
Successful retirement consumes the adapter instead of returning stale root-switch
authority alongside detached pages. Final review identified and removed that
unnecessary return value before the final native replay.

`native/kernel/src/arch/x86_64.rs` adds the privileged `UserRootCpu` adapter using
actual control/MSR reads, BSP observation, CPUID identity and MOV CR3. Its unsafe
constructor requires the exclusive single-BSP lease, all APs offline, preserved
code/stack/data/exception paths, retained mappings and no conflicting CPU/DMA
mutation. Its private, non-Send/non-Sync state is not a scheduler lease proof.
The adapter is compiled but not called by any boot scenario in this checkpoint.

The `Cpu` and `TableMemory` implementations remain trusted boundaries. Host
models do not prove their hardware observations, serialization, boot lifetimes,
DMA exclusion or temporary-alias behavior. In particular `finish` must revoke
only its own temporary mappings, not alter persistent audited mappings.

## Verification

The retained final run is `outputs/cycle236-user-entry-owned-adapter`; public receipt
`runs/native-user-entry-readiness.json` SHA-256:
`0CE9612DEF69AA63110F6E5A6D4D016DDE8D8F2D7E62A95E36938930D873CAE8`.

- 284 debug kernel host tests pass, including 12 new CPU-lifecycle tests.
- 38 optimized user-entry tests pass; these repeat the focused debug cases.
- Five ownership compile-fail tests pass, three newly added for CPU ownership.
- Formatting, freestanding library and freestanding kernel/adapter checks pass.
- Source and the owner-modified PooleGlyph report remain unchanged during replay.
- No guest execution, actual CR3 switch, ring-3 entry or new ISO was tested.

Fault tests cover successful ownership transfer/retirement, twelve unsupported
context/root cases, mapping drift, foreign retention identity, context changes
during audit, writes failing before/after effect, silent no-op, failed observation,
duplicate activation, restoration failures, CPU migration, unexpected roots,
cleanup failure/retry, dropped uncertain owners and never-exposed cancellation.

The initial bare cargo-format invocation lacked the pinned tool environment and
failed before formatting. Re-running through the existing verified toolchain
environment succeeded; no tool was installed or global PATH changed. All first
native checks passed, but their outer capture rejected a changed tracked receipt
(the qualifier's own output). That result is retained as
`outputs/cycle236-nativefirst.json`. The final run writes to ignored output,
then the exact passing receipt is copied into `runs`; that outer capture
passed in 34.406 seconds with no source changes. The subsequent final review
removed adapter return authority and replayed all native checks in 34.328 seconds
with unchanged source and owner report. These textual execution logs have
SHA-256 `D1C1E8BD3466F6C5AE97ADE7374F112E804C5B798639C1080D7F9772318F76C1`;
the differing capture records retain the rejected and accepted conditions.

Cycle 235 evidence is frozen at
`tests/fixtures/cycle235-user-entry-readiness.json`, SHA-256
`967233D0AFDAD3B8485A93EE74AB759E2BC6E2E1EEA6690499F8DF97E5B22EFD`.
Historical tests check those immutable bytes; current tests bind this cycle's
receipt to actual source bytes. Old guest receipts are not silently requalified.

The first 84-test metadata run passed 83 and failed one old current-source-count
assertion (43 versus 45 Rust files). The exact uncovered set now includes the two
new CPU files; the historical 79-input receipt is unchanged. Failure capture:
69.188 seconds, log SHA-256
`3493A8978F9CCAED492BB6799E9FBA43763CB858257B60C5315383FE5C2F4AF2`.
The corrected pre-final-review run passed all 84 in 68.473 seconds (capture
69.297 seconds), log `5D2ECE4A17B06E07AF72F8DDFCF54949EA783D2E4EC387A513C813E32FCB3CBB`.
Its earlier native receipt remains in ignored outputs, SHA-256
`E41A5F0357E00F9662F80206702268857B504F6183F8DA86A8FE95AA40F0F0CD`.
Final-source metadata replay: 84/84 pass in 67.572 seconds (capture 68.390),
unchanged source/owner report, log
`5E261AF830B86EC8130F00909D2B0A136A0ED0306EAC06F613AC1F328550D03D`.
The architecture baseline binds 425 files and Python discovery counts 1,239
tests; that inventory is not a claim that all 1,239 were executed this cycle.

## Progress And Remaining Work

The build plan, roadmap, release gate, charter reconciliation, evidence baseline,
README and cycle log record this increment. The locked master remains 10,512
lines, 171 sections and 8,996 requirements, with all 59 additions retained.
PooleGlyph remains at Phase 65/66, archive `F3CCEB701CF76274D9464A0958BF6106888FB34F3C0BFBD55DE4ACE03C427ABC`;
the owner report `F75E4836FAA9DDD59BA62648FE9542415F2119B659A583FB3F5959F2F5CAE87B` is preserved.

Next: reconcile bootstrap temporary access with the strict mapping audit and
owned timer/MMIO mappings; populate scrubbed task pages; wire the CPU adapter into
a bounded development-only guest probe. Then install GDT/TSS/IRETQ and supported
architectural state, and prove actual ring-3 return, timer recovery and contained
faults. No unsafe user entry is enabled merely because PKUSER3 host tests pass.
Capabilities/IPC, init/services, a real shell/two applications and optical ISO
qualification follow. Full robust microkernel work continues after that preview.

Twenty-five of 27 retained native admissions still require fresh execution for
the changed kernel. No exact-candidate merge qualification, release, signing,
hardware change, production promotion or new demo image is claimed.

## Architecture Reference

The restricted flush profile follows the architectural distinction between
ordinary CR3 invalidation, global translations and PCID-scoped behavior in
[AMD64 System Programming, revision 3.44, section 5.5.3](https://docs.amd.com/v/u/en-US/24593_3.44_APM_Vol2).
This is a design reference, not external verification of the implementation.
