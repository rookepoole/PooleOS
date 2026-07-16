# Microkernel Isolation Spike - Historical Simulator Evidence

> **Non-promoting evidence notice (2026-07-15):** this spike models region/capability behavior in the earlier Buildroot/QEMU lab path. It does not implement or enforce PooleKernel isolation. Its artifacts may inform N4, N13-N16, and N36 tests, but native promotion requires booted PooleKernel enforcement and matching negative-test receipts.

Status: draft v0.1

PooleOS now has a static isolation spike for the `PGVM2.Rg` region/capability map named in the kernel charter.

This is not a production security boundary. It is a proof artifact that makes the first region/capability assumptions explicit before a bootable PooleOS Lab image or native substrate exists.

## Compartments

- `pgvm_guest`: untrusted PGB1/PGB2 candidate program surface.
- `geometry_kernel`: trusted staged lattice updates, support counts, typed channels, and traps.
- `provenance_service`: trusted claim lanes, hashes, manifests, and replay proof records.
- `signed_metric_service`: restricted signed-state benchmark descriptor service.
- `operator_shell`: operator-approved boot, diagnostics, and host-prep workflow surface.
- `host_bridge`: untrusted Buildroot/QEMU and host integration surface.

## Required Denials

- Guest code cannot directly write claim-lane or provenance records.
- Guest code cannot directly set signed membrane benchmark results.
- Host integration cannot directly mutate lattice state or staged writes.
- Signed metric computation cannot feed state changes back into geometry execution.
- Provenance services cannot rewrite geometry-kernel trace events.

## Evidence

Emit the proof:

```powershell
python .\tools\emit_isolation_proof.py --out .\runs\microkernel_isolation.json
```

Validate the proof:

```powershell
python .\tools\validate_artifact.py --schema .\specs\isolation-proof.schema.json .\runs\microkernel_isolation.json
```

Include it in release gate:

```powershell
python .\tools\pooleos_release_gate.py --bundle .\runs\six_support.pgb2.json --replay-proof .\runs\six_support.replay.json --isolation-proof .\runs\microkernel_isolation.json --out .\runs\release_gate.json
```

Bind it to PGB2-style trap checks:

```powershell
python .\tools\emit_capability_trap_proof.py --isolation-proof .\runs\microkernel_isolation.json --out .\runs\capability_trap_proof.json
```

## Next Kernel Work

- Attach the trap cases to concrete PGB2 bytecode encodings.
- Add property tests that generate unknown region/capability edges and require traps.
- Re-run the proof from inside the QEMU Lab image after boot evidence exists.
