"""Execute published PDC verifiers and reproduce their exact families independently."""

from __future__ import annotations

import csv
import io
import json
import math
import os
import platform
import shutil
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Iterable, Sequence
from zipfile import ZipFile

import numpy as np

from runtime import pdc_reference
from runtime import pdc_verifier_intake


PLANAR_DATA_MEMBERS = {
    "rectangle": pdc_verifier_intake.PLANAR_ROOT + "evidence/data/rectangle_square_channel_W_full3d_audit.csv",
    "line_hole": pdc_verifier_intake.PLANAR_ROOT + "evidence/data/line_hole_edge_case_law_audit.csv",
    "arbitrary_mask": pdc_verifier_intake.PLANAR_ROOT + "evidence/data/arbitrary_planar_selector_random_audit.csv",
    "inversion": pdc_verifier_intake.PLANAR_ROOT + "evidence/data/qp_rectangle_inversion_audit.csv",
}
NONPLANAR_DATA_MEMBERS = {
    "nonplanar_rows": "nonplanar_exact_formula_verifier.csv",
    "nonplanar_summary": "nonplanar_exact_formula_summary.csv",
}
DECLARED_COUNTS = {
    "rectangle": 841,
    "line_hole": 80,
    "arbitrary_mask": 720,
    "inversion": 1225,
    "solid_cuboid": 729,
    "surface_shell": 729,
}


class PdcVerifierReproductionError(ValueError):
    """Raised when source execution or independent reproduction cannot be trusted."""


def _package_version(name: str) -> str:
    try:
        return version(name)
    except PackageNotFoundError:
        return "not_installed"


def _load_json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def _source_by_id(intake: dict[str, object], source_id: str) -> dict[str, object]:
    for item in intake["selected_sources"]:  # type: ignore[index]
        if item["id"] == source_id:
            return item
    raise PdcVerifierReproductionError(f"verifier intake is missing {source_id}")


def _csv_rows_from_bytes(payload: bytes) -> list[dict[str, str]]:
    return list(csv.DictReader(io.StringIO(payload.decode("utf-8-sig"))))


def _csv_rows_from_archive(path: Path, member: str) -> list[dict[str, str]]:
    with ZipFile(path) as archive:
        return _csv_rows_from_bytes(archive.read(member))


def _csv_rows_from_path(path: Path) -> list[dict[str, str]]:
    return list(csv.DictReader(path.read_text(encoding="utf-8-sig").splitlines()))


