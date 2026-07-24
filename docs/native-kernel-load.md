# PKLOAD6 Profile Artifact Load And Retained Exit Proof

## Scope

PKLOAD6 is the bounded live integration proof for PooleBoot's current N5.6 and
N5.8 development boundary. It reads PBC1 and unsigned PSM1 from the EFI system
partition, selects and digest-binds the real PKELF1 PooleKernel plus six exact
profile artifacts, validates each non-kernel PBART1 envelope, retains exact
PSM1, PBTP1, and PBTS1 copies beside them, reparses all six inner payloads from
their exact retained firmware-page copies, independently
reconstructs that result in the host oracle, parses separate PBTRUST1 immutable
policy and mutable acceptance-state development candidates, cross-binds them
to the exact manifest, kernel, retained set, revocation set, roles, and rollback
floors, requires unsigned-policy denial with zero effects, retains every
loaded page range and PKMAP2 transfer allocation, creates final
development-profile PBP1 bytes, exits UEFI boot services, and halts before
kernel transfer.

The machine-readable contract is `specs/native-kernel-load-contract.json`.
`native/inner` is the allocation-free target validator.
`native/trust` is the allocation-free PBTRUST1 validator.
`runtime/native_inner_live.py`, `runtime/native_boot_trust.py`, and
`runtime/native_kernel_load.py` are the independent retained-set, trust, media,
marker, PBP1, map, and claim oracles.
`tools/qualify_native_kernel_load.py` builds and boots the product twice and
emits `runs/native_kernel_load_readiness.json`.

## Live Intake

The qualified media contains exactly twelve deterministic files:

- `EFI/BOOT/BOOTX64.EFI`;
- `EFI/POOLEOS/BOOT.CFG`;
- `EFI/POOLEOS/SYSTEM_A.PBM`;
- `EFI/POOLEOS/KERNEL.ELF`;
- `EFI/POOLEOS/INITIAL.PBA`;
- `EFI/POOLEOS/RECOVERY.PBA`;
- `EFI/POOLEOS/SYMBOLS.PBA`;
- `EFI/POOLEOS/MICROCOD.PBA`;
- `EFI/POOLEOS/FIRMWARE.PBA`;
- `EFI/POOLEOS/POLICY.PBA`;
- `EFI/POOLEOS/TRUST.PBT`;
- `EFI/POOLEOS/TRUSTST.PBS`.

PooleBoot obtains Loaded Image and Simple File System protocols, opens the root,
parses bounded PBC1 configuration, then parses bounded PSM1. PSM1 selects slot
1, version 1, and the exact kernel path, file size, image size, and SHA-256.
PSM1 requires the exact seven-entry manifest profile in role order: kernel,
initial-system, recovery, symbols, microcode, firmware manifest, and policy.
It binds every path, version, byte count, and whole-file SHA-256. The digest
equality is real but not security trust: the manifest and artifacts are
unsigned and attacker-controllable in this development profile.

PKELF1 accepts the frozen x86-64 `ET_DYN` profile, computes the four mapping
ranges, allocates 70 loader pages, copies segments, applies 593 relative
relocations, verifies the 286,720-byte loaded image, and binds the entry at
offset `0x8000`.
Every file and temporary intake pool is closed or freed before the final map.

Each non-kernel file has a fixed 96-byte PBART1 header. PooleBoot validates its
magic, format version, role, artifact version, reserved-zero bytes, payload
length, and payload SHA-256 before allocating a distinct `EfiLoaderData` page
range. The exact file bytes are copied and page padding is zeroed. After every
copy, PooleBoot reconstructs slices directly from the retained page addresses
and reparses PINIT1, PREC1, PSYM1, PMCU1, PFWM1, and PPOL1. It binds PPOL1's
five payload digests to roles 2 through 6, binds all eleven policy routes to the
exact PINIT1 capabilities, and requires each development activation or
consumption gate to fail first at the missing outer signature. A
domain-separated SHA-256 binds the six ordered retained PBART1 files. The live
receipt reports zero authority grants, authorized actions, state writes, and
hardware observations. The independent host media oracle reconstructs the
same result from the media. PREC1 state transitions remain host-model evidence;
PooleBoot neither reads nor writes persistent state. PSM1, PBTP1, and PBTS1
are copied to distinct final allocations, reparsed from the destination bytes,
and retained after their source pools are freed. No recovery,
initial-system, symbol, policy, microcode, or firmware action executes.

