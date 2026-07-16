# PGB2 Trap Execution

The PGB2 trap execution artifact decodes the concatenated `PGB2_TRAP_DRAFT_V0` byte program and checks that every instruction preserves the expected trap outcome from the prior capability proof.

Execution version: `PGB2_TRAP_EXEC_DRAFT_V0`

The simulator verifies:

- the raw hex program decodes into complete instructions;
- every instruction advances by its measured byte length;
- the computed program SHA-256 matches the encoding artifact;
- decoded operands match the encoding manifest in order;
- trap and allow outcomes match the source proof metadata;
- all bytes are consumed with no trailing or truncated data.

This is byte-level simulator evidence, not booted kernel execution and not a hardware isolation claim.

When bundled, the matching artifacts are stored as `TRAP_ENCODING` and `TRAP_EXECUTION` sections. Bundle validation checks both schemas and cross-checks program SHA-256, byte length, instruction count, byte consumption, and outcome mismatch count.

Emit it with:

```powershell
python .\tools\emit_pgb2_trap_execution.py --trap-encoding .\runs\pgb2_trap_encoding.json --out .\runs\pgb2_trap_execution.json
python .\tools\validate_artifact.py --schema .\specs\pgb2-trap-execution.schema.json .\runs\pgb2_trap_execution.json
```
