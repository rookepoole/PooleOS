"""Exercise native atomic guards and reject inconsistent PKATOM1 evidence."""
import copy
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from runtime import native_kernel_atomics as atomics
from tools import pooleos_release_gate as gate
from tools import qualify_native_kernel_atomics as qualifier
from tests.test_native_cpu_entry_provenance import pair_mutations

ROOT = Path(__file__).resolve().parents[1]


def recorded_atomics_mutations(baseline):
    def change(path, value):
        candidate = copy.deepcopy(baseline)
        target = candidate
        for key in path[:-1]:
            target = target[key]
        target[path[-1]] = value
        return candidate

    for family in ("exit", "coverage", "evidence"):
        for label, pair in pair_mutations(baseline["execution"], family):
            yield family + ":" + label, change(("execution",), pair)
    for name in ("kernel_summary", "host_probe", "linked_instruction_audit", "execution", "negative_controls"):
        for value in (None, [], "invalid"):
            yield name + repr(value), change((name,), value)
    for name in ("kernel_summary", "host_probe", "linked_instruction_audit"):
        for key in baseline[name]:
            yield name + "." + key, change((name, key), None)
    for name in ("source_audit", "default_pooleboot", "atomics_pooleboot"):
        for key in baseline["kernel_summary"][name]:
            replacement = "invalid" if baseline["kernel_summary"][name][key] is None else None
            yield name + "." + key, change(("kernel_summary", name, key), replacement)
    for index, symbol in enumerate(baseline["linked_instruction_audit"]["symbols"]):
        for key in symbol:
            yield f"symbol.{index}.{key}", change(("linked_instruction_audit", "symbols", index, key), None)
    for key in baseline["execution"]["media"]:
        yield "media." + key, change(("execution", "media", key), None)
    for key in ("production_ready", "production_promotion_allowed", "n12_exit_gate_satisfied", "flag_n12_concurrency_atomics_001_closed"):
        yield "claim-type." + key, change((key,), int(baseline[key]))
    for key, value in baseline["execution"].items():
        if key in ("runs", "observation", "media"):
            continue
        replacement = float(value) if type(value) is int else 1 if type(value) is bool else "invalid"
        yield "execution." + key, change(("execution", key), replacement)
    for name, fields in baseline["execution"]["observation"].items():
        yield "observation." + name, change(("execution", "observation", name), None)
        if name == "transfer_prefix":
            continue
        for key, value in fields.items():
            replacement = float(value) if type(value) is int else None
            yield "observation." + name + "." + key, change(("execution", "observation", name, key), replacement)
    for index, control in enumerate(baseline["negative_controls"]):
        for key, value in (("case_count", control["case_count"] + 1), ("case_count", float(control["case_count"])),
                           ("status", "fail"), ("expected", "unknown")):
            yield f"control.{index}.{key}.{value}", change(("negative_controls", index, key), value)
    candidate = change(("negative_controls", 0, "case_count"), 2)
    candidate["negative_controls"][4]["case_count"] -= 1
    yield "control.redistributed", candidate
    for value in (None, [], "invalid"):
        yield "root." + repr(value), value
    for value in (None, 7, True, "", "20261004", "2026-10-4", "2026-02-29", "2026-04-31", "2026-13-01", "2026-10-04T00:00:00"):
        yield "date." + repr(value), change(("status_date",), value)