PBTRUST1 then parses a 320-byte PBTP1 immutable-policy candidate and a 256-byte
PBTS1 mutable acceptance-state candidate. It validates fixed geometry, body
digests, signer/revocation shapes, redundant-copy and previous-state-chain
shapes, and fourteen exact policy/state/observed-boot bindings. The live
development records bind the exact PSM1, PooleKernel, retained-set digest,
revocation-set identity, seven artifact roles, policy version, secure-version
floor, trust epoch, and state generation, then deny exactly at
`pbtrust_policy_unsigned`. The ESP files are candidates only: they are not
authenticated, monotonic, writable, selected, repaired, migrated, or accepted
as persistent authority. PBTRUST1 is separate from PREC1 boot-attempt state.

## Retained Transfer Storage

Before the first exit attempt, PooleBoot allocates and zeroes all storage needed
after boot services become unavailable:

- 66 kernel pages;
- six distinct PBART1 page ranges, one page each in the canonical fixture;
- one exact-file PSM1 range;
- one exact-file PBTP1 range;
- one exact-file PBTS1 range;
- four PKMAP2 page-table pages;
- fourteen kernel-stack pages with one absent guard page on each side;
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
- exact artifact roles 1 through 7 followed by roles 9 through 11, with the
  kernel executable and all nine non-kernel files physical-only and
  non-executable; role 8 remains the absent reserved crash-kernel slot;
- exact whole-file byte counts and digests for all ten descriptors;
- nonzero retained root, stack top, and handoff addresses;
- the PSM1 kernel digest and boot-selection state;
- optional GOP state;
- loader-reserved final-map coverage for kernel, six auxiliary artifacts,
  PSM1, PBTP1, PBTS1, table, stack, and handoff physical ranges.

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

The Cycle 128-refreshed default-path receipt records:

- 155/155 Rust host tests across PooleBoot, PBART1, the six-format retained-set
  validator, PBTRUST1, PBC1/PSM1/PKELF1/PBP1, PKMAP2, PBEXIT1, and PKENTRY1;
- two byte-identical PooleBoot builds, PooleKernel builds, and GPT/FAT32 media
  generations;
- two fresh-vars, read-only-media, network-disabled QEMU/OVMF boots;
- 25 identical ordered serial/debugcon markers;
- exact static GOP frames;
- exact 5,048-byte post-exit PBP1 reconstruction with 97 memory entries and
  ten artifact descriptors;
- six PBART1 files totaling 8,761 bytes and six retained pages, independently
  cross-bound to PSM1, guest markers, and final PBP1;
- exact 320-byte PBTP1 and 256-byte PBTS1 candidates, fourteen cross-bindings,
  one unsigned-policy denial, and zero signature verifications, authority
  grants, or state writes;
- exact PINIT1 host-oracle validation of the 1,764-byte payload, deterministic
  start order `1,2,3`, and mandatory development activation denial;
- exact PREC1 host-oracle validation of the 992-byte policy, two slots, ten
  failure routes, seven authority requirements, a 128-byte mutable state
  contract, bounded transitions, and mandatory development activation denial;
- exact PSYM1 host-oracle validation of the public-only image-relative index,
  five-part image/debug/source identity, three public symbols, bounded lookup,
  source-path exclusion, pointer redaction, split-debug correspondence, and
  mandatory development consumption denial;
- exact synthetic-only PMCU1 host-oracle validation of the 1,408-byte payload,
  two patches for `AuthenticAMD` CPUID `0x00B40F40`, bounded revision/floor and
  reset-known-good selection, BSP/AP apply prerequisites, mixed-revision and
  post-apply checks, and mandatory development activation denial;
- exact synthetic-only PFWM1 host-oracle validation of the 1,312-byte payload,
  three external-payload components, two dependency edges, exact hardware and
  version floors, one-at-a-time dry-run ordering, post-reset receipt rules, and
  mandatory development activation denial;
- exact qualification-only PPOL1 host-oracle validation of the 1,984-byte
  payload, six exact modes, eleven PINIT1-cross-bound capability rules,
  default-deny authority intersection, safe/recovery floors, firmware
  physical-presence separation, durable receipt rules, and mandatory
  development activation denial;
- an exact six-file PBART1 retained set totaling 8,761 bytes with SHA-256
  `E80E88314DD131BF5D3DE61C01CD0DF91A4087555BEBE60003053F4A9A64DCFB`,
  plus exact retained PSM1, PBTP1, and PBTS1 files, nine target parsers,
  manifest/inner/trust cross-bindings, exact unsigned-policy denial, and zero
  authority/action/state/hardware effects;
