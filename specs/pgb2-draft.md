# PGB2 / PGVM2 Draft

Status: draft v0.1

Date: 2026-06-29

## Purpose

PGB2 is the proposed PooleOS bytecode container for OS-grade execution while preserving PGB1 compatibility.

PGB1 remains the canonical public compatibility contract for current PooleGlyph programs. PGB2 adds typed channels, rule metadata, provenance, and signed-state sections needed by PooleOS.

## Compatibility Rule

A PGB2 runtime must be able to run PGB1 programs or delegate them to a PGB1-compatible execution mode. A PGB1 program must not change its result merely because it is run inside PooleOS.

## Container Sketch

```text
PGB2_HEADER
SECTION_TABLE
CODE
SYMBOLS
RULES
CHANNELS
REGIONS
TRAP_ENCODING
TRAP_EXECUTION
TRACE_SCHEMA
CLAIM_LANE
SIGNATURE
```

The first PooleOS implementation uses a JSON PGB2 draft bundle to avoid freezing a binary wire format before the section semantics are proven. The JSON bundle is specified in `pgb2-bundle.schema.json` and uses:

- `CODE` section with PGB1 raw hex compatibility payload;
- `TRACE` section with `channel-trace.schema.json` artifact body;
- `CLAIM_LANE` section with `claim-lanes.schema.json` body;
- optional `TRAP_ENCODING` and `TRAP_EXECUTION` sections with draft capability-trap byte evidence;
- per-section SHA-256 hashes over canonical JSON section bodies.

## Required Sections

### CODE

Instruction stream. PGB1-compatible instruction streams may be embedded as a compatibility mode.

### RULES

Declares the active birth/survival rule windows.

Minimum fields:

```json
{
  "birth": [5, 7],
  "survival": [5, 9],
  "neighborhood": "3D_MOORE_N26",
  "boundary": "sparse_unbounded"
}
```

### CHANNELS

Declares typed channel readout.

Canonical base channels:

```text
B5 B6 B7 S5 S6 S7 S8 S9 O10+ psi
```

### CLAIM_LANE

Embeds or references a `claim-lanes.schema.json` record.

## Draft Instruction Families

### Channel Readout

```text
MEASURE_CHANNELS
MATCH_CHANNEL B5
MATCH_CHANNEL_RANGE B5 B7
FILTER_CHANNEL B6
REPORT_CHANNEL_SUMMARY
```

### Rule Windows

```text
SET_RULE B 5 7 S 5 9
ASSERT_RULE B 5 7 S 5 9
SET_SIGNED_RULE B 5 7 S 3 11 COLLAPSE 3
```

### Defect Calculus

```text
MEASURE_DEFECT_FOOTPRINT
FILTER_Q_RANGE 1 3
FILTER_R_RANGE 2 4
REPORT_DEFECT_SUMMARY
```

### Signed State

```text
MATCH_SIGN plus
MATCH_SIGN minus
WRITE_SIGN plus
WRITE_SIGN minus
PROJECT_SIGN plus
PROJECT_SIGN minus
PROJECT_ABS
MEASURE_MEMBRANE
```

### Regions And Capabilities

```text
DEFINE_REGION name bounds
ENTER_REGION name
ASSERT_REGION_CAP read
ASSERT_REGION_CAP write
ASSERT_REGION_CAP trace
SNAPSHOT_REGION name
```

Draft trap encoding evidence currently uses `PGB2_TRAP_DRAFT_V0`:

```text
E0 ASSERT_REGION_CAP region source target capability expected_trap trap_code
E1 SNAPSHOT_REGION region source target capability expected_trap trap_code
E2 ASSERT_MATRIX_PERMISSION region source target capability expected_trap trap_code
```

Each text operand is UTF-8 with a 16-bit little-endian length prefix. `expected_trap` is a one-byte boolean. This encoding is deterministic proof evidence only and is not a frozen binary ABI.

Draft trap execution evidence uses `PGB2_TRAP_EXEC_DRAFT_V0` to decode the concatenated byte program, verify instruction offsets, and compare the simulated trap outcome stream against the encoding manifest. It is not booted kernel execution.

## Kernel Fix Requirements

Before PGB2 can be treated as stable:

1. Each new channel instruction must have a collapse-equivalence test.
2. Each signed-state instruction must have deterministic replay tests.
3. Each provenance section must have schema validation.
4. Each region/capability instruction must define trap behavior.
5. Each benchmark-facing instruction must declare its claim lane.
