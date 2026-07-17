# poole-bootload

`poole-bootload` is the allocation-independent `PKLOAD1` contract used by
PooleBoot to validate live UEFI file metadata, parse `PBC1`, plan and load a
`PKELF1` image, validate the resulting mapping plan, and account for cleanup.

The current development profile reads `\EFI\POOLEOS\BOOT.CFG` and the fixed,
untrusted `\EFI\POOLEOS\KERNEL.ELF` path. It does not authenticate a manifest,
activate page tables, call `ExitBootServices`, or transfer control.