def _atomic_copy(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(destination.suffix + ".tmp")
    try:
        shutil.copyfile(source, temporary)
        os.replace(temporary, destination)
    finally:
        if temporary.exists():
            temporary.unlink()


def _canonical_csv_bytes(payload: bytes) -> bytes:
    text = payload.decode("utf-8-sig").replace("\r\n", "\n").replace("\r", "\n")
    return text.encode("utf-8")


def _run_source(command: Sequence[str], *, cwd: Path, timeout_seconds: int) -> dict[str, object]:
    environment = os.environ.copy()
    environment["MPLBACKEND"] = "Agg"
    environment["PYTHONHASHSEED"] = "0"
    started_utc = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    started = time.perf_counter()
    try:
        completed = subprocess.run(
            list(command),
            cwd=cwd,
            env=environment,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
            timeout=timeout_seconds,
        )
    except subprocess.TimeoutExpired as exc:
        raise PdcVerifierReproductionError(f"source verifier exceeded {timeout_seconds}s: {command}") from exc
    duration = time.perf_counter() - started
    return {
        "command": list(command),
        "working_directory": str(cwd),
        "started_utc": started_utc,
        "duration_seconds": round(duration, 6),
        "return_code": completed.returncode,
        "stdout_sha256": pdc_verifier_intake.sha256_bytes(completed.stdout),
        "stderr_sha256": pdc_verifier_intake.sha256_bytes(completed.stderr),
        "stdout_tail": completed.stdout.decode("utf-8", errors="replace")[-4000:],
        "stderr_tail": completed.stderr.decode("utf-8", errors="replace")[-4000:],
    }


def _output_record(
    *,
    output_id: str,
    generated: Path,
    published_payload: bytes,
    destination: Path,
    workspace: Path,
) -> dict[str, object]:
    if not generated.is_file():
        raise PdcVerifierReproductionError(f"source verifier did not emit {generated}")
    _atomic_copy(generated, destination)
    generated_hash = pdc_verifier_intake.sha256_file(destination)
    published_hash = pdc_verifier_intake.sha256_bytes(published_payload)
    generated_payload = destination.read_bytes()
    generated_canonical = _canonical_csv_bytes(generated_payload)
    published_canonical = _canonical_csv_bytes(published_payload)
    byte_match = generated_hash == published_hash and destination.stat().st_size == len(published_payload)
    canonical_match = generated_canonical == published_canonical
    return {
        "id": output_id,
        "preserved_path": destination.relative_to(workspace).as_posix(),
        "sha256": generated_hash,
        "size_bytes": destination.stat().st_size,
        "published_sha256": published_hash,
        "published_size_bytes": len(published_payload),
        "byte_match": byte_match,
        "canonical_lf_sha256": pdc_verifier_intake.sha256_bytes(generated_canonical),
        "published_canonical_lf_sha256": pdc_verifier_intake.sha256_bytes(published_canonical),
        "canonical_lf_match": canonical_match,
        "serialization_difference": "none" if byte_match else "line_endings_crlf_vs_lf_only",
        "row_count": len(_csv_rows_from_path(destination)),
    }


def execute_published_sources(
    *, workspace: Path, intake: dict[str, object], timeout_seconds: int = 300
) -> tuple[list[dict[str, object]], dict[str, Path]]:
    workspace = workspace.resolve()
    runs = workspace / "runs"
    runs.mkdir(parents=True, exist_ok=True)
    planar = _source_by_id(intake, "VER-SRC-PLANAR-V1_1")
    nonplanar_runner = _source_by_id(intake, "VER-SRC-NONPLANAR-RUNNER-V1_3_3")
    nonplanar_results = _source_by_id(intake, "VER-SRC-NONPLANAR-RESULTS-V1_3_3")
    planar_archive_path = workspace / planar["stored_path"]
    nonplanar_results_path = workspace / nonplanar_results["stored_path"]

    preserved: dict[str, Path] = {}
    execution_records: list[dict[str, object]] = []
    with tempfile.TemporaryDirectory(prefix="pdc-verifier-cycle75-", dir=runs) as temporary_name:
        temporary = Path(temporary_name)
        planar_work = temporary / "planar"
        nonplanar_work = temporary / "nonplanar"
        planar_work.mkdir()
        nonplanar_work.mkdir()

        planar_output = planar_work / "evidence"
        planar_command = [
            sys.executable,
            str(workspace / planar["executable_path"]),
            "--out",
            str(planar_output),
            "--seed",
            "20260620",
        ]
        planar_run = _run_source(planar_command, cwd=planar_work, timeout_seconds=timeout_seconds)
        if planar_run["return_code"] != 0:
            raise PdcVerifierReproductionError(f"planar source verifier failed: {planar_run['stderr_tail']}")
        planar_outputs = []
        with ZipFile(planar_archive_path) as archive:
            for output_id, member in PLANAR_DATA_MEMBERS.items():
                generated = planar_output / "data" / Path(member).name
                destination = workspace / "runs" / "pdc_verifier_source_outputs" / "planar" / Path(member).name
                record = _output_record(
                    output_id=output_id,
                    generated=generated,
                    published_payload=archive.read(member),
                    destination=destination,
                    workspace=workspace,
                )
                planar_outputs.append(record)
                preserved[output_id] = destination
        planar_run.update(
            {
                "id": "source-execution-planar-v1_1",
                "source_id": planar["id"],
                "source_sha256": planar["sha256"],
                "required_outputs": planar_outputs,
                "status": (
                    "pass"
                    if all(item["byte_match"] for item in planar_outputs)
                    else "pass_with_documented_serialization_drift"
                    if all(item["canonical_lf_match"] for item in planar_outputs)
                    else "fail"
                ),
            }
        )
        execution_records.append(planar_run)

        nonplanar_command = [sys.executable, str(workspace / nonplanar_runner["executable_path"])]
        nonplanar_run = _run_source(nonplanar_command, cwd=nonplanar_work, timeout_seconds=timeout_seconds)
        if nonplanar_run["return_code"] != 0:
            raise PdcVerifierReproductionError(f"nonplanar source verifier failed: {nonplanar_run['stderr_tail']}")
        generated_root = nonplanar_work / "poole_limitation_closure_v1_3_3_output"
        nonplanar_outputs = []
        with ZipFile(nonplanar_results_path) as archive:
            for output_id, member in NONPLANAR_DATA_MEMBERS.items():
                generated = generated_root / member
                destination = workspace / "runs" / "pdc_verifier_source_outputs" / "nonplanar" / Path(member).name
                record = _output_record(
                    output_id=output_id,
                    generated=generated,
                    published_payload=archive.read(member),
                    destination=destination,
                    workspace=workspace,
                )
                nonplanar_outputs.append(record)
                preserved[output_id] = destination
        nonplanar_run.update(
            {
                "id": "source-execution-nonplanar-v1_3_3",
                "source_id": nonplanar_runner["id"],
                "source_sha256": nonplanar_runner["sha256"],
                "required_outputs": nonplanar_outputs,
                "status": (
                    "pass"
                    if all(item["byte_match"] for item in nonplanar_outputs)
                    else "pass_with_documented_serialization_drift"
                    if all(item["canonical_lf_match"] for item in nonplanar_outputs)
                    else "fail"
                ),
            }
        )
        execution_records.append(nonplanar_run)

    if any(item["status"] == "fail" for item in execution_records):
        raise PdcVerifierReproductionError("published source execution did not reproduce canonical required output rows")
    return execution_records, preserved


def _bool_value(value: str) -> bool:
    if value == "True":
        return True
    if value == "False":
        return False
    raise PdcVerifierReproductionError(f"invalid published boolean {value!r}")


def _typed_equal(published: str, independent: object) -> bool:
    if isinstance(independent, bool):
        return _bool_value(published) is independent
    if isinstance(independent, int):
        return int(published) == independent
    if isinstance(independent, float):
        return math.isclose(float(published), independent, rel_tol=0.0, abs_tol=5e-13)
    return published == str(independent)


def _independent_mismatches(
    family: str,
    published: Sequence[dict[str, str]],
    independent: Sequence[dict[str, object]],
    keys: Sequence[str],
) -> tuple[int, list[dict[str, object]]]:
    mismatch_count = 0
    samples: list[dict[str, object]] = []
    if len(published) != len(independent):
        mismatch_count += abs(len(published) - len(independent)) or 1
        samples.append(
            {
                "family": family,
                "row": -1,
                "field": "row_count",
                "published": len(published),
                "independent": len(independent),
            }
        )
    for index, (expected, actual) in enumerate(zip(published, independent, strict=False), start=1):
        for key in keys:
            if key not in expected or key not in actual or not _typed_equal(expected[key], actual[key]):
                mismatch_count += 1
                if len(samples) < 25:
                    samples.append(
                        {
                            "family": family,
                            "row": index,
                            "field": key,
                            "published": expected.get(key),
                            "independent": actual.get(key),
                        }
                    )
    return mismatch_count, samples


def _semantic_csv_mismatch_count(
    published: Sequence[dict[str, str]], reproduced: Sequence[dict[str, str]]
) -> int:
    mismatch_count = abs(len(published) - len(reproduced))
    for left, right in zip(published, reproduced, strict=False):
        if left != right:
            mismatch_count += 1
    return mismatch_count


def _rectangle_rows() -> tuple[list[dict[str, object]], int]:
    rows: list[dict[str, object]] = []
    formula_mismatches = 0
    for a in range(2, 31):
        for b in range(2, 31):
            shape = (a + 6, b + 6)
            defects = pdc_reference.rectangle_defect_field(a, b, shape, origin=(3, 3))
            observed = pdc_reference.planar_first_step_summary(defects, shape)
            raw = pdc_reference.rectangle_formula(a, b)
            prime = pdc_reference.rectangle_formula(a, b, model_tag="PMphi.default.remove_B7")
            active0 = 64 * 64 - a * b
            active1 = active0 + observed.total_births - observed.deaths
            overcomp_actual = active1 > 64 * 64
            overcomp_predicted = (a - 4) * (b - 4) < 28
            raw_match = observed.total_births == raw["births"] and observed.deaths == 0
            channel_match = observed.birth_spectrum == raw["birth_spectrum"]
            prime_actual = observed.birth_spectrum["B5"] + observed.birth_spectrum["B6"]
            prime_match = prime_actual == prime["births"]
            overcomp_match = overcomp_actual == overcomp_predicted
            formula_mismatches += int(not (raw_match and channel_match and prime_match and overcomp_match))
            rows.append(
                {
                    "a": a,
                    "b": b,
                    "area": a * b,
                    "perimeter": 2 * (a + b),
                    "active0": active0,
                    "births_raw_actual": observed.total_births,
                    "births_raw_predicted": raw["births"],
                    "deaths_actual": observed.deaths,
                    "n5_actual": observed.birth_spectrum["B5"],
                    "n6_actual": observed.birth_spectrum["B6"],
                    "n7_actual": observed.birth_spectrum["B7"],
                    "n5_predicted": raw["birth_spectrum"]["B5"],
                    "n6_predicted": raw["birth_spectrum"]["B6"],
                    "n7_predicted": raw["birth_spectrum"]["B7"],
                    "births_prime_actual": prime_actual,
                    "births_prime_predicted": prime["births"],
                    "active1_raw_actual": active1,
                    "active1_raw_predicted": active0 + raw["births"],
                    "overcomp_actual": overcomp_actual,
                    "overcomp_predicted": overcomp_predicted,
                    "raw_match": raw_match,
                    "channel_match": channel_match,
                    "prime_match": prime_match,
                    "overcomp_match": overcomp_match,
                }
            )
    return rows, formula_mismatches


def _line_rows() -> tuple[list[dict[str, object]], int]:
    rows: list[dict[str, object]] = []
    formula_mismatches = 0
    for length in range(1, 81):
        shape = (7, length + 6)
        defects = pdc_reference.line_defect_field(length, shape, origin=(3, 3), axis="y")
        observed = pdc_reference.planar_first_step_summary(defects, shape)
        formula = pdc_reference.line_hole_formula(length)
        prime_actual = observed.birth_spectrum["B5"] + observed.birth_spectrum["B6"]
        prime_predicted = 0 if length == 1 else 7 * length - 14
        raw_match = observed.total_births == formula["births"] and observed.deaths == 0
        prime_match = prime_actual == prime_predicted
        formula_mismatches += int(not (raw_match and prime_match))
        rows.append(
            {
                "n": length,
                "area": length,
                "births_raw_actual": observed.total_births,
                "births_raw_predicted": formula["births"],
                "deaths_actual": observed.deaths,
                "n5_actual": observed.birth_spectrum["B5"],
                "n6_actual": observed.birth_spectrum["B6"],
                "n7_actual": observed.birth_spectrum["B7"],
                "births_prime_actual": prime_actual,
                "births_prime_predicted": prime_predicted,
                "raw_match": raw_match,
                "prime_match": prime_match,
            }
        )
    return rows, formula_mismatches


def _arbitrary_mask_rows(seed: int = 20260620) -> tuple[list[dict[str, object]], int]:
    rng = np.random.default_rng(seed)
    rows: list[dict[str, object]] = []
    matrix_scalar_mismatches = 0
    for case_id in range(1, 721):
        box_w = int(rng.integers(3, 13))
        box_h = int(rng.integers(3, 13))
        density = float(rng.uniform(0.07, 0.62))
        coords = set()
        for x in range(box_w):
            for y in range(box_h):
                if rng.random() < density:
                    coords.add((x, y))
        if not coords:
            coords.add((box_w // 2, box_h // 2))
        if len(coords) == box_w * box_h:
            coords.remove((box_w // 2, box_h // 2))
        shape = (box_w + 6, box_h + 6)
        shifted = ((x + 3, y + 3) for x, y in coords)
        defects = pdc_reference.defect_field_2d(shape, shifted)
        scalar_counts = pdc_reference.scalar_planar_counts(defects, shape)
        matrix_counts = pdc_reference.matrix_planar_counts(defects, shape)
        matrix_scalar_mismatches += int(scalar_counts != matrix_counts)
        observed = pdc_reference.planar_first_step_summary(defects, shape)
        rows.append(
            {
                "case_id": case_id,
                "seed": seed,
                "box_w": box_w,
                "box_h": box_h,
                "density": round(density, 6),
                "removed_count": len(coords),
                "actual_births": observed.total_births,
                "predicted_births": observed.total_births,
                "actual_deaths": observed.deaths,
                "predicted_deaths": observed.deaths,
                "actual_plane_births": observed.in_plane_births,
                "predicted_plane_births": observed.in_plane_births,
                "actual_adjacent_births": observed.normal_layer_births,
                "predicted_adjacent_births": observed.normal_layer_births,
                "actual_nonlocal_events": 0,
                "match": scalar_counts == matrix_counts,
            }
        )
    return rows, matrix_scalar_mismatches


def _recover_rectangle(area: int, side_sum: int) -> tuple[int, int] | None:
    discriminant = side_sum * side_sum - 4 * area
    if discriminant < 0:
        return None
    root = math.isqrt(discriminant)
    if root * root != discriminant or (side_sum - root) % 2 or (side_sum + root) % 2:
        return None
    result = ((side_sum - root) // 2, (side_sum + root) // 2)
    return tuple(sorted(result)) if result[0] * result[1] == area else None


def _inversion_rows() -> tuple[list[dict[str, object]], int]:
    rows: list[dict[str, object]] = []
    formula_mismatches = 0
    for a in range(2, 37):
        for b in range(2, 37):
            area = a * b
            raw_births = int(pdc_reference.rectangle_formula(a, b)["births"])
            prime_births = int(
                pdc_reference.rectangle_formula(a, b, model_tag="PMphi.default.remove_B7")["births"]
            )
            raw = _recover_rectangle(area, (raw_births - 12) // 4)
            prime = _recover_rectangle(area, (prime_births + 4) // 4)
            target = tuple(sorted((a, b)))
            raw_match = raw == target
            prime_match = prime == target
            formula_mismatches += int(not (raw_match and prime_match))
            rows.append(
                {
                    "a": a,
                    "b": b,
                    "area": area,
                    "raw_births": raw_births,
                    "prime_births": prime_births,
                    "recovered_raw_a": -1 if raw is None else raw[0],
                    "recovered_raw_b": -1 if raw is None else raw[1],
                    "recovered_prime_a": -1 if prime is None else prime[0],
                    "recovered_prime_b": -1 if prime is None else prime[1],
                    "raw_match": raw_match,
                    "prime_match": prime_match,
                }
            )
    return rows, formula_mismatches


def _nonplanar_rows(family: str) -> tuple[list[dict[str, object]], int]:
    rows: list[dict[str, object]] = []
    formula_mismatches = 0
    shape = (40, 40, 40)
    for a in range(4, 13):
        for b in range(4, 13):
            for c in range(4, 13):
                if family == "solid_cuboid":
                    coords = pdc_reference.solid_cuboid_coords(a, b, c, shape)
                    formula = pdc_reference.cuboid_formula(a, b, c)
                elif family == "surface_shell":
                    coords = pdc_reference.closed_surface_shell_coords(a, b, c, shape)
                    formula = pdc_reference.closed_shell_formula(a, b, c)
                else:
                    raise PdcVerifierReproductionError(f"unsupported nonplanar family {family}")
                observed = pdc_reference.sparse_first_response(coords, shape)
                formula_match = (
                    observed.initial_active == formula["active_0"]
                    and observed.births == formula["births"]
                    and observed.deaths == formula["deaths"]
                    and observed.final_active == formula["active_1"]
                    and observed.birth_spectrum == formula["birth_spectrum"]
                    and observed.death_spectrum["D_low"] == 0
                    and observed.death_spectrum["D_high"] == formula["deaths"]
                )
                formula_mismatches += int(not formula_match)
                rows.append(
                    {
                        "family": family,
                        "a": a,
                        "b": b,
                        "c": c,
                        "L": 40,
                        "initial_active": observed.initial_active,
                        "births": observed.births,
                        "deaths": observed.deaths,
                        "events": observed.events,
                        "final_active": observed.final_active,
                        "B5": observed.birth_spectrum["B5"],
                        "B6": observed.birth_spectrum["B6"],
                        "B7": observed.birth_spectrum["B7"],
                        "D_low": observed.death_spectrum["D_low"],
                        "D_high": observed.death_spectrum["D_high"],
                        "S5": observed.survival_spectrum["S5"],
                        "S6": observed.survival_spectrum["S6"],
                        "S7": observed.survival_spectrum["S7"],
                        "S8": observed.survival_spectrum["S8"],
                        "S9": observed.survival_spectrum["S9"],
                        "expected_initial_active": formula["active_0"],
                        "expected_births": formula["births"],
                        "expected_deaths": formula["deaths"],
                        "expected_final_active": formula["active_1"],
                        "expected_B5": formula["birth_spectrum"]["B5"],
                        "expected_B6": formula["birth_spectrum"]["B6"],
                        "expected_B7": formula["birth_spectrum"]["B7"],
                        "expected_D_low": 0,
                        "expected_D_high": formula["deaths"],
                        "formula_match": formula_match,
                    }
                )
    return rows, formula_mismatches


def _family_record(
    *,
    family: str,
    published: list[dict[str, str]],
    reproduced: list[dict[str, str]],
    independent: list[dict[str, object]],
    keys: Sequence[str],
    source_output: dict[str, object],
    formula_mismatches: int,
    secondary_mismatches: int,
    published_pass_fields: Sequence[str],
) -> tuple[dict[str, object], list[dict[str, object]]]:
    independent_mismatch_count, samples = _independent_mismatches(family, published, independent, keys)
    source_semantic_mismatches = _semantic_csv_mismatch_count(published, reproduced)
    published_failed = sum(
        any(not _bool_value(row[field]) for field in published_pass_fields) for row in published
    )
    status = "pass" if not (
        independent_mismatch_count
        or source_semantic_mismatches
        or formula_mismatches
        or secondary_mismatches
        or published_failed
        or not source_output["canonical_lf_match"]
        or len(independent) != DECLARED_COUNTS[family]
    ) else "fail"
    return (
        {
            "id": family,
            "declared_case_count": DECLARED_COUNTS[family],
            "published_case_count": len(published),
            "source_execution_case_count": len(reproduced),
            "independent_case_count": len(independent),
            "source_execution_raw_byte_match": source_output["byte_match"],
            "source_execution_canonical_lf_match": source_output["canonical_lf_match"],
            "source_execution_semantic_mismatch_count": source_semantic_mismatches,
            "published_failed_case_count": published_failed,
            "independent_source_mismatch_count": independent_mismatch_count,
            "formula_mismatch_count": formula_mismatches,
            "secondary_oracle_mismatch_count": secondary_mismatches,
            "cases_digest_sha256": pdc_verifier_intake.sha256_json(independent),
            "status": status,
        },
        samples,
    )


def make_verifier_reproduction(
    *,
    workspace: Path,
    verifier_intake_path: Path,
    math_contract_path: Path,
    execute_sources: bool = True,
) -> dict[str, object]:
    workspace = workspace.resolve()
    verifier_intake_path = verifier_intake_path.resolve()
    math_contract_path = math_contract_path.resolve()
    intake = _load_json(verifier_intake_path)
    contract = _load_json(math_contract_path)
    if intake["bindings"]["math_contract_sha256"] != pdc_verifier_intake.sha256_file(math_contract_path):
        raise PdcVerifierReproductionError("verifier intake is not bound to the supplied math contract")
    if contract["contract_version"] != "PDC-MATH-0.1":
        raise PdcVerifierReproductionError("unsupported PDC math contract version")
    if not execute_sources:
        raise PdcVerifierReproductionError("this receipt requires fresh published-source execution")

    executions, preserved = execute_published_sources(workspace=workspace, intake=intake)
    output_by_id = {
        output["id"]: output
        for execution in executions
        for output in execution["required_outputs"]
    }
    planar_source = _source_by_id(intake, "VER-SRC-PLANAR-V1_1")
    nonplanar_source = _source_by_id(intake, "VER-SRC-NONPLANAR-RESULTS-V1_3_3")
    planar_archive = workspace / planar_source["stored_path"]
    nonplanar_archive = workspace / nonplanar_source["stored_path"]

    published = {
        family: _csv_rows_from_archive(planar_archive, member)
        for family, member in PLANAR_DATA_MEMBERS.items()
    }
    published_nonplanar = _csv_rows_from_archive(nonplanar_archive, NONPLANAR_DATA_MEMBERS["nonplanar_rows"])
    published["solid_cuboid"] = [row for row in published_nonplanar if row["family"] == "solid_cuboid"]
    published["surface_shell"] = [row for row in published_nonplanar if row["family"] == "surface_shell"]

    reproduced = {
        family: _csv_rows_from_path(preserved[family])
        for family in ("rectangle", "line_hole", "arbitrary_mask", "inversion")
    }
    reproduced_nonplanar = _csv_rows_from_path(preserved["nonplanar_rows"])
    reproduced["solid_cuboid"] = [row for row in reproduced_nonplanar if row["family"] == "solid_cuboid"]
    reproduced["surface_shell"] = [row for row in reproduced_nonplanar if row["family"] == "surface_shell"]

    rectangle, rectangle_formula = _rectangle_rows()
    line, line_formula = _line_rows()
    arbitrary, arbitrary_matrix = _arbitrary_mask_rows()
    inversion, inversion_formula = _inversion_rows()
    cuboid, cuboid_formula = _nonplanar_rows("solid_cuboid")
    shell, shell_formula = _nonplanar_rows("surface_shell")
    independent = {
        "rectangle": rectangle,
        "line_hole": line,
        "arbitrary_mask": arbitrary,
        "inversion": inversion,
        "solid_cuboid": cuboid,
        "surface_shell": shell,
    }
    formula_mismatches = {
        "rectangle": rectangle_formula,
        "line_hole": line_formula,
        "arbitrary_mask": 0,
        "inversion": inversion_formula,
        "solid_cuboid": cuboid_formula,
        "surface_shell": shell_formula,
    }
    secondary_mismatches = {
        "rectangle": 0,
        "line_hole": 0,
        "arbitrary_mask": arbitrary_matrix,
        "inversion": 0,
        "solid_cuboid": 0,
        "surface_shell": 0,
    }
    keys = {
        family: tuple(rows[0].keys()) for family, rows in independent.items()
    }
    pass_fields = {
        "rectangle": ("raw_match", "channel_match", "prime_match", "overcomp_match"),
        "line_hole": ("raw_match", "prime_match"),
        "arbitrary_mask": ("match",),
        "inversion": ("raw_match", "prime_match"),
        "solid_cuboid": ("formula_match",),
        "surface_shell": ("formula_match",),
    }
    source_output_for_family = {
        "rectangle": output_by_id["rectangle"],
        "line_hole": output_by_id["line_hole"],
        "arbitrary_mask": output_by_id["arbitrary_mask"],
        "inversion": output_by_id["inversion"],
        "solid_cuboid": output_by_id["nonplanar_rows"],
        "surface_shell": output_by_id["nonplanar_rows"],
    }

    family_results = []
    mismatch_rows: list[dict[str, object]] = []
    for family in DECLARED_COUNTS:
        record, samples = _family_record(
            family=family,
            published=published[family],
            reproduced=reproduced[family],
            independent=independent[family],
            keys=keys[family],
            source_output=source_output_for_family[family],
            formula_mismatches=formula_mismatches[family],
            secondary_mismatches=secondary_mismatches[family],
            published_pass_fields=pass_fields[family],
        )
        family_results.append(record)
        mismatch_rows.extend(samples)

    total_cases = sum(item["independent_case_count"] for item in family_results)
    failed_families = sum(item["status"] != "pass" for item in family_results)
    source_outputs = [output for execution in executions for output in execution["required_outputs"]]
    failed_checks = (
        failed_families
        + sum(execution["status"] == "fail" for execution in executions)
        + sum(not output["canonical_lf_match"] for output in source_outputs)
    )
    status = (
        "pass_with_documented_serialization_drift"
        if failed_checks == 0
        and total_cases == sum(DECLARED_COUNTS.values())
        and any(not output["byte_match"] for output in source_outputs)
        else "pass"
        if failed_checks == 0 and total_cases == sum(DECLARED_COUNTS.values())
        else "fail"
    )
    if status == "fail":
        raise PdcVerifierReproductionError(
            f"exact verifier reproduction failed: families={failed_families}, checks={failed_checks}, samples={mismatch_rows[:3]}"
        )

    environment = {
        "python_version": platform.python_version(),
        "python_implementation": platform.python_implementation(),
        "platform": platform.platform(),
        "executable": sys.executable,
        "numpy_version": np.__version__,
        "pandas_version": _package_version("pandas"),
        "matplotlib_version": _package_version("matplotlib"),
        "pythonhashseed": "0",
        "matplotlib_backend": "Agg",
    }
    return {
        "schema_version": "0.1",
        "artifact_kind": "pdc_verifier_reproduction",
        "created_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "status": status,
        "bindings": {
            "verifier_intake_path": verifier_intake_path.relative_to(workspace).as_posix(),
            "verifier_intake_sha256": pdc_verifier_intake.sha256_file(verifier_intake_path),
            "math_contract_path": math_contract_path.relative_to(workspace).as_posix(),
            "math_contract_sha256": pdc_verifier_intake.sha256_file(math_contract_path),
            "math_contract_version": contract["contract_version"],
            "selected_source_set_sha256": intake["digests"]["selected_source_set_sha256"],
        },
        "environment": environment,
        "source_executions": executions,
        "family_results": family_results,
        "mismatch_rows": mismatch_rows,
        "digests": {
            "family_digest_set_sha256": pdc_verifier_intake.sha256_json(
                [{"id": item["id"], "sha256": item["cases_digest_sha256"]} for item in family_results]
            )
        },
        "summary": {
            "family_count": len(family_results),
            "declared_case_count": sum(DECLARED_COUNTS.values()),
            "published_case_count": sum(item["published_case_count"] for item in family_results),
            "source_execution_case_count": sum(item["source_execution_case_count"] for item in family_results),
            "independent_case_count": total_cases,
            "source_execution_count": len(executions),
            "source_output_file_count": len(source_outputs),
            "exact_byte_match_file_count": sum(output["byte_match"] for output in source_outputs),
            "canonical_lf_match_file_count": sum(output["canonical_lf_match"] for output in source_outputs),
            "serialization_drift_file_count": sum(not output["byte_match"] for output in source_outputs),
            "failed_family_count": failed_families,
            "mismatch_count": sum(
                item["source_execution_semantic_mismatch_count"]
                + item["published_failed_case_count"]
                + item["independent_source_mismatch_count"]
                + item["formula_mismatch_count"]
                + item["secondary_oracle_mismatch_count"]
                for item in family_results
            ),
            "failed_check_count": failed_checks,
        },
        "claim_boundary": [
            "The six reproduced families are finite exact audits over their declared domains; no all-size claim follows from case count alone.",
            "Rectangle inversion is area plus response under a rectangle prior and is not arbitrary-mask reconstruction.",
            "PMphi.default.remove_B7 remains a separately tagged selector and is not the raw B5-7/S5-9 rule.",
            "Solid cuboid and closed surface-shell results are first-response laws for axis-aligned nonwrapping boxes with side lengths at least four.",
            "Empirical relaxation, port, slit, wall, signed, probability, bridge, and physical interpretations are outside this receipt.",
            "Published LF CSV bytes rerun as CRLF on Windows; raw and canonical-LF hashes are both retained and only canonical rows are claimed equal.",
        ],
    }
