# PKLOAD2 Live Manifest-Bound Kernel Load Proof

## Scope

Cycle 103 composes `N5-KLOAD-001` and `N5-MANIFEST-001` across N5.1, N5.4,
and N5.5. PooleBoot discovers the filesystem that contains its own loaded
image, opens and parses live PBC1, opens and parses its selected PSM1 manifest,
binds slot/version/path/file/image/SHA-256/entry fields, reads the real Cycle
101 PKELF1 PooleKernel product, verifies its digest, allocates firmware pages,
materializes segments/BSS/relative relocations, repeats the digest check,
validates the mapping plan, and releases every acquired resource.

This is a load-then-release proof. It is deliberately not a transfer proof.

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

## Cleanup

The success path closes the config, manifest, kernel, and root handles; frees
the config, manifest, and kernel pools; and frees all kernel pages. Cleanup is
attempted on every handled failure path, and cleanup failure is itself fatal.
Because pages are released, the kernel is not resident when PooleBoot returns.

## Qualification

Run:

```powershell
python tools/qualify_native_kernel_load.py
```

The qualifier performs strict Rust formatting and Clippy checks, 35 Rust host
tests across manifest/bootload/PooleBoot/PooleKernel, two exact 61,440-byte
PooleBoot builds, two clean PooleKernel builds, two exact four-file media
generations, and two fresh-vars QEMU/OVMF runs. Independent Python PBC1, PSM1,
PKELF1, and SHA-256 decisions must match nineteen live guest markers. Forty
negative controls cover file, FAT, path, config, manifest, digest, kernel,
marker, W^X, cleanup, oracle-divergence, overclaim, and stale-binding failures.

The signed receipt is not produced in this cycle. The generated readiness file
remains an unsigned, single-host, non-promoting development record.

## Nonclaims

- Manifest-driven digest equality is proved; signature-backed authentication is not.
- No completed digest-provider security review or persistent rollback state.
- No retained kernel allocation or installed page tables.
- No PBP1 producer, final memory-map retry, or `ExitBootServices` call.
- No kernel entry, panic, recovery, or reset execution evidence.
- No target-firmware, physical-hardware, second-builder, signing, ISO, N5 exit,
  or production-readiness claim.

## Primary References

- UEFI 2.11, [Loaded Image Protocol](https://uefi.org/specs/UEFI/2.11/09_Protocols_EFI_Loaded_Image.html)
- UEFI 2.11, [Media Access Protocols](https://uefi.org/specs/UEFI/2.11/13_Protocols_Media_Access.html)
- UEFI 2.11, [Boot Services](https://uefi.org/specs/UEFI/2.11/07_Services_Boot_Services.html)
