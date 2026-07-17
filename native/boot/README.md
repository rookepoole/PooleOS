# Boot

PooleBoot, raw reviewed UEFI bindings, boot manifest verification, boot protocol generation, and firmware-handoff tests live here. No third-party production bootloader may be substituted.

The current `pooleboot` crate is an unsigned, non-promoting `x86_64-unknown-uefi` proof application. It validates bounded firmware-table structure, writes independent 16550 UART and QEMU debugcon diagnostics, exercises console and memory-map services, discovers GOP, and renders a deterministic static PooleOS identity before returning `EFI_SUCCESS`.

`PKLOAD3` discovers the filesystem that loaded PooleBoot, opens and parses live PBC1 and its selected PSM1 manifest, binds slot/version/path/size/SHA-256/entry fields, reads and hashes the real PKELF1 PooleKernel product, materializes it in firmware pages, validates the W^X mapping plan, and keeps it live while PBLIVE1 produces an exact pre-exit PBP1 snapshot. Serial/debugcon transcripts are independently reconstructed and cross-bound before all file, PBP1 pool, and kernel-page resources are released. The unsigned manifest-driven selection remains development-only and untrusted.

This is not the complete PooleBoot loader. It proves digest equality and a temporary live PBP1 producer, but not signature-backed authentication, trusted rollback state, or digest-provider security review. It does not retain the kernel or PBP1, install page tables, load system bundles, call `ExitBootServices`, transfer control, enforce Secure Boot, or satisfy the N5 exit gate. The canonical PBP1 codec lives under `native/handoff`; the pure live producer lives under `native/livehandoff`; the preserved empty compiler fixture lives under `native/fixtures/pooleboot`.
