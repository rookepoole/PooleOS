# PooleBoot Aggregate Proof 7

Status: bounded unsigned PBART1/PINIT1/PREC1/post-exit PBP1/retained PKMAP2/
stop-before-transfer non-promoting proof

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

The normative aggregate contract is `specs/native-pooleboot-proof.json`.
`tools/qualify_native_pooleboot.py` validates the current PKLOAD6 receipt,
rebuilds and executes the live proof twice, and emits
`runs/native_pooleboot_readiness.json`.

## Boot Sequence

The qualified application:

1. validates UEFI system and boot-service tables;
2. disables the watchdog and initializes independent COM1/debugcon diagnostics;
3. opens the EFI system partition and parses bounded PBC1;
4. parses unsigned PSM1 and requires the exact seven-artifact profile;
5. reads, SHA-256 checks, allocates, relocates, and verifies PooleKernel;
6. validates six PBART1 role/version/payload envelopes, copies each exact file
   into a distinct zero-padded loader range, and applies no payload semantics;
7. renders the static high-contrast PooleOS GOP identity;
8. builds and actively audits PKMAP2, then restores the firmware CR3 while
   retaining the kernel, six profile ranges, private root, guarded stack, and
   handoff pages;
9. obtains the final UEFI memory map and serializes PBLIVE3 into retained memory;
10. calls `ExitBootServices`, retrying only stale-map-key failure within a bound;
11. verifies immutable PBP1 state and zero post-exit firmware calls;
12. emits the 23-marker dual-channel receipt and halts at
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
- exact seven-artifact, root, stack, handoff, map, and digest cross-bindings;
- 118/118 integrated hostile controls;
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
handoff, seven-artifact, GOP, and final-map state. It remains a development
profile: signature fields are absent and the kernel-entry profile rejects it. Therefore
the proof deliberately does not load the retained CR3, switch RSP, or call the
entry point.

## Current Claims

The receipt proves, on the pinned profile:

- reproducible PE32+ and deterministic ten-file GPT/FAT32 media;
- live PBC1/PSM1/PKELF1/PBART1 intake and exact manifest digest equality;
- PBART1 role, version, payload length, and payload-digest validation for the
  initial-system, recovery, symbols, microcode, firmware, and policy files;
- host-oracle validation of the PINIT1 graph and a fail-closed activation result
  for the unsigned development context;
- host-oracle validation of the 992-byte PREC1 policy, 128-byte mutable state,
  exact A/B and safe/recovery transitions, receipt binding, and fail-closed
  activation result for the unsigned development context;
- complete higher-half kernel alias verification with W^X, CR0.WP, and NX;
- framebuffer translation and cache-bit preservation during the active audit;
- retention of kernel and six profile artifact ranges, four table pages, an
  eight-page guarded stack, and a one-MiB read-only/NX handoff range;
- a final-map-bound post-exit development PBP1 reconstructed identically from
  both diagnostics transports;
- successful `ExitBootServices`, zero later firmware calls, and a permanent
  stop before transfer;
- two exact QEMU/OVMF executions.

## Explicit Nonclaims

The manifest and all seven artifacts are unsigned and untrusted. The proof does
not establish artifact authentication, PooleBoot inner semantics, initial-system
or recovery execution, authenticated rollback persistence or state I/O,
microcode application, final active kernel CR3/RSP,
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
PREC1 policy/state/transition and activation-denial slice. N5.6 and N5.9 remain
partial because PooleBoot enforcement, PooleKernel activation or recovery
execution, trust, authenticated state persistence, and the
symbol/microcode/firmware/policy formats are open. The next owner-independent
move is `N5-SYMBOLS-SEMANTICS-001`. Hardware-key acquisition, artifact authentication,
and governance signing remain separate owner-controlled lanes.

## Primary References

- UEFI 2.11, [Boot Services](https://uefi.org/specs/UEFI/2.11/07_Services_Boot_Services.html)
- Rust, [x86_64-unknown-uefi platform support](https://doc.rust-lang.org/rustc/platform-support/unknown-uefi.html)
- QEMU, [QMP reference](https://www.qemu.org/docs/master/interop/qemu-qmp-ref.html)
