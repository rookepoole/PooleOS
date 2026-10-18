# Cycle302: Bounded Serial Delivery

Started: 2026-10-17. Updated: 2026-10-18.
Status: bounded implementation and scoped qualification complete; full production goal active.
Parent: `8e11ffd7c9e451f4ece3fc681fe90f7162c09f68`, Cycle301.
Previous goal turn: progress. It repaired input ownership and real native stack
failures, qualified the bounded desktop cohort and pushed its source/evidence.
The complete production goal remains active, not narrowed to this increment.

## Entry And Selection

The tracked worktree is clean and on `agent/userspace-integration-iso` at entry.
Ordinary usage is allowed; the available weekly window is73% used. No separate
five-hour value is available. Apply the next-best-move skill to PooleOS scope,
not the unrelated Android/Poole Learning product steps in that general skill.
Keep all N0-N39, original microkernel, PooleGlyph/PDC and accessible PooleGlass
requirements. Do not sign, merge or publish a production release from this cycle.

Cycle301 retains a VBox observation failure: COM1 ends inside a RUN record while
COM2 later reports the app fault. An unchanged repeat passes. The current COM1
writer permanently disables after4096 unsuccessful transmit-ready reads. That
policy demonstrably cannot recover from transient backpressure; it is a plausible
but unproven explanation of the historical failure. Preserve host-side buffering,
capture failure and other causes as alternatives until discriminating evidence.

Compare mechanisms before implementation: merely increasing the spin allowance
does not provide recovery; retrying the next byte without retaining the failed
byte corrupts records; the overwrite-oriented early log ring is not an owned
lossless transmit queue; a new general asynchronous driver is broader production
work; a fixed-capacity retained FIFO with bounded explicit draining can preserve
ordered bytes across temporary not-ready states. Saturation must remain explicit,
not silently accepted as a valid stream. Select and verify that bounded direction
without claiming unrestricted delivery on failed physical hardware.

## Active Invariants

- SD1: within a live transmitter, accepted bytes retain order and exact value until sent;
  temporary not-ready is not permanent device absence. Never write an unready UART.
- SD2: each drain has a fixed total status-read/work budget. No unbounded retry,
  timing-limit increase or per-byte backlog multiplication hides a stall.
- SD3: fixed storage, checked indices and explicit saturation/loss accounting;
  do not overwrite queued data, allocate dynamically or claim success after loss.
- SD4: the existing probe, UART register ownership, capability authority, stack
  guards and total image capacity remain enforced. Measure new stack/layout cost.
- SD5: reject counterexamples with scripted register behavior before native use;
  qualify actual compiled adapter recovery and ordinary desktop regressions.
  Controlled backpressure is not proof of the old VBox failure's physical cause.
- SD6: preserve failed attempts, historical receipts and the old ISO; source,
  binary, transcript and image identities must agree before selecting a preview.
- SD7: update the build plan, flags and evidence; keep graphical launch controls,
  compositor recovery, persistence and all full production gates in the next path.

## Storage Preflight

C: has about590 MB free. Archive only explicitly selected superseded Cycle301
diagnostic media and Cycle300 optical/capacity media. Verify compressed content,
each decompressed hash and unchanged source bytes before removing loose copies.
Keep receipts, logs, binaries, current Cycle301 optical media and Downloads copies.
Record a manifest with exact relative paths so historical media can be restored.
This is evidence-preserving workspace maintenance, not physical-media writing.

Completed storage preflight:22 selected media files totaling1,465,401,344 bytes
were verified in `outputs/cycle302-superseded-media.zip` before individual loose
file removal. The archive is9,213,658 bytes. Manifest SHA256:
`5060A4006894F068A3D23DE44445DF2217B55B295C1EFAC644A59E597953686B`.
Current Cycle301 preview and historical receipts are unchanged; C: now has about
2.1 GB free. Historical archived media require exact manifest-guided restoration.

## Implementation Progress

The extracted old policy fails the retained `AB\n` counterexample after exactly
4096 busy reads; log SHA256
`3BE4BA11C09F0A1C36B371FDEBB94486FD4ABEA46D6B77E868697212673DED57`.
An earlier abbreviated exact-name filter ran zero tests and is explicitly not
evidence. The new pure transmitter retains1024 bytes, caps each drain at4096
total status reads, retries at record boundaries and between user dispatches,
and permanently rejects new bytes after saturation rather than inventing valid
records across a lost-byte gap. Accepted prefix bytes remain drainable. Counters
saturate; absence never touches registers; a floating bus is not transmit-ready.
The existing loopback probe and all authority/image/stack limits stay unchanged.
Emergency halted paths remain bounded best-effort, not eventual delivery promises.

All17 focused Rust serial tests pass after correcting a test's hand-counted
rejected-byte total (16 passed, one failed in the retained first repaired run).
Five new Python oracle tests pass, including ten hostile challenge variants.
The compiled diagnostic feature withholds exactly4096 status polls at the first
RUN record; it must recover the exact CRLF byte length with one timeout and no
pending/rejected bytes. Only its explicit diagnostic oracle may remove that one
validated observation; ordinary oracles continue rejecting it. Initial native
build attempt correctly rejected the unregistered feature combination. Only
the two explicit diagnostic combinations were then added to the build allowlist.
At that intermediate stage, no compiled/native pass was established.

