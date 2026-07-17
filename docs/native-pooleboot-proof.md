# Native PooleBoot UEFI Proof

Status: bounded unsigned live-load/pre-exit-PBP1/temporary-PKMAP1/rollback/release non-promoting proof
Contract: `POOLEOS-N5-POOLEBOOT-5`
Phase mapping: N5.1, N5.2, N5.3, N5.4, N5.5, N5.7, and N5.8 partial
Receipt: `runs/native_pooleboot_readiness.json`

## Purpose

Cycle 97 replaced the empty compiler fixture with the first Poole-authored freestanding x86-64 UEFI product. Cycles 102-104 added bounded live PBC1/PSM1/PKELF1 selection, temporary PBP1 production, and complete release. Cycle 105 adds PKMAP1: an exact temporary higher-half kernel mapping is activated under a cloned four-level root, audited in place, rolled back to the exact original CR3, and fully released. The aggregate receipt reconstructs PBP1 and PKMAP1 state independently from serial and debugcon before accepting the return path.

This proof is deliberately smaller than the complete loader. Its evidence can be consumed by later work, but it cannot satisfy the N5 exit gate.

## Implemented Surface

The `native/boot` product crate:

- uses Rust 2024 `no_std`, `no_main`, panic abort, static linking, `efiapi`, and the official `x86_64-unknown-uefi` target;
- validates the UEFI System Table and Boot Services signatures, bounded header sizes, and CRC32 values before dereferencing service entries;
- emits the same ordered diagnostics over polling 16550A COM1 and QEMU debugcon;
- disables the watchdog, attempts firmware console output, and continues through an independently observable fallback path if the console is unavailable;
- enumerates at most 256 configuration-table entries and recognizes bounded ACPI and SMBIOS GUIDs without parsing their payloads;
- locates GOP, accepts only direct RGB or BGR framebuffers, validates dimensions, stride, base alignment, byte bounds, and end-address overflow, and draws a deterministic static Poole identity;
- follows the two-call UEFI memory-map pattern, adds descriptor headroom, validates descriptor size and result bounds, and frees the pool allocation;
- builds a four-record pre-exit PBP1 with zero stack/CR3, 95 normalized memory entries, GOP metadata, and one live kernel artifact; requires the kernel-entry profile to reject; transcripts and rechecks exact bytes; and frees all three PBP1 pools;
- requires CR0.WP and processor/EFER NX, clones the active PML4 into four private table pages, installs 48 exact supervisor 4 KiB higher-half leaves with zero W+X, activates and audits the candidate CR3, preserves framebuffer translation/cache bits, restores the exact original CR3 before firmware use, and frees all table pages; and
- emits a fixed non-claim marker and returns `EFI_SUCCESS` without calling `ExitBootServices`.

The Cycle 105 media builder emits a 64 MiB ordinary workspace file with a protective MBR, mirrored GPT structures, one FAT32 ESP, two identical FATs, fixed metadata, and exactly four files: `EFI/BOOT/BOOTX64.EFI`, `EFI/POOLEOS/BOOT.CFG`, `EFI/POOLEOS/SYSTEM_A.PBM`, and `EFI/POOLEOS/KERNEL.ELF`. The ordinary-file boundary rejects oversized inputs, workspace escapes, device namespaces, alternate data streams, reserved device names, symlinks, and non-file replacements. It has no physical-media output mode.

## Qualification Contract

`tools/qualify_native_pooleboot.py` performs the complete bounded qualification:

1. Run eight host-side Rust contract tests.
2. Build `PooleBoot.efi` in two clean target directories and require exact bytes.
3. Independently inspect PE32+ machine, subsystem, entry point, timestamp, imports, debug directory, sections, and host leakage.
4. Generate and independently inspect two media images and require exact bytes.
5. Verify the pinned Tier 0 QEMU/OVMF runtime closure and launch profile.
6. Execute two Q35/TCG runs with read-only media, fresh OVMF variables, no guest network, no host acceleration, and loopback-only QMP.
7. Require 23 ordered markers covering filesystem/config/manifest/kernel binding and intake, load, PBP1 production/release, PKMAP1 plan/activation/rollback, kernel release, GOP, memory map, and return; independently reconstruct exact PBP1 and PKMAP1 evidence from both transports; require a nonblank Poole-identity GOP frame, exact marker/frame/PBP1 matches, clean QMP quit, and empty QEMU stderr.
8. Execute all 77 negative controls and fail on any unexpected acceptance.
9. Bind every contract, implementation, toolchain, Tier 0, result, command, and claim-boundary input into the public readiness receipt.

The current exact evidence is:

- host contract tests: 8/8;
- clean PE32+ builds: 2/2 exact, 94,720 bytes, SHA-256 `7C3365BDC88D9E3B9D8CA9C0832E52527650C11563C48C2AD81233F5E123B4AD`;
- clean media generations: 2/2 exact, 67,108,864 bytes, SHA-256 `26AC661BEEE8EC1E2FA9D38EC610FC38677709E136E750A5352D1AEF5FA9EE90`;
- guest runs: 2/2, with 23/23 ordered markers in each run;
- serial/debugcon matches: 2/2;
- exact pre-exit PBP1 matches: 2/2, 4,248 bytes, SHA-256 `7643A0C05838F2E6862CE9FA6DA604B02EDC7F3B7CC4F731ECAEC5C90C8E2279`;
- exact PKMAP1 matches: 2/2, with 48 leaves, `6/28/14` read-only/read-execute/read-write pages, leaf fingerprint `A671D0D8901064A5`, full-image FNV-1a `80F8CD80B30B2EBA`, exact original-CR3 restoration, and four freed table pages;
- GOP frames: 2/2 exact at 1280x800, screenshot SHA-256 `E9D4CFD48C23DBA760AED5B2049B39DCA49A0D172F680D570082EB0680FDFDBD`;
- hostile controls: 77/77; and
- production claims: zero; and
- deterministic readiness receipt: 59,749 bytes, SHA-256 `874D85A0C49784C917C5E4BAB5166A54791DB09ED38DD339A2FE76FE229D980C`.

