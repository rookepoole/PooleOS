"""PKBUDGET1: measure linker-declared use, not runtime safety or future capacity."""
from __future__ import annotations

import hashlib
from collections.abc import Iterable, Mapping

from runtime import native_kernel_image as image
from runtime import native_kernel_map as kmap
from runtime import native_symbols

CONTRACT_ID = "PKBUDGET1"
PAGE = image.PAGE_SIZE
NAMES = frozenset("__poole_" + name for name in (
    "ro_start", "ro_used_end", "ro_end", "text_start", "text_used_end", "text_end",
    "data_start", "relro_used_end", "relro_end", "data_used_end", "bss_used_end", "image_end"))


class BudgetError(ValueError):
    pass


def markers(symbols: Iterable[native_symbols.ElfSymbol]) -> dict[str, int]:
    result = {}
    for symbol in symbols:
        if symbol.name not in NAMES:
            continue
        if symbol.name in result or symbol.binding != 1 or symbol.byte_count != 0:
            raise BudgetError("ambiguous_budget_symbol")
        result[symbol.name] = symbol.value
    if result.keys() != NAMES:
        raise BudgetError("missing_budget_symbol")
    return result


def measure(plan: image.LinkedImagePlan, values: Mapping[str, int]) -> dict:
    if values.keys() != NAMES or any(type(v) is not int or not 0 <= v < 2**64 for v in values.values()):
        raise BudgetError("budget_marker_type_or_set")
    m = {k.removeprefix("__poole_"): v for k, v in values.items()}
    if not (
        m["ro_start"] == 0 < m["ro_used_end"] <= m["ro_end"] == m["text_start"] == plan.entry_offset
        < m["text_used_end"] <= m["text_end"] == m["data_start"] == plan.relro_offset
        < m["relro_used_end"] <= m["relro_end"] < m["data_used_end"] == plan.canonical_byte_count
        <= m["bss_used_end"] <= m["image_end"] == plan.image_byte_count
    ):
        raise BudgetError("budget_layout_order_or_binding")
    if m["relro_end"] - m["data_start"] != plan.relro_byte_count:
        raise BudgetError("budget_relro_binding")
    if any(m[key] % PAGE for key in ("ro_end", "text_end", "relro_end", "image_end")):
        raise BudgetError("budget_page_alignment")
    if any(((m[used] + PAGE - 1) // PAGE) * PAGE != m[end] for used, end in (
        ("text_used_end", "text_end"), ("relro_used_end", "relro_end"), ("bss_used_end", "image_end"))):
        raise BudgetError("budget_unreviewed_fixed_padding")
    pages = plan.image_byte_count // PAGE
    if not 0 < pages <= kmap.KERNEL_PAGE_CAPACITY:
        raise BudgetError("budget_bootstrap_capacity")
    return dict(contract_id=CONTRACT_ID, image_pages=pages,
        reserved_pages=kmap.KERNEL_PAGE_CAPACITY,
        remaining_pages=kmap.KERNEL_PAGE_CAPACITY-pages,
        guarded_stack_pages=kmap.STACK_PAGE_COUNT, entry_offset=plan.entry_offset,
        ro_used_bytes=m["ro_used_end"], ro_padding_bytes=m["ro_end"]-m["ro_used_end"],
        text_used_bytes=m["text_used_end"]-m["text_start"], text_padding_bytes=m["text_end"]-m["text_used_end"],
        relro_used_bytes=m["relro_used_end"]-m["data_start"], relro_padding_bytes=m["relro_end"]-m["relro_used_end"],
        data_bytes=m["data_used_end"]-m["relro_end"], bss_used_bytes=m["bss_used_end"]-m["data_used_end"],
        bss_padding_bytes=m["image_end"]-m["bss_used_end"], linker_markers=dict(values),
        full_stack_bound_proven=False, native_execution_verified=False, production_ready=False)


def inspect(linked: bytes) -> dict:
    canonical, plan = image.canonicalize_linked_image(linked)
    values = markers(native_symbols.inspect_debug_elf(linked).symbols)
    report = measure(plan, values)
    for start, end in (("ro_used_end", "ro_end"), ("text_used_end", "text_end"), ("relro_used_end", "relro_end")):
        if any(linked[values["__poole_" + start]:values["__poole_" + end]]):
            raise BudgetError("budget_nonzero_padding")
    report.update(linked_sha256=hashlib.sha256(linked).hexdigest().upper(),
        canonical_sha256=hashlib.sha256(canonical).hexdigest().upper(),
        linked_bytes=len(linked), canonical_bytes=len(canonical))
    return report
