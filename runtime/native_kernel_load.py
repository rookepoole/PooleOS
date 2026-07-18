"""Deterministic PKLOAD6 PBART1/PBP1/PKMAP2/PBEXIT1 media and live oracles."""

from __future__ import annotations

import dataclasses
import hashlib
import json
import re
import struct
from pathlib import Path
from typing import Any

from runtime import (
    native_boot_artifact,
    native_boot_config,
    native_boot_exit,
    native_boot_trust,
    native_elf_loader,
    native_firmware,
    native_initial_system,
    native_inner_live,
    native_kernel_map,
    native_live_boot_handoff,
    native_microcode,
    native_policy,
    native_pooleboot,
    native_recovery,
    native_symbols,
    native_system_manifest,
)
from runtime.schema_validation import validate_json


CONTRACT_ID = "PKLOAD6"
CONFIG_PATH = "EFI/POOLEOS/BOOT.CFG"
MANIFEST_PATH = "EFI/POOLEOS/SYSTEM_A.PBM"
KERNEL_PATH = "EFI/POOLEOS/KERNEL.ELF"
INITIAL_SYSTEM_PATH = "EFI/POOLEOS/INITIAL.PBA"
RECOVERY_PATH = "EFI/POOLEOS/RECOVERY.PBA"
SYMBOLS_PATH = "EFI/POOLEOS/SYMBOLS.PBA"
MICROCODE_PATH = "EFI/POOLEOS/MICROCOD.PBA"
FIRMWARE_PATH = "EFI/POOLEOS/FIRMWARE.PBA"
POLICY_PATH = "EFI/POOLEOS/POLICY.PBA"
TRUST_POLICY_PATH = native_boot_trust.POLICY_PATH
TRUST_STATE_PATH = native_boot_trust.STATE_PATH
POOLEOS_DIRECTORY_NAME = b"POOLEOS    "
CONFIG_SHORT_NAME = b"BOOT    CFG"
MANIFEST_SHORT_NAME = b"SYSTEM_APBM"
KERNEL_SHORT_NAME = b"KERNEL  ELF"
INITIAL_SYSTEM_SHORT_NAME = b"INITIAL PBA"
RECOVERY_SHORT_NAME = b"RECOVERYPBA"
SYMBOLS_SHORT_NAME = b"SYMBOLS PBA"
MICROCODE_SHORT_NAME = b"MICROCODPBA"
FIRMWARE_SHORT_NAME = b"FIRMWAREPBA"
POLICY_SHORT_NAME = b"POLICY  PBA"
TRUST_POLICY_SHORT_NAME = b"TRUST   PBT"
TRUST_STATE_SHORT_NAME = b"TRUSTST PBS"
ARTIFACT_DEFINITIONS = (
    (
        native_boot_artifact.ROLE_INITIAL_SYSTEM,
        "b_initial_system",
        "initial_system",
        r"\EFI\POOLEOS\INITIAL.PBA",
        INITIAL_SYSTEM_PATH,
        INITIAL_SYSTEM_SHORT_NAME,
    ),
    (
        native_boot_artifact.ROLE_RECOVERY,
        "c_recovery",
        "recovery",
        r"\EFI\POOLEOS\RECOVERY.PBA",
        RECOVERY_PATH,
        RECOVERY_SHORT_NAME,
    ),
    (
        native_boot_artifact.ROLE_SYMBOLS,
        "d_symbols",
        "symbols",
        r"\EFI\POOLEOS\SYMBOLS.PBA",
        SYMBOLS_PATH,
        SYMBOLS_SHORT_NAME,
    ),
    (
        native_boot_artifact.ROLE_MICROCODE,
        "e_microcode",
        "microcode",
        r"\EFI\POOLEOS\MICROCOD.PBA",
        MICROCODE_PATH,
        MICROCODE_SHORT_NAME,
    ),
    (
        native_boot_artifact.ROLE_FIRMWARE_MANIFEST,
        "f_firmware",
        "firmware",
        r"\EFI\POOLEOS\FIRMWARE.PBA",
        FIRMWARE_PATH,
        FIRMWARE_SHORT_NAME,
    ),
    (
        native_boot_artifact.ROLE_POLICY_BUNDLE,
        "g_policy",
        "policy",
        r"\EFI\POOLEOS\POLICY.PBA",
        POLICY_PATH,
        POLICY_SHORT_NAME,
    ),
)
PHYSICAL_ORACLE_BASE = 0x0200_0000
CONTRACT_RELATIVE = "specs/native-kernel-load-contract.json"
CONTRACT_SCHEMA_RELATIVE = "specs/native-kernel-load-contract.schema.json"
KMAP_CONTRACT_RELATIVE = "specs/native-kernel-map-contract.json"
KMAP_CONTRACT_SCHEMA_RELATIVE = "specs/native-kernel-map-contract.schema.json"
BOOT_EXIT_CONTRACT_RELATIVE = "specs/native-boot-exit-contract.json"
BOOT_EXIT_CONTRACT_SCHEMA_RELATIVE = "specs/native-boot-exit-contract.schema.json"
READINESS_RELATIVE = "runs/native_kernel_load_readiness.json"
READINESS_SCHEMA_RELATIVE = "specs/native-kernel-load-readiness.schema.json"

IMPLEMENTATION_INPUTS = (
    "native/Cargo.toml",
    "native/Cargo.lock",
    "native/artifact/Cargo.toml",
    "native/artifact/src/lib.rs",
    "native/artifact/src/bin/pbart1_probe.rs",
    "native/boot/Cargo.toml",
    "native/boot/src/lib.rs",
    "native/boot/src/main.rs",
    "native/boot/src/kload.rs",
    "native/boot/src/livehandoff.rs",
    "native/boot/src/kmap.rs",
    "native/boot/src/exit.rs",
    "native/bootload/Cargo.toml",
    "native/bootload/src/lib.rs",
    "native/bootcfg/src/lib.rs",
    "native/trust/Cargo.toml",
    "native/trust/src/lib.rs",
    "native/trust/src/bin/pbtrust1_probe.rs",
    "native/manifest/Cargo.toml",
    "native/manifest/src/lib.rs",
    "native/elf/src/lib.rs",
    "native/firmware/Cargo.toml",
    "native/firmware/src/lib.rs",
    "native/firmware/src/bin/pfwm1_probe.rs",
    "native/handoff/Cargo.toml",
    "native/handoff/src/lib.rs",
    "native/inner/Cargo.toml",
    "native/inner/src/lib.rs",
    "native/inner/src/bin/pinner1_probe.rs",
    "native/kernel/Cargo.toml",
    "native/kernel/linker.ld",
    "native/kernel/manifest.pkm",
    "native/kernel/src/lib.rs",
    "native/kernel/src/main.rs",
    "native/kmap/Cargo.toml",
    "native/kmap/README.md",
    "native/kmap/src/bin/pkmap1_probe.rs",
    "native/kmap/src/bin/pkmap2_probe.rs",
    "native/kmap/src/lib.rs",
    "native/livehandoff/Cargo.toml",
    "native/livehandoff/src/lib.rs",
    "native/microcode/Cargo.toml",
    "native/microcode/src/lib.rs",
    "native/microcode/src/bin/pmcu1_probe.rs",
    "native/policy/Cargo.toml",
    "native/policy/src/lib.rs",
    "native/policy/src/bin/ppol1_probe.rs",
    "native/recovery/Cargo.toml",
    "native/recovery/src/lib.rs",
    "native/recovery/src/bin/prec1_probe.rs",
    "native/symbols/Cargo.toml",
    "native/symbols/src/lib.rs",
    "native/symbols/src/bin/psym1_probe.rs",
    "native/bootexit/Cargo.toml",
    "native/bootexit/README.md",
    "native/bootexit/src/lib.rs",
    "runtime/native_boot_exit.py",
    "runtime/native_boot_artifact.py",
    "runtime/native_boot_config.py",
    "runtime/native_boot_trust.py",
    "runtime/native_elf_loader.py",
    "runtime/native_firmware.py",
    "runtime/native_kernel_image.py",
    "runtime/native_initial_system.py",
    "runtime/native_inner_live.py",
    "runtime/native_microcode.py",
    "runtime/native_policy.py",
    "runtime/native_recovery.py",
    "runtime/native_symbols.py",
    "runtime/native_kernel_load.py",
    "runtime/native_kernel_map.py",
    "runtime/native_live_boot_handoff.py",
    "runtime/native_pooleboot.py",
    "runtime/native_system_manifest.py",
    "specs/native-boot-digest-provider.json",
    "specs/native-boot-digest-provider.schema.json",
    "docs/native-boot-trust.md",
    "specs/native-boot-trust-contract.json",
    "specs/native-boot-trust-contract.schema.json",
    "specs/native-boot-trust-readiness.schema.json",
    "runs/native_boot_trust_readiness.json",
    "docs/native-initial-system-profile.md",
    "docs/native-initial-system-bundle.md",
    "specs/native-initial-system-contract.json",
    "specs/native-initial-system-contract.schema.json",
    "specs/native-initial-system-golden-vectors.json",
    "specs/native-initial-system-golden-vectors.schema.json",
    "specs/native-initial-system-readiness.schema.json",
    "runs/native_initial_system_readiness.json",
    "docs/native-recovery-bundle.md",
    "specs/native-recovery-contract.json",
    "specs/native-recovery-contract.schema.json",
    "specs/native-recovery-golden-vectors.json",
    "specs/native-recovery-golden-vectors.schema.json",
    "specs/native-recovery-readiness.schema.json",
    "specs/fixtures/prec1-canonical.bin",
    "specs/fixtures/prec1-canonical-state.bin",
    "runs/native_recovery_readiness.json",
    "docs/native-symbol-bundle.md",
    "specs/native-symbol-contract.json",
    "specs/native-symbol-contract.schema.json",
    "specs/native-symbol-golden-vectors.json",
    "specs/native-symbol-golden-vectors.schema.json",
    "specs/native-symbol-readiness.schema.json",
    "specs/fixtures/psym1-canonical.bin",
    "specs/fixtures/psym1-minimal.bin",
    "specs/fixtures/psym1-boundary.bin",
    "runs/native_symbol_readiness.json",
    "docs/native-microcode-bundle.md",
    "specs/native-microcode-contract.json",
    "specs/native-microcode-contract.schema.json",
    "specs/native-microcode-golden-vectors.json",
    "specs/native-microcode-golden-vectors.schema.json",
    "specs/native-microcode-readiness.schema.json",
    "specs/fixtures/pmcu1-canonical.bin",
    "specs/fixtures/pmcu1-minimal.bin",
    "specs/fixtures/pmcu1-boundary.bin",
    "runs/native_microcode_readiness.json",
    "docs/native-firmware-manifest.md",
    "specs/native-firmware-contract.json",
    "specs/native-firmware-contract.schema.json",
    "specs/native-firmware-golden-vectors.json",
    "specs/native-firmware-golden-vectors.schema.json",
    "specs/native-firmware-readiness.schema.json",
    "specs/fixtures/pfwm1-canonical.bin",
    "runs/native_firmware_readiness.json",
    "docs/native-policy-bundle.md",
    "specs/native-policy-contract.json",
    "specs/native-policy-contract.schema.json",
    "specs/native-policy-golden-vectors.json",
    "specs/native-policy-golden-vectors.schema.json",
    "specs/native-policy-readiness.schema.json",
    "specs/fixtures/ppol1-canonical.bin",
    "specs/fixtures/ppol1-minimal.bin",
    "specs/fixtures/ppol1-boundary.bin",
    "specs/fixtures/ppol1-canonical-pinit.bin",
    "runs/native_policy_readiness.json",
    "specs/native-kernel-load-contract.json",
    "specs/native-kernel-load-contract.schema.json",
    "specs/native-kernel-load-readiness.schema.json",
    "specs/native-kernel-map-contract.json",
    "specs/native-kernel-map-contract.schema.json",
    "tools/qualify_native_pooleboot.py",
    "tools/qualify_native_boot_trust.py",
    "tools/qualify_native_kernel_load.py",
    "tools/generate_native_recovery_vectors.py",
    "tools/qualify_native_recovery.py",
    "tools/generate_native_symbol_vectors.py",
    "tools/qualify_native_symbols.py",
    "tools/generate_native_microcode_vectors.py",
    "tools/qualify_native_microcode.py",
    "tools/generate_native_firmware_vectors.py",
    "tools/qualify_native_firmware.py",
    "tools/generate_native_policy_vectors.py",
    "tools/qualify_native_policy.py",
    "tests/test_native_boot_artifact.py",
    "tests/test_native_boot_trust.py",
    "tests/test_native_initial_system.py",
    "tests/test_native_inner_live.py",
    "tests/test_native_recovery.py",
    "tests/test_native_symbols.py",
    "tests/test_native_microcode.py",
    "tests/test_native_firmware.py",
    "tests/test_native_policy.py",
    "tests/test_native_live_boot_handoff.py",
)

TRUE_CLAIMS = (
    "loaded_image_protocol_observed",
    "simple_filesystem_protocol_observed",
    "live_pbc1_file_parsed",
    "live_psm1_file_parsed",
    "manifest_selected_kernel_path",
    "manifest_slot_bound",
    "manifest_version_floor_validated",
    "manifest_kernel_size_bound",
    "manifest_kernel_sha256_matched",
    "live_pkelf1_file_read",
    "pkelf1_relocated_into_firmware_pages",
    "pkelf1_mapping_plan_validated",
    "live_pbart1_files_read",
    "pbart1_role_version_payload_digest_validated",
    "initial_system_inner_oracle_validated",
    "initial_system_development_activation_denied",
    "recovery_inner_oracle_validated",
    "recovery_development_activation_denied",
    "symbols_inner_oracle_validated",
    "symbols_development_activation_denied",
    "microcode_inner_oracle_validated",
    "microcode_development_activation_denied",
    "firmware_inner_oracle_validated",
    "firmware_development_activation_denied",
    "policy_inner_oracle_validated",
    "policy_development_activation_denied",
    "pooleboot_retained_inner_set_parsed",
    "pooleboot_policy_payload_bindings_enforced",
    "pooleboot_initial_routes_cross_bound",
    "pooleboot_development_denials_enforced",
    "live_pbtrust1_policy_read",
    "live_pbtrust1_state_candidate_read",
    "pooleboot_trust_cross_bindings_enforced",
    "pooleboot_trust_development_denial_enforced",
    "artifact_set_manifest_sha256_matched",
    "artifact_pages_retained",
    "pbp1_profile_artifacts_cross_bound",
    "kernel_pages_live_during_pbp1",
    "live_pbp1_post_exit_development_produced",
    "live_pbp1_transcript_reconstructed",
    "uefi_descriptor_stride_honored",
    "pbp1_kernel_manifest_cross_bound",
    "pbp1_logical_finalization_verified",
    "pkmap1_exact_4k_leaves_built",
    "pkmap2_guarded_stack_retained",
    "pkmap2_read_only_handoff_retained",
    "temporary_candidate_cr3_activated",
    "higher_half_kernel_alias_verified",
    "wp_nx_wx_enforced",
    "framebuffer_translation_cache_preserved",
    "original_cr3_restored_before_firmware",
    "kernel_pages_retained",
    "page_tables_retained",
    "zero_firmware_calls_while_candidate_active",
    "exit_boot_services_called",
    "no_firmware_calls_after_exit",
    "stop_before_transfer_observed",
    "two_qemu_runs_exact",
)
FALSE_CLAIMS = (
    "manifest_signature_verified",
    "manifest_trusted",
    "persistent_rollback_state_enforced",
    "kernel_signature_verified",
    "artifact_signatures_verified",
    "artifact_semantics_applied",
    "pooleboot_inner_authority_created",
    "pooleboot_inner_action_authorized",
    "pooleboot_inner_state_written",
    "pooleboot_initial_system_semantics_enforced",
    "poolekernel_initial_system_activation_enforced",
    "initial_system_executed",
    "pooleboot_recovery_semantics_enforced",
    "poolekernel_recovery_activation_enforced",
    "recovery_executed",
    "pooleboot_symbols_semantics_enforced",
    "poolekernel_symbols_activation_enforced",
    "symbols_consumed",
    "pooleboot_microcode_semantics_enforced",
    "poolekernel_microcode_apply_enforced",
    "microcode_applied",
    "pooleboot_firmware_semantics_enforced",
    "poolekernel_firmware_apply_enforced",
    "firmware_update_applied",
    "live_firmware_inventory_observed",
    "production_firmware_payload_included",
    "pooleboot_policy_semantics_enforced",
    "poolekernel_policy_enforced",
    "policy_decision_applied",
    "pooleglyph_policy_authority_created",
    "trust_policy_signature_verified",
    "trust_state_authenticated",
    "trust_state_monotonic",
    "trust_state_backend_written",
    "all_pbp1_temporary_pools_released",
    "all_kmap_table_pages_released",
    "all_kload_resources_released",
    "final_kernel_address_space_established",
    "final_framebuffer_cache_policy_qualified",
    "kernel_entry_called",
    "transferable_pbp1_handoff_produced",
    "secure_boot_enforced",
    "measured_boot_performed",
    "physical_hardware_tested",
    "n5_exit_gate_satisfied",
    "production_ready",
)

