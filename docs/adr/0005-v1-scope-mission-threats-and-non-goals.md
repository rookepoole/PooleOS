# ADR-0005: V1 Scope, Mission, Threats, and Non-Goals

Status: accepted-owner-directed  
Date: 2026-07-16  
Decision owner: Rooke Poole  
Ratification: cryptographic signature and final quantitative targets pending  
Supersedes: none  
Superseded by: none  
Requirement mappings: N0.5-N0.7, N2.1-N2.3, section 001  

## Mission

PooleOS is a native, inspectable, capability-oriented workstation operating system for general computing and trustworthy execution of PooleGlyph and bounded Poole Defect Calculus workloads.

The v1 product profile is `PooleOS Workstation`. Developer, live, installer, safe, diagnostic, previous-known-good, and recovery modes are profiles of the same signed release, not separate security products.

## Supported Scope

- x86-64 long mode, little endian, UEFI 2.x, GPT media, no legacy BIOS;
- Tier 0: pinned QEMU q35 plus OVMF reference profile;
- Tier 1: the exact inventoried Gigabyte B650M GAMING PLUS WIFI / Ryzen 7 9800X3D system and its explicitly qualified devices and firmware revisions;
- all other hardware unsupported until assigned a reviewed support tier;
- authenticated graphical workstation, terminal, shell, networking, audio, storage, update, rollback, recovery, and accessible software-rendered UI fallback for production;
- PooleGlyph/PGB2/PGVM2 and canonical PDC reference execution for production, with optimized routes guarded by exact fallback rules.

## Initial Threat Model

V1 defends against malicious or malformed applications, packages, filesystems, removable media, network traffic, IPC, drivers, devices capable of DMA, updates, and recovery inputs within the declared platform assumptions. It assumes firmware, CPU package, required microcode, hardware roots, and owner-controlled signing keys are external trust dependencies that must be inventoried, measured where supported, revocable, and explicitly limited.

Invasive physical attacks, malicious foundry hardware, compromised motherboard firmware beyond measured/recovery capabilities, nation-state laboratory attacks, and unqualified hardware are outside the v1 protection claim. Their exclusion does not permit silent failure or false attestation.

## Earliest-Milestone Non-Goals

Accelerated NVIDIA graphics, Wi-Fi, Bluetooth, suspend, hibernation, CPU hot-plug, multi-socket NUMA, legacy BIOS, 32-bit kernel execution, broad USB class support, all NVMe/ACPI/POSIX options, Windows drivers, Linux modules, a custom browser engine, a custom compiler backend, machine-wide PDC actuation, and permanent installation are not early boot prerequisites. Production requirements later in N0-N39 remain in force.

## Claims and Reproduction

Security, durability, update, recovery, PDC, performance, accessibility, and reproducibility claims require independent evidence at their declared scope. Advantages over existing systems remain hypotheses until controlled comparisons exist.

## Open Items

N0.6 remains partial until quantitative boot, latency, memory, power, durability, availability, accessibility, privacy, compatibility, and support targets are frozen against Tier 0/Tier 1 measurement baselines.

