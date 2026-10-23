# Cycle314: Native Entered-Child Exhausted Recovery

2026-10-22. Kernel/native and selected integration verification complete.
Production incomplete. Parent
`a973f5f8ae1ee193da61c08b8c27ddafdd8b0170`. Previous turn: verified, committed
and pushed progress. Microkernel work remains first; no demo packaging selected.
The live PooleGlyph checkpoint is still Phase65 and its owner-modified conformance
report is preserved. All eight locked master-checklist coverage checks pass.
Ordinary usage is allowed; weekly consumption was 6% at entry, with no separate
five-hour percentage available.

## Scope And Invariants

N13/N14, `N13-CAPABILITY-IPC-001`, with existing launch-failure, user-stack and
user-space integration flags. Entry evidence is Cycle313's exact slice-accounting
repair and host-only entered-child exhausted recovery. Extend the existing
non-optical shell owner-fault profile; keep the ordinary profile intact.

- R1: actual parent UD2 follows a measured, already-entered child. No synthetic
  owner cancellation or prepared-child substitution satisfies this case.
- R2: retain exact pages and accounting through three failed deferred retries at
  64, 192 and 448 dispatches after deferral; one closed-job attempt follows at512.
- R3: success releases only after zero/readback cleanup and scheduler teardown;
  no dead-parent completion, premature slot reuse or authority extension.
- R4: persistent failure keeps the child blocked, retains ownership and runtime,
  and never rearms writes; independent init/counter/console continue progressing.
- R5: reconstruct exact source, paired kernel/program builds, boot media, raw
  input and serial/debug logs. COM2 output is interaction, not kernel evidence.
- R6: preserve ordinary deferred behavior, resource bounds, historical receipts,
  owner files and Cycle308 preview. No ISO, GUI replay, merge or promotion.

Alternatives considered: use prepared launch rejection again (does not cover the
gap), reset cleanup retries (violates bounded ownership), retain everything
forever (loses legitimate recovery), or exercise the existing one-shot mechanism
after a real fault. Select the latter with successful and persistent controls.
Marker-validator acceptance alone is not proof that a guest executed.

## Failure History

Preserve `outputs/cycle314-oracle1` through `oracle3`. The first rejection campaign
incorrectly expected deletion of an optional final progress sample to fail.
After correcting that test, adversarial ordering exposed missing owner/death and
drain interval checks in the new validator. Both are now bound to surrounding
dispatch samples. `oracle4` passes 12 tests; later feature-admission coverage
requires a fresh final run.

`native-recovery1` failed before compilation because the new feature tuples were
not in the kernel builder's explicit allowlist. Add only the four exact headless
success/persistent and denied-authority combinations; preserve all other rejection
behavior, linker limits and production defaults. `native-recovery2` passes.

`metadata1` ran all 512 selected checks and rejected three stale assertions of
the current execution inventory (1,016 instead of 1,018). Only those current-count
expectations changed; historical receipt bytes and historical binding counts
remain unchanged. The failed log is retained; `metadata2` passes all 512 checks.

## Verified Evidence

All 615 kernel tests pass in each debug/release recovery profile; 633 pass in the
ordinary feature profile. All 36 focused integration checks pass. Nine QEMU guests
pass: three successful exhausted recoveries, three persistently retained failures,
and three ordinary deferred regressions. Each profile includes an independent
denied-authority kernel; each successful qualification keeps the 180-second guest
bound. Rustfmt and whitespace checks pass.

Independent reconstruction verifies all 1,018 execution bindings, paired kernels,
five selected paired user programs, exact input/output, both raw kernel logs,
boot media, retained manifests/transcripts and hostile marker replays. The new
compact aggregate binds full raw evidence retained under `outputs`; it does not
delete or replace those artifacts. Receipt:
`runs/native-entered-recovery-readiness.json`, SHA256
`AB606AD836D1FB4B1D2CA818BE64739BFFDF347353B05ECE450869AC27592C48`.
PooleGlyph inputs and the Cycle308 preview pointer and both ISO copies match the
parent checkpoint. No new ISO, GUI replay or physical-hardware run occurred.

## Remaining Work

All 512 selected roadmap/integration checks pass, including the eight checklist
coverage tests. The 1,660 discovered Python tests are inventory, not a full run.
Architecture bindings total 921; program bindings remain 111. Counts overlap.
Before commit/push, require exact staged blobs, 98 unchanged historical receipts,
source/artifact reconstruction, schema/generator checks and publication scan.
Keep PR81 draft; no merge or promotion. All 40 phases, 301 subphases and 101 flags
(46 open) remain. Complete canonical qualification has not run.

Next: bounded multi-owner reclamation and fault isolation. Begin by checking
exclusive generation-bound job membership across owners, then fair cleanup when
one child remains retained. The standalone Job API and current native loop do not
yet establish that multi-owner contract. Capability/IPC lifetime, stale-generation
denial and bounded service restart/rebinding follow. General owner-death recovery,
partial allocator release, construction/committed-handoff recovery, all-path stack
and SMP isolation remain unproven. Demo work stays deferred; the full native OS,
PooleGlyph/PDC, PooleGlass and eventual signed ISO objective is unchanged.
