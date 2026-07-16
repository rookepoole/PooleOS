# PooleGlyph Bridge Manifest

The PooleGlyph bridge manifest is the first PooleOS artifact that consumes the verified PooleGlyph v0.5-dev checkpoint surface directly.

It reads:

- a PooleOS PooleGlyph source anchor;
- `language_surface_inventory.json`;
- `diagnostic_hardening_manifest.json`;
- the public v0.5-dev language spec;
- the spec sync matrix;
- the PooleOS reoriented plan.

It also carries a `core_ir_boundary` section that points to `pooleos.pooleglyph_core_ir_boundary_receipt`. The bridge manifest remains metadata-only; the receipt is the artifact that distinguishes valid zero-program metadata outputs from nonzero public Core IR executable candidates.

The manifest groups PooleGlyph declarations into PooleOS integration lanes:

- ABI and package surface;
- capability, permission, policy, and contract security;
- target, deployment, entrypoint, service, lifecycle, and schedule boot graph inputs;
- resource, interface, adapter, binding, route, channel, endpoint, port, and gateway service graph inputs;
- node, cluster, mesh, fabric, and higher topology descriptors;
- diagnostic/source-map evidence.

This is intentionally metadata-only. It does not freeze PGB2, prove runtime behavior, claim kernel enforcement, or expose private PooleMath runtime methods. Its job is to make the live PooleGlyph checkpoint surface release-gated and consumable by later PooleOS artifacts.

Before claiming parser-to-kernel readiness, emit and release-gate the Core IR boundary receipt. In the current Phase 65 state the receipt should be `phase66_pending` and non-promoting.

Emit it with:

```powershell
python .\tools\emit_pooleglyph_bridge_manifest.py --source-anchor .\runs\pooleglyph_source_anchor.json --pooleglyph <POOLEGYPH_REPO> --out .\runs\pooleglyph_bridge_manifest.json
python .\tools\validate_artifact.py --schema .\specs\pooleglyph-bridge-manifest.schema.json .\runs\pooleglyph_bridge_manifest.json
python .\tools\emit_pooleglyph_core_ir_boundary_receipt.py --bridge-manifest .\runs\pooleglyph_bridge_manifest.json --pooleglyph <POOLEGYPH_REPO> --out .\runs\pooleglyph_core_ir_boundary_receipt.json
python .\tools\validate_artifact.py --schema .\specs\pooleglyph-core-ir-boundary-receipt.schema.json .\runs\pooleglyph_core_ir_boundary_receipt.json
```
