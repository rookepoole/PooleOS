#!/usr/bin/env python3
"""Check an extracted PooleOS release tree for native-architecture policy violations."""

from __future__ import annotations

import argparse
import fnmatch
import hashlib
import json
import os
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_POLICY = ROOT / "specs" / "native-release-architecture-policy.json"


@dataclass(frozen=True)
class TreeEntry:
    relative_path: str
    path: Path
    kind: str
    is_symlink: bool


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest().upper()


def _relative_posix(root: Path, path: Path) -> str:
    return path.relative_to(root).as_posix()


def _path_matches(path: str, pattern: str, *, case_insensitive: bool) -> bool:
    candidate = path.casefold() if case_insensitive else path
    rule = pattern.casefold() if case_insensitive else pattern
    if rule.endswith("/**") and candidate == rule[:-3]:
        return True
    return fnmatch.fnmatchcase(candidate, rule)


def _matches_any(path: str, patterns: Iterable[str], *, case_insensitive: bool) -> bool:
    return any(_path_matches(path, pattern, case_insensitive=case_insensitive) for pattern in patterns)


def casefold_collisions(paths: Iterable[str]) -> list[list[str]]:
    """Return deterministic sets of distinct paths that collide when case-folded."""
    grouped: dict[str, list[str]] = {}
    for path in paths:
        grouped.setdefault(path.casefold(), []).append(path)
    return [
        sorted(set(group))
        for _, group in sorted(grouped.items())
        if len(set(group)) > 1
    ]


def _inventory_tree(root: Path) -> tuple[list[TreeEntry], list[dict[str, str]]]:
    entries: list[TreeEntry] = []
    errors: list[dict[str, str]] = []

    def on_error(error: OSError) -> None:
        errors.append(
            {
                "type": "inventory_error",
                "path": "<unreadable>",
                "rule": "tree_must_be_fully_inventoryable",
                "detail": type(error).__name__,
            }
        )

    for current, directory_names, file_names in os.walk(root, topdown=True, followlinks=False, onerror=on_error):
        directory_names.sort(key=lambda item: (item.casefold(), item))
        file_names.sort(key=lambda item: (item.casefold(), item))
        current_path = Path(current)
        for name in directory_names:
            path = current_path / name
            entries.append(TreeEntry(_relative_posix(root, path), path, "directory", path.is_symlink()))
        for name in file_names:
            path = current_path / name
            entries.append(TreeEntry(_relative_posix(root, path), path, "file", path.is_symlink()))
    entries.sort(key=lambda item: (item.relative_path.casefold(), item.relative_path))
    return entries, errors


