# ADR-0003: Implementation Language and Toolchain Split

Status: proposed  
Date: 2026-07-16  
Decision owner: Rooke Poole  
Ratification: owner acceptance and full two-host toolchain qualification pending  
Supersedes: none  
Superseded by: none  
Requirement mappings: N0.2, N3.1-N3.8, sections 008-011  

## Context

PooleOS requires freestanding UEFI PE32+ and x86-64 ELF64 output, explicit ABIs, small unsafe surfaces, deterministic release tooling, and interoperability with a portable PDC reference. Cycle 82 installs a pinned Rust/LLD toolchain only in the ignored workspace-local tool directory; no global Rust state or `PATH` mutation is permitted. NASM, the freestanding C17 path, image tools, QEMU, and OVMF are not yet qualified.

## Proposed Decision

- PooleBoot: Rust 2024, `#![no_std]`, `x86_64-unknown-uefi`, panic abort, static PE32+, Rust `efiapi` calls, and `rust-lld`. Poole-authored raw UEFI bindings are generated from reviewed schemas; helper crates require a separate reuse ADR.
- PooleKernel: Rust 2024, `#![no_std]`, initially `x86_64-unknown-none`, ELF64, kernel code model, no red zone, panic abort, no unwinding, and no floating/vector register use before explicit context support.
- Privileged servers and drivers: Rust `no_std` plus controlled `alloc` initially, with only explicit stable wire ABIs crossing protection domains.
- Architecture entry, interrupt, context-switch, and atomic primitives: minimal reviewed x86-64 assembly, preferably through the pinned LLVM integrated assembler or tightly bounded Rust assembly.
- Portable PDC reference and ABI probes: freestanding C17 with checked arithmetic and no undefined-behavior tolerance.
- Host evidence and migration tools: Python remains an oracle and harness, not a production-image dependency. Release-critical host tools must be hermetic and reproducibility-qualified.
- C++ is excluded from the v1 TCB. Applications may revisit it through a separate runtime and ABI ADR.

Rust `core`, controlled `alloc`, compiler builtins, LLVM, LLD, and their source/toolchain manifests are external build inputs, not Poole-authored operating-system code. Third-party crates are denied by default and require license, provenance, feature, unsafe-code, transitive-dependency, SBOM, and update review.

Public and persistent ABIs never use the unstable native Rust ABI. They use generated fixed-width layouts, explicit endianness, size/version/flags fields, checked offsets, and independent C/Rust layout fixtures.

## Alternatives

- C17 for the entire OS: mature and portable but exposes a substantially larger memory-safety and UB burden.
- C++ for the kernel: rejected from the v1 TCB due to runtime, ABI, exception, and language-surface complexity.
- Zig as the primary implementation language: attractive cross-compilation model, but requires a separate maturity and assurance evaluation.
- custom compiler backend before boot: rejected as an early dependency.

## Consequences

The memory-safe default narrows but does not remove the TCB or unsafe-code burden. Compiler, linker, core-library, codegen, and target assumptions become explicit assurance inputs. C interoperability requires an independently validated freestanding cross toolchain.

## Evidence and Exit Gate

Cycle 82 pins Rust 1.97.0, Cargo 1.97.0, rustup 1.29.0, LLD 22.1.6, the dated Rust channel manifest, and both target library components. Dependency-free empty fixtures build offline in two separate clean target trees on one Windows host. The 3,072-byte PE32+ and 984-byte ELF64 outputs are byte-identical across runs, pass independent structure checks, contain no scanned host paths or runtime-library markers, and reject malformed/substituted targets. `runs/native_toolchain_qualification.json` records this bounded evidence.

N3 must still reproduce the artifacts on a second clean host, verify detached distribution signatures and source-rebuild provenance, qualify the C17/assembly/ABI/image tools, prove ABI fixtures, inventory unsafe code, and show no host headers or libraries leak into any production artifact before this ADR becomes accepted.
