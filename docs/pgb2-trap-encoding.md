# PGB2 Trap Encoding

The PGB2 trap encoding artifact converts capability trap proof operations into deterministic draft bytes.

Encoding version: `PGB2_TRAP_DRAFT_V0`

The draft opcode table is:

- `E0`: `ASSERT_REGION_CAP`
- `E1`: `SNAPSHOT_REGION`
- `E2`: `ASSERT_MATRIX_PERMISSION`

Each instruction stores:

- opcode byte;
- length-prefixed UTF-8 `region`;
- length-prefixed UTF-8 `source`;
- length-prefixed UTF-8 `target`;
- length-prefixed UTF-8 `capability`;
- one-byte `expected_trap`;
- length-prefixed UTF-8 `trap_code`.

This is not a frozen ABI. It is a round-trip checked bridge from simulator operation records toward encoded instruction evidence.

After emitting this artifact, `pgb2-trap-execution.md` describes the byte-level simulator that walks the concatenated program and recomputes the trap outcomes from the encoded stream.

Emit it with:

```powershell
python .\tools\emit_pgb2_trap_encoding.py --trap-proof .\runs\capability_trap_proof.json --out .\runs\pgb2_trap_encoding.json
python .\tools\validate_artifact.py --schema .\specs\pgb2-trap-encoding.schema.json .\runs\pgb2_trap_encoding.json
```