- 155/155 integrated negative controls, including exact retained PSM1/PBTP1/
  PBTS1 descriptor size and digest substitution plus PINIT1, PREC1, PSYM1, PMCU1,
  PFWM1, and PPOL1 inner
  semantic mutation, outer/inner version mismatch, activation overreach,
  artifact omission, path, role, version,
  payload digest, whole-file digest, overlap, signature overclaim, final-map
  coverage, stale keys, retry exhaustion, descriptor drift, guard mutation,
  post-exit firmware use, transfer overreach, PBTRUST1 policy/state
  substitution, rollback, authority overreach, marker drift, and oracle
  divergence.

The observed emulator path succeeds on its first exit attempt. Retry behavior
is covered by the independent state-machine tests and negative controls; the
receipt does not claim that this OVMF run naturally produced a stale map key.

## Nonclaims And Next Boundary

PKLOAD6 does not authenticate PSM1, any loaded artifact, PBTP1, PBTS1, or a
revocation store; verify policy signatures, Secure Boot state, or an
authenticated redundant monotonic backend; select, repair, migrate, or update
persistent rollback state;
establish the final active kernel address space or framebuffer cache policy,
switch to the guarded stack, call PooleKernel, grant authority from PINIT1,
PREC1, PSYM1, PMCU1, PFWM1, or PPOL1, live-execute the independently qualified
PooleKernel revalidation path, persist PREC1 mutable state, activate or execute the initial
system or recovery in PooleKernel, consume symbols or create diagnostic
authority, validate a real vendor microcode or firmware payload, observe privileged
per-processor revisions or live firmware inventory, load an updater, apply microcode or
firmware, create a capability, apply a policy decision, grant PooleGlyph
executable authority, enforce Secure
Boot, perform measured boot, test a second host, test target firmware, touch
physical media, satisfy N5, or establish production readiness.

Cycle 118 separately closes the opt-in QEMU-only
`N5-KERNEL-TRANSFER-001` development boundary without changing this default
PKLOAD6 stop. Cycle 119 separately closes the bounded BSP-only PKTRAP1 slice,
Cycle 120 closes the bounded qemu64 read-only PKCPU1 slice, and Cycle 121
closes only the pure PKERR1 exact-target policy boundary while retaining direct
errata and numeric microcode-floor stop-ship gaps. Cycles 122 and 123 separately
close the bounded PKXSTATE1 ownership and PKXEXC1 exception-delivery slices,
Cycle 124 closes only the read-only PKMSR1 privileged-MSR policy slice. Cycle
125 separately closes the bounded selector-8 PKPMM1 physical-page ownership and
allocator foundation after expanding the shared guarded stack to fourteen
pages. Cycle 126 separately closes the bounded selector-9 PKVM1 inactive
virtual-memory foundation. Cycle 127 closes the bounded selector-10 PKVM2
active-root move. Cycle 128 upgrades selector 8 to PKPMM2 with full-page
scrub-before-allocation and scrub-before-reuse, readback, receipts, exact-reuse
residue rejection, fault rollback, and temporary-alias revocation. Cycle 129
upgrades it to PKPMM3 with a retained five-page guarded metadata arena,
complete-manager transactional handoff, integrity seal, corruption rejection,
rollback, and release exclusion. Cycle 130 upgrades it to PKPMM4 with monotonic
reclaim stages, complete streamed preflight, scrub-before-admission, retained-
range exclusion, atomic metadata commit, idempotence, and immutable Boot Services
reclaim receipts while ACPI remains held. Cycle 131 upgrades it to PKPMM5 with
guarded generation-owned ledgers and one explicit atomic 4-to-8-page growth.
Cycle 132 upgrades it to PKPMM6 with exact-demand pressure checks, automatic
4/8/15/29-page generation growth, rollback/retry headroom, three scrubbed
predecessor retirements, bounded-window soft fallback, and hard rejection before
physical or ownership effects when the 58-page next layout cannot fit. These
remain one-BSP development profiles with no interrupt-context/concurrent/SMP
allocation, complete direct map, shootdown, ring 3, complete ACPI consumer
integration, heap, pager, target, or production claim. The next chronological
owner-independent move is `N9-PMM-ACPI-CONSUMER-001`.
Capability creation, lifecycle execution, signature trust, authenticated
persistent state, production transfer, and physical-target qualification remain
separately gated by N5/N6 and owner-controlled N0 work.

## Primary Reference

- UEFI 2.11, [Boot Services](https://uefi.org/specs/UEFI/2.11/07_Services_Boot_Services.html)
- seL4, [CapDL language specification](https://docs.sel4.systems/projects/capdl/lang-spec.html)
- Fuchsia, [Component lifecycle](https://fuchsia.dev/docs/concepts/components/v2/lifecycle)
