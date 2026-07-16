"""Bounded TLC qualification support for the PooleOS N4 model slice."""

from __future__ import annotations

import copy
import hashlib
import json
import os
import re
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Iterable

from runtime.schema_validation import validate_json


ROOT = Path(__file__).resolve().parents[1]
LOCK_RELATIVE = Path("specs/native-model-toolchain-lock.json")
LOCK_SCHEMA_RELATIVE = Path("specs/native-model-toolchain-lock.schema.json")
CONTRACT_RELATIVE = Path("specs/native-model-contract.json")
CONTRACT_SCHEMA_RELATIVE = Path("specs/native-model-contract.schema.json")
READINESS_RELATIVE = Path("runs/native_model_readiness.json")
READINESS_SCHEMA_RELATIVE = Path("specs/native-model-readiness.schema.json")
DEFAULT_TOOLCHAIN_ROOT = ROOT / ".toolchains" / "native-models"
MODEL_INPUTS = (
    "models/tla/PooleBootSlots.tla",
    "models/tla/PooleBootSlots.safe.cfg",
    "models/tla/PooleBootSlots.hostile.cfg",
    "models/tla/PooleCapabilities.tla",
    "models/tla/PooleCapabilities.safe.cfg",
    "models/tla/PooleCapabilities.hostile.cfg",
    "models/tla/PooleVirtualMemory.tla",
    "models/tla/PooleVirtualMemory.safe.cfg",
    "models/tla/PooleVirtualMemory.stale_mapping.cfg",
    "models/tla/PooleVirtualMemory.early_reuse.cfg",
    "models/tla/PooleIPC.tla",
    "models/tla/PooleIPC.safe.cfg",
    "models/tla/PooleIPC.unauthorized_call.cfg",
    "models/tla/PooleIPC.token_reuse.cfg",
    "models/tla/PooleIPC.stale_reply.cfg",
    "models/tla/PooleIPC.leaky_teardown.cfg",
)
IMPLEMENTATION_INPUTS = (
    "runtime/native_models.py",
    "tools/bootstrap_native_models.ps1",
    "tools/qualify_native_models.py",
)
RUN_IDS = (
    "boot_slot_rollback.safe",
    "boot_slot_rollback.unsafe_rollback",
    "capability_revocation.safe",
    "capability_revocation.unsafe_local_revoke",
    "virtual_memory_ownership.safe",
    "virtual_memory_ownership.unsafe_stale_mapping",
    "virtual_memory_ownership.unsafe_early_reuse",
    "capability_mediated_ipc.safe",
    "capability_mediated_ipc.unsafe_unauthorized_call",
    "capability_mediated_ipc.unsafe_token_reuse",
    "capability_mediated_ipc.unsafe_stale_reply",
    "capability_mediated_ipc.unsafe_leaky_teardown",
)
NEGATIVE_CONTROL_IDS = (
    "NEG-N4-MODEL-TLC-PRERELEASE",
    "NEG-N4-MODEL-TLC-HASH",
    "NEG-N4-MODEL-TLC-SIGNATURE-OVERCLAIM",
    "NEG-N4-MODEL-JRE-HASH",
    "NEG-N4-MODEL-JRE-SIGNATURE-OVERCLAIM",
    "NEG-N4-MODEL-RUNTIME-CLOSURE",
    "NEG-N4-MODEL-BOOT-MUTANT",
    "NEG-N4-MODEL-CAPABILITY-MUTANT",
    "NEG-N4-MODEL-VM-STALE-MAPPING-MUTANT",
    "NEG-N4-MODEL-VM-EARLY-REUSE-MUTANT",
    "NEG-N4-MODEL-IPC-UNAUTHORIZED-CALL-MUTANT",
    "NEG-N4-MODEL-IPC-TOKEN-REUSE-MUTANT",
    "NEG-N4-MODEL-IPC-STALE-REPLY-MUTANT",
    "NEG-N4-MODEL-IPC-LEAKY-TEARDOWN-MUTANT",
    "NEG-N4-MODEL-SAFE-VIOLATION",
    "NEG-N4-MODEL-PATH-ESCAPE",
    "NEG-N4-MODEL-EXTRA-ARGUMENT",
    "NEG-N4-MODEL-TRACE-OVERCLAIM",
)
NEGATIVE_CONTROL_EVIDENCE_KINDS = (
    "release_channel_policy",
    "exact_hash_policy",
    "claim_boundary",
    "exact_hash_policy",
    "claim_boundary",
    "runtime_closure",
    "executed_counterexample",
    "executed_counterexample",
    "executed_counterexample",
    "executed_counterexample",
    "executed_counterexample",
    "executed_counterexample",
    "executed_counterexample",
    "executed_counterexample",
    "safe_model_result",
    "path_policy",
    "closed_command_template",
    "claim_boundary",
)
OPEN_WORK = (
    "Model scheduler transitions, cancellation, priority inversion, and bounded fairness assumptions.",
    "Model PooleFS transaction recovery and power-loss state before freezing persistent formats.",
    "Cross-check all four current models against exact native implementation traces when those implementations exist.",
    "Source-build and independently reproduce the model-checker and Java inputs with signed provenance, SBOM, vulnerability, license, and redistribution review.",
)
FROZEN_MODEL_CONTRACT_SHA256 = "CD6ED60F79E1566625D04BA180ECCE64540DEAB6BDE881583BA14580BC37807B"
RUN_KEYS = {
    "id", "model_id", "case_id", "mode", "status", "expected_exit_code", "observed_exit_code",
    "expected_invariant_violation", "observed_invariant_violation", "generated_states",
    "distinct_states", "left_on_queue", "depth", "trace", "trace_sha256",
    "repeat_exact_match", "raw_output_public", "command_sha256",
}
TRACE_STEP_KEYS = {"index", "action", "state_sha256", "state_lines"}
MESSAGE_PATTERN = re.compile(
    r"@!@!@STARTMSG (?P<code>\d+):\d+ @!@!@\r?\n(?P<body>.*?)@!@!@ENDMSG (?P=code) @!@!@",
    flags=re.DOTALL,
)
STATS_PATTERN = re.compile(
    r"(?P<generated>[\d,]+) states generated, (?P<distinct>[\d,]+) distinct states found, "
    r"(?P<left>[\d,]+) states left on queue\."
)
DEPTH_PATTERN = re.compile(r"The depth of the complete state graph search is (?P<depth>[\d,]+)\.")
INVARIANT_PATTERN = re.compile(r"Invariant (?P<name>[A-Za-z][A-Za-z0-9_]*) is violated\.")
TRACE_HEADER_PATTERN = re.compile(r"(?P<index>\d+): <(?P<title>[^>]+)>")
ABSOLUTE_USER_PATH = re.compile(
    r"(?:[A-Za-z]:[\\/](?:Users|Documents and Settings)[\\/][^\\/\s]+|/(?:Users|home)/[^/\s]+)",
    flags=re.IGNORECASE,
)


