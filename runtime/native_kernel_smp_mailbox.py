"""Independent PKMBX1 decoder for saved, quiesced PKSMP5 AP snapshots."""

from __future__ import annotations

import re

CONTRACT_ID = "PKMBX1"
CONTEXT_FIELDS = ("bsp_leaf1_ecx", "bsp_leaf1_edx", "bsp_tsc_before", "bsp_tsc_online_after", "bsp_tsc_quiesced_after")
BASELINE_FIELDS = (
    "magic", "version", "state", "command", "target_apic_id", "bsp_apic_id", "observed_apic_id",
    "leaf1_ecx", "leaf1_edx", "cr0", "cr3", "cr4", "efer", "tsc_online", "tsc_stop",
)
RUNTIME_FIELDS = (
    "baseline_checksum", "runtime_magic", "runtime_version", "runtime_state",
    "expected_gdt_base", "expected_idt_base", "expected_tss_base", "rsp0",
    "ist1_bottom", "ist1_top", "ist2_bottom", "ist2_top", "xstate_base", "xstate_bytes",
    "xstate_owner_initial", "observed_gdt_base", "observed_idt_base", "observed_rsp",
    "xcr0", "xstate_bv", "rflags", "observed_gdt_limit", "observed_idt_limit", "task_selector",
    "code_selector", "data_selector", "installed_gate_count", "owned_interrupt_vector_count",
    "interrupts_enabled", "initial_fcw", "initial_mxcsr", "xstate_owner_final",
    "xstate_save_count", "xstate_restore_count", "fault_code", "supported_xcr0",
    "enabled_area_bytes", "maximum_area_bytes",
)
U64_MAX = (1 << 64) - 1
BASELINE_U32 = frozenset(BASELINE_FIELDS[1:9])
RUNTIME_U32 = frozenset(("runtime_version", "runtime_state", "xstate_bytes", "xstate_owner_initial",
                       *RUNTIME_FIELDS[21:35], "enabled_area_bytes", "maximum_area_bytes"))
WORD_PATTERN = r"0x[0-9A-F]{16}"
CONTRACT = {
    "contract_id": CONTRACT_ID, "snapshot": "quiesced", "encoding": "comma_separated_uppercase_hex_u64",
    "checksum": "fnv1a64_over_u64_little_endian_words",
    "context_fields": list(CONTEXT_FIELDS), "baseline_fields": list(BASELINE_FIELDS), "runtime_fields": list(RUNTIME_FIELDS),
    "baseline_u32_fields": sorted(BASELINE_U32), "runtime_u32_fields": sorted(RUNTIME_U32),
    "context_repeated_identically_for_all_aps": True, "old_opaque_receipts_accepted": False,
    "normalization_after_validation_only": True, "authentication_claim": False,
}


class MailboxEvidenceError(ValueError):
    """The exported snapshot cannot establish the bounded mailbox invariant."""


def require(condition: bool, detail: str) -> None:
    if not condition:
        raise MailboxEvidenceError("PKMBX1 " + detail)


def parse_words(text: str, fields: tuple[str, ...], u32_fields: frozenset[str]) -> dict[str, int]:
    pattern = WORD_PATTERN + rf"(?:,{WORD_PATTERN}){{{len(fields) - 1}}}"
    require(type(text) is str and re.fullmatch(pattern, text) is not None, "word shape/order/count is invalid")
    values = dict(zip(fields, (int(word, 16) for word in text.split(",")), strict=True))
    require(all(values[name] <= 0xFFFF_FFFF for name in u32_fields), "u32 field overflow")
    return values


def checksum(words) -> int:
    value = 0xCBF29CE484222325
    for word in words:
        require(type(word) is int and 0 <= word <= U64_MAX, "checksum input is not u64")
        for byte in word.to_bytes(8, "little"):
            value = ((value ^ byte) * 0x100000001B3) & U64_MAX
    return value


