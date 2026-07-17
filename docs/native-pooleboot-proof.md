# Native PooleBoot UEFI Proof

Status: bounded unsigned live-load-then-release non-promoting proof
Contract: `POOLEOS-N5-POOLEBOOT-2`
Phase mapping: N5.1, N5.2, N5.3, N5.4, N5.5, and N5.7 partial
Receipt: `runs/native_pooleboot_readiness.json`

## Purpose

Cycle 97 replaced the empty compiler fixture with the first Poole-authored freestanding x86-64 UEFI product. Cycle 102 extends that same product with bounded live PBC1 and PKELF1 reads, firmware-page allocation, kernel materialization, mapping-plan validation, and complete load-then-release cleanup. The aggregate receipt provides deterministic PE32+ and GPT/FAT32 media evidence, observable guest execution, GOP output, guest/oracle load agreement, and a clean Rust return path.

This proof is deliberately smaller than the complete loader. Its evidence can be consumed by later work, but it cannot satisfy the N5 exit gate.

## Implemented Surface

The `native/boot` product crate:

- uses Rust 2024 `no_std`, `no_main`, panic abort, static linking, `efiapi`, and the official `x86_64-unknown-uefi` target;
- validates the UEFI System Table and Boot Services signatures, bounded header sizes, and CRC32 values before dereferencing service entries;
- emits the same ordered diagnostics over polling 16550A COM1 and QEMU debugcon;
- disables the watchdog, attempts firmware console output, and continues through an independently observable fallback path if the console is unavailable;
- enumerates at most 256 configuration-table entries and recognizes bounded ACPI and SMBIOS GUIDs without parsing their payloads;
- locates GOP, accepts only direct RGB or BGR framebuffers, validates dimensions, stride, base alignment, byte bounds, and end-address overflow, and draws a deterministic static Poole identity;
- follows the two-call UEFI memory-map pattern, adds descriptor headroom, validates descriptor size and result bounds, and frees the pool allocation; and
- emits a fixed non-claim marker and returns `EFI_SUCCESS` without calling `ExitBootServices`.

The Cycle 102 media builder emits a 64 MiB ordinary workspace file with a protective MBR, mirrored GPT structures, one FAT32 ESP, two identical FATs, fixed metadata, and exactly three files: `EFI/BOOT/BOOTX64.EFI`, `EFI/POOLEOS/BOOT.CFG`, and `EFI/POOLEOS/KERNEL.ELF`. The ordinary-file boundary rejects oversized inputs, workspace escapes, device namespaces, alternate data streams, reserved device names, symlinks, and non-file replacements. It has no physical-media output mode.

## Qualification Contract

`tools/qualify_native_pooleboot.py` performs the complete bounded qualification:

1. Run eight host-side Rust contract tests.
2. Build `PooleBoot.efi` in two clean target directories and require exact bytes.
3. Independently inspect PE32+ machine, subsystem, entry point, timestamp, imports, debug directory, sections, and host leakage.
4. Generate and independently inspect two media images and require exact bytes.
5. Verify the pinned Tier 0 QEMU/OVMF runtime closure and launch profile.
6. Execute two Q35/TCG runs with read-only media, fresh OVMF variables, no guest network, no host acceleration, and loopback-only QMP.
7. Require seventeen ordered markers covering filesystem/config/kernel intake, load, mapping plan, cleanup, GOP, memory map, and return; require exact serial/debugcon agreement, a nonblank Poole-identity GOP frame, exact marker and frame matches, clean QMP quit, and empty QEMU stderr.
8. Execute all thirty negative controls and fail on any unexpected acceptance.
9. Bind every contract, implementation, toolchain, Tier 0, result, command, and claim-boundary input into the public readiness receipt.

The current exact evidence is:

- host contract tests: 8/8;
- clean PE32+ builds: 2/2 exact, 45,056 bytes, SHA-256 `B97B4A40BACC7BEA7E5C344B8C1FF6A2AEE7985E379749270EE193ADA95E5C4C`;
- clean media generations: 2/2 exact, 67,108,864 bytes, SHA-256 `311A2133174105974FECDAE4CE0122F94E3DF1911176DFFCB2BD8D6A2415E364`;
- guest runs: 2/2, with 17/17 ordered markers in each run;
- serial/debugcon matches: 2/2;
- GOP frames: 2/2 exact at 1280x800, screenshot SHA-256 `E9D4CFD48C23DBA760AED5B2049B39DCA49A0D172F680D570082EB0680FDFDBD`;
- hostile controls: 30/30; and
- production claims: zero; and
- deterministic readiness receipt: 33,689 bytes, SHA-256 `6604FE8D1D54E622AD3B0537D88CAAEAAC32E510522616A9E855C08A7B565508`.

The hostile corpus covers missing, empty, oversized, malformed, short-read, path, FAT, PBC1, PKELF1, allocation, relocation, W^X, cleanup, marker, oracle-divergence, stale-binding, and claim-overreach failures.

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
KERNEL_FILE PASS
KERNEL_LOAD PASS
KERNEL_MAP PASS
KERNEL_RELEASE PASS
GOP PASS
MEMORY_MAP PASS
BOUNDARY
FRAME READY
RETURN EFI_SUCCESS
```

The markers prove only that the instrumented application reached each point under the pinned OVMF profile. The final marker precedes the Rust return and does not prove later firmware behavior.

## Open N5 Work

Cycles 98-101 qualify PBP1, PBC1, PKELF1, and the real PKENTRY1 PooleKernel product. Cycle 102 proves bounded live load then release. The next chronological move is `N5-MANIFEST-001`: freeze a canonical manifest and replace the fixed development path with digest-bound manifest-driven selection without claiming signature trust.

N5 still requires authenticated manifest and system-artifact selection; retained kernel pages and installed W^X mappings; complete menu, rollback, RNG, and TCG2 handling; live PBP1 population; final memory-map normalization; `ExitBootServices` retry behavior; immutable handoff transfer; second-host reproduction; target-firmware execution; and separately authorized physical-media qualification.

## Claim Boundary

This is an unsigned live-load-then-release UEFI proof, not the complete PooleBoot loader. It loads and relocates PooleKernel only at a fixed untrusted development path, validates but does not install a mapping plan, then releases the pages. It does not authenticate a manifest, retain the kernel, define or transfer a live handoff, call `ExitBootServices`, enter PooleKernel, enforce Secure Boot, perform measured boot, use TPM state, generate or use a key, create a signature, test target firmware, write physical media, build an ISO, or satisfy N5, N38, N39, release, or production gates. The static framebuffer identity is not the final animated PooleGlass boot identity or an accessibility acceptance result.

## Primary References

- UEFI 2.11 System Table and Boot Services: `https://uefi.org/specs/UEFI/2.11/04_EFI_System_Table.html` and `https://uefi.org/specs/UEFI/2.11/07_Services_Boot_Services.html`
- UEFI 2.11 Graphics Output Protocol: `https://uefi.org/specs/UEFI/2.11/12_Protocols_Console_Support.html`
- Rust UEFI target support: `https://doc.rust-lang.org/rustc/platform-support/unknown-uefi.html`
- QEMU QMP screenshot command: `https://www.qemu.org/docs/master/interop/qemu-qmp-ref.html`
