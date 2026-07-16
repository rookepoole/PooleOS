# Lab Kernel Transcript Export Receipt

Status: draft v0.2

The lab kernel transcript export receipt records whether `/usr/bin/pooleos-kernel-pgvm2-transcript-contract` was run, whether it was run disabled or enabled, where the transcript was exported, and whether `verify_kernel_pgvm2_loader_transcript.py` accepted the resulting `kernel_pgvm2_loader_output.json` without enforcement over-claiming. Format v0.2 also binds the exact verifier-output file, the transcript file digest consumed by that verifier, and the two guest environment digests supplied to the contract.

Emit the default pending receipt:

```powershell
python .\tools\emit_lab_kernel_transcript_export_receipt.py --out .\runs\lab_kernel_transcript_export_receipt.json
python .\tools\validate_artifact.py --schema .\specs\lab-kernel-transcript-export-receipt.schema.json .\runs\lab_kernel_transcript_export_receipt.json
```

After an operator or booted lab path runs the contract and regenerates `kernel_pgvm2_loader_output.json`, record the observed contract mode:

```powershell
python .\tools\emit_lab_kernel_transcript_export_receipt.py --contract-run-recorded --contract-mode disabled --out .\runs\lab_kernel_transcript_export_receipt.json
python .\tools\emit_lab_kernel_transcript_export_receipt.py --contract-run-recorded --contract-mode enabled --out .\runs\lab_kernel_transcript_export_receipt.json
```

A recorded run requires exactly one transcript audit line for each guest environment variable:

```text
POOLEOS_KERNEL_GUEST_ENV POOLEOS_POOLEGLYPH_SOURCE_ANCHOR_SHA256 <sha256>
POOLEOS_KERNEL_GUEST_ENV POOLEOS_POOLEGLYPH_PARSER_PROMOTION_RECEIPT_SHA256 <sha256>
```

Each value must be a 64-character SHA-256 digest and must match the corresponding digest expected by `kernel_pgvm2_loader_output.json`. The loader output's `transcript_source.sha256` must match the exported transcript, and the receipt's verifier-output hash must match the loader output supplied to the release gate. Missing, duplicate, malformed, substituted, or mismatched evidence produces `verification_failed` or a failed release-gate check.

## Statuses

- `pending_contract_run`: the receipt slot exists, but no lab contract execution is recorded. This is non-claiming and release-gate acceptable.
- `disabled_verified`: the contract run is recorded as disabled, the transcript and verifier artifacts are hash-bound, the exact guest digest pair is attested, the verifier accepted the output as blocked/non-claiming, and kernel promotion remains false.
- `enabled_verified`: the contract run is recorded as enabled, the transcript and verifier artifacts are hash-bound, the exact guest digest pair is attested, the verifier output is `pass`, every kernel check is satisfied, and kernel promotion is allowed.
- `verification_failed`: a contract run was recorded, but the transcript or verifier output was missing, incomplete, or over-claiming.
- `invalid`: the receipt source structure is malformed, such as a missing reviewed contract source or wrong loader output artifact kind.

## Boundary

This receipt does not run the lab script and does not boot a kernel. It records export continuity, guest-environment provenance, and verifier acceptance only. `kernel_enforcement_promotion_allowed=true` is reserved for `enabled_verified`; disabled and pending receipts must keep promotion false.