NEGATIVE_CONTROL_IDS = (
    "NEG-N5-KLOAD-CONFIG-MISSING",
    "NEG-N5-KLOAD-CONFIG-EMPTY",
    "NEG-N5-KLOAD-CONFIG-OVERSIZE",
    "NEG-N5-KLOAD-CONFIG-MALFORMED",
    "NEG-N5-KLOAD-MANIFEST-MISSING",
    "NEG-N5-KLOAD-MANIFEST-EMPTY",
    "NEG-N5-KLOAD-MANIFEST-OVERSIZE",
    "NEG-N5-KLOAD-MANIFEST-MALFORMED",
    "NEG-N5-KLOAD-KERNEL-MISSING",
    "NEG-N5-KLOAD-KERNEL-EMPTY",
    "NEG-N5-KLOAD-KERNEL-OVERSIZE",
    "NEG-N5-KLOAD-KERNEL-MALFORMED",
    "NEG-N5-KLOAD-FAT-COPY",
    "NEG-N5-KLOAD-FAT-CHAIN-LOOP",
    "NEG-N5-KLOAD-DIRECTORY-PATH",
    "NEG-N5-KLOAD-CONFIG-PATH",
    "NEG-N5-KLOAD-MANIFEST-PATH",
    "NEG-N5-KLOAD-KERNEL-PATH",
    "NEG-N5-KLOAD-CONFIG-CONTENT",
    "NEG-N5-KLOAD-MANIFEST-CONTENT",
    "NEG-N5-KLOAD-KERNEL-CONTENT",
    "NEG-N5-KLOAD-ARTIFACT-MISSING",
    "NEG-N5-KLOAD-ARTIFACT-EMPTY",
    "NEG-N5-KLOAD-ARTIFACT-OVERSIZE",
    "NEG-N5-KLOAD-ARTIFACT-PATH",
    "NEG-N5-KLOAD-ARTIFACT-CONTENT",
    "NEG-N5-KLOAD-ARTIFACT-ROLE",
    "NEG-N5-KLOAD-ARTIFACT-VERSION",
    "NEG-N5-KLOAD-ARTIFACT-PAYLOAD-DIGEST",
    "NEG-N5-KLOAD-ARTIFACT-MANIFEST-DIGEST",
    "NEG-N5-KLOAD-INITIAL-SYSTEM-INNER-SEMANTICS",
    "NEG-N5-KLOAD-INITIAL-SYSTEM-INNER-VERSION",
    "NEG-N5-KLOAD-INITIAL-SYSTEM-ACTIVATION-OVERREACH",
    "NEG-N5-KLOAD-RECOVERY-INNER-SEMANTICS",
    "NEG-N5-KLOAD-RECOVERY-INNER-VERSION",
    "NEG-N5-KLOAD-RECOVERY-ACTIVATION-OVERREACH",
    "NEG-N5-KLOAD-SYMBOLS-INNER-SEMANTICS",
    "NEG-N5-KLOAD-SYMBOLS-INNER-VERSION",
    "NEG-N5-KLOAD-SYMBOLS-ACTIVATION-OVERREACH",
    "NEG-N5-KLOAD-MICROCODE-INNER-SEMANTICS",
    "NEG-N5-KLOAD-MICROCODE-INNER-VERSION",
    "NEG-N5-KLOAD-MICROCODE-ACTIVATION-OVERREACH",
    "NEG-N5-KLOAD-FIRMWARE-INNER-SEMANTICS",
    "NEG-N5-KLOAD-FIRMWARE-INNER-VERSION",
    "NEG-N5-KLOAD-FIRMWARE-ACTIVATION-OVERREACH",
    "NEG-N5-KLOAD-POLICY-INNER-SEMANTICS",
    "NEG-N5-KLOAD-POLICY-INNER-VERSION",
    "NEG-N5-KLOAD-POLICY-ACTIVATION-OVERREACH",
    "NEG-N5-KLOAD-MARKER-OMISSION",
    "NEG-N5-KLOAD-MARKER-ORDER",
    "NEG-N5-KLOAD-MARKER-CONFIG-BOUND",
    "NEG-N5-KLOAD-MARKER-MANIFEST-BOUND",
    "NEG-N5-KLOAD-MARKER-MANIFEST-SLOT",
    "NEG-N5-KLOAD-MARKER-DIGEST",
    "NEG-N5-KLOAD-MARKER-KERNEL-BOUND",
    "NEG-N5-KLOAD-MARKER-PAGE-MATH",
    "NEG-N5-KLOAD-MARKER-ENTRY-BOUND",
    "NEG-N5-KLOAD-MARKER-ARTIFACT-COUNT",
    "NEG-N5-KLOAD-MARKER-ARTIFACT-SIGNATURE",
    "NEG-N5-KLOAD-MARKER-INNER-PARSER",
    "NEG-N5-KLOAD-MARKER-INNER-BINDING",
    "NEG-N5-KLOAD-MARKER-INNER-DENIAL",
    "NEG-N5-KLOAD-MARKER-INNER-DIGEST",
    "NEG-N5-KLOAD-MARKER-INNER-AUTHORITY",
    "NEG-N5-KLOAD-MARKER-INNER-ACTION",
    "NEG-N5-KLOAD-MARKER-INNER-STATE",
    "NEG-N5-KLOAD-MARKER-INNER-HARDWARE",
    "NEG-N5-KLOAD-INNER-ORACLE-DIVERGENCE",
    "NEG-N5-KLOAD-TRUST-POLICY-MISSING",
    "NEG-N5-KLOAD-TRUST-STATE-MISSING",
    "NEG-N5-KLOAD-TRUST-POLICY-CORRUPT",
    "NEG-N5-KLOAD-TRUST-STATE-CORRUPT",
    "NEG-N5-KLOAD-TRUST-POLICY-KERNEL-BINDING",
    "NEG-N5-KLOAD-TRUST-STATE-POLICY-BINDING",
    "NEG-N5-KLOAD-MARKER-TRUST-DENIAL",
    "NEG-N5-KLOAD-MARKER-TRUST-AUTHORITY",
    "NEG-N5-KLOAD-TRUST-ORACLE-DIVERGENCE",
    "NEG-N5-KLOAD-MARKER-MAPPING-COUNT",
    "NEG-N5-KLOAD-MARKER-WX",
    "NEG-N5-KLOAD-MARKER-RETAIN-COUNT",
    "NEG-N5-KLOAD-MARKER-BOUNDARY",
    "NEG-N5-KLOAD-CONFIG-ORACLE-DIVERGENCE",
    "NEG-N5-KLOAD-MANIFEST-ORACLE-DIVERGENCE",
    "NEG-N5-KLOAD-ELF-ORACLE-DIVERGENCE",
    "NEG-N5-KLOAD-LOADED-HASH-DIVERGENCE",
    "NEG-N5-KLOAD-ARTIFACT-ORACLE-DIVERGENCE",
    "NEG-N5-KLOAD-CLAIM-OVERREACH",
    "NEG-N5-KLOAD-STALE-BINDING",
    "NEG-N5-PBP1-TRANSCRIPT-MISSING",
    "NEG-N5-PBP1-TRANSCRIPT-DUPLICATE-BEGIN",
    "NEG-N5-PBP1-TRANSCRIPT-OFFSET-GAP",
    "NEG-N5-PBP1-TRANSCRIPT-NONHEX",
    "NEG-N5-PBP1-TRANSCRIPT-BYTE-COUNT",
    "NEG-N5-PBP1-TRANSCRIPT-MESSAGE-CRC",
    "NEG-N5-PBP1-TRANSCRIPT-FNV",
    "NEG-N5-PBP1-EXIT-STATE",
    "NEG-N5-PBP1-ARTIFACT-DIGEST-ORACLE",
    "NEG-N5-PBP1-ARTIFACT-ROLE",
    "NEG-N5-PBP1-ARTIFACT-OMISSION",
    "NEG-N5-PBP1-ARTIFACT-OVERLAP",
    "NEG-N5-PBP1-ARTIFACT-SIGNATURE",
    "NEG-N5-PBP1-ARTIFACT-RANGE-COVERAGE",
    "NEG-N5-PBP1-MARKER-BYTE-DIVERGENCE",
    "NEG-N5-PBP1-MARKER-MEMORY-DIVERGENCE",
    "NEG-N5-PBP1-RETAINED-RANGE-OMISSION",
    "NEG-N5-KMAP-CPU-WP",
    "NEG-N5-KMAP-CPU-NX-SUPPORT",
    "NEG-N5-KMAP-CPU-NX-ENABLE",
    "NEG-N5-KMAP-CPU-LA57",
    "NEG-N5-KMAP-CPU-PCID",
    "NEG-N5-KMAP-ROOT-OCCUPIED",
    "NEG-N5-KMAP-ALIGNMENT",
    "NEG-N5-KMAP-COVERAGE-GAP",
    "NEG-N5-KMAP-COVERAGE-OVERLAP",
    "NEG-N5-KMAP-PHYSICAL-RANGE",
    "NEG-N5-KMAP-TABLE-OVERLAP",
    "NEG-N5-KMAP-WX",
    "NEG-N5-KMAP-LEAF-PHYSICAL",
    "NEG-N5-KMAP-LEAF-FLAGS",
    "NEG-N5-KMAP-LARGE-PAGE",
    "NEG-N5-KMAP-FRAMEBUFFER-TRANSLATION",
    "NEG-N5-KMAP-FRAMEBUFFER-CACHE",
    "NEG-N5-KMAP-ACTIVATION",
    "NEG-N5-KMAP-ROLLBACK",
    "NEG-N5-KMAP-FIRMWARE-ACTIVE",
    "NEG-N5-KMAP-RETENTION",
    "NEG-N5-KMAP-MARKER-PLAN",
    "NEG-N5-KMAP-MARKER-ACTIVE",
    "NEG-N5-KMAP-MARKER-RETAIN",
    "NEG-N5-KMAP-ORACLE-DIVERGENCE",
    "NEG-N5-PBP1-RETAINED-RANGE-KIND",
    "NEG-N5-PBP1-ROOT-BINDING",
    "NEG-N5-PBP1-STACK-BINDING",
    "NEG-N5-PBP1-HANDOFF-BINDING",
    "NEG-N5-KMAP-RETAINED-OVERLAP",
    "NEG-N5-KMAP-STACK-SHAPE",
    "NEG-N5-KMAP-GUARD-LAYOUT",
    "NEG-N5-PBEXIT-MAP-SHAPE",
    "NEG-N5-PBEXIT-DESCRIPTOR-VERSION",
    "NEG-N5-PBEXIT-ORDER",
    "NEG-N5-PBEXIT-NONRETRYABLE",
    "NEG-N5-PBEXIT-RETRY-EXHAUSTED",
    "NEG-N5-PBEXIT-POST-ATTEMPT-FIRMWARE",
    "NEG-N5-PBEXIT-POST-EXIT-FIRMWARE",
    "NEG-N5-PBEXIT-MARKER-ATTEMPTS",
    "NEG-N5-PBEXIT-MARKER-DESCRIPTOR",
    "NEG-N5-PBEXIT-FIRMWARE-BOUNDARY",
    "NEG-N5-PBEXIT-TRANSFER",
)
KMAP_NEGATIVE_CONTROL_IDS = tuple(
    value for value in NEGATIVE_CONTROL_IDS if value.startswith("NEG-N5-KMAP-")
)
BOOT_EXIT_NEGATIVE_CONTROL_IDS = tuple(
    value for value in NEGATIVE_CONTROL_IDS if value.startswith("NEG-N5-PBEXIT-")
)

