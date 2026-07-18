# PooleBoot Aggregate Proof 6

Status: bounded unsigned post-exit PBP1/retained PKMAP2/stop-before-transfer
non-promoting proof

## What Exists

PooleBoot is a Poole-authored, dependency-minimal `no_std` x86-64 PE32+ UEFI
application. The deterministic development image uses protective MBR, primary
and backup GPT, a FAT32 EFI system partition, the standard fallback path, PBC1
boot configuration, unsigned PSM1, and the real PKELF1 PooleKernel product.

Cycles 97-105 established reproducible UEFI entry, PBP1, live configuration and
manifest parsing, bounded ELF relocation, the real PooleKernel image, and exact
temporary higher-half mapping validation. Cycle 106 evolves that path to
PKLOAD5, PBLIVE2, PKMAP2, and PBEXIT1: retained transfer storage, a guarded
stack, final-map-bound development PBP1, successful `ExitBootServices`, zero
post-exit firmware calls, and a permanent stop before transfer.

The normative aggregate contract is `specs/native-pooleboot-proof.json`.
`tools/qualify_native_pooleboot.py` validates the current PKLOAD5 receipt,
rebuilds and executes the live proof twice, and emits
`runs/native_pooleboot_readiness.json`.

## Boot Sequence

The qualified application:

1. validates UEFI system and boot-service tables;
2. disables the watchdog and initializes independent COM1/debugcon diagnostics;
3. opens the EFI system partition and parses bounded PBC1;
4. parses unsigned PSM1 and selects its kernel artifact;
5. reads, SHA-256 checks, allocates, relocates, and verifies PooleKernel;
6. renders the static high-contrast PooleOS GOP identity;
7. builds and actively audits PKMAP2, then restores the firmware CR3 while
   retaining the kernel, private root, guarded stack, and handoff pages;
8. obtains the final UEFI memory map and serializes PBLIVE2 into retained memory;
9. calls `ExitBootServices`, retrying only stale-map-key failure within a bound;
10. verifies immutable PBP1 state and zero post-exit firmware calls;
11. emits the 22-marker dual-channel receipt and halts at
    `STOP BEFORE TRANSFER`.

## Evidence Method

Qualification uses the pinned single-threaded QEMU TCG and OVMF profile with a
fresh variable-store copy, read-only media, no guest network, no host
acceleration, loopback-only QMP, and no shared folders. It requires:

- two byte-identical clean PooleBoot builds;
- two byte-identical PooleKernel builds and media generations;
- two exact marker streams and static GOP screenshots;
- exact serial/debugcon agreement;
- independent PBC1, PSM1, PKELF1, PBP1, PKMAP2, and PBEXIT1 reconstruction;
- exact kernel, root, stack, handoff, map, and digest cross-bindings;
- 95/95 hostile controls;
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
handoff, kernel, GOP, and final-map state. It remains a development profile:
signature fields are absent and the kernel-entry profile rejects it. Therefore
the proof deliberately does not load the retained CR3, switch RSP, or call the
entry point.

## Current Claims

The receipt proves, on the pinned profile:

- reproducible PE32+ and deterministic four-file GPT/FAT32 media;
- live PBC1/PSM1/PKELF1 intake and exact manifest digest equality;
- complete higher-half kernel alias verification with W^X, CR0.WP, and NX;
- framebuffer translation and cache-bit preservation during the active audit;
- retention of kernel pages, four table pages, an eight-page guarded stack, and
  a one-MiB read-only/NX handoff range;
- a final-map-bound post-exit development PBP1 reconstructed identically from
  both diagnostics transports;
- successful `ExitBootServices`, zero later firmware calls, and a permanent
  stop before transfer;
- two exact QEMU/OVMF executions.

## Explicit Nonclaims

The manifest and kernel are unsigned and untrusted. The proof does not establish
artifact authentication, rollback persistence, final active kernel CR3/RSP,
final framebuffer cache policy, a transferable kernel-entry handoff, initial
system loading, PooleKernel execution, descriptor tables, interrupts, SMP,
capabilities, userspace, native drivers, PooleFS, PooleGlass, Secure Boot,
measured boot, TPM policy, target-firmware behavior, physical hardware, physical
media, an installer, an ISO, N5 exit, release acceptance, or production
readiness.

No key was generated or used, no signature was created, and no merge, tag, or
release follows from this proof.

## Chronological Next Move

`N5-HANDOFF-001` now closes only its bounded exit-and-stop slice. The next
owner-independent N5 move should define authenticated transfer preconditions,
load the initial-system artifact set, promote PBP1 to the kernel-entry profile,
install retained CR3 and RSP state without firmware use, call the frozen entry
ABI, and prove PooleKernel consumes the handoff. Hardware-key acquisition and
governance signing remain a separate blocked owner lane.

## Primary References

- UEFI 2.11, [Boot Services](https://uefi.org/specs/UEFI/2.11/07_Services_Boot_Services.html)
- Rust, [x86_64-unknown-uefi platform support](https://doc.rust-lang.org/rustc/platform-support/unknown-uefi.html)
- QEMU, [QMP reference](https://www.qemu.org/docs/master/interop/qemu-qmp-ref.html)
