# PooleOS

PooleOS is a source-available, commercial-rights-reserved native operating system owned and directed by Rooke Poole. It is being built as an original `PooleBoot.efi` UEFI loader, an original capability-based PooleKernel microkernel, isolated native system and driver services, PooleGlyph/PGB2/PGVM2 execution, canonical Poole Defect Calculus services, and an accessible PooleGlass desktop.

PooleGlyph IP is owned by Rooke Poole. PooleOS follows the same source-available path unless the owner later adopts a different licensing structure.

## Native Architecture Contract

Linux, Debian, Buildroot, GRUB, Limine, and systemd are not production foundations or release-media dependencies. QEMU, OVMF, EDK II, Windows, WSL, Linux, and Buildroot may be used only as development tools, references, compatibility environments, or historical evidence.

The production chain is:

```text
x86-64 UEFI firmware
-> signed PooleBoot.efi
-> verified PooleKernel plus initial-system and recovery bundles
-> PooleKernel capability microkernel
-> isolated native servers and user-space driver domains
-> native application, PooleGlyph/PGB2/PGVM2, and PDC services
-> PooleGlass compositor and desktop
-> reproducible signed PooleOS ISO
```

The ring-0 boundary is defined in `specs/pooleos-kernel-charter.md`. General device drivers, filesystems, networking, graphics, audio, PGVM2, PDC, package management, authentication policy, and desktop behavior stay outside the kernel TCB. Production loadable kernel modules are prohibited in v1.

## Authoritative Plan

- `docs/production-goal-charter.md`: completion contract and per-turn next-best-move protocol.
- `docs/pdc-production-build-plan.md`: comprehensive native build plan with 40 phases and 287 explicit subphases.
- `runs/pdc_production_roadmap.json`: schema-validated machine roadmap, dependencies, status, evidence, gaps, and flags.
- `runs/pooleos_native_checklist_coverage.json`: exact line and section mapping from the locked master checklist to N0-N39.
- `docs/adr/`: seven-record native architecture constitution and required ADR template.
- `runs/native_architecture_baseline.json`: deterministic byte binding for the ADRs, constitution, plan, policy, checklist, license, and repository identity.
- `specs/native-v1-objectives.json`, `docs/native-v1-objectives.md`, and `runs/native_v1_objectives_readiness.json`: 38 measurable candidate v1 targets, owner-ratification boundary, deterministic readiness, and ten fail-closed controls.
- `specs/adr-ratification-policy.json`, `docs/adr-ratification-ceremony.md`, and `runs/adr_ratification_readiness.json`: secret-free owner-signing contract, exact action boundary, and deterministic pending ledger.
- `specs/native-toolchain-lock.json`, `specs/native-target-contract.json`, and `runs/native_toolchain_qualification.json`: exact Rust inputs, freestanding target contracts, and bounded one-host PE32+/ELF64 evidence.
- `docs/native-toolchain-qualification.md`: reproduction procedure, exact fixture hashes, discovered PE nondeterminism, and open gates.
- `specs/hardware-support-policy.json`, `specs/tier1-hardware-target.json`, and `specs/native-standards-register.json`: hardware support tiers, exact Tier 1 identity, evidence/safety gates, and primary-source standards metadata.
- `runs/tier1_hardware_observation.json`, `runs/hardware_target_readiness.json`, and `docs/hardware-target-and-lab-safety.md`: sanitized host observation, deterministic N2 readiness ledger, privacy boundary, and safe capture procedure.
- `specs/native-release-architecture-policy.json`: extracted-release conformance policy with executable negative tests.
- `docs/publication-boundary.md`: public source-available and private evidence-vault boundary.
- `specs/pdc-production-roadmap.schema.json`: roadmap validation contract.
- `specs/pooleos-native-checklist-coverage.schema.json`: checklist-coverage validation contract.

The locked source checklist has SHA-256 `A8C94719FAF9428C1F133010BA2603C0270C4E1EFD7327AF8EAB9C8C362ABB3D`, 10,512 lines, 171 numbered sections, 8,998 checkbox lines, and 8,996 implementation items after its two generated-metadata checkboxes are excluded. Every source line and requirement is mapped; mapping does not imply completion.

Current Cycle 85 status: 40 phases, 0 complete, 12 partial, 1 blocked, and 27 not started. The public repository, protected workflow, bounded one-host toolchain fixtures, canonical ADR ceremony, candidate v1 objectives, exact Tier 1 target, read-only hardware collector, sanitized observation, and fail-closed readiness ledgers exist. The objectives contract defines 38 measurable targets and passes ten negative controls, but Rooke Poole has not accepted the profile or values and every target remains unmeasured. The hardware target matches 24/24 required identity checks with zero privacy violations, but N2 still has seven evidence channels, 15 standards hashes, and ten lab-safety prerequisites open. The public ADR trust store intentionally has zero keys; no ADR is cryptographically signed; ADR-0003 and ADR-0004 remain proposed; and `N0-RATIFY-001` awaits owner target acceptance or amendment, ADR disposition, and custody choice. Native PooleBoot, PooleKernel, ring-3 execution, capability enforcement, native drivers, PooleFS, PooleGlass, and the production ISO do not exist.

## Validation

```powershell
python .\tools\generate_native_checklist_coverage.py
python .\tools\generate_native_production_roadmap.py
python .\tools\generate_native_architecture_baseline.py
python .\tools\generate_native_v1_objectives_readiness.py
python .\tools\verify_native_v1_objectives.py
python .\tools\generate_adr_ratification_readiness.py
python .\tools\sanitize_tier1_hardware_capture.py --capture .\runs\tier1_hardware_capture.private.json --out .\runs\tier1_hardware_observation.json
python .\tools\generate_hardware_target_readiness.py
python .\tools\verify_hardware_target.py
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\tools\bootstrap_native_toolchain.ps1
python .\tools\qualify_native_toolchain.py
python -m unittest discover -s tests
python .\tools\check_publication_boundary.py
python .\tools\pooleos_doctor.py --pooleglyph <POOLEGYPH_REPO>
```

