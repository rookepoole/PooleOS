# PKLOAD4 Temporary PKMAP1 Activation And Rollback Proof

## Scope

Cycle 105 composes `N5-KLOAD-001`, `N5-MANIFEST-001`,
`N5-PBP1-LIVE-001`, and `N5-KMAP-001` across N5.1, N5.4, N5.5, and
N5.8. PooleBoot discovers the filesystem that contains its own loaded
image, opens and parses live PBC1, opens and parses its selected PSM1 manifest,
binds slot/version/path/file/image/SHA-256/entry fields, reads the real Cycle
101 PKELF1 PooleKernel product, verifies its digest, allocates firmware pages,
materializes segments/BSS/relative relocations, repeats the digest check,
validates the mapping plan, keeps the kernel allocation live while producing a
temporary PBP1 snapshot, activates and verifies an exact temporary higher-half
mapping, restores the firmware CR3, then releases every acquired resource.

This is a load, pre-exit snapshot, temporary mapping, rollback, then release
proof. It is deliberately not a retained-address-space, `ExitBootServices`,
retained-handoff, or transfer proof.

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

After PBP1 temporary pools are released, PKMAP1 requires four-level paging,
CR0.WP, CPU NX support, EFER.NXE, 36-52 physical-address bits, LA57 disabled,
and PCID disabled. PooleBoot allocates four private table pages, clones the
active PML4, requires target PML4 slot 511 to be empty, and installs one
PML4[511]/PDPT[510]/PD[0]/PT path. Every kernel page is a supervisor 4 KiB
leaf. Read-only and read-write pages are NX; executable pages are read-only;
PAT, PCD, and PWT are clear; and the entry must resolve RX.

With interrupts temporarily disabled, PooleBoot loads the candidate CR3,
walks all leaves, reads and hashes the complete higher-half alias, and compares
that hash with the loaded physical image. It also compares the first and last
GOP framebuffer translations, page sizes, effective permissions, and
PAT/PCD/PWT bits against the original root. It then restores and rereads the
exact original CR3 before restoring interrupts or calling firmware. A rollback
mismatch emits a fatal raw diagnostic and halts instead of returning to UEFI
with the wrong root.

Framebuffer equality proves that the cloned address space did not alter the
firmware mapping. It does not prove that the firmware mapping is the final
PooleOS cache policy; that remains an N6/N9 obligation.

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
the three file pools and three PBP1 pools; restores the original CR3; frees all
four private page-table pages; and frees all kernel pages. Cleanup is attempted
on every handled failure path after rollback, and cleanup failure is itself
fatal. Because pages are released, neither the kernel nor candidate tables are
resident when PooleBoot returns.

## Qualification

Run:

```powershell
python tools/qualify_native_kernel_load.py
```

The qualifier performs strict Rust formatting and Clippy checks, the independent
Rust `pkmap1_probe`, Python model agreement, two clean PooleBoot and PooleKernel
builds, two exact four-file media generations, and two fresh-vars QEMU/OVMF
runs. Independent PBC1, PSM1, PKELF1, PBP1, PKMAP1, SHA-256, and FNV decisions
must match 23 live guest markers. Seventy-seven negative controls cover the
earlier media, parser, transcript, claim, and cleanup boundaries plus CPU mode,
target-slot occupancy, alignment, coverage, W+X, physical/table overlap, wrong
leaf targets and flags, large-page substitution, framebuffer drift,
activation, rollback, active-firmware-call, and table-cleanup failures.

The signed receipt is not produced in this cycle. The generated readiness file
remains an unsigned, single-host, non-promoting development record.

## Nonclaims

- Manifest-driven digest equality is proved; signature-backed authentication is not.
- No completed digest-provider security review or persistent rollback state.
- Temporary page-table activation is proved; no retained kernel allocation,
  retained PBP1 container, retained page table, or final address space exists.
- A temporary pre-exit PBP1 producer is proved; no transferable handoff, final
  memory-map/MapKey sequence, or `ExitBootServices` call is proved.
- No kernel entry, panic, recovery, or reset execution evidence.
- No target-firmware, physical-hardware, second-builder, signing, ISO, N5 exit,
  or production-readiness claim.

## Primary References

- UEFI 2.11, [Loaded Image Protocol](https://uefi.org/specs/UEFI/2.11/09_Protocols_EFI_Loaded_Image.html)
- UEFI 2.11, [Media Access Protocols](https://uefi.org/specs/UEFI/2.11/13_Protocols_Media_Access.html)
- UEFI 2.11, [Boot Services](https://uefi.org/specs/UEFI/2.11/07_Services_Boot_Services.html)
- Intel, [Intel 64 and IA-32 Architectures Software Developer Manuals](https://www.intel.com/content/www/us/en/developer/articles/technical/intel-sdm.html)
- AMD, [AMD64 Architecture Programmer's Manual Volume 2](https://docs.amd.com/v/u/en-US/24593_3.44_APM_Vol2)
