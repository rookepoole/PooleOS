# PooleBoot Aggregate Proof 7

Status: bounded unsigned PBART1/PINIT1/PREC1/PSYM1/synthetic-only PMCU1/PFWM1/qualification-only PPOL1/PBTRUST1-denial/post-exit PBP1/retained PKMAP2/stop-before-transfer non-promoting proof

## What Exists

PooleBoot is a Poole-authored, dependency-minimal `no_std` x86-64 PE32+ UEFI
application. The deterministic development image uses protective MBR, primary
and backup GPT, a FAT32 EFI system partition, the standard fallback path, PBC1
boot configuration, unsigned PSM1, and the real PKELF1 PooleKernel product.

Cycles 97-105 established reproducible UEFI entry, PBP1, live configuration and
manifest parsing, bounded ELF relocation, the real PooleKernel image, and exact
temporary higher-half mapping validation. Cycle 106 evolved that path to
retained exit-and-stop state. Cycle 107 advanced it to PKLOAD6, PBART1,
PBLIVE3, PKMAP2, and PBEXIT1: six additional profile artifact ranges, a guarded
stack, final-map-bound development PBP1, successful `ExitBootServices`, zero
post-exit firmware calls, and a permanent stop before transfer. Cycle 108 binds
the deterministic PINIT1 initial-system declaration and host activation-denial
oracle. Cycle 109 adds the PREC1 immutable recovery policy, separately mutable
state, bounded boot transition, receipt, authority, and activation-denial
oracle while leaving PooleBoot's inner payload handling opaque.
Cycle 110 adds the PSYM1 public-symbol identity, image-relative address,
bounded lookup, split-debug correspondence, privacy, and consumption-denial
oracle while leaving both PooleBoot and PooleKernel symbol consumption disabled.
Cycle 111 adds the synthetic-only PMCU1 exact-CPU package, revision/floor and
reset-known-good selection, apply-plan, mixed-revision, post-apply, and
activation-denial oracle while leaving vendor validation, privileged revision
observation, and PooleBoot/PooleKernel application disabled.
Cycle 112 adds the synthetic-only PFWM1 three-component firmware manifest,
two-edge dependency order, exact hardware and version identity, 47 dry-run
prerequisites, recovery and post-reset receipt checks, and activation-denial
oracle while leaving live inventory, payload validation, updater loading, and
PooleBoot/PooleKernel application disabled.
Cycle 113 adds the qualification-only PPOL1 six-mode policy, exact PINIT1
capability-route cross-binding, default-deny authority intersection,
attenuation, safe/recovery floors, firmware physical-presence separation,
durable decision receipts, and activation-denial oracle while leaving live
PooleBoot/PooleKernel policy interpretation and authority creation disabled.
Cycle 114 adds live `N5-INNER-LIVE-PARSE-001`: PooleBoot reparses all six exact
retained PBART1 files from their allocated pages, binds PPOL1's five payload
digests and eleven PINIT1 routes, requires six missing-signature denials, and
emits one retained-set digest with explicit zero-effect counters.
Cycle 115 adds `N5-INNER-TRUST-CONTRACT-001`: PBTRUST1 freezes separate
immutable-policy and mutable acceptance-state records, exact artifact,
revocation, rollback, redundant-copy, previous-state-chain, and external
evidence boundaries, then integrates both development candidates into
PooleBoot. The live path cross-binds fourteen facts and denies exactly at the
unsigned policy without verifying a signature, granting authority, or writing
state. PREC1 boot-attempt state remains a third, separate contract.
Cycle 116 adds `N5-INNER-TRUST-BACKEND-001`: the linked `native/trust` library
now contains an allocation-free PBSTATE1 two-copy selection, repair, migration,
and interrupted-transition planner rooted in externally authenticated monotonic
evidence. Its source is included in both aggregate implementation-input ledgers,
but PooleBoot does not invoke it; the live path and denial boundary are unchanged.
Cycle 117 adds `N5-INNER-KERNEL-REVALIDATE-001`: PooleBoot now retains exact
PSM1, PBTP1, and PBTS1 file bytes beside the six PBART1 files and represents all
ten present artifacts in final PBP1. Allocation-free `no_std` PKREVAL1
PooleKernel code independently reparses all nine non-kernel files, reconstructs
their manifest, inner, policy, and state bindings, rejects substitution and
mutation, and requires exact unsigned-policy denial. The verifier is
host-executed and target-built only; PooleBoot still stops before transfer.