MARKER_PATTERNS = (
    re.compile(r"^POOLEBOOT/0\.1 ENTRY$"),
    re.compile(r"^POOLEBOOT/0\.1 SYSTEM_TABLE PASS revision=0x([0-9A-F]{8})$"),
    re.compile(r"^POOLEBOOT/0\.1 BOOT_SERVICES PASS$"),
    re.compile(r"^POOLEBOOT/0\.1 WATCHDOG status=0x[0-9A-F]{16}$"),
    re.compile(r"^POOLEBOOT/0\.1 CONSOLE (?:PASS|FALLBACK status=0x[0-9A-F]{16})$"),
    re.compile(
        r"^POOLEBOOT/0\.1 CONFIG PASS count=([0-9]+) acpi20=([01]) smbios3=([01]) smbios2=([01])$"
    ),
    re.compile(r"^POOLEBOOT/0\.1 FILESYSTEM PASS loaded_image=1 simple_fs=1 root=1$"),
    re.compile(
        r"^POOLEBOOT/0\.1 BOOTCFG PASS bytes=([0-9]+) entries=([0-9]+) default_hash=([0-9A-F]{16}) timeout_ms=([0-9]+) attempts=([0-9]+) slot=([0-9]+) manifest_max_bytes=([0-9]+)$"
    ),
    re.compile(
        r"^POOLEBOOT/0\.1 MANIFEST PASS bytes=([0-9]+) artifacts=([0-9]+) id_hash=([0-9A-F]{16}) slot=([0-9]+) version=([0-9]+) minimum_secure_version=([0-9]+)$"
    ),
    re.compile(
        r"^POOLEBOOT/0\.1 KERNEL_BINDING PASS version=([0-9]+) file_bytes=([0-9]+) image_bytes=([0-9]+) sha256_prefix=([0-9A-F]{16}) path=manifest$"
    ),
    re.compile(r"^POOLEBOOT/0\.1 KERNEL_FILE PASS bytes=([0-9]+) path=manifest_development$"),
    re.compile(
        r"^POOLEBOOT/0\.1 KERNEL_LOAD PASS image_bytes=([0-9]+) pages=([0-9]+) entry_offset=([0-9]+) relocations=([0-9]+) files_closed=([0-9]+) pools_freed=([0-9]+) fnv1a64=([0-9A-F]{16})$"
    ),
    re.compile(
        r"^POOLEBOOT/0\.1 ARTIFACT_SET PASS contract=(PBART1) count=([0-9]+) file_bytes=([0-9]+) pages=([0-9]+) roles=2-7 fnv1a64=([0-9A-F]{16}) retained=([01]) signatures=([01]) measured=([01])$"
    ),
    re.compile(
        r"^POOLEBOOT/0\.1 INNER_SET PASS proof=(N5-INNER-LIVE-PARSE-001) artifacts=([0-9]+) parsers=([0-9]+) bindings=([0-9]+) denials=([0-9]+) file_bytes=([0-9]+) payload_bytes=([0-9]+) sha256=([0-9A-F]{64}) retained=([01]) authority_grants=([0-9]+) actions=([0-9]+) state_writes=([0-9]+) hardware_observations=([0-9]+)$"
    ),
    re.compile(
        r"^POOLEBOOT/0\.1 TRUST_STATE DENY contract=(PBTRUST1) policy_bytes=([0-9]+) state_bytes=([0-9]+) bindings=([0-9]+) denials=([0-9]+) denial=(pbtrust_policy_unsigned) policy_sha256=([0-9A-F]{64}) state_sha256=([0-9A-F]{64}) source=(esp_candidate) auth=(missing) monotonic=(missing) signatures=([0-9]+) authority_grants=([0-9]+) state_writes=([0-9]+)$"
    ),
    re.compile(
        r"^POOLEBOOT/0\.1 GOP PASS width=([0-9]+) height=([0-9]+) stride=([0-9]+) mode=([0-9]+) format=(RGB|BGR)$"
    ),
    re.compile(r"^POOLEBOOT/0\.1 FRAME READY$"),
    re.compile(
        r"^POOLEBOOT/0\.1 KERNEL_MAP_PLAN PASS contract=(PKMAP2) mappings=([0-9]+) kernel_pages=([0-9]+) ro=([0-9]+) rx=([0-9]+) rw=([0-9]+) wx=([0-9]+) pml4=([0-9]+) pdpt=([0-9]+) pd=([0-9]+) pt=([0-9]+) leaf_fnv1a64=([0-9A-F]{16})$"
    ),
    re.compile(
        r"^POOLEBOOT/0\.1 KERNEL_MAP_ACTIVE PASS table_pages=([0-9]+) kernel_pages=([0-9]+) physical_bits=([0-9]+) mapped_fnv1a64=([0-9A-F]{16}) framebuffer=preserved cache_signature=([0-9A-F]{2}) first_page_bytes=([0-9]+) last_page_bytes=([0-9]+)$"
    ),
    re.compile(
        r"^POOLEBOOT/0\.1 KERNEL_MAP_RETAIN PASS table_pages=([0-9]+) stack_pages=([0-9]+) handoff_pages=([0-9]+) guards=([0-9]+) total_pages=([0-9]+) stack_pt=([0-9]+) handoff_pt=([0-9]+) kernel_phys=([0-9A-F]{16}) root=([0-9A-F]{16}) stack_phys=([0-9A-F]{16}) stack_top=([0-9A-F]{16}) handoff_phys=([0-9A-F]{16}) handoff_virt=([0-9A-F]{16}) retained_fnv1a64=([0-9A-F]{16}) original_cr3=restored firmware_calls_while_active=([0-9]+)$"
    ),
    re.compile(
        r"^POOLEBOOT/0\.1 PBP1_FINAL PASS bytes=([0-9]+) records=([0-9]+) memory_entries=([0-9]+) framebuffer=([01]) artifacts=([0-9]+) descriptor_bytes=([0-9]+) exit_attempts=([0-9]+) message_crc32=([0-9A-F]{8}) fnv1a64=([0-9A-F]{16}) state=boot_services_exited bytes_unchanged=([01])$"
    ),
    re.compile(
        r"^POOLEBOOT/0\.1 EXIT_BOOT_SERVICES PASS contract=(PBEXIT1) attempts=([0-9]+) map_bytes=([0-9]+) descriptor_bytes=([0-9]+) descriptors=([0-9]+)$"
    ),
    re.compile(
        r"^POOLEBOOT/0\.1 FIRMWARE_BOUNDARY PASS calls_after_exit=([0-9]+) kernel_pages=([0-9]+) artifact_pages=([0-9]+) table_pages=([0-9]+) stack_pages=([0-9]+) handoff_pages=([0-9]+)$"
    ),
    re.compile(
        r"^POOLEBOOT/0\.1 BOUNDARY unsigned=1 secure_boot=not_tested selection=manifest_digest_untrusted artifacts=digest_verified_untrusted semantics=parsed_live_unsigned_denied authority=none actions=none kernel=retained handoff=retained mappings=retained entry=not_called exit_boot_services=called transfer=stopped$"
    ),
    re.compile(r"^POOLEBOOT/0\.1 STOP BEFORE TRANSFER$"),
)


class KernelLoadError(RuntimeError):
    """Raised when a PKLOAD6 proof input violates its bounded contract."""


def canonical_config_bytes() -> bytes:
    return native_boot_config.encode(
        (
            native_boot_config.Entry(
                "normal",
                "normal",
                1,
                r"\EFI\POOLEOS\SYSTEM_A.PBM",
                65_536,
            ),
        ),
        default_entry="normal",
        timeout_ms=0,
        boot_attempt_limit=3,
    )


def canonical_artifact_files() -> dict[str, bytes]:
    encoded = native_boot_artifact.canonical_artifacts()
    return {path: encoded[role] for role, _, _, _, path, _ in ARTIFACT_DEFINITIONS}


def canonical_trust_files(
    manifest_data: bytes,
    kernel_data: bytes,
    artifact_files: dict[str, bytes],
) -> tuple[dict[str, bytes], native_boot_trust.ObservedBoot]:
    manifest = native_system_manifest.parse(manifest_data)
    retained = native_inner_live.retained_set_sha256(
        [artifact_files[definition[4]] for definition in ARTIFACT_DEFINITIONS]
    )
    policy, state, observed = native_boot_trust.canonical_development_records(
        manifest_data=manifest_data,
        kernel_data=kernel_data,
        retained_set_sha256=retained,
        manifest_version=manifest.manifest_version,
        minimum_secure_version=manifest.minimum_secure_version,
    )
    return {
        TRUST_POLICY_PATH: policy,
        TRUST_STATE_PATH: state,
    }, observed


def initial_system_oracle(data: bytes, expected_version: int) -> dict[str, Any]:
    artifact = native_boot_artifact.parse_bound(
        data, native_boot_artifact.ROLE_INITIAL_SYSTEM, expected_version
    )
    _, bundle = native_boot_artifact.parse_initial_system(data)
    errors = native_initial_system.activation_errors(
        bundle, native_initial_system.development_activation_context()
    )
    if not errors or errors[0] != "pinit_activation_outer_signature_verified":
        raise KernelLoadError("PINIT1 development activation boundary changed")
    return {
        "contract_id": native_initial_system.CONTRACT_ID,
        "summary": native_initial_system.summary(bundle),
        "bundle_sha256": native_initial_system.sha256_bytes(bundle.raw),
        "bundle_version": bundle.bundle_version,
        "component_count": len(bundle.components),
        "service_count": len(bundle.services),
        "dependency_count": len(bundle.dependencies),
        "resource_count": len(bundle.resources),
        "capability_count": len(bundle.capabilities),
        "start_order": list(bundle.start_order),
        "outer_payload_sha256": artifact.payload_sha256,
        "activation_allowed": False,
        "activation_errors": list(errors),
        "validated_by": "independent_host_media_oracle",
        "pooleboot_enforced": False,
        "poolekernel_enforced": False,
    }


def recovery_oracle(data: bytes, expected_version: int) -> dict[str, Any]:
    artifact = native_boot_artifact.parse_bound(
        data, native_boot_artifact.ROLE_RECOVERY, expected_version
    )
    _, bundle = native_boot_artifact.parse_recovery(data)
    errors = native_recovery.activation_errors(
        bundle, native_recovery.development_activation_context()
    )
    if not errors or errors[0] != "prec_activation_outer_signature":
        raise KernelLoadError("PREC1 development activation boundary changed")
    return {
        "contract_id": native_recovery.CONTRACT_ID,
        "summary": native_recovery.summary(bundle),
        "bundle_sha256": native_recovery.sha256_bytes(bundle.raw),
        "bundle_version": bundle.bundle_version,
        "slot_count": len(bundle.slots),
        "failure_rule_count": len(bundle.failure_rules),
        "authority_rule_count": len(bundle.authority_rules),
        "max_attempts": bundle.max_attempts,
        "mutable_state_bytes": native_recovery.STATE_BYTES,
        "outer_payload_sha256": artifact.payload_sha256,
        "activation_allowed": False,
        "activation_errors": list(errors),
        "validated_by": "independent_host_media_oracle",
        "pooleboot_enforced": False,
        "poolekernel_enforced": False,
        "recovery_executed": False,
    }


def symbols_oracle(data: bytes, expected_version: int) -> dict[str, Any]:
    artifact = native_boot_artifact.parse_bound(
        data, native_boot_artifact.ROLE_SYMBOLS, expected_version
    )
    _, bundle = native_boot_artifact.parse_symbols(data)
    errors = native_symbols.consumption_errors(
        bundle, native_symbols.development_consumption_context(bundle)
    )
    if not errors or errors[0] != "psym_activation_outer_signature":
        raise KernelLoadError("PSYM1 development activation boundary changed")
    return {
        "contract_id": native_symbols.CONTRACT_ID,
        "summary": native_symbols.summary(bundle),
        "bundle_sha256": native_symbols.sha256_bytes(bundle.raw),
        "bundle_version": native_symbols.MAJOR_VERSION,
        "segment_count": len(bundle.segments),
        "symbol_count": len(bundle.symbols),
        "string_bytes": sum(len(item.name) for item in bundle.symbols),
        "maximum_lookup_steps": native_symbols.MAX_LOOKUP_STEPS,
        "outer_payload_sha256": artifact.payload_sha256,
        "activation_allowed": False,
        "activation_errors": list(errors),
        "validated_by": "independent_host_media_oracle",
        "pooleboot_enforced": False,
        "poolekernel_enforced": False,
        "symbols_consumed": False,
        "runtime_addresses_disclosed": False,
        "full_debug_file_on_media": False,
        "authority_created": False,
    }


def microcode_oracle(data: bytes, expected_version: int) -> dict[str, Any]:
    artifact = native_boot_artifact.parse_bound(
        data, native_boot_artifact.ROLE_MICROCODE, expected_version
    )
    _, bundle = native_boot_artifact.parse_microcode(data)
    errors = native_microcode.apply_plan_errors(
        bundle,
        native_microcode.development_apply_context(
            bundle, outer_file_sha256=artifact.file_sha256
        ),
    )
    if not errors or errors[0] != "pmcu_activation_outer_signature":
        raise KernelLoadError("PMCU1 development activation boundary changed")
    return {
        "contract_id": native_microcode.CONTRACT_ID,
        "summary": native_microcode.summary(bundle),
        "bundle_sha256": hashlib.sha256(bundle.raw).hexdigest().upper(),
        "bundle_version": native_microcode.MAJOR_VERSION,
        "patch_count": len(bundle.patches),
        "security_revision_floor": bundle.security_revision_floor,
        "known_good_revision": bundle.known_good_revision,
        "preferred_revision": bundle.preferred_revision,
        "outer_payload_sha256": artifact.payload_sha256,
        "activation_allowed": False,
        "activation_errors": list(errors),
        "validated_by": "independent_host_media_oracle",
        "pooleboot_enforced": False,
        "poolekernel_enforced": False,
        "vendor_container_validated": False,
        "production_vendor_payload_included": False,
        "privileged_revision_observed": False,
        "microcode_applied": False,
        "firmware_mutated": False,
        "physical_media_written": False,
        "synthetic_payloads_only": True,
        "authority_created": False,
    }


def firmware_oracle(data: bytes, expected_version: int) -> dict[str, Any]:
    artifact = native_boot_artifact.parse_bound(
        data, native_boot_artifact.ROLE_FIRMWARE_MANIFEST, expected_version
    )
    _, bundle = native_boot_artifact.parse_firmware(data)
    errors = native_firmware.activation_errors(
        bundle,
        native_firmware.development_activation_context(
            bundle, outer_file_sha256=artifact.file_sha256
        ),
    )
    if not errors or errors[0] != "pfwm_activation_outer_signature":
        raise KernelLoadError("PFWM1 development activation boundary changed")
    return {
        "contract_id": native_firmware.CONTRACT_ID,
        "summary": native_firmware.summary(bundle),
        "bundle_sha256": native_firmware.sha256_bytes(bundle.raw),
        "bundle_version": native_firmware.MAJOR_VERSION,
        "component_count": len(bundle.components),
        "dependency_count": len(bundle.dependencies),
        "declared_external_payload_bytes": sum(
            item.external_payload_bytes for item in bundle.components
        ),
        "maximum_transaction_components": bundle.maximum_transaction_components,
        "outer_payload_sha256": artifact.payload_sha256,
        "activation_allowed": False,
        "activation_errors": list(errors),
        "validated_by": "independent_host_media_oracle",
        "pooleboot_enforced": False,
        "poolekernel_enforced": False,
        "live_firmware_inventory_observed": False,
        "vendor_payload_validated": False,
        "production_vendor_payload_included": False,
        "external_payload_bytes_embedded": False,
        "updater_driver_loaded": False,
        "capsule_submitted": False,
        "firmware_mutated": False,
        "physical_media_written": False,
        "synthetic_manifest_only": True,
        "authority_created": False,
    }


def policy_oracle(data: bytes, expected_version: int) -> dict[str, Any]:
    artifact = native_boot_artifact.parse_bound(
        data, native_boot_artifact.ROLE_POLICY_BUNDLE, expected_version
    )
    _, bundle = native_boot_artifact.parse_policy(data)
    initial = native_initial_system.parse(native_initial_system.canonical_bundle())
    native_policy.validate_initial_system(bundle, initial)
    errors = native_policy.activation_errors(
        bundle,
        native_policy.development_activation_context(
            bundle, outer_file_sha256=artifact.file_sha256
        ),
    )
    if not errors or errors[0] != "ppol_activation_outer_signature":
        raise KernelLoadError("PPOL1 development activation boundary changed")
    return {
        "contract_id": native_policy.CONTRACT_ID,
        "summary": native_policy.summary(bundle),
        "bundle_sha256": native_policy.sha256_bytes(bundle.raw),
        "bundle_version": native_policy.MAJOR_VERSION,
        "mode_count": len(bundle.modes),
        "capability_rule_count": len(bundle.capability_rules),
        "initial_system_sha256": bundle.initial_system_sha256,
        "outer_payload_sha256": artifact.payload_sha256,
        "activation_allowed": False,
        "activation_errors": list(errors),
        "validated_by": "independent_host_media_oracle",
        "initial_system_cross_bound": True,
        "safe_floor_validated": True,
        "recovery_floor_validated": True,
        "firmware_physical_presence_modeled": True,
        "firmware_separate_authority_modeled": True,
        "pooleboot_enforced": False,
        "poolekernel_enforced": False,
        "policy_decision_applied": False,
        "pooleglyph_executable_authority": False,
        "signature_verified": False,
        "state_mutated": False,
        "physical_media_written": False,
        "synthetic_policy_only": True,
        "authority_created": False,
    }


