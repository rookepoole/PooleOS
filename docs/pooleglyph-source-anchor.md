# PooleGlyph Source Anchor

Status: draft v0.1

PooleOS and PooleGlyph are being developed in tandem. The source anchor records which live PooleGlyph tree PooleOS verification is currently using, plus the latest local checkpoint manifest.

Current intended live path:

```text
<POOLEGYPH_REPO>
```

The anchor is read-only evidence. It does not modify, stage, commit, tag, branch, or push the PooleGlyph repository.

## Evidence

Emit the anchor:

```powershell
python .\tools\emit_pooleglyph_source_anchor.py --pooleglyph <POOLEGYPH_REPO> --out .\runs\pooleglyph_source_anchor.json
```

Validate it:

```powershell
python .\tools\validate_artifact.py --schema .\specs\pooleglyph-source-anchor.schema.json .\runs\pooleglyph_source_anchor.json
```

Include it in release gate:

```powershell
python .\tools\pooleos_release_gate.py --bundle .\runs\six_support.pgb2.json --replay-proof .\runs\six_support.replay.json --pooleglyph-source-anchor .\runs\pooleglyph_source_anchor.json --out .\runs\release_gate.json
```

## Checkpoint Signal

The current checkpoint lineage should capture PooleGlyph v0.5-dev language phases. The checkpoint folder has advanced through Phase 65 diagnostic hardening, with Phase 66 Core IR boundary audit listed as the next recommended language move.

The anchor parser accepts both checkpoint manifest styles used so far:

- early manifests with `checkpoint`, `sha256`, and `zip_path`;
- later manifests with `phase`, `phase_name`, `checkpoint_zip_sha256`, and `checkpoint_zip_path`.