The normative aggregate contract is `specs/native-pooleboot-proof.json`.
`tools/qualify_native_pooleboot.py` validates the current PKLOAD6 receipt,
rebuilds and executes the live proof twice, and emits
`runs/native_pooleboot_readiness.json`.

## Boot Sequence

The qualified application:

1. validates UEFI system and boot-service tables;
2. disables the watchdog and initializes independent COM1/debugcon diagnostics;
3. opens the EFI system partition and parses bounded PBC1;
4. parses unsigned PSM1 and requires the exact seven-entry manifest profile;
5. reads, SHA-256 checks, allocates, relocates, and verifies PooleKernel;
6. validates six PBART1 role/version/payload envelopes and copies each exact file
   into a distinct zero-padded loader range;
7. reparses all six retained files, cross-binds PPOL1 to the other payloads and
   PINIT1 routes, and requires every development gate to deny without effects;
8. parses PBTP1/PBTS1 development candidates, cross-binds the exact manifest,
   kernel, retained set, revocation identity, roles, and rollback floors, then
   denies at `pbtrust_policy_unsigned` with zero effects;
9. renders the static high-contrast PooleOS GOP identity;
10. copies exact PSM1, PBTP1, and PBTS1 files into final ranges, reparses them,
    and frees their source pools;
11. builds and actively audits PKMAP2, then restores the firmware CR3 while
   retaining the kernel, nine non-kernel file ranges, private root, guarded
   stack, and handoff pages;
12. obtains the final UEFI memory map and serializes ten-descriptor PBLIVE3 into retained memory;
13. calls `ExitBootServices`, retrying only stale-map-key failure within a bound;
14. verifies immutable PBP1 state and zero post-exit firmware calls;
15. emits the 25-marker dual-channel receipt and halts at
    `STOP BEFORE TRANSFER`.

## Evidence Method

Qualification uses the pinned single-threaded QEMU TCG and OVMF profile with a
fresh variable-store copy, read-only media, no guest network, no host
acceleration, loopback-only QMP, and no shared folders. It requires:

- two byte-identical clean PooleBoot builds;
- two byte-identical PooleKernel builds and media generations;
- two exact marker streams and static GOP screenshots;
- exact serial/debugcon agreement;
- independent PBC1, PSM1, PBART1, PKELF1, PBP1, PKMAP2, and PBEXIT1
  reconstruction;
- independent PINIT1 declaration validation and development activation denial;
- independent PREC1 policy/state/transition validation and development
  activation denial;
- independent PSYM1 identity/address/privacy/lookup validation, split-debug
  correspondence, and development consumption denial;
- independent PMCU1 package/digest/selection/apply-plan/post-apply validation
  over visibly synthetic never-apply payloads and development activation denial;
- independent PFWM1 identity/dependency/dry-run/recovery/post-reset validation
  over a synthetic external-payload-only manifest and development activation denial;
- independent PPOL1 mode/precedence/attenuation/PINIT1-cross-binding/receipt
  validation over qualification-only policy bytes and development activation denial;
- exact target-side reparse of the six retained files, independently reproduced
  from media, with one domain-separated retained-set digest and zero authority,
  action, state-write, and hardware-observation counts;
- exact PBTRUST1 policy/state candidate parsing, fourteen target/host
  cross-bindings, deterministic unsigned-policy denial, and zero signature,
  authority, or write effects;
