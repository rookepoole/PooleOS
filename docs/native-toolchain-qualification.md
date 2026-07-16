# Native Toolchain Qualification

Status: single-host pass, non-promoting  
Cycle: PooleOS Cycle 82  
Owner: Rooke Poole

## Scope

`N3-TOOLCHAIN-001` freezes and exercises the smallest dependency-free compiler/linker path needed to emit an empty UEFI PE32+ fixture and an empty freestanding ELF64 fixture. It does not implement or boot PooleBoot or PooleKernel.

The pinned host is `x86_64-pc-windows-msvc`. The toolchain is Rust 1.97.0 with Cargo 1.97.0, rustup 1.29.0, LLVM/LLD 22.1.6, `x86_64-unknown-uefi`, and `x86_64-unknown-none`. Exact distribution URLs and hashes are in `specs/native-toolchain-lock.json`; target ABI and binary requirements are in `specs/native-target-contract.json`.

The official Rust target documentation defines `x86_64-unknown-uefi` as a `no_std` PE32+ target using the Win64 UEFI ABI through `efiapi`. It defines `x86_64-unknown-none` as a freestanding `no_std` ELF target with the kernel code model, no red zone, and no default floating-point or vector use.

## Reproduction

The bootstrap uses a verified `rustup-init.exe`, a verified dated channel manifest, workspace-local `RUSTUP_HOME` and `CARGO_HOME`, and no global `PATH` mutation:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\tools\bootstrap_native_toolchain.ps1
python .\tools\qualify_native_toolchain.py
python -m unittest tests.test_native_toolchain_qualification -v
```

Qualification performs two offline, locked release builds in distinct clean target directories. It parses the resulting formats without external binary-analysis libraries, checks the declared machine, subsystem/type, entry point, timestamp, imports, debug directory, dynamic loader state, segments, sections, and bounds, then scans ASCII and UTF-16LE bytes for host paths, account names, SDK names, and Windows runtime libraries.

The negative controls inject a synthetic host path, substitute the PE fixture where ELF64 is required, and truncate an ELF header. All must be rejected.

## Results

| Fixture | Format | Bytes | SHA-256 | Clean builds | Leakage hits |
|---|---|---:|---|---:|---:|
| PooleBoot qualification fixture | PE32+ EFI application | 3,072 | `41E212DE8ADFF8F673B857C46EA9913F94A6B09C35567E2B5F289BDEB756DE45` | 2 identical | 0 |
| PooleKernel qualification fixture | static ELF64 executable | 984 | `806660E6276777DC0023ED89379B0F94FDB5FF354325F5CABB6E808F94B27322` | 2 identical | 0 |

The first UEFI attempt exposed an eight-byte nondeterministic CodeView/PDB identity in the PE debug directory. Release linking now explicitly applies `/debug:none`; the inspector requires an absent PE debug directory and timestamp zero.

## Open Gates

- A second clean host must independently reproduce both exact binaries.
- Detached channel-manifest signature verification and compiler/LLVM/LLD source-rebuild provenance remain open.
- The freestanding C17 compiler, bounded assembly path, ABI headers/probes, archive tools, image tools, QEMU, and OVMF remain unqualified.
- ADR-0003 still requires owner acceptance and its complete N3 exit gate.
- No UEFI boot, kernel execution, ring transition, capability enforcement, or production-media claim follows from these fixtures.
