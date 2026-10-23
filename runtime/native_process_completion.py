"""PCOMP1 extends the frozen PLAUNCH1 observations, not its historical evidence."""
from __future__ import annotations
import re
from runtime import native_process_launch as launch

END = launch.END
COMPLETION = launch.COMPLETION
ROW = re.compile(r"POOLEOS:KERNEL:LAUNCH-COMPLETED PASS contract=PLAUNCH1 sequence=([0-9]+) child_generation=([0-9]+) outcome_word=([0-9]+) observers=([0-9]+) held_dispatches=([0-9]+)")


def validate_markers(markers: list[str], *, bad_owner: bool = False, supervisor_code_pages: int = 1) -> dict:
    if bad_owner:
        result = launch.validate_markers(markers, bad_owner=True, supervisor_code_pages=supervisor_code_pages)
        result["completions"] = []
        return result
    if len(markers) != 38:
        raise ValueError("completion ordering/count")
    completions = []
    for sequence, index in ((1, 32), (2, 35)):
        match = ROW.fullmatch(markers[index])
        if match is None:
            raise ValueError("missing ordered completion")
        values = list(map(int, match.groups()))
        if values[:4] != [sequence, sequence, (1 << 32) | 100, 1] or not 1 <= values[4] <= 512:
            raise ValueError("completion identity/outcome/deferred dispatch")
        completions.append(dict(zip(("sequence", "child_generation", "outcome_word", "observers", "held_dispatches"), values)))
    result = launch.validate_markers([m for i, m in enumerate(markers) if i not in (32, 35)], supervisor_code_pages=supervisor_code_pages)
    if sum(r["held_dispatches"] for r in completions) >= result["result"]["dispatches"]:
        raise ValueError("completion dispatch accounting")
    result["completions"] = completions
    result["completion_contract_id"] = "PCOMP1"
    return result


def negative_controls(markers: list[str], *, bad_owner: bool = False, supervisor_code_pages: int = 1) -> int:
    validate_markers(markers, bad_owner=bad_owner, supervisor_code_pages=supervisor_code_pages)
    if bad_owner:
        return launch.negative_controls(markers, bad_owner=True, supervisor_code_pages=supervisor_code_pages)
    # Reuse the full historical oracle challenge with only the new rows removed.
    count = launch.negative_controls([m for i, m in enumerate(markers) if i not in (32, 35)], supervisor_code_pages=supervisor_code_pages)
    cases = [markers[:i] + markers[i+1:] for i in range(len(markers))]
    cases += [markers + [markers[-1]], markers[:29] + list(reversed(markers[29:]))]
    for i in (32, 35):
        for match in re.finditer(r"(?<==)[0-9]+(?= |$)", markers[i]):
            changed = markers.copy()
            changed[i] = markers[i][:match.start()] + "0" + markers[i][match.end():]
            cases.append(changed)
    for case in cases:
        try:
            validate_markers(case, supervisor_code_pages=supervisor_code_pages)
        except ValueError:
            continue
        raise ValueError("hostile completion observation accepted")
    return count + len(cases)
