#!/usr/bin/env python3
"""Audit the exact Git index against the PooleOS public publication boundary."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
from pathlib import Path
from typing import Any, Callable, Iterable


ROOT = Path(__file__).resolve().parents[1]
FORBIDDEN_PREFIXES = (
    "docs/archive",
    "firmware/private",
    "keys/private",
    "lab-os",
    "runs/archive",
    "secrets",
    "sources/buildroot-",
    "sources/pdc",
)
ALLOWED_RUNS = {
    "runs/adr_ratification_manifest.json",
    "runs/adr_ratification_manifest.json.sig",
    "runs/adr_ratification_readiness.json",
    "runs/adr_ratification_receipt.json",
    "runs/hardware_target_readiness.json",
    "runs/native_architecture_baseline.json",
    "runs/native_toolchain_qualification.json",
    "runs/native_v1_objectives_readiness.json",
    "runs/pdc_production_roadmap.json",
    "runs/pooleos_native_checklist_coverage.json",
    "runs/tier1_hardware_observation.json",
}
FORBIDDEN_SUFFIXES = (".img", ".iso", ".key", ".p12", ".pem", ".pfx", ".qcow2", ".vhdx", ".zip")
DOCUMENT_SUFFIXES = (".json", ".md", ".txt", ".toml", ".yaml", ".yml")
SECRET_PATTERNS = (
    ("pem_private_key", re.compile(rb"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----")),
    ("github_classic_token", re.compile(rb"ghp_[A-Za-z0-9]{30,}")),
    ("github_fine_grained_token", re.compile(rb"github_pat_[A-Za-z0-9_]{20,}")),
    ("openai_api_key", re.compile(rb"sk-(?:proj-)?[A-Za-z0-9_-]{20,}")),
    ("aws_access_key", re.compile(rb"AKIA[A-Z0-9]{16}")),
)
ABSOLUTE_USER_PATH = re.compile(
    rb"(?:[A-Za-z]:[\\/](?:Users|Documents and Settings)[\\/][^\\/\s]+|/(?:Users|home)/[^/\s]+)",
    flags=re.IGNORECASE,
)


def _git_index_paths(root: Path = ROOT) -> list[str]:
    completed = subprocess.run(
        ["git", "ls-files", "--cached", "-z"],
        cwd=root,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if completed.returncode != 0:
        raise RuntimeError("unable to enumerate the Git index")
    return sorted(
        (item.decode("utf-8", errors="strict").replace("\\", "/") for item in completed.stdout.split(b"\0") if item),
        key=lambda item: (item.casefold(), item),
    )


def _read_index_blob(relative_path: str, root: Path = ROOT) -> bytes:
    completed = subprocess.run(
        ["git", "show", f":{relative_path}"],
        cwd=root,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if completed.returncode != 0:
        raise RuntimeError(f"unable to read indexed blob: {relative_path}")
    return completed.stdout


def inspect_public_blob(relative_path: str, data: bytes) -> list[dict[str, str]]:
    path = relative_path.replace("\\", "/").lstrip("./")
    folded = path.casefold()
    violations: list[dict[str, str]] = []

    for prefix in FORBIDDEN_PREFIXES:
        prefix_folded = prefix.casefold()
        if folded == prefix_folded or folded.startswith(prefix_folded + "/") or (
            prefix.endswith("-") and folded.startswith(prefix_folded)
        ):
            violations.append(
                {
                    "type": "forbidden_path",
                    "path": path,
                    "detail": f"path crosses private or historical boundary {prefix}",
                }
            )
            break
    if folded.startswith("runs/") and path not in ALLOWED_RUNS:
        violations.append(
            {
                "type": "private_run_artifact",
                "path": path,
                "detail": "only explicitly allowlisted deterministic public ledgers may be published",
            }
        )
    if folded.endswith(FORBIDDEN_SUFFIXES):
        violations.append(
            {
                "type": "forbidden_file_type",
                "path": path,
                "detail": "release media, archives, and private-key containers require separate approval",
            }
        )
    if Path(path).name.casefold() in {".env", ".env.local", "credentials.json"}:
        violations.append(
            {
                "type": "credential_file",
                "path": path,
                "detail": "credential-bearing filename is prohibited",
            }
        )

    for name, pattern in SECRET_PATTERNS:
        if pattern.search(data):
            violations.append(
                {
                    "type": "secret_pattern",
                    "path": path,
                    "detail": name,
                }
            )
    if (folded.endswith(DOCUMENT_SUFFIXES) or Path(path).name in {"LICENSE", "NOTICE"}) and ABSOLUTE_USER_PATH.search(data):
        violations.append(
            {
                "type": "absolute_user_path",
                "path": path,
                "detail": "public documentation or artifact records a workstation-specific user path",
            }
        )
    return violations


def audit_paths(
    paths: Iterable[str],
    read_blob: Callable[[str], bytes],
) -> dict[str, Any]:
    normalized_paths = sorted({path.replace("\\", "/") for path in paths}, key=lambda item: (item.casefold(), item))
    violations: list[dict[str, str]] = []
    byte_count = 0
    for path in normalized_paths:
        try:
            data = read_blob(path)
        except (OSError, RuntimeError, subprocess.SubprocessError) as error:
            violations.append(
                {
                    "type": "unreadable_index_blob",
                    "path": path,
                    "detail": type(error).__name__,
                }
            )
            continue
        byte_count += len(data)
        violations.extend(inspect_public_blob(path, data))
    violations.sort(key=lambda item: (item["path"].casefold(), item["type"], item["detail"]))
    return {
        "schema_version": "1.0",
        "artifact_kind": "pooleos_publication_boundary_report",
        "scope": "git_index",
        "status": "pass" if not violations else "fail",
        "publication_allowed": not violations,
        "summary": {
            "indexed_path_count": len(normalized_paths),
            "indexed_byte_count": byte_count,
            "violation_count": len(violations),
        },
        "violations": violations,
        "claim_boundary": [
            "This scan supplements owner and legal review; it does not determine copyright, patent, export, trademark, or redistribution rights.",
            "The report inspects the Git index and does not approve ignored local evidence for publication.",
        ],
    }


def audit_git_index(root: Path = ROOT) -> dict[str, Any]:
    return audit_paths(_git_index_paths(root), lambda path: _read_index_blob(path, root))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args(argv)
    try:
        report = audit_git_index()
    except (OSError, RuntimeError, UnicodeError) as error:
        print(f"FAIL {type(error).__name__}: {error}")
        return 2
    encoded = json.dumps(report, indent=2, ensure_ascii=True) + "\n"
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(encoded, encoding="utf-8", newline="\n")
        print(
            f"wrote {args.out}: status={report['status']} "
            f"paths={report['summary']['indexed_path_count']} violations={report['summary']['violation_count']}"
        )
    else:
        print(encoded, end="")
    return 0 if report["publication_allowed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
