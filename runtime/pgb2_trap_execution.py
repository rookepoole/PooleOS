"""Byte-level simulator for draft PGB2 trap instruction programs."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from runtime import pgb2_trap_encoding


SCHEMA_VERSION = "0.1"
ARTIFACT_KIND = "pooleos.pgb2_trap_execution"
EXECUTION_VERSION = "PGB2_TRAP_EXEC_DRAFT_V0"


def _check(name: str, ok: bool, detail: str) -> dict[str, Any]:
    return {"name": name, "ok": bool(ok), "detail": detail}


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _hex(data: bytes) -> str:
    return " ".join(f"{byte:02X}" for byte in data)


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest().upper()


def _program_bytes(encoding: dict[str, Any]) -> tuple[bytes, str]:
    raw_hex = str(encoding.get("program", {}).get("raw_hex", ""))
    try:
        return bytes.fromhex(raw_hex), ""
    except ValueError as exc:
        return b"", str(exc)


def _source_instruction(encoding: dict[str, Any], index: int) -> dict[str, Any]:
    instructions = encoding.get("instructions", [])
    if isinstance(instructions, list) and index < len(instructions) and isinstance(instructions[index], dict):
        return instructions[index]
    return {}


def _operand_match(decoded: dict[str, Any], source: dict[str, Any]) -> bool:
    expected = source.get("decoded_operands", {})
    if not isinstance(expected, dict):
        return False
    return all(
        decoded.get(key) == expected.get(key)
        for key in ("opcode", "region", "source", "target", "capability", "expected_trap", "trap_code")
    )


def _execute_instruction(
    *,
    index: int,
    start_offset: int,
    next_offset: int,
    decoded: dict[str, Any],
    encoded_bytes: bytes,
    source: dict[str, Any],
) -> dict[str, Any]:
    source_present = bool(source)
    source_expected_trap = source.get("expected_trap") is True if source_present else decoded.get("expected_trap") is True
    source_expected_code = str(source.get("expected_trap_code", "")) if source_present else str(decoded.get("trap_code", ""))
    actual_trapped = decoded.get("expected_trap") is True
    actual_trap_code = str(decoded.get("trap_code", "")) if actual_trapped else ""
    expected_trap_code = source_expected_code if source_expected_trap else ""
    bytes_match = source_present and _hex(encoded_bytes) == source.get("encoded_hex")
    order_match = source_present and source.get("index") == index and _operand_match(decoded, source)
    outcome_match = source_present and actual_trapped == source_expected_trap and actual_trap_code == expected_trap_code

    return {
        "index": index,
        "source_instruction_index": int(source.get("source_operation_index", -1)) if source_present else -1,
        "case_id": str(source.get("case_id", "")) if source_present else "",
        "fuzz_kind": str(source.get("fuzz_kind", "")) if source_present else "",
        "operation_opcode": str(decoded.get("opcode", "")),
        "region": str(decoded.get("region", "")),
        "source": str(decoded.get("source", "")),
        "target": str(decoded.get("target", "")),
        "capability": str(decoded.get("capability", "")),
        "expected_trap": bool(source_expected_trap),
        "expected_trap_code": expected_trap_code,
        "actual_trapped": bool(actual_trapped),
        "actual_trap_code": actual_trap_code,
        "outcome_match": bool(outcome_match),
        "instruction_order_match": bool(order_match),
        "instruction_bytes_match": bool(bytes_match),
        "byte_offset": start_offset,
        "byte_length": next_offset - start_offset,
    }


def make_pgb2_trap_execution(*, trap_encoding_path: Path) -> dict[str, Any]:
    encoding = _read_json(trap_encoding_path) if trap_encoding_path.exists() else {}
    source = encoding.get("source_trap_proof", {}) if isinstance(encoding.get("source_trap_proof", {}), dict) else {}
    summary = encoding.get("summary", {}) if isinstance(encoding.get("summary", {}), dict) else {}
    program_meta = encoding.get("program", {}) if isinstance(encoding.get("program", {}), dict) else {}
    program_data, hex_error = _program_bytes(encoding)
    program_hash = _sha256_bytes(program_data)
    declared_hash = str(program_meta.get("sha256", ""))
    declared_byte_length = int(program_meta.get("byte_length", 0) or 0)
    declared_instruction_count = int(program_meta.get("instruction_count", 0) or 0)
    expected_instruction_count = int(summary.get("instruction_count", declared_instruction_count) or 0)

    executed: list[dict[str, Any]] = []
    decode_errors: list[str] = []
    offset = 0
    if not hex_error:
        while offset < len(program_data):
            index = len(executed)
            start = offset
            try:
                decoded, next_offset = pgb2_trap_encoding.decode_instruction_at(program_data, offset)
            except Exception as exc:
                decode_errors.append(f"offset={offset}: {exc}")
                break
            if next_offset <= start:
                decode_errors.append(f"offset={offset}: decoder did not advance")
                break
            encoded_instruction = program_data[start:next_offset]
            source_instruction = _source_instruction(encoding, index)
            executed.append(
                _execute_instruction(
                    index=index,
                    start_offset=start,
                    next_offset=next_offset,
                    decoded=decoded,
                    encoded_bytes=encoded_instruction,
                    source=source_instruction,
                )
            )
            offset = next_offset

    all_bytes_consumed = not hex_error and offset == len(program_data)
    order_failures = sum(1 for instruction in executed if not instruction["instruction_order_match"])
    byte_failures = sum(1 for instruction in executed if not instruction["instruction_bytes_match"])
    outcome_failures = sum(1 for instruction in executed if not instruction["outcome_match"])
    failed_source_checks = int(source.get("failed_check_count", 0) or 0)
    matrix_bound = source.get("matrix_bound") is True
    fuzz_bound = source.get("fuzz_bound") is True
    core_ir_binding_mode = str(source.get("core_ir_binding_mode", ""))
    core_ir_boundary_status = str(source.get("core_ir_boundary_status", ""))
    parser_kernel_promotion_receipt_bound = source.get("parser_kernel_promotion_receipt_bound") is True
    parser_kernel_promotion_receipt_status = str(source.get("parser_kernel_promotion_receipt_status", ""))
    parser_kernel_promotion_kernel_handoff_allowed = (
        source.get("parser_kernel_promotion_kernel_handoff_allowed") is True
    )
    parser_to_kernel_promotion_allowed = source.get("parser_to_kernel_promotion_allowed") is True
    kernel_enforcement_claimed = source.get("kernel_enforcement_claimed") is True
    security_boundary_claimed = False

    checks = [
        _check("trap_encoding_present", trap_encoding_path.exists(), str(trap_encoding_path)),
        _check(
            "trap_encoding_passed",
            encoding.get("status") == "pass" and int(summary.get("failed_check_count", 0) or 0) == 0,
            f"status={encoding.get('status', 'missing')}; failed_checks={summary.get('failed_check_count', 'missing')}",
        ),
        _check(
            "encoding_version_supported",
            encoding.get("encoding_version") == pgb2_trap_encoding.ENCODING_VERSION,
            f"encoding_version={encoding.get('encoding_version', 'missing')}",
        ),
        _check("program_hex_decoded", not hex_error, "decoded" if not hex_error else hex_error),
        _check(
            "program_hash_matches",
            bool(program_data) and declared_hash == program_hash,
            f"declared={declared_hash}; actual={program_hash}",
        ),
        _check(
            "program_byte_length_matches",
            declared_byte_length == len(program_data),
            f"declared={declared_byte_length}; actual={len(program_data)}",
        ),
        _check(
            "all_bytes_consumed",
            all_bytes_consumed,
            f"consumed={offset}; total={len(program_data)}; decode_errors={len(decode_errors)}",
        ),
        _check(
            "decoded_count_matches_program",
            len(executed) == declared_instruction_count,
            f"program={declared_instruction_count}; executed={len(executed)}",
        ),
        _check(
            "decoded_count_matches_encoding_summary",
            len(executed) == expected_instruction_count,
            f"summary={expected_instruction_count}; executed={len(executed)}",
        ),
        _check(
            "instruction_order_matches",
            order_failures == 0,
            f"order_failures={order_failures}",
        ),
        _check(
            "instruction_bytes_match_manifest",
            byte_failures == 0,
            f"byte_failures={byte_failures}",
        ),
        _check("all_outcomes_match", outcome_failures == 0, f"outcome_failures={outcome_failures}"),
        _check(
            "matrix_and_fuzz_bound",
            matrix_bound and fuzz_bound,
            f"matrix_bound={matrix_bound}; fuzz_bound={fuzz_bound}",
        ),
        _check(
            "core_ir_boundary_source_carried",
            core_ir_binding_mode in {"metadata_only_non_promoting", "phase66_parser_to_kernel_promotable"}
            and not kernel_enforcement_claimed,
            f"binding_mode={core_ir_binding_mode}; boundary_status={core_ir_boundary_status}; kernel_claimed={kernel_enforcement_claimed}",
        ),
        _check(
            "parser_kernel_promotion_receipt_source_carried",
            parser_kernel_promotion_receipt_bound
            and parser_kernel_promotion_receipt_status in {"blocked_until_phase66", "parser_to_kernel_ready"}
            and (
                not parser_kernel_promotion_kernel_handoff_allowed
                or core_ir_binding_mode == "phase66_parser_to_kernel_promotable"
            ),
            (
                f"promotion_bound={parser_kernel_promotion_receipt_bound}; "
                f"promotion_status={parser_kernel_promotion_receipt_status}; "
                f"handoff={parser_kernel_promotion_kernel_handoff_allowed}"
            ),
        ),
        _check("no_failed_source_checks", failed_source_checks == 0, f"failed_source_checks={failed_source_checks}"),
        _check(
            "execution_not_security_boundary",
            security_boundary_claimed is False,
            "draft byte simulator; no booted kernel enforcement claimed",
        ),
    ]
    failed = [check for check in checks if not check["ok"]]

    return {
        "schema_version": SCHEMA_VERSION,
        "artifact_kind": ARTIFACT_KIND,
        "status": "pass" if not failed else "fail",
        "execution_version": EXECUTION_VERSION,
        "encoding_artifact": {
            "artifact_path": str(trap_encoding_path),
            "status": str(encoding.get("status", "")),
            "encoding_version": str(encoding.get("encoding_version", "")),
            "instruction_count": declared_instruction_count,
            "byte_length": declared_byte_length,
            "sha256": declared_hash,
            "matrix_bound": matrix_bound,
            "fuzz_bound": fuzz_bound,
            "core_ir_boundary_status": core_ir_boundary_status,
            "core_ir_binding_mode": core_ir_binding_mode,
            "parser_kernel_promotion_receipt_bound": parser_kernel_promotion_receipt_bound,
            "parser_kernel_promotion_receipt_status": parser_kernel_promotion_receipt_status,
            "parser_kernel_promotion_kernel_handoff_allowed": parser_kernel_promotion_kernel_handoff_allowed,
            "parser_to_kernel_promotion_allowed": parser_to_kernel_promotion_allowed,
            "kernel_enforcement_claimed": kernel_enforcement_claimed,
            "failed_check_count": int(summary.get("failed_check_count", 0) or 0),
        },
        "security_boundary_claimed": security_boundary_claimed,
        "program": {
            "decoded_instruction_count": len(executed),
            "byte_length": len(program_data),
            "sha256": program_hash,
            "all_bytes_consumed": all_bytes_consumed,
        },
        "executed_instructions": executed,
        "decode_errors": decode_errors,
        "checks": checks,
        "summary": {
            "encoded_instruction_count": expected_instruction_count,
            "executed_instruction_count": len(executed),
            "allowed_count": sum(1 for instruction in executed if instruction["actual_trapped"] is False),
            "trapped_count": sum(1 for instruction in executed if instruction["actual_trapped"] is True),
            "matrix_instruction_count": sum(
                1 for instruction in executed if instruction["operation_opcode"] == "ASSERT_MATRIX_PERMISSION"
            ),
            "fuzz_instruction_count": sum(1 for instruction in executed if instruction["case_id"]),
            "byte_length": len(program_data),
            "decode_error_count": len(decode_errors),
            "outcome_mismatch_count": outcome_failures,
            "failed_check_count": len(failed),
        },
        "limitations": [
            "PGB2_TRAP_EXEC_DRAFT_V0 interprets draft trap bytes only; it is not a booted PooleOS kernel.",
            "The simulator validates encoded trap contracts and byte offsets, not hardware isolation.",
            "Opcode semantics are intentionally narrow until PGB2 trap handling reaches an ABI freeze.",
        ],
        "next_steps": [
            "Attach the encoded and executed trap program as an optional PGB2 bundle section.",
            "Run the same byte program inside the PooleOS Lab image once QEMU boot evidence exists.",
            "Replace draft trap contracts with kernel trap handlers after the substrate boundary is live.",
        ],
    }


def write_execution(execution: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(execution, indent=2, sort_keys=True) + "\n", encoding="utf-8")