- provenance binding of the pure PBSTATE1 backend model while requiring that
  the live proof perform no backend selection, repair, migration, or I/O;
- exact kernel/six-PBART1/PSM1/PBTP1/PBTS1, root, stack, handoff, map, and
  digest cross-bindings;
- 155/155 integrated hostile controls;
- no absolute user path in public readiness artifacts;
- a clean QMP shutdown of the intentionally halted guest.

The aggregate report records only claims frozen by its schema. The observed
single-host emulator path is evidence, not promotion authority.

## Exit Discipline

All allocations and fallible setup occur before the first exit attempt. After
an attempt, the implementation permits no firmware service except a fresh
`GetMemoryMap` followed by `ExitBootServices`; after success it permits none.
Unexpected failures after the first attempt halt instead of returning into an
ambiguous firmware state.

The retained PBP1 says boot services have exited and includes real CR3, stack,
handoff, ten-descriptor artifact, GOP, and final-map state. It remains a development
profile: signature fields are absent and the kernel-entry profile rejects it. Therefore
the proof deliberately does not load the retained CR3, switch RSP, or call the
entry point.

## Current Claims

The receipt proves, on the pinned profile:

- reproducible PE32+ and deterministic twelve-file GPT/FAT32 media;
- live PBC1/PSM1/PKELF1/PBART1 intake and exact manifest digest equality;
- PBART1 role, version, payload length, and payload-digest validation for the
  initial-system, recovery, symbols, microcode, firmware, and policy files;
- host-oracle validation of the PINIT1 graph and a fail-closed activation result
  for the unsigned development context;
- host-oracle validation of the 992-byte PREC1 policy, 128-byte mutable state,
  exact A/B and safe/recovery transitions, receipt binding, and fail-closed
  activation result for the unsigned development context;
- host-oracle validation of the PSYM1 public-only image-relative index, exact
  five-part image/debug/source identity, three public functions, bounded
  lookup, source-path exclusion, pointer redaction, and fail-closed consumption
  for the unsigned development context;
- host-oracle validation of the synthetic-only PMCU1 package, exact
  `AuthenticAMD`/CPUID identity, two patch records, revision/floor and
  reset-known-good selection, no in-session downgrade, BSP/AP prerequisites,
  mixed-revision failure, post-apply checks, and fail-closed activation for the
  unsigned development context;
- host-oracle validation of the synthetic-only PFWM1 manifest, three exact
  components, two dependency edges, hardware and version floors, external
  payload identities, dry-run ordering, recovery, post-reset receipts, and
  fail-closed activation for the unsigned development context;
- host-oracle validation of the qualification-only 1,984-byte PPOL1 policy,
  six exact modes, eleven PINIT1-cross-bound capability rules, default-deny
  authority intersection, safe/recovery floors, firmware physical-presence
  separation, durable decision receipts, and fail-closed activation for the
  unsigned development context;
- live reparse of all six exact retained PBART1 files, PPOL1 payload-digest and
  PINIT1 route cross-binding, six first-failure denials, and exact nine-file
  retained-set SHA-256 `FEE092995AF574AABDC329154E27E9464252923B87D58171DD4455B89FCBBA49`;
- live parse of the exact 320-byte PBTP1 policy and 256-byte PBTS1 acceptance
  state, fourteen cross-bindings, rejection of the ESP candidate as persistent
  authority, and exact unsigned-policy denial with zero effects;
- complete higher-half kernel alias verification with W^X, CR0.WP, and NX;
- framebuffer translation and cache-bit preservation during the active audit;
- retention of kernel, six profile artifacts, PSM1, PBTP1, and PBTS1 ranges,
  four table pages, an eight-page guarded stack, and a one-MiB read-only/NX
  handoff range;
- a final-map-bound post-exit development PBP1 reconstructed identically from
  both diagnostics transports;
- successful `ExitBootServices`, zero later firmware calls, and a permanent
  stop before transfer;
- two exact QEMU/OVMF executions.

## Explicit Nonclaims

