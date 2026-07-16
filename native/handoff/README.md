# Poole Boot Protocol

`poole-handoff` is the dependency-free `no_std` PBP1 byte codec shared by the future PooleBoot producer and PooleKernel consumer. It manually reads and writes canonical little-endian bytes; no persistent or cross-domain layout depends on Rust's native ABI.

The crate is a qualified protocol implementation, not evidence that PooleBoot has loaded PooleKernel, exited UEFI boot services, or transferred control. The authoritative contract and evidence are `specs/native-boot-handoff-contract.json`, `docs/native-boot-handoff.md`, and `runs/native_boot_handoff_readiness.json`.
