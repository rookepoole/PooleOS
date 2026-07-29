#!/usr/bin/env python3
"""Generate exact synthetic PKELF1 golden images and loaded-byte expectations."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from runtime import native_elf_loader as elf  # noqa: E402


DESCRIPTIONS = {
    "minimal_relative_v1": "Three canonical load segments, one RELRO page, two relative relocations, and one BSS page.",
    "alternate_base_v1": "Two-page RELRO image with 32 relocations loaded at independent physical and high-half virtual bases.",
    "maximum_relocations_v1": "Exact 4,096-relocation upper bound with a page-rounded RELRO table and retained writable BSS page.",
}


def _plan(plan: elf.ImagePlan) -> dict[str, Any]:
    return {
        "file_size": plan.file_size,
        "image_size": plan.image_size,
        "entry_offset": plan.entry_offset,
        "entry_virtual": plan.entry_virtual,
        "entry_physical": plan.entry_physical,
        "relocation_count": plan.relocation_count,
        "relro_offset": plan.relro_offset,
        "relro_size": plan.relro_size,
        "segments": [
            {
                "file_offset": segment.file_offset,
                "virtual_offset": segment.virtual_offset,
                "file_size": segment.file_size,
                "memory_size": segment.memory_size,
                "permissions": segment.permissions,
            }
            for segment in plan.segments
        ],
        "mappings": [
            {
                "virtual_offset": mapping.virtual_offset,
                "memory_size": mapping.memory_size,
                "permissions": mapping.permissions,
            }
            for mapping in plan.mappings
        ],
    }


def make_vectors() -> dict[str, Any]:
    vectors = []
    for profile in elf.vector_profiles():
        vector_id = str(profile["id"])
        physical_base = int(profile["physical_base"])
        virtual_base = int(profile["virtual_base"])
        data = elf.build_fixture(vector_id)
        plan, loaded = elf.load(data, physical_base, virtual_base)
        vectors.append(
            {
                "id": vector_id,
                "description": DESCRIPTIONS[vector_id],
                "synthetic": True,
                "physical_base": physical_base,
                "virtual_base": virtual_base,
                "file_byte_count": len(data),
                "file_sha256": elf.sha256_bytes(data),
                "file_hex": data.hex(),
                "image_byte_count": plan.image_size,
                "loaded_sha256": elf.sha256_bytes(loaded[: plan.image_size]),
                "semantic_summary": elf.semantic_summary(plan, loaded),
                "expected_plan": _plan(plan),
            }
        )
    return {
        "schema_version": "1.0",
        "artifact_kind": "pooleos_native_elf_loader_golden_vectors",
        "status_date": "2026-07-16",
        "contract_id": elf.CONTRACT_ID,
        "vectors": vectors,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, default=ROOT / elf.GOLDEN_RELATIVE)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    value = make_vectors()
    encoded = json.dumps(value, indent=2, sort_keys=True) + "\n"
    if args.check:
        if not args.out.is_file() or args.out.read_text(encoding="utf-8") != encoded:
            raise SystemExit("PKELF1 golden vectors are stale")
        errors = elf.golden_errors(value)
        if errors:
            raise SystemExit("; ".join(errors))
        print("PKELF1 golden vectors are exact")
        return 0
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(encoded, encoding="utf-8", newline="\n")
    print(f"wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
