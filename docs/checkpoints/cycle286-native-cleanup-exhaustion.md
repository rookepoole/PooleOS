# Cycle286: Overlapping Native Cleanup Exhaustion

Date: 2026-10-13. Previous goal turn: progress, Cycle285 committed and pushed as
73c79dd. Owner priority remains the usable native user-space integration ISO,
then the complete robust microkernel. No new optical ISO exists yet.

## Implementation And Evidence

Add the development-app-cleanup-exhaustion profile. It uses the actual unchanged
PooleText and PooleNumbers programs. Both compute results before cancellation;
the stale-file control denies Numbers as expected. Initial cleanup is injected
to fail, followed by three dispatch-separated finish failures. The original
cleanup state machine and its 64/128/256-dispatch retry schedule are unchanged.
No production algorithm, user ABI/authority, capacity or signing policy changes.

The exclusive dispatcher emits read-only PCLEANUP3 exhausted-owner observations.
They bind task/generation, retained pages, cleanup attempt, physical-write count,
terminal syscall count, charged runtime, dispatch and parent job membership.
Scheduler wait kind, matching runtime, no pending/unknown charge, Reclaiming state,
and two retained job members are checked before emission. Existing native cleanup
checks deny reentry, early completion publication and ordinary free on every
failed attempt. After exhaustion no further retries are scheduled.

A separate verifier requires both deferred owners to overlap, exactly three
attempts each, no release/retirement/restart, frozen child counters, unchanged
physical-write counts, and continued init/files/console/shell progress. It allows
a one-dispatch collision delay only when another cleanup used the due dispatch.
All post-exhaustion RUN samples require one HOLD for each exhausted owner. At
least 512 further dispatches are required after the last exhaustion. The existing
live_mask denotes admitted ownership, not runnable tasks; 63 is not resumed apps.

The real-input scenario waits for both exact generation-1 exhaustion records.
Status/start/stop each report retiring; exit is denied while children remain
owned. A version-file read and fresh nonce echo then succeed. All 206 input bytes
and replies are checked exactly; COM2 output is not used as kernel execution proof.

Three final-source guests pass, with 3072/3136/3136 dispatches and 708/730/730 hostile
evidence mutations rejected. Each retains 28 child pages, with no additional
cleanup writes after exhaustion. Three ordinary useful-application regressions
and three successful live-parent delayed-cleanup/restart regressions pass: nine
current-source cases total, each within the original 240-second bound. Fresh
OVMF variables, read-only media, network off and exact serial/debugcon agreement
are verified. Exhaustion is safe retention, not successful recovery.

Host tests pass 554 default and 573 application-profile kernel tests in each
debug/release configuration, plus 26 ownership doctests. A new two-child host test
retains both job members after exhaustion, clears the simulated fault, advances
1024 more unrelated dispatches and proves further polls still do not write/free,
restart or release membership. All 22 focused Python oracle tests pass, including
synthetic due-dispatch collision cases. Synthetic fixtures are not VM evidence.

Two independent linked/canonical kernel builds match for each profile. Image
budgets: exhaustion122, deferred122, ordinary121 of208 pages; guarded stack36.
Six roles, 32 PMM records and16384-byte user RX bounds remain. Full call-chain stack
bounds are not proven. All64 user-build inputs remain unchanged; retained Cycle285
18 independent ELF/code pairs are reused and directly revalidated at closeout.
No fresh default/prepared/file-control guest replay is claimed this cycle.

Immutable public receipt: `runs/native-cleanup-exhaustion-readiness.json`,
2213006 bytes, SHA256
`F038AB7B8D2575102098B0682A407B3B1D4D8DD974CA252187F1A94D7ECC4135`.
It binds917 execution inputs, actual guest logs/transcripts, binary/media hashes,
build budgets and command captures. Historical Cycle285 receipt bytes are frozen;
the exact7 changed and2 added execution inputs are recorded separately. Older
Cycle283/284 source deltas remain bound to Cycle285, not mislabeled as current.

Reproduce with fresh output directories and the provenance-checked local tools:
`python -B tools/qualify_native_app_session.py --work-dir outputs/new-exhaustion --program-dir outputs/qualified-programs --exhaust-cleanup`.
Build the program directory with `tools/qualify_native_user_programs.py` first.
Omit the flag for ordinary sessions; use `--deferred-cleanup` for successful
delayed reclamation. Control modes are mutually exclusive.

## Failures And Retention

The first hostile test incorrectly expected a legitimate increase in a running
app's syscall counter to reject. Restrict frozen-counter attacks to stopped apps
and explicitly reject nonzero unadmitted counters. This left296 synthetic hostile
cases, below the test's expected300 threshold; add corruption of task identity,
admission, process handle, sequence and root. No semantic gate was relaxed. All22
tests then pass. Three native exhaustion guests had already passed the first
verifier; repeat all three against final verifier inputs and preserve the earlier
capture as superseded. No native failure or timeout was hidden.

Before builds, five failed/superseded trees were copied to retained evidence.
All5856 files/1880934049 bytes were checked by size and SHA256 at source and
destination before removing exact workspace copies. The local manifest is hashed
in the public summary without exposing private paths. Current passing builds,
shared host target, owner temporary files and PooleGlyph inputs were preserved.
Space remains limited; retain more superseded evidence before future large builds.

## Remaining Work

Next: waiting/pending/claimed request interleavings, including claimed-requester
death, then actual optical ISO packaging and sustained interaction on fresh boots
through a documented VM launcher. COM2 is not local keyboard/display. Exhausted
owners currently remain retained; a generalized recovery policy is still open.
General supervision, efficient idle, job interruption, full stack bounds,
PooleGlyph/PDC and accessible PooleGlass remain. No ISO, signing, release, main
merge, full canonical qualification or production promotion is claimed.

No phase/flag closes:40 phases,301 subphases,8996 requirements,59 additions,
98 flags/43 open,20 gap groups. Inventory:1466 Python tests,751 architecture
bindings,917 execution inputs. Inventory is not qualification. Live PooleGlyph
remains Phase65 with Phase66 Core IR audit next. Master checklist, Phase65 archive,
prior generated-report change and all owner inputs remain preserved.

Focused metadata replay passes311 tests in73.915 seconds,75.016 seconds including
capture, SHA256
`54DDCDD7A59504826D566C477C636352F662B14ED40CC0B800657E796006A64E`.
Capture confirms unchanged source and owner report. This is not full canonical
qualification; final staged checks follow this documentation closeout.