The manifest, kernel, all six PBART1 files, and both PBTRUST1 candidates are unsigned or
unauthenticated and untrusted. The proof does not establish policy-signature or
threshold verification, authenticated revocation, Secure Boot-state evidence,
a live redundant authenticated monotonic writable state backend, performed
state selection, repair, migration, or power-loss durability, artifact authentication,
authorized semantic activation, live PooleKernel retained-byte parsing,
initial-system or recovery
execution, symbol consumption, policy application, capability
creation, PooleGlyph executable authority, microcode or firmware application,
live firmware inventory, updater loading, kernel exports, diagnostic authority,
authenticated rollback persistence or state I/O,
real vendor-container validation, redistribution approval, privileged
per-processor revision observation, final active kernel CR3/RSP,
final framebuffer cache policy, a transferable kernel-entry handoff, initial
system loading, PooleKernel execution, descriptor tables, interrupts, SMP,
capabilities, userspace, native drivers, PooleFS, PooleGlass, Secure Boot,
measured boot, TPM policy, target-firmware behavior, physical hardware, physical
media, an installer, an ISO, N5 exit, release acceptance, or production
readiness.

No key was generated or used, no signature was created, and no merge, tag, or
release follows from this proof.

## Chronological Next Move

`N5-INIT-SYSTEM-001` closes only its unsigned load/retain/PBP1-bind slice, and
`N5-INIT-BUNDLE-001` closes only the independently validated declaration and
activation-denial slice. `N5-RECOVERY-SEMANTICS-001` closes only the independent
PREC1 policy/state/transition and activation-denial slice, and
`N5-SYMBOLS-SEMANTICS-001` closes only the independent PSYM1
format/identity/lookup/privacy/correspondence/consumption-denial slice, and
`N5-MICROCODE-SEMANTICS-001` closes only the independent synthetic PMCU1
format/selection/apply-plan/post-verify/activation-denial slice, and
`N5-FIRMWARE-SEMANTICS-001` closes only the independent synthetic PFWM1
manifest/dependency/dry-run/post-reset/activation-denial slice, and
`N5-POLICY-SEMANTICS-001` closes only the independent PPOL1
mode/precedence/attenuation/cross-binding/receipt/activation-denial slice.
`FLAG-N5-INIT-SEMANTICS-001` is closed for independent semantics across all six
formats. `FLAG-N5-INNER-PARSE-001` is closed only for exact retained-page
PooleBoot parsing, cross-binding, development denial, and zero-effect evidence.
`FLAG-N5-INNER-TRUST-CONTRACT-001` is closed only for PBTRUST1 format,
precedence, bounded-model, and live unsigned-denial evidence.
`FLAG-N5-INNER-TRUST-BACKEND-MODEL-001` is closed only for the pure PBSTATE1
model. `FLAG-N5-INNER-KERNEL-REVALIDATE-001` is closed only for host-executed
PooleKernel parsing, binding reconstruction, mutation rejection, and exact
zero-authority denial. N5.6 and N5.9 remain partial because artifact
authentication, monotonic durable state, live PooleKernel execution,
capability creation and activation, recovery execution, symbol consumption,
policy application, and microcode or firmware application are open. The next
owner-independent move is `N5-KERNEL-TRANSFER-001`. Hardware-key acquisition
and governance signing remain separate owner-controlled lanes.

## Primary References

- UEFI 2.11, [Boot Services](https://uefi.org/specs/UEFI/2.11/07_Services_Boot_Services.html)
- Rust, [x86_64-unknown-uefi platform support](https://doc.rust-lang.org/rustc/platform-support/unknown-uefi.html)
- QEMU, [QMP reference](https://www.qemu.org/docs/master/interop/qemu-qmp-ref.html)
- seL4, [CapDL language specification](https://docs.sel4.systems/projects/capdl/lang-spec.html)
- Fuchsia, [Component lifecycle](https://fuchsia.dev/docs/concepts/components/v2/lifecycle)
