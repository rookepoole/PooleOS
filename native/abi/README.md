# Native ABI

Canonical boot, syscall, IPC, capability, driver, executable, package, filesystem, receipt, crash, and release schemas and generated layouts belong here. Persistent and cross-domain layouts must never depend on the native Rust ABI.

The first executable boundary is PBP1 under `native/handoff`, with its authoritative public contract in `specs/native-boot-handoff-contract.json`. It remains a qualified candidate until a separately authorized ABI ratification and live PooleBoot/PooleKernel integration gate pass.