def scan_release_tree(root: Path, policy_path: Path = DEFAULT_POLICY, *, input_id: str | None = None) -> dict[str, Any]:
    root = root.resolve()
    policy_bytes = policy_path.read_bytes()
    policy = json.loads(policy_bytes.decode("utf-8-sig"))
    if not root.is_dir():
        raise ValueError("release root must be an existing directory")

    entries, violations = _inventory_tree(root)
    if root.is_symlink() and policy["reject_symbolic_links"]:
        violations.append(
            {
                "type": "symbolic_link",
                "path": ".",
                "rule": "reject_symbolic_links",
                "detail": "release root is a symbolic link",
            }
        )

    case_insensitive = bool(policy["path_matching_case_insensitive"])
    entry_by_key: dict[str, TreeEntry] = {}
    for entry in entries:
        key = entry.relative_path.casefold() if case_insensitive else entry.relative_path
        entry_by_key.setdefault(key, entry)

        if policy["reject_symbolic_links"] and entry.is_symlink:
            violations.append(
                {
                    "type": "symbolic_link",
                    "path": entry.relative_path,
                    "rule": "reject_symbolic_links",
                    "detail": "symbolic links are prohibited in release media",
                }
            )
        if policy["reject_non_nfc_paths"] and unicodedata.normalize("NFC", entry.relative_path) != entry.relative_path:
            violations.append(
                {
                    "type": "non_nfc_path",
                    "path": entry.relative_path,
                    "rule": "reject_non_nfc_paths",
                    "detail": "path is not Unicode NFC normalized",
                }
            )
        if _matches_any(
            entry.relative_path,
            policy["forbidden_path_globs"],
            case_insensitive=case_insensitive,
        ):
            matching_rule = next(
                pattern
                for pattern in policy["forbidden_path_globs"]
                if _path_matches(entry.relative_path, pattern, case_insensitive=case_insensitive)
            )
            violations.append(
                {
                    "type": "forbidden_path",
                    "path": entry.relative_path,
                    "rule": matching_rule,
                    "detail": "path matches a prohibited production-substitute pattern",
                }
            )

    if policy["reject_casefold_path_collisions"]:
        for paths in casefold_collisions(entry.relative_path for entry in entries):
            violations.append(
                {
                    "type": "casefold_collision",
                    "path": " | ".join(paths),
                    "rule": "reject_casefold_path_collisions",
                    "detail": "multiple paths collapse to the same case-insensitive name",
                }
            )

    required_results: list[dict[str, str]] = []
    for required_path in policy["required_paths"]:
        key = required_path.casefold() if case_insensitive else required_path
        entry = entry_by_key.get(key)
        if entry is None:
            required_results.append({"path": required_path, "status": "missing"})
            violations.append(
                {
                    "type": "required_path_missing",
                    "path": required_path,
                    "rule": "required_paths",
                    "detail": "required native release object is absent",
                }
            )
        elif entry.kind != "file":
            required_results.append({"path": required_path, "status": "wrong_type"})
            violations.append(
                {
                    "type": "required_path_wrong_type",
                    "path": entry.relative_path,
                    "rule": "required_paths",
                    "detail": "required native release object is not a regular file",
                }
            )
        else:
            required_results.append({"path": required_path, "status": "present"})

    scanned_file_count = 0
    scanned_byte_count = 0
    maximum_bytes = int(policy["maximum_scanned_file_bytes"])
    marker_case_insensitive = bool(policy["content_matching_case_insensitive"])
    for entry in entries:
        if entry.kind != "file" or entry.is_symlink:
            continue
        if not _matches_any(
            entry.relative_path,
            policy["content_scan_globs"],
            case_insensitive=case_insensitive,
        ):
            continue
        try:
            size = entry.path.stat().st_size
        except OSError as error:
            violations.append(
                {
                    "type": "content_stat_error",
                    "path": entry.relative_path,
                    "rule": "content_scan_globs",
                    "detail": type(error).__name__,
                }
            )
            continue
        if size > maximum_bytes:
            violations.append(
                {
                    "type": "content_scan_size_exceeded",
                    "path": entry.relative_path,
                    "rule": "maximum_scanned_file_bytes",
                    "detail": f"file size {size} exceeds scan ceiling {maximum_bytes}",
                }
            )
            continue
        try:
            content = entry.path.read_bytes()
        except OSError as error:
            violations.append(
                {
                    "type": "content_read_error",
                    "path": entry.relative_path,
                    "rule": "content_scan_globs",
                    "detail": type(error).__name__,
                }
            )
            continue
        scanned_file_count += 1
        scanned_byte_count += len(content)
        haystack = content.lower() if marker_case_insensitive else content
        for marker in policy["forbidden_ascii_markers"]:
            needle = marker.encode("ascii")
            if marker_case_insensitive:
                needle = needle.lower()
            if needle in haystack:
                violations.append(
                    {
                        "type": "forbidden_content_marker",
                        "path": entry.relative_path,
                        "rule": marker,
                        "detail": "scanned release object contains a prohibited production-substitute marker",
                    }
                )

    violations.sort(key=lambda item: (item["path"].casefold(), item["type"], item["rule"], item["detail"]))
    passed = not violations
    return {
        "schema_version": "1.0",
        "artifact_kind": "pooleos_native_release_architecture_report",
        "input": {
            "id": input_id or root.name,
            "kind": policy["input_kind"],
            "absolute_path_recorded": False,
        },
        "policy": {
            "version": policy["policy_version"],
            "path": policy_path.name,
            "sha256": _sha256(policy_bytes),
        },
        "status": "pass" if passed else "fail",
        "architecture_conformance_passed": passed,
        "production_promotion_allowed": False,
        "summary": {
            "entry_count": len(entries),
            "file_count": sum(entry.kind == "file" for entry in entries),
            "directory_count": sum(entry.kind == "directory" for entry in entries),
            "required_path_count": len(required_results),
            "required_path_missing_count": sum(item["status"] != "present" for item in required_results),
            "content_scanned_file_count": scanned_file_count,
            "content_scanned_byte_count": scanned_byte_count,
            "violation_count": len(violations),
        },
        "required_paths": required_results,
        "violations": violations,
        "limitations": list(policy["limitations"]),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True, help="Extracted release tree to inspect")
    parser.add_argument("--policy", type=Path, default=DEFAULT_POLICY)
    parser.add_argument("--input-id", help="Public identifier recorded instead of a local path")
    parser.add_argument("--out", type=Path)
    args = parser.parse_args(argv)

    try:
        report = scan_release_tree(args.root, args.policy, input_id=args.input_id)
    except (OSError, ValueError, json.JSONDecodeError) as error:
        print(f"FAIL {type(error).__name__}: {error}")
        return 2

    encoded = json.dumps(report, indent=2, ensure_ascii=True) + "\n"
    if args.out is None:
        print(encoded, end="")
    else:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(encoded, encoding="utf-8", newline="\n")
        print(
            f"wrote {args.out}: status={report['status']} "
            f"violations={report['summary']['violation_count']}"
        )
    return 0 if report["architecture_conformance_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