class AtomicsAdmissionTests(unittest.TestCase):
    def baseline(self):
        return atomics.read_json(ROOT / atomics.READINESS_RELATIVE)

    def test_runtime_and_actual_gate_reject_corrupted_records(self):
        baseline = self.baseline()
        self.assertEqual([], atomics.readiness_errors(baseline))
        self.assertTrue(gate.check_native_kernel_atomics_readiness()["ok"])
        for label, candidate in recorded_atomics_mutations(baseline):
            with self.subTest(label=label), patch.object(gate, "_load_schema_artifact", return_value=(candidate, [])):
                self.assertTrue(atomics.readiness_errors(candidate))
                self.assertFalse(gate.check_native_kernel_atomics_readiness()["ok"])

    def test_calendar_dates_are_validated_not_pinned(self):
        for value in ("2024-02-29", "2026-10-04"):
            candidate = self.baseline()
            candidate["status_date"] = value
            self.assertEqual([], atomics.readiness_errors(candidate))

    def test_aggregate_image_identity_and_count_checks_are_independent(self):
        baseline = self.baseline()
        mutations = [(("linked_instruction_audit", key), value)
            for key, value in (("canonical_sha256", "0" * 64), ("linked_sha256", "0" * 64),
                               ("canonical_byte_count", 538264.0), ("canonical_byte_count", 530072),
                               ("image_byte_count", 602112), ("symbol_count", 7.0))]
        mutations.extend([(("kernel_summary", "host_tests_total"), 246.0),
                          (("kernel_summary", "canonical_sha256"), "0" * 64)])
        for path, value in mutations:
            candidate = copy.deepcopy(baseline)
            candidate[path[0]][path[1]] = value
            with self.subTest(path=path, value=value), patch.object(atomics, "readiness_errors", return_value=[]), \
                    patch.object(gate, "_load_schema_artifact", return_value=(candidate, [])):
                self.assertFalse(gate.check_native_kernel_atomics_readiness()["ok"])

    def test_linked_evidence_rejects_rehashed_missing_instructions(self):
        baseline = self.baseline()
        for symbol in baseline["linked_instruction_audit"]["symbols"]:
            candidate = copy.deepcopy(baseline)
            item = next(s for s in candidate["linked_instruction_audit"]["symbols"] if s["symbol"] == symbol["symbol"])
            item["body"] = "0: c3 retq\n# " + " ".join(item["required_instruction_classes"])
            item["body_sha256"] = atomics.sha256_bytes(item["body"].encode())
            candidate["linked_instruction_audit"]["disassembly_sha256"] = atomics.sha256_bytes(
                atomics.canonical_disassembly_bytes(candidate["linked_instruction_audit"]["symbols"]))
            with self.subTest(symbol=symbol["symbol"]), patch.object(gate, "_load_schema_artifact", return_value=(candidate, [])):
                self.assertTrue(atomics.readiness_errors(candidate))
                self.assertFalse(gate.check_native_kernel_atomics_readiness()["ok"])

    def test_disassembly_requires_real_instruction_lines(self):
        baseline = self.baseline()["linked_instruction_audit"]
        text = "\n".join(f"00000000 <{s['symbol']}>:\n{s['body']}" for s in baseline["symbols"])
        self.assertEqual(7, qualifier._validate_disassembly(text)["symbol_count"])
        for symbol in baseline["symbols"]:
            candidate = text.replace(symbol["body"], "0: c3 retq\n# " + " ".join(symbol["required_instruction_classes"]), 1)
            with self.subTest(symbol=symbol["symbol"]), self.assertRaises(qualifier.QualificationError):
                qualifier._validate_disassembly(candidate)
        for old, new in (("48 0f c1 07", "48 01 07 90"), ("(%rdi)", "%rdi"),
                         ("%rsi, (%rdi)", "%rdi, (%rsi)"), ("\tlock", "\tnop"),
                         ("75 f3", "75 f4"), ("+0x7>", "+0x8>"), ("\tretq", "\tcallq")):
            self.assertIn(old, text)
            with self.subTest(mutation=old), self.assertRaises(qualifier.QualificationError):
                qualifier._validate_disassembly(text.replace(old, new, 1))

    def test_empty_and_disabled_control_validators_cannot_pass(self):
        for operations in ([], [lambda: None]):
            with self.assertRaises(qualifier.QualificationError):
                qualifier._require_rejections("disabled", operations)
        baseline = self.baseline()
        disassembly = "\n".join(f"00000000 <{s['symbol']}>:\n{s['body']}" for s in baseline["linked_instruction_audit"]["symbols"])
        source = baseline["kernel_summary"]["source_audit"]["files"]
        texts = tuple((ROOT / source[key]["path"]).read_text(encoding="utf-8")
                      for key in ("core", "main", "kernel_lib", "boot_exit", "boot_manifest", "bootexit"))
        args = (baseline["execution"]["runs"][0]["markers"], baseline["host_probe"]["lines"], disassembly, texts)
        self.assertEqual(atomics.expected_controls(), qualifier._negative_controls(*args))
        for name in ("_validate_disassembly", "_audit_atomic_source"):
            with self.subTest(validator=name), patch.object(qualifier, name, return_value={}):
                with self.assertRaises(qualifier.QualificationError):
                    qualifier._negative_controls(*args)


class NativeAtomicGuardTests(unittest.TestCase):
    def test_native_tests_detect_disabled_guards_at_both_optimization_levels(self):
        source = (ROOT / "native/kernel/src/atomics.rs").read_text(encoding="utf-8")
        _, rustc, env = qualifier.qualify_native_kernel_entry._toolchain(qualifier.DEFAULT_TOOLCHAIN_ROOT)
        mutations = {
            "load": ("Err(OrderError::InvalidLoad)", "Ok(LoadOrder::Relaxed)"),
            "store": ("Err(OrderError::InvalidStore)", "Ok(StoreOrder::Relaxed)"),
            "fence": ("MemoryOrder::Relaxed => Err(OrderError::InvalidFence)", "MemoryOrder::Relaxed => Ok(FenceOrder::SeqCst)"),
            "cas": ("if valid {", "if true {"),
            "bit-width": ("if bit >= <$value>::BITS {", "if false {"),
            "initial-count": ("if value == 0 || value > MAX_REFCOUNT {", "if false {"),
            "overflow": ("if observed == MAX_REFCOUNT {", "if false {"),
            "underflow": ("if observed == 0 {", "if false {"),
        }
        with tempfile.TemporaryDirectory(prefix="pkatom1-guards-", dir=ROOT / "tmp") as temporary:
            work = Path(temporary)
            for optimization in (0, 3):
                for label in ("baseline", *mutations):
                    modified = source
                    if label != "baseline":
                        old, new = mutations[label]
                        self.assertEqual(2 if label in ("bit-width", "underflow") else 1, source.count(old))
                        modified = source.replace(old, new)
                    path = work / f"{label}-{optimization}.rs"
                    path.write_text(modified, encoding="utf-8")
                    exe = path.with_suffix(".exe")
                    built = subprocess.run([str(rustc), "--edition=2024", "--crate-name", "atomic_guards", "--test",
                        str(path), "-C", f"opt-level={optimization}", "-o", str(exe)], env=env, cwd=ROOT,
                        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=60,
                        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
                    self.assertEqual(0, built.returncode, built.stdout.decode(errors="replace"))
                    result = subprocess.run([str(exe)], env=env, cwd=ROOT, stdout=subprocess.PIPE,
                        stderr=subprocess.STDOUT, timeout=15, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
                    output = result.stdout.decode(errors="replace")
                    with self.subTest(optimization=optimization, disabled=label):
                        if label == "baseline":
                            self.assertEqual(0, result.returncode, output)
                            self.assertIn("7 passed; 0 failed; 0 ignored", output)
                        else:
                            self.assertNotEqual(0, result.returncode, output)
                            self.assertIn("FAILED", output)
