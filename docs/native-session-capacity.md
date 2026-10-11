# Native Session Capacity

Cycle266, 2026-10-11. Invariants frozen before implementation; final six-process,
four-process and default regression profiles pass after the explicit CP4 repair.
See [checkpoint](checkpoints/cycle266-native-session-capacity.md). No ISO claim.
Previous goal turn: progress, Cycle265 tracked console revocation committed8ee3a99.

## Contract PCAP8

- CP1: Eight IPC task tables and endpoint objects, matching the existing scheduler.
  Per-task capability/reply/request limits4, message depth4 and size64 unchanged.
  No implicit authority, shared user roots, or unbounded allocation.
- CP2: Atomic admission/rollback covers every slot, including4..7. Exhaustion,
  stale generations, duplicate identities/roots and partial plans fail without
  publishing scheduler state or reviving consumed authority.
- CP3: Six distinct private native roots: original init/counter, console pair and
  an additional isolated init/counter pair. The extra pair is a capacity workload,
  not useful applications. Returned actual grants authenticate all startup locators.
- CP4:78 task-image pages plus at most12 separately counted ACPI pages. Keep205
  image pages within208 reserved pages and36-page guarded stack, or separately
  review a layout change from measured failure/footprint evidence. No silent
  enlargement or deletion of diagnostics to make the implementation fit.
  Reviewed revision after the default regression linked BSS through0xCE818:
  reserve207 image pages (0xCF000), still within the unchanged208-page bootstrap
  capacity. The original205-page six/four-process results are historical after
  this layout repair; all affected native profiles require fresh execution.
- CP5: Two fresh six-process guests echo distinct real host input, console programs
  exit0/reap26 pages, both independent pairs progress through512 dispatches.
- CP6: Separate malformed-extra-worker-startup guest: task5 exit120, partner4
  exit111, both by64 dispatches and within8 of each other. Original pair and console
  still process actual input; console close plus worker cleanup return52 pages.
  This is fixed bootstrap dependency cleanup, not user-space restart/supervision.
- CP7: Preserve four-process PRPC1, default containment and ordinary unsigned
  denial. Freeze old receipts and distinguish stale source history. No shell,
  useful apps, ISO, lifecycle authority, production or full canonical claim.

## Alternatives And Risks

Select bounded capacity aligned with the scheduler and measured six-root execution.
Reject identity time-sharing (ownership), calling test pairs useful apps (wrong
acceptance), raising only scheduler limits (IPC still full), unbounded allocation
(unnecessary ownership surface), and silent image/stack enlargement.
Null/other: stack growth, stale quota-test assumptions or PMM record capacity may
invalidate naive expansion. Test these before promotion.

Next: narrow kernel lifecycle mechanisms and real user-space start/stop/supervision,
shell/read-only files/two useful apps, then fresh optical ISO acceptance. Full
robust microkernel, PDC/PooleGlyph and accessible PooleGlass remain required.
