# Capability Trap Fuzz

Capability trap fuzzing adds deterministic closed-by-default evidence to the PooleOS trap simulator.

The fuzzer emits two bounded case families:

- unknown region/capability edges, which must trap with `CAPABILITY_UNKNOWN`;
- unknown PooleGlyph permission paths, which must trap with `POOLEGLYPH_PERMISSION_DENIED`.

The fuzzer is intentionally deterministic. It is not exhaustive formal verification and does not claim a booted kernel security boundary. Its job is to prove that generated unknown edges trap closed before the same cases are later attached to concrete PGB2 bytecode encodings and QEMU Lab image evidence.

Emit it with:

```powershell
python .\tools\emit_capability_trap_fuzz.py --isolation-proof .\runs\microkernel_isolation.json --permission-capability-matrix .\runs\permission_capability_matrix.json --out .\runs\capability_trap_fuzz.json
python .\tools\emit_capability_trap_proof.py --isolation-proof .\runs\microkernel_isolation.json --permission-capability-matrix .\runs\permission_capability_matrix.json --capability-trap-fuzz .\runs\capability_trap_fuzz.json --out .\runs\capability_trap_proof.json
```
