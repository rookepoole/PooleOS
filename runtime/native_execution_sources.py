"""Invalidate retained profile evidence when its static Python inputs change."""

from __future__ import annotations

import ast
import hashlib
import json
import re
from pathlib import Path, PurePosixPath
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
RECEIPT = "runs/native_execution_sources.json"
PROFILES = (
    "entry", "symbols", "policy", "load", "pooleboot", "revalidation", "transfer",
    "trap", "cpu_policy", "errata_policy", "xstate_policy", "xstate_exception",
    "privilege_msr_policy",
    "physical_memory", "virtual_memory", "interrupt_time", "smp_first_ap",
    "smp_percpu_runtime", "smp_ipi", "scheduler", "scheduler_preempt",
    "scheduler_deferred", "scheduler_smp", "scheduler_ap_workers",
    "scheduler_smp_preempt", "atomics", "locks",
)
BOUNDARIES = {
    "static_python_sources_only": True,
    "fresh_guest_execution": False,
    "authentication": False,
    "independent_builder": False,
    "dynamic_data_and_tool_closure": False,
    "production_ready": False,
}


class SourceEvidenceError(ValueError):
    pass


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest().upper()


def canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def safe_path(root: Path, relative: str) -> Path:
    if (not isinstance(relative, str) or not relative or "\\" in relative or ":" in relative
            or PurePosixPath(relative).is_absolute() or ".." in PurePosixPath(relative).parts
            or PurePosixPath(relative).as_posix() != relative):
        raise SourceEvidenceError("noncanonical repository path")
    path = root / relative
    if not path.resolve().is_relative_to(root.resolve()):
        raise SourceEvidenceError("repository path escapes root")
    return path


def binding(root: Path, relative: str) -> dict[str, str]:
    return {"path": relative, "sha256": digest(safe_path(root, relative).read_bytes())}


def profile_paths(profile: str) -> tuple[str, tuple[str, str]]:
    if profile not in PROFILES:
        raise SourceEvidenceError("unknown execution profile")
    upstream = {
        "entry": ("kernel_entry", "kernel_entry"),
        "symbols": ("symbols", "symbol"),
        "policy": ("policy", "policy"),
        "load": ("kernel_load", "kernel_load"),
        "pooleboot": ("pooleboot", "pooleboot"),
    }
    if profile in upstream:
        module, receipt = upstream[profile]
        return (f"runs/native_{receipt}_readiness.json",
                (f"runtime/native_{module}.py", f"tools/qualify_native_{module}.py"))
    suffix = "scheduler-preemption" if profile == "scheduler_preempt" else profile.replace("_", "-")
    return (f"runs/native-kernel-{suffix}-readiness.json",
            (f"runtime/native_kernel_{profile}.py", f"tools/qualify_native_kernel_{profile}.py"))


def _modules(root: Path, name: str, required: bool = False) -> set[str]:
    parts = name.split(".")
    if parts[0] not in ("runtime", "tools", "tests"):
        return set()
    if not all(part.isidentifier() for part in parts):
        raise SourceEvidenceError("invalid local module name")
    base = "/".join(parts)
    candidates = (base + ".py", base + "/__init__.py")
    target = next((p for p in candidates if safe_path(root, p).is_file()), None)
    if target is None and required and not safe_path(root, base).is_dir():
        raise SourceEvidenceError("missing local module: " + name)
    result = {target} if target else set()
    for index in range(1, len(parts)):
        package = "/".join(parts[:index]) + "/__init__.py"
        if safe_path(root, package).is_file():
            result.add(package)
    return result


def source_closure(root: Path, roots: tuple[str, ...]) -> list[dict[str, str]]:
    pending, visited = list(roots), set()
    while pending:
        path = pending.pop()
        if path in visited:
            continue
        visited.add(path)
        tree = ast.parse(safe_path(root, path).read_text(encoding="utf-8-sig"), filename=path)
        package = path.removesuffix(".py").split("/")[:-1]
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    pending.extend(_modules(root, alias.name, required=True))
            elif isinstance(node, ast.ImportFrom):
                if node.level:
                    if node.level > len(package):
                        raise SourceEvidenceError("relative import escapes package")
                    base = ".".join(package[:len(package) - node.level + 1])
                    name = base + ("." + node.module if node.module else "")
                else:
                    name = node.module or ""
                pending.extend(_modules(root, name, required=True))
                for alias in node.names:
                    if alias.name != "*":
                        pending.extend(_modules(root, name + "." + alias.name))
            elif isinstance(node, ast.Call):
                func = node.func
                name = func.id if isinstance(func, ast.Name) else func.attr if isinstance(func, ast.Attribute) else ""
                if name in ("__import__", "import_module", "spec_from_file_location", "exec_module", "exec", "eval"):
                    raise SourceEvidenceError("dynamic code/import requires separate review: " + path)
    return [binding(root, path) for path in sorted(visited)]


