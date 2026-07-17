# PKLOAD1 Live Kernel Load Proof

## Scope

`N5-KLOAD-001` advances N5.1, N5.4, and N5.5 with one bounded live UEFI
proof. PooleBoot discovers the filesystem that contains its own loaded image,
opens and parses `PBC1`, reads the real Cycle 101 `PKELF1` PooleKernel product,
allocates firmware pages, materializes segments/BSS/relative relocations, checks
the mapping plan, and releases every acquired resource before returning.

This is a load-then-release proof. It is deliberately not a transfer proof.

## Firmware Call Chain

1. `HandleProtocol(image_handle, EFI_LOADED_IMAGE_PROTOCOL)` obtains the loaded
   image record.
2. `DeviceHandle` identifies the device from which PooleBoot was loaded.
3. `HandleProtocol(DeviceHandle, EFI_SIMPLE_FILE_SYSTEM_PROTOCOL)` obtains the
   filesystem interface.
4. `OpenVolume()` obtains the root file handle.
5. Read-only `Open`, bounded `GetInfo`, exact `Read`, and `Close` operations
   consume `\EFI\POOLEOS\BOOT.CFG` and `\EFI\POOLEOS\KERNEL.ELF`.

The GUIDs, layouts, paths, limits, and required cleanup are frozen in
`specs/native-kernel-load-contract.json`.

## Trust Boundary

The live `BOOT.CFG` is parsed by PBC1 and its default entry is observed. PBC1
names a manifest, not a direct kernel path. This bounded cycle therefore uses
the fixed `KERNEL.ELF` development path and marks it `fixed_untrusted` in the
guest transcript. No manifest is opened, and no hash, signature, revocation,
Secure Boot, TCG2, or TPM policy promotes the kernel to trusted state.

## Allocation And Load

PooleBoot rejects zero, directory, unknown-attribute, oversized, malformed, and
short-read inputs. It inspects PKELF1 before allocation, requests exact 4 KiB
`EfiLoaderData` pages, then independently repeats validation while loading at
the returned physical base. The expected final mapping plan is `r`, `rx`, `r`,
and `rw`; any writable-executable mapping fails closed.

Page tables are not created or activated. The plan is evidence about required
future mappings, not evidence that hardware permissions were enforced.

## Cleanup

The success path closes the config file, kernel file, and root handle; frees
the config and kernel pools; and frees all kernel pages. Cleanup is attempted on
every handled failure path, and cleanup failure is itself fatal. The successful
marker reports exact counts. Because pages are released, the kernel is not
resident when PooleBoot returns.

## Qualification

Run:

```powershell
python tools/qualify_native_kernel_load.py
```

The qualifier performs strict Rust formatting and Clippy checks, 33 Rust host
tests across bootload/PooleBoot/PooleKernel, two clean PooleBoot builds, two
clean PooleKernel builds, two exact media generations, and two fresh-vars
QEMU/OVMF runs. The independent Python PBC1 and PKELF1 implementations must
match the live guest markers and loaded-image FNV-1a digest. Thirty negative
controls cover missing, empty, oversized, malformed, path, FAT, marker, W^X,
cleanup, oracle-divergence, claim-overreach, and stale-binding failures.

The signed receipt is not produced in this cycle. The generated readiness file
remains an unsigned, single-host, non-promoting development record.

## Nonclaims

- No manifest-driven or authenticated selection.
- No retained kernel allocation or installed page tables.
- No PBP1 producer, final memory-map retry, or `ExitBootServices` call.
- No kernel entry, panic, recovery, or reset execution evidence.
- No target-firmware, physical-hardware, second-builder, signing, ISO, N5 exit,
  or production-readiness claim.

## Primary References

- UEFI 2.11, [Loaded Image Protocol](https://uefi.org/specs/UEFI/2.11/09_Protocols_EFI_Loaded_Image.html)
- UEFI 2.11, [Media Access Protocols](https://uefi.org/specs/UEFI/2.11/13_Protocols_Media_Access.html)
- UEFI 2.11, [Boot Services](https://uefi.org/specs/UEFI/2.11/07_Services_Boot_Services.html)
