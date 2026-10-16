# Cycle 246: Owned Timer Shutdown

Date: 2026-10-08. Result: PROGRESS, not production readiness or phase exit.
Move: N13-USER-ENTRY-LIVE-001, USI-1 timer shutdown before user-space integration.
Owner priority remains a usable native user-space ISO, then the complete robust
N0-N39 microkernel. No new ISO or interactive user session exists in this cycle.

## Implementation

PKUSER12 adds a no-std bounded drain policy and a native adapter. The timer is
masked and stopped; all IRR/ISR/TMR banks, timer mode/counts and delivery/EOI
accounting are checked. Only the owned vector can be pending; preexisting ISR,
foreign vectors, unsafe modes and unbalanced accounting retain ownership.
A maximum32 checked interrupt windows and at most2 new deliveries per shutdown
bound recovery. Even an empty first snapshot gets a window for accepted work.

The native window retains root, task pages, syscall/interrupt descriptors and
private stack. Dispatch validates its root lease, vector, privilege selectors,
RFLAGS, RIP window, saved RSP, stack bounds, trap depth and actual IF before
acknowledging the sole owned in-service timer. It never resumes a user frame or
rearms the timer. Unexpected entry is fatal rather than guessed safe.

The live proof adds actual one-shot pending and empty-then-arrival cases, plus
an injected window failure while13 task pages remain retained. Resume/reap/root
activation and copied free handles reject during quarantine. Abandonment retries
the same pending request without rearming, detaches only after quiescence and
then scrubs/unmaps/releases. The healthy peer continues and exits84.
All14 previous survival cases and construction rollback/retry remain exercised.
See [mechanism and limits](../native-user-timer-shutdown.md).

## Verification

The final full focused capture passes in283.125 seconds. Fourteen checks include
361 debug kernel,111 repeated user-release,24 repeated VM-release,8 compile-fail
and10 boot-exit Rust executions (514 total, not514 distinct tests),35 Python
oracle tests, formatting, freestanding builds and two feature-conflict denials.
Two fresh57-marker native guests pass with matching serial/debugcon plus one
ordinary unsigned-denial guest. Each rejects548 altered-evidence controls.
Both qualification boots use the new fixed120-second bound; ordinary boot45s.

Each native guest records15 peer-survival cases,148 dispatches,119 accepted
preemptions,62 survivor quanta after the first task stops,307 actual CR3 writes,
538 released pages,247 scrubbed data pages and one retained ACPI page. Three
timer-drain deliveries receive exactly three EOIs. One pending case, one late
case and one quarantine/retry pass. The failed-cleanup task consumed a quantum
whose outcome never reached the scheduler: zero committed ticks/preemptions for
that task do not mean no execution. Exact accounting is the next work item.

All754 captured source bindings and the PooleGlyph owner report remain unchanged
during qualification. Fresh variables, read-only virtual media, no guest network
and no host acceleration are recorded. This is an emulator proof, not hardware
qualification or optical-ISO acceptance.

- Receipt: `runs/native-user-entry-readiness.json`, SHA-256 `A77030BD8C2557C85D5670D7EDE5C17876C6B05F5EF5E303BC8C82126FC3A6F8`.
- Capture log: `9B543AEDBC6E0DF78893333362B5AC837F03E8FF4C9B35C92D46031AAB6FCD9A`.
- Kernel:651064 bytes,178 mapped pages, entry0xB000, SHA-256 `92107CE1F169C5E2069161F8F04C2E3613705F7825D4A545C1C9814C2E9A57D1`.
- Linked kernel SHA-256: `7E8CCE7E0219B239210E42D69EEB70813D7EED6A155E4B34DF8E2D957CDD7442`.
- Historical Cycle245 receipt preserved verbatim at `tests/fixtures/cycle245-user-entry-readiness.json`, SHA-256 `AC96D028977F357C41318AB2CF33E761B0552E82FAB30B5637835681A6CE8346`.