The generators are deterministic: tests reproduce the checklist, roadmap, architecture baseline, objectives-readiness, ADR-readiness, native-toolchain, and hardware-readiness ledgers byte for byte. Cycle 85 passes 427 tests with one Windows symlink-permission skip, and the non-promoting consistency release gate passes 65/65 checks over 60 artifacts with 20 explicit gaps. Doctor verifies the locked checklist hash, coverage digest, N0-N39 sequence, ADR/source hashes, candidate objectives and owner boundary, ratification boundary, repository identity, native toolchain/target contracts, hardware target/readiness/privacy boundaries, public index boundary, PooleGlyph bridge, PDC evidence, and retained historical consistency artifacts.

The public repository currently carries source, specifications, tests, and eight allowlisted deterministic ledgers. The public hardware observation is rebuilt from a fixed whitelist and binds only the byte count and SHA-256 of its ignored private capture; raw firmware-table bytes, serials, MAC addresses, UUIDs, host/user names, absolute local paths, full PnP instances, and TPM key material are not published. Public ratification manifest, detached signature, and receipt paths are reserved but remain absent until owner action. Raw internal PDC inputs, private benchmark evidence, other local run artifacts, historical lab images, firmware without redistribution clearance, secrets, and private signing material remain in the ignored private evidence vault. Full private-evidence reproduction therefore requires an owner-authorized local vault in addition to the public checkout.

## Current PDC Evidence

The Cycle 74-79 PDC chain is valid reference evidence and is carried into N32-N33. It does not prove native-kernel or production-backend execution.

## PDC Math Reference

Cycle 74 adds the first source-bound executable PDC contract:

- `runs/pdc_source_intake.json`: seven verified content-addressed authorities plus a nonpromoting raw-candidate index.
- `specs/pdc-math-contract-v0.1.md` and `runs/pdc_math_contract.json`: axes, flattening, periodic boundaries, matrices, channels, numerical bounds, hashes, variants, and claim boundaries.
- `runtime/pdc_reference.py`: independent scalar-stencil and dense Kronecker-matrix oracles.
- `runs/pdc_golden_vectors.json`: binary, wraparound, planar, rectangle, line, PMphi, cuboid, and shell vectors.

Regenerate and validate the chain:

```powershell
python .\tools\emit_pdc_source_intake.py --out .\runs\pdc_source_intake.json
python .\tools\emit_pdc_math_contract.py --source-intake .\runs\pdc_source_intake.json --out .\runs\pdc_math_contract.json
python .\tools\emit_pdc_golden_vectors.py --math-contract .\runs\pdc_math_contract.json --out .\runs\pdc_golden_vectors.json
python .\tools\validate_artifact.py --schema .\specs\pdc-golden-vectors.schema.json .\runs\pdc_golden_vectors.json
```

The dense matrices are bounded specification oracles, not production routes. The raw package index is inventory, not imported or reproduced benchmark evidence.

## PDC Exact Verifier Reproduction

Cycle 75 imports four canonical verifier sources into `sources/pdc/verifiers/sha256/`, verifies 46/46 embedded manifest entries, and preserves six source-run CSVs under `runs/pdc_verifier_source_outputs/`. `runtime/pdc_verifier_reproduction.py` independently checks the declared 841 rectangle, 80 line-hole, 720 arbitrary-mask, 1,225 inversion, 729 cuboid, and 729 shell cases against `PDC-MATH-0.1`; all 4,324 cases pass with zero semantic mismatch.

```powershell
python .\tools\emit_pdc_verifier_intake.py --out .\runs\pdc_verifier_intake.json
python .\tools\emit_pdc_verifier_reproduction.py --verifier-intake .\runs\pdc_verifier_intake.json --math-contract .\runs\pdc_math_contract.json --out .\runs\pdc_verifier_reproduction.json
python .\tools\validate_artifact.py --schema .\specs\pdc-verifier-intake.schema.json .\runs\pdc_verifier_intake.json
python .\tools\validate_artifact.py --schema .\specs\pdc-verifier-reproduction.schema.json .\runs\pdc_verifier_reproduction.json
```

The source runners emitted CRLF CSVs on Windows while the published files use LF. Typed rows and canonical LF hashes match for all six outputs; raw byte equality is intentionally not claimed. These are exact finite-domain verifier results, not all-size theorems or production backend evidence.

## PDC Representation ABI

Cycle 76 freezes `PDC-REP-0.1` over dense binary, sorted sparse binary, LSB-first bit-packed binary, finite IEEE-754 probability fields, and checked native-buffer snapshots. Ten directed conversion paths bind shape, axes, dtype, byte/bit order, offset, padded strides, ownership provenance, mutability provenance, checked `u64` span arithmetic, and representation-specific storage hashes without changing `PDC-MATH-0.1` semantics.

```powershell
python .\tools\emit_pdc_representation_contract.py --out .\runs\pdc_representation_contract.json
python .\tools\emit_pdc_representation_receipt.py --representation-contract .\runs\pdc_representation_contract.json --out .\runs\pdc_representation_receipt.json
python .\tools\validate_artifact.py --schema .\specs\pdc-representation-contract.schema.json .\runs\pdc_representation_contract.json
python .\tools\validate_artifact.py --schema .\specs\pdc-representation-receipt.schema.json .\runs\pdc_representation_receipt.json
```

The receipt tests 10 lattice-bearing golden cases and all 3,099 representation-applicable exact fields through four round trips each, repeats the applicable PDC result, and passes 13 fail-closed malformed-input checks. Three golden formula records and 1,225 inversion formula rows have no lattice payload; they remain explicitly excluded and digest-bound rather than being described as converted fields. Native storage is snapshotted reference evidence: actual C pointers, mutable outputs, device buffers, and kernel validation remain later gates.

## PDC Boundary and Metamorphic Corpus

Cycle 77 adds `PDC-GOLDEN-0.2` without replacing the original Cycle 74 vectors. It publishes all 54 binary state/support pairs, eight empty/full/singleton/wrap/padding fixtures, 32 periodic translations, 40 joint axis/shape permutations, and six explicit non-relations. The receipt executes 206 direct/scalar/matrix field evaluations and 824 representation round trips with zero mismatch.

