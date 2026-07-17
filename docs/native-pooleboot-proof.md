# Native PooleBoot UEFI Proof

Status: bounded unsigned manifest-bound live-load/pre-exit-PBP1/then-release non-promoting proof
Contract: `POOLEOS-N5-POOLEBOOT-4`
Phase mapping: N5.1, N5.2, N5.3, N5.4, N5.5, N5.7, and N5.8 partial
Receipt: `runs/native_pooleboot_readiness.json`

## Purpose

Cycle 97 replaced the empty compiler fixture with the first Poole-authored freestanding x86-64 UEFI product. Cycles 102-103 added bounded live PBC1/PSM1/PKELF1 selection and load then release. Cycle 104 keeps the kernel allocation live while producing PBLIVE1 bytes from normalized UEFI descriptors, GOP, PBC1 policy, and the PSM1 kernel digest. The aggregate receipt reconstructs exact PBP1 bytes independently from serial and debugcon before all temporary resources are released.

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
- builds a four-record pre-exit PBP1 with zero stack/CR3, 95 normalized memory entries, GOP metadata, and one live kernel artifact; requires the kernel-entry profile to reject; transcripts and rechecks exact bytes; and frees all three PBP1 pools; and
- emits a fixed non-claim marker and returns `EFI_SUCCESS` without calling `ExitBootServices`.

The Cycle 104 media builder emits a 64 MiB ordinary workspace file with a protective MBR, mirrored GPT structures, one FAT32 ESP, two identical FATs, fixed metadata, and exactly four files: `EFI/BOOT/BOOTX64.EFI`, `EFI/POOLEOS/BOOT.CFG`, `EFI/POOLEOS/SYSTEM_A.PBM`, and `EFI/POOLEOS/KERNEL.ELF`. The ordinary-file boundary rejects oversized inputs, workspace escapes, device namespaces, alternate data streams, reserved device names, symlinks, and non-file replacements. It has no physical-media output mode.

## Qualification Contract

`tools/qualify_native_pooleboot.py` performs the complete bounded qualification:

1. Run eight host-side Rust contract tests.
2. Build `PooleBoot.efi` in two clean target directories and require exact bytes.
3. Independently inspect PE32+ machine, subsystem, entry point, timestamp, imports, debug directory, sections, and host leakage.
4. Generate and independently inspect two media images and require exact bytes.
5. Verify the pinned Tier 0 QEMU/OVMF runtime closure and launch profile.
6. Execute two Q35/TCG runs with read-only media, fresh OVMF variables, no guest network, no host acceleration, and loopback-only QMP.
7. Require 21 ordered markers covering filesystem/config/manifest/kernel binding and intake, load, mapping plan, PBP1 production/release, kernel release, GOP, memory map, and return; independently reconstruct exact PBP1 bytes from both transports; require a nonblank Poole-identity GOP frame, exact marker/frame/PBP1 matches, clean QMP quit, and empty QEMU stderr.
8. Execute all 52 negative controls and fail on any unexpected acceptance.
9. Bind every contract, implementation, toolchain, Tier 0, result, command, and claim-boundary input into the public readiness receipt.

The current exact evidence is:

- host contract tests: 8/8;
- clean PE32+ builds: 2/2 exact, 81,408 bytes, SHA-256 `C836D82D7E94E3360DD24C52C830CC298250E5E0DC797FD09003A8AC94FEAB07`;
- clean media generations: 2/2 exact, 67,108,864 bytes, SHA-256 `877D1E4F78479873090630E203C1F9CD7259D44528D8E9A27D4911A9948DABDA`;
- guest runs: 2/2, with 21/21 ordered markers in each run;
- serial/debugcon matches: 2/2;
- exact pre-exit PBP1 matches: 2/2, 4,248 bytes, SHA-256 `5E213BF701454BC597AA028D5C65E6C8EAE53978C29C7572E429BADFFEE9F2D8`;
- GOP frames: 2/2 exact at 1280x800, screenshot SHA-256 `E9D4CFD48C23DBA760AED5B2049B39DCA49A0D172F680D570082EB0680FDFDBD`;
- hostile controls: 52/52; and
- production claims: zero; and
- deterministic readiness receipt: 49,989 bytes, SHA-256 `BC8EAD11CDF63EB44DCB68D8C25B92604FF56F6318C61313B9F80E9E2D35BD32`.

The hostile corpus covers missing, empty, oversized, malformed, path, FAT, PBC1, PSM1, manifest binding, digest, PKELF1, allocation, relocation, W^X, cleanup, marker, oracle-divergence, stale-binding, and claim-overreach failures.

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
KERNEL_MAP PASS
PBP1 PASS
PBP1_RELEASE PASS
KERNEL_RELEASE PASS
GOP PASS
MEMORY_MAP PASS
BOUNDARY
FRAME READY
RETURN EFI_SUCCESS
```

The markers prove only that the instrumented application reached each point under the pinned OVMF profile. The final marker precedes the Rust return and does not prove later firmware behavior.

## Open N5 Work

Cycles 98-103 qualify PBP1, PBC1, PKELF1, PKENTRY1, live load, and PSM1. Cycle 104 closes `N5-PBP1-LIVE-001` with a temporary, logically finalized pre-exit PBP1 producer. The next chronological owner-independent move is `N5-KMAP-001`: retain the kernel and handoff allocations while constructing and auditing the exact page-table ownership and W^X/RELRO mapping plan, still without claiming `ExitBootServices` or transfer.

N5 still requires signature-authenticated manifest and system-artifact selection, persistent rollback enforcement, independent digest-provider review, retained kernel/PBP1 pages and installed W^X/read-only mappings, complete menu/RNG/TCG2 handling, final memory-map normalization, `ExitBootServices` retry behavior, immutable handoff transfer, second-host reproduction, target-firmware execution, and separately authorized physical-media qualification.

## Claim Boundary

This is an unsigned manifest-bound live-load/pre-exit-PBP1/then-release UEFI proof, not the complete PooleBoot loader. It proves exact digest equality to an attacker-controllable manifest and an exact temporary PBP1 snapshot, validates but does not install a mapping plan, then releases all pages. It does not authenticate the manifest or provider, enforce persistent rollback, retain the kernel/PBP1, establish hardware read-only mappings, produce a transferable handoff, call `ExitBootServices`, enter PooleKernel, enforce Secure Boot, perform measured boot, use TPM state, generate or use a key, create a signature, test target firmware, write physical media, build an ISO, or satisfy N5, N38, N39, release, or production gates. The static framebuffer identity is not the final animated PooleGlass boot identity or an accessibility acceptance result.

## Primary References

- UEFI 2.11 System Table and Boot Services: `https://uefi.org/specs/UEFI/2.11/04_EFI_System_Table.html` and `https://uefi.org/specs/UEFI/2.11/07_Services_Boot_Services.html`
- UEFI 2.11 Graphics Output Protocol: `https://uefi.org/specs/UEFI/2.11/12_Protocols_Console_Support.html`
- Rust UEFI target support: `https://doc.rust-lang.org/rustc/platform-support/unknown-uefi.html`
- QEMU QMP screenshot command: `https://www.qemu.org/docs/master/interop/qemu-qmp-ref.html`