def canonical_manifest_bytes(
    kernel_data: bytes, artifact_files: dict[str, bytes] | None = None
) -> bytes:
    plan, _ = native_elf_loader.load(
        kernel_data,
        PHYSICAL_ORACLE_BASE,
        native_elf_loader.MIN_VIRTUAL_BASE,
    )
    files = canonical_artifact_files() if artifact_files is None else artifact_files
    if set(files) != {definition[4] for definition in ARTIFACT_DEFINITIONS}:
        raise KernelLoadError("PBASET1 artifact paths are incomplete or unexpected")
    artifacts = [
        native_system_manifest.Artifact(
            id="a_kernel",
            type="kernel",
            format="PKELF1",
            version=1,
            path=r"\EFI\POOLEOS\KERNEL.ELF",
            file_bytes=len(kernel_data),
            image_bytes=plan.image_size,
            sha256=native_system_manifest.sha256_bytes(kernel_data),
            entry_contract="PKENTRY1",
        )
    ]
    for role, artifact_id, kind, manifest_path, media_path, _ in ARTIFACT_DEFINITIONS:
        data = files[media_path]
        native_boot_artifact.parse_bound(data, role, 1)
        if role == native_boot_artifact.ROLE_INITIAL_SYSTEM:
            initial_system_oracle(data, 1)
        elif role == native_boot_artifact.ROLE_RECOVERY:
            recovery_oracle(data, 1)
        elif role == native_boot_artifact.ROLE_SYMBOLS:
            symbols_oracle(data, 1)
        elif role == native_boot_artifact.ROLE_MICROCODE:
            microcode_oracle(data, 1)
        elif role == native_boot_artifact.ROLE_FIRMWARE_MANIFEST:
            firmware_oracle(data, 1)
        elif role == native_boot_artifact.ROLE_POLICY_BUNDLE:
            policy_oracle(data, 1)
        artifacts.append(
            native_system_manifest.Artifact(
                id=artifact_id,
                type=kind,
                format=native_boot_artifact.CONTRACT_ID,
                version=1,
                path=manifest_path,
                file_bytes=len(data),
                image_bytes=0,
                sha256=native_system_manifest.sha256_bytes(data),
                entry_contract="none",
            )
        )
    return native_system_manifest.encode(
        artifacts,
        manifest_id="PSM-CYCLE107-SLOT1",
        slot=1,
        manifest_version=1,
        minimum_secure_version=1,
    )


def _profile_artifacts(
    manifest: native_system_manifest.SystemManifest,
) -> tuple[native_system_manifest.Artifact, ...]:
    expected = (
        (
            "a_kernel",
            "kernel",
            "PKELF1",
            r"\EFI\POOLEOS\KERNEL.ELF",
            "PKENTRY1",
        ),
        *tuple(
            (artifact_id, kind, native_boot_artifact.CONTRACT_ID, manifest_path, "none")
            for _, artifact_id, kind, manifest_path, _, _ in ARTIFACT_DEFINITIONS
        ),
    )
    if len(manifest.artifacts) != len(expected):
        raise KernelLoadError("PBASET1 requires exactly seven PSM1 artifacts")
    for index, (artifact, definition) in enumerate(zip(manifest.artifacts, expected, strict=True)):
        artifact_id, kind, artifact_format, path, entry_contract = definition
        if (
            artifact.id != artifact_id
            or artifact.type != kind
            or artifact.format != artifact_format
            or artifact.path != path
            or artifact.entry_contract != entry_contract
            or (index != 0 and artifact.image_bytes != 0)
        ):
            raise KernelLoadError("PBASET1 PSM1 role profile changed")
    return manifest.artifacts


def artifact_set_fnv1a64(
    artifacts: tuple[native_system_manifest.Artifact, ...],
) -> str:
    value = 0xCBF29CE484222325
    for role, artifact in zip(
        native_boot_artifact.ROLES, artifacts[1:], strict=True
    ):
        for byte in (
            struct.pack("<I", role)
            + struct.pack("<Q", artifact.file_bytes)
            + bytes.fromhex(artifact.sha256)
        ):
            value ^= byte
            value = (value * 0x00000100000001B3) & 0xFFFF_FFFF_FFFF_FFFF
    return f"{value:016X}"


def _cluster_count(byte_count: int) -> int:
    if byte_count <= 0:
        raise KernelLoadError("file payload is empty")
    return (byte_count + native_pooleboot.SECTOR_BYTES - 1) // native_pooleboot.SECTOR_BYTES


def _write_chain(
    image: bytearray,
    fat: bytearray,
    data_start_lba: int,
    first_cluster: int,
    payload: bytes,
) -> tuple[int, int]:
    count = _cluster_count(len(payload))
    last_cluster = first_cluster + count - 1
    for index, cluster in enumerate(range(first_cluster, last_cluster + 1)):
        next_cluster = native_pooleboot.FAT_END if cluster == last_cluster else cluster + 1
        struct.pack_into("<I", fat, cluster * 4, next_cluster)
        chunk = payload[
            index * native_pooleboot.SECTOR_BYTES : (index + 1) * native_pooleboot.SECTOR_BYTES
        ]
        native_pooleboot._write_cluster(image, data_start_lba, cluster, chunk)
    return count, last_cluster


def build_media_bytes(
    efi_data: bytes,
    config_data: bytes,
    manifest_data: bytes,
    kernel_data: bytes,
    artifact_files: dict[str, bytes] | None = None,
) -> bytes:
    files = canonical_artifact_files() if artifact_files is None else artifact_files
    try:
        config = native_boot_config.parse(config_data)
        selected = next(entry for entry in config.entries if entry.id == config.default_entry)
        manifest = native_system_manifest.parse(manifest_data)
        profile = _profile_artifacts(manifest)
        kernel = profile[0]
        if selected.manifest != r"\EFI\POOLEOS\SYSTEM_A.PBM":
            raise KernelLoadError("PBC1 selected manifest path is not canonical")
        if len(manifest_data) > selected.manifest_max_bytes:
            raise KernelLoadError("PSM1 exceeds the selected PBC1 manifest bound")
        if manifest.slot != selected.slot:
            raise KernelLoadError("PSM1 slot differs from the selected PBC1 slot")
        if kernel.path != r"\EFI\POOLEOS\KERNEL.ELF":
            raise KernelLoadError("PSM1 kernel path is not canonical")
        native_system_manifest.verify_file(kernel, kernel_data)
        if set(files) != {definition[4] for definition in ARTIFACT_DEFINITIONS}:
            raise KernelLoadError("PBASET1 media artifact paths are incomplete or unexpected")
        for index, definition in enumerate(ARTIFACT_DEFINITIONS, start=1):
            role, _, _, _, media_path, _ = definition
            artifact_data = files[media_path]
            native_system_manifest.verify_file(profile[index], artifact_data)
            native_boot_artifact.parse_bound(artifact_data, role, profile[index].version)
            if role == native_boot_artifact.ROLE_INITIAL_SYSTEM:
                initial_system_oracle(artifact_data, profile[index].version)
            elif role == native_boot_artifact.ROLE_RECOVERY:
                recovery_oracle(artifact_data, profile[index].version)
            elif role == native_boot_artifact.ROLE_SYMBOLS:
                symbols_oracle(artifact_data, profile[index].version)
            elif role == native_boot_artifact.ROLE_MICROCODE:
                microcode_oracle(artifact_data, profile[index].version)
            elif role == native_boot_artifact.ROLE_FIRMWARE_MANIFEST:
                firmware_oracle(artifact_data, profile[index].version)
            elif role == native_boot_artifact.ROLE_POLICY_BUNDLE:
                policy_oracle(artifact_data, profile[index].version)
        kernel_plan, _ = native_elf_loader.load(
            kernel_data,
            PHYSICAL_ORACLE_BASE,
            native_elf_loader.MIN_VIRTUAL_BASE,
        )
        if kernel_plan.image_size != kernel.image_bytes:
            raise KernelLoadError("PSM1 kernel image size differs from PKELF1")
        trust_files, trust_observed = canonical_trust_files(
            manifest_data, kernel_data, files
        )
        native_boot_trust.validate_development(
            trust_files[TRUST_POLICY_PATH],
            trust_files[TRUST_STATE_PATH],
            trust_observed,
        )
    except (
        native_boot_config.BootConfigError,
        native_system_manifest.ManifestError,
        native_elf_loader.ElfError,
        native_boot_artifact.BootArtifactError,
        native_initial_system.InitialSystemError,
        native_recovery.RecoveryError,
        native_symbols.SymbolError,
        native_microcode.MicrocodeError,
        native_firmware.FirmwareError,
        native_policy.PolicyError,
        native_boot_trust.BootTrustError,
        StopIteration,
    ) as error:
        raise KernelLoadError(f"PKLOAD6 input validation failed: {error}") from error
    if len(config_data) > native_boot_config.MAX_CONFIG_BYTES:
        raise KernelLoadError("PBC1 input exceeds its file bound")
    if len(manifest_data) > native_system_manifest.MAX_MANIFEST_BYTES:
        raise KernelLoadError("PSM1 input exceeds its file bound")
    if len(kernel_data) > native_elf_loader.MAX_FILE_BYTES:
        raise KernelLoadError("PKELF1 input exceeds its file bound")
    if kernel_plan.image_size > native_elf_loader.MAX_IMAGE_BYTES:
        raise KernelLoadError("PKELF1 image exceeds its allocation bound")
    if any(len(value) > native_boot_artifact.MAX_FILE_BYTES for value in files.values()):
        raise KernelLoadError("PBART1 input exceeds its file bound")
    if (
        len(trust_files[TRUST_POLICY_PATH]) != native_boot_trust.POLICY_BYTES
        or len(trust_files[TRUST_STATE_PATH]) != native_boot_trust.STATE_BYTES
    ):
        raise KernelLoadError("PBTRUST1 candidate sizes changed")

    image = bytearray(native_pooleboot.build_media_bytes(efi_data))
    fat_sectors, cluster_count = native_pooleboot._fat_sector_count()
    fat_offset = (
        native_pooleboot.ESP_START_LBA + native_pooleboot.FAT_RESERVED_SECTORS
    ) * native_pooleboot.SECTOR_BYTES
    fat_byte_count = fat_sectors * native_pooleboot.SECTOR_BYTES
    fat = bytearray(image[fat_offset : fat_offset + fat_byte_count])
    data_start_lba = (
        native_pooleboot.ESP_START_LBA
        + native_pooleboot.FAT_RESERVED_SECTORS
        + native_pooleboot.FAT_COUNT * fat_sectors
    )
    efi_clusters = _cluster_count(len(efi_data))
    pooleos_cluster = 5 + efi_clusters
    file_definitions = [
        (CONFIG_SHORT_NAME, config_data),
        (MANIFEST_SHORT_NAME, manifest_data),
        (KERNEL_SHORT_NAME, kernel_data),
        *[(definition[5], files[definition[4]]) for definition in ARTIFACT_DEFINITIONS],
        (TRUST_POLICY_SHORT_NAME, trust_files[TRUST_POLICY_PATH]),
        (TRUST_STATE_SHORT_NAME, trust_files[TRUST_STATE_PATH]),
    ]
    placements: list[tuple[bytes, bytes, int, int, int]] = []
    next_cluster = pooleos_cluster + 1
    for short_name, payload in file_definitions:
        count, last = _write_chain(image, fat, data_start_lba, next_cluster, payload)
        placements.append((short_name, payload, next_cluster, count, last))
        next_cluster = last + 1
    final_cluster = placements[-1][4]
    if final_cluster > cluster_count + 1:
        raise KernelLoadError("PKLOAD6 files do not fit in the deterministic ESP")
    struct.pack_into("<I", fat, pooleos_cluster * 4, native_pooleboot.FAT_END)

    efi_directory = bytearray(
        native_pooleboot._cluster_bytes(bytes(image), data_start_lba, 3)
    )
    efi_directory[96:128] = native_pooleboot._directory_entry(
        POOLEOS_DIRECTORY_NAME, 0x10, pooleos_cluster
    )
    native_pooleboot._write_cluster(image, data_start_lba, 3, efi_directory)

    pooleos_directory = bytearray(native_pooleboot.SECTOR_BYTES)
    pooleos_directory[0:32] = native_pooleboot._directory_entry(
        b".          ", 0x10, pooleos_cluster
    )
    pooleos_directory[32:64] = native_pooleboot._directory_entry(b"..         ", 0x10, 3)
    for index, (short_name, payload, first, _, _) in enumerate(placements):
        offset = 64 + index * 32
        pooleos_directory[offset : offset + 32] = native_pooleboot._directory_entry(
            short_name, 0x20, first, len(payload)
        )
    native_pooleboot._write_cluster(image, data_start_lba, pooleos_cluster, pooleos_directory)

    for index in range(native_pooleboot.FAT_COUNT):
        copy_offset = fat_offset + index * fat_byte_count
        image[copy_offset : copy_offset + fat_byte_count] = fat
    allocated_clusters = 4 + efi_clusters + sum(item[3] for item in placements)
    free_clusters = cluster_count - allocated_clusters
    next_free = final_cluster + 1 if final_cluster + 1 <= cluster_count + 1 else 0xFFFF_FFFF
    for sector in (1, 7):
        fsinfo_offset = (
            native_pooleboot.ESP_START_LBA + sector
        ) * native_pooleboot.SECTOR_BYTES
        struct.pack_into("<I", image, fsinfo_offset + 488, free_clusters)
        struct.pack_into("<I", image, fsinfo_offset + 492, next_free)
    return bytes(image)


def _file_bytes(
    data: bytes,
    fat: bytes,
    data_start_lba: int,
    entry: dict[str, int],
    cluster_count: int,
    maximum_size: int,
    label: str,
) -> tuple[bytes, list[int]]:
    size = entry.get("size", 0)
    if entry.get("attributes") != 0x20 or size <= 0 or size > maximum_size:
        raise KernelLoadError(f"{label} directory entry is invalid")
    chain = native_pooleboot._cluster_chain(fat, entry["cluster"], cluster_count)
    expected = _cluster_count(size)
    if len(chain) != expected:
        raise KernelLoadError(f"{label} FAT chain length differs from its file size")
    payload = b"".join(
        native_pooleboot._cluster_bytes(data, data_start_lba, cluster) for cluster in chain
    )[:size]
    return payload, chain


