#!/usr/bin/env python3
"""Build one deterministic ordinary-file GPT/FAT32 PooleBoot proof image."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from runtime.native_pooleboot import (  # noqa: E402
    MAX_EFI_BYTES,
    PooleBootError,
    build_media_bytes,
    inspect_media_bytes,
    validate_workspace_input_file,
    validate_workspace_output_path,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--efi", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--inspection", type=Path)
    args = parser.parse_args(argv)
    try:
        efi_path = validate_workspace_input_file(ROOT, args.efi, ".efi", MAX_EFI_BYTES)
        output_path = validate_workspace_output_path(ROOT, args.out, ".img")
        inspection_path = (
            validate_workspace_output_path(ROOT, args.inspection, ".json")
            if args.inspection
            else None
        )
        efi_data = efi_path.read_bytes()
        media = build_media_bytes(efi_data)
        inspection = inspect_media_bytes(media)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path = validate_workspace_output_path(ROOT, output_path, ".img")
        output_path.write_bytes(media)
        if inspection_path:
            inspection_path.parent.mkdir(parents=True, exist_ok=True)
            inspection_path = validate_workspace_output_path(ROOT, inspection_path, ".json")
            inspection_path.write_text(
                json.dumps(inspection, indent=2, ensure_ascii=True) + "\n",
                encoding="utf-8",
                newline="\n",
            )
    except (OSError, ValueError, PooleBootError) as error:
        print(f"POOLEBOOT_MEDIA FAIL {type(error).__name__}: {error}")
        return 1
    print(
        "POOLEBOOT_MEDIA PASS "
        f"bytes={inspection['image']['byte_count']} sha256={inspection['image']['sha256']} "
        f"efi={inspection['files'][0]['sha256']} physical_media=false"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
