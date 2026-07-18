# PKLOAD5 Retained Handoff And Boot-Services Exit Proof

## Scope

PKLOAD5 is the bounded live integration proof for PooleBoot's current N5.8
handoff boundary. It reads PBC1 and unsigned PSM1 from the EFI system
partition, selects and digest-binds the real PKELF1 PooleKernel, allocates and
relocates it, retains PKMAP2 transfer storage, creates final development-profile
PBP1 bytes, exits UEFI boot services, and halts before kernel transfer.

The machine-readable contract is `specs/native-kernel-load-contract.json`.
`runtime/native_kernel_load.py` is the independent media, marker, PBP1, map,
and claim oracle. `tools/qualify_native_kernel_load.py` builds and boots the
product twice and emits `runs/native_kernel_load_readiness.json`.

## Live Intake

The qualified media contains exactly four deterministic files:

- `EFI/BOOT/BOOTX64.EFI`;
- `EFI/POOLEOS/BOOT.CFG`;
- `EFI/POOLEOS/SYSTEM_A.PBM`;
- `EFI/POOLEOS/KERNEL.ELF`.

PooleBoot obtains Loaded Image and Simple File System protocols, opens the root,
parses bounded PBC1 configuration, then parses bounded PSM1. PSM1 selects slot
1, version 1, and the exact kernel path, file size, image size, and SHA-256.
The digest equality is real but not security trust: the manifest is unsigned
and attacker-controllable in this development profile.

PKELF1 accepts the frozen x86-64 `ET_DYN` profile, computes the four mapping
ranges, allocates 48 loader pages, copies segments, applies 40 relative
relocations, verifies the loaded image, and binds the entry at offset `0x4000`.
Every file and temporary intake pool is closed or freed before the final map.

## Retained Transfer Storage

Before the first exit attempt, PooleBoot allocates and zeroes all storage needed
after boot services become unavailable:

- 48 kernel pages;
- four PKMAP2 page-table pages;
- eight kernel-stack pages with one absent guard page on each side;
- a 256-page, one-MiB handoff allocation;
- fixed one-MiB raw-map and 640-KiB normalized-map work pools.

PKMAP2 maps the kernel according to its exact `r`, `rx`, `r`, `rw` plan, the
stack as supervisor RW/NX, and the handoff as supervisor RO/NX. It activates the
candidate root only for a bounded audit, verifies the complete higher-half alias
and framebuffer invariants, restores the original CR3, and retains the private
root. No firmware call occurs while the candidate root is active.

## Final PBP1

For each exit attempt, PBLIVE2 normalizes the newly captured UEFI map into the
fixed retained work buffer and serializes PBP1 directly into the retained
handoff allocation. The final development profile requires:

- `boot_services_exited=true` in the logical candidate;
- `development_mode=true`;
- exact kernel physical/virtual ranges and entry;
- nonzero retained root, stack top, and handoff addresses;
- the PSM1 kernel digest and boot-selection state;
- optional GOP state;
- loader-reserved final-map coverage for kernel, table, stack, and handoff
  physical ranges.

The resulting bytes are intentionally not transferable to PooleKernel. The
kernel-entry profile rejects because manifest and kernel signatures are absent.
The live oracle reconstructs every byte from both serial and debugcon and
requires exact CRC32, FNV-1a, record, memory-entry, and cross-binding agreement.

## PBEXIT1 State Machine

PBEXIT1 preallocates all buffers and finalizes every fallible setup step before
the first `ExitBootServices` attempt. It then enforces this order:

1. call `GetMemoryMap` into fixed storage;
2. validate descriptor size, version, shape, and capacity;
3. rebuild and validate the final PBP1 candidate;
4. call `ExitBootServices` with that map's current key;
5. on `EFI_INVALID_PARAMETER` only, obtain a fresh map and retry;
6. stop after at most four attempts;
7. treat every other failure after the first attempt as fatal and non-returning.

The implementation is stricter than UEFI's post-first-attempt allowance: it
uses only `GetMemoryMap` and `ExitBootServices` after the first attempt and does
not allocate. After success, it disables interrupts, makes zero firmware calls,
checks that PBP1 bytes are unchanged, emits direct COM1/debugcon evidence, and
halts permanently at `STOP BEFORE TRANSFER`.

## Qualified Evidence

The Cycle 106 receipt records:

- 70/70 Rust host tests across PooleBoot, PBC1/PSM1/PKELF1/PBP1, PKMAP2,
  PBEXIT1, and PKENTRY1;
- two byte-identical PooleBoot builds, PooleKernel builds, and GPT/FAT32 media
  generations;
- two fresh-vars, read-only-media, network-disabled QEMU/OVMF boots;
- 22 identical ordered serial/debugcon markers;
- exact static GOP frames;
- exact 4,208-byte post-exit PBP1 reconstruction with 94 memory entries;
- 95/95 negative controls, including stale keys, retry exhaustion, descriptor
  drift, retained-range omission/overlap, guard mutation, post-exit firmware
  use, transfer overreach, marker drift, and oracle divergence.

The observed emulator path succeeds on its first exit attempt. Retry behavior
is covered by the independent state-machine tests and negative controls; the
receipt does not claim that this OVMF run naturally produced a stale map key.

## Nonclaims And Next Boundary

PKLOAD5 does not authenticate PSM1 or PooleKernel, enforce persistent rollback,
establish the final active kernel address space or framebuffer cache policy,
switch to the guarded stack, call PooleKernel, load the initial-system bundle,
enforce Secure Boot, perform measured boot, test a second host, test target
firmware, touch physical media, satisfy N5, or establish production readiness.

The next chronological transfer slice must authenticate the required artifacts,
validate the kernel-entry PBP1 profile, install the retained CR3 and RSP without
firmware use, call the ABI-defined PooleKernel entry, and prove that the kernel
consumes the immutable handoff or fails closed.

## Primary Reference

- UEFI 2.11, [Boot Services](https://uefi.org/specs/UEFI/2.11/07_Services_Boot_Services.html)