def inspect_media_bytes(data: bytes) -> dict[str, Any]:
    if len(data) != native_pooleboot.IMAGE_BYTES:
        raise KernelLoadError("PKLOAD6 image byte count is not canonical")
    try:
        primary = native_pooleboot._parse_gpt_header(
            data,
            native_pooleboot.PRIMARY_HEADER_LBA,
            native_pooleboot.BACKUP_HEADER_LBA,
            native_pooleboot.PRIMARY_ENTRIES_LBA,
        )
        backup = native_pooleboot._parse_gpt_header(
            data,
            native_pooleboot.BACKUP_HEADER_LBA,
            native_pooleboot.PRIMARY_HEADER_LBA,
            native_pooleboot.BACKUP_ENTRIES_LBA,
        )
        if primary["entries"] != backup["entries"]:
            raise KernelLoadError("primary and backup GPT entries differ")
        fat_sectors, cluster_count = native_pooleboot._fat_sector_count()
        fat_offset = (
            native_pooleboot.ESP_START_LBA + native_pooleboot.FAT_RESERVED_SECTORS
        ) * native_pooleboot.SECTOR_BYTES
        fat_bytes = fat_sectors * native_pooleboot.SECTOR_BYTES
        first_fat = native_pooleboot._slice(data, fat_offset, fat_bytes, "PKLOAD6 first FAT")
        second_fat = native_pooleboot._slice(
            data, fat_offset + fat_bytes, fat_bytes, "PKLOAD6 second FAT"
        )
        if first_fat != second_fat:
            raise KernelLoadError("PKLOAD6 FAT copies differ")
        data_start_lba = (
            native_pooleboot.ESP_START_LBA
            + native_pooleboot.FAT_RESERVED_SECTORS
            + native_pooleboot.FAT_COUNT * fat_sectors
        )
        root_entries = native_pooleboot._directory_entries(
            native_pooleboot._cluster_bytes(data, data_start_lba, 2)
        )
        if set(root_entries) != {native_pooleboot.VOLUME_LABEL, b"EFI        "}:
            raise KernelLoadError("PKLOAD6 root directory changed")
        efi_entries = native_pooleboot._directory_entries(
            native_pooleboot._cluster_bytes(data, data_start_lba, 3)
        )
        expected_efi_names = {
            b".          ",
            b"..         ",
            b"BOOT       ",
            POOLEOS_DIRECTORY_NAME,
        }
        if set(efi_entries) != expected_efi_names:
            raise KernelLoadError("PKLOAD6 EFI directory changed")
        boot_entries = native_pooleboot._directory_entries(
            native_pooleboot._cluster_bytes(data, data_start_lba, 4)
        )
        if set(boot_entries) != {b".          ", b"..         ", b"BOOTX64 EFI"}:
            raise KernelLoadError("PKLOAD6 EFI/BOOT directory changed")
        efi_data, efi_chain = _file_bytes(
            data,
            first_fat,
            data_start_lba,
            boot_entries[b"BOOTX64 EFI"],
            cluster_count,
            native_pooleboot.MAX_EFI_BYTES,
            "PooleBoot",
        )
        expected_pooleos_cluster = efi_chain[-1] + 1
        pooleos_entry = efi_entries[POOLEOS_DIRECTORY_NAME]
        if pooleos_entry != {
            "attributes": 0x10,
            "cluster": expected_pooleos_cluster,
            "size": 0,
        }:
            raise KernelLoadError("PKLOAD6 POOLEOS directory placement changed")
        pooleos_entries = native_pooleboot._directory_entries(
            native_pooleboot._cluster_bytes(data, data_start_lba, expected_pooleos_cluster)
        )
        if set(pooleos_entries) != {
            b".          ",
            b"..         ",
            CONFIG_SHORT_NAME,
            MANIFEST_SHORT_NAME,
            KERNEL_SHORT_NAME,
            *(definition[5] for definition in ARTIFACT_DEFINITIONS),
            TRUST_POLICY_SHORT_NAME,
            TRUST_STATE_SHORT_NAME,
        }:
            raise KernelLoadError("PKLOAD6 POOLEOS directory changed")
        config_data, config_chain = _file_bytes(
            data,
            first_fat,
            data_start_lba,
            pooleos_entries[CONFIG_SHORT_NAME],
            cluster_count,
            native_boot_config.MAX_CONFIG_BYTES,
            "PBC1",
        )
        manifest_data, manifest_chain = _file_bytes(
            data,
            first_fat,
            data_start_lba,
            pooleos_entries[MANIFEST_SHORT_NAME],
            cluster_count,
            native_system_manifest.MAX_MANIFEST_BYTES,
            "PSM1",
        )
        kernel_data, kernel_chain = _file_bytes(
            data,
            first_fat,
            data_start_lba,
            pooleos_entries[KERNEL_SHORT_NAME],
            cluster_count,
            native_elf_loader.MAX_FILE_BYTES,
            "PKELF1",
        )
        artifact_files: dict[str, bytes] = {}
        artifact_chains: dict[str, list[int]] = {}
        for role, _, _, _, media_path, short_name in ARTIFACT_DEFINITIONS:
            artifact_data, artifact_chain = _file_bytes(
                data,
                first_fat,
                data_start_lba,
                pooleos_entries[short_name],
                cluster_count,
                native_boot_artifact.MAX_FILE_BYTES,
                f"PBART1 role {role}",
            )
            artifact_files[media_path] = artifact_data
            artifact_chains[media_path] = artifact_chain
        trust_policy_data, trust_policy_chain = _file_bytes(
            data,
            first_fat,
            data_start_lba,
            pooleos_entries[TRUST_POLICY_SHORT_NAME],
            cluster_count,
            native_boot_trust.POLICY_BYTES,
            "PBTRUST1 policy candidate",
        )
        trust_state_data, trust_state_chain = _file_bytes(
            data,
            first_fat,
            data_start_lba,
            pooleos_entries[TRUST_STATE_SHORT_NAME],
            cluster_count,
            native_boot_trust.STATE_BYTES,
            "PBTRUST1 state candidate",
        )
        ordered_chains = [
            config_chain,
            manifest_chain,
            kernel_chain,
            *(artifact_chains[definition[4]] for definition in ARTIFACT_DEFINITIONS),
            trust_policy_chain,
            trust_state_chain,
        ]
        if ordered_chains[0][0] != expected_pooleos_cluster + 1 or any(
            current[0] != previous[-1] + 1
            for previous, current in zip(ordered_chains, ordered_chains[1:])
        ):
            raise KernelLoadError("PKLOAD6 file cluster placement changed")
        config = native_boot_config.parse(config_data)
        selected = next(entry for entry in config.entries if entry.id == config.default_entry)
        manifest = native_system_manifest.parse(manifest_data)
        profile = _profile_artifacts(manifest)
        if selected.manifest != r"\EFI\POOLEOS\SYSTEM_A.PBM":
            raise KernelLoadError("PBC1 selected manifest path changed")
        if len(manifest_data) > selected.manifest_max_bytes or manifest.slot != selected.slot:
            raise KernelLoadError("PSM1 selection binding changed")
        kernel_artifact = profile[0]
        if kernel_artifact.path != r"\EFI\POOLEOS\KERNEL.ELF":
            raise KernelLoadError("PSM1 kernel path changed")
        native_system_manifest.verify_file(kernel_artifact, kernel_data)
        for index, definition in enumerate(ARTIFACT_DEFINITIONS, start=1):
            role, _, _, _, media_path, _ = definition
            artifact_data = artifact_files[media_path]
            native_system_manifest.verify_file(profile[index], artifact_data)
            native_boot_artifact.parse_bound(
                artifact_data, role, profile[index].version
            )
            if role == native_boot_artifact.ROLE_INITIAL_SYSTEM:
                initial_system_oracle(artifact_data, profile[index].version)
            elif role == native_boot_artifact.ROLE_RECOVERY:
                recovery_oracle(artifact_data, profile[index].version)
            elif role == native_boot_artifact.ROLE_SYMBOLS:
                symbols_oracle(artifact_data, profile[index].version)
            elif role == native_boot_artifact.ROLE_MICROCODE:
                microcode_oracle(artifact_data, profile[index].version)
            elif role == native_boot_artifact.ROLE_FIRMWARE_MANIFEST:
                firmware_oracle(artifact_data, profile[index].version)
            elif role == native_boot_artifact.ROLE_POLICY_BUNDLE:
                policy_oracle(artifact_data, profile[index].version)
        expected_trust_files, trust_observed = canonical_trust_files(
            manifest_data, kernel_data, artifact_files
        )
        trust_summary = native_boot_trust.validate_development(
            trust_policy_data, trust_state_data, trust_observed
        )
        if trust_policy_data != expected_trust_files[TRUST_POLICY_PATH]:
            raise KernelLoadError("PBTRUST1 policy differs from the canonical candidate")
        if trust_state_data != expected_trust_files[TRUST_STATE_PATH]:
            raise KernelLoadError("PBTRUST1 state differs from the canonical candidate")
        kernel_plan, loaded = native_elf_loader.load(
            kernel_data,
            PHYSICAL_ORACLE_BASE,
            native_elf_loader.MIN_VIRTUAL_BASE,
        )
    except (
        native_pooleboot.PooleBootError,
        native_boot_config.BootConfigError,
        native_elf_loader.ElfError,
        native_system_manifest.ManifestError,
        native_boot_artifact.BootArtifactError,
        native_initial_system.InitialSystemError,
        native_recovery.RecoveryError,
        native_symbols.SymbolError,
        native_microcode.MicrocodeError,
        native_firmware.FirmwareError,
        native_policy.PolicyError,
        native_boot_trust.BootTrustError,
        StopIteration,
        KeyError,
        IndexError,
        struct.error,
    ) as error:
        raise KernelLoadError(f"PKLOAD6 media inspection failed: {error}") from error

    if config_data != canonical_config_bytes():
        raise KernelLoadError("PKLOAD6 config differs from the canonical development profile")
    if manifest_data != canonical_manifest_bytes(kernel_data, artifact_files):
        raise KernelLoadError("PKLOAD6 manifest differs from the canonical development profile")
    if kernel_plan.image_size != kernel_artifact.image_bytes:
        raise KernelLoadError("PSM1 kernel image size differs from PKELF1")
    expected = build_media_bytes(
        efi_data, config_data, manifest_data, kernel_data, artifact_files
    )
    if data != expected:
        raise KernelLoadError("PKLOAD6 media differs from its canonical reconstruction")
    base = native_pooleboot.inspect_media_bytes(native_pooleboot.build_media_bytes(efi_data))
    base["image"]["sha256"] = native_pooleboot.sha256_bytes(data)
    base["files"] = [
        {
            "path": native_pooleboot.FALLBACK_PATH,
            "sha256": native_pooleboot.sha256_bytes(efi_data),
            "byte_count": len(efi_data),
            "cluster_count": len(efi_chain),
        },
        {
            "path": CONFIG_PATH,
            "sha256": native_pooleboot.sha256_bytes(config_data),
            "byte_count": len(config_data),
            "cluster_count": len(config_chain),
        },
        {
            "path": MANIFEST_PATH,
            "sha256": native_pooleboot.sha256_bytes(manifest_data),
            "byte_count": len(manifest_data),
            "cluster_count": len(manifest_chain),
        },
        {
            "path": KERNEL_PATH,
            "sha256": native_pooleboot.sha256_bytes(kernel_data),
            "byte_count": len(kernel_data),
            "cluster_count": len(kernel_chain),
        },
        *[
            {
                "path": definition[4],
                "sha256": native_pooleboot.sha256_bytes(
                    artifact_files[definition[4]]
                ),
                "byte_count": len(artifact_files[definition[4]]),
                "cluster_count": len(artifact_chains[definition[4]]),
            }
            for definition in ARTIFACT_DEFINITIONS
        ],
        {
            "path": TRUST_POLICY_PATH,
            "sha256": native_pooleboot.sha256_bytes(trust_policy_data),
            "byte_count": len(trust_policy_data),
            "cluster_count": len(trust_policy_chain),
        },
        {
            "path": TRUST_STATE_PATH,
            "sha256": native_pooleboot.sha256_bytes(trust_state_data),
            "byte_count": len(trust_state_data),
            "cluster_count": len(trust_state_chain),
        },
    ]
    base["config"] = {
        "default_entry": config.default_entry,
        "default_entry_hash": f"{native_elf_loader.fnv1a64(config.default_entry.encode('ascii')):016X}",
        "entry_count": len(config.entries),
        "timeout_ms": config.timeout_ms,
        "boot_attempt_limit": config.boot_attempt_limit,
        "selected_slot": next(
            entry.slot for entry in config.entries if entry.id == config.default_entry
        ),
        "manifest_max_bytes": next(
            entry.manifest_max_bytes for entry in config.entries if entry.id == config.default_entry
        ),
        "selected_manifest_path": selected.manifest,
    }
    base["manifest"] = {
        **native_system_manifest.summary(manifest),
        "byte_count": len(manifest_data),
        "sha256": native_pooleboot.sha256_bytes(manifest_data),
        "manifest_id_hash": f"{native_elf_loader.fnv1a64(manifest.manifest_id.encode('ascii')):016X}",
        "kernel_sha256_prefix": kernel_artifact.sha256[:16],
    }
    base["kernel"] = {
        "plan": dataclasses.asdict(kernel_plan),
        "loaded_fnv1a64": f"{native_elf_loader.fnv1a64(loaded):016X}",
        "loaded_sha256": native_pooleboot.sha256_bytes(loaded),
    }
    artifact_summaries = []
    for index, definition in enumerate(ARTIFACT_DEFINITIONS, start=1):
        role, _, _, _, media_path, _ = definition
        artifact_data = artifact_files[media_path]
        page_count = (
            len(artifact_data) + native_elf_loader.PAGE_SIZE - 1
        ) // native_elf_loader.PAGE_SIZE
        loaded = artifact_data.ljust(page_count * native_elf_loader.PAGE_SIZE, b"\0")
        artifact_summaries.append(
            {
                **native_boot_artifact.summary(artifact_data),
                "path": media_path,
                "manifest_id": profile[index].id,
                "page_count": page_count,
                "loaded_fnv1a64": f"{native_elf_loader.fnv1a64(loaded):016X}",
            }
        )
    base["artifact_set"] = {
        "contract_id": native_boot_artifact.CONTRACT_ID,
        "artifact_count": len(artifact_summaries),
        "file_bytes": sum(item["file_bytes"] for item in artifact_summaries),
        "page_count": sum(item["page_count"] for item in artifact_summaries),
        "fnv1a64": artifact_set_fnv1a64(profile),
        "signatures_verified": False,
        "measured": False,
        "semantics_applied": False,
        "artifacts": artifact_summaries,
    }
    base["initial_system"] = initial_system_oracle(
        artifact_files[INITIAL_SYSTEM_PATH], profile[1].version
    )
    base["recovery"] = recovery_oracle(
        artifact_files[RECOVERY_PATH], profile[2].version
    )
    base["symbols"] = symbols_oracle(
        artifact_files[SYMBOLS_PATH], profile[3].version
    )
    base["microcode"] = microcode_oracle(
        artifact_files[MICROCODE_PATH], profile[4].version
    )
    base["firmware"] = firmware_oracle(
        artifact_files[FIRMWARE_PATH], profile[5].version
    )
    base["policy"] = policy_oracle(
        artifact_files[POLICY_PATH], profile[6].version
    )
    base["inner_set"] = native_inner_live.validate_development_set(
        [artifact_files[definition[4]] for definition in ARTIFACT_DEFINITIONS]
    )
    base["trust_state"] = trust_summary
    base["fat32"]["cluster_count"] = cluster_count
    return base


