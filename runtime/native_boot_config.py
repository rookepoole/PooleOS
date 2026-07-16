"""Independent Python oracle for the canonical PBC1 boot configuration."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from runtime.schema_validation import validate_json


ROOT = Path(__file__).resolve().parents[1]
CONTRACT_RELATIVE = Path("specs/native-boot-config-contract.json")
CONTRACT_SCHEMA_RELATIVE = Path("specs/native-boot-config-contract.schema.json")
GOLDEN_RELATIVE = Path("specs/native-boot-config-golden-vectors.json")
GOLDEN_SCHEMA_RELATIVE = Path("specs/native-boot-config-golden-vectors.schema.json")
READINESS_RELATIVE = Path("runs/native_boot_config_readiness.json")
READINESS_SCHEMA_RELATIVE = Path("specs/native-boot-config-readiness.schema.json")

CONTRACT_ID = "PBC1"
MAGIC = "POOLEOS-BOOTCFG/1.0"
END_MARKER = "end=PBC1"
MAX_CONFIG_BYTES = 16 * 1024
MAX_LINE_BYTES = 320
MAX_LINES = 64
MAX_ENTRIES = 8
MAX_IDENTIFIER_BYTES = 31
MAX_MANIFEST_PATH_BYTES = 240
MAX_MANIFEST_BYTES = 1024 * 1024
MAX_TIMEOUT_MS = 30_000
MAX_BOOT_ATTEMPTS = 8
MAX_SLOT = 4
MANIFEST_ROOT = "\\EFI\\POOLEOS\\"
MODES = ("normal", "safe", "previous", "recovery", "diagnostic")
U64_MAX = (1 << 64) - 1
IDENTIFIER = re.compile(r"[a-z][a-z0-9_]{0,30}\Z", re.ASCII)

NEGATIVE_CONTROL_IDS = (
    "NEG-N5-PBC1-EMPTY",
    "NEG-N5-PBC1-CONFIG-OVERSIZED",
    "NEG-N5-PBC1-FINAL-LF",
    "NEG-N5-PBC1-NUL",
    "NEG-N5-PBC1-BOM",
    "NEG-N5-PBC1-CRLF",
    "NEG-N5-PBC1-NON-ASCII",
    "NEG-N5-PBC1-SPACE",
    "NEG-N5-PBC1-EMPTY-LINE",
    "NEG-N5-PBC1-LINE-OVERSIZED",
    "NEG-N5-PBC1-LINE-COUNT",
    "NEG-N5-PBC1-MAGIC",
    "NEG-N5-PBC1-MAJOR-VERSION",
    "NEG-N5-PBC1-MINOR-VERSION",
    "NEG-N5-PBC1-NO-EQUALS",
    "NEG-N5-PBC1-EMPTY-KEY",
    "NEG-N5-PBC1-EMPTY-VALUE",
    "NEG-N5-PBC1-MULTIPLE-EQUALS",
    "NEG-N5-PBC1-DUPLICATE-STATIC",
    "NEG-N5-PBC1-DUPLICATE-ENTRY",
    "NEG-N5-PBC1-UNKNOWN-STATIC",
    "NEG-N5-PBC1-UNKNOWN-ENTRY",
    "NEG-N5-PBC1-HEADER-ORDER",
    "NEG-N5-PBC1-ENTRY-FIELD-ORDER",
    "NEG-N5-PBC1-TRUNCATED-HEADER",
    "NEG-N5-PBC1-TRUNCATED-ENTRY",
    "NEG-N5-PBC1-END-MISSING",
    "NEG-N5-PBC1-END-WRONG",
    "NEG-N5-PBC1-ENTRY-COUNT-ZERO",
    "NEG-N5-PBC1-ENTRY-COUNT-HIGH",
    "NEG-N5-PBC1-ENTRY-COUNT-LEADING-ZERO",
    "NEG-N5-PBC1-ENTRY-COUNT-NONNUMERIC",
    "NEG-N5-PBC1-TIMEOUT-HIGH",
    "NEG-N5-PBC1-TIMEOUT-NEGATIVE",
    "NEG-N5-PBC1-TIMEOUT-OVERFLOW",
    "NEG-N5-PBC1-ATTEMPTS-ZERO",
    "NEG-N5-PBC1-ATTEMPTS-HIGH",
    "NEG-N5-PBC1-DEFAULT-ID",
    "NEG-N5-PBC1-DEFAULT-MISSING",
    "NEG-N5-PBC1-ENTRY-ID-START",
    "NEG-N5-PBC1-ENTRY-ID-LENGTH",
    "NEG-N5-PBC1-ENTRY-ORDER",
    "NEG-N5-PBC1-MODE",
    "NEG-N5-PBC1-SLOT-ZERO",
    "NEG-N5-PBC1-SLOT-HIGH",
    "NEG-N5-PBC1-SLOT-LEADING-ZERO",
    "NEG-N5-PBC1-PATH-RELATIVE",
    "NEG-N5-PBC1-PATH-ROOT",
    "NEG-N5-PBC1-PATH-SLASH",
    "NEG-N5-PBC1-PATH-TRAVERSAL",
    "NEG-N5-PBC1-PATH-EMPTY-SEGMENT",
    "NEG-N5-PBC1-PATH-LOWERCASE",
    "NEG-N5-PBC1-PATH-SUFFIX",
    "NEG-N5-PBC1-PATH-LENGTH",
    "NEG-N5-PBC1-MANIFEST-LIMIT-ZERO",
    "NEG-N5-PBC1-MANIFEST-LIMIT-HIGH",
    "NEG-N5-PBC1-MANIFEST-LIMIT-OVERFLOW",
    "NEG-N5-PBC1-OUTPUT-CAPACITY",
    "NEG-N5-PBC1-ARTIFACT-ZERO",
    "NEG-N5-PBC1-ARTIFACT-OVER-CONFIGURED",
    "NEG-N5-PBC1-ARTIFACT-OVER-ABSOLUTE",
    "NEG-N5-PBC1-DECLARED-COUNT-SHORT",
    "NEG-N5-PBC1-DECLARED-COUNT-EXTRA",
    "NEG-N5-PBC1-TRAILING-KEY",
)

IMPLEMENTATION_INPUTS = (
    "native/Cargo.toml",
    "native/Cargo.lock",
    "native/boot/Cargo.toml",
    "native/boot/src/lib.rs",
    "native/bootcfg/Cargo.toml",
    "native/bootcfg/README.md",
    "native/bootcfg/src/lib.rs",
    "native/bootcfg/src/bin/pbc1_probe.rs",
    "runtime/native_boot_config.py",
    "tools/generate_native_boot_config_vectors.py",
    "tools/qualify_native_boot_config.py",
    "tests/test_native_boot_config.py",
    "docs/native-boot-config.md",
)


class BootConfigError(ValueError):
    """Raised with a stable PBC1 rejection code."""

    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


@dataclass(frozen=True)
class Entry:
    id: str
    mode: str
    slot: int
    manifest: str
    manifest_max_bytes: int


@dataclass(frozen=True)
class Config:
    default_entry: str
    timeout_ms: int
    boot_attempt_limit: int
    entries: tuple[Entry, ...]


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest().upper()


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(value, dict):
        raise BootConfigError("json_object")
    return value


def write_json(value: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=True) + "\n", encoding="utf-8", newline="\n")


def file_binding(path: Path, root: Path = ROOT) -> dict[str, Any]:
    resolved = path.resolve()
    try:
        relative = resolved.relative_to(root.resolve()).as_posix()
    except ValueError as error:
        raise BootConfigError("binding_escape") from error
    data = resolved.read_bytes()
    return {"path": relative, "sha256": sha256_bytes(data), "byte_count": len(data)}


def _lex(data: bytes) -> list[str]:
    if not data:
        raise BootConfigError("empty")
    if len(data) > MAX_CONFIG_BYTES:
        raise BootConfigError("config_too_large")
    if not data.endswith(b"\n"):
        raise BootConfigError("missing_final_lf")
    if any(byte != 10 and not 33 <= byte <= 126 for byte in data):
        raise BootConfigError("character")
    raw_lines = data[:-1].split(b"\n")
    if any(not line for line in raw_lines):
        raise BootConfigError("empty_line")
    if any(len(line) > MAX_LINE_BYTES for line in raw_lines):
        raise BootConfigError("line_too_long")
    if len(raw_lines) > MAX_LINES:
        raise BootConfigError("too_many_lines")
    return [line.decode("ascii") for line in raw_lines]


def _key_value(line: str) -> tuple[str, str]:
    if line.count("=") != 1:
        raise BootConfigError("syntax")
    key, value = line.split("=", 1)
    if not key or not value:
        raise BootConfigError("syntax")
    return key, value


def _parse_number(value: str) -> int:
    if not value or not value.isascii() or not value.isdigit():
        raise BootConfigError("number")
    if len(value) > 1 and value.startswith("0"):
        raise BootConfigError("number_canonical")
    number = 0
    for character in value:
        digit = ord(character) - ord("0")
        if number > (U64_MAX - digit) // 10:
            raise BootConfigError("numeric_overflow")
        number = number * 10 + digit
    return number


def _parse_range(value: str, minimum: int, maximum: int) -> int:
    number = _parse_number(value)
    if not minimum <= number <= maximum:
        raise BootConfigError("range")
    return number


def _valid_identifier(value: str) -> bool:
    return IDENTIFIER.fullmatch(value) is not None and len(value.encode("ascii")) <= MAX_IDENTIFIER_BYTES


def _validate_path(value: str) -> None:
    if len(value) > MAX_MANIFEST_PATH_BYTES or not value.startswith(MANIFEST_ROOT):
        raise BootConfigError("path")
    relative = value[len(MANIFEST_ROOT) :]
    if not relative or "/" in relative or not relative.endswith(".PBM"):
        raise BootConfigError("path")
    components = relative.split("\\")
    for index, component in enumerate(components):
        if not component or component in {".", ".."} or len(component) > 64:
            raise BootConfigError("path")
        body = component[:-4] if index == len(components) - 1 else component
        if not body or not body[0].isupper() or any(character not in "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-" for character in body):
            raise BootConfigError("path")


def _classify_key(key: str) -> str:
    if key in {"entry_count", "default_entry", "timeout_ms", "boot_attempt_limit"}:
        return "known"
    if not key.startswith("entry."):
        return "unknown"
    rest = key[len("entry.") :]
    if "." not in rest:
        return "unknown"
    identifier, field = rest.split(".", 1)
    if not _valid_identifier(identifier):
        return "identifier"
    return "known" if field in {"mode", "slot", "manifest", "manifest_max_bytes"} else "unknown"


def _expect(pairs: list[tuple[str, str]], index: int, key: str) -> str:
    try:
        actual, value = pairs[index - 1]
    except IndexError as error:
        raise BootConfigError("truncated") from error
    if actual == key:
        return value
    classification = _classify_key(actual)
    if classification == "known":
        raise BootConfigError("key_order")
    if classification == "identifier":
        raise BootConfigError("identifier")
    raise BootConfigError("unknown_key")


def _entry_key(key: str, field: str) -> str:
    classification = _classify_key(key)
    if classification == "identifier":
        raise BootConfigError("identifier")
    if classification == "unknown":
        raise BootConfigError("unknown_key")
    if not key.startswith("entry."):
        raise BootConfigError("key_order")
    _, identifier, actual_field = key.split(".")
    if actual_field != field:
        raise BootConfigError("key_order")
    return identifier


def parse(data: bytes, capacity: int = MAX_ENTRIES) -> Config:
    lines = _lex(data)
    first = lines[0]
    if first != MAGIC:
        raise BootConfigError("version" if first.startswith("POOLEOS-BOOTCFG/") else "magic")
    if len(lines) < 6:
        raise BootConfigError("truncated")
    if lines[-1] != END_MARKER:
        raise BootConfigError("end_marker")
    pairs = [_key_value(line) for line in lines[1:-1]]
    seen: set[str] = set()
    for key, _ in pairs:
        if key in seen:
            raise BootConfigError("duplicate_key")
        seen.add(key)

    entry_count = _parse_range(_expect(pairs, 1, "entry_count"), 1, MAX_ENTRIES)
    expected_lines = 6 + entry_count * 4
    if len(lines) < expected_lines:
        raise BootConfigError("truncated")
    if len(lines) > expected_lines:
        key, _ = _key_value(lines[expected_lines - 1])
        classification = _classify_key(key)
        if classification == "known":
            raise BootConfigError("key_order")
        if classification == "identifier":
            raise BootConfigError("identifier")
        raise BootConfigError("unknown_key")
    if capacity < entry_count:
        raise BootConfigError("output_capacity")

    default_entry = _expect(pairs, 2, "default_entry")
    if not _valid_identifier(default_entry):
        raise BootConfigError("identifier")
    timeout_ms = _parse_range(_expect(pairs, 3, "timeout_ms"), 0, MAX_TIMEOUT_MS)
    boot_attempt_limit = _parse_range(_expect(pairs, 4, "boot_attempt_limit"), 1, MAX_BOOT_ATTEMPTS)

    entries: list[Entry] = []
    previous = ""
    for index in range(entry_count):
        base = 4 + index * 4
        mode_key, mode = pairs[base]
        identifier = _entry_key(mode_key, "mode")
        if previous and identifier <= previous:
            raise BootConfigError("entry_order")
        previous = identifier
        slot_key, slot_text = pairs[base + 1]
        manifest_key, manifest = pairs[base + 2]
        limit_key, limit_text = pairs[base + 3]
        if (
            _entry_key(slot_key, "slot") != identifier
            or _entry_key(manifest_key, "manifest") != identifier
            or _entry_key(limit_key, "manifest_max_bytes") != identifier
        ):
            raise BootConfigError("key_order")
        if mode not in MODES:
            raise BootConfigError("mode")
        slot = _parse_range(slot_text, 1, MAX_SLOT)
        _validate_path(manifest)
        manifest_max_bytes = _parse_range(limit_text, 1, MAX_MANIFEST_BYTES)
        entries.append(Entry(identifier, mode, slot, manifest, manifest_max_bytes))
    if default_entry not in {entry.id for entry in entries}:
        raise BootConfigError("default_entry")
    return Config(default_entry, timeout_ms, boot_attempt_limit, tuple(entries))


def encode(
    entries: Iterable[Entry],
    *,
    default_entry: str,
    timeout_ms: int,
    boot_attempt_limit: int,
) -> bytes:
    ordered = tuple(sorted(entries, key=lambda entry: entry.id))
    lines = [
        MAGIC,
        f"entry_count={len(ordered)}",
        f"default_entry={default_entry}",
        f"timeout_ms={timeout_ms}",
        f"boot_attempt_limit={boot_attempt_limit}",
    ]
    for entry in ordered:
        lines.extend(
            (
                f"entry.{entry.id}.mode={entry.mode}",
                f"entry.{entry.id}.slot={entry.slot}",
                f"entry.{entry.id}.manifest={entry.manifest}",
                f"entry.{entry.id}.manifest_max_bytes={entry.manifest_max_bytes}",
            )
        )
    lines.append(END_MARKER)
    encoded = ("\n".join(lines) + "\n").encode("ascii")
    parse(encoded)
    return encoded


def validate_manifest_size(configured_limit: int, observed_size: int) -> None:
    if (
        configured_limit <= 0
        or configured_limit > MAX_MANIFEST_BYTES
        or observed_size <= 0
        or observed_size > configured_limit
        or observed_size > MAX_MANIFEST_BYTES
    ):
        raise BootConfigError("artifact_size")


def summarize(config: Config) -> str:
    result = (
        f"OK;entry_count={len(config.entries)};default_entry={config.default_entry};"
        f"timeout_ms={config.timeout_ms};boot_attempt_limit={config.boot_attempt_limit}"
    )
    for entry in config.entries:
        result += f";entry={entry.id},{entry.mode},{entry.slot},{entry.manifest},{entry.manifest_max_bytes}"
    return result


def parse_result(data: bytes, capacity: int = MAX_ENTRIES) -> str:
    try:
        return summarize(parse(data, capacity))
    except BootConfigError as error:
        return f"ERR:{error.code}"


def size_result(configured_limit: int, observed_size: int) -> str:
    try:
        validate_manifest_size(configured_limit, observed_size)
        return "OK"
    except BootConfigError as error:
        return f"ERR:{error.code}"


def _boundary_path() -> str:
    remaining = MAX_MANIFEST_PATH_BYTES - len(MANIFEST_ROOT) - len(".PBM")
    components: list[str] = []
    while remaining > 64:
        components.append("A" * 64)
        remaining -= 65
    components.append("Z" * remaining)
    path = MANIFEST_ROOT + "\\".join(components) + ".PBM"
    if len(path) != MAX_MANIFEST_PATH_BYTES:
        raise BootConfigError("boundary_path")
    return path


def build_fixture(vector_id: str) -> bytes:
    if vector_id == "minimal_v1":
        return encode(
            (Entry("normal", "normal", 1, MANIFEST_ROOT + "MANIFEST_A.PBM", 65_536),),
            default_entry="normal",
            timeout_ms=0,
            boot_attempt_limit=3,
        )
    if vector_id == "multi_mode_v1":
        entries = (
            Entry("diagnostic", "diagnostic", 4, MANIFEST_ROOT + "DIAGNOSTIC.PBM", 131_072),
            Entry("normal", "normal", 1, MANIFEST_ROOT + "NORMAL.PBM", 524_288),
            Entry("previous", "previous", 2, MANIFEST_ROOT + "PREVIOUS.PBM", 524_288),
            Entry("recovery", "recovery", 3, MANIFEST_ROOT + "RECOVERY.PBM", 262_144),
            Entry("safe", "safe", 1, MANIFEST_ROOT + "SAFE.PBM", 262_144),
        )
        return encode(entries, default_entry="normal", timeout_ms=5_000, boot_attempt_limit=4)
    if vector_id == "bounded_maxima_v1":
        entries = tuple(
            Entry(f"slot_{index}", MODES[index % len(MODES)], MAX_SLOT, _boundary_path() if index == 7 else MANIFEST_ROOT + f"SLOT_{index}.PBM", MAX_MANIFEST_BYTES)
            for index in range(MAX_ENTRIES)
        )
        return encode(entries, default_entry="slot_7", timeout_ms=MAX_TIMEOUT_MS, boot_attempt_limit=MAX_BOOT_ATTEMPTS)
    raise BootConfigError("unknown_fixture")


def make_golden_vectors() -> dict[str, Any]:
    definitions = (
        ("minimal_v1", "Smallest valid PBC1 configuration."),
        ("multi_mode_v1", "All five defined boot modes in canonical entry order."),
        ("bounded_maxima_v1", "Eight entries with maximum numeric and path bounds."),
    )
    vectors = []
    for vector_id, purpose in definitions:
        data = build_fixture(vector_id)
        config = parse(data)
        vectors.append(
            {
                "id": vector_id,
                "purpose": purpose,
                "entry_count": len(config.entries),
                "byte_count": len(data),
                "sha256": sha256_bytes(data),
                "summary": summarize(config),
                "hex": data.hex().upper(),
            }
        )
    return {
        "schema_version": "1.0",
        "artifact_kind": "pooleos_native_boot_config_golden_vectors",
        "contract_id": CONTRACT_ID,
        "status": "synthetic_non_promoting_golden_bytes",
        "production_ready": False,
        "vectors": vectors,
        "claim_boundary": [
            "Vectors are synthetic parser fixtures, not files captured from firmware.",
            "A valid vector proves canonical codec agreement only, not trusted entry selection or artifact loading.",
            "Paths name synthetic manifests and do not attest that any artifact exists or is signed.",
        ],
    }


def expected_contract() -> dict[str, Any]:
    return {
        "schema_version": "1.0",
        "artifact_kind": "pooleos_native_boot_config_contract",
        "contract_id": CONTRACT_ID,
        "status": "candidate_pre_abi_non_promoting",
        "production_ready": False,
        "encoding": {
            "character_set": "ASCII bytes 0x21..0x7E plus LF line terminators",
            "line_ending": "LF",
            "final_lf_required": True,
            "bom_allowed": False,
            "comments_allowed": False,
            "blank_lines_allowed": False,
            "whitespace_allowed": False,
        },
        "grammar": {
            "magic": MAGIC,
            "fixed_keys": ["entry_count", "default_entry", "timeout_ms", "boot_attempt_limit"],
            "entry_key_template": "entry.<id>.<mode|slot|manifest|manifest_max_bytes>",
            "entry_field_order": ["mode", "slot", "manifest", "manifest_max_bytes"],
            "terminal": END_MARKER,
            "entry_order": "strict ascending ASCII identifier order",
            "duplicate_policy": "reject every repeated full key before semantic interpretation",
            "unknown_key_policy": "reject",
            "number_policy": "canonical unsigned decimal u64; no sign or leading zero except zero",
        },
        "limits": {
            "config_bytes": MAX_CONFIG_BYTES,
            "line_bytes": MAX_LINE_BYTES,
            "lines": MAX_LINES,
            "entries": MAX_ENTRIES,
            "identifier_bytes": MAX_IDENTIFIER_BYTES,
            "timeout_ms": MAX_TIMEOUT_MS,
            "boot_attempts": MAX_BOOT_ATTEMPTS,
            "slot": MAX_SLOT,
            "manifest_path_bytes": MAX_MANIFEST_PATH_BYTES,
            "manifest_bytes": MAX_MANIFEST_BYTES,
        },
        "entry_modes": list(MODES),
        "path_policy": {
            "root": MANIFEST_ROOT,
            "separator": "\\",
            "case": "uppercase ASCII path components",
            "component_characters": "A-Z 0-9 underscore hyphen",
            "component_bytes": 64,
            "required_suffix": ".PBM",
            "dot_components_allowed": False,
            "forward_slash_allowed": False,
            "absolute_paths_outside_root_allowed": False,
        },
        "version_policy": {
            "accepted": "1.0",
            "incompatible_major": "reject",
            "unknown_minor": "reject until an explicit compatibility contract exists",
        },
        "artifact_size_policy": {
            "zero_length_allowed": False,
            "configured_limit_required": True,
            "observed_size_must_not_exceed_configured_limit": True,
            "absolute_maximum_bytes": MAX_MANIFEST_BYTES,
        },
        "production_claims": expected_claims(),
        "claim_boundary": [
            "PBC1 is a candidate parser contract and is not an owner-ratified stable ABI.",
            "PooleBoot compiles against the parser but does not yet open or parse a live configuration file.",
            "No vector or receipt proves filesystem discovery, artifact existence, hashing, signature verification, or loading.",
            "No receipt proves boot-menu input, timeout behavior, slot health, fallback, recovery, or diagnostic execution.",
            "No receipt proves ExitBootServices, PBP1 population, PooleKernel transfer, target firmware, or physical media.",
            "No key was generated or used, and no signing, merge, tag, release, firmware mutation, or media write is authorized.",
            "N5 and production readiness remain false.",
        ],
    }


def expected_claims() -> dict[str, bool]:
    return {
        "canonical_grammar_defined": True,
        "rust_no_std_parser_executed": True,
        "independent_python_parser_executed": True,
        "pooleboot_compile_time_dependency": True,
        "golden_semantic_agreement": True,
        "hostile_controls_executed": True,
        "deterministic_differential_fuzz_executed": True,
        "live_config_file_opened": False,
        "live_config_parsed_by_pooleboot": False,
        "boot_entry_selected": False,
        "artifact_loaded": False,
        "artifact_signature_verified": False,
        "target_firmware_tested": False,
        "n5_exit_gate_satisfied": False,
        "production_ready": False,
    }


def contract_errors(contract: dict[str, Any], root: Path = ROOT) -> list[str]:
    schema = read_json(root / CONTRACT_SCHEMA_RELATIVE)
    errors = [f"schema {item.path}: {item.message}" for item in validate_json(contract, schema)]
    if contract != expected_contract():
        errors.append("contract differs from the executable PBC1 constants")
    return errors


def golden_errors(golden: dict[str, Any], root: Path = ROOT) -> list[str]:
    schema = read_json(root / GOLDEN_SCHEMA_RELATIVE)
    errors = [f"schema {item.path}: {item.message}" for item in validate_json(golden, schema)]
    try:
        expected = make_golden_vectors()
    except (BootConfigError, UnicodeError, ValueError) as error:
        return errors + [f"unable to construct vectors: {error}"]
    if golden != expected:
        errors.append("golden vectors do not reproduce exactly")
    return errors


def readiness_errors(readiness: dict[str, Any], root: Path = ROOT) -> list[str]:
    schema = read_json(root / READINESS_SCHEMA_RELATIVE)
    errors = [f"schema {item.path}: {item.message}" for item in validate_json(readiness, schema)]
    try:
        contract = read_json(root / CONTRACT_RELATIVE)
        golden = read_json(root / GOLDEN_RELATIVE)
    except (OSError, json.JSONDecodeError, BootConfigError) as error:
        return errors + [f"unable to read bound contract: {error}"]
    errors.extend(f"contract {item}" for item in contract_errors(contract, root))
    errors.extend(f"golden {item}" for item in golden_errors(golden, root))
    expected_bindings = {
        "contract": file_binding(root / CONTRACT_RELATIVE, root),
        "contract_schema": file_binding(root / CONTRACT_SCHEMA_RELATIVE, root),
        "golden_vectors": file_binding(root / GOLDEN_RELATIVE, root),
        "golden_schema": file_binding(root / GOLDEN_SCHEMA_RELATIVE, root),
        "readiness_schema": file_binding(root / READINESS_SCHEMA_RELATIVE, root),
        "implementation_inputs": [file_binding(root / path, root) for path in IMPLEMENTATION_INPUTS],
    }
    if readiness.get("bindings") != expected_bindings:
        errors.append("readiness input bindings are stale")
    if readiness.get("claims") != expected_claims():
        errors.append("readiness claim boundary changed")
    expected_summary = {
        "rust_host_tests_passed": 12,
        "rust_host_tests_total": 12,
        "no_std_target_builds_passed": 2,
        "no_std_target_builds_total": 2,
        "golden_vectors_matched": 3,
        "golden_vectors_total": 3,
        "negative_controls_passed": len(NEGATIVE_CONTROL_IDS),
        "negative_controls_total": len(NEGATIVE_CONTROL_IDS),
        "differential_fuzz_cases": 16_384,
        "differential_mismatches": 0,
        "production_claim_count": 0,
    }
    if readiness.get("summary") != expected_summary:
        errors.append("readiness summary changed")
    controls = readiness.get("negative_controls", [])
    if [item.get("id") for item in controls if isinstance(item, dict)] != list(NEGATIVE_CONTROL_IDS):
        errors.append("negative control register changed")
    if any(item.get("status") != "pass" for item in controls if isinstance(item, dict)):
        errors.append("negative control did not pass")
    if readiness.get("production_ready") is not False or readiness.get("n5_exit_gate_satisfied") is not False:
        errors.append("readiness overclaims production or N5 exit")
    return errors
