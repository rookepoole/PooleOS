# PGB2 Trap ABI Boundary Receipt

The PGB2 trap ABI boundary receipt verifies that the current trap byte chain is coherent while keeping it non-promoting.

It consumes:

- `pgb2_trap_encoding.json`
- `pgb2_trap_execution.json`
- `signed_trap_evidence.pgb2.json`
- `pooleos_boot_trap_bundle_manifest.json`
- `qemu_shared_folder_contract.json`

Current status is expected to be `draft_verified`. That means the draft trap bytes, simulator execution, bundle sections, boot manifest, and QEMU shared-folder staging agree. It does not mean the byte format is frozen, kernel-owned, or safe to call a PooleOS kernel ABI.

When this receipt is staged into the QEMU shared folder as `pgb2_trap_abi_boundary_receipt.json`, the guest verifier can include it in `boot_trap_bundle_verification.json` and emit `POOLEOS_LAB_TRAP_ABI_BOUNDARY_PASS`. That marker proves only that the guest observed the same non-promoting draft receipt; it is not a kernel-enforcement claim.

The release gate treats the receipt and shared-folder contract as a pair: if `--pgb2-trap-abi-boundary-receipt` is supplied, `qemu_shared_folder_contract.json` must also include a staged file with role `pgb2_trap_abi_boundary_receipt`.

The release gate accepts this receipt only when:

- `abi_frozen=false`
- `kernel_abi_promotion_allowed=false`
- `kernel_enforcement_claimed=false`
- `security_boundary_claimed=false`
- all source artifacts have 0 failed checks
- no source artifact claims ABI freeze, kernel ABI promotion, kernel enforcement, or a security boundary

Emit and validate:

```powershell
python .\tools\emit_pgb2_trap_abi_boundary_receipt.py --trap-encoding .\runs\pgb2_trap_encoding.json --trap-execution .\runs\pgb2_trap_execution.json --bundle .\runs\signed_trap_evidence.pgb2.json --boot-trap-bundle-manifest .\runs\pooleos_boot_trap_bundle_manifest.json --qemu-shared-folder-contract .\runs\qemu_shared_folder_contract.json --out .\runs\pgb2_trap_abi_boundary_receipt.json
python .\tools\validate_artifact.py --schema .\specs\pgb2-trap-abi-boundary-receipt.schema.json .\runs\pgb2_trap_abi_boundary_receipt.json
```
