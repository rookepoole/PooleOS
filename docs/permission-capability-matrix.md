# Permission Capability Matrix

The permission/capability/resource matrix converts public PooleGlyph v0.5-dev metadata into a PooleOS security-planning artifact.

It reads the PooleGlyph bridge manifest plus public symbol outputs for:

- `capability`;
- `resource`;
- `permission`;
- `policy`;
- `contract`.

The matrix resolves:

- declared capabilities;
- declared resources;
- declared permissions;
- policy `allow permission ...` references;
- contract `require policy ...` references;
- metadata-derived resource permission candidates;
- matrix-derived trap operations for the PooleOS capability trap simulator.

This artifact is intentionally conservative. Resource-permission links are name-derived until the PooleGlyph Phase 66 Core IR boundary audit provides stronger public linkage. The matrix does not claim booted kernel enforcement, hardware isolation, or a frozen ABI.

The matrix requires `pooleglyph_core_ir_boundary_receipt.json`, `pooleglyph_core_ir_executable_audit.json`, and `pooleglyph_parser_kernel_promotion_receipt.json`. Each resource-permission row and trap operation carries the receipt-derived binding mode plus the executable audit and parser promotion status. In the current Phase 65 state, the binding mode is `metadata_only_non_promoting` and the parser promotion receipt is `blocked_until_phase66`: PooleOS can distinguish metadata-only zero-program Core IR outputs from nonzero public Core IR executable candidates, but it cannot claim parser-to-kernel readiness.

Emit it with:

```powershell
python .\tools\emit_permission_capability_matrix.py --bridge-manifest .\runs\pooleglyph_bridge_manifest.json --core-ir-boundary-receipt .\runs\pooleglyph_core_ir_boundary_receipt.json --core-ir-executable-audit .\runs\pooleglyph_core_ir_executable_audit.json --parser-kernel-promotion-receipt .\runs\pooleglyph_parser_kernel_promotion_receipt.json --pooleglyph <POOLEGYPH_REPO> --out .\runs\permission_capability_matrix.json
python .\tools\validate_artifact.py --schema .\specs\permission-capability-matrix.schema.json .\runs\permission_capability_matrix.json
```
