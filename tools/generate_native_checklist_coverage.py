#!/usr/bin/env python3
"""Generate the exact-line coverage ledger for the native PooleOS checklist."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE_RELATIVE = Path(
    "sources/requirements/sha256/"
    "a8c94719faf9428c1f133010ba2603c0270c4e1efd7327af8eab9c8c362abb3d/"
    "PooleOS_From_Scratch_Master_Checklist.md"
)
SOURCE_SHA256 = "A8C94719FAF9428C1F133010BA2603C0270C4E1EFD7327AF8EAB9C8C362ABB3D"


PHASES = [
    ("N0", "Native Architecture Constitution", ["000", "001", "170"]),
    ("N1", "Requirements, Governance, Legal, and Provenance", ["002", "003", "004"]),
    ("N2", "Hardware Target, Laboratory, and Standards", ["005", "006", "007", "146", "169"]),
    ("N3", "Toolchain, Build, CI, and Low-Level Safety", ["008", "009", "010", "011"]),
    ("N4", "Emulation, Reference Devices, and Formal Models", ["012"]),
    ("N5", "Boot Media, Boot Protocol, and PooleBoot UEFI Loader", ["013", "014", "015"]),
    ("N6", "Boot Trust, Kernel Image, Early Runtime, and Emergency Diagnostics", ["016", "017", "018", "019", "148", "149"]),
    ("N7", "x86-64 CPU, Privilege, Descriptor, and Fault Foundation", ["020", "021", "022"]),
    ("N8", "Interrupts, Time, SMP, and CPU Lifecycle", ["023", "024", "025"]),
    ("N9", "Physical and Virtual Memory, MMIO, Allocation, and Reclaim", ["026", "027", "028", "029", "151"]),
    ("N10", "Platform Discovery, ACPI, SMBIOS, PCIe, and Low-Speed Buses", ["042", "043", "044", "045", "046", "152"]),
    ("N11", "DMA, IOMMU, and Interrupt Remapping", ["030"]),
    ("N12", "Concurrency, Scheduler, Deferred Work, and Context Switching", ["031", "032", "033", "034"]),
    ("N13", "Tasks, Syscalls, Events, and Capability Object Model", ["035", "036", "037", "038"]),
    ("N14", "IPC, Identity, Isolation, Async I/O, and Resource Control", ["039", "040", "041", "163", "164"]),
    ("N15", "Security, Cryptography, TPM, Secrets, MAC, and Firmware Boundaries", ["107", "108", "109", "110", "111", "112", "155"]),
    ("N16", "Isolated Driver Domains and Extension Lifecycle", ["150"]),
    ("N17", "Block Storage, Partitions, and Volume Management", ["047", "048", "049", "050", "166"]),
    ("N18", "USB, Input, and Removable Media", ["051", "052", "053", "054", "055", "056", "057", "165"]),
    ("N19", "VFS, PooleFS, Page Cache, Encryption, and Persistent Data", ["076", "077", "078", "079", "080", "081"]),
    ("N20", "Executable Loader, User ABI, C Runtime, Threads, and Language Runtimes", ["082", "083", "084", "085", "086", "087"]),
    ("N21", "Init, Services, Utilities, Logging, Device Policy, and Integrity Maintenance", ["088", "089", "090", "091", "092", "141", "158", "168"]),
    ("N22", "Authentication, Sessions, Shell, Terminal, Accounts, and User Data", ["093", "094", "157", "162", "167"]),
    ("N23", "Packages, Updates, Installer, Recovery, Backup, and Migration", ["095", "096", "097", "098", "159"]),
    ("N24", "Shutdown, Power, Firmware Updates, Sensors, and Hardware Health", ["099", "100", "153", "154"]),
    ("N25", "Ethernet, Wi-Fi, Bluetooth, and Link Drivers", ["063", "064", "065", "066"]),
    ("N26", "Network Protocols, Services, Firewall, TLS, and Virtual Links", ["067", "068", "069", "070", "071", "072", "073", "074", "075", "156"]),
    ("N27", "Display Bootstrap, Virtio GPU, and Native Graphics Research", ["058", "059", "060", "061"]),
    ("N28", "Audio, Media Policy, and Optional Peripherals", ["062", "104", "105"]),
    ("N29", "Compositor, Text, Desktop, GUI Toolkit, and Accessibility", ["101", "102", "103", "160", "161"]),
    ("N30", "Application Model, SDK, Sandboxing, and Porting", ["106"]),
    ("N31", "Debugging, Crash Analysis, Tracing, and Performance Methodology", ["113", "114", "115", "116"]),
    ("N32", "PDC Canonical Mathematics, Portable Runtime, and Guarded Backends", []),
    ("N33", "PDC Native Control Plane and Bounded Actuation Lanes", ["117", "118", "119", "120", "121", "122", "123"]),
    ("N34", "PooleGlyph, PGB2, PGVM2, and System Policy", ["124"]),
    ("N35", "Reliability, Watchdogs, Fault Containment, Virtualization, and RAS", ["125", "126", "127"]),
    ("N36", "Verification, Fuzzing, Fault Injection, Security, and Conformance", ["128", "129", "130", "131", "132", "133", "134", "140"]),
    ("N37", "Supply Chain, Release, Signing, Operations, Documentation, and Manifest", ["135", "136", "137", "138", "139", "147"]),
    ("N38", "Dependency Milestones, Hardware Qualification, and Readiness Gates", ["142", "143", "144", "145"]),
    ("N39", "Reproducible Signed Native ISO and Production Release", []),
]


PHASE_STATUS = {
    "N0": "partial",
    "N1": "partial",
    "N2": "partial",
    "N3": "partial",
    "N4": "partial",
    "N5": "partial",
    "N6": "partial",
    "N15": "partial",
    "N31": "partial",
    "N32": "partial",
    "N33": "partial",
    "N34": "blocked",
    "N35": "partial",
    "N36": "partial",
    "N37": "partial",
}


ADDED_REQUIREMENTS = [
    {
        "id": "ADD-NATIVE-001",
        "phase_id": "N0",
        "requirement": "Freeze PooleOS v1 as an original capability-based microkernel system with Poole-authored PooleBoot and PooleKernel; Linux, Debian, Buildroot, GRUB, Limine, and systemd are development or comparison inputs only and cannot satisfy production gates.",
        "basis": ["architecture clarification from Rooke Poole on 2026-07-15"],
    },
    {
        "id": "ADD-NATIVE-002",
        "phase_id": "N0",
        "requirement": "Inventory the trusted computing base and assign every subsystem to kernel, privileged server, isolated driver domain, ordinary service, or recovery environment with explicit authority and restart semantics.",
        "basis": ["https://sel4.systems/About/whitepaper.html", "https://sel4.systems/Verification/assumptions.html"],
    },
    {
        "id": "ADD-REUSE-001",
        "phase_id": "N1",
        "requirement": "Adopt a signed reuse-boundary ADR covering studied code, ported libraries, generated standards data, cryptography, fonts, codecs, vendor firmware, microcode, and clean-room constraints; from-scratch status must be provenance-exact rather than rhetorical.",
        "basis": ["master checklist sections 000.2, 003, and 170"],
    },
    {
        "id": "ADD-ASSURE-001",
        "phase_id": "N4",
        "requirement": "Maintain executable or machine-checked models for capability derivation/revocation, IPC state, scheduler transitions, virtual-memory map/unmap, boot-slot state, update rollback, and PooleFS transaction recovery before freezing each corresponding ABI.",
        "basis": ["https://sel4.systems/Verification/", "https://sel4.systems/Verification/proofs.html"],
    },
    {
        "id": "ADD-ASSURE-002",
        "phase_id": "N36",
        "requirement": "Record proof assumptions and coverage boundaries; formal models supplement but never replace executable negative, concurrency, fault, hardware, and recovery tests.",
        "basis": ["https://sel4.systems/Verification/assumptions.html"],
    },
    {
        "id": "ADD-VIRTIO-001",
        "phase_id": "N4",
        "requirement": "Add OASIS VIRTIO 1.3 as the QEMU-first reference-device contract and implement modern PCI transport negotiation before physical-device drivers.",
        "basis": ["https://docs.oasis-open.org/virtio/virtio/v1.3/virtio-v1.3.html"],
    },
    {
        "id": "ADD-TIER0-SUPPLY-001",
        "phase_id": "N4",
        "requirement": "Treat QEMU, firmware, and debugger inputs as a pinned host-tool supply chain: bind exact source tags and commits, provider patch deltas, signatures, executable and runtime-closure hashes, firmware source-to-binary provenance, licenses, SBOM, vulnerabilities, redistribution status, host security controls, and second-builder reproduction; reject aliases, development builds, Android forks, expired-certificate trust, and stale bundled firmware as silent substitutes.",
        "basis": [
            "https://www.qemu.org/download/",
            "https://github.com/tianocore/edk2/releases",
            "Cycle 88 observed QEMU/OVMF candidate provenance gaps",
        ],
    },
    {
        "id": "ADD-HW-PROBE-001",
        "phase_id": "N2",
        "requirement": "Separate unprivileged CPUID collection from privileged MSR, PCI configuration-space, SPD, UEFI-variable, physical-memory, and I/O-port probes; require exact allowlists, deterministic logical-processor affinity with restoration, source-bound read-only mechanisms, no write-capable path, driver and side-effect review, hostile tests, and explicit operator authorization before any kernel driver is loaded.",
        "basis": [
            "https://docs.amd.com/v/u/en-US/40332_4.09_APM_PUB",
            "https://learn.microsoft.com/en-us/windows/win32/api/memoryapi/nf-memoryapi-virtualalloc",
            "PooleOS destructive and privileged hardware safety boundary",
        ],
    },
    {
        "id": "ADD-VIRTIO-002",
        "phase_id": "N16",
        "requirement": "Provide isolated virtio console, block, network, input, GPU, RNG, balloon, and IOMMU driver paths as applicable, each with feature negotiation, queue validation, DMA confinement, reset, cancellation, and malformed-device tests.",
        "basis": ["https://docs.oasis-open.org/virtio/virtio/v1.3/virtio-v1.3.html"],
    },
    {
        "id": "ADD-BOOT-001",
        "phase_id": "N5",
        "requirement": "Define the PooleBoot-to-PooleKernel protocol as a canonical versioned binary schema with independent decoder, structure-layout assertions, golden byte vectors, downgrade tests, and fuzzing before kernel entry code depends on it.",
        "basis": ["https://uefi.org/specs/UEFI/2.11/"],
    },
    {
        "id": "ADD-BOOT-004",
        "phase_id": "N5",
        "requirement": "Define a bounded typed envelope and exact profile for every non-kernel boot artifact; independently validate role, version, size, payload and whole-file digests, transactional loading, zero padding, retained-range ownership, cleanup, and PBP1 cross-binding while keeping authentication and each payload's executable or device-changing semantics separately gated.",
        "basis": [
            "Cycle 107 PBART1 and PBASET1 integration",
            "master checklist sections 013-015",
            "N5.6 initial-system, recovery, symbol, microcode, firmware-manifest, and policy artifact requirements",
        ],
    },
    {
        "id": "ADD-BOOT-005",
        "phase_id": "N5",
        "requirement": "Define every executable initial-system bundle as a deterministic declaration contract whose parsing and graph validation cannot confer authority; gate activation separately on authenticated outer and manifest signatures, persistent rollback state, ABI compatibility, resource and capability allocator readiness, complete component verification, transactional capacity, and fail-closed rollback before any allocation, capability issuance, or instruction execution.",
        "basis": [
            "Cycle 108 PINIT1 declaration and activation-separation qualification",
            "https://docs.sel4.systems/projects/capdl/lang-spec.html",
            "https://fuchsia.dev/fuchsia-src/concepts/components/v2/capabilities",
            "https://fuchsia.dev/fuchsia-src/concepts/components/v2/lifecycle",
            "https://theupdateframework.github.io/specification/v1.0.26/",
        ],
    },
    {
        "id": "ADD-BOOT-002",
        "phase_id": "N6",
        "requirement": "Model UEFI PK, KEK, db, dbx, image signer revocation, minimum secure version, authenticated boot state, recovery-key rotation, and development-key containment as one boot-trust state machine.",
        "basis": ["https://uefi.org/specs/UEFI/2.11/32_Secure_Boot_and_Driver_Signing.html"],
    },
    {
        "id": "ADD-BOOT-003",
        "phase_id": "N6",
        "requirement": "Pin and vendor every boot-time digest provider, remove absolute build paths reproducibly, qualify standard, differential, and artifact-mutation vectors, and require independent cryptographic review plus target-backend qualification before trust promotion; digest equality against an unsigned manifest is not authentication.",
        "basis": [
            "Cycle 103 PBDIGEST1 boot-time SHA-256 provider integration",
            "specs/native-boot-digest-provider.json",
            "master checklist sections 016, 017, 099, and 170",
        ],
    },
    {
        "id": "ADD-KERNEL-001",
        "phase_id": "N6",
        "requirement": "Declare the exact temporary mapping, lifetime, cache policy, write permission, and revocation transition for every physical address passed to early PooleKernel diagnostics; in particular, no PBP1 framebuffer physical address may be dereferenced until the entry contract proves that mapping is present.",
        "basis": [
            "PBP1 framebuffer physical-address contract",
            "master checklist section 018 early framebuffer requirements",
            "Cycle101 N6-KENTRY-001 mapping-gap analysis",
        ],
    },
    {
        "id": "ADD-TIME-001",
        "phase_id": "N8",
        "requirement": "Keep monotonic, boot, UTC, and civil time domains separate; specify leap-second, time-step, suspend, RTC-invalid, and pre-network trust behavior without allowing wall-clock changes to break deadlines or signature rollback state.",
        "basis": ["https://pubs.opengroup.org/onlinepubs/9799919799/", "https://www.iana.org/time-zones"],
    },
    {
        "id": "ADD-CAP-001",
        "phase_id": "N13",
        "requirement": "Specify unforgeable capabilities, rights attenuation, derivation provenance, transfer, revocation, generation-safe handles, quotas, object destruction, and zero ambient authority; prove no authority amplification across IPC.",
        "basis": ["https://sel4.systems/About/whitepaper.html", "https://sel4.systems/Research/pdfs/comprehensive-formal-verification-os-microkernel.pdf"],
    },
    {
        "id": "ADD-ABI-001",
        "phase_id": "N14",
        "requirement": "Freeze generated syscall and IPC wire ABIs with explicit widths, byte order, alignment, maximum message sizes, capability-transfer slots, cancellation, deadlines, compatibility negotiation, and independent conformance fixtures.",
        "basis": ["master checklist sections 008.3, 036, 039, and 140"],
    },
    {
        "id": "ADD-CPU-001",
        "phase_id": "N15",
        "requirement": "Maintain a target-CPU and microcode mitigation matrix for transient execution, branch prediction, return-stack, store-bypass, SMT, and control-flow protections; gate every mitigation by exact CPUID, firmware, threat, and benchmark evidence.",
        "basis": ["https://docs.amd.com/", "https://www.intel.com/content/www/us/en/developer/articles/technical/intel-sdm.html"],
    },
    {
        "id": "ADD-DRIVER-001",
        "phase_id": "N16",
        "requirement": "Run nonessential drivers outside the kernel in capability-confined address spaces; bind MMIO, ports, IRQs, DMA domains, and device reset to revocable leases and prove supervisor restart without stale completion or cross-domain memory access.",
        "basis": ["native microkernel architecture decision", "master checklist sections 030 and 042"],
    },
    {
        "id": "ADD-MODULE-001",
        "phase_id": "N16",
        "requirement": "Prohibit production loadable kernel modules in v1; satisfy checklist section 150 through signed user-space driver packages unless a later reviewed ADR proves a kernel extension indispensable and preserves the TCB assurance case.",
        "basis": ["native microkernel architecture decision", "master checklist section 150"],
    },
    {
        "id": "ADD-FS-001",
        "phase_id": "N19",
        "requirement": "Specify PooleFS transaction, ordering, flush/FUA, checksum, repair, snapshot, quota, encryption, and power-loss semantics independently from implementation and retain every failing disk image used to refine the model.",
        "basis": ["master checklist sections 080, 131, 151, 159, and 166"],
    },
    {
        "id": "ADD-UPDATE-001",
        "phase_id": "N23",
        "requirement": "Use compromise-resilient update metadata with separated root, targets, snapshot, and timestamp roles, threshold keys, expiry, consistent snapshots, rollback/freeze/mix-and-match protection, offline recovery, and monotonic secure-version policy.",
        "basis": ["https://theupdateframework.github.io/specification/"],
    },
    {
        "id": "ADD-RECOVERY-001",
        "phase_id": "N23",
        "requirement": "Keep recovery independently bootable and operable without PooleGlyph, PDC, package service, network, native GPU acceleration, normal compositor, or the mutable production system slot.",
        "basis": ["master checklist sections 001.4, 098, 125, and 170"],
    },
    {
        "id": "ADD-GPU-001",
        "phase_id": "N27",
        "requirement": "Make GOP software rendering and virtio-gpu the required graphics path; keep RTX 5070 native acceleration an isolated research lane that cannot gate boot, recovery, installation, accessibility, or v1 correctness.",
        "basis": ["master checklist sections 058-061 and 142.15"],
    },
    {
        "id": "ADD-UI-001",
        "phase_id": "N29",
        "requirement": "Implement the original Liquid Glass system and boot identity with reduced transparency, reduced motion, high contrast, screen-reader semantics, software rendering, non-composited recovery, and deterministic screenshot/frame-time gates.",
        "basis": ["production goal", "master checklist sections 101-103 and 160-161"],
    },
    {
        "id": "ADD-PDC-001",
        "phase_id": "N32",
        "requirement": "Carry forward the locked PDC-MATH-0.1, PDC-REP-0.1, PDC-GOLDEN-0.2, PDC-QP-0.1, and PDC-QP-STABILITY-0.1 evidence as host oracles, then require independent native scalar and optimized differential execution before any PooleOS control-plane promotion.",
        "basis": ["PooleOS Cycle 79 evidence baseline"],
    },
    {
        "id": "ADD-PGL-001",
        "phase_id": "N34",
        "requirement": "Freeze PGB2 as a canonical binary package and PGVM2 as a bounded deterministic virtual-machine ABI with typed effects, capabilities, verification, quotas, cancellation, traps, replay, and version negotiation after PooleGlyph Phase 66 promotion evidence.",
        "basis": ["live PooleGlyph Phase 65 checkpoint", "existing draft PGB2/PGVM2 evidence"],
    },
    {
        "id": "ADD-PGL-002",
        "phase_id": "N34",
        "requirement": "Develop PooleGlyph machine language and PooleOS in tandem through exact checkpoint, commit, manifest, compatibility-matrix, and change-impact records; preserve user work and reject silent source, language, Core IR, package, VM, host-ABI, or policy drift between repositories.",
        "basis": ["Rooke Poole tandem-development direction on 2026-07-16", "live PooleGlyph Phase 65 checkpoint protocol"],
    },
    {
        "id": "ADD-PGL-003",
        "phase_id": "N34",
        "requirement": "Specify and independently validate the complete deterministic PooleGlyph pipeline from source bytes through tokens, AST, semantic analysis, canonical Core IR, PGASM, PGB2, and PGVM2 behavior; metadata-only declarations must remain non-executable and no lowering or optimization may amplify effects or authority.",
        "basis": ["PooleGlyph v0.5-dev parser/AST system specification", "Phase 66 Core IR boundary requirement"],
    },
    {
        "id": "ADD-PGL-004",
        "phase_id": "N34",
        "requirement": "Maintain versioned golden, malformed, adversarial, migration, differential, and replay corpora across every PooleGlyph representation, with independent encoders, decoders, verifiers, interpreters, source maps, compatibility profiles, and cross-repository fixtures before a language or runtime version is promoted.",
        "basis": ["PooleGlyph v0.5-dev conformance and diagnostic evidence", "native PooleOS independent-verification policy"],
    },
    {
        "id": "ADD-PGL-005",
        "phase_id": "N34",
        "requirement": "Confine PooleGlyph execution behind verified PGB2/PGVM2 and capability-broker boundaries with explicit rights, effects, resources, quotas, deadlines, cancellation, teardown, host-call schemas, and recovery independence; language policy may only attenuate authority already issued by PooleKernel.",
        "basis": ["native PooleOS capability architecture", "PooleGlyph-to-PooleOS integration boundary"],
    },
    {
        "id": "ADD-PGL-006",
        "phase_id": "N34",
        "requirement": "Keep the public PooleGlyph source-available language, reference compiler, canonical formats, baseline verifier/runtime, and conformance evidence sufficient for independent review while segregating private PooleMath optimizations and acceleration strategy; every private backend must remain differential-equivalent to a public-safe reference path and must not change semantics or authority.",
        "basis": ["Rooke Poole IP direction", "PooleGlyph public/private IP boundary"],
    },
    {
        "id": "ADD-TEST-001",
        "phase_id": "N36",
        "requirement": "Add property-based testing, model-based state-machine testing, schedule exploration, mutation testing, symbolic execution where tractable, parser differential testing, and proof-to-test traceability to the existing unit/fuzz/fault suites.",
        "basis": ["research gap analysis against master checklist sections 128-134"],
    },
    {
        "id": "ADD-SUPPLY-001",
        "phase_id": "N37",
        "requirement": "Bind source, review, build, test, image assembly, signing, and publication with in-toto-style links, SLSA 1.2 provenance, and SPDX 3.0.1 SBOMs; verify attestations separately from the build that produced them.",
        "basis": ["https://github.com/in-toto/docs/blob/master/in-toto-spec.md", "https://slsa.dev/spec/v1.2/", "https://spdx.github.io/spdx-spec/"],
    },
    {
        "id": "ADD-REPRO-001",
        "phase_id": "N39",
        "requirement": "Require two clean independent builders to reproduce the declared unsigned bytes and a documented deterministic-signing policy to bind the exact signed PooleBoot, kernel, system, recovery, manifest, and ISO bytes distributed to users.",
        "basis": ["https://reproducible-builds.org/docs/definition/", "https://slsa.dev/spec/v1.2/"],
    },
]


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest().upper()


def parse_sections(lines: list[str]) -> list[dict]:
    headings: list[tuple[str, str, int]] = []
    for line_number, line in enumerate(lines, start=1):
        match = re.match(r"^## (\d{3})\.\s+(.+)$", line)
        if match:
            headings.append((match.group(1), match.group(2), line_number))

    sections: list[dict] = []
    for index, (section_id, title, start_line) in enumerate(headings):
        end_line = headings[index + 1][2] - 1 if index + 1 < len(headings) else len(lines)
        section_lines = lines[start_line - 1 : end_line]
        sections.append(
            {
                "section_id": section_id,
                "title": title,
                "start_line": start_line,
                "end_line": end_line,
                "line_count": end_line - start_line + 1,
                "subheading_count": sum(line.startswith("### ") for line in section_lines),
                "checkbox_count": sum(bool(re.match(r"^\s*- \[[ xX~-]\]", line)) for line in section_lines),
            }
        )
    return sections


def build_coverage(source_path: Path, status_date: str) -> dict:
    source_bytes = source_path.read_bytes()
    if sha256_bytes(source_bytes) != SOURCE_SHA256:
        raise ValueError("locked master checklist hash does not match the architecture-reset source")
    text = source_bytes.decode("utf-8")
    lines = text.splitlines()
    sections = parse_sections(lines)
    expected_sections = {f"{index:03d}" for index in range(171)}
    parsed_sections = {section["section_id"] for section in sections}
    if parsed_sections != expected_sections:
        raise ValueError(f"section inventory drift: missing={sorted(expected_sections - parsed_sections)} extra={sorted(parsed_sections - expected_sections)}")

    section_to_phase: dict[str, str] = {}
    for phase_id, _title, section_ids in PHASES:
        for section_id in section_ids:
            if section_id in section_to_phase:
                raise ValueError(f"section {section_id} is mapped more than once")
            section_to_phase[section_id] = phase_id
    if set(section_to_phase) != expected_sections:
        raise ValueError(f"phase mapping does not cover all sections: {sorted(expected_sections - set(section_to_phase))}")

    for section in sections:
        section["phase_id"] = section_to_phase[section["section_id"]]
        section["phase_status"] = PHASE_STATUS.get(section["phase_id"], "not_started")
        section["completion_inferred"] = False

    phase_records = []
    section_by_id = {section["section_id"]: section for section in sections}
    for phase_id, title, section_ids in PHASES:
        phase_records.append(
            {
                "phase_id": phase_id,
                "title": title,
                "status": PHASE_STATUS.get(phase_id, "not_started"),
                "source_section_ids": section_ids,
                "source_line_count": sum(section_by_id[item]["line_count"] for item in section_ids),
                "source_checkbox_count": sum(section_by_id[item]["checkbox_count"] for item in section_ids),
                "added_requirement_ids": [item["id"] for item in ADDED_REQUIREMENTS if item["phase_id"] == phase_id],
            }
        )

    checkbox_lines = [number for number, line in enumerate(lines, start=1) if re.match(r"^\s*- \[[ xX~-]\]", line)]
    covered_line_numbers = set(range(1, 17))
    for section in sections:
        covered_line_numbers.update(range(section["start_line"], section["end_line"] + 1))
    all_line_numbers = set(range(1, len(lines) + 1))

    return {
        "schema_version": "1.0",
        "artifact_kind": "pooleos_native_checklist_coverage",
        "status_date": status_date,
        "status": "pass" if covered_line_numbers == all_line_numbers else "fail",
        "source": {
            "path": SOURCE_RELATIVE.as_posix(),
            "sha256": SOURCE_SHA256,
            "byte_count": len(source_bytes),
            "line_count": len(lines),
            "top_level_section_count": len(sections),
            "checkbox_line_count": len(checkbox_lines),
            "declared_generated_implementation_item_count": 8996,
            "metadata_checkbox_count": 2,
            "governing_preamble_checkbox_count": 10,
            "section_checkbox_count": sum(section["checkbox_count"] for section in sections),
        },
        "counting_rule": {
            "description": "The source's 8,996 implementation-item count excludes its two generated-metadata checkbox lines 3-4 and includes the ten governing preamble requirements plus all section checkboxes.",
            "equation": "8998 total checkbox lines - 2 generated metadata lines = 8996 implementation items",
        },
        "coverage_policy": {
            "every_source_line_mapped": covered_line_numbers == all_line_numbers,
            "every_section_mapped_once": len(section_to_phase) == 171,
            "every_checkbox_inherited": len(checkbox_lines) == 8998,
            "mapping_does_not_imply_completion": True,
            "source_text_is_immutable": True,
            "research_additions_are_separate": True,
        },
        "unmapped_source_lines": sorted(all_line_numbers - covered_line_numbers),
        "phase_coverage": phase_records,
        "section_coverage": sections,
        "added_requirements": ADDED_REQUIREMENTS,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, default=ROOT / SOURCE_RELATIVE)
    parser.add_argument("--out", type=Path, default=ROOT / "runs/pooleos_native_checklist_coverage.json")
    parser.add_argument("--status-date", default="2026-07-17")
    args = parser.parse_args()
    artifact = build_coverage(args.source, args.status_date)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(artifact, indent=2, ensure_ascii=True) + "\n", encoding="utf-8", newline="\n")
    print(
        f"wrote {args.out}: lines={artifact['source']['line_count']} "
        f"checkboxes={artifact['source']['checkbox_line_count']} "
        f"sections={artifact['source']['top_level_section_count']} "
        f"additions={len(artifact['added_requirements'])} status={artifact['status']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
