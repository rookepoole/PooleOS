# Boot Trap Bundle Manifest

The boot trap bundle manifest prepares a trap-bearing PGB2 bundle for the PooleOS Lab image.

Artifact kind: `pooleos.boot_trap_bundle_manifest`

The manifest binds host artifacts to the lab loader paths:

- bundle source -> `/mnt/pooleos-output/input.pgb2.json`;
- replay proof source -> `/mnt/pooleos-output/input.replay.json`;
- manifest source -> `/mnt/pooleos-output/pooleos_boot_trap_bundle_manifest.json`;
- verification result -> `/var/lib/pooleos/runs/boot_trap_bundle_verification.json`.

It records bundle and replay file hashes, confirms the bundle contains `TRAP_ENCODING` and `TRAP_EXECUTION` sections, and stores the expected trap execution summary. The lab verifier checks mounted files against those expectations before `pooleos-lab-smoke` runs the normal release gate.

Emit it with:

```powershell
python .\tools\emit_boot_trap_bundle_manifest.py --bundle .\runs\signed_trap_evidence.pgb2.json --replay-proof .\runs\signed_trap_evidence.replay.json --trap-execution .\runs\pgb2_trap_execution.json --out .\runs\pooleos_boot_trap_bundle_manifest.json
```

For a QEMU shared folder, copy these files using the manifest target names:

```text
input.pgb2.json
input.replay.json
pooleos_boot_trap_bundle_manifest.json
```

This is pre-boot readiness evidence. It does not claim that the PooleOS Lab image has booted or enforced traps in a kernel substrate.

After a real captured boot, the guest should export `boot_trap_bundle_verification.json`. Feed that output into `tools/emit_kernel_boot_handoff.py` with captured readiness and the marker contract, then emit `tools/emit_kernel_pgvm2_loader_output.py` and `tools/emit_kernel_pgvm2_loader_evidence.py` to reserve the output slot and record the kernel-owned PGVM2 loader checks.
