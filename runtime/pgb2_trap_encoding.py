"""Draft PGB2 byte encodings for capability trap proof operations."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "0.1"
ARTIFACT_KIND = "pooleos.pgb2_trap_encoding"
ENCODING_VERSION = "PGB2_TRAP_DRAFT_V0"

OPERAND_LAYOUT = ["region", "source", "target", "capability", "expected_trap", "trap_code"]
OPCODE_TABLE = {
    "ASSERT_REGION_CAP": 0xE0,
    "SNAPSHOT_REGION": 0xE1,
    "ASSERT_MATRIX_PERMISSION": 0xE2,
}


def _check(name: str, ok: bool, detail: str) -> dict[str, Any]:
    return {"name": name, "ok": bool(ok), "detail": detail}


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _hex(data: bytes) -> str:
    return " ".join(f"{byte:02X}" for byte in data)


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest().upper()


def _write_text_operand(buffer: bytearray, value: str) -> None:
    raw = value.encode("utf-8")
    if len(raw) > 65535:
        raise ValueError("operand too long for PGB2_TRAP_DRAFT_V0")
    buffer.extend(len(raw).to_bytes(2, "little"))
    buffer.extend(raw)


def _read_text_operand(data: bytes, offset: int) -> tuple[str, int]:
    if offset + 2 > len(data):
        raise ValueError("truncated operand length")
    length = int.from_bytes(data[offset : offset + 2], "little")
    offset += 2
    if offset + length > len(data):
        raise ValueError("truncated operand value")
    value = data[offset : offset + length].decode("utf-8")
    return value, offset + length


def opcode_table_records() -> list[dict[str, Any]]:
    return [
        {
            "operation_opcode": name,
            "encoded_opcode_hex": f"{code:02X}",
            "operand_layout": OPERAND_LAYOUT,
        }
        for name, code in sorted(OPCODE_TABLE.items(), key=lambda item: item[1])
    ]


def encode_operation(operation: dict[str, Any]) -> bytes:
    opcode = str(operation.get("opcode", ""))
    if opcode not in OPCODE_TABLE:
        raise ValueError(f"unsupported trap opcode: {opcode}")
    buffer = bytearray([OPCODE_TABLE[opcode]])
    for key in ("region", "source", "target", "capability"):
        _write_text_operand(buffer, str(operation.get(key, "")))
    buffer.append(1 if operation.get("expected_trap") is True else 0)
    _write_text_operand(buffer, str(operation.get("trap_code", "")))
    return bytes(buffer)


def decode_instruction_at(data: bytes, offset: int = 0) -> tuple[dict[str, Any], int]:
    if offset < 0 or offset >= len(data):
        raise ValueError("empty instruction")
    opcode_value = data[offset]
    opcode = next((name for name, value in OPCODE_TABLE.items() if value == opcode_value), "")
    if not opcode:
        raise ValueError(f"unsupported encoded opcode: {opcode_value:02X}")
    offset += 1
    region, offset = _read_text_operand(data, offset)
    source, offset = _read_text_operand(data, offset)
    target, offset = _read_text_operand(data, offset)
    capability, offset = _read_text_operand(data, offset)
    if offset >= len(data):
        raise ValueError("truncated expected_trap flag")
    if data[offset] not in (0, 1):
        raise ValueError(f"invalid expected_trap flag: {data[offset]:02X}")
    expected_trap = data[offset] == 1
    offset += 1
    trap_code, offset = _read_text_operand(data, offset)
    return {
        "opcode": opcode,
        "region": region,
        "source": source,
        "target": target,
        "capability": capability,
        "expected_trap": expected_trap,
        "trap_code": trap_code,
    }, offset


def decode_instruction(data: bytes) -> dict[str, Any]:
    decoded, offset = decode_instruction_at(data, 0)
    if offset != len(data):
        raise ValueError("trailing bytes after instruction")
    return decoded


def _expected_decoded(operation: dict[str, Any]) -> dict[str, Any]:
    return {
        "opcode": str(operation.get("opcode", "")),
        "region": str(operation.get("region", "")),
        "source": str(operation.get("source", "")),
        "target": str(operation.get("target", "")),
        "capability": str(operation.get("capability", "")),
        "expected_trap": operation.get("expected_trap") is True,
        "trap_code": str(operation.get("trap_code", "")),
    }


def make_pgb2_trap_encoding(*, trap_proof_path: Path) -> dict[str, Any]:
    proof = _read_json(trap_proof_path) if trap_proof_path.exists() else {}
    operations = proof.get("operations", [])
    instructions = []
    unsupported = []
    program_bytes = bytearray()

    for index, operation in enumerate(operations):
        try:
            encoded = encode_operation(operation)
            decoded = decode_instruction(encoded)
            expected = _expected_decoded(operation)
            roundtrip_ok = decoded == expected
            program_bytes.extend(encoded)
            instruction = {
                "index": index,
                "source_operation_index": index,
                "case_id": str(operation.get("case_id", "")),
                "fuzz_kind": str(operation.get("fuzz_kind", "")),
                "operation_opcode": str(operation.get("opcode", "")),
                "encoded_opcode_hex": f"{encoded[0]:02X}",
                "byte_length": len(encoded),
                "encoded_hex": _hex(encoded),
                "encoded_sha256": _sha256_bytes(encoded),
                "expected_trap": operation.get("expected_trap") is True,
                "expected_trap_code": str(operation.get("trap_code", "")),
                "decoded_operands": decoded,
                "roundtrip_ok": roundtrip_ok,
            }
            instructions.append(instruction)
        except Exception as exc:
            unsupported.append(f"{index}:{operation.get('opcode')}:{exc}")

    proof_summary = proof.get("summary", {})
    matrix_summary = proof.get("matrix_summary", {})
    fuzz_summary = proof.get("fuzz_summary", {})
    failed_source_checks = int(proof_summary.get("failed_check_count", 0) or 0)
    program = bytes(program_bytes)
    checks = [
        _check("trap_proof_present", trap_proof_path.exists(), str(trap_proof_path)),
        _check(
            "trap_proof_passed",
            proof.get("status") == "pass" and failed_source_checks == 0,
            f"status={proof.get('status', 'missing')}; failed_checks={failed_source_checks}",
        ),
        _check(
            "matrix_bound_in_source",
            matrix_summary.get("matrix_bound") is True,
            f"matrix_bound={matrix_summary.get('matrix_bound')}",
        ),
        _check(
            "fuzz_bound_in_source",
            fuzz_summary.get("fuzz_bound") is True,
            f"fuzz_bound={fuzz_summary.get('fuzz_bound')}",
        ),
        _check(
            "all_operations_supported",
            not unsupported,
            "all source operations have draft opcodes" if not unsupported else "; ".join(unsupported[:5]),
        ),
        _check(
            "all_operations_encoded",
            len(instructions) == len(operations),
            f"source={len(operations)}; encoded={len(instructions)}",
        ),
        _check(
            "all_instructions_roundtrip",
            all(instruction["roundtrip_ok"] for instruction in instructions),
            f"roundtrip_failures={sum(1 for instruction in instructions if not instruction['roundtrip_ok'])}",
        ),
        _check("program_hash_present", bool(program), f"byte_length={len(program)}"),
        _check(
            "trap_metadata_preserved",
            all(
                instruction["decoded_operands"]["expected_trap"] == instruction["expected_trap"]
                and instruction["decoded_operands"]["trap_code"] == instruction["expected_trap_code"]
                for instruction in instructions
            ),
            f"instruction_count={len(instructions)}",
        ),
    ]
    failed = [check for check in checks if not check["ok"]]

    return {
        "schema_version": SCHEMA_VERSION,
        "artifact_kind": ARTIFACT_KIND,
        "status": "pass" if not failed else "fail",
        "encoding_version": ENCODING_VERSION,
        "source_trap_proof": {
            "artifact_path": str(trap_proof_path),
            "status": str(proof.get("status", "")),
            "operation_count": int(proof_summary.get("operation_count", 0) or 0),
            "failed_check_count": failed_source_checks,
            "matrix_bound": matrix_summary.get("matrix_bound") is True,
            "fuzz_bound": fuzz_summary.get("fuzz_bound") is True,
            "core_ir_boundary_status": str(matrix_summary.get("core_ir_boundary_status", "")),
            "core_ir_binding_mode": str(matrix_summary.get("core_ir_binding_mode", "")),
            "core_ir_executable_audit_bound": matrix_summary.get("core_ir_executable_audit_bound") is True,
            "core_ir_executable_audit_status": str(matrix_summary.get("core_ir_executable_audit_status", "")),
            "core_ir_executable_candidate_count": int(matrix_summary.get("core_ir_executable_candidate_count", 0) or 0),
            "core_ir_metadata_zero_count": int(matrix_summary.get("core_ir_metadata_zero_count", 0) or 0),
            "core_ir_kernel_handoff_allowed": matrix_summary.get("core_ir_kernel_handoff_allowed") is True,
            "parser_kernel_promotion_receipt_bound": matrix_summary.get("parser_kernel_promotion_receipt_bound") is True,
            "parser_kernel_promotion_receipt_status": str(matrix_summary.get("parser_kernel_promotion_receipt_status", "")),
            "parser_kernel_promotion_kernel_handoff_allowed": matrix_summary.get("parser_kernel_promotion_kernel_handoff_allowed") is True,
            "parser_to_kernel_promotion_allowed": matrix_summary.get("parser_to_kernel_promotion_allowed") is True,
            "kernel_enforcement_claimed": matrix_summary.get("kernel_enforcement_claimed") is True,
        },
        "opcode_table": opcode_table_records(),
        "program": {
            "instruction_count": len(instructions),
            "byte_length": len(program),
            "raw_hex": _hex(program),
            "sha256": _sha256_bytes(program),
        },
        "instructions": instructions,
        "checks": checks,
        "summary": {
            "source_operation_count": len(operations),
            "instruction_count": len(instructions),
            "byte_length": len(program),
            "allowed_instruction_count": sum(1 for operation in operations if operation.get("expected_trap") is not True),
            "trapped_instruction_count": sum(1 for operation in operations if operation.get("expected_trap") is True),
            "matrix_instruction_count": sum(1 for operation in operations if operation.get("opcode") == "ASSERT_MATRIX_PERMISSION"),
            "fuzz_instruction_count": sum(1 for operation in operations if operation.get("case_id")),
            "failed_check_count": len(failed),
        },
        "limitations": [
            "PGB2_TRAP_DRAFT_V0 is deterministic evidence, not a frozen binary bytecode format.",
            "Encoded instructions preserve trap metadata but are not executed by a booted PooleOS kernel yet.",
            "String operands are UTF-8 length-prefixed draft fields and may change before ABI freeze.",
        ],
        "next_steps": [
            "Add a PGB2 trap execution simulator that interprets these encoded instructions.",
            "Attach the encoded trap program as an optional PGB2 bundle section.",
            "Run encoded trap cases inside the PooleOS Lab image after QEMU boot evidence exists.",
        ],
    }


def write_encoding(encoding: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(encoding, indent=2, sort_keys=True) + "\n", encoding="utf-8")
