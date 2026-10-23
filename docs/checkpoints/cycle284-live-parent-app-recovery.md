# Cycle284: Live-Parent Application Recovery

Date: 2026-10-13. Previous goal turn: progress, native applications qualified and
pushed as a draft checkpoint. This cycle follows the user-space integration ISO
priority. Complete robust microkernel development remains required afterward.

## Scope And Result

The existing native deferred-cleanup mechanism now runs with PooleText,
PooleNumbers, PooleAppShell and the file/console/init services. The only kernel
build change is allowlisting the exact application/deferred feature combination;
no native algorithm or capacity changed. Three fresh contained guests pass,
including stale numbers-file authority. They complete 8576, 8576 and 8448
dispatches and reject 1197, 1197 and 1183 hostile evidence mutations.

Each guest has four cleanup lifetimes, covering both generations of both apps.
The first cleanup failure retains all 14 pages; retry after 64 dispatches fails
again, then completion follows after another 128 dispatches. Child calls/ticks
stay frozen. Init, files, console and shell progress across the retained interval.
Actual page release precedes completion publication and generation-bound restart.
The existing kernel adapter tests early-completion rejection and ordinary free
denial during each injected failure. Its admitted/live mask includes retained
terminal owners; this does not mean they remain runnable.

The harness sends the same 557 bytes/37 commands and checks useful computations,
fault containment, both restarts and stale-file denial. Four explicit barriers
wait for exact kernel task/generation COMPLETE observations before the following
status command. No synthetic completion, transcript-only proof or sleep is used.
The frozen per-guest bound remains 240 seconds. Kernel observations are separate
from COM2. All captures retain unchanged source and owner-report identities.

Combined-profile host tests: 570 debug, 570 release, 26 ownership doctests.
13 application oracle tests pass. Independent linked and canonical kernels match.
Recovery image: 122/208 pages, 36 stack pages, RO used 73544/padding 4280 bytes.
Six roles, 32 PMM records and 16384-byte user RX remain unchanged. Full call-chain
stack bounds are not established. No new default/prepared guest replay is claimed.

Public immutable receipt: `runs/native-app-recovery-readiness.json`, 867649 bytes,
SHA256 `CC53CE50B9ADE16E0D4B6C79723B46FE5B6AA721A927BD5D00C12ACE42115FA4`.
Native capture: 170.312 seconds,
SHA256 `4ED314CAEE56D157BFA63A06CC7DFA5960DFA065D255FA5DB0BF0B14AF5CFED6`.
Host capture: 39.203 seconds,
SHA256 `C757CA2CA52D56B2CA8A7199C2E5F080072E6D514D438497DB91BA695B318585`.
All 912 execution inputs remain bound. Metadata and exact staged checks follow
closeout; inventories are not full canonical qualification.
The repaired metadata/oracle set passes 300 tests in 65.134 seconds (66.234 seconds
including capture), SHA256
`1C702C1A1488B6D385FAB852690B4B9179778F3C9783F68A7166F02E875ECCF6`.
Final staged replay follows these documentation edits; the native receipt stays
immutable. Reproduce in a new output directory with
`python -B tools/qualify_native_app_session.py --work-dir outputs/new-app-recovery --program-dir outputs/cycle282-programs5 --deferred-cleanup`.
The program directory must contain its verified source-bound receipt and binaries;
regenerate it with the user-program qualifier if those inputs have changed.

## Failures Preserved

The first synthetic mutation set zero to zero and expected rejection. The second
advanced shell counters when it meant to stall them. Both fixture errors were
repaired without rejecting valid service progress. Their failed logs remain.
The first guest correctly printed `retiring`; the old scenario expected terminal
fault status too early. Its 70.234-second failed run and partial raw input/output
remain retained, SHA256
`0E9EA697A9DA5D3E7542F55F027D6148DE9CAC62908F4CCDD0FA81CA7301560E`.
Generation-bound observation barriers repaired the harness, not the kernel.
The final three guests pass with the original limit and exact expected results.

The first 300-test metadata run failed three stale current-roadmap assertions:
two next-move title phrases and the preceding qualification status. Reconciled
the labels with the remaining native-shell application/optical work and new
recovery state; no native receipt or acceptance predicate changed. The failed
66.016-second capture is retained, SHA256
`783A95F491F66864D0A92EE192219AB5D452DCB09C8210D828E1C65D746B63EB`.

## Next Move And Boundaries

Next: native malformed/untracked file requests and requester death; exhausted and
multiple pending cleanup owners; waiting/pending/claimed request interleavings.
Then optical ISO packaging, sustained input and fresh boots through a documented
interactive VM launcher. Current interface remains serial, not local display/input.
Host C storage is low (about 1.3 GB observed); retain and verify older build evidence
before additional large builds, never delete the shared host target or owner temps.

No ISO, signing, release, main merge or production promotion occurred. General
supervision, idle, job abort, full stack bounds, PooleGlyph/PDC and PooleGlass remain.
No production phase or flag closes: 40 phases, 301 subphases, 8996 requirements,
59 additions, 98 flags/43 open, 20 gap groups. Inventories: 1455 Python tests,
742 architecture bindings, 912 execution inputs. Historical receipts are immutable.
Live PooleGlyph folder remains at Phase65; Phase66 Core IR audit is next. Its
existing generated report change is preserved. No PooleGlyph source was modified.
