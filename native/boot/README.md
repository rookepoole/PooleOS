# Boot

PooleBoot, raw reviewed UEFI bindings, boot manifest verification, boot protocol generation, and firmware-handoff tests live here. No third-party production bootloader may be substituted.

The current `pooleboot` crate is an unsigned, non-promoting `x86_64-unknown-uefi` proof application. It validates bounded firmware-table structure, writes independent 16550 UART and QEMU debugcon diagnostics, exercises console and memory-map services, discovers GOP, and renders a deterministic static PooleOS identity before returning `EFI_SUCCESS`.

`PKLOAD2` now discovers the filesystem that loaded PooleBoot, opens and parses live PBC1 and its selected PSM1 manifest, binds slot/version/path/size/SHA-256/entry fields, reads and hashes the real PKELF1 PooleKernel product, materializes it in firmware pages, validates the W^X mapping plan, and releases all file, pool, and page resources. The unsigned manifest-driven selection remains development-only and untrusted.

This is not the complete PooleBoot loader. It proves digest equality but not signature-backed authentication, trusted rollback state, or digest-provider security review. It does not retain the kernel, install page tables, load system bundles, call `ExitBootServices`, populate live PBP1, transfer control, enforce Secure Boot, or satisfy the N5 exit gate. The separately qualified candidate PBP1 codec lives under `native/handoff`; the preserved empty compiler fixture lives under `native/fixtures/pooleboot`.
