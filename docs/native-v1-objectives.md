# PooleOS Native V1 Candidate Objectives

Status: Cycle 85 pre-production candidate

Selected move: `N0-OBJECTIVES-001`

Authority boundary: `specs/native-v1-objectives.json` is a measurable proposal for N0.6 owner review. It does not amend or ratify ADR-0005, record Rooke Poole's acceptance, provide measured product evidence, or permit production promotion.

## Profile

The candidate edition is `PooleOS Workstation` for native x86-64 UEFI operation. It covers exactly one pending Tier-0 QEMU/q35/OVMF profile and the declared exact Tier-1 machine. Normal, safe, previous-known-good, diagnostic, live, installer, and recovery modes belong to one signed release profile.

Required use cases are an authenticated local graphical workstation, terminal and native development, explicitly authorized network use, signed update/rollback/recovery, PooleGlyph/PGB2/PGVM2 execution, canonical PDC reference execution, and an accessible software-rendered fallback.

The candidate does not claim generic-PC, Windows binary/driver, Linux ABI/module/driver, multi-tenant server, safety-critical, medical-device, or invasive-physical-attack support.

## Target Families

| Family | Definitions | Current evidence |
|---|---:|---|
| Reliability | 7 | 0 measured |
| Accessibility | 8 | 0 measured |
| Compatibility | 6 | 0 measured |
| Privacy | 7 | 0 measured |
| Performance and power | 10 | 0 measured |
| Total | 38 | 0 measured |

The values are deliberately test-shaped. Each target names an operator, threshold, unit, minimum sample count, minimum duration, percentile where applicable, exact profiles, evidence phases, and retained-evidence requirement.

Reliability candidates include 10,000 clean Tier-0 boots, 1,000 exact Tier-1 boot/restart/shutdown cycles, a 168-hour mixed-workload soak, 1,000 interrupted update/rollback scenarios, 10,000 randomized PooleFS power cuts, 10,000 driver crash/reset cycles, and a 15-minute Tier-1 recovery-time objective. Zero-tolerance metrics still remain finite tests and do not prove universal failure-free behavior.

Accessibility uses WCAG 2.2 A/AA as an applicability baseline, not as an automatic native-software conformance claim. It also requires keyboard completion, semantic name/role/state/value exposure, 200 percent text scaling, contrast, reduced motion, flash limits, and keyboard/high-contrast/static/serial recovery alternatives. EN 301 549 V3.2.1 is a candidate ICT crosswalk pending applicability and supersession review.

Compatibility is exact and fail-closed. Unknown major versions are rejected, advertised POSIX behavior is an enumerated source subset, and v1 has no Linux ABI, Linux kernel-module/driver, Windows binary, or Windows-driver compatibility claim.

Privacy candidates require telemetry disabled by default, zero undeclared pre-consent outbound connections, zero unscoped stable identifiers, seeded-secret diagnostics testing, visible and reversible consent, bounded local retention, and no automatic crash upload.

Performance candidates cover first PooleBoot marker, PooleKernel-to-PooleInit readiness, login readiness, PooleGlass frame distributions, physical input response, idle memory/CPU, instrumented power regression, and 64-byte local IPC. They are budgets for future qualification, not benchmark results.

## Measurement Rules

- Use monotonic clocks for latency and duration.
- Retain raw samples, failures, environment, exact hardware/firmware, workload, and test configuration.
- Use nearest-rank percentiles over retained samples.
- Declare and exclude warm-up before measurement.
- Count failed samples as failures.
- Do not remove outliers unless the rule is predeclared and both raw and filtered results are reported.
- Bind power evidence to external instrumentation, ambient conditions, firmware, device/display state, and workload.
- Require independent reproduction before release promotion.

## Owner Gate

The deterministic ledger at `runs/native_v1_objectives_readiness.json` records:

- 38 complete candidate definitions;
- zero measured targets;
- zero schema or semantic violations;
- ten of ten negative controls passing;
- profile acceptance false;
- target-value acceptance false;
- cryptographic signature false;
- `n0_6_exit_gate_satisfied=false`;
- `production_promotion_allowed=false`.

Rooke Poole must accept, amend, or reject the profile and values before they can enter the owner-signed architecture manifest. Baseline evidence may justify an amendment, but no threshold may be silently weakened to turn a failing implementation into a passing claim.

## Reproduction

```powershell
python .\tools\generate_native_v1_objectives_readiness.py
python .\tools\verify_native_v1_objectives.py
python -m unittest tests.test_native_v1_objectives -v
```

The readiness ledger is deterministic from public inputs. It contains no owner key, signature, private evidence, or measured production result.
