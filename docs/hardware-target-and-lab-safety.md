# Tier 1 Hardware Target and Lab Safety

Status: Cycle 87 pre-production evidence
Selected move: `N2-HW-002`
Production promotion: prohibited

## Purpose

This subsystem turns the first physical PooleOS target into a reviewable, privacy-preserving contract. It does not initialize hardware, qualify a native driver, change firmware, inspect secrets, write storage, alter boot state, or authorize destructive tests.

The evidence chain is:

1. `tools/collect_tier1_hardware.ps1` emits a local `*.private.json` receipt using read-only CIM, PnP, WMI, Secure Boot, TPM, Windows firmware-table queries, and a bounded user-mode CPUID probe.
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
| CPU | AMD Ryzen 7 9800X3D, 8 cores, 16 logical processors, AM5 | 16 allowlisted user-mode CPUID records observed; MSR remains open; host hypervisor is present |
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

## CPU Architecture Evidence and Privileged Boundary

Cycle 87 adds direct CPUID observation without crossing into a driver or privileged probe. AMD64 Architecture Programmer's Manual revision 4.09 documents CPUID as executable at any privilege level and defines its EAX, EBX, ECX, and EDX result contract. The collector uses a 24-byte x86-64 thunk which preserves nonvolatile RBX, passes the requested leaf and subleaf under the Windows x64 ABI, and stores the four result registers into private capture memory.

`POOLEOS-CPUID-ALLOWLIST-1` permits only:

- basic leaves `0x00000000`, `0x00000001`, `0x00000007`, `0x0000000B`, and `0x0000000D`, with bounded advertised subleaves;
- extended leaves `0x80000000`, `0x80000001`, `0x80000007`, `0x80000008`, `0x8000000A`, `0x8000001E`, and `0x8000001F` when supported;
- at most 32 canonical unique records.

Processor-serial leaf `0x00000003` is never queried. Before each query, the collector pins its current thread to the lowest logical processor permitted by the process affinity mask; it restores the exact previous thread affinity immediately after the query. This prevents per-logical-processor APIC/topology fields from making consecutive transcripts nondeterministic without changing hardware state. The thunk memory is allocated read/write, populated, changed to execute/read with `VirtualProtect`, and synchronized with `FlushInstructionCache`; an RWX mapping is never requested. The collector loads no driver and records all MSR, PCI, SPD, UEFI-variable, physical-memory, I/O-port, firmware-write, disk-write, boot-state, and device-state attempts as false.

The ignored private capture contains the canonical register records. The public observation contains a SHA-256 transcript commitment and decoded allowlisted facts only. The affinity-pinned current transcript has 16 records, SHA-256 `1C4EB05B165ABA43F3DED644B0ADFB29A96D8919D0A15948028C1BEA03CC2848`, vendor `AuthenticAMD`, family 26, model 68, stepping 0, and 48-bit physical/linear address widths. Raw register values and processor serial data are not published.

This closes `FLAG-N2-CPUID-001` only. It does not satisfy MSR evidence, native CPUID parsing, kernel feature enablement, mitigation correctness, performance qualification, or general CPU support. `FLAG-N2-PRIVILEGED-PROBE-001` remains open: no driver-backed or privileged collection may run until its exact source, access allowlist, read-only semantics, possible side effects, cleanup/failure behavior, negative tests, and operator authorization are reviewed.

## Privacy Boundary

The raw receipt stays ignored. Public evidence records only its artifact kind, SHA-256, and byte count. The sanitizer never copies arbitrary raw objects; it constructs the public document from named fields.

Public hardware evidence prohibits:

- serial numbers, UUIDs, MAC addresses, IP addresses, host names, and user names;
- absolute workstation paths and full PnP instance suffixes;
- raw ACPI, SMBIOS, EDID, SPD, or UEFI-variable bytes;
- TPM endorsement keys, certificates, owner state, or key material;
- raw CPUID registers or processor-serial leaves;
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
- bounded CPUID records: 16, represented publicly by one transcript hash and decoded facts;
- hostile controls: 14/14 pass;
- partially satisfied evidence channels: 2 (CPU CPUID/MSR and memory SPD/topology);
- required evidence channels not fully observed: 7, including the two partial channels above;
- standards entries with unresolved lock or exact artifact hash: 15;
- accepted destructive-safety prerequisites: 0/10;
- `n2_exit_gate_satisfied=false`;
- `production_ready=false`.

The direct user-mode CPUID portion of `N2-HW-002` is complete. The remaining N2 work is to design and review source-bound read-only mechanisms for MSR, PCI configuration-space, complete ACPI duplicate-table, EDID, SPD, UEFI-variable, sensor, and power acquisition; resolve Secure Boot and TPM read permissions without collecting secrets; compare future native parsers; then acquire and hash lawful standards bytes. No driver-backed or privileged probe is authorized by this plan. Destructive lab acceptance remains a separate owner action.

Primary implementation references for this boundary are AMD64 APM 4.09 (`https://docs.amd.com/v/u/en-US/40332_4.09_APM_PUB`) and Microsoft's `VirtualAlloc`, `VirtualProtect`, and `FlushInstructionCache` API documentation (`https://learn.microsoft.com/windows/win32/api/memoryapi/nf-memoryapi-virtualalloc`, `https://learn.microsoft.com/windows/win32/api/memoryapi/nf-memoryapi-virtualprotect`, and `https://learn.microsoft.com/windows/win32/api/processthreadsapi/nf-processthreadsapi-flushinstructioncache`).