class NativeModelError(RuntimeError):
    """Raised when the bounded model contract fails closed."""


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest().upper()


def canonical_json_bytes(value: Any) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True) + "\n").encode("ascii")


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(value, dict):
        raise NativeModelError(f"JSON object required: {path.name}")
    return value


def write_json(value: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=True) + "\n", encoding="utf-8", newline="\n")


def file_binding(path: Path, root: Path = ROOT) -> dict[str, Any]:
    resolved = path.resolve()
    try:
        relative = resolved.relative_to(root.resolve()).as_posix()
    except ValueError as error:
        raise NativeModelError("public binding path escapes the repository") from error
    data = resolved.read_bytes()
    return {"path": relative, "byte_count": len(data), "sha256": sha256_bytes(data)}


def _schema_errors(value: dict[str, Any], root: Path, relative: Path) -> list[str]:
    schema = read_json(root / relative)
    return [f"{item.path}: {item.message}" for item in validate_json(value, schema)]


def lock_contract_errors(lock: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    tlc = lock.get("tlc", {})
    jar = tlc.get("jar", {})
    rejected = tlc.get("rejected_candidate", {})
    java = lock.get("java", {})
    runtime = java.get("runtime_tree", {})
    executable = java.get("java_executable", {})
    supply = lock.get("supply_chain_boundary", {})
    if tlc.get("release_tag") != "v1.7.4" or tlc.get("stable_release") is not True:
        errors.append("stable TLC release lock changed")
    if tlc.get("prerelease") is not False or tlc.get("source_commit") != "5a47802b5c391f59ecdd44117981f4ff8c0656ba":
        errors.append("TLC source identity changed")
    if tlc.get("tag_or_commit_signature_verified") is not False:
        errors.append("unsigned TLC tag is overclaimed")
    if jar.get("sha256") != "936A262061C914694DFD669A543BE24573C45D5AA0FF20A8B96B23D01E050E88":
        errors.append("TLC jar hash changed")
    if rejected.get("release_tag") != "v1.8.0" or rejected.get("prerelease") is not True:
        errors.append("TLC prerelease rejection changed")
    if java.get("release_name") != "jdk-21.0.11+10":
        errors.append("Java release changed")
    if java.get("package_sha256") != "BE26677AAA20B39A62EDCAAB4C8857A8B76673B0F45ABC0B6143B142B62717E4":
        errors.append("Java package hash changed")
    if java.get("detached_signature_verified") is not False:
        errors.append("unverified Java detached signature is overclaimed")
    if runtime != {
        "file_count": 315,
        "byte_count": 151530953,
        "tree_sha256": "057E582B6FAC90535C1A51A66856C7D7DCCE27B03536FA0FB019A7C7ADA56DC9",
    }:
        errors.append("Java runtime closure changed")
    if executable.get("sha256") != "5E0FAB9F07952CEB6E71EB9FD33E1ED69959904CA00CF70869B7BAF516A98016":
        errors.append("java.exe hash changed")
    if executable.get("authenticode_status") != "Valid":
        errors.append("java.exe Authenticode status changed")
    expected_false = (
        "global_installation_performed",
        "global_path_mutated",
        "tlc_source_build_performed",
        "java_source_build_performed",
        "second_host_reproduction_performed",
        "vulnerability_review_complete",
        "sbom_review_complete",
        "redistribution_review_complete",
    )
    if supply.get("workspace_local_only") is not True or any(supply.get(key) is not False for key in expected_false):
        errors.append("model toolchain supply boundary changed")
    return errors


def contract_errors(contract: dict[str, Any], root: Path = ROOT) -> list[str]:
    errors: list[str] = []
    engine = contract.get("engine", {})
    expected_command = [
        "$JAVA", "-XX:+UseParallelGC", "-Dfile.encoding=UTF-8", "-jar", "$TLC_JAR",
        "-workers", "1", "-fp", "0", "-terse", "-tool", "-cleanup", "-metadir", "$RUN_DIR",
        "-config", "$CONFIG", "$MODULE",
    ]
    if engine.get("command_template") != expected_command:
        errors.append("TLC command template changed")
    if engine.get("workers") != 1 or engine.get("fingerprint_polynomial") != 0 or engine.get("repeat_count") != 2:
        errors.append("deterministic TLC controls changed")
    required = contract.get("required_domains", [])
    modeled = contract.get("modeled_domains", [])
    if len(required) != 7 or len(set(required)) != 7 or len(modeled) != 5 or not set(modeled).issubset(set(required)):
        errors.append("model domain coverage is malformed")
    model_value = contract.get("models", [])
    models = model_value if isinstance(model_value, list) else []
    expected_model_ids = [
        "boot_slot_rollback",
        "capability_revocation",
        "virtual_memory_ownership",
        "capability_mediated_ipc",
    ]
    if [item.get("id") for item in models if isinstance(item, dict)] != expected_model_ids:
        errors.append("model identifier set changed")
    if not isinstance(model_value, list) or sha256_bytes(canonical_json_bytes(models)) != FROZEN_MODEL_CONTRACT_SHA256:
        errors.append("frozen model/case contract changed")
    for model in models:
        if not isinstance(model, dict) or model.get("id") not in expected_model_ids:
            continue
        cases = model.get("cases", [])
        if not isinstance(cases, list) or not cases:
            errors.append(f"model cases are missing: {model['id']}")
            continue
        case_ids = [case.get("id") for case in cases if isinstance(case, dict)]
        if len(case_ids) != len(cases) or len(set(case_ids)) != len(case_ids):
            errors.append(f"model case identifiers are malformed: {model['id']}")
        if sum(case.get("role") == "safe" for case in cases if isinstance(case, dict)) != 1:
            errors.append(f"model must have exactly one safe case: {model['id']}")
        paths = [model.get("module_path")] + [case.get("config_path") for case in cases if isinstance(case, dict)]
        for relative in paths:
            try:
                _model_input_path(str(relative), root)
            except NativeModelError as error:
                errors.append(f"model input path invalid: {model['id']}: {error}")
        for case in cases:
            if not isinstance(case, dict):
                continue
            role = case.get("role")
            violation = case.get("expected_invariant_violation")
            outcome = case.get("expected", {})
            if not isinstance(outcome, dict):
                errors.append(f"case outcome is malformed: {model['id']}.{case.get('id')}")
                continue
            if role == "safe" and (violation is not None or outcome.get("exit_code") != 0):
                errors.append(f"safe-case expectation changed: {model['id']}.{case.get('id')}")
            if role == "hostile" and (not isinstance(violation, str) or outcome.get("exit_code") != 12):
                errors.append(f"hostile-case expectation changed: {model['id']}.{case.get('id')}")
            if outcome.get("trace_length") != len(outcome.get("trace_actions", [])):
                errors.append(f"trace expectation is inconsistent: {model['id']}.{case.get('id')}")
            try:
                config_text = _model_input_path(str(case.get("config_path")), root).read_text(encoding="utf-8-sig")
            except (OSError, UnicodeError, NativeModelError):
                continue
            assignments = case.get("constant_assignments", {})
            if not isinstance(assignments, dict) or not assignments:
                errors.append(f"constant assignments are missing: {model['id']}.{case.get('id')}")
                continue
            for name, value in assignments.items():
                if not isinstance(name, str) or value not in {"TRUE", "FALSE"} or f"{name} = {value}" not in config_text:
                    errors.append(f"constant assignment changed: {model['id']}.{case.get('id')}.{name}")
    trace = contract.get("trace_cross_check", {})
    if (
        trace.get("status") != "pending_native_implementation_traces"
        or trace.get("required_model_count") != 4
        or trace.get("completed_model_count") != 0
        or trace.get("abi_freeze_authorized") is not False
    ):
        errors.append("implementation trace boundary is overclaimed")
    claims = contract.get("claim_boundary", {})
    if claims.get("bounded_model_checks_claimed") is not True or any(
        claims.get(key) is not False
        for key in ("formal_proof_claimed", "implementation_correctness_claimed", "kernel_execution_claimed", "boot_execution_claimed", "n4_exit_gate_claimed")
    ):
        errors.append("model claim boundary changed")
    return errors


def validate_contracts(root: Path = ROOT) -> tuple[dict[str, Any], dict[str, Any]]:
    lock = read_json(root / LOCK_RELATIVE)
    contract = read_json(root / CONTRACT_RELATIVE)
    errors: list[str] = []
    errors.extend(f"lock schema {item}" for item in _schema_errors(lock, root, LOCK_SCHEMA_RELATIVE))
    errors.extend(f"contract schema {item}" for item in _schema_errors(contract, root, CONTRACT_SCHEMA_RELATIVE))
    errors.extend(f"lock contract {item}" for item in lock_contract_errors(lock))
    errors.extend(f"model contract {item}" for item in contract_errors(contract, root))
    if errors:
        raise NativeModelError("; ".join(errors[:16]))
    return lock, contract


def _model_input_path(relative: str, root: Path = ROOT) -> Path:
    path = Path(relative)
    if path.is_absolute() or ".." in path.parts:
        raise NativeModelError("absolute or parent-relative model path is prohibited")
    resolved = (root / path).resolve()
    model_root = (root / "models" / "tla").resolve()
    try:
        resolved.relative_to(model_root)
    except ValueError as error:
        raise NativeModelError("model input escapes models/tla") from error
    if not resolved.is_file() or resolved.is_symlink():
        raise NativeModelError("model input must be a regular non-symlink file")
    return resolved


def runtime_tree_binding(root: Path) -> dict[str, Any]:
    root = root.resolve()
    if not root.is_dir() or root.is_symlink():
        raise NativeModelError("Java runtime root must be a regular directory")
    entries = list(root.rglob("*"))
    if any(path.is_symlink() for path in entries):
        raise NativeModelError("Java runtime closure contains a symbolic link")
    records: list[tuple[str, int, str]] = []
    for path in sorted(
        (item for item in entries if item.is_file()),
        key=lambda item: (item.relative_to(root).as_posix().casefold(), item.relative_to(root).as_posix()),
    ):
        data = path.read_bytes()
        records.append((path.relative_to(root).as_posix(), len(data), sha256_bytes(data)))
    payload = b"".join(
        relative.encode("utf-8") + b"\0" + str(size).encode("ascii") + b"\0" + digest.encode("ascii") + b"\n"
        for relative, size, digest in records
    )
    return {
        "file_count": len(records),
        "byte_count": sum(size for _, size, _ in records),
        "tree_sha256": sha256_bytes(payload),
    }


def _verify_file(path: Path, *, size: int, sha256: str, role: str) -> None:
    if not path.is_file() or path.is_symlink():
        raise NativeModelError(f"missing regular {role}")
    data = path.read_bytes()
    if len(data) != size or sha256_bytes(data) != sha256:
        raise NativeModelError(f"{role} identity mismatch")


def verify_toolchain(lock: dict[str, Any], toolchain_root: Path = DEFAULT_TOOLCHAIN_ROOT) -> dict[str, Any]:
    root = toolchain_root.resolve()
    expected_parent = (ROOT / ".toolchains").resolve()
    try:
        root.relative_to(expected_parent)
    except ValueError as error:
        raise NativeModelError("model toolchain must remain under .toolchains") from error
    downloads = root / "downloads"
    runtime_root = root / "runtime" / "jdk-21.0.11+10-jre"
    jre_archive = downloads / lock["java"]["package_name"]
    jre_signature = Path(str(jre_archive) + ".sig")
    tlc_jar = downloads / "tla2tools-v1.7.4.jar"
    java = runtime_root / lock["java"]["java_executable"]["relative_path"]
    _verify_file(jre_archive, size=lock["java"]["package_byte_count"], sha256=lock["java"]["package_sha256"], role="JRE archive")
    _verify_file(jre_signature, size=lock["java"]["signature_byte_count"], sha256=lock["java"]["signature_sha256"], role="JRE detached signature")
    _verify_file(tlc_jar, size=lock["tlc"]["jar"]["byte_count"], sha256=lock["tlc"]["jar"]["sha256"], role="TLC jar")
    if hashlib.sha1(tlc_jar.read_bytes()).hexdigest().upper() != lock["tlc"]["jar"]["published_sha1"]:
        raise NativeModelError("TLC published SHA-1 mismatch")
    _verify_file(java, size=lock["java"]["java_executable"]["byte_count"], sha256=lock["java"]["java_executable"]["sha256"], role="java executable")
    tree = runtime_tree_binding(runtime_root)
    if tree != lock["java"]["runtime_tree"]:
        raise NativeModelError("Java runtime closure mismatch")
    completed = subprocess.run(
        [str(java), "-version"],
        cwd=ROOT,
        text=True,
        encoding="utf-8",
        errors="replace",
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
        timeout=30,
    )
    version_lines = [line.strip() for line in completed.stdout.splitlines() if line.strip()]
    if completed.returncode != 0 or version_lines != lock["java"]["version_lines"]:
        raise NativeModelError("Java version probe mismatch")
    return {"root": root, "runtime_root": runtime_root, "java": java, "tlc_jar": tlc_jar, "runtime_tree": tree}


def _messages(output: str) -> dict[int, list[str]]:
    messages: dict[int, list[str]] = {}
    for match in MESSAGE_PATTERN.finditer(output.replace("\x1b", "")):
        messages.setdefault(int(match.group("code")), []).append(match.group("body").strip())
    return messages


def _trace_steps(messages: dict[int, list[str]]) -> list[dict[str, Any]]:
    trace: list[dict[str, Any]] = []
    for body in messages.get(2217, []):
        lines = body.splitlines()
        if not lines:
            continue
        header = TRACE_HEADER_PATTERN.fullmatch(lines[0].strip())
        if header is None:
            raise NativeModelError("malformed TLC trace-state header")
        title = header.group("title")
        action = "Init" if title == "Initial predicate" else title.split()[0]
        state_lines = [line.rstrip() for line in lines[1:] if line.strip()]
        if not state_lines:
            raise NativeModelError("TLC trace state has no assignments")
        trace.append(
            {
                "index": int(header.group("index")),
                "action": action,
                "state_sha256": sha256_bytes(canonical_json_bytes(state_lines)),
                "state_lines": state_lines,
            }
        )
    if [item["index"] for item in trace] != list(range(1, len(trace) + 1)):
        raise NativeModelError("TLC trace state order is not contiguous")
    return trace


def parse_tlc_output(output: str, exit_code: int) -> dict[str, Any]:
    messages = _messages(output)
    banner = messages.get(2262, [""])[0]
    stats_text = messages.get(2199, [""])[-1]
    depth_text = messages.get(2194, [""])[-1]
    stats = STATS_PATTERN.fullmatch(stats_text)
    depth = DEPTH_PATTERN.fullmatch(depth_text)
    if not banner or stats is None or depth is None:
        raise NativeModelError("required TLC tool messages are missing")
    invariant: str | None = None
    if messages.get(2110):
        match = INVARIANT_PATTERN.fullmatch(messages[2110][-1])
        if match is None:
            raise NativeModelError("malformed TLC invariant violation message")
        invariant = match.group("name")
    no_error = bool(messages.get(2193))
    if (exit_code == 0) != no_error or (exit_code == 12) != (invariant is not None):
        raise NativeModelError("TLC exit code and tool messages disagree")
    trace = _trace_steps(messages)
    if invariant is None and trace:
        raise NativeModelError("safe TLC run unexpectedly emitted a trace")
    return {
        "tool_banner": banner,
        "observed_exit_code": exit_code,
        "observed_invariant_violation": invariant,
        "generated_states": int(stats.group("generated").replace(",", "")),
        "distinct_states": int(stats.group("distinct").replace(",", "")),
        "left_on_queue": int(stats.group("left").replace(",", "")),
        "depth": int(depth.group("depth").replace(",", "")),
        "trace": trace,
        "trace_sha256": sha256_bytes(canonical_json_bytes(trace)),
    }


def normalized_command(contract: dict[str, Any], model: dict[str, Any], case: dict[str, Any]) -> list[str]:
    if case.get("role") not in {"safe", "hostile"}:
        raise NativeModelError("unsupported model case role")
    config = case["config_path"]
    replacements = {
        "$JAVA": "$MODEL_TOOLCHAIN/java",
        "$TLC_JAR": "$MODEL_TOOLCHAIN/tla2tools.jar",
        "$RUN_DIR": "$PRIVATE_RUN_DIR",
        "$CONFIG": config,
        "$MODULE": model["module_path"],
    }
    return [replacements.get(item, item) for item in contract["engine"]["command_template"]]


def _actual_command(
    contract: dict[str, Any],
    model: dict[str, Any],
    case: dict[str, Any],
    toolchain: dict[str, Any],
    run_directory: Path,
) -> list[str]:
    config = _model_input_path(case["config_path"])
    module = _model_input_path(model["module_path"])
    replacements = {
        "$JAVA": str(toolchain["java"]),
        "$TLC_JAR": str(toolchain["tlc_jar"]),
        "$RUN_DIR": str(run_directory),
        "$CONFIG": str(config),
        "$MODULE": str(module),
    }
    return [replacements.get(item, item) for item in contract["engine"]["command_template"]]


def _run_once(
    contract: dict[str, Any],
    model: dict[str, Any],
    case: dict[str, Any],
    toolchain: dict[str, Any],
    private_root: Path,
    repeat_index: int,
) -> dict[str, Any]:
    case_root = Path(tempfile.mkdtemp(prefix=f"{model['id']}-{case['id']}-{repeat_index}-", dir=private_root))
    metadata = case_root / "tlc-metadata"
    command = _actual_command(contract, model, case, toolchain, metadata)
    environment = os.environ.copy()
    for key in ("JAVA_TOOL_OPTIONS", "JDK_JAVA_OPTIONS", "_JAVA_OPTIONS"):
        environment.pop(key, None)
    completed = subprocess.run(
        command,
        cwd=ROOT,
        env=environment,
        text=True,
        encoding="utf-8",
        errors="replace",
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
        timeout=60,
    )
    (case_root / "tlc-output.private.log").write_text(completed.stdout, encoding="utf-8", newline="\n")
    parsed = parse_tlc_output(completed.stdout, completed.returncode)
    if parsed["tool_banner"] != "TLC2 Version 2.19 of 08 August 2024 (rev: 5a47802)":
        raise NativeModelError("TLC tool banner changed")
    parsed.pop("tool_banner")
    return parsed


def _expected_tuple(outcome: dict[str, Any]) -> tuple[int, int, int, int, int, int]:
    return tuple(
        int(outcome[key])
        for key in ("exit_code", "generated_states", "distinct_states", "left_on_queue", "depth", "trace_length")
    )


def execute_case(
    contract: dict[str, Any],
    model: dict[str, Any],
    case: dict[str, Any],
    toolchain: dict[str, Any],
    private_root: Path,
) -> dict[str, Any]:
    repeats = [
        _run_once(contract, model, case, toolchain, private_root, index)
        for index in range(1, contract["engine"]["repeat_count"] + 1)
    ]
    if any(item != repeats[0] for item in repeats[1:]):
        raise NativeModelError(f"nondeterministic normalized result: {model['id']}.{case['id']}")
    observed = repeats[0]
    expected = case["expected"]
    expected_tuple = _expected_tuple(expected)
    observed_tuple = (
        observed["observed_exit_code"], observed["generated_states"], observed["distinct_states"],
        observed["left_on_queue"], observed["depth"], len(observed["trace"]),
    )
    if observed_tuple != expected_tuple:
        raise NativeModelError(f"frozen state-space result changed: {model['id']}.{case['id']}")
    expected_violation = case["expected_invariant_violation"]
    if observed["observed_invariant_violation"] != expected_violation:
        raise NativeModelError(f"unexpected invariant result: {model['id']}.{case['id']}")
    observed_actions = [item["action"] for item in observed["trace"]]
    if observed_actions != expected["trace_actions"] or observed["trace_sha256"] != expected["trace_sha256"]:
        raise NativeModelError(f"frozen counterexample trace changed: {model['id']}.{case['id']}")
    normalized = normalized_command(contract, model, case)
    return {
        "id": f"{model['id']}.{case['id']}",
        "model_id": model["id"],
        "case_id": case["id"],
        "mode": case["role"],
        "status": "pass",
        "expected_exit_code": expected["exit_code"],
        "observed_exit_code": observed["observed_exit_code"],
        "expected_invariant_violation": expected_violation,
        "observed_invariant_violation": observed["observed_invariant_violation"],
        "generated_states": observed["generated_states"],
        "distinct_states": observed["distinct_states"],
        "left_on_queue": observed["left_on_queue"],
        "depth": observed["depth"],
        "trace": observed["trace"],
        "trace_sha256": observed["trace_sha256"],
        "repeat_exact_match": True,
        "raw_output_public": False,
        "command_sha256": sha256_bytes(canonical_json_bytes(normalized)),
    }


def _control(identifier: str, condition: bool, evidence_kind: str) -> dict[str, str]:
    if not condition:
        raise NativeModelError(f"negative control failed open: {identifier}")
    return {"id": identifier, "expected": "reject", "observed": "reject", "status": "pass", "evidence_kind": evidence_kind}


def _path_escape_rejected() -> bool:
    try:
        _model_input_path("../README.md")
    except NativeModelError:
        return True
    return False


def negative_controls(lock: dict[str, Any], contract: dict[str, Any], runs: list[dict[str, Any]]) -> list[dict[str, str]]:
    by_id = {item["id"]: item for item in runs}
    claims = contract["claim_boundary"]
    normalized = normalized_command(contract, contract["models"][0], contract["models"][0]["cases"][0])
    controls = [
        _control("NEG-N4-MODEL-TLC-PRERELEASE", lock["tlc"]["rejected_candidate"]["prerelease"] is True, "release_channel_policy"),
        _control("NEG-N4-MODEL-TLC-HASH", lock["tlc"]["jar"]["sha256"] != lock["tlc"]["rejected_candidate"]["jar_sha256"], "exact_hash_policy"),
        _control("NEG-N4-MODEL-TLC-SIGNATURE-OVERCLAIM", lock["tlc"]["tag_or_commit_signature_verified"] is False, "claim_boundary"),
        _control("NEG-N4-MODEL-JRE-HASH", lock["java"]["package_sha256"] == "BE26677AAA20B39A62EDCAAB4C8857A8B76673B0F45ABC0B6143B142B62717E4", "exact_hash_policy"),
        _control("NEG-N4-MODEL-JRE-SIGNATURE-OVERCLAIM", lock["java"]["detached_signature_verified"] is False, "claim_boundary"),
        _control("NEG-N4-MODEL-RUNTIME-CLOSURE", lock["java"]["runtime_tree"]["file_count"] == 315, "runtime_closure"),
        _control("NEG-N4-MODEL-BOOT-MUTANT", by_id["boot_slot_rollback.unsafe_rollback"]["observed_invariant_violation"] == "Recoverable", "executed_counterexample"),
        _control("NEG-N4-MODEL-CAPABILITY-MUTANT", by_id["capability_revocation.unsafe_local_revoke"]["observed_invariant_violation"] == "NoLiveDescendantOfRevoked", "executed_counterexample"),
        _control("NEG-N4-MODEL-VM-STALE-MAPPING-MUTANT", by_id["virtual_memory_ownership.unsafe_stale_mapping"]["observed_invariant_violation"] == "PageTableSafety", "executed_counterexample"),
        _control("NEG-N4-MODEL-VM-EARLY-REUSE-MUTANT", by_id["virtual_memory_ownership.unsafe_early_reuse"]["observed_invariant_violation"] == "TlbSafety", "executed_counterexample"),
        _control("NEG-N4-MODEL-IPC-UNAUTHORIZED-CALL-MUTANT", by_id["capability_mediated_ipc.unsafe_unauthorized_call"]["observed_invariant_violation"] == "QueuedCallAuthorized", "executed_counterexample"),
        _control("NEG-N4-MODEL-IPC-TOKEN-REUSE-MUTANT", by_id["capability_mediated_ipc.unsafe_token_reuse"]["observed_invariant_violation"] == "LiveTokenConsistent", "executed_counterexample"),
        _control("NEG-N4-MODEL-IPC-STALE-REPLY-MUTANT", by_id["capability_mediated_ipc.unsafe_stale_reply"]["observed_invariant_violation"] == "AcceptedRepliesFresh", "executed_counterexample"),
        _control("NEG-N4-MODEL-IPC-LEAKY-TEARDOWN-MUTANT", by_id["capability_mediated_ipc.unsafe_leaky_teardown"]["observed_invariant_violation"] == "ClosedEndpointQuiescent", "executed_counterexample"),
        _control("NEG-N4-MODEL-SAFE-VIOLATION", all(item["observed_invariant_violation"] is None for item in runs if item["mode"] == "safe"), "safe_model_result"),
        _control("NEG-N4-MODEL-PATH-ESCAPE", _path_escape_rejected(), "path_policy"),
        _control(
            "NEG-N4-MODEL-EXTRA-ARGUMENT",
            len(normalized) == 17
            and normalized[-1] == "models/tla/PooleBootSlots.tla"
            and not any(item in normalized for item in ("-simulate", "-generateSpecTE", "-continue")),
            "closed_command_template",
        ),
        _control("NEG-N4-MODEL-TRACE-OVERCLAIM", claims["implementation_correctness_claimed"] is False and contract["trace_cross_check"]["completed_model_count"] == 0, "claim_boundary"),
    ]
    if [item["id"] for item in controls] != list(NEGATIVE_CONTROL_IDS):
        raise NativeModelError("negative-control order changed")
    return controls


def build_readiness(toolchain_root: Path = DEFAULT_TOOLCHAIN_ROOT, root: Path = ROOT) -> dict[str, Any]:
    lock, contract = validate_contracts(root)
    toolchain = verify_toolchain(lock, toolchain_root)
    private_root = toolchain["root"] / "evidence"
    private_root.mkdir(parents=True, exist_ok=True)
    runs = [
        execute_case(contract, model, case, toolchain, private_root)
        for model in contract["models"]
        for case in model["cases"]
    ]
    if [item["id"] for item in runs] != list(RUN_IDS):
        raise NativeModelError("model-run order changed")
    controls = negative_controls(lock, contract, runs)
    required = contract["required_domains"]
    modeled = contract["modeled_domains"]
    open_domains = [item for item in required if item not in modeled]
    readiness = {
        "schema_version": "1.2",
        "artifact_kind": "pooleos_native_model_readiness",
        "status_date": "2026-07-16",
        "status": "bounded_models_pass_counterexamples_detected",
        "selected_move_id": contract["selected_move_id"],
        "production_ready": False,
        "production_promotion_allowed": False,
        "n4_model_slice_satisfied": True,
        "n4_exit_gate_satisfied": False,
        "bindings": {
            "lock": file_binding(root / LOCK_RELATIVE, root),
            "contract": file_binding(root / CONTRACT_RELATIVE, root),
            "implementation_inputs": [file_binding(root / item, root) for item in IMPLEMENTATION_INPUTS],
            "model_inputs": [file_binding(root / item, root) for item in MODEL_INPUTS],
        },
        "toolchain": {
            "tlc_version": "2.19",
            "tlc_jar_sha256": lock["tlc"]["jar"]["sha256"],
            "java_release": lock["java"]["release_name"],
            "java_runtime_tree_sha256": toolchain["runtime_tree"]["tree_sha256"],
            "workspace_local": True,
            "source_built": False,
            "second_host_reproduced": False,
        },
        "domain_coverage": {
            "required_domains": required,
            "modeled_domains": modeled,
            "open_domains": open_domains,
            "required_count": len(required),
            "modeled_count": len(modeled),
            "open_count": len(open_domains),
        },
        "runs": runs,
        "negative_controls": controls,
        "summary": {
            "model_count": len(contract["models"]),
            "run_case_count": len(runs),
            "safe_run_count": sum(item["mode"] == "safe" for item in runs),
            "safe_run_pass_count": sum(item["mode"] == "safe" and item["status"] == "pass" for item in runs),
            "hostile_run_count": sum(item["mode"] == "hostile" for item in runs),
            "hostile_counterexample_count": sum(
                item["mode"] == "hostile" and item["observed_invariant_violation"] is not None
                for item in runs
            ),
            "repeat_match_count": sum(item["repeat_exact_match"] for item in runs),
            "negative_control_count": len(controls),
            "negative_control_pass_count": sum(item["status"] == "pass" for item in controls),
            "normalized_trace_count": sum(bool(item["trace"]) for item in runs),
            "implementation_trace_cross_check_count": 0,
            "failed_check_count": 0,
        },
        "assumptions": contract["assumptions"],
        "open_work": list(OPEN_WORK),
        "claim_boundary": {
            "bounded_state_search_only": True,
            "formal_proof_claimed": False,
            "fingerprint_collision_free_claimed": False,
            "liveness_checked": False,
            "implementation_trace_cross_checked": False,
            "abi_freeze_authorized": False,
            "pooleboot_executed": False,
            "poolekernel_executed": False,
            "production_promotion_allowed": False,
        },
    }
    errors = readiness_contract_errors(readiness, root)
    if errors:
        raise NativeModelError("; ".join(errors[:16]))
    return readiness


def readiness_contract_errors(readiness: dict[str, Any], root: Path = ROOT) -> list[str]:
    errors = [f"schema {item}" for item in _schema_errors(readiness, root, READINESS_SCHEMA_RELATIVE)]
    try:
        lock, contract = validate_contracts(root)
    except (OSError, ValueError, json.JSONDecodeError, NativeModelError) as error:
        return errors + [f"contract validation failed: {error}"]
    bindings = readiness.get("bindings", {})
    expected_bindings = {
        "lock": file_binding(root / LOCK_RELATIVE, root),
        "contract": file_binding(root / CONTRACT_RELATIVE, root),
    }
    for key, expected in expected_bindings.items():
        if bindings.get(key) != expected:
            errors.append(f"stale {key} binding")
    expected_implementation = [file_binding(root / item, root) for item in IMPLEMENTATION_INPUTS]
    expected_models = [file_binding(root / item, root) for item in MODEL_INPUTS]
    if bindings.get("implementation_inputs") != expected_implementation:
        errors.append("stale implementation input bindings")
    if bindings.get("model_inputs") != expected_models:
        errors.append("stale model input bindings")
    runs = readiness.get("runs", [])
    if [item.get("id") for item in runs if isinstance(item, dict)] != list(RUN_IDS):
        errors.append("model run set or ordering changed")
    model_by_id = {item["id"]: item for item in contract["models"]}
    for run in runs:
        if not isinstance(run, dict) or run.get("model_id") not in model_by_id:
            continue
        model = model_by_id[run["model_id"]]
        case_by_id = {item["id"]: item for item in model["cases"]}
        case = case_by_id.get(run.get("case_id"))
        if case is None or run.get("mode") != case["role"]:
            errors.append(f"run case or role changed: {run.get('id')}")
            continue
        if set(run) != RUN_KEYS:
            errors.append(f"run field set changed: {run.get('id')}")
        if run.get("id") != f"{run['model_id']}.{case['id']}":
            errors.append(f"run identifier changed: {run.get('id')}")
        expected = case["expected"]
        observed = tuple(run.get(key) for key in ("observed_exit_code", "generated_states", "distinct_states", "left_on_queue", "depth")) + (len(run.get("trace", [])),)
        frozen = tuple(expected[key] for key in ("exit_code", "generated_states", "distinct_states", "left_on_queue", "depth", "trace_length"))
        if observed != frozen:
            errors.append(f"run result drift: {run.get('id')}")
        expected_violation = case["expected_invariant_violation"]
        if (
            run.get("status") != "pass"
            or run.get("expected_exit_code") != expected["exit_code"]
            or run.get("expected_invariant_violation") != expected_violation
            or run.get("observed_invariant_violation") != expected_violation
        ):
            errors.append(f"invariant result drift: {run.get('id')}")
        trace = run.get("trace", [])
        trace_actions = [item.get("action") for item in trace if isinstance(item, dict)]
        if trace_actions != expected["trace_actions"]:
            errors.append(f"trace action drift: {run.get('id')}")
        if run.get("trace_sha256") != expected["trace_sha256"] or run.get("trace_sha256") != sha256_bytes(canonical_json_bytes(trace)):
            errors.append(f"trace digest mismatch: {run.get('id')}")
        for index, step in enumerate(trace, start=1):
            if not isinstance(step, dict) or set(step) != TRACE_STEP_KEYS:
                errors.append(f"trace field set changed: {run.get('id')}[{index}]")
                continue
            if step.get("index") != index or step.get("state_sha256") != sha256_bytes(canonical_json_bytes(step.get("state_lines", []))):
                errors.append(f"trace state binding mismatch: {run.get('id')}[{index}]")
        expected_command_sha256 = sha256_bytes(
            canonical_json_bytes(normalized_command(contract, model, case))
        )
        if run.get("command_sha256") != expected_command_sha256:
            errors.append(f"command digest mismatch: {run.get('id')}")
        if run.get("repeat_exact_match") is not True or run.get("raw_output_public") is not False:
            errors.append(f"repeat or raw-output boundary changed: {run.get('id')}")
    controls = readiness.get("negative_controls", [])
    if [item.get("id") for item in controls if isinstance(item, dict)] != list(NEGATIVE_CONTROL_IDS):
        errors.append("negative control set or ordering changed")
    expected_controls = [
        {"id": identifier, "expected": "reject", "observed": "reject", "status": "pass", "evidence_kind": evidence_kind}
        for identifier, evidence_kind in zip(NEGATIVE_CONTROL_IDS, NEGATIVE_CONTROL_EVIDENCE_KINDS, strict=True)
    ]
    if controls != expected_controls:
        errors.append("negative control evidence changed")
    coverage = readiness.get("domain_coverage", {})
    required = contract["required_domains"]
    modeled = contract["modeled_domains"]
    expected_coverage = {
        "required_domains": required,
        "modeled_domains": modeled,
        "open_domains": [item for item in required if item not in modeled],
        "required_count": len(required),
        "modeled_count": len(modeled),
        "open_count": len(required) - len(modeled),
    }
    if coverage != expected_coverage:
        errors.append("domain coverage binding changed")
    summary = readiness.get("summary", {})
    expected_summary = {
        "model_count": 4,
        "run_case_count": 12,
        "safe_run_count": 4,
        "safe_run_pass_count": 4,
        "hostile_run_count": 8,
        "hostile_counterexample_count": 8,
        "repeat_match_count": 12,
        "negative_control_count": 18,
        "negative_control_pass_count": 18,
        "normalized_trace_count": 8,
        "implementation_trace_cross_check_count": 0,
        "failed_check_count": 0,
    }
    if summary != expected_summary:
        errors.append("readiness summary overclaims trace closure")
    expected_toolchain = {
        "tlc_version": "2.19",
        "tlc_jar_sha256": lock["tlc"]["jar"]["sha256"],
        "java_release": lock["java"]["release_name"],
        "java_runtime_tree_sha256": lock["java"]["runtime_tree"]["tree_sha256"],
        "workspace_local": True,
        "source_built": False,
        "second_host_reproduced": False,
    }
    if readiness.get("toolchain") != expected_toolchain:
        errors.append("readiness toolchain summary changed")
    if readiness.get("assumptions") != contract["assumptions"] or readiness.get("open_work") != list(OPEN_WORK):
        errors.append("assumption or open-work boundary changed")
    claims = readiness.get("claim_boundary", {})
    expected_claims = {
        "bounded_state_search_only": True,
        "formal_proof_claimed": False,
        "fingerprint_collision_free_claimed": False,
        "liveness_checked": False,
        "implementation_trace_cross_checked": False,
        "abi_freeze_authorized": False,
        "pooleboot_executed": False,
        "poolekernel_executed": False,
        "production_promotion_allowed": False,
    }
    if claims != expected_claims:
        errors.append("readiness claim boundary changed")
    encoded = json.dumps(readiness, ensure_ascii=True)
    if ABSOLUTE_USER_PATH.search(encoded):
        errors.append("readiness contains an absolute user path")
    if readiness.get("n4_model_slice_satisfied") is not True or readiness.get("n4_exit_gate_satisfied") is not False:
        errors.append("N4 model-slice or exit boundary changed")
    return errors


def mutated_readiness_errors(readiness: dict[str, Any], path: tuple[str, ...], value: Any) -> list[str]:
    altered = copy.deepcopy(readiness)
    target: Any = altered
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = value
    return readiness_contract_errors(altered)
