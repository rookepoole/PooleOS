# Cycle 223: Atomics Admission and Instruction Audit

Status date: 2026-10-04. Pre-production. Goal ACTIVE.

## Scope

N12.1/N36, `N12-CONCURRENCY-ATOMICS-001`, advances existing requirements
`ADD-N12-CONCURRENCY-ATOMICS-001` and `ADD-N36-RECEIPT-COVERAGE-001`.
The preceding merge-status turn did not advance implementation; this cycle
resumes the already measured atomics defects. N0 custody and N5 authentication
remain open. No native atomics defect was established, so native source and
kernel bytes are unchanged. No requirement, phase or implementation flag closes.

## Findings and Repair

The diagnostic qualifier passed two boots and 246 kernel host tests, but its
receipt validator accepted 168 of 277 corruptions and raised four exceptions.
The aggregate gate accepted 91 and raised nineteen exceptions. A fake assembly
body containing only a return plus required words in comments also passed.
Diagnostic receipt SHA256:
`61AC116FD675948E45F9BCE626F338B5B03C3496A146608A114FE15511FC568F`.
These results remain failures of admission, not production evidence.

Recorded admission now reconstructs both marker streams, their summaries and
digests, PBP1 agreement, observed counters, host litmus output, exact typed
control accounting, canonical calendar dates, source audits, linked/tool/image
bindings and development/default boot metadata. Malformed records fail closed.
The aggregate gate independently pins the current kernel's identity and sizes.

Instruction auditing parses actual lines, requires the narrow pinned compiler
lowering's opcode bytes and operands, checks contiguous addresses, adjacent LOCK
and memory-RMW instructions, and verifies the CAS retry displacement and target.
The receipt retains seven instruction bodies; the disassembly digest covers
canonical symbol/body JSON, explicitly excluding the private local tool header.
Neither rehashing a corrupted body nor comment text can supply an instruction.
The host probe and objdump subprocesses now have explicit bounded timeouts.

## Verification

- Final receipt: `runs/native-kernel-atomics-readiness.json`, SHA256
  `1E684D59C800F1C08BD05C1BEAB940654FD1CC8550779217FFE5AA4162DAB3CC`.
- Two final qemu64 one-BSP boots, 41 markers each, matching marker/frame/PBP1
  evidence; 29 hostile groups covering 78 executed rejection cases.
- 246/246 kernel host tests; eight host-probe records; seven linked symbols.
  Publication: 4096 rounds. Contention: 20480 operations. Sequential consistency:
  2048 rounds, zero forbidden outcomes. Host concurrency is not live AP stress.
- Qualification: 93.828 seconds. Stage log SHA256
  `0BF036FC79C939C9EB6CDB0C580AB2D279EE05C4D7B64A29D07B34995FCC76BD`.
  The stage-only log text is identical across successful attempts; it alone
  does not identify a run. Receipts and local command/source snapshots do.
- Initial focused regression: 22/22 tests, zero skips, 26.831 seconds (runner 27.703).
  Log SHA256 `8097A531343C60DA999DC5708F91F2C42F44BA26BDB763E41102922C2A52544C`.
- Final bound-source combined regression: 146/146 tests, zero skips, 160.360
  seconds (runner 161.297). Includes all 22 focused tests, entry, interrupts,
  preemption, capture and 70 metadata tests. Counts overlap, not independent
  totals. Log SHA256
  `93361F4A4C29D8A740FDAFD174986E04AA4652C20DCB97EC16884074F2C1F2AD`.
- Both runtime and actual aggregate gate reject 356 corrupted records without
  exceptions. Eight image/count mutations reject with the component disabled.
- Seven rehashed instruction receipts, seven comment-only symbol bodies and
  seven byte/operand/branch/instruction mutations reject. Empty control lists
  and disabled source/disassembly auditors cannot produce passing controls.
- The actual native atomics module's seven tests pass at optimization 0 and 3.
  Eight distinct disabled guard variants fail at both levels: sixteen mutant
  executions, not sixteen distinct bugs or guest fault injections.

The first expanded corruption corpus mistakenly replaced a null default feature
with the same null value. The genuine receipt correctly passed; the harness
assertion failed and no current receipt was replaced. The mutation was repaired,
then qualification was rerun against the new bound test source without rebinding
old evidence. Review also added direct loader/transfer source bindings followed
by fresh qualification. Eight successful boots occurred: two diagnostic, four
superseded and two final. Only the final two count toward this checkpoint.
The failed admission, original audit and all superseded outputs remain local.
The initial metadata suite passed 69/70; its obsolete two-pending-profiles
assertion is corrected to one. The failed log is retained, not relabeled.

## Preservation and Next Move

Selected native readiness is 26/27; locks remain stale. All 26 parent current
records are archived without rewriting earlier history. The inventory is 1157
Python tests with 379 architecture-bound sources; discovery is not execution.
Conservation passes against parent `4714a19`, checking every bound source hash,
prior current/historical record, phase/flag status and preserved artifact.
The 40 phases, 301 subphases, 94 flags (39 open), 57 ADD requirements, locked
10512-line/8996-requirement checklist and coverage ledger remain unchanged.
PooleGlyph Phase 65 remains latest, its dirty generated report is preserved,
and no syntax/Core IR/PGB2/PGVM2/ABI/IP migration is adopted. Phase 66 is pending.

Kernel216 remains canonical SHA256
`FD6C2A0C709957B9EDFFC0647D534E060ED68215C075F07D70AB2AEBCA6C81D1`:
538264 canonical bytes, 7158864 linked bytes, 610304 loaded-image bytes,
149 pages, 1326 relocations, entry offset 0xA000. The demo ISO is unchanged.

Exact next move: `N12-CONCURRENCY-LOCKS-001`, audit recorded lock admission and
actual controls before fresh qualification. Then complete the N36 shared-helper
transitive-binding review and exact-candidate canonical, Doctor, release,
publication and GitHub/review checks before main merge. Branch cloud backup is
separate from main acceptance. The shared all-profile provenance suite still
includes stale locks and is not represented as passing in this cycle.

No signing, secrets, key use, firmware mutation, physical-media action, release
publication or production promotion occurred. Recorded consistency does not
prove authenticity, independent builders, physical hardware, general SMP,
reclamation, complete architectural task state or the signed production ISO.
