# Poole Boot Protocol

`poole-handoff` is the dependency-free `no_std` PBP1 byte codec shared by PooleBoot producers and the future PooleKernel consumer. It manually reads and writes canonical little-endian bytes; no persistent or cross-domain layout depends on Rust's native ABI. Core validation distinguishes temporary pre-exit snapshots, which require zero stack and CR3, from transferable post-exit state, which requires both fields to be nonzero and aligned.

This standalone crate receipt is protocol evidence, not by itself evidence that PooleBoot loaded PooleKernel, exited UEFI boot services, or transferred control. PKLOAD3/PBLIVE1 separately proves a temporary live pre-exit producer; it does not prove a retained read-only handoff or transfer. The authoritative contract and evidence are `specs/native-boot-handoff-contract.json`, `docs/native-boot-handoff.md`, and `runs/native_boot_handoff_readiness.json`.