## Failed Attempts And Bound Revision

1. First native attempt failed linking after70.063s: text0x8D83E exceeded the
   0x8D000 reservation. Text/data moved to0x8E000, RELRO end0x9E000 and image end
   0xB2000. Existing192-page cap and36-page guarded bootstrap stack are unchanged.
   Log: `E0718E78A13E02C6F4DD0178758ADF9F82CD44094CB48F320BA12FA91A35DAA7`.
2. Second attempt failed after165.000s when the expanded first guest exceeded90s
   after passing its original14 rounds. Log:
   `93EE7DB24458DAC03A862492554AD618FBE98D12B8F73DA261D3F185DC278743`.
3. Diagnostic only: unchanged source bindings and exact failed-attempt media
   SHA-256 `FFA145890011C23EA3D682C873BD950C58430AB92451CAF10D73795083EBF7D7`
   completed all markers in93.844s within a180s diagnostic bound. Capture97.391s,
   log `509540CCA3E841C59B1B5C9F19F8C39BAE90E579B9E754940F30F71C5A86ABDB`.
   This is not the qualifying run. A120s qualification bound was then fixed
   before both fresh final boots. No case, workload loop or success criterion
   was removed. The old90s failure is not retroactively marked passing.

Earlier focused checks: five drain host tests pass (capture5.016s), freestanding
compile passes (3.625s),35 oracle tests pass (0.641s). Their logs respectively:
`192182BFC0925045C683B2C433525096D06FE8FC1A25D3D2E259DB1114170742`,
`C73D66B31A7448C0A8EF5E6DF344722549022D722AF89FE36F308A3C10428CF4`,
`9F1B8D6658DF77A62EE2B34DC2ECCF4EE7F1192526C62A281644CBC67D17083C`.

## Progress And Remaining Gaps

USI-1 remains partial; USI-2 through USI-5 are not started. N12/N13 stay partial.
No phase or flag closes:40 phases,301 subphases,8996 mapped implementation
requirements,59 additions,97 flags/42 open and20 program gaps remain.
The open N13 integration flag now explicitly requires exact accounting of
terminal and failed-cleanup consumed quanta through retry and abandonment.

Broad after-mask silicon races, ambiguous ISR recovery, timer configuration
failure before lease publication, independent missing-IRQ recovery, general
quarantine/admission, complete N3.7 stack bounds, native #SS/general exceptions,
XSAVE/SMAP/SMP/async state, IPC, services, shell/apps and hardware remain open.
The late test observes empty IRR then creates a real arrival before masking;
it does not qualify every pipeline race after masking. An external120s guest
bound is not a native watchdog. Full production-contract migration and fresh
candidate/prerequisite replay remain required before merge; old gates are not
rebound to this image. No signing, release, firmware or physical-media operation.

PooleGlyph Phase65 remains the observed checkpoint, Phase66 next; no metadata
or checkpoint is promoted to kernel authority. Its owner report is untouched.
Master checklist coverage remains zero unmapped. Historical execution-source
ledger is conserved, not rewritten as new execution.

Metadata attempt1 ran129 tests in51.164s (capture52.0s);127 passed and two failed
because the roadmap schema still required Cycle245. The constant is advanced
to246 without relaxing validation. Log SHA-256:
`5D4B40D29D18551AE8FECBFFE10ACF727251119477EAE944B77702BF23CAEC93`.
The repaired closeout passes129/129 tests in51.122s (capture51.953s), zero skips;
source and owner report unchanged. Log SHA-256:
`DBA9CA1E66E7E09566C9F8D97F566356518528E1C23375EEA5702EE3AC6E72FC`.
Discovery finds1284 Python tests with zero import errors; this is not a full1284
execution claim. The read-only gate projection still has2/27 current native
admissions and5/27 current static source closures;25 and22 respectively remain
stale. These are not fresh guest qualifications. Architecture binds477 sources.