First compiled diagnostic cohort: `serial-diagnostic2` passes two independent
normal workflows, stale-file authority and ordinary unsigned denial in641.687
wrapper seconds. Each forced stall delivers the exact preceding RUN record
with one timeout and zero pending/rejected bytes; normal oracles reject the
diagnostic marker. All eight kernel library profiles pass debug and release.
These are retained intermediate results, not final-source promotion.

The separately compiled default kernel then fails warnings-as-errors: its unused
explicit `Com1::flush` method is desktop-loop-only. Retained log SHA256:
`CFAF1F96ADF81004CC8141631FC0429B9403466A4CB7551CB01D6CABA28FB30D`.
Gate that adapter method under `development-shell-process`, exactly like its
caller; do not suppress the lint. Rebuild the default product and replay host
and native diagnostic checks against this final source. The prior diagnostic
media is losslessly archived (eight files,532,873,216 loose bytes,3,384,638 archive
bytes); receipt/log/binary identities remain available.

Final-source default build passes at207/208 image pages, with36 guarded stack
pages and one remaining image page. This preserves an already known tight
default-product budget, not a new capacity expansion or native legacy replay.
All eight final-source kernel library profiles pass debug/release (counts592,
611,617,623,624,624,624,624); all47 focused Python checks pass. Final host wrapper
106.984 seconds, SHA256
`2F22F926DDBCA99A79B4E219CDE7767AC48E03381057408FF7A1EA0876667C88`.

`serial-diagnostic3` passes all four final-source optical controls in632.734
wrapper seconds. Its three compiled forced-stall workflows pass exact byte-count,
zero-pending/rejection and independent COM1/debugcon marker checks. The diagnostic
is not preview-eligible. Its eight media files are archived losslessly (532,873,216
loose bytes,3,384,610 archive bytes). Superseded Cycle301 legacy-regression media
is separately archived with the same loose-byte count and3,283,238 archive bytes.
The Cycle301 selected optical image, Downloads copy, receipts and binary artifacts
remain untouched. Both archives carry per-member decompression/hash manifests.

Compiler prologues are retained for diagnostic3: entry local reservation0x818,
emergency panic0x468, interactive run0xC9D8, excluding saved registers/return
addresses and nested callees. These are measurements, not complete call-chain
stack bounds. The original36-page kernel and one-page user guards remain enforced.
The ordinary desktop builds at134/208 pages, entry0x1C000, read-only padding664.
Its four optical controls pass in636.047 wrapper seconds. All four standard/burst
QEMU/VirtualBox input runs pass:384 exact app observations,68 pointer steps and24
lifecycle pixel barriers. Wrapper times are239.735,224.297,245.719 and227.563
seconds, including setup and cleanup outside each frozen guest bound. All guest
and action limits are unchanged. QEMU1280x800 and VirtualBox1024x768 captures were
visually inspected: Terminal, Text and Numbers remain native, legible and bounded.
No new graphical feature or PooleGlass styling is claimed by this repair.
All four lifetime runs pass in160.296,159.000,155.329 and147.422 wrapper seconds.
The complete final-source cohort passes12 QEMU and four visible VirtualBox checks,
384 exact application observations,96 lifetime observations and48 lifecycle pixel
barriers. Every owned VirtualBox guest stops/unregisters without changing prior
registrations or moving the host cursor. Source/ISO identities stay unchanged.
All29 existing independent userspace ELF/code pairs are unchanged; their earlier
217 tests per mode are historical evidence, not new execution in this cycle.

Ordinary compiled prologues reserve0x808 entry,0x458 emergency panic and0xC9D8
interactive locals, excluding saved registers, return addresses and nested frames.
These scoped measurements do not prove all-path stack bounds. SD1 is explicitly
limited to a live transmitter; emergency owner replacement and halted paths
remain the best-effort limitations recorded above and in PSERIAL1.

Evidence reconstruction passes in9.469 seconds, rechecking native transcripts,
kernel budgets, pixels, lossless archives and owner inputs. Public receipt SHA256:
`49AF224C2B3213E7173AC52663E2713B4B2F1FE3F5D6528D90FA1BD716C3EF92`.
The local launcher selects only the ordinary image, and the Downloads copy is
byte-identical:66,109,440 bytes, SHA256
`E7AA840981B2A109619CD94B28CA2BF12DF9066E965002C13C6E22A8E6F2A12C`.
The Cycle301 image/copy and previous pointer remain retained. Metadata, staged
artifact and publication checks remain required before the development push.