```powershell
python .\tools\emit_pdc_golden_metamorphic_corpus.py --out .\runs\pdc_golden_metamorphic_corpus.json
python .\tools\emit_pdc_golden_metamorphic_receipt.py --corpus .\runs\pdc_golden_metamorphic_corpus.json --out .\runs\pdc_golden_metamorphic_receipt.json
python .\tools\validate_artifact.py --schema .\specs\pdc-golden-metamorphic-corpus.schema.json .\runs\pdc_golden_metamorphic_corpus.json
python .\tools\validate_artifact.py --schema .\specs\pdc-golden-metamorphic-receipt.schema.json .\runs\pdc_golden_metamorphic_receipt.json
```

Complement, shape reinterpretation, PMphi-as-storage, nonperiodic translation, 2D-as-A26, and fractional-probability-as-binary are explicitly rejected or excluded. This closes the supported periodic P1 reference gate; it does not qualify native C, optimized routes, kernels, UI, or boot media.

## PDC Q/P Probability and Typed Channels

Cycle 78 freezes `PDC-QP-0.1`. Distinct tagged APIs prevent feature vectors, probability values, typed gate/cardinality readouts, geometry spectra, and collapsed one-bit state from being interchanged. The receipt checks fixed-order dynamic programming against independent polynomial and bounded brute-force oracles, verifies center and neighbor derivatives, and recomputes all 42 imported gate, identity/not, half-adder, full-adder, and cardinality cases instead of trusting embedded pass markers.

```powershell
python .\tools\emit_pdc_qp_contract.py --out .\runs\pdc_qp_contract.json
python .\tools\emit_pdc_qp_receipt.py --contract .\runs\pdc_qp_contract.json --out .\runs\pdc_qp_receipt.json
python .\tools\validate_artifact.py --schema .\specs\pdc-qp-contract.schema.json .\runs\pdc_qp_contract.json
python .\tools\validate_artifact.py --schema .\specs\pdc-qp-receipt.schema.json .\runs\pdc_qp_receipt.json
```

All 54 feature thresholds, 10 full probability cases, 12 brute-force cases, 270 DP/polynomial checks, 260 derivative-oracle checks, 104 finite-difference checks, 42 typed cases, and 16 negative checks pass with zero mismatch. The v5.5 field benchmark, perturbation stability, and PooleGlyph/PGB2 typed exposure remain open; this is classical measured-field evidence, not quantum-state reconstruction.

## Native Kernel Principle

Native implementation proceeds from a frozen architecture and executable models into the smallest bootable TCB, then moves policy and drivers into capability-confined user space:

```text
signed architecture ADRs and clean-room boundary
-> hermetic x86-64 UEFI toolchain and QEMU/OVMF profile
-> PooleBoot and frozen boot protocol
-> PooleKernel entry, memory, interrupts, SMP, and diagnostics
-> ring 3, syscalls, IPC, capabilities, and IOMMU confinement
-> isolated VIRTIO reference drivers and native system services
-> PooleGlyph/PGB2/PGVM2 and PDC services
-> PooleGlass, installer, recovery, signed reproducible ISO
```

## Historical Cycle 1-79 Artifacts

The remaining lab commands and artifacts below preserve the Cycle 1-79 PGB2, PDC, Buildroot/QEMU, and capability-simulator evidence. They are useful regression and provenance inputs but are **non-promoting** for native PooleOS. A Buildroot image, Linux rootfs, fixture boot marker, or simulated capability proof cannot satisfy any PooleBoot or PooleKernel release gate.

