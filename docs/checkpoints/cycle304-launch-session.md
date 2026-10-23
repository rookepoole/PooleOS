# Cycle304: Launch Session Integration

Started: 2026-10-20. Status: session host/build checkpoint; native admission pending.
Parent: `f5dcf6f0011f202378cbc6cb6a94a60f94c136e1`, Cycle303.
The interrupted continuation inspected code but produced no implementation:
classify it as no progress, revalidate, and implement the next unblocked step.
The complete native production goal remains active.

## Entry And Scope

The branch remains `agent/userspace-integration-iso`. Existing unstaged changes
in `tools/native_build_space.py` and its tests raise build admission to a 12 GiB
floor and add a manual preflight. Preserve those changes; do not revert or lower
the limit. C has about 47 GiB free at entry. Ordinary usage is allowed; the weekly
window is 6% used, with no separately reported five-hour window.
The master checklist, latest Phase65 archive and conformance hashes are unchanged.
No PooleGlyph/PDC promotion follows from this work. Preserve all 40 phases and
301 subphases, accessible PooleGlass and the full native microkernel requirements.

Cycle303 implemented the typed broker and authenticated transport but not the
Read/result/ack session. The current shell owns terminal draft, command output,
file jobs and both application factories. Reuse that owner and the ordinary
console policy. Keep graphical native admission, actual connected code/stack
measurements and launch-failure cleanup as explicit gates, not inferred results.

## Selection And Invariants

Alternatives: command-text injection breaks draft ownership; giving factories to
the window service expands authority; a new broker service requires additional
startup/lease/lifecycle work; a new parallel endpoint requires bootstrap and
demultiplexing; a bounded explicit wrapper can preserve the existing session and
serialize typed work at an outstanding Read. Select the wrapper. Keep the
separate-endpoint alternative if actual compiled capacity or coupling disproves
this choice. Device delay and admission without a surface remain alternatives
to successful visible launching.

- LS1: a control request consumes only an outstanding Read at sequence S.
  No Write, Close, active file job or partially acknowledged output is replaced.
- LS2: the process owner, peer authentication, one-use RPC tokens, original
  guards, quotas and failure ownership remain. No synthesized terminal text.
- LS3: reserve S+1 for Written and S+2 for the next Read before any launch effect.
  No wrapping, stale result, wrong app/action/generation or mismatched ack.
- LS4: pending requests/results retain exact values through backpressure.
  At most one IPC operation or process syscall per wrapper poll. No duplicate
  admission, automatic replay after transport failure, or slot reuse before ack.
- LS5: preserve all shell draft/rejection/CRLF state, output cursor, command route,
  and active file work. Control completion must not print or execute a command.
- LS6: both session ends fail closed after malformed transport or sequence state.
  Server results become available only after the bound acknowledgment is sent.
- LS7: host session tests are not connected native execution or a usable launch
  UI. Measure compiled integration before admission and keep failed attempts.

## Execution

1. Implement opt-in shell and console session wrappers over the existing policies.
2. Test real shell draft/command preservation, both protocol ends, delayed and
   duplicate traffic, generation/status binding, exhaustion and failure poisoning.
3. Measure the compiled connection and determine any explicit profile/layout
   changes needed without silently increasing budgets.
4. Reconcile native evidence, preview status, roadmap, flags and cloud checkpoint.
   Actual graphical controls, keyboard access, compositor recovery, COM2-free
   boot, persistence and every remaining production gate stay in scope.

## Results And Retained Failures

Implemented both session wrappers and the owned Connection transport adapter.
Added22 Rust tests, including the two real session ends over authenticated PRPC1
with one-use fake-kernel replies, foreign-peer poisoning, sequence exhaustion,
backpressure, draft rejection/CRLF preservation, active Files and waiting Jobs.
Final268 tests pass in each debug/release profile.

The first end-to-end assertion incorrectly expected Running from a successful
launch admission. The host run retained267 passes/one failure. Corrected the test
to Admitted and the terminal prompt spelling; no protocol behavior was weakened.
The following debug and both final qualification runs pass.

The real freestanding candidate first failed the unchanged four-page linker
assertion at0x4C08 (19464 bytes). Retain `outputs/cycle304-candidate1`, including
its map, log and source bindings. Added the separate feature-gated PooleLaunchShell,
exact launch-shell startup role and five-page PLCODE1 build profile. It is not
selected by any kernel or ISO. The extractor rejects this size under PUSERBIN1,
and both code-profile symbols cannot coexist.

`outputs/cycle304-launch-programs1/receipt.json`: two independent identical
candidate ELF/code builds;19464/20480 bytes,1016 free,266 local relative object
relocations audited, no writable segment/import/dynamic relocation.
`outputs/cycle304-programs1/receipt.json`: all29 ordinary pairs reproduce;
their ELF and extracted code are byte-identical to Cycle303. No kernel source
changed. These build checks are not new native guest execution.
Reconstructed scoped evidence: `runs/native-launch-session-readiness.json`.

The user-authored storage floor/CLI and two tests were present at entry and
remain byte-for-byte intact. Include these relevant tested dependencies in the
cloud checkpoint so its source bindings are reproducible. Local AGENTS.md,
output-storage notes and temporary directories are not part of this change.
No output cleanup, historical receipt rewrite or preview reselection occurs.

## Next Chronological Move

Implement explicit kernel mapping/embedded-layout admission and the matching
window-service role, then measured nested stack paths and real launch controls.
The ordinary embedded read-only margin of360 bytes cannot absorb4024 bytes of
shell growth. Keep kernel guards and capability ownership unchanged; a build-only
five-page extractor is not native admission. Graphical controls must distinguish
admission, liveness and published surfaces and support keyboard access.
Qualify real cross-process stale/repeated/failed controls, draft/file work and
focus/lifetime cases on both backends before selecting a new source-bound ISO.
All101 flags (46 open),40 phases and301 subphases remain; no production promotion.
The retained Cycle303 pointer is historical and its strict launcher can reject
current-source drift. Full canonical replay, main merge and connected native
session qualification have not occurred in this cycle.

## Metadata Verification

The first selected metadata replay ran453 tests:444 passed and nine failed.
Failures were stale current-source counts (102 to108 program bindings and1000
to1006 execution bindings) and a linker-source assertion that lacked the explicit
candidate branch. The corrected assertions retain historical receipt hashes,
four-page ordinary rejection, seven-page window capacity and mutually exclusive
candidate selection. `outputs/cycle304-metadata1.log` is retained.
Python discovery finds1601 tests with no import errors; inventory is not a
full-suite pass. The source-bound build evidence covers108 files; architecture
coverage includes879 files. Final replay and staged/publication audit follow.
The second replay retained452 passes/one failure: an older test pinned the current
next-move title to Cycle303. Update it to the explicit Cycle304 admission step;
no historical result or acceptance rule changes.
The final selected replay passes453/453 with unchanged execution sources and no
discovery errors (`outputs/cycle304-metadata3.json`). This is scoped regression,
not the full canonical suite. Final artifact reconstruction rechecks the actual
paired ELF/code bytes, live program bindings, retained failed link map/log,
owner-input hashes and unchanged historical receipts before cloud backup.
All nine publication-boundary tests also pass with unchanged execution sources
(`outputs/cycle304-publication-tests1.json`). The checkpoint remains draft-only;
these checks do not authorize production promotion or replace canonical replay.
