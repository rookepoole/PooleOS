# Cycle266: Native Six-Process Capacity

2026-10-11. Previous goal turn: progress (Cycle265, commit8ee3a99).
Current move: USI-3 capacity prerequisite for the owner-prioritized usable native
user-space ISO. No new boot-screen work. The complete robust microkernel remains
required after the ISO. Contract: [PCAP8](../native-session-capacity.md).

## Implementation

- IPC task tables/endpoints4->8 match scheduler capacity8. Per-task capability,
  reply and request slots4, queue depth4 and message size64 remain unchanged.
- Atomic six-member admission publishes13 explicit grants: two isolated endpoint
  pairs plus the console service/client pair. Only the console service owns COM2.
  Partial plans, exhausted tables/objects and stale generations roll back.
- Native startup copies four independently compiled program blobs into six private
  CPL3 images. Additional init/counter copies are capacity workloads, not useful
  applications or a real init supervisor. Fixed pair-dependency cleanup covers4/5.
- PSESSION5/PCAP8 records all six roots, worker progress/retirement and78 owned
  task pages. Firmware snapshot quota12 is separate (one page in every guest).
- No user-space program source changed. Reused source-current Cycle265 builds;
  independently compared all five retained ELF/code pairs and embedded bytes.
  Reuse is not a fresh user-program build claim.

## Executed Results

Final capacity capture: `outputs/cycle266-native-second/receipt.json`,75.312s.
Two normal46/49-byte real inputs echo exactly; console tasks exit0 at448/449 and
484/485 dispatches. Both independent pairs reach576 dispatches, with1152 root
writes and26 pages reclaimed. Extra pair remains live.

Malformed worker5 exits120 at dispatch6; dependent4 exits111 at10. Console still
echoes35 bytes and exits0 at291/292; the original pair reaches512 dispatches with
1024 root writes. Total52 pages reclaimed. Worker counters remain frozen after
retirement. Hostile marker controls reject78/78/75 cases. No timer preemption was
observed in these short cooperative workloads; no new preemption claim follows.

Both final normal kernel builds match byte-for-byte. Canonical capacity kernel:
`E57488A34E37CBF1082B82260A1A365DF56F625CE2B6D00B83CE819277C48D73`.
Linked kernel:
`80C3D7D243B4C8674813F63CC7C43C93A195FF8B65F1CF6599C185B364EF2640`.
Bad-worker canonical:
`ED4670FAC774F001420D22C28884ADA203E2E3146645AE78825A685B66FA3A28`.
Canonical files772968 bytes each; mapped image207 pages, not the file-size ratio.

Four-process replay: `outputs/cycle266-four-second/receipt.json` retains normal
45/52-byte echo/close and authenticated wrong-peer revocation. Its three guests
passed in70.750s on the final layout. Public aggregate:
`runs/native-session-capacity-readiness.json`, sections `session_capacity`,
`four_process_regression`, `default_regression` and `footprint`.
Aggregate SHA256:
`40C82DC8AF19815503268F3242AC23C556BBD1BA3C1B405C3DD2C5E52ACC3D5A`.
Current source bindings:837 capacity,837 four-process,830 default and29 unchanged
user-program inputs. These are separate from the whole-tree capture guards.

Final default regression passed25 checks in411.453s:1730 Rust test executions,
116 Python oracle tests, two default containment guests and ordinary unsigned
denial. Console kernel debug/release each pass489 tests; default host475. Six new
Rust tests cover upper-slot authority/rollback and six-process console admission.
Focused Python25/25 passed. Counts overlap; none is the full canonical suite.
Default canonical kernel:
`04536053EF9DFA91DCCD55E827AC85CC1520E76FD6F251FD992E8DDBEE9E66F5`.
Capture log:
`1097F08AC97556DA0784DC4E39788500F02127E1D43E380A0D4979154CD993E9`.

Checkpoint metadata223/223 passed in52.927s (capture53.985s), log
`ABD91A41F3A6F92D7A62591BFCB56E9FF8184B81CE8AA622491394F51ACA3D72`.
Historical conservation159/159 passed in9.763s (capture11.235s), log
`978246C5FCB0211642427044DC5CB45C0F573BE5F21F6E55EF4D7BD5EFE3A25C`.
These pre-closeout suites overlap. Final staged artifact/publication checks remain
a separate capture; neither suite replaces the full canonical audit.

## Failures And Layout Repair

Initial205-page six/four-process runs passed but the default regression failed
linking: expanded IPC BSS reached0xCE818 beyond fixed0xCD000. The24 preceding
host/oracle checks passed; no default guest ran in that failed attempt. Preserved
capture `outputs/cycle266-regressionfirst.log`:
`BF6BE96528415F5DC77E525536F4AF8FE6155FA8337B26A36F914B09F6D1C1BB`.

Reviewed CP4 migration sets image end0xCF000 (207 pages) within unchanged208-page
bootstrap capacity. No diagnostic removed, stack enlargement or authority
relaxation. All three affected profiles were rebuilt/re-executed afterward;
initial205-page successes remain historical, not final candidate evidence.

Other failures retained: two atomic patch-verification failures made no edits;
initial Rust test compilation incorrectly compared Scheduler directly instead of
its public summary; hostfirst detached only4 of8 owners; focusedfirst expected the
old pair expression; nativeverify initially used the wrong ELF path/field. All
were repaired and retested. Raw captures remain, except the initial compiler
output retained in the tool transcript only. Detailed notes:
`outputs/cycle266-development-failures.md`.

## Resource Boundaries

IPC static owner19264 bytes. Final disassembly records session stack allocation
0xF000+0xF68 (65384 bytes), caller allocation0x8000+0x38, and saved registers.
The36-page guarded stack is unchanged. Prologue inspection and passing boots are
not a maximum call-chain stack proof; this remains open before further growth.

Each image retains five PMM allocation records. Six consume30 plus firmware
within32 records; eight native images are NOT qualified merely because IPC has
eight slots. One image page remains before the208-page cap. Keep both constraints
visible during lifecycle/shell integration; review layout/allocator changes first.

Generated objects are retained in individually hash-verified D-drive archives,
including failed and superseded builds. Raw failures, receipts and canonical
ELFs stay available. No owner scratch/private inputs are deleted. Full disk-space
reservation and reproducible archive restore remain open.
Cycle266 adds38 scoped archives (87 across264..266), including the failed default
build. Every archived member was compared to its source before removing only
the verified generated target. No recursive scan of the whole evidence tree.

## Progress And Next Move

USI-3 remains partial. Next: generation-bound, narrow kernel process start/stop
authority and a real user-space supervisor, then USI-4 shell/read-only files/two
useful apps and USI-5 optical ISO acceptance. Retain native console pressure and
malformed-request controls, executable trust/loading, restart, efficient idle and
native clock recovery as open requirements. A kernel command shell is not a
substitute for user-space policy.

No production phase/flag closes:40 phases301 subphases8996 requirements59 additions,
98 flags43 open20 gap groups.1378 discovered Python tests and608 architecture
bindings are inventory only. Three known load/transfer readiness tests and the
full exact-candidate canonical suite still gate main. No ISO, useful application,
release, signing, physical hardware/media action or production promotion claimed.
PooleGlyph Phase65/Phase66 boundary and owner conformance inputs remain unchanged.