- `specs/pooleos-kernel-charter.md`: kernel-level invariants and production-readiness gates.
- `specs/claim-lanes.schema.json`: machine-readable claim-lane record shape.
- `specs/channel-trace.schema.json`: JSON artifact shape for typed channel telemetry.
- `specs/pgb2-bundle.schema.json`: sectioned JSON bundle for PGB1-compatible code plus PooleOS trace/provenance sections.
- `specs/signed-membrane.schema.json`: benchmark-lane signed membrane metric artifact.
- `specs/replay-proof.schema.json`: deterministic replay proof record for a bundle and declared reference case.
- `specs/isolation-proof.schema.json`: static microkernel region/capability proof artifact.
- `specs/boot-trap-bundle-manifest.schema.json`: lab boot-readiness manifest for trap-bearing PGB2 bundle inputs.
- `specs/qemu-shared-folder-contract.schema.json`: host-side QEMU shared-folder staging contract.
- `specs/lab-guest-autostart.schema.json`: guest init-time mount and smoke autostart evidence.
- `specs/qemu-boot-evidence.schema.json`: QEMU serial boot evidence with fixture versus captured-source provenance.
- `specs/qemu-captured-boot-preflight.schema.json`: non-mutating preflight for real captured QEMU boot launches.
- `specs/qemu-captured-boot-launch-bundle.schema.json`: operator-facing command bundle for a real captured QEMU boot.
- `specs/qemu-captured-boot-dry-run-checklist.schema.json`: operator dry-run checklist and receipt template for captured QEMU boot handoff.
- `specs/qemu-boot-marker-contract.schema.json`: marker-to-emitter responsibility contract for the QEMU trap-input boot path.
- `specs/qemu-boot-marker-image-binding.schema.json`: hashes marker emitters and Buildroot scaffold files for the QEMU trap-input boot path.
- `specs/rootfs-content-manifest.schema.json`: compares bound marker/support files against a built and extracted rootfs tree.
- `specs/rootfs-extraction-handoff.schema.json`: operator-reviewed WSL/Linux read-only rootfs extraction command plan.
- `specs/rootfs-extraction-receipt.schema.json`: operator receipt that gates captured-QEMU promotion on verified rootfs continuity.
- `specs/qemu-captured-boot-receipt.schema.json`: receipt that keeps fixture and captured QEMU boot evidence in separate handoff slots.
- `specs/qemu-captured-boot-readiness.schema.json`: reconciles verified rootfs, captured boot receipt, and captured evidence before promotion language.
- `specs/buildroot-build.schema.json`: WSL-gated Buildroot image build report that binds the planned rootfs image path before captured-boot promotion.
- `specs/kernel-boot-handoff.schema.json`: ties captured readiness to guest loader output without claiming kernel/PGVM2 enforcement.
- `specs/kernel-pgvm2-loader-output.schema.json`: defines the booted kernel loader output slot and current non-claiming negative fixture.
- `specs/lab-kernel-transcript-export-receipt.schema.json`: records whether the lab transcript contract ran and whether the exported transcript was accepted without over-claiming.
- `specs/kernel-pgvm2-loader-evidence.schema.json`: records the kernel-owned PGVM2 loader checks and parser-promotion receipt gate without claiming enforcement before booted output exists.
- `tools/verify_kernel_pgvm2_loader_transcript.py`: converts a complete booted-kernel transcript into `kernel_pgvm2_loader_output.json`.
- `lab-os/buildroot/.../pooleos-kernel-pgvm2-transcript-contract`: disabled lab-side transcript emitter contract for future kernel loader output.
- `specs/capability-trap-proof.schema.json`: PGB2-style region/capability trap proof artifact.
- `specs/capability-trap-fuzz.schema.json`: deterministic closed-by-default trap fuzz evidence.
- `specs/pgb2-trap-encoding.schema.json`: draft byte encoding evidence for capability trap operations.
- `specs/pgb2-trap-execution.schema.json`: byte-level simulator evidence for draft PGB2 trap programs.
- `specs/pgb2-trap-abi-boundary-receipt.schema.json`: release-gated receipt that keeps draft trap bytes separate from a frozen kernel ABI.
- `specs/pooleglyph-source-anchor.schema.json`: live PooleGlyph source/checkpoint anchor artifact.
- `specs/pooleglyph-bridge-manifest.schema.json`: PooleGlyph v0.5-dev metadata bridge surface for PooleOS artifact lanes.
- `specs/pooleglyph-core-ir-boundary-receipt.schema.json`: distinguishes metadata-only PooleGlyph declarations from public Core IR executable candidates before parser-to-kernel promotion.
- `specs/pooleglyph-core-ir-executable-audit.schema.json`: audits executable Core IR candidates separately from metadata-only zero-program outputs before permission/trap promotion.
- `specs/pooleglyph-parser-kernel-promotion-receipt.schema.json`: release-gated parser-to-kernel receipt that remains blocked until Phase 66 evidence permits handoff.
- `docs/pooleglyph-checkpoint-deep-inspection.md`: refreshed Phase 65 PooleGlyph checkpoint inspection and PooleOS integration boundary.
- `specs/permission-capability-matrix.schema.json`: PooleGlyph-derived permission/capability/resource matrix for trap-proof inputs.
- `specs/pgb2-draft.md`: draft PGB2/PGVM2 kernel contract.
- `tools/pooleos_doctor.py`: verification entry point for the scaffold and PooleGlyph baseline.

Emit a reference channel trace:

```powershell
python .\tools\emit_channel_trace.py --case rectangle-2x2 --out .\runs\rectangle_trace.json
```

Emit and validate a draft PGB2 bundle:

```powershell
python .\tools\emit_pgb2_bundle.py --case six-support --out .\runs\six_support.pgb2.json
python .\tools\validate_pgb2_bundle.py .\runs\six_support.pgb2.json
```

Attach signed membrane smoke metrics to a bundle:

```powershell
python .\tools\emit_pgb2_bundle.py --case six-support --include-signed-metrics --out .\runs\signed_smoke.pgb2.json
```

Attach trap encoding and execution evidence to a bundle:

```powershell
python .\tools\emit_pgb2_bundle.py --case six-support --include-signed-metrics --trap-encoding .\runs\pgb2_trap_encoding.json --trap-execution .\runs\pgb2_trap_execution.json --out .\runs\signed_trap_evidence.pgb2.json
python .\tools\validate_pgb2_bundle.py .\runs\signed_trap_evidence.pgb2.json
```

Emit a replay proof:

```powershell
python .\tools\emit_replay_proof.py --bundle .\runs\six_support.pgb2.json --case six-support --out .\runs\six_support.replay.json
```

Emit a Lab boot trap-bundle manifest:

```powershell
python .\tools\emit_boot_trap_bundle_manifest.py --bundle .\runs\signed_trap_evidence.pgb2.json --replay-proof .\runs\signed_trap_evidence.replay.json --trap-execution .\runs\pgb2_trap_execution.json --out .\runs\pooleos_boot_trap_bundle_manifest.json
```

Stage QEMU shared-folder inputs for the Lab image:

```powershell
python .\tools\pooleos_qemu_prepare_inputs.py --shared-dir .\runs\qemu_shared --bundle .\runs\signed_trap_evidence.pgb2.json --replay-proof .\runs\signed_trap_evidence.replay.json --boot-trap-bundle-manifest .\runs\pooleos_boot_trap_bundle_manifest.json --pgb2-trap-abi-boundary-receipt .\runs\pgb2_trap_abi_boundary_receipt.json --out .\runs\qemu_shared_folder_contract.json
.\lab-os\qemu\scripts\run-pooleos-lab.ps1 -PrepareInputsOnly -SharedOutputPath .\runs\qemu_shared -TrapBundlePath .\runs\signed_trap_evidence.pgb2.json -ReplayProofPath .\runs\signed_trap_evidence.replay.json -BootTrapBundleManifestPath .\runs\pooleos_boot_trap_bundle_manifest.json -Pgb2TrapAbiBoundaryReceiptPath .\runs\pgb2_trap_abi_boundary_receipt.json
```

The ABI receipt flag is optional during the first bootstrap staging pass, then required for the guest to emit `POOLEOS_LAB_TRAP_ABI_BOUNDARY_PASS`. When `pooleos_release_gate.py` is invoked with `--pgb2-trap-abi-boundary-receipt`, the QEMU shared-folder contract must also stage `pgb2_trap_abi_boundary_receipt.json`.

