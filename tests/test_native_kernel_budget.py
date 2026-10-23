import copy
import hashlib
import tomllib
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from runtime import native_kernel_budget as budget
from runtime.native_symbols import ElfSymbol

ROOT = Path(__file__).resolve().parents[1]


def fixture():
    values = dict(ro_start=0, ro_used_end=52144, ro_end=53248, text_start=53248,
        text_used_end=647124, text_end=647168, data_start=647168, relro_used_end=727792,
        relro_end=729088, data_used_end=752872, bss_used_end=825752, image_end=827392)
    return SimpleNamespace(entry_offset=53248, relro_offset=647168, relro_byte_count=81920,
        canonical_byte_count=752872, image_byte_count=827392), {"__poole_"+k:v for k,v in values.items()}


class NativeKernelBudgetTests(unittest.TestCase):
    def test_rejected_candidate_layout_does_not_promote_runtime_or_stack(self):
        plan, values = fixture()
        result = budget.measure(plan, values)
        self.assertEqual((result["image_pages"], result["remaining_pages"], result["guarded_stack_pages"]), (202, 6, 36))
        self.assertEqual((result["text_used_bytes"], result["relro_used_bytes"], result["ro_padding_bytes"]), (593876, 80624, 1104))
        self.assertFalse(result["native_execution_verified"] or result["full_stack_bound_proven"] or result["production_ready"])

    def test_bootstrap_capacity_is_inclusive_never_enlarged(self):
        for pages, accepted in ((208, True), (209, False)):
            plan, values = fixture()
            plan.image_byte_count = values["__poole_image_end"] = pages * 4096
            values["__poole_bss_used_end"] = plan.image_byte_count - 1640
            if accepted:
                self.assertEqual(budget.measure(plan, values)["remaining_pages"], 0)
            else:
                with self.assertRaisesRegex(budget.BudgetError, "bootstrap_capacity"):
                    budget.measure(plan, values)

    def test_missing_duplicate_or_nonglobal_symbols_fail_closed(self):
        _, values = fixture()
        symbols = [ElfSymbol(k, 1, 0, 0, 1, v, 0) for k,v in values.items()]
        self.assertEqual(budget.markers(symbols), values)
        for candidate in (symbols[:-1], symbols + [symbols[0]],
                          [ElfSymbol(symbols[0].name, 0, 0, 0, 1, 0, 0)] + symbols[1:]):
            with self.assertRaises(budget.BudgetError):
                budget.markers(candidate)

    def test_each_marker_rejects_negative_bool_or_out_of_range(self):
        plan, values = fixture()
        for key in values:
            for value in (-1, True, 2**64, "0"):
                altered = dict(values, **{key:value})
                with self.subTest(key=key,value=value), self.assertRaises(budget.BudgetError):
                    budget.measure(plan, altered)
        for altered in ({},dict(values,extra=0)):
            with self.assertRaises(budget.BudgetError):
                budget.measure(plan, altered)

    def test_every_plan_binding_and_segment_order_is_checked(self):
        plan, values = fixture()
        for key in vars(plan):
            altered = copy.copy(plan)
            setattr(altered,key,getattr(altered,key)+1)
            with self.subTest(key=key), self.assertRaises(budget.BudgetError):
                budget.measure(altered, values)
        for key in ("ro_used_end", "text_used_end", "relro_used_end", "bss_used_end"):
            altered = dict(values, **{"__poole_"+key:values["__poole_image_end"]+1})
            with self.subTest(key=key), self.assertRaises(budget.BudgetError):
                budget.measure(plan, altered)

    def test_unreviewed_whole_page_padding_is_rejected(self):
        plan, values = fixture()
        for key in ("text_used_end", "relro_used_end", "bss_used_end"):
            altered = dict(values)
            altered["__poole_"+key] -= 4096
            with self.subTest(key=key), self.assertRaisesRegex(budget.BudgetError, "fixed_padding"):
                budget.measure(plan, altered)

    def test_inspector_binds_bytes_and_rejects_nonzero_padding(self):
        # Synthetic parser outputs exercise composition, not native ELF validation.
        plan, values = fixture()
        symbols = [ElfSymbol(k,1,0,0,1,v,0) for k,v in values.items()]
        linked = b"\0" * plan.canonical_byte_count
        with mock.patch.object(budget.image, "canonicalize_linked_image", return_value=(linked,plan)), \
             mock.patch.object(budget.native_symbols, "inspect_debug_elf", return_value=SimpleNamespace(symbols=symbols)):
            result = budget.inspect(linked)
            self.assertEqual(result["linked_sha256"], hashlib.sha256(linked).hexdigest().upper())
            for key in ("ro_used_end", "text_used_end", "relro_used_end"):
                altered = bytearray(linked)
                altered[values["__poole_"+key]]=1
                with self.subTest(key=key), self.assertRaisesRegex(budget.BudgetError, "nonzero_padding"):
                    budget.inspect(bytes(altered))

    def test_existing_profile_and_build_audit_preserve_safety_settings(self):
        config=tomllib.loads((ROOT/'native/Cargo.toml').read_text(encoding='utf-8'))
        release=config['profile']['release']
        self.assertNotIn('package',release)
        self.assertEqual(release['opt-level'],'s')
        self.assertTrue(release['overflow-checks'])
        self.assertEqual(release['panic'],'abort')
        self.assertFalse(release['lto'])
        source=(ROOT/'tools/qualify_native_kernel_entry.py').read_text(encoding='utf-8')
        self.assertIn('budget = kernel_budget.inspect(linked)',source)
        self.assertIn('kernel-budget.json',source)
        linker=(ROOT/'native/kernel/linker.ld').read_text(encoding='utf-8')
        self.assertIn('__poole_image_end <= 0xD0000',linker)
        for name in budget.NAMES:
            self.assertIn(name,linker)
        main=(ROOT/'native/kernel/src/main.rs').read_text(encoding='utf-8')
        boundary=main.index('#[inline(never)]\nfn run_development_diagnostics(')
        self.assertLess(main.index('user_root_probe::run('),boundary)
        self.assertLess(boundary,main.index('let proof = pmm_try!(run_physical_memory_profile('))


if __name__ == '__main__':
    unittest.main()