def validate_markers(markers: list[str]) -> dict[str, Any]:
    if len(markers) != len(MARKER_PATTERNS):
        raise KernelLoadError(
            f"expected {len(MARKER_PATTERNS)} PKLOAD6 markers, observed {len(markers)}"
        )
    matches = []
    for index, (pattern, marker) in enumerate(zip(MARKER_PATTERNS, markers, strict=True)):
        match = pattern.fullmatch(marker)
        if match is None:
            raise KernelLoadError(f"PKLOAD6 marker {index} violates its contract: {marker!r}")
        matches.append(match)

    config_bytes = int(matches[7].group(1))
    config_entries = int(matches[7].group(2))
    timeout_ms = int(matches[7].group(4))
    attempts = int(matches[7].group(5))
    slot = int(matches[7].group(6))
    manifest_max = int(matches[7].group(7))
    if not 1 <= config_bytes <= native_boot_config.MAX_CONFIG_BYTES:
        raise KernelLoadError("PKLOAD6 config marker exceeds its byte bound")
    if not 1 <= config_entries <= native_boot_config.MAX_ENTRIES:
        raise KernelLoadError("PKLOAD6 config marker exceeds its entry bound")
    if timeout_ms > native_boot_config.MAX_TIMEOUT_MS or not 1 <= attempts <= 8 or not 1 <= slot <= 4:
        raise KernelLoadError("PKLOAD6 config marker exceeds its policy bounds")
    if not 1 <= manifest_max <= native_boot_config.MAX_MANIFEST_BYTES:
        raise KernelLoadError("PKLOAD6 config marker exceeds its manifest bound")

    manifest_bytes = int(matches[8].group(1))
    artifact_count = int(matches[8].group(2))
    manifest_slot = int(matches[8].group(4))
    manifest_version = int(matches[8].group(5))
    minimum_secure_version = int(matches[8].group(6))
    if not 1 <= manifest_bytes <= min(
        manifest_max, native_system_manifest.MAX_MANIFEST_BYTES
    ):
        raise KernelLoadError("PKLOAD6 manifest marker exceeds its selected byte bound")
    if not 1 <= artifact_count <= native_system_manifest.MAX_ARTIFACTS:
        raise KernelLoadError("PKLOAD6 manifest marker exceeds its artifact bound")
    if manifest_slot != slot:
        raise KernelLoadError("PKLOAD6 manifest marker differs from the selected slot")
    if not 1 <= manifest_version or minimum_secure_version > manifest_version:
        raise KernelLoadError("PKLOAD6 manifest marker violates its version floor")

    kernel_version = int(matches[9].group(1))
    bound_file_bytes = int(matches[9].group(2))
    bound_image_bytes = int(matches[9].group(3))
    kernel_file_bytes = int(matches[10].group(1))
    image_bytes = int(matches[11].group(1))
    pages = int(matches[11].group(2))
    entry_offset = int(matches[11].group(3))
    relocations = int(matches[11].group(4))
    files_closed = int(matches[11].group(5))
    pools_freed = int(matches[11].group(6))
    if kernel_version < max(1, minimum_secure_version):
        raise KernelLoadError("PKLOAD6 kernel marker violates the manifest version floor")
    if bound_file_bytes != kernel_file_bytes or bound_image_bytes != image_bytes:
        raise KernelLoadError("PKLOAD6 kernel markers diverge from the manifest binding")
    if not 1 <= kernel_file_bytes <= native_elf_loader.MAX_FILE_BYTES:
        raise KernelLoadError("PKLOAD6 kernel marker exceeds its file bound")
    if not 1 <= image_bytes <= native_elf_loader.MAX_IMAGE_BYTES:
        raise KernelLoadError("PKLOAD6 kernel marker exceeds its image bound")
    if pages <= 0 or pages * native_elf_loader.PAGE_SIZE != image_bytes:
        raise KernelLoadError("PKLOAD6 marker page math is inconsistent")
    if not 0 <= entry_offset < image_bytes or relocations > native_elf_loader.MAX_RELOCATIONS:
        raise KernelLoadError("PKLOAD6 entry or relocation marker exceeds its bound")
    if (files_closed, pools_freed) != (12, 11):
        raise KernelLoadError("PKLOAD6 file and pool cleanup accounting diverges")

    artifact_contract = matches[12].group(1)
    loaded_artifact_count = int(matches[12].group(2))
    artifact_file_bytes = int(matches[12].group(3))
    artifact_pages = int(matches[12].group(4))
    artifact_fingerprint = matches[12].group(5)
    artifact_retained = int(matches[12].group(6))
    artifact_signatures = int(matches[12].group(7))
    artifact_measured = int(matches[12].group(8))
    if (
        artifact_contract != native_boot_artifact.CONTRACT_ID
        or loaded_artifact_count != len(native_boot_artifact.ROLES)
        or not loaded_artifact_count * native_boot_artifact.HEADER_BYTES
        < artifact_file_bytes
        <= loaded_artifact_count * native_boot_artifact.MAX_FILE_BYTES
        or artifact_pages < loaded_artifact_count
        or artifact_pages * native_elf_loader.PAGE_SIZE < artifact_file_bytes
        or artifact_retained != 1
        or artifact_signatures != 0
        or artifact_measured != 0
    ):
        raise KernelLoadError("PKLOAD6 PBART1 marker violates the unsigned retained profile")

    inner_proof = matches[13].group(1)
    inner_artifacts = int(matches[13].group(2))
    inner_parsers = int(matches[13].group(3))
    inner_bindings = int(matches[13].group(4))
    inner_denials = int(matches[13].group(5))
    inner_file_bytes = int(matches[13].group(6))
    inner_payload_bytes = int(matches[13].group(7))
    inner_sha256 = matches[13].group(8)
    inner_retained = int(matches[13].group(9))
    inner_authority_grants = int(matches[13].group(10))
    inner_actions = int(matches[13].group(11))
    inner_state_writes = int(matches[13].group(12))
    inner_hardware_observations = int(matches[13].group(13))
    if (
        inner_proof != native_inner_live.PROOF_ID
        or inner_artifacts != native_inner_live.ARTIFACT_COUNT
        or inner_parsers != native_inner_live.PARSER_COUNT
        or inner_bindings != native_inner_live.CROSS_BINDING_COUNT
        or inner_denials != native_inner_live.DEVELOPMENT_DENIAL_COUNT
        or inner_file_bytes != artifact_file_bytes
        or inner_payload_bytes
        != inner_file_bytes
        - native_inner_live.ARTIFACT_COUNT * native_boot_artifact.HEADER_BYTES
        or inner_retained != 1
        or inner_authority_grants != 0
        or inner_actions != 0
        or inner_state_writes != 0
        or inner_hardware_observations != 0
    ):
        raise KernelLoadError("PKLOAD6 live inner-set marker violates its fail-closed profile")

    trust_contract = matches[14].group(1)
    trust_policy_bytes = int(matches[14].group(2))
    trust_state_bytes = int(matches[14].group(3))
    trust_bindings = int(matches[14].group(4))
    trust_denials = int(matches[14].group(5))
    trust_denial = matches[14].group(6)
    trust_policy_sha256 = matches[14].group(7)
    trust_state_sha256 = matches[14].group(8)
    trust_signatures = int(matches[14].group(12))
    trust_authority = int(matches[14].group(13))
    trust_writes = int(matches[14].group(14))
    if (
        trust_contract != native_boot_trust.CONTRACT_ID
        or trust_policy_bytes != native_boot_trust.POLICY_BYTES
        or trust_state_bytes != native_boot_trust.STATE_BYTES
        or trust_bindings != 14
        or trust_denials != 1
        or trust_denial != "pbtrust_policy_unsigned"
        or trust_signatures != 0
        or trust_authority != 0
        or trust_writes != 0
    ):
        raise KernelLoadError("PKLOAD6 trust-state marker violates its fail-closed profile")

    config_table_count = int(matches[5].group(1))
    width = int(matches[15].group(1))
    height = int(matches[15].group(2))
    stride = int(matches[15].group(3))
    if config_table_count > 256:
        raise KernelLoadError("configuration-table marker exceeds its bound")
    if width < 320 or height < 200 or stride < width or stride > 16_384:
        raise KernelLoadError("GOP marker geometry is outside its bound")

    mapping_contract = matches[17].group(1)
    mappings = int(matches[17].group(2))
    mapped_pages = int(matches[17].group(3))
    read_only_pages = int(matches[17].group(4))
    read_execute_pages = int(matches[17].group(5))
    read_write_pages = int(matches[17].group(6))
    writable_executable_pages = int(matches[17].group(7))
    pml4_index = int(matches[17].group(8))
    pdpt_index = int(matches[17].group(9))
    page_directory_index = int(matches[17].group(10))
    first_page_table_index = int(matches[17].group(11))
    leaf_fingerprint = matches[17].group(12)
    if mapping_contract != native_kernel_map.RETAINED_CONTRACT_ID or mappings != 4:
        raise KernelLoadError("PKLOAD6 PKMAP2 contract or mapping count diverges")
    if mapped_pages != pages or (
        read_only_pages
        + read_execute_pages
        + read_write_pages
        + writable_executable_pages
        != pages
    ):
        raise KernelLoadError("PKLOAD6 PKMAP2 kernel page accounting diverges")
    if writable_executable_pages != 0:
        raise KernelLoadError("PKLOAD6 PKMAP2 marker reports writable-executable pages")
    if (pml4_index, pdpt_index, page_directory_index, first_page_table_index) != (
        511,
        510,
        0,
        0,
    ):
        raise KernelLoadError("PKLOAD6 PKMAP2 indices diverge from the bounded window")

    table_pages = int(matches[18].group(1))
    active_kernel_pages = int(matches[18].group(2))
    physical_address_bits = int(matches[18].group(3))
    mapped_fnv1a64 = matches[18].group(4)
    cache_signature = int(matches[18].group(5), 16)
    first_page_bytes = int(matches[18].group(6))
    last_page_bytes = int(matches[18].group(7))
    if table_pages != native_kernel_map.TABLE_PAGE_COUNT or active_kernel_pages != pages:
        raise KernelLoadError("PKLOAD6 PKMAP2 active page accounting diverges")
    if not 36 <= physical_address_bits <= 52:
        raise KernelLoadError("PKLOAD6 PKMAP2 physical-address width is unsupported")
    if mapped_fnv1a64 != matches[11].group(7):
        raise KernelLoadError("PKLOAD6 PKMAP2 higher-half alias hash diverges")
    valid_page_sizes = {native_kernel_map.PAGE_SIZE, native_kernel_map.WINDOW_BYTES, 1024 * 1024 * 1024}
    if (
        not 0 <= cache_signature <= 0x3F
        or first_page_bytes not in valid_page_sizes
        or last_page_bytes not in valid_page_sizes
    ):
        raise KernelLoadError("PKLOAD6 PKMAP2 framebuffer translation summary is invalid")

    retained_table_pages = int(matches[19].group(1))
    stack_pages = int(matches[19].group(2))
    handoff_pages = int(matches[19].group(3))
    guard_pages = int(matches[19].group(4))
    total_pages = int(matches[19].group(5))
    stack_pt = int(matches[19].group(6))
    handoff_pt = int(matches[19].group(7))
    kernel_physical = int(matches[19].group(8), 16)
    root_physical = int(matches[19].group(9), 16)
    stack_physical = int(matches[19].group(10), 16)
    stack_top = int(matches[19].group(11), 16)
    handoff_physical = int(matches[19].group(12), 16)
    handoff_virtual = int(matches[19].group(13), 16)
    retained_fingerprint = matches[19].group(14)
    firmware_calls_while_active = int(matches[19].group(15))
    if (
        retained_table_pages != native_kernel_map.TABLE_PAGE_COUNT
        or stack_pages != native_kernel_map.STACK_PAGE_COUNT
        or handoff_pages != native_kernel_map.HANDOFF_PAGE_COUNT
        or guard_pages != 2
        or total_pages != pages + stack_pages + handoff_pages
        or stack_pt != native_kernel_map.STACK_FIRST_PAGE
        or handoff_pt != native_kernel_map.HANDOFF_FIRST_PAGE
        or firmware_calls_while_active != 0
    ):
        raise KernelLoadError("PKLOAD6 PKMAP2 retained page accounting diverges")
    maximum_physical = 1 << physical_address_bits
    retained_ranges = (
        (kernel_physical, image_bytes),
        (root_physical, retained_table_pages * native_kernel_map.PAGE_SIZE),
        (stack_physical, stack_pages * native_kernel_map.PAGE_SIZE),
        (handoff_physical, handoff_pages * native_kernel_map.PAGE_SIZE),
    )
    for start, byte_count in retained_ranges:
        if start <= 0 or start % native_kernel_map.PAGE_SIZE or start + byte_count > maximum_physical:
            raise KernelLoadError("PKLOAD6 retained physical range is invalid")
    for index, (start, byte_count) in enumerate(retained_ranges):
        end = start + byte_count
        for other_start, other_size in retained_ranges[index + 1 :]:
            if start < other_start + other_size and other_start < end:
                raise KernelLoadError("PKLOAD6 retained physical ranges overlap")
    if stack_top % 16 or handoff_virtual % native_kernel_map.PAGE_SIZE:
        raise KernelLoadError("PKLOAD6 retained virtual state is invalid")

    pbp1_bytes = int(matches[20].group(1))
    pbp1_records = int(matches[20].group(2))
    pbp1_memory_entries = int(matches[20].group(3))
    pbp1_framebuffer = int(matches[20].group(4))
    pbp1_artifacts = int(matches[20].group(5))
    pbp1_descriptor_bytes = int(matches[20].group(6))
    pbp1_exit_attempts = int(matches[20].group(7))
    pbp1_unchanged = int(matches[20].group(10))
    if (
        not 1 <= pbp1_bytes <= 1024 * 1024
        or pbp1_records not in {3, 4}
        or not 1 <= pbp1_memory_entries <= 16_384
        or pbp1_framebuffer != 1
        or pbp1_artifacts != 1 + loaded_artifact_count
        or not 40 <= pbp1_descriptor_bytes <= 256
        or pbp1_descriptor_bytes % 8
        or not 1 <= pbp1_exit_attempts <= native_boot_exit.MAX_EXIT_ATTEMPTS
        or pbp1_unchanged != 1
    ):
        raise KernelLoadError("PKLOAD6 PBP1 marker violates its exited-development profile")

    try:
        boot_exit = native_boot_exit.validate_live_markers(
            markers[21], markers[22], markers[23], markers[24]
        )
    except native_boot_exit.BootExitError as error:
        raise KernelLoadError(str(error)) from error
    if (
        boot_exit["attempt_count"] != pbp1_exit_attempts
        or boot_exit["descriptor_size"] != pbp1_descriptor_bytes
        or boot_exit["kernel_page_count"] != pages
        or boot_exit["artifact_page_count"] != artifact_pages
    ):
        raise KernelLoadError("PKLOAD6 PBP1 and PBEXIT1 markers diverge")
    return {
        "marker_count": len(markers),
        "ordered_contract_match": True,
        "uefi_revision": int(matches[1].group(1), 16),
        "config_table_count": config_table_count,
        "boot_config": {
            "byte_count": config_bytes,
            "entry_count": config_entries,
            "default_entry_hash": matches[7].group(3),
            "timeout_ms": timeout_ms,
            "boot_attempt_limit": attempts,
            "selected_slot": slot,
            "manifest_max_bytes": manifest_max,
        },
        "manifest": {
            "byte_count": manifest_bytes,
            "artifact_count": artifact_count,
            "manifest_id_hash": matches[8].group(3),
            "slot": manifest_slot,
            "manifest_version": manifest_version,
            "minimum_secure_version": minimum_secure_version,
            "kernel_version": kernel_version,
            "kernel_file_byte_count": bound_file_bytes,
            "kernel_image_byte_count": bound_image_bytes,
            "kernel_sha256_prefix": matches[9].group(4),
        },
        "kernel": {
            "file_byte_count": kernel_file_bytes,
            "image_byte_count": image_bytes,
            "page_count": pages,
            "entry_offset": entry_offset,
            "relocation_count": relocations,
            "loaded_fnv1a64": matches[11].group(7),
            "file_handles_closed": files_closed,
            "file_pools_freed": pools_freed,
            "pages_retained": True,
            "resources_released": False,
        },
        "artifact_set": {
            "contract_id": artifact_contract,
            "artifact_count": loaded_artifact_count,
            "file_bytes": artifact_file_bytes,
            "page_count": artifact_pages,
            "fnv1a64": artifact_fingerprint,
            "pages_retained": bool(artifact_retained),
            "signatures_verified": bool(artifact_signatures),
            "measured": bool(artifact_measured),
            "semantics_applied": False,
        },
        "inner_set": {
            "proof_id": inner_proof,
            "artifact_count": inner_artifacts,
            "parser_count": inner_parsers,
            "cross_binding_count": inner_bindings,
            "development_denial_count": inner_denials,
            "file_bytes": inner_file_bytes,
            "payload_bytes": inner_payload_bytes,
            "retained_set_sha256": inner_sha256,
            "exact_retained_bytes": bool(inner_retained),
            "authority_grants": inner_authority_grants,
            "actions_authorized": inner_actions,
            "state_writes": inner_state_writes,
            "hardware_observations": inner_hardware_observations,
        },
        "trust_state": {
            "contract_id": trust_contract,
            "policy_bytes": trust_policy_bytes,
            "state_bytes": trust_state_bytes,
            "binding_count": trust_bindings,
            "denial_count": trust_denials,
            "denial": trust_denial,
            "policy_sha256": trust_policy_sha256,
            "state_sha256": trust_state_sha256,
            "state_source": "esp_candidate_not_persistent_authority",
            "signature_verifications": trust_signatures,
            "authority_grants": trust_authority,
            "state_writes": trust_writes,
            "state_authenticated": False,
            "state_monotonic": False,
        },
        "pbp1": {
            "byte_count": pbp1_bytes,
            "record_count": pbp1_records,
            "memory_entry_count": pbp1_memory_entries,
            "framebuffer_present": pbp1_framebuffer,
            "artifact_count": pbp1_artifacts,
            "descriptor_bytes": pbp1_descriptor_bytes,
            "exit_attempts": pbp1_exit_attempts,
            "message_crc32": matches[20].group(8),
            "fnv1a64": matches[20].group(9),
            "pre_exit": False,
            "boot_services_exited": True,
            "development_mode_only": True,
            "temporary_pools_released": False,
            "bytes_unchanged": True,
        },
        "kernel_map": {
            "contract_id": mapping_contract,
            "mapping_count": mappings,
            "mapped_page_count": mapped_pages,
            "read_only_page_count": read_only_pages,
            "read_execute_page_count": read_execute_pages,
            "read_write_page_count": read_write_pages,
            "writable_executable_page_count": writable_executable_pages,
            "pml4_index": pml4_index,
            "pdpt_index": pdpt_index,
            "page_directory_index": page_directory_index,
            "first_page_table_index": first_page_table_index,
            "leaf_fingerprint": leaf_fingerprint,
            "table_page_count": table_pages,
            "physical_address_bits": physical_address_bits,
            "mapped_fnv1a64": mapped_fnv1a64,
            "framebuffer_preserved": True,
            "framebuffer_cache_signature": f"{cache_signature:02X}",
            "framebuffer_first_page_bytes": first_page_bytes,
            "framebuffer_last_page_bytes": last_page_bytes,
            "original_cr3_restored": True,
            "tables_retained": True,
            "firmware_calls_while_active": firmware_calls_while_active,
            "retained": {
                "table_page_count": retained_table_pages,
                "stack_page_count": stack_pages,
                "handoff_page_count": handoff_pages,
                "guard_page_count": guard_pages,
                "total_mapped_page_count": total_pages,
                "stack_first_page_table_index": stack_pt,
                "handoff_first_page_table_index": handoff_pt,
                "kernel_physical_base": kernel_physical,
                "page_table_root_physical": root_physical,
                "stack_physical_base": stack_physical,
                "stack_top_virtual": stack_top,
                "handoff_physical_base": handoff_physical,
                "handoff_virtual_base": handoff_virtual,
                "retained_leaf_fingerprint": retained_fingerprint,
            },
        },
        "gop": {
            "width": width,
            "height": height,
            "stride": stride,
            "mode": int(matches[15].group(4)),
            "format": matches[15].group(5),
        },
        "memory_map": {
            "byte_count": boot_exit["map_byte_count"],
            "descriptor_bytes": boot_exit["descriptor_size"],
            "descriptor_count": boot_exit["descriptor_count"],
        },
        "boot_exit": boot_exit,
    }


