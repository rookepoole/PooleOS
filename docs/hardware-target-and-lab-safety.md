# Tier 1 Hardware Target and Lab Safety

Status: Cycle 84 pre-production evidence
Selected move: `N2-HW-001`
Production promotion: prohibited

## Purpose

This subsystem turns the first physical PooleOS target into a reviewable, privacy-preserving contract. It does not initialize hardware, qualify a native driver, change firmware, inspect secrets, write storage, alter boot state, or authorize destructive tests.

The evidence chain is:

1. `tools/collect_tier1_hardware.ps1` emits a local `*.private.json` receipt using read-only CIM, PnP, WMI, Secure Boot, TPM, and Windows firmware-table queries.
2. `tools/sanitize_tier1_hardware_capture.py` validates the private shape and reconstructs `runs/tier1_hardware_observation.json` from a fixed whitelist.
3. `runtime/hardware_target.py` compares the sanitized facts to `specs/tier1-hardware-target.json`, enforces the public privacy boundary, and evaluates standards and lab-safety gaps.
4. `tools/generate_hardware_target_readiness.py` emits `runs/hardware_target_readiness.json`.
5. `tools/verify_hardware_target.py`, Doctor, tests, and the release gate require exact deterministic reproduction.

## Exact Target

The candidate Tier 1 profile is `TIER1-B650M-9800X3D-RTX5070-001`:

| Area | Exact candidate identity | Current boundary |
|---|---|---|
| Board | Gigabyte B650M GAMING PLUS WIFI, version `x.x` | Full PCI and firmware qualification open |
| Firmware | AMI `F32`, SMBIOS exposure `3.7`, UEFI | Secure Boot query permission-limited |
| CPU | AMD Ryzen 7 9800X3D, 8 cores, 16 logical processors, AM5 | Raw CPUID/MSR capture open; host hypervisor is present |
| Memory | 2 x TeamGroup `UD5-6000`, 8 GiB each, configured 6000 | Raw SPD and topology validation open |
| NVMe | Samsung 970 PRO 512GB, `1B2QEXP7`, controller `144D:A808` | Read-only candidate; writes not approved |
| SATA | Crucial BX500 2TB, `M6CR061` | Existing data device; not sacrificial |
| Display | RTX 5070 `10DE:2F04`, subsystem `89E7:1043`, revision A1 | GOP then software rendering; native acceleration quarantined |
| Ethernet | RTL8125 `10EC:8125`, subsystem `E000:1458`, revision 05 | Deferred until isolated native driver work |
| Wi-Fi | RTL8851BE `10EC:B851`, subsystem `B851:10EC`, revision 00 | Quarantined pending firmware, regulatory, isolation, and recovery work |
| Bluetooth | Realtek USB `0BDA:B850` | Quarantined |
| Audio | Realtek HDA codec `10EC:0897`, subsystem `1458:A194` | Candidate first audio path; implementation deferred |
| USB host | AMD `1022:15B6`, `15B7`, `15B8`, and `43F7` | Raw configuration space and native xHCI proof open |

Twenty-four required identity rules match the current sanitized observation. The current display resolution is an additional non-required observation. This consistency result is not the N2 exit gate.

## Firmware Evidence

The collector enumerated 25 ACPI table identifiers and published only unique table signatures, byte counts, and SHA-256 values. The observed signatures include `IVRS` and `TPM2`. Raw SMBIOS bytes are also represented only by byte count and SHA-256.

The Windows API has a documented limitation: when ACPI contains multiple tables with the same signature, `GetSystemFirmwareTable` returns only the first. The public artifact therefore records `acpi_duplicate_retrieval_limitation=true`; a later read-only acquisition path must preserve every duplicate table.

The board vendor release date for BIOS F32 is recorded as `2025-02-04`, while CIM exposes `2025-02-05` in UTC form. `HW-DISCREPANCY-BIOS-DATE-001` remains open. Version and future image/table hashes control firmware equivalence; date alone does not.

## Privacy Boundary

The raw receipt stays ignored. Public evidence records only its artifact kind, SHA-256, and byte count. The sanitizer never copies arbitrary raw objects; it constructs the public document from named fields.

Public hardware evidence prohibits:

- serial numbers, UUIDs, MAC addresses, IP addresses, host names, and user names;
- absolute workstation paths and full PnP instance suffixes;
- raw ACPI, SMBIOS, EDID, SPD, or UEFI-variable bytes;
- TPM endorsement keys, certificates, owner state, or key material;
- any private signing or release material.

Hardware prefixes such as `PCI\VEN_10DE&DEV_2F04&SUBSYS_89E71043&REV_A1` are permitted because the machine-specific instance suffix has been removed. Recursive scans and hostile fixtures reject sensitive fields, MAC-like values, user paths, and full device instances.

## Support Tiers

`specs/hardware-support-policy.json` defines:

| Tier | Meaning |
|---|---|
| Tier 0 | One exact pinned QEMU/OVMF/VIRTIO reference profile; pending N4 |
| Tier 1 | One exact physical machine and recovery setup |
| Tier 2 | A controller family supported by independent samples |
| Tier 3 | Signed, reviewable community-tested exact profiles |
| Tier 4 | Best effort with no support or recovery claim |
| Unsupported | Outside a declared release profile |
| Quarantined | Known hardware blocked from initialization or promotion |

Unlisted hardware defaults to unsupported. Unknown firmware, changed subsystem/revision IDs, missing recovery evidence, and devices without DMA confinement default to quarantined. One Tier 1 result never creates a controller-family claim.

## Standards Register

`specs/native-standards-register.json` records official-primary-source metadata, access terms, errata state, supersession review, and implementation ownership for 15 entries. Important current findings include:

- UEFI 2.11 and ACPI 6.6 are the current UEFI Forum releases listed at `https://uefi.org/specifications`.
- DMTF publishes SMBIOS 3.9.0 as DSP0134.
- AMD publishes AMD64 APM revision 4.09 and AMD IOMMU revision 3.09-PUB.
- PCI-SIG lists PCIe Base 7.0 as current, but the target programming revision and lawful document access remain unresolved.
- NVM Express lists 2.3 as current, while the Build Plan names 2.2; this is an explicit supersession review, not a silent version change.
- xHCI 1.2 remains the candidate host-controller interface baseline.
- USB HID 1.11 and HID Usage Tables 1.7 are recorded.
- TCG TPM 2.0 Version 185 is the current candidate, with platform profile, ACPI, UEFI protocol, and errata bindings still open.
- VIRTIO 1.3 is recorded at OASIS Committee Specification Draft 01 stage.
- Unicode 17.0.0 and POSIX.1-2024 Issue 8 are recorded with ongoing errata/defect tracking.

No exact standards artifact hash has passed yet, and no external specification is redistributed. Metadata lock is useful preparation but does not satisfy the N2 standards exit gate.

## Lab Safety

Destructive testing is not approved. All ten prerequisites remain pending:

- one owner-confirmed expendable SSD;
- two separately labeled expendable USB devices;
- verified backups and sampled restoration;
- immutable recovery media and firmware recovery instructions;
- an independent second recovery machine;
- an independent early-boot diagnostic path;
- accepted UPS, interruption, thermal, and emergency shutdown apparatus;
- an isolated network and packet-capture path;
- private target identity confirmation immediately before use;
- a separate owner approval for the exact mutation and target.

Neither the policy nor a passing consistency gate constitutes approval. A later destructive action must stop if the selected device identity differs, backup or recovery evidence is stale, the command scope broadens, or the operator cannot independently restore the machine.

## Current Result

The current public readiness ledger is `consistent_partial_non_promoting`:

- required target identity: 24/24 match;
- public privacy findings: 0;
- hostile controls: 10/10 pass;
- required evidence channels still pending: 7;
- standards entries with unresolved lock or exact artifact hash: 15;
- accepted destructive-safety prerequisites: 0/10;
- `n2_exit_gate_satisfied=false`;
- `production_ready=false`.

The exact next N2 move is to add reviewed read-only CPUID/MSR, PCI configuration-space, complete ACPI duplicate-table, EDID, SPD, UEFI-variable, sensor, and power acquisition; resolve Secure Boot and TPM read permissions without collecting secrets; then acquire and hash lawful standards bytes. Destructive lab acceptance remains a separate owner action.
