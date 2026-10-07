#!/usr/bin/env python3
"""Read an ordinary ISO file and inspect its actual ISO and EFI namespaces."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import stat
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from runtime import native_iso_media as media
from tools.check_native_release_architecture import DEFAULT_POLICY, _matches_any


def scan_iso(data: bytes, policy_path: Path = DEFAULT_POLICY) -> dict:
    policy_bytes = policy_path.read_bytes()
    policy = json.loads(policy_bytes)
    result = {"format": "POOLEOS-ISO-ARCHITECTURE-1", "iso_sha256": hashlib.sha256(data).hexdigest().upper(),
              "byte_count": len(data), "policy_sha256": hashlib.sha256(policy_bytes).hexdigest().upper(),
              "status": "fail", "structural_passed": False, "architecture_conformance_passed": False,
              "production_ready": False, "production_promotion_allowed": False, "files": [], "violations": [],
              "limitations": ["Bounded optical ISO9660 and mirrored FAT32 profile only; unsupported layouts reject.",
                              "Required objects must be in the EFI tree for this profile.",
                              "No executable provenance, signature, boot, hardware or production qualification.",
                              "Known-marker absence does not prove native authorship or absence of all substitutes."]}
    try:
        inventory = media.inspect(data)
    except media.MediaError as error:
        result["violations"].append({"type": "media_structure", "path": "<image>", "rule": str(error)})
        return result
    result["structural_passed"] = not inventory["structural_issues"]
    for issue in inventory["structural_issues"]:
        result["violations"].append({"type": "media_structure", "path": "esp", "rule": issue})
    for namespace in ("iso", "esp"):
        for path, item in sorted(inventory[namespace].items()):
            for spelling in (path, *item["aliases"]):
                for pattern in policy["forbidden_path_globs"]:
                    if _matches_any(spelling, [pattern], case_insensitive=policy["path_matching_case_insensitive"]):
                        result["violations"].append({"type": "forbidden_path", "path": namespace + ":/" + spelling, "rule": pattern})
            content = item["data"]
            if content is None:
                continue
            result["files"].append({"namespace": namespace, "path": path, "byte_count": len(content),
                                    "sha256": hashlib.sha256(content).hexdigest().upper(), "aliases": list(item["aliases"])})
            # The embedded FAT image is scanned as decoded files; inspect every other file, regardless of extension.
            if namespace == "iso" and path == inventory["esp_path"]:
                continue
            haystack = content.lower() if policy["content_matching_case_insensitive"] else content
            for marker in policy["forbidden_ascii_markers"]:
                needle = marker.encode("ascii")
                if policy["content_matching_case_insensitive"]:
                    needle = needle.lower()
                if needle in haystack:
                    result["violations"].append({"type": "forbidden_content_marker", "path": namespace + ":/" + path, "rule": marker})
    inner_files = {p.casefold(): v["data"] for p, v in inventory["esp"].items()}
    for required in policy["required_paths"]:
        if not inner_files.get(required.casefold()):
            result["violations"].append({"type": "required_path_missing_or_empty", "path": "esp:/" + required, "rule": "required_paths"})
    # Inspect metadata and allocation bytes too; decoded files catch fragmented markers.
    haystack = data.lower() if policy["content_matching_case_insensitive"] else data
    found = {v["rule"] for v in result["violations"] if v["type"] == "forbidden_content_marker"}
    for marker in policy["forbidden_ascii_markers"]:
        needle = marker.encode("ascii")
        if policy["content_matching_case_insensitive"]:
            needle = needle.lower()
        if marker not in found and needle in haystack:
            result["violations"].append({"type": "forbidden_content_marker", "path": "<image>", "rule": marker})
    passed = not result["violations"]
    result.update(status="pass" if passed else "fail", architecture_conformance_passed=passed)
    return result


def inspect_file(path: Path) -> dict:
    require_regular = path.stat()
    if not stat.S_ISREG(require_regular.st_mode) or require_regular.st_size > media.MAX_IMAGE:
        raise media.MediaError("input must be a bounded ordinary file")
    with path.open("rb") as stream:
        data = stream.read(media.MAX_IMAGE + 1)
    return scan_iso(data)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--iso", required=True, type=Path)
    parser.add_argument("--out", type=Path, help="New report file; existing evidence is never overwritten")
    args = parser.parse_args(argv)
    try:
        report = inspect_file(args.iso)
        encoded = json.dumps(report, indent=2, ensure_ascii=True) + "\n"
        if args.out:
            with args.out.open("x", encoding="utf-8", newline="\n") as stream:
                stream.write(encoded)
        else:
            print(encoded, end="")
        return 0 if report["architecture_conformance_passed"] else 1
    except (OSError, ValueError) as error:
        print("FAIL " + type(error).__name__ + ": ISO inspection did not complete")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