Emit Lab guest autostart evidence:

```powershell
python .\tools\emit_lab_guest_autostart.py --qemu-shared-folder-contract .\runs\qemu_shared_folder_contract.json --out .\runs\lab_guest_autostart.json
```

Emit QEMU boot evidence from the trap-input fixture, or from a captured serial log after boot:

```powershell
python .\tools\emit_qemu_boot_evidence.py --source fixture --out .\runs\qemu_boot_evidence.json
python .\tools\emit_qemu_boot_evidence.py --log .\runs\pooleos-lab-serial.log --source captured_qemu_serial --out .\runs\qemu_boot_evidence.captured.json
```

The Lab QEMU launcher emits captured evidence automatically after a real boot unless `-SkipBootEvidence` is passed:

```powershell
python .\tools\emit_qemu_captured_boot_preflight.py --image .\output\images\rootfs.ext4 --shared-output .\runs\qemu_shared --serial-log .\runs\pooleos-lab-serial.log --boot-validation-output .\runs\boot_log_validation.captured.json --qemu-boot-evidence-output .\runs\qemu_boot_evidence.captured.json --qemu-captured-boot-receipt-output .\runs\qemu_captured_boot_receipt.json --out .\runs\qemu_captured_boot_preflight.json
python .\tools\emit_qemu_captured_boot_receipt.py --fixture-evidence .\runs\qemu_boot_evidence.json --captured-evidence .\runs\qemu_boot_evidence.captured.json --out .\runs\qemu_captured_boot_receipt.json
python .\tools\emit_qemu_captured_boot_launch_bundle.py --preflight .\runs\qemu_captured_boot_preflight.json --qemu-shared-folder-contract .\runs\qemu_shared_folder_contract.json --qemu-captured-boot-receipt .\runs\qemu_captured_boot_receipt.json --fixture-evidence .\runs\qemu_boot_evidence.json --release-gate-output .\runs\release_gate.json --out .\runs\qemu_captured_boot_launch_bundle.json
python .\tools\emit_qemu_captured_boot_dry_run_checklist.py --launch-bundle .\runs\qemu_captured_boot_launch_bundle.json --release-gate-output .\runs\release_gate.json --out .\runs\qemu_captured_boot_dry_run_checklist.json
python .\tools\emit_qemu_boot_marker_contract.py --dry-run-checklist .\runs\qemu_captured_boot_dry_run_checklist.json --lab-guest-autostart .\runs\lab_guest_autostart.json --out .\runs\qemu_boot_marker_contract.json
python .\tools\emit_qemu_boot_marker_image_binding.py --marker-contract .\runs\qemu_boot_marker_contract.json --lab-image-manifest .\runs\lab_image_manifest.json --out .\runs\qemu_boot_marker_image_binding.json
python .\tools\emit_rootfs_content_manifest.py --image-binding .\runs\qemu_boot_marker_image_binding.json --image .\output\images\rootfs.ext4 --extracted-rootfs .\runs\rootfs_extracted --out .\runs\rootfs_content_manifest.json
python .\tools\emit_rootfs_extraction_handoff.py --rootfs-content-manifest .\runs\rootfs_content_manifest.json --note-out .\runs\rootfs_extraction_handoff.md --out .\runs\rootfs_extraction_handoff.json
python .\tools\emit_rootfs_extraction_receipt.py --handoff .\runs\rootfs_extraction_handoff.json --rootfs-content-manifest .\runs\rootfs_content_manifest.json --out .\runs\rootfs_extraction_receipt.json
.\lab-os\qemu\scripts\run-pooleos-lab.ps1 -ImagePath .\output\images\rootfs.ext4 -SharedOutputPath .\runs\qemu_shared -TrapBundlePath .\runs\signed_trap_evidence.pgb2.json -ReplayProofPath .\runs\signed_trap_evidence.replay.json -BootTrapBundleManifestPath .\runs\pooleos_boot_trap_bundle_manifest.json -Pgb2TrapAbiBoundaryReceiptPath .\runs\pgb2_trap_abi_boundary_receipt.json -SerialLog .\runs\pooleos-lab-serial.log -BootValidationOutput .\runs\boot_log_validation.captured.json -QemuBootEvidenceOutput .\runs\qemu_boot_evidence.captured.json
python .\tools\emit_qemu_captured_boot_receipt.py --fixture-evidence .\runs\qemu_boot_evidence.json --captured-evidence .\runs\qemu_boot_evidence.captured.json --operator-executed --out .\runs\qemu_captured_boot_receipt.json
python .\tools\emit_qemu_captured_boot_readiness.py --rootfs-extraction-receipt .\runs\rootfs_extraction_receipt.json --qemu-captured-boot-receipt .\runs\qemu_captured_boot_receipt.json --qemu-captured-boot-evidence .\runs\qemu_boot_evidence.captured.json --out .\runs\qemu_captured_boot_readiness.json
python .\tools\emit_kernel_boot_handoff.py --qemu-captured-boot-readiness .\runs\qemu_captured_boot_readiness.json --qemu-boot-marker-contract .\runs\qemu_boot_marker_contract.json --boot-trap-bundle-manifest .\runs\pooleos_boot_trap_bundle_manifest.json --guest-loader-verification .\runs\boot_trap_bundle_verification.json --out .\runs\kernel_boot_handoff.json
python .\tools\emit_kernel_pgvm2_loader_output.py --kernel-boot-handoff .\runs\kernel_boot_handoff.json --pooleglyph-source-anchor .\runs\pooleglyph_source_anchor.json --parser-kernel-promotion-receipt .\runs\pooleglyph_parser_kernel_promotion_receipt.json --kernel-build-id pending-kernel-loader --out .\runs\kernel_pgvm2_loader_output.json
python .\tools\emit_lab_kernel_transcript_export_receipt.py --out .\runs\lab_kernel_transcript_export_receipt.json
python .\tools\emit_kernel_pgvm2_loader_evidence.py --kernel-boot-handoff .\runs\kernel_boot_handoff.json --kernel-loader-output .\runs\kernel_pgvm2_loader_output.json --pooleglyph-source-anchor .\runs\pooleglyph_source_anchor.json --parser-kernel-promotion-receipt .\runs\pooleglyph_parser_kernel_promotion_receipt.json --out .\runs\kernel_pgvm2_loader_evidence.json
```

