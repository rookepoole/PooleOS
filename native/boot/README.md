# Boot

PooleBoot, raw reviewed UEFI bindings, boot manifest verification, boot protocol generation, and firmware-handoff tests live here. No third-party production bootloader may be substituted.

The current `pooleboot` crate is the first unsigned, non-promoting `x86_64-unknown-uefi` proof application. It validates bounded firmware-table structure, writes independent 16550 UART and QEMU debugcon diagnostics, exercises console and memory-map services, discovers GOP, and renders a deterministic static PooleOS identity before returning `EFI_SUCCESS`.

This is not the complete PooleBoot loader. It does not parse boot configuration, verify signatures, load PooleKernel or system bundles, call `ExitBootServices`, establish the boot handoff, enforce Secure Boot, or satisfy the N5 exit gate. The preserved empty compiler fixture lives under `native/fixtures/pooleboot`.