The hostile corpus covers missing, empty, oversized, malformed, path, FAT, PBC1, PSM1, manifest binding, digest, PKELF1, allocation, relocation, W^X, cleanup, marker, oracle-divergence, stale-binding, claim-overreach, WP/NX/LA57/PCID profile drift, occupied roots, malformed map coverage/ranges, table overlap, wrong leaves, large pages, framebuffer drift, activation/rollback failure, firmware calls while active, and table cleanup failure.

## Reproduction

From the repository root, with the workspace-local Rust and Tier 0 toolchains already qualified:

```powershell
python .\tools\qualify_native_pooleboot.py
python -m unittest -v tests.test_native_pooleboot
python .\tools\pooleos_doctor.py --no-runtime
```

For an explicitly named ordinary-file image only:

```powershell
python .\tools\build_native_pooleboot_media.py --efi <PooleBoot.efi> --out .\tmp\pooleboot-proof.img --inspection .\tmp\pooleboot-proof-inspection.json
```

The command enforces the ordinary-workspace-file boundary and rejects physical disk, partition, volume, device-namespace, mounted-image, and firmware paths. Physical-media writing remains separately approval-gated.

## Ordered Markers

The current run records these semantic stages in order:

```text
ENTRY
SYSTEM_TABLE PASS
BOOT_SERVICES PASS
WATCHDOG
CONSOLE PASS_OR_FALLBACK
CONFIG PASS
FILESYSTEM PASS
BOOTCFG PASS
MANIFEST PASS
KERNEL_BINDING PASS
KERNEL_FILE PASS
KERNEL_LOAD PASS
PBP1 PASS
PBP1_RELEASE PASS
KERNEL_MAP_PLAN PASS
KERNEL_MAP_ACTIVE PASS
KERNEL_MAP_ROLLBACK PASS
KERNEL_RELEASE PASS
GOP PASS
MEMORY_MAP PASS
BOUNDARY
FRAME READY
RETURN EFI_SUCCESS
```

The markers prove only that the instrumented application reached each point under the pinned OVMF profile. The final marker precedes the Rust return and does not prove later firmware behavior.

## Open N5 Work

Cycles 98-104 qualify PBP1, PBC1, PKELF1, PKENTRY1, live load, PSM1, and the temporary live handoff. Cycle 105 closes `N5-KMAP-001` with temporary candidate-root activation, complete alias verification, and exact rollback. The next chronological owner-independent move is `N5-HANDOFF-001`: retain the qualified kernel mappings and immutable PBP1, normalize and retry the final memory map, call `ExitBootServices`, and prove that no later boot-service call occurs, still without claiming kernel transfer.

N5 still requires signature-authenticated manifest and system-artifact selection, persistent rollback enforcement, independent digest-provider review, retained kernel/PBP1/page-table pages, final framebuffer cache policy, complete menu/RNG/TCG2 handling, final memory-map normalization, `ExitBootServices` retry behavior, immutable handoff transfer, second-host reproduction, target-firmware execution, and separately authorized physical-media qualification.

## Claim Boundary

This is an unsigned manifest-bound live-load/pre-exit-PBP1/temporary-PKMAP1/rollback/release UEFI proof, not the complete PooleBoot loader. It proves exact digest equality to an attacker-controllable manifest, an exact temporary PBP1 snapshot, and temporary hardware activation of an exact higher-half W^X map whose complete alias and framebuffer invariants are audited before exact rollback and release. It does not authenticate the manifest or provider, enforce persistent rollback, retain the kernel/PBP1/page tables, establish the final address space or framebuffer cache policy, produce a transferable handoff, call `ExitBootServices`, enter PooleKernel, enforce Secure Boot, perform measured boot, use TPM state, generate or use a key, create a signature, test target firmware, write physical media, build an ISO, or satisfy N5, N38, N39, release, or production gates. The static framebuffer identity is not the final animated PooleGlass boot identity or an accessibility acceptance result.

## Primary References

- UEFI 2.11 System Table and Boot Services: `https://uefi.org/specs/UEFI/2.11/04_EFI_System_Table.html` and `https://uefi.org/specs/UEFI/2.11/07_Services_Boot_Services.html`
- UEFI 2.11 Graphics Output Protocol: `https://uefi.org/specs/UEFI/2.11/12_Protocols_Console_Support.html`
- Rust UEFI target support: `https://doc.rust-lang.org/rustc/platform-support/unknown-uefi.html`
- QEMU QMP screenshot command: `https://www.qemu.org/docs/master/interop/qemu-qmp-ref.html`
- Intel 64 and IA-32 Architectures Software Developer's Manual: `https://www.intel.com/content/www/us/en/developer/articles/technical/intel-sdm.html`
- AMD64 Architecture Programmer's Manual, Volume 2: `https://docs.amd.com/v/u/en-US/24593_3.44_APM_Vol2`