The lab transcript receipt stays non-claiming until a real contract run is recorded. Recorded runs are accepted only when the transcript contains exactly one `POOLEOS_KERNEL_GUEST_ENV` audit line for both the PooleGlyph source-anchor and parser-promotion hashes, those values match the host verifier, and the transcript and verifier-output artifact hashes remain bound.

If QEMU already produced a serial log, re-emit the captured evidence without booting again:

```powershell
.\lab-os\qemu\scripts\run-pooleos-lab.ps1 -EmitCapturedEvidenceOnly -SerialLog .\runs\pooleos-lab-serial.log -BootValidationOutput .\runs\boot_log_validation.captured.json -QemuBootEvidenceOutput .\runs\qemu_boot_evidence.captured.json
```

Emit the captured-boot receipt. Before a real QEMU capture exists, this records a pending captured slot while preserving fixture evidence:

```powershell
python .\tools\emit_qemu_captured_boot_receipt.py --fixture-evidence .\runs\qemu_boot_evidence.json --captured-evidence .\runs\qemu_boot_evidence.captured.json --out .\runs\qemu_captured_boot_receipt.json
python .\tools\emit_qemu_captured_boot_launch_bundle.py --preflight .\runs\qemu_captured_boot_preflight.json --qemu-shared-folder-contract .\runs\qemu_shared_folder_contract.json --qemu-captured-boot-receipt .\runs\qemu_captured_boot_receipt.json --fixture-evidence .\runs\qemu_boot_evidence.json --release-gate-output .\runs\release_gate.json --out .\runs\qemu_captured_boot_launch_bundle.json
python .\tools\emit_qemu_captured_boot_dry_run_checklist.py --launch-bundle .\runs\qemu_captured_boot_launch_bundle.json --release-gate-output .\runs\release_gate.json --out .\runs\qemu_captured_boot_dry_run_checklist.json
python .\tools\emit_qemu_boot_marker_contract.py --dry-run-checklist .\runs\qemu_captured_boot_dry_run_checklist.json --lab-guest-autostart .\runs\lab_guest_autostart.json --out .\runs\qemu_boot_marker_contract.json
python .\tools\emit_qemu_boot_marker_image_binding.py --marker-contract .\runs\qemu_boot_marker_contract.json --lab-image-manifest .\runs\lab_image_manifest.json --out .\runs\qemu_boot_marker_image_binding.json
python .\tools\emit_rootfs_content_manifest.py --image-binding .\runs\qemu_boot_marker_image_binding.json --image .\output\images\rootfs.ext4 --extracted-rootfs .\runs\rootfs_extracted --out .\runs\rootfs_content_manifest.json
python .\tools\emit_rootfs_extraction_handoff.py --rootfs-content-manifest .\runs\rootfs_content_manifest.json --note-out .\runs\rootfs_extraction_handoff.md --out .\runs\rootfs_extraction_handoff.json
python .\tools\emit_rootfs_extraction_receipt.py --handoff .\runs\rootfs_extraction_handoff.json --rootfs-content-manifest .\runs\rootfs_content_manifest.json --out .\runs\rootfs_extraction_receipt.json
python .\tools\emit_qemu_captured_boot_readiness.py --rootfs-extraction-receipt .\runs\rootfs_extraction_receipt.json --qemu-captured-boot-receipt .\runs\qemu_captured_boot_receipt.json --qemu-captured-boot-evidence .\runs\qemu_boot_evidence.captured.json --out .\runs\qemu_captured_boot_readiness.json
python .\tools\emit_kernel_boot_handoff.py --qemu-captured-boot-readiness .\runs\qemu_captured_boot_readiness.json --qemu-boot-marker-contract .\runs\qemu_boot_marker_contract.json --boot-trap-bundle-manifest .\runs\pooleos_boot_trap_bundle_manifest.json --guest-loader-verification .\runs\boot_trap_bundle_verification.json --out .\runs\kernel_boot_handoff.json
python .\tools\emit_kernel_pgvm2_loader_output.py --kernel-boot-handoff .\runs\kernel_boot_handoff.json --pooleglyph-source-anchor .\runs\pooleglyph_source_anchor.json --parser-kernel-promotion-receipt .\runs\pooleglyph_parser_kernel_promotion_receipt.json --kernel-build-id pending-kernel-loader --out .\runs\kernel_pgvm2_loader_output.json
python .\tools\emit_lab_kernel_transcript_export_receipt.py --out .\runs\lab_kernel_transcript_export_receipt.json
python .\tools\emit_kernel_pgvm2_loader_evidence.py --kernel-boot-handoff .\runs\kernel_boot_handoff.json --kernel-loader-output .\runs\kernel_pgvm2_loader_output.json --pooleglyph-source-anchor .\runs\pooleglyph_source_anchor.json --parser-kernel-promotion-receipt .\runs\pooleglyph_parser_kernel_promotion_receipt.json --out .\runs\kernel_pgvm2_loader_evidence.json
```

Emit a static microkernel isolation proof:

```powershell
python .\tools\emit_isolation_proof.py --out .\runs\microkernel_isolation.json
python .\tools\validate_artifact.py --schema .\specs\isolation-proof.schema.json .\runs\microkernel_isolation.json
```

Emit a PGB2-style capability trap proof:

```powershell
python .\tools\emit_capability_trap_proof.py --isolation-proof .\runs\microkernel_isolation.json --out .\runs\capability_trap_proof.json
python .\tools\validate_artifact.py --schema .\specs\capability-trap-proof.schema.json .\runs\capability_trap_proof.json
```

Emit a live PooleGlyph source anchor:

```powershell
python .\tools\emit_pooleglyph_source_anchor.py --pooleglyph <POOLEGYPH_REPO> --out .\runs\pooleglyph_source_anchor.json
python .\tools\validate_artifact.py --schema .\specs\pooleglyph-source-anchor.schema.json .\runs\pooleglyph_source_anchor.json
```

Emit a PooleGlyph bridge manifest:

```powershell
python .\tools\emit_pooleglyph_bridge_manifest.py --source-anchor .\runs\pooleglyph_source_anchor.json --pooleglyph <POOLEGYPH_REPO> --out .\runs\pooleglyph_bridge_manifest.json
python .\tools\validate_artifact.py --schema .\specs\pooleglyph-bridge-manifest.schema.json .\runs\pooleglyph_bridge_manifest.json
```

Emit a PooleGlyph Core IR boundary receipt:

```powershell
python .\tools\emit_pooleglyph_core_ir_boundary_receipt.py --bridge-manifest .\runs\pooleglyph_bridge_manifest.json --pooleglyph <POOLEGYPH_REPO> --out .\runs\pooleglyph_core_ir_boundary_receipt.json
python .\tools\validate_artifact.py --schema .\specs\pooleglyph-core-ir-boundary-receipt.schema.json .\runs\pooleglyph_core_ir_boundary_receipt.json
```

Emit a PooleGlyph executable Core IR audit:

```powershell
python .\tools\emit_pooleglyph_core_ir_executable_audit.py --core-ir-boundary-receipt .\runs\pooleglyph_core_ir_boundary_receipt.json --out .\runs\pooleglyph_core_ir_executable_audit.json
python .\tools\validate_artifact.py --schema .\specs\pooleglyph-core-ir-executable-audit.schema.json .\runs\pooleglyph_core_ir_executable_audit.json
```

Emit the parser-to-kernel promotion receipt:

```powershell
python .\tools\emit_pooleglyph_parser_kernel_promotion_receipt.py --core-ir-executable-audit .\runs\pooleglyph_core_ir_executable_audit.json --out .\runs\pooleglyph_parser_kernel_promotion_receipt.json
python .\tools\validate_artifact.py --schema .\specs\pooleglyph-parser-kernel-promotion-receipt.schema.json .\runs\pooleglyph_parser_kernel_promotion_receipt.json
```

Emit a PooleGlyph-derived permission/capability/resource matrix and bind it into trap proof:

```powershell
python .\tools\emit_permission_capability_matrix.py --bridge-manifest .\runs\pooleglyph_bridge_manifest.json --core-ir-boundary-receipt .\runs\pooleglyph_core_ir_boundary_receipt.json --core-ir-executable-audit .\runs\pooleglyph_core_ir_executable_audit.json --parser-kernel-promotion-receipt .\runs\pooleglyph_parser_kernel_promotion_receipt.json --pooleglyph <POOLEGYPH_REPO> --out .\runs\permission_capability_matrix.json
python .\tools\emit_capability_trap_fuzz.py --isolation-proof .\runs\microkernel_isolation.json --permission-capability-matrix .\runs\permission_capability_matrix.json --out .\runs\capability_trap_fuzz.json
python .\tools\emit_capability_trap_proof.py --isolation-proof .\runs\microkernel_isolation.json --permission-capability-matrix .\runs\permission_capability_matrix.json --capability-trap-fuzz .\runs\capability_trap_fuzz.json --out .\runs\capability_trap_proof.json
python .\tools\emit_pgb2_trap_encoding.py --trap-proof .\runs\capability_trap_proof.json --out .\runs\pgb2_trap_encoding.json
python .\tools\emit_pgb2_trap_execution.py --trap-encoding .\runs\pgb2_trap_encoding.json --out .\runs\pgb2_trap_execution.json
python .\tools\emit_pgb2_trap_abi_boundary_receipt.py --trap-encoding .\runs\pgb2_trap_encoding.json --trap-execution .\runs\pgb2_trap_execution.json --bundle .\runs\signed_trap_evidence.pgb2.json --boot-trap-bundle-manifest .\runs\pooleos_boot_trap_bundle_manifest.json --qemu-shared-folder-contract .\runs\qemu_shared_folder_contract.json --out .\runs\pgb2_trap_abi_boundary_receipt.json
python .\tools\validate_artifact.py --schema .\specs\pgb2-trap-abi-boundary-receipt.schema.json .\runs\pgb2_trap_abi_boundary_receipt.json
```

Emit a release-gate report:

```powershell
python .\tools\pooleos_release_gate.py --bundle .\runs\signed_trap_evidence.pgb2.json --replay-proof .\runs\signed_trap_evidence.replay.json --lab-manifest .\runs\lab_image_manifest.json --boot-trap-bundle-manifest .\runs\pooleos_boot_trap_bundle_manifest.json --qemu-shared-folder-contract .\runs\qemu_shared_folder_contract.json --lab-guest-autostart .\runs\lab_guest_autostart.json --qemu-boot-evidence .\runs\qemu_boot_evidence.json --qemu-captured-boot-preflight .\runs\qemu_captured_boot_preflight.json --qemu-captured-boot-launch-bundle .\runs\qemu_captured_boot_launch_bundle.json --qemu-captured-boot-dry-run-checklist .\runs\qemu_captured_boot_dry_run_checklist.json --qemu-boot-marker-contract .\runs\qemu_boot_marker_contract.json --qemu-boot-marker-image-binding .\runs\qemu_boot_marker_image_binding.json --rootfs-content-manifest .\runs\rootfs_content_manifest.json --rootfs-extraction-handoff .\runs\rootfs_extraction_handoff.json --rootfs-extraction-receipt .\runs\rootfs_extraction_receipt.json --qemu-captured-boot-receipt .\runs\qemu_captured_boot_receipt.json --qemu-captured-boot-readiness .\runs\qemu_captured_boot_readiness.json --kernel-boot-handoff .\runs\kernel_boot_handoff.json --kernel-pgvm2-loader-output .\runs\kernel_pgvm2_loader_output.json --lab-kernel-transcript-export-receipt .\runs\lab_kernel_transcript_export_receipt.json --kernel-pgvm2-loader-evidence .\runs\kernel_pgvm2_loader_evidence.json --wsl-prerequisites .\runs\wsl_prerequisites.json --operator-action .\runs\operator_action_request.json --operator-receipt .\runs\operator_action_receipt.json --host-prep-note .\runs\host_prep_note.json --buildroot-probe .\runs\buildroot_probe.json --buildroot-configure .\runs\buildroot_configure.json --buildroot-build .\runs\buildroot_build.json --isolation-proof .\runs\microkernel_isolation.json --capability-trap-proof .\runs\capability_trap_proof.json --capability-trap-fuzz .\runs\capability_trap_fuzz.json --pgb2-trap-encoding .\runs\pgb2_trap_encoding.json --pgb2-trap-execution .\runs\pgb2_trap_execution.json --pgb2-trap-abi-boundary-receipt .\runs\pgb2_trap_abi_boundary_receipt.json --pooleglyph-source-anchor .\runs\pooleglyph_source_anchor.json --pooleglyph-bridge-manifest .\runs\pooleglyph_bridge_manifest.json --pooleglyph-core-ir-boundary-receipt .\runs\pooleglyph_core_ir_boundary_receipt.json --pooleglyph-core-ir-executable-audit .\runs\pooleglyph_core_ir_executable_audit.json --pooleglyph-parser-kernel-promotion-receipt .\runs\pooleglyph_parser_kernel_promotion_receipt.json --permission-capability-matrix .\runs\permission_capability_matrix.json --pdc-source-intake .\runs\pdc_source_intake.json --pdc-math-contract .\runs\pdc_math_contract.json --pdc-golden-vectors .\runs\pdc_golden_vectors.json --pdc-verifier-intake .\runs\pdc_verifier_intake.json --pdc-verifier-reproduction .\runs\pdc_verifier_reproduction.json --pdc-representation-contract .\runs\pdc_representation_contract.json --pdc-representation-receipt .\runs\pdc_representation_receipt.json --pdc-golden-metamorphic-corpus .\runs\pdc_golden_metamorphic_corpus.json --pdc-golden-metamorphic-receipt .\runs\pdc_golden_metamorphic_receipt.json --pdc-qp-contract .\runs\pdc_qp_contract.json --pdc-qp-receipt .\runs\pdc_qp_receipt.json --out .\runs\release_gate.json
```

Emit a Lab image manifest:

```powershell
python .\tools\emit_lab_manifest.py --buildroot-path .\sources\buildroot-2026.05 --buildroot-probe .\runs\buildroot_probe.json --buildroot-configure .\runs\buildroot_configure.json --buildroot-build .\runs\buildroot_build.json --wsl-prerequisites .\runs\wsl_prerequisites.json --release-gate .\runs\release_gate.json --out .\runs\lab_image_manifest.json
```

Run host preflight:

```powershell
python .\tools\pooleos_preflight.py --buildroot-path C:\path\to\buildroot --include-wsl --out .\runs\host_preflight.json
```

Emit a non-mutating WSL prerequisite report:

```powershell
python .\tools\pooleos_wsl_prereqs.py --buildroot-path .\sources\buildroot-2026.05 --out .\runs\wsl_prerequisites.json
```

Emit the operator approval request for WSL package installation:

```powershell
python .\tools\pooleos_operator_action.py --wsl-prerequisites .\runs\wsl_prerequisites.json --out .\runs\operator_action_request.json
python .\tools\pooleos_operator_receipt.py --operator-action .\runs\operator_action_request.json --wsl-prerequisites .\runs\wsl_prerequisites.json --out .\runs\operator_action_receipt.json
python .\tools\pooleos_host_prep_note.py --operator-action .\runs\operator_action_request.json --operator-receipt .\runs\operator_action_receipt.json --note-out .\runs\host_prep_note.md --manifest-out .\runs\host_prep_note.json
```

The host prep note is generated from the action request and receipt. It quotes the exact WSL command, the command SHA-256, and the verification commands to run after operator-approved host preparation.

Run a no-build Buildroot probe once a Buildroot tree is available:

```powershell
.\lab-os\buildroot\scripts\run-build.ps1 -BuildrootPath .\sources\buildroot-2026.05 -ProbeOnly -ProbeReport .\runs\buildroot_probe.json
python .\tools\pooleos_release_gate.py --bundle .\runs\six_support.pgb2.json --replay-proof .\runs\six_support.replay.json --buildroot-probe .\runs\buildroot_probe.json --out .\runs\release_gate.json
```

Current lab source baseline: official Buildroot tag `2026.05`, commit `313414b92c2501a2bc123ffa1b6383dca464de05`.

Run only the Buildroot defconfig step and emit structured evidence:

```powershell
.\lab-os\buildroot\scripts\run-build.ps1 -BuildrootPath .\sources\buildroot-2026.05 -ConfigureOnly -ConfigureReport .\runs\buildroot_configure.json
python .\tools\pooleos_release_gate.py --bundle .\runs\six_support.pgb2.json --replay-proof .\runs\six_support.replay.json --buildroot-probe .\runs\buildroot_probe.json --buildroot-configure .\runs\buildroot_configure.json --out .\runs\release_gate.json
```

Run the WSL-gated defconfig step after emitting WSL prerequisites:

```powershell
python .\tools\pooleos_wsl_configure.py --buildroot-path .\sources\buildroot-2026.05 --prerequisites .\runs\wsl_prerequisites.json --output-dir .\output --out .\runs\buildroot_configure.json
python .\tools\pooleos_wsl_build.py --buildroot-path .\sources\buildroot-2026.05 --configure-report .\runs\buildroot_configure.json --output-dir .\output --out .\runs\buildroot_build.json
```

The build report remains `blocked` until configure passes and `.\output\images\rootfs.ext4` exists with a recorded hash.

## Quick Check

From this directory:

```powershell
python .\tools\pooleos_doctor.py
```

To run the full current PooleGlyph stack as part of the check:

```powershell
python .\tools\pooleos_doctor.py --full
```