def validate(context_text: str, baseline_text: str, runtime_text: str,
             baseline_digest: int, runtime_digest: int, apic_id: int, start: int) -> dict:
    require(type(apic_id) is int and apic_id in (1, 2, 3), "AP identity is outside the frozen profile")
    require(type(start) is int and start == (0x1000, 0x23000, 0x45000)[apic_id - 1], "private resource placement changed")
    context = parse_words(context_text, CONTEXT_FIELDS, frozenset(CONTEXT_FIELDS[:2]))
    baseline = parse_words(baseline_text, BASELINE_FIELDS, BASELINE_U32)
    runtime = parse_words(runtime_text, RUNTIME_FIELDS, RUNTIME_U32)
    for digest in (baseline_digest, runtime_digest):
        require(type(digest) is int and 0 <= digest <= U64_MAX, "digest is not u64")
    require(baseline_digest == checksum(baseline.values()), "baseline checksum mismatch")
    require(runtime["baseline_checksum"] == baseline_digest, "runtime does not bind this baseline")
    require(runtime_digest == checksum(runtime.values()), "runtime checksum mismatch")

    expected_baseline = {"magic": 0x504B534D50324D42, "version": 2, "state": 3, "command": 1,
                         "target_apic_id": apic_id, "bsp_apic_id": 0, "observed_apic_id": apic_id,
                         "cr3": start + 0x1000}
    require(all(baseline[key] == value for key, value in expected_baseline.items()), "baseline identity/state/root changed")
    ecx_required = (1 << 26) | (1 << 27)
    edx_required = (1 << 9) | (1 << 24) | (1 << 25) | (1 << 26)
    require(baseline["leaf1_ecx"] & ecx_required == ecx_required
            and baseline["leaf1_ecx"] & ~(1 << 27) == context["bsp_leaf1_ecx"] & ~(1 << 27)
            and baseline["leaf1_edx"] == context["bsp_leaf1_edx"]
            and baseline["leaf1_edx"] & edx_required == edx_required, "CPU feature mismatch")
    require(baseline["cr0"] & 0x80010023 == 0x80010023 and baseline["cr0"] & 0xC == 0
            and baseline["cr4"] & 0x40620 == 0x40620 and baseline["efer"] & 0xD00 == 0xD00,
            "control state is invalid")
    require(0 < context["bsp_tsc_before"] <= baseline["tsc_online"] <= context["bsp_tsc_online_after"]
            <= context["bsp_tsc_quiesced_after"]
            and baseline["tsc_online"] <= baseline["tsc_stop"] <= context["bsp_tsc_quiesced_after"],
            "snapshot time bounds are invalid")

    expected_runtime = {
        "runtime_magic": 0x504B525450324355, "runtime_version": 1, "runtime_state": 5,
        "expected_gdt_base": start + 0xF000, "observed_gdt_base": start + 0xF000,
        "expected_idt_base": start + 0x12000, "observed_idt_base": start + 0x12000,
        "expected_tss_base": start + 0xF040, "rsp0": start + 0xA000, "observed_rsp": start + 0xA000,
        "ist1_bottom": start + 0x15000, "ist1_top": start + 0x17000,
        "ist2_bottom": start + 0x19000, "ist2_top": start + 0x1B000,
        "xstate_base": start + 0x1D000, "xstate_bytes": 4096, "xstate_owner_initial": 0x50580000 | apic_id,
        "xcr0": 3, "observed_gdt_limit": 39, "observed_idt_limit": 4095,
        "task_selector": 24, "code_selector": 8, "data_selector": 16,
        "installed_gate_count": 27, "owned_interrupt_vector_count": 19, "interrupts_enabled": 0,
        "initial_fcw": 0x37F, "initial_mxcsr": 0x1F80, "xstate_owner_final": 0,
        "xstate_save_count": 1, "xstate_restore_count": 1, "fault_code": 0,
    }
    require(all(runtime[key] == value for key, value in expected_runtime.items()), "runtime descriptor/stack/xstate/state changed")
    require(runtime["xstate_bv"] & ~3 == 0 and runtime["rflags"] & (1 << 9) == 0
            and runtime["supported_xcr0"] & 3 == 3
            and 576 <= runtime["enabled_area_bytes"] <= runtime["maximum_area_bytes"] <= 4096,
            "runtime feature/interrupt state is invalid")
    return {"contract_id": CONTRACT_ID, "snapshot": "quiesced", "context": context,
            "baseline": baseline, "runtime": runtime, "baseline_checksum": baseline_digest,
            "runtime_checksum": runtime_digest}


def normalized_words(values: dict[str, int], dynamic_fields: tuple[str, ...]) -> str:
    return ",".join("<validated-dynamic>" if name in dynamic_fields else f"0x{value:016X}"
                    for name, value in values.items())