def validate_oracle_binding(
    marker_summary: dict[str, Any],
    media_inspection: dict[str, Any],
    pbp1_transcript: dict[str, Any] | None = None,
) -> None:
    config = marker_summary["boot_config"]
    media_config = media_inspection["config"]
    config_file = media_inspection["files"][1]
    if (
        config["byte_count"] != config_file["byte_count"]
        or config["entry_count"] != media_config["entry_count"]
        or config["default_entry_hash"] != media_config["default_entry_hash"]
        or config["timeout_ms"] != media_config["timeout_ms"]
        or config["boot_attempt_limit"] != media_config["boot_attempt_limit"]
        or config["selected_slot"] != media_config["selected_slot"]
        or config["manifest_max_bytes"] != media_config["manifest_max_bytes"]
    ):
        raise KernelLoadError("firmware PBC1 markers diverge from the independent media oracle")
    manifest = marker_summary["manifest"]
    media_manifest = media_inspection["manifest"]
    manifest_file = media_inspection["files"][2]
    kernel_artifact = next(
        item for item in media_manifest["artifacts"] if item["type"] == "kernel"
    )
    if (
        manifest["byte_count"] != manifest_file["byte_count"]
        or manifest["artifact_count"] != media_manifest["artifact_count"]
        or manifest["manifest_id_hash"] != media_manifest["manifest_id_hash"]
        or manifest["slot"] != media_manifest["slot"]
        or manifest["manifest_version"] != media_manifest["manifest_version"]
        or manifest["minimum_secure_version"]
        != media_manifest["minimum_secure_version"]
        or manifest["kernel_version"] != kernel_artifact["version"]
        or manifest["kernel_file_byte_count"] != kernel_artifact["file_bytes"]
        or manifest["kernel_image_byte_count"] != kernel_artifact["image_bytes"]
        or manifest["kernel_sha256_prefix"] != kernel_artifact["sha256"][:16]
    ):
        raise KernelLoadError("firmware PSM1 markers diverge from the independent media oracle")
    kernel = marker_summary["kernel"]
    media_kernel = media_inspection["kernel"]
    kernel_file = media_inspection["files"][3]
    plan = media_kernel["plan"]
    if (
        kernel["file_byte_count"] != kernel_file["byte_count"]
        or kernel["image_byte_count"] != plan["image_size"]
        or kernel["entry_offset"] != plan["entry_offset"]
        or kernel["relocation_count"] != plan["relocation_count"]
        or kernel["loaded_fnv1a64"] != media_kernel["loaded_fnv1a64"]
    ):
        raise KernelLoadError("firmware PKELF1 markers diverge from the independent media oracle")
    artifact_set = marker_summary["artifact_set"]
    media_artifact_set = media_inspection["artifact_set"]
    if (
        artifact_set["contract_id"] != media_artifact_set["contract_id"]
        or artifact_set["artifact_count"] != media_artifact_set["artifact_count"]
        or artifact_set["file_bytes"] != media_artifact_set["file_bytes"]
        or artifact_set["page_count"] != media_artifact_set["page_count"]
        or artifact_set["fnv1a64"] != media_artifact_set["fnv1a64"]
        or artifact_set["pages_retained"] is not True
        or artifact_set["signatures_verified"] is not False
        or artifact_set["measured"] is not False
        or artifact_set["semantics_applied"] is not False
    ):
        raise KernelLoadError("firmware PBART1 markers diverge from the independent media oracle")
    inner_set = marker_summary["inner_set"]
    media_inner_set = media_inspection.get("inner_set", {})
    if (
        inner_set["proof_id"] != media_inner_set.get("proof_id")
        or inner_set["artifact_count"] != media_inner_set.get("artifact_count")
        or inner_set["parser_count"] != media_inner_set.get("parser_count")
        or inner_set["cross_binding_count"]
        != media_inner_set.get("cross_binding_count")
        or inner_set["development_denial_count"]
        != media_inner_set.get("development_denial_count")
        or inner_set["file_bytes"] != media_inner_set.get("file_bytes")
        or inner_set["payload_bytes"] != media_inner_set.get("payload_bytes")
        or inner_set["retained_set_sha256"]
        != media_inner_set.get("retained_set_sha256")
        or inner_set["exact_retained_bytes"] is not True
        or media_inner_set.get("exact_retained_bytes") is not True
        or media_inner_set.get("policy_payload_digests_bound") is not True
        or media_inner_set.get("initial_routes_cross_bound") is not True
        or inner_set["authority_grants"] != 0
        or inner_set["actions_authorized"] != 0
        or inner_set["state_writes"] != 0
        or inner_set["hardware_observations"] != 0
        or media_inner_set.get("development_denials")
        != list(native_inner_live.EXPECTED_DENIALS)
    ):
        raise KernelLoadError(
            "firmware live inner-set marker diverges from the independent retained-byte oracle"
        )
    trust_state = marker_summary["trust_state"]
    media_trust_state = media_inspection.get("trust_state", {})
    if (
        trust_state["contract_id"] != media_trust_state.get("contract_id")
        or trust_state["policy_bytes"] != media_trust_state.get("policy_bytes")
        or trust_state["state_bytes"] != media_trust_state.get("state_bytes")
        or trust_state["binding_count"] != media_trust_state.get("binding_count")
        or trust_state["denial_count"] != media_trust_state.get("denial_count")
        or trust_state["denial"] != media_trust_state.get("denial")
        or trust_state["policy_sha256"] != media_trust_state.get("policy_sha256")
        or trust_state["state_sha256"] != media_trust_state.get("state_sha256")
        or trust_state["signature_verifications"] != 0
        or trust_state["authority_grants"] != 0
        or trust_state["state_writes"] != 0
        or media_trust_state.get("state_source")
        != "esp_candidate_not_persistent_authority"
        or media_trust_state.get("state_authenticated") is not False
        or media_trust_state.get("state_monotonic") is not False
        or media_trust_state.get("state_backend_writable") is not False
    ):
        raise KernelLoadError(
            "firmware PBTRUST1 marker diverges from the independent trust-state oracle"
        )
    initial_system = media_inspection.get("initial_system", {})
    if (
        initial_system.get("contract_id") != native_initial_system.CONTRACT_ID
        or initial_system.get("validated_by") != "independent_host_media_oracle"
        or initial_system.get("activation_allowed") is not False
        or initial_system.get("pooleboot_enforced") is not False
        or initial_system.get("poolekernel_enforced") is not False
        or not initial_system.get("activation_errors")
        or initial_system["activation_errors"][0]
        != "pinit_activation_outer_signature_verified"
    ):
        raise KernelLoadError("PINIT1 oracle or activation boundary changed")
    recovery = media_inspection.get("recovery", {})
    if (
        recovery.get("contract_id") != native_recovery.CONTRACT_ID
        or recovery.get("validated_by") != "independent_host_media_oracle"
        or recovery.get("activation_allowed") is not False
        or recovery.get("pooleboot_enforced") is not False
        or recovery.get("poolekernel_enforced") is not False
        or recovery.get("recovery_executed") is not False
        or not recovery.get("activation_errors")
        or recovery["activation_errors"][0] != "prec_activation_outer_signature"
    ):
        raise KernelLoadError("PREC1 oracle or activation boundary changed")
    symbols = media_inspection.get("symbols", {})
    if (
        symbols.get("contract_id") != native_symbols.CONTRACT_ID
        or symbols.get("validated_by") != "independent_host_media_oracle"
        or symbols.get("activation_allowed") is not False
        or symbols.get("pooleboot_enforced") is not False
        or symbols.get("poolekernel_enforced") is not False
        or symbols.get("symbols_consumed") is not False
        or symbols.get("runtime_addresses_disclosed") is not False
        or symbols.get("full_debug_file_on_media") is not False
        or symbols.get("authority_created") is not False
        or not symbols.get("activation_errors")
        or symbols["activation_errors"][0] != "psym_activation_outer_signature"
    ):
        raise KernelLoadError("PSYM1 oracle or activation boundary changed")
    microcode = media_inspection.get("microcode", {})
    if (
        microcode.get("contract_id") != native_microcode.CONTRACT_ID
        or microcode.get("validated_by") != "independent_host_media_oracle"
        or microcode.get("activation_allowed") is not False
        or microcode.get("pooleboot_enforced") is not False
        or microcode.get("poolekernel_enforced") is not False
        or microcode.get("vendor_container_validated") is not False
        or microcode.get("production_vendor_payload_included") is not False
        or microcode.get("privileged_revision_observed") is not False
        or microcode.get("microcode_applied") is not False
        or microcode.get("firmware_mutated") is not False
        or microcode.get("physical_media_written") is not False
        or microcode.get("synthetic_payloads_only") is not True
        or microcode.get("authority_created") is not False
        or not microcode.get("activation_errors")
        or microcode["activation_errors"][0] != "pmcu_activation_outer_signature"
    ):
        raise KernelLoadError("PMCU1 oracle or activation boundary changed")
    firmware = media_inspection.get("firmware", {})
    if (
        firmware.get("contract_id") != native_firmware.CONTRACT_ID
        or firmware.get("validated_by") != "independent_host_media_oracle"
        or firmware.get("activation_allowed") is not False
        or firmware.get("pooleboot_enforced") is not False
        or firmware.get("poolekernel_enforced") is not False
        or firmware.get("live_firmware_inventory_observed") is not False
        or firmware.get("vendor_payload_validated") is not False
        or firmware.get("production_vendor_payload_included") is not False
        or firmware.get("external_payload_bytes_embedded") is not False
        or firmware.get("updater_driver_loaded") is not False
        or firmware.get("capsule_submitted") is not False
        or firmware.get("firmware_mutated") is not False
        or firmware.get("physical_media_written") is not False
        or firmware.get("synthetic_manifest_only") is not True
        or firmware.get("authority_created") is not False
        or not firmware.get("activation_errors")
        or firmware["activation_errors"][0] != "pfwm_activation_outer_signature"
    ):
        raise KernelLoadError("PFWM1 oracle or activation boundary changed")
    policy = media_inspection.get("policy", {})
    if (
        policy.get("contract_id") != native_policy.CONTRACT_ID
        or policy.get("validated_by") != "independent_host_media_oracle"
        or policy.get("activation_allowed") is not False
        or policy.get("initial_system_cross_bound") is not True
        or policy.get("safe_floor_validated") is not True
        or policy.get("recovery_floor_validated") is not True
        or policy.get("firmware_physical_presence_modeled") is not True
        or policy.get("firmware_separate_authority_modeled") is not True
        or policy.get("pooleboot_enforced") is not False
        or policy.get("poolekernel_enforced") is not False
        or policy.get("policy_decision_applied") is not False
        or policy.get("pooleglyph_executable_authority") is not False
        or policy.get("signature_verified") is not False
        or policy.get("state_mutated") is not False
        or policy.get("physical_media_written") is not False
        or policy.get("synthetic_policy_only") is not True
        or policy.get("authority_created") is not False
        or not policy.get("activation_errors")
        or policy["activation_errors"][0] != "ppol_activation_outer_signature"
    ):
        raise KernelLoadError("PPOL1 oracle or activation boundary changed")
    kernel_map = marker_summary["kernel_map"]
    expected_map = native_kernel_map.marker_expectation(
        plan, kernel_map["physical_address_bits"]
    )
    if kernel_map["contract_id"] != native_kernel_map.RETAINED_CONTRACT_ID:
        raise KernelLoadError("firmware PKMAP2 contract identifier diverges")
    for field in (
        "mapping_count",
        "mapped_page_count",
        "read_only_page_count",
        "read_execute_page_count",
        "read_write_page_count",
        "writable_executable_page_count",
        "pml4_index",
        "pdpt_index",
        "page_directory_index",
        "first_page_table_index",
        "leaf_fingerprint",
    ):
        if kernel_map[field] != expected_map[field]:
            raise KernelLoadError(
                f"firmware PKMAP2 kernel field {field} diverges from the independent page oracle"
            )
    if kernel_map["mapped_fnv1a64"] != media_kernel["loaded_fnv1a64"]:
        raise KernelLoadError("firmware PKMAP2 alias hash diverges from the loaded-image oracle")
    retained = kernel_map["retained"]
    expected_retained = native_kernel_map.retained_marker_expectation(
        plan,
        kernel_map["physical_address_bits"],
        kernel_physical_base=retained["kernel_physical_base"],
        stack_physical_base=retained["stack_physical_base"],
        handoff_physical_base=retained["handoff_physical_base"],
        table_base=retained["page_table_root_physical"],
    )
    for field in (
        "table_page_count",
        "stack_page_count",
        "handoff_page_count",
        "guard_page_count",
        "total_mapped_page_count",
        "stack_first_page_table_index",
        "handoff_first_page_table_index",
        "kernel_physical_base",
        "page_table_root_physical",
        "stack_physical_base",
        "stack_top_virtual",
        "handoff_physical_base",
        "handoff_virtual_base",
        "retained_leaf_fingerprint",
    ):
        if retained[field] != expected_retained[field]:
            raise KernelLoadError(
                f"firmware PKMAP2 retained field {field} diverges from the independent page oracle"
            )
    if pbp1_transcript is None:
        raise KernelLoadError("live PBP1 transcript oracle is missing")
    try:
        native_live_boot_handoff.validate_oracle_binding(
            pbp1_transcript,
            marker_summary,
            media_inspection,
        )
    except native_live_boot_handoff.LiveHandoffError as error:
        raise KernelLoadError(str(error)) from error


