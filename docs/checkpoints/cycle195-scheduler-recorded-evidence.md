# Cycle 195: Scheduler Recorded Evidence

Status date: 2026-09-27
Status: bounded native qualification; pre-production, not merge-qualified
Move: `N12-SCHED-001`, N12.1/N12.2/N12.5/N12.6/N12.7 supporting N36
Requirement: `ADD-N36-RECEIPT-COVERAGE-001`
Flags retained: `FLAG-N12-SCHED-FOUNDATION-001`, `FLAG-N12-SCHED-PREEMPT-001`, `FLAG-N36-RECEIPT-COVERAGE-001`

## Implemented Scope

The runtime independently reparses raw paired scheduler guest markers and four
host probe lines; validates exact integer exit codes, ordered runs, dual-channel
evidence, transfer bindings, frame hashes and execution profile; reconstructs
typed observations and summaries; and checks exact per-control rejection counts.
The actual release gate now fails closed before using malformed fields. The
qualifier validates its result before creating or replacing an output file.

These are consistency and bounded execution checks, not authentication, proof
of receipt freshness, or exclusion of every coherent forgery. The native kernel
and scheduler implementation did not change during this receipt-repair cycle.

## Execution Evidence

Two final guest boots, 246 native kernel host tests, linked audits and 115 real
rejection cases in 28 control groups pass. The fresh public receipt passes its
runtime validator and actual release gate. No old receipt was rebound to new
source. Final receipt SHA-256:
`0CA89C0F579FB5BA086ED61FF7D56B0F68E6C82A974B4698CFEA84F621B83363`.
Qualifier log SHA-256:
`8F867ACC242340662A5873DD9035F537409D16A81AF05268BEABE7274F48A33F`.

All 14 focused scheduler tests pass with zero skips in 16.423 seconds, including
221 corrupted records through runtime and actual gate, coherent marker/host
corruptions, detection of three disabled validators, and two output-preservation
cases. Log SHA-256:
`E58C5B0675259CBFDA13624156F7C6C24DDC46152986DEDF36E7AE0372F4C5DE`.
An additional cloud-backup run passes 23 scheduler/publication tests, zero skips,
in 105.171 seconds; it is not an additional set of 14 distinct scheduler tests.
Log SHA-256:
`9AC6DE2CD459085794B28E5DF9B85614C456BEC207ED44B40CC7328FF151BD1F`.

Canonical kernel remains 530,072 bytes, 1,327 relocations, build ID
`PKBUILD1-CYCLE192-N8-MBX-ORCL-V01-0000000001`, SHA-256
`B9AF7DFB13472C0A0D3CBE70036EFAD7C3B792F13FC9944ACEC935B362F0FBA8`.
Retained memory/AP/IPI/CPU/boot receipts are not counted as fresh Cycle 195 boots.

## Counterevidence And History

The genuine initial receipt supported 219 corruption cases. Before repair,
runtime accepted 172 and the actual gate accepted 100; they raised four and
nine exceptions respectively. After repair the same 219 all reject through
both paths, with no exceptions. Before/after log SHA-256 values:

- `04155A4918C88EC0251F4012000D8653DD16325996CE57451E74DCA25798F7A4`.
- `2BA5A86349B0ADEB8E02B971473CDE3A036B6C34B18EA86CF32738B3FDBC9762`.

Two initial guest boots are superseded. An early four-test payload run had two
passes, one failure and one error because it consumed an old public receipt
with stale kernel identity. Fresh genuine evidence and explicit baseline checks
fixed the test setup without relaxing admission. Failed log SHA-256:
`75F703268BC6B22151A302382B24B24DD65EEFE58B0AF2D76F2981AD8F8AD4FB`.
The [intermediate cloud backup](cycle195-scheduler-cloud-backup.md) remains an
immutable record of incomplete reconciliation at commit `be02799`.

Initial metadata regression passed 42/43. One old entry-provenance assertion
still expected scheduler evidence to be stale. It now checks scheduler as
current and the unreplayed preemption receipt as historical, preserving both
positive and negative assertions. Failed log SHA-256:
`F518887F1351092BC2AADC32A1388191921DF9122AC03513BBB58CCD53336A20`.

## Reconciliation And Exit Gate

Roadmap 195 archives five replaced Cycle 194 records without changing prior
history. Ownership remains qualified at Cycle 194; CPU at 193 and boot/core at
192 are retained unchanged. Current dependency qualification adds only scheduler
to six retained memory/IRQ/AP/IPI profiles, leaving seven pending. The selected
projection is 20/27, not a full canonical score. Architecture binds 310 source
files, including scheduler validation, qualifier, tests, documentation and both
Cycle 195 checkpoints and the audited preemption qualifier. The 1,050 Python
tests are discovered inventory only.

Corrected metadata regression passes 43/43 with zero skips. Its log SHA-256 is
`FA5B3191D619D6AF939D0C57572B85BB0E64A40294FE2FA6BC99CB6506CF0C0B`.
Combined scoped regression passes 322 tests with zero skips in 303.618 seconds,
including exact kernel-entry reproduction. Source and owner data were unchanged
during execution. Log SHA-256:
`C8B15D4B8BF19675781D0C5C2F7B22DF7111E01F41065D1F2CED90292831C40A`.
The supplemental preemption audit and final metadata edits followed that run;
final metadata replay and conservation must pass before commit.
The full exact-candidate canonical/Doctor suite has not passed this candidate.
No phase, flag, checklist item, normative charter term or production gate closes.

## Additional Preemption Finding

Source inspection of `tools/qualify_native_kernel_scheduler_preempt.py` found
nine controls at `ids[15:24]` emitted as constant pass/rejected/case-count-one
records. An AST check confirms the loop calls only `controls.append`, without
per-control rejection execution. The preceding positive source/linked audit
does not establish that these nine negative controls executed. This is a
bounded evidence-coverage finding, not proof of a native preemption defect or
absence of all related Rust tests. Source SHA-256:
`9461C3A0DE65CDEA1C9F1E31FAF7518225293E5B1DAFE2238C85D33DB6783473`.

The nine IDs cover interrupt-frame contract, context ownership, event capacity,
deadline, duplicate events, quantum boundary, transactional rollback, linked
switch scope and retained-stack partition. Roadmap 195 records them under
`current_preemption_control_execution_audit` and the existing coverage/preemption
flags. They do not overlap the previous 65 IDs. The prior four-loop audit remains
unchanged; together the known lower bound is 74 across five qualifiers, still
not an exhaustive audit of all profiles. No preemption source was changed and
its stale receipt was not admitted.

## Next Dependencies

After closeout, run `N12-SCHED-PREEMPT-001`, then deferred work, SMP scheduling,
AP workers, SMP preemption, atomics and locks. Inspect recorded-evidence and
control-execution paths before admitting fresh receipts. At least 74 known
constant-only control groups in five scheduler qualifiers still require
real rejection execution; the broader receipt-coverage flag remains open.

Then pass full exact-candidate canonical/Doctor/publication/configured-check/
review requirements before PR #78 becomes ready for main merge. These are
engineering tasks, not an owner approval wait. General task/CPU retirement,
independent builders, hardware, native services and production remain unproved.
The locked checklist, historical full gate, demo ISO and PooleGlyph Phase 65
owner data are preserved. No new ISO, signing, hardware, firmware, physical-
media, tag, release or production-promotion action occurs.