First metadata run executes440 tests with three failures: the architecture schema
still requires857 bound files, and the roadmap schema still requires Cycle301
(also failing its checklist-gate integration test). Discovered inventory is1595,
with no discovery errors. Retained log SHA256:
`B6868F89470301352E2602C89AF11A0DCF164ABCA168E3D9A213E4628A345B0E`.
Update only those exact inventory/cycle pins to862/302; keep301 subphases, all
native limits and every production gate unchanged. Regenerate and replay the
metadata suite; these schema edits do not change the995 execution bindings.

Architecture regeneration then reports Windows `OSError: [Errno 22] Invalid
argument` while opening its existing output. The old baseline remains readable.
The following metadata invocation was mistakenly started despite that failed
generation:440 tests execute with two stale-baseline hash/reproduction failures,
not native failures. Retain that orchestration failure and log SHA256:
`37779183839A62A4A98D6CB087CFE393A39E190251F654CB378995A227D7FA2F`.
Regeneration must succeed as a separately checked step before replay. The cause
of the one file-write error is not established; no permission or guard is relaxed.

The isolated generator retry passes. `metadata3` then passes all440 selected
metadata/integration checks in121.625 wrapper seconds, with1595 discovered tests,
zero discovery errors and unchanged execution sources. Log SHA256:
`DA4335AB4D182110D68A84FC538BF691BC7629E9FF8F82FEBF1742EA9608A2EE`.
This selection overlaps the47 focused tests and is not a full canonical replay.
Architecture binds862 files, execution995 and programs97. All100 implementation
flags remain,45 open; no phase is newly complete. Staged/publication replay is
still required before commit/push. All earlier failed artifacts remain retained.

The first staging command rejects the new receipt under `runs/*`; the following
audit reports23 staged files and2101 scanned paths with zero violations. That is
not publication clearance for the missing receipt. Preserve `finalaudit1`, declare
only this exact public receipt in the existing `.gitignore`/publication allowlists,
and strengthen the final helper to require the complete27-file intended change
set, including explicit public/private/secret-path coverage for the new receipt.
Raw VM images, captures and private inputs remain excluded. The next audit
must include the receipt, not reuse the incomplete-stage result.

UART semantics are checked against TI's original
[PC16550D datasheet, section8.6.3](https://media.digikey.com/pdf/Data%20Sheets/Texas%20Instruments%20PDFs/PC16550D.pdf)
and [TL16C550D datasheet](https://www.ti.com/lit/ds/symlink/tl16c550d.pdf).
THRE readiness is distinct from shift-register-empty TEMT; neither spec establishes
the cause of Cycle301's host observation failure or physical-device qualification.

## Next Launcher Integration Constraints

Read the native application shell, startup parser and window service while native
qualification runs. `PooleAppShell` is15136/16384 bytes, leaving1248 bytes; its
startup decoder requires exactly eight arguments. `PooleWindowInput` remains
24594/28672 bytes with the explicit seventh-page probe. Ordinary WindowConsole
still has only20 bytes free. Future control code must measure real section use
and embedded-kernel read-only capacity before adding handlers or bootstrap grants.

The shell, not the compositor, currently owns the two process factories. Compare
a separate kernel-authenticated control endpoint with an explicitly versioned
typed extension of the existing authenticated console channel. Preserve the
ordinary PCS1 decoder's unknown-message rejection, generation/sequence binding,
one-shot launch effects, pending/failed replies, quotas and launch rollback.
Do not implement graphical launch by synthesizing shell-command text or granting
the compositor unrestricted process factories. These are source-backed design
constraints for the next increment, not a newly implemented launch protocol.

## Closeout

The expanded publication tests pass all nine checks in88.781 wrapper seconds,
including the complete staged receipt and explicit rejection of its private/raw
variants, secrets and user paths. Log SHA256:
`FD5EE0EE15EE69A5F2041C9963184E9C4DF9E73CDA166CA1BF3F47EFFC33CFA6`.
The complete `finalaudit2` passes in62.828 seconds: exactly27 staged files,
86 unchanged historical readiness/execution receipts, all29 ELF/code pairs,
exact ISO-copy equality, owner-input hashes, schemas and generated ledgers.
Publication scans2102 indexed paths with zero violations. Audit log SHA256:
`7A28B50A5775A562DF1C93D75EB9099533A6678131C678BA6AB968ED6B58698E`.
Rebind and replay after adding this closeout before committing the final tree.

SD1-SD3 pass for the live fixed-capacity transmitter through scripted hostile
controls and compiled recovery. SD4 retains authority/guards and measures actual
layout/prologues, without claiming complete stack bounds. SD5 includes the full
ordinary input/lifetime matrix. SD6 preserves historical bytes, failures and the
prior preview while reconstructing the new artifact identities. SD7 updates the
plan, charter, ledgers and existing flags. These are bounded development results;
all unqualified production properties and the complete goal remain active.

Next: authenticated graphical launch/restart through the process-owning shell,
with measured code/stack/layout budgets, one-shot requests and stale-generation
rejection. Then compositor recovery, COM2-independent local graphical boot,
persistence, accessible PooleGlass and the complete native microkernel/PDC/
PooleGlyph path. No main merge, release, signing, firmware change or physical-media
write is part of this checkpoint. Development PR remains81.