def _exact_keys(value: Any, keys: set[str], label: str) -> None:
    if not isinstance(value, dict) or set(value) != keys:
        raise SourceEvidenceError(label + " fields changed")


def _hash(value: Any) -> None:
    if not isinstance(value, str) or re.fullmatch("[0-9A-F]{64}", value) is None:
        raise SourceEvidenceError("invalid SHA-256")


def evidence_errors(value: Any, root: Path = ROOT) -> list[str]:
    try:
        _exact_keys(value, {"format", "profiles", "boundaries"}, "source evidence")
        if value["format"] != "POOLEOS-STATIC-EXECUTION-SOURCES-1" or canonical(value["boundaries"]) != canonical(BOUNDARIES):
            raise SourceEvidenceError("source evidence contract changed")
        records = value["profiles"]
        if not isinstance(records, list) or len(records) != len(PROFILES):
            raise SourceEvidenceError("profile coverage changed")
        for profile, record in zip(PROFILES, records, strict=True):
            _exact_keys(record, {"profile", "receipt", "sources", "capture"}, "profile")
            if record["profile"] != profile:
                raise SourceEvidenceError("profile order/identity changed")
            receipt, roots = profile_paths(profile)
            if canonical(record["receipt"]) != canonical(binding(root, receipt)):
                raise SourceEvidenceError(profile + " receipt changed")
            if canonical(record["sources"]) != canonical(source_closure(root, roots)):
                raise SourceEvidenceError(profile + " static dependency closure changed")
            capture = record["capture"]
            _exact_keys(capture, {"record_sha256", "log_sha256", "source_snapshot_sha256",
                                 "return_code", "source_unchanged"}, "capture")
            for field in ("record_sha256", "log_sha256", "source_snapshot_sha256"):
                _hash(capture[field])
            if type(capture["return_code"]) is not int or capture["return_code"] != 0 or capture["source_unchanged"] is not True:
                raise SourceEvidenceError("capture did not complete with unchanged source")
    except (SourceEvidenceError, OSError, SyntaxError, ValueError, TypeError, KeyError, RecursionError) as error:
        return [f"execution source evidence invalid: {error}"]
    return []


def captured_profile(profile: str, capture_path: Path, root: Path = ROOT) -> dict[str, Any]:
    """Project original captures; never replace their input hashes with current ones."""
    raw = capture_path.read_bytes()
    capture = json.loads(raw)
    if (not isinstance(capture, dict) or type(capture.get("return_code")) is not int or capture["return_code"] != 0
            or capture.get("source_unchanged") is not True or capture.get("changed_paths") != []):
        raise SourceEvidenceError("unsuccessful or changed-source execution capture")
    receipt_path, roots = profile_paths(profile)
    command = capture["command"]
    qualifier = roots[1]
    if (not isinstance(command, list) or len(command) < 5 or not all(isinstance(s, str) for s in command)
            or command[1] != "-B" or command[2].replace("\\", "/") != qualifier
            or command.count("--out") != 1):
        raise SourceEvidenceError("capture command does not identify the expected qualifier")
    output_name = command[command.index("--out") + 1]
    if not isinstance(output_name, str):
        raise SourceEvidenceError("capture output path is not text")
    output = safe_path(root, output_name.replace("\\", "/"))
    if output.read_bytes() != safe_path(root, receipt_path).read_bytes():
        raise SourceEvidenceError("capture output differs from current receipt")
    if digest(capture_path.with_suffix(".log").read_bytes()) != capture["log_sha256"]:
        raise SourceEvidenceError("capture log changed")
    sources = source_closure(root, roots)
    snapshot = capture["source_before"]
    if not isinstance(snapshot, dict) or any(snapshot.get(b["path"]) != b["sha256"] for b in sources):
        raise SourceEvidenceError("missing or changed dependency in original execution snapshot")
    return {"profile": profile, "receipt": binding(root, receipt_path), "sources": sources,
            "capture": {"record_sha256": digest(raw), "log_sha256": capture["log_sha256"],
                        "source_snapshot_sha256": digest(canonical(snapshot)),
                        "return_code": 0, "source_unchanged": True}}
