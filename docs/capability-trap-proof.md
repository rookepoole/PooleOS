# Capability Trap Proof

Status: draft v0.1

The PGB2 draft requires every region/capability instruction to define trap behavior. The capability trap proof is a deterministic simulator over the current microkernel isolation policy.

It is not a booted-kernel enforcement result and does not claim production security isolation.

After Cycle 33, the proof can also consume `pooleos.permission_capability_matrix` evidence. Matrix operations use `ASSERT_MATRIX_PERMISSION` and classify PooleGlyph-derived permission paths as allowed or trapped while preserving the metadata-only boundary.

After Cycle 34, the proof can also consume `pooleos.capability_trap_fuzz` evidence. Fuzz operations are deterministic generated denials for unknown capability edges and unknown PooleGlyph permission paths.

## Covered Instruction Family

- `DEFINE_REGION`
- `ENTER_REGION`
- `ASSERT_REGION_CAP`
- `SNAPSHOT_REGION`

The first proof exercises `ASSERT_REGION_CAP` and `SNAPSHOT_REGION` decisions against known allowed and denied region/capability edges.

## Trap Codes

- `CAPABILITY_DENIED`: the attempted edge is explicitly denied by the isolation policy.
- `CAPABILITY_UNKNOWN`: the attempted edge is neither allowed nor explicitly denied and must trap closed.
- `POOLEGLYPH_PERMISSION_DENIED`: the attempted permission path is denied by the PooleGlyph-derived permission/capability matrix.
- Empty trap code: the operation is allowed and did not trap.

## Evidence

Emit the trap proof:

```powershell
python .\tools\emit_capability_trap_fuzz.py --isolation-proof .\runs\microkernel_isolation.json --permission-capability-matrix .\runs\permission_capability_matrix.json --out .\runs\capability_trap_fuzz.json
python .\tools\emit_capability_trap_proof.py --isolation-proof .\runs\microkernel_isolation.json --permission-capability-matrix .\runs\permission_capability_matrix.json --capability-trap-fuzz .\runs\capability_trap_fuzz.json --out .\runs\capability_trap_proof.json
```

Validate it:

```powershell
python .\tools\validate_artifact.py --schema .\specs\capability-trap-proof.schema.json .\runs\capability_trap_proof.json
```

## Next Kernel Work

- Attach these cases to concrete PGB2 bytecode encodings.
- Add property tests for unknown region/capability edges.
- Re-run the same cases inside the QEMU Lab image after boot evidence exists.
