# PKLOAD6 Profile Artifact Load And Retained Exit Proof

## Scope

PKLOAD6 is the bounded live integration proof for PooleBoot's current N5.6 and
N5.8 development boundary. It reads PBC1 and unsigned PSM1 from the EFI system
partition, selects and digest-binds the real PKELF1 PooleKernel plus six exact
profile artifacts, validates each non-kernel PBART1 envelope, independently
validates the PINIT1 initial-system payload in the host oracle, retains every
loaded page range and PKMAP2 transfer allocation, creates final
development-profile PBP1 bytes, exits UEFI boot services, and halts before
kernel transfer.

The machine-readable contract is `specs/native-kernel-load-contract.json`.
`runtime/native_kernel_load.py` is the independent media, marker, PBP1, map,
and claim oracle. `tools/qualify_native_kernel_load.py` builds and boots the
product twice and emits `runs/native_kernel_load_readiness.json`.

## Live Intake

The qualified media contains exactly ten deterministic files:

- `EFI/BOOT/BOOTX64.EFI`;
- `EFI/POOLEOS/BOOT.CFG`;
- `EFI/POOLEOS/SYSTEM_A.PBM`;
- `EFI/POOLEOS/KERNEL.ELF`;
- `EFI/POOLEOS/INITIAL.PBA`;
- `EFI/POOLEOS/RECOVERY.PBA`;
- `EFI/POOLEOS/SYMBOLS.PBA`;
- `EFI/POOLEOS/MICROCOD.PBA`;
- `EFI/POOLEOS/FIRMWARE.PBA`;
- `EFI/POOLEOS/POLICY.PBA`.

PooleBoot obtains Loaded Image and Simple File System protocols, opens the root,
parses bounded PBC1 configuration, then parses bounded PSM1. PSM1 selects slot
1, version 1, and the exact kernel path, file size, image size, and SHA-256.
PSM1 requires the exact seven-artifact profile in role order: kernel,
initial-system, recovery, symbols, microcode, firmware manifest, and policy.
It binds every path, version, byte count, and whole-file SHA-256. The digest
equality is real but not security trust: the manifest and artifacts are
unsigned and attacker-controllable in this development profile.

PKELF1 accepts the frozen x86-64 `ET_DYN` profile, computes the four mapping
ranges, allocates 48 loader pages, copies segments, applies 40 relative
relocations, verifies the loaded image, and binds the entry at offset `0x4000`.
Every file and temporary intake pool is closed or freed before the final map.

Each non-kernel file has a fixed 96-byte PBART1 header. PooleBoot validates its
magic, format version, role, artifact version, reserved-zero bytes, payload
length, and payload SHA-256 before allocating a distinct `EfiLoaderData` page
range. The exact file bytes are copied and page padding is zeroed. PooleBoot
does not invoke an inner payload parser. The independent host media oracle
parses PINIT1, cross-binds its version, and requires unsigned-development
activation denial; no microcode is applied and no initial-system instruction
executes.

## Retained Transfer Storage

Before the first exit attempt, PooleBoot allocates and zeroes all storage needed
after boot services become unavailable:

- 48 kernel pages;
- six distinct PBART1 page ranges, one page each in the canonical fixture;
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

For each exit attempt, PBLIVE3 normalizes the newly captured UEFI map into the
fixed retained work buffer and serializes PBP1 directly into the retained
handoff allocation. The final development profile requires:

- `boot_services_exited=true` in the logical candidate;
- `development_mode=true`;
- exact kernel physical/virtual ranges and entry;
- exact artifact roles 1 through 7, with kernel executable and all six
  auxiliary artifacts physical-only and non-executable;
- exact whole-file digests for all seven artifacts;
- nonzero retained root, stack top, and handoff addresses;
- the PSM1 kernel digest and boot-selection state;
- optional GOP state;
- loader-reserved final-map coverage for kernel, six auxiliary artifacts,
  table, stack, and handoff physical ranges.

The resulting bytes are intentionally not transferable to PooleKernel. The
kernel-entry profile rejects because manifest and artifact signatures are
absent.
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

The Cycle 108 receipt records:

- 76/76 Rust host tests across PooleBoot, PBART1, PBC1/PSM1/PKELF1/PBP1, PKMAP2,
  PBEXIT1, and PKENTRY1;
- two byte-identical PooleBoot builds, PooleKernel builds, and GPT/FAT32 media
  generations;
- two fresh-vars, read-only-media, network-disabled QEMU/OVMF boots;
- 23 identical ordered serial/debugcon markers;
- exact static GOP frames;
- exact 4,728-byte post-exit PBP1 reconstruction with 95 memory entries and
  seven artifact descriptors;
- six PBART1 files totaling 2,663 bytes and six retained pages, independently
  cross-bound to PSM1, guest markers, and final PBP1;
- exact PINIT1 host-oracle validation of the 1,764-byte payload, deterministic
  start order `1,2,3`, and mandatory development activation denial;
- 115/115 integrated negative controls, including inner semantic mutation,
  outer/inner version mismatch, activation overreach, artifact omission, path, role, version,
  payload digest, whole-file digest, overlap, signature overclaim, final-map
  coverage, stale keys, retry exhaustion, descriptor drift, guard mutation,
  post-exit firmware use, transfer overreach, marker drift, and oracle
  divergence.

The observed emulator path succeeds on its first exit attempt. Retry behavior
is covered by the independent state-machine tests and negative controls; the
receipt does not claim that this OVMF run naturally produced a stale map key.

## Nonclaims And Next Boundary

PKLOAD6 does not authenticate PSM1 or any loaded artifact, enforce persistent rollback,
establish the final active kernel address space or framebuffer cache policy,
switch to the guarded stack, call PooleKernel, enforce PINIT1 in PooleBoot,
activate or execute the initial system in PooleKernel, apply microcode or firmware, enforce policy payloads, enforce Secure
Boot, perform measured boot, test a second host, test target firmware, touch
physical media, satisfy N5, or establish production readiness.

The next chronological owner-independent move is
`N5-RECOVERY-SEMANTICS-001`: define and independently validate the recovery
payload contract and its fail-closed selection, lifecycle, and rollback rules
without entering recovery. Transfer-state, signature-trust, and production
transfer remain separately gated by the N5/N6 and owner-controlled N0 work.

## Primary Reference

- UEFI 2.11, [Boot Services](https://uefi.org/specs/UEFI/2.11/07_Services_Boot_Services.html)