def expected_claims() -> dict[str, bool]:
    return {
        **{name: True for name in TRUE_CLAIMS},
        **{name: False for name in FALSE_CLAIMS},
    }


def validate_claims(claims: dict[str, Any]) -> None:
    expected = expected_claims()
    if claims != expected:
        raise KernelLoadError("PKLOAD6 claim set contains an omission or overreach")


def canonical_json_bytes(value: object) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True) + "\n").encode(
        "ascii"
    )


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest().upper()


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(value, dict):
        raise KernelLoadError(f"JSON root must be an object: {path.name}")
    return value


def file_binding(root: Path, relative_path: str) -> dict[str, Any]:
    path = (root / relative_path).resolve()
    try:
        path.relative_to(root.resolve())
    except ValueError as error:
        raise KernelLoadError(f"binding escapes repository root: {relative_path}") from error
    data = path.read_bytes()
    return {
        "path": relative_path.replace("\\", "/"),
        "sha256": sha256_bytes(data),
        "byte_count": len(data),
    }


def binding_matches(binding: Any, root: Path, expected_path: str) -> bool:
    if not isinstance(binding, dict) or binding.get("path") != expected_path:
        return False
    try:
        return binding == file_binding(root, expected_path)
    except (OSError, KernelLoadError):
        return False


def _schema_errors(value: dict[str, Any], root: Path, schema_relative: str) -> list[str]:
    schema = read_json(root / schema_relative)
    return [f"schema {item.path}: {item.message}" for item in validate_json(value, schema)]


def contract_errors(contract: dict[str, Any], root: Path) -> list[str]:
    errors = _schema_errors(contract, root, CONTRACT_SCHEMA_RELATIVE)
    if contract.get("phase_mapping") != ["N5.1", "N5.4", "N5.5", "N5.6", "N5.8", "N5.9"]:
        errors.append("PKLOAD6 phase mapping changed")
    if contract.get("required_negative_controls") != list(NEGATIVE_CONTROL_IDS):
        errors.append("PKLOAD6 negative-control register changed")
    if contract.get("required_marker_count") != len(MARKER_PATTERNS):
        errors.append("PKLOAD6 marker count changed")
    media = contract.get("media", {})
    if (
        media.get("config_path") != CONFIG_PATH
        or media.get("manifest_path") != MANIFEST_PATH
        or media.get("kernel_path") != KERNEL_PATH
        or media.get("artifact_paths")
        != [definition[4] for definition in ARTIFACT_DEFINITIONS]
        or media.get("trust_policy_path") != TRUST_POLICY_PATH
        or media.get("trust_state_path") != TRUST_STATE_PATH
    ):
        errors.append("PKLOAD6 development media paths changed")
    try:
        kmap_contract = read_json(root / KMAP_CONTRACT_RELATIVE)
        errors.extend(_schema_errors(kmap_contract, root, KMAP_CONTRACT_SCHEMA_RELATIVE))
        if kmap_contract.get("required_negative_controls") != list(KMAP_NEGATIVE_CONTROL_IDS):
            errors.append("PKMAP2 negative-control register changed")
    except (OSError, json.JSONDecodeError, KernelLoadError) as error:
        errors.append(f"PKMAP2 contract cannot be read: {error}")
    try:
        boot_exit_contract = read_json(root / BOOT_EXIT_CONTRACT_RELATIVE)
        errors.extend(
            _schema_errors(boot_exit_contract, root, BOOT_EXIT_CONTRACT_SCHEMA_RELATIVE)
        )
        if boot_exit_contract.get("required_negative_controls") != list(
            BOOT_EXIT_NEGATIVE_CONTROL_IDS
        ):
            errors.append("PBEXIT1 negative-control register changed")
    except (OSError, json.JSONDecodeError, KernelLoadError) as error:
        errors.append(f"PBEXIT1 contract cannot be read: {error}")
    try:
        validate_claims(contract.get("claims", {}))
    except KernelLoadError as error:
        errors.append(str(error))
    return errors


def readiness_errors(readiness: dict[str, Any], root: Path) -> list[str]:
    errors = _schema_errors(readiness, root, READINESS_SCHEMA_RELATIVE)
    try:
        contract = read_json(root / CONTRACT_RELATIVE)
    except (OSError, json.JSONDecodeError, KernelLoadError) as error:
        return errors + [f"PKLOAD6 contract cannot be read: {error}"]
    errors.extend(contract_errors(contract, root))
    bindings = readiness.get("bindings", {})
    expected_bindings = {
        "contract": CONTRACT_RELATIVE,
        "kernel_map_contract": KMAP_CONTRACT_RELATIVE,
        "boot_exit_contract": BOOT_EXIT_CONTRACT_RELATIVE,
        "toolchain_lock": "specs/native-toolchain-lock.json",
        "toolchain_qualification": "runs/native_toolchain_qualification.json",
        "tier0_lock": "specs/native-tier0-lock.json",
        "tier0_profile": "specs/native-tier0-profile.json",
        "tier0_readiness": "runs/native_tier0_readiness.json",
        "kernel_entry_contract": "specs/native-kernel-entry-contract.json",
        "kernel_entry_readiness": "runs/native_kernel_entry_readiness.json",
        "system_manifest_contract": native_system_manifest.CONTRACT_RELATIVE,
        "system_manifest_readiness": native_system_manifest.READINESS_RELATIVE,
        "digest_provider": native_system_manifest.DIGEST_PROVIDER_RELATIVE,
        "initial_system_contract": native_initial_system.CONTRACT_RELATIVE.as_posix(),
        "initial_system_readiness": native_initial_system.READINESS_RELATIVE.as_posix(),
        "recovery_contract": native_recovery.CONTRACT_RELATIVE.as_posix(),
        "recovery_readiness": native_recovery.READINESS_RELATIVE.as_posix(),
        "symbols_contract": native_symbols.CONTRACT_RELATIVE.as_posix(),
        "symbols_readiness": native_symbols.READINESS_RELATIVE.as_posix(),
        "microcode_contract": native_microcode.CONTRACT_RELATIVE.as_posix(),
        "microcode_readiness": native_microcode.READINESS_RELATIVE.as_posix(),
        "firmware_contract": native_firmware.CONTRACT_RELATIVE.as_posix(),
        "firmware_readiness": native_firmware.READINESS_RELATIVE.as_posix(),
        "policy_contract": native_policy.CONTRACT_RELATIVE.as_posix(),
        "policy_readiness": native_policy.READINESS_RELATIVE.as_posix(),
        "boot_trust_contract": native_boot_trust.CONTRACT_RELATIVE,
        "boot_trust_readiness": native_boot_trust.READINESS_RELATIVE,
    }
    for name, path in expected_bindings.items():
        if not binding_matches(bindings.get(name), root, path):
            errors.append(f"stale {name} binding")
    implementation = bindings.get("implementation_inputs", [])
    if not isinstance(implementation, list) or [
        item.get("path") for item in implementation if isinstance(item, dict)
    ] != list(IMPLEMENTATION_INPUTS):
        errors.append("PKLOAD6 implementation-input order changed")
    else:
        for item, path in zip(implementation, IMPLEMENTATION_INPUTS, strict=True):
            if not binding_matches(item, root, path):
                errors.append(f"stale implementation input {path}")

    media = readiness.get("media", {}).get("inspection", {})
    files = media.get("files", [])
    build = readiness.get("build", {})
    kernel_product = readiness.get("kernel_product", {})
    if not isinstance(files, list) or len(files) != 6 + len(ARTIFACT_DEFINITIONS):
        errors.append("PKLOAD6 media must contain exactly twelve files")
    else:
        expected_paths = [
            native_pooleboot.FALLBACK_PATH,
            CONFIG_PATH,
            MANIFEST_PATH,
            KERNEL_PATH,
            *(definition[4] for definition in ARTIFACT_DEFINITIONS),
            TRUST_POLICY_PATH,
            TRUST_STATE_PATH,
        ]
        if [item.get("path") for item in files] != expected_paths:
            errors.append("PKLOAD6 media path order changed")
        if files[0].get("sha256") != build.get("sha256"):
            errors.append("embedded PooleBoot does not match its build")
        if files[2].get("sha256") != media.get("manifest", {}).get("sha256"):
            errors.append("embedded PSM1 does not match its independent parse")
        if files[3].get("sha256") != kernel_product.get("canonical_sha256"):
            errors.append("embedded PooleKernel does not match PKENTRY1")
        artifact_set = media.get("artifact_set", {})
        artifacts = artifact_set.get("artifacts", [])
        if (
            artifact_set.get("contract_id") != native_boot_artifact.CONTRACT_ID
            or artifact_set.get("artifact_count") != len(ARTIFACT_DEFINITIONS)
            or not isinstance(artifacts, list)
            or len(artifacts) != len(ARTIFACT_DEFINITIONS)
        ):
            errors.append("PKLOAD6 artifact-set profile changed")
        else:
            for file_item, artifact, definition in zip(
                files[4 : 4 + len(ARTIFACT_DEFINITIONS)],
                artifacts,
                ARTIFACT_DEFINITIONS,
                strict=True,
            ):
                role, manifest_id, _, _, media_path, _ = definition
                if (
                    artifact.get("path") != media_path
                    or artifact.get("manifest_id") != manifest_id
                    or artifact.get("role") != role
                    or artifact.get("file_sha256") != file_item.get("sha256")
                    or artifact.get("file_bytes") != file_item.get("byte_count")
                ):
                    errors.append(f"PKLOAD6 artifact binding changed for {media_path}")
        trust_state = media.get("trust_state", {})
        if (
            trust_state.get("contract_id") != native_boot_trust.CONTRACT_ID
            or trust_state.get("denial") != "pbtrust_policy_unsigned"
            or trust_state.get("binding_count") != 14
            or trust_state.get("authority_grants") != 0
            or trust_state.get("state_writes") != 0
            or trust_state.get("policy_sha256")
            != files[-2].get("sha256")
            or trust_state.get("state_sha256")
            != files[-1].get("sha256")
        ):
            errors.append("PKLOAD6 PBTRUST1 independent-oracle summary changed")
        try:
            expected_initial_system = initial_system_oracle(
                canonical_artifact_files()[INITIAL_SYSTEM_PATH], 1
            )
        except (
            KernelLoadError,
            native_boot_artifact.BootArtifactError,
            native_initial_system.InitialSystemError,
        ) as error:
            errors.append(f"canonical PINIT1 oracle failed: {error}")
        else:
            if media.get("initial_system") != expected_initial_system:
                errors.append("PKLOAD6 PINIT1 independent-oracle summary changed")
        try:
            expected_recovery = recovery_oracle(
                canonical_artifact_files()[RECOVERY_PATH], 1
            )
        except (
            KernelLoadError,
            native_boot_artifact.BootArtifactError,
            native_recovery.RecoveryError,
        ) as error:
            errors.append(f"canonical PREC1 oracle failed: {error}")
        else:
            if media.get("recovery") != expected_recovery:
                errors.append("PKLOAD6 PREC1 independent-oracle summary changed")
        try:
            expected_symbols = symbols_oracle(
                canonical_artifact_files()[SYMBOLS_PATH], 1
            )
        except (
            KernelLoadError,
            native_boot_artifact.BootArtifactError,
            native_symbols.SymbolError,
        ) as error:
            errors.append(f"canonical PSYM1 oracle failed: {error}")
        else:
            if media.get("symbols") != expected_symbols:
                errors.append("PKLOAD6 PSYM1 independent-oracle summary changed")
        try:
            expected_microcode = microcode_oracle(
                canonical_artifact_files()[MICROCODE_PATH], 1
            )
        except (
            KernelLoadError,
            native_boot_artifact.BootArtifactError,
            native_microcode.MicrocodeError,
        ) as error:
            errors.append(f"canonical PMCU1 oracle failed: {error}")
        else:
            if media.get("microcode") != expected_microcode:
                errors.append("PKLOAD6 PMCU1 independent-oracle summary changed")
        try:
            expected_firmware = firmware_oracle(
                canonical_artifact_files()[FIRMWARE_PATH], 1
            )
        except (
            KernelLoadError,
            native_boot_artifact.BootArtifactError,
            native_firmware.FirmwareError,
        ) as error:
            errors.append(f"canonical PFWM1 oracle failed: {error}")
        else:
            if media.get("firmware") != expected_firmware:
                errors.append("PKLOAD6 PFWM1 independent-oracle summary changed")
        try:
            expected_policy = policy_oracle(
                canonical_artifact_files()[POLICY_PATH], 1
            )
        except (
            KernelLoadError,
            native_boot_artifact.BootArtifactError,
            native_policy.PolicyError,
        ) as error:
            errors.append(f"canonical PPOL1 oracle failed: {error}")
        else:
            if media.get("policy") != expected_policy:
                errors.append("PKLOAD6 PPOL1 independent-oracle summary changed")
        try:
            expected_inner_set = native_inner_live.validate_development_set(
                [
                    canonical_artifact_files()[definition[4]]
                    for definition in ARTIFACT_DEFINITIONS
                ]
            )
        except (
            native_inner_live.InnerLiveError,
            native_boot_artifact.BootArtifactError,
            native_initial_system.InitialSystemError,
            native_recovery.RecoveryError,
            native_symbols.SymbolError,
            native_microcode.MicrocodeError,
            native_firmware.FirmwareError,
            native_policy.PolicyError,
        ) as error:
            errors.append(f"canonical live inner-set oracle failed: {error}")
        else:
            if media.get("inner_set") != expected_inner_set:
                errors.append("PKLOAD6 live inner-set independent-oracle summary changed")
    runs = readiness.get("execution", {}).get("runs", [])
    marker_sets: list[list[str]] = []
    if not isinstance(runs, list) or len(runs) != 2:
        errors.append("PKLOAD6 execution must contain exactly two runs")
    else:
        for index, run in enumerate(runs):
            try:
                summary = validate_markers(run.get("markers", []))
                validate_oracle_binding(summary, media, run.get("pbp1_transcript"))
            except (KernelLoadError, KeyError, TypeError) as error:
                errors.append(f"PKLOAD6 run {index} validation failed: {error}")
                continue
            marker_sets.append(run["markers"])
            if run.get("marker_summary") != summary:
                errors.append(f"PKLOAD6 run {index} marker summary changed")
            if run.get("marker_sha256") != sha256_bytes(
                native_pooleboot.canonical_json_bytes(run["markers"])
            ):
                errors.append(f"PKLOAD6 run {index} marker digest changed")
    if len(marker_sets) == 2 and marker_sets[0] != marker_sets[1]:
        errors.append("PKLOAD6 run markers differ")

    execution = readiness.get("execution", {})
    normalized = execution.get("normalized_command", [])
    if execution.get("normalized_command_sha256") != sha256_bytes(
        native_pooleboot.canonical_json_bytes(normalized)
    ):
        errors.append("PKLOAD6 normalized command digest mismatch")

    controls = readiness.get("negative_controls", [])
    if [item.get("id") for item in controls if isinstance(item, dict)] != list(
        NEGATIVE_CONTROL_IDS
    ):
        errors.append("PKLOAD6 readiness negative-control register changed")
    if any(
        item.get("expected") != "reject"
        or item.get("observed") != "reject"
        or item.get("status") != "pass"
        for item in controls
        if isinstance(item, dict)
    ):
        errors.append("PKLOAD6 readiness has a failing negative control")
    try:
        validate_claims(readiness.get("claims", {}))
    except KernelLoadError as error:
        errors.append(str(error))
    if readiness.get("claim_boundary") != contract.get("claim_boundary"):
        errors.append("PKLOAD6 readiness claim boundary differs from its contract")
    if native_pooleboot.ABSOLUTE_USER_PATH.search(json.dumps(readiness, ensure_ascii=True)):
        errors.append("absolute user path leaked into PKLOAD6 readiness")
    return errors
