# QEMU Shared Folder Contract

The QEMU shared-folder contract stages the trap-bearing PooleOS Lab inputs into the filenames expected by `pooleos-lab-smoke`.

Artifact kind: `pooleos.qemu_shared_folder_contract`

Host staging writes:

- `input.pgb2.json`
- `input.replay.json`
- `pooleos_boot_trap_bundle_manifest.json`
- `pgb2_trap_abi_boundary_receipt.json` when a draft ABI boundary receipt is supplied

The contract records source and staged hashes, the expected guest paths, draft ABI boundary flags when supplied, and the QEMU `-virtfs` argument using mount tag `pooleos_output`.

Release-gate boundary: a three-file shared-folder contract is still valid for base bootstrap evidence, but once `pooleos_release_gate.py` is invoked with `--pgb2-trap-abi-boundary-receipt`, the same release gate also requires the shared-folder contract to stage `pgb2_trap_abi_boundary_receipt.json`.

Emit it with:

```powershell
python .\tools\pooleos_qemu_prepare_inputs.py --shared-dir .\runs\qemu_shared --bundle .\runs\signed_trap_evidence.pgb2.json --replay-proof .\runs\signed_trap_evidence.replay.json --boot-trap-bundle-manifest .\runs\pooleos_boot_trap_bundle_manifest.json --pgb2-trap-abi-boundary-receipt .\runs\pgb2_trap_abi_boundary_receipt.json --out .\runs\qemu_shared_folder_contract.json
```

The launcher can run this staging step without booting:

```powershell
.\lab-os\qemu\scripts\run-pooleos-lab.ps1 -PrepareInputsOnly -SharedOutputPath .\runs\qemu_shared -TrapBundlePath .\runs\signed_trap_evidence.pgb2.json -ReplayProofPath .\runs\signed_trap_evidence.replay.json -BootTrapBundleManifestPath .\runs\pooleos_boot_trap_bundle_manifest.json -Pgb2TrapAbiBoundaryReceiptPath .\runs\pgb2_trap_abi_boundary_receipt.json
```

This is host-side launch preparation only. Guest mount success and trap input verification still require real QEMU boot evidence. The ABI receipt is a non-promoting draft boundary receipt; staging it lets the guest verifier emit `POOLEOS_LAB_TRAP_ABI_BOUNDARY_PASS`, but it still does not freeze a kernel ABI.
