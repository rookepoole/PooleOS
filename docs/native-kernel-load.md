# PKLOAD3 Live Manifest-Bound Pre-Exit PBP1 Proof

## Scope

Cycle 104 composes `N5-KLOAD-001`, `N5-MANIFEST-001`, and
`N5-PBP1-LIVE-001` across N5.1, N5.4, N5.5, and N5.8. PooleBoot discovers the filesystem that contains its own loaded
image, opens and parses live PBC1, opens and parses its selected PSM1 manifest,
binds slot/version/path/file/image/SHA-256/entry fields, reads the real Cycle
101 PKELF1 PooleKernel product, verifies its digest, allocates firmware pages,
materializes segments/BSS/relative relocations, repeats the digest check,
validates the mapping plan, keeps the kernel allocation live while producing a
temporary PBP1 snapshot, then releases every acquired resource.

This is a load, pre-exit-snapshot, then release proof. It is deliberately not a
mapping, `ExitBootServices`, retained-handoff, or transfer proof.

## Firmware Call Chain

1. `HandleProtocol(image_handle, EFI_LOADED_IMAGE_PROTOCOL)` obtains the loaded
   image record.
2. `DeviceHandle` identifies the device from which PooleBoot was loaded.
3. `HandleProtocol(DeviceHandle, EFI_SIMPLE_FILE_SYSTEM_PROTOCOL)` obtains the
   filesystem interface.
4. `OpenVolume()` obtains the root file handle.
5. Read-only `Open`, bounded `GetInfo`, exact `Read`, and `Close` operations
   consume `\EFI\POOLEOS\BOOT.CFG`, its selected
   `\EFI\POOLEOS\SYSTEM_A.PBM`, and the manifest-selected kernel path.

The GUIDs, layouts, paths, limits, and required cleanup are frozen in
`specs/native-kernel-load-contract.json`.

## Trust Boundary

The live `BOOT.CFG` selects a PSM1 manifest and slot. PSM1 binds the exact
kernel path, version, file and image sizes, SHA-256 digest, PKELF1 format, and
PKENTRY1 contract. PooleBoot rejects any disagreement and reports
`selection=manifest_digest_untrusted`.

The manifest is unsigned. Hashing proves equality to the bytes named by that
unsigned manifest; it does not authenticate who selected those bytes. No
signature, revocation, persistent rollback state, Secure Boot, TCG2, or TPM
policy promotes the selection to trusted state.

## Allocation And Load

PooleBoot rejects zero, directory, unknown-attribute, oversized, malformed, and
short-read inputs. It inspects PKELF1 before allocation, requests exact 4 KiB
`EfiLoaderData` pages, then independently repeats validation while loading at
the returned physical base. The expected final mapping plan is `r`, `rx`, `r`,
and `rw`; any writable-executable mapping fails closed.

Page tables are not created or activated. The plan is evidence about required
future mappings, not evidence that hardware permissions were enforced.

## Pre-Exit PBP1

Before the snapshot, PooleBoot allocates bounded raw-map, normalized-map, and
PBP1 container pools. The final call for this provisional snapshot therefore
observes those allocations and the still-live kernel pages. PBLIVE1 honors the
returned descriptor stride and version, maps every standard UEFI memory type,
preserves attributes and source type, sorts by physical start, and rejects zero,
overflowing, unsupported, or overlapping ranges.

The exact PBP1 records are required core, required normalized memory map,
optional GOP framebuffer, and one required kernel artifact. The artifact binds
the live physical allocation, PKELF1 virtual bounds and entry, and full PSM1
SHA-256. Core binds the PBC1 attempt limit and slot. Because this is pre-exit,
`BOOT_SERVICES_EXITED` is clear and stack and CR3 are zero; the kernel-entry
profile must reject. No random seed, early log, TCG log, signature, or measured
state enters the public transcript.

PooleBoot emits the exact bytes over both serial and debugcon, recomputes the
FNV and PBP1 decode/profile after emission, and only then frees all three pools.
This proves logical byte stability during the bounded observation, not a
hardware read-only mapping. A later transfer implementation must recapture the
current map and MapKey after all retained allocations are final.

## Cleanup

The success path closes the config, manifest, kernel, and root handles; frees
the three file pools and three PBP1 pools; and frees all kernel pages. Cleanup is
attempted on every handled failure path, and cleanup failure is itself fatal.
Because pages are released, the kernel is not resident when PooleBoot returns.

## Qualification

Run:

```powershell
python tools/qualify_native_kernel_load.py
```

The qualifier performs strict Rust formatting and Clippy checks, 49 Rust host
tests across PBP1/PBLIVE1/manifest/bootload/PooleBoot/PooleKernel, two exact 81,408-byte
PooleBoot builds, two clean PooleKernel builds, two exact four-file media
generations, and two fresh-vars QEMU/OVMF runs. Independent Python PBC1, PSM1,
PKELF1, PBP1, and SHA-256 decisions must match 21 live guest markers. Fifty-two
negative controls cover file, FAT, path, config, manifest, digest, kernel,
marker, W^X, cleanup, descriptor/profile/transcript mutation,
oracle-divergence, overclaim, and stale-binding failures. Both runs reconstruct
the same 4,248-byte PBP1 (`5E213BF701454BC597AA028D5C65E6C8EAE53978C29C7572E429BADFFEE9F2D8`)
with 95 normalized memory entries.

The signed receipt is not produced in this cycle. The generated readiness file
remains an unsigned, single-host, non-promoting development record.

## Nonclaims

- Manifest-driven digest equality is proved; signature-backed authentication is not.
- No completed digest-provider security review or persistent rollback state.
- No retained kernel allocation, retained PBP1 container, or installed page tables.
- A temporary pre-exit PBP1 producer is proved; no transferable handoff, final
  memory-map/MapKey sequence, or `ExitBootServices` call is proved.
- No kernel entry, panic, recovery, or reset execution evidence.
- No target-firmware, physical-hardware, second-builder, signing, ISO, N5 exit,
  or production-readiness claim.

## Primary References

- UEFI 2.11, [Loaded Image Protocol](https://uefi.org/specs/UEFI/2.11/09_Protocols_EFI_Loaded_Image.html)
- UEFI 2.11, [Media Access Protocols](https://uefi.org/specs/UEFI/2.11/13_Protocols_Media_Access.html)
- UEFI 2.11, [Boot Services](https://uefi.org/specs/UEFI/2.11/07_Services_Boot_Services.html)
