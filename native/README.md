# Native PooleOS Source Tree

This tree is reserved for code and data that can become part of the native PooleOS product. Root-level `runtime/`, `tools/`, `tests/`, `specs/`, and `runs/` are current host-side reference and evidence surfaces; they are not silently promoted into release media.

`fixtures/pooleboot` and `kernel` retain the empty compiler/linker qualification inputs. `boot` contains the bounded unsigned PooleBoot proof application that executes under pinned OVMF but does not load a kernel or exit boot services. `handoff` contains the candidate PBP1 `no_std` codec; it is qualified independently and is not yet called by PooleBoot or PooleKernel.

All native code must follow ADR-0001 through ADR-0007, the Production Goal Charter, the N0-N39 Build Plan, and the public/private publication boundary.
