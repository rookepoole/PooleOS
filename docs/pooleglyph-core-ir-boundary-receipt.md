# PooleGlyph Core IR Boundary Receipt

The PooleGlyph Core IR boundary receipt is the release-gated artifact that separates three ideas that must not be blended:

- PooleGlyph v0.5-dev metadata declarations;
- public Core IR structural validation outputs;
- future PooleOS parser-to-kernel readiness.

The current PooleGlyph package contains public `.coreir.validate.json` outputs. Some are valid zero-program metadata outputs. Some are valid nonzero executable candidates. The validator also carries expected negative fixtures such as out-of-range `k`, missing `halt`, and unknown instructions.

This receipt records that boundary explicitly. In the current Phase 65 state it should report `phase66_pending`, keep `parser_to_kernel_promotion_allowed` false, and keep `kernel_enforcement_claimed` false.

Emit it with:

```powershell
python .\tools\emit_pooleglyph_core_ir_boundary_receipt.py --bridge-manifest .\runs\pooleglyph_bridge_manifest.json --pooleglyph <POOLEGYPH_REPO> --out .\runs\pooleglyph_core_ir_boundary_receipt.json
python .\tools\validate_artifact.py --schema .\specs\pooleglyph-core-ir-boundary-receipt.schema.json .\runs\pooleglyph_core_ir_boundary_receipt.json
```

Release-gate it with:

```powershell
python .\tools\pooleos_release_gate.py --pooleglyph-source-anchor .\runs\pooleglyph_source_anchor.json --pooleglyph-bridge-manifest .\runs\pooleglyph_bridge_manifest.json --pooleglyph-core-ir-boundary-receipt .\runs\pooleglyph_core_ir_boundary_receipt.json --out .\runs\release_gate.json
```

Accepted non-promoting evidence means the receipt has no failed hard checks, no unexpected invalid Core IR validation outputs, and no kernel enforcement claim. It does not mean the PooleOS kernel executes PooleGlyph Core IR.
