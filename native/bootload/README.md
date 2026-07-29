# poole-bootload

`poole-bootload` is the allocation-independent `PKLOAD2` contract used by
PooleBoot to validate live UEFI file metadata, parse `PBC1` and `PSM1`, bind
the selected kernel's slot/version/path/size/SHA-256/entry fields, plan and load
a `PKELF1` image, validate the resulting mapping plan, and account for cleanup.

The current development profile reads `\EFI\POOLEOS\BOOT.CFG`, its selected
`\EFI\POOLEOS\SYSTEM_A.PBM`, and the manifest-selected kernel path. It checks
SHA-256 equality but does not authenticate the unsigned manifest, activate page
tables, call `ExitBootServices`, or transfer control.
