# Native PooleBoot UEFI Proof

Status: bounded unsigned non-promoting proof
Contract: `POOLEOS-N5-POOLEBOOT-1`
Phase mapping: N5.1, N5.2, N5.3, and N5.7 partial
Receipt: `runs/native_pooleboot_readiness.json`

## Purpose

Cycle 97 replaces the empty PooleBoot compiler fixture with a separate product crate while preserving the empty fixture under `native/fixtures/pooleboot`. The product is the first Poole-authored freestanding x86-64 UEFI application in the native boot path. It provides proof-strength evidence for deterministic PE32+ production, deterministic GPT/FAT32 development media, bounded firmware-interface use, observable guest execution, GOP output, and a clean Rust return path.

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

The media builder emits exactly one 64 MiB ordinary workspace file with a protective MBR, mirrored primary and backup GPT headers and entries, CRC32 validation, one FAT32 ESP, two identical FATs, fixed GUIDs and timestamps, and exactly one fallback executable at `EFI/BOOT/BOOTX64.EFI`. Its CLI accepts only an existing regular workspace `.efi` input at or below the frozen 256 KiB ceiling and `.img` or `.json` outputs under `tmp` or `runs/native-tier0`; it rejects oversized inputs, workspace escapes, device namespaces, alternate data streams, reserved device names, symlinks, and non-file replacements before writing.

## Qualification Contract

`tools/qualify_native_pooleboot.py` performs the complete bounded qualification:

1. Run eight host-side Rust contract tests.
2. Build `PooleBoot.efi` in two clean target directories and require exact bytes.
3. Independently inspect PE32+ machine, subsystem, entry point, timestamp, imports, debug directory, sections, and host leakage.
4. Generate and independently inspect two media images and require exact bytes.
5. Verify the pinned Tier 0 QEMU/OVMF runtime closure and launch profile.
6. Execute two Q35/TCG runs with read-only media, fresh OVMF variables, no guest network, no host acceleration, and loopback-only QMP.
7. Require eleven ordered markers, exact serial/debugcon agreement, a nonblank Poole-identity GOP frame, exact marker and frame matches across runs, clean QMP quit, and empty QEMU stderr.
8. Execute all fifteen negative controls and fail on any unexpected acceptance.
9. Bind every contract, implementation, toolchain, Tier 0, result, command, and claim-boundary input into the public readiness receipt.

The current exact evidence is:

- host contract tests: 8/8;
- clean PE32+ builds: 2/2 exact, 13,312 bytes, SHA-256 `B4EF888C588807CBF715E33831A0B52B07CEF5F8BEAFA4FD74D65BD9AA4919B8`;
- clean media generations: 2/2 exact, 67,108,864 bytes, SHA-256 `E8175F70270D6E0A9D4BD1FB16A8814D9B30DD460CE1E6219CCF7AC528600FCA`;
- guest runs: 2/2, with 11/11 ordered markers in each run;
- serial/debugcon matches: 2/2;
- GOP frames: 2/2 exact at 1280x800, screenshot SHA-256 `E9D4CFD48C23DBA760AED5B2049B39DCA49A0D172F680D570082EB0680FDFDBD`;
- hostile controls: 15/15; and
- production claims: zero; and
- deterministic readiness receipt: 22,541 bytes, SHA-256 `D31B029FAFE523C85E20164BAE2F712107FE9E0BDF4DFE151CE07682E04410C8` on two consecutive complete qualifier runs.

The hostile corpus rejects a wrong PE subsystem, wrong machine, debug directory, corrupt primary GPT CRC, corrupt backup GPT CRC, corrupt partition-entry CRC, wrong ESP type with internally recomputed GPT CRCs, mismatched FAT copies, a FAT chain loop, a mutated fallback path, device/outside/source/reserved-name/alternate-stream media targets, marker omission, marker reordering, a blank screenshot, and production-claim overreach.

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
GOP PASS
MEMORY_MAP PASS
BOUNDARY
FRAME READY
RETURN EFI_SUCCESS
```

The markers prove only that the instrumented application reached each point under the pinned OVMF profile. The final marker precedes the Rust return and does not prove later firmware behavior.

## Open N5 Work

The next chronological move is `N5-BOOTPROTO-001`: freeze `ADD-BOOT-001` as canonical versioned handoff bytes with an independent decoder, layout assertions, golden vectors, downgrade controls, malformed records, and fuzzing before kernel entry consumes the protocol.

After that, N5 still requires a bounded boot configuration grammar; complete filesystem and RNG/TCG2 handling; ELF64 validation, relocation, and loading; signed kernel and system-artifact verification; normal/safe/previous/recovery/diagnostic selection; memory-map normalization; `ExitBootServices` retry behavior; immutable handoff transfer; hostile loader coverage; second-host reproduction; exact target-firmware execution; and separately authorized physical-media qualification.

## Claim Boundary

This is an unsigned UEFI proof application, not the complete PooleBoot loader. It does not authenticate, relocate, load, or enter PooleKernel; define or transfer a boot handoff; call `ExitBootServices`; enforce Secure Boot; perform measured boot; use TPM state; generate or use a key; create a signature; test target firmware; write physical media; build an ISO; or satisfy N5, N38, N39, release, or production gates. The static framebuffer identity is not the final animated PooleGlass boot identity or an accessibility acceptance result.

## Primary References

- UEFI 2.11 System Table and Boot Services: `https://uefi.org/specs/UEFI/2.11/04_EFI_System_Table.html` and `https://uefi.org/specs/UEFI/2.11/07_Services_Boot_Services.html`
- UEFI 2.11 Graphics Output Protocol: `https://uefi.org/specs/UEFI/2.11/12_Protocols_Console_Support.html`
- Rust UEFI target support: `https://doc.rust-lang.org/rustc/platform-support/unknown-uefi.html`
- QEMU QMP screenshot command: `https://www.qemu.org/docs/master/interop/qemu-qmp-ref.html`
