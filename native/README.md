# Native PooleOS Source Tree

This tree is reserved for code and data that can become part of the native PooleOS product. Root-level `runtime/`, `tools/`, `tests/`, `specs/`, and `runs/` are current host-side reference and evidence surfaces; they are not silently promoted into release media.

The PooleBoot and PooleKernel directories contain dependency-free, non-booting qualification fixtures for the pinned freestanding Rust targets. They prove only compiler, linker, object-format, reproducibility, and host-leakage properties. Native bootloader and kernel implementation has not started.

All native code must follow ADR-0001 through ADR-0007, the Production Goal Charter, the N0-N39 Build Plan, and the public/private publication boundary.
