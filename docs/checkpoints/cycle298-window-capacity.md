# Cycle298: Explicit Native Window-Service Capacity

Started: 2026-10-15; final native replay and closeout: 2026-10-17.
Status: host-runtime refresh replay passed; production readiness partial.
Contract PWCODE1.
The first final check failed because the installed PowerShell executable changed
after the October16 guest cohort. That failed candidate was not committed/pushed. Its terminal failure
is retained in `outputs/cycle298-finalverify.json`; the pre-refresh receipt is
preserved byte-for-byte in `outputs/cycle298-before-host-refresh.json`.

The replacement is 495616 bytes, Microsoft-signed PowerShell10.0.26100.8972,
SHA256 `60C9B29843624DD8AF6B6A7B26147753BE6AEEF65098B9A503CC50850AFE410F`.
Local Authenticode validation reports Valid, signer Microsoft Windows,
thumbprint `667BBA1E1F478221AA65DE4F75187A751B03A453`. The reviewed exact hash
replaces the former `8BB6FA8C283B4D92120B1EF249A9B311B0F804D4CABBE9981159976C8BE76A5E`
pin; no limit or ownership check changes. No host installation/configuration is
performed. The review is not complete host attestation. A review helper initially
inherited an incompatible PowerShell module search path; its failed capture is
retained. Using the Windows PowerShell built-in module directory only in that
child process reproduced the valid signature without changing global settings.
The complete source-bound guest cohort passes after replay as optical4,
qemu-standard4, qemu-burst3, vbox-standard4 and vbox-burst3. Earlier results below
remain historical pre-refresh evidence, not qualification of the replacement pin.
Parent commit: `08a25a3366c23f65710b39915283764733a8a66f` (Cycle297).
Branch: `agent/userspace-integration-iso`; PR81 remains draft.

Entering Cycle298, the previous goal turn made progress: bounded VirtualBox pointer integration,
both complete input modes, regression evidence and build-plan updates were
committed and pushed. This cycle addresses the desktop code-capacity constraint
without converting the native architecture to a host OS or dropping requirements.
The October17 continuation also classifies its predecessor as progress: kernel
capacity implementation, repaired qualification and completed guest evidence.
The old process handle was missing; terminal captures and source-bound receipts,
not an assumed live process, established completion. No guest was restarted merely
because the observation handle expired.

## Implementation

The explicit `development-window-capacity` profile admits a seven-page service
only through the trusted slot 2 launch constructor. Ordinary `Program::new`,
PUSERBIN1 extraction and ordinary linking remain limited to four pages. Existing
eight VM mapping slots accommodate seven RX pages plus the one RW/NX user-stack
page. Stack guards, exact allocation ownership, full-tree readback, alias checks,
retention, scrubbing and retirement remain enforced. No new device authority.

PooleWindowCapacity shares the actual window service with PooleWindowConsole.
A startup function on page seven executes before that service. Its 18 compiled
bytes are `48c1c71148b84e4957454c4f4f504831f8c3`, at code offset 24576; a direct
relative-call pattern at 4338 targets it, corroborated by the source and object
relocation to the local read-only `.window_capacity` section. The byte-pattern
check alone is not general instruction-semantics proof. The deliberate padding
is test instrumentation, not new desktop functionality or a claimed optimization.

The service is 24594 bytes/seven pages; ordinary WindowConsole remains 16344 bytes.
There are 4078 bytes below the explicit 28672-byte image ceiling, plus deliberate
padding before the fixed probe. Future source/layout changes need fresh evidence.
The kernel is 130/208 pages with 36 guarded stack pages. The capacity-only read-only
boundary is 0x1A000; existing window 0x18000 and other profile selectors are unchanged.

## Verification And Failure History

Kernel suites pass debug/release: default 576, applications 595, desktop 601,
windows 607 and capacity 608. All 25 independently built user ELF/code pairs match;
182 user-space tests pass per profile. Final focused checks pass 81 tests.
The host sets overlap; they are not a full canonical-suite execution.

`outputs/cycle298-optical1.json` retains a genuine link failure: the embedded
larger service exceeds the old 0x18000 read-only boundary (used 0x192E0). No guest
was produced by that attempt. The repair is a separately selected 0x1A000 boundary,
not an increase in the 208-page overall image or 36-page stack capacity. The kernel
host matrix was rerun after the repair in `outputs/cycle298-host2.json`.

`outputs/cycle298-programs1/receipt.json` records 25 native pairs and 87 program
bindings. `outputs/cycle298-focused5.json` records 81 current-pin focused checks.
Execution binds 973 sources. The pre-refresh guest cohort is `outputs/cycle298-optical3`
followed by `qemu-standard3`, `qemu-burst2`, `vbox-standard3` and `vbox-burst2`.
All eight checks passed before the later host identity change.

| Pre-Host-Refresh Check | Result | Wrapper Seconds |
| --- | --- | ---: |
| optical3: two normal, stale-file-authority and ordinary unsigned denial | PASS | 563.907 |
| qemu-standard3: complete mouse and single-character keyboard | PASS | 196.641 |
| qemu-burst2: complete mouse and four-character keyboard | PASS | 194.547 |
| vbox-standard3: owned visible VM, complete single-character mode | PASS | 210.265 |
| vbox-burst2: owned visible VM, complete four-character mode | PASS | 190.891 |

Wrapper times include host validation; they are not performance benchmarks.

| October17 Host-Refresh Replay | Result | Wrapper Seconds |
| --- | --- | ---: |
| optical4: two normal, stale-file-authority and ordinary unsigned denial | PASS | 616.063 |
| qemu-standard4: complete mouse and single-character keyboard | PASS | 226.938 |
| qemu-burst3: complete mouse and four-character keyboard | PASS | 192.328 |
| vbox-standard4: owned visible VM, complete single-character mode | PASS | 207.375 |
| vbox-burst3: owned visible VM, complete four-character mode | PASS | 190.828 |

The refreshed final-source cohort passes all eight checks: six QEMU and two
visible VirtualBox guests. Native source and all normal/control kernel bytes are
unchanged across the host-pin refresh. The source-binding difference is exactly
`specs/native-virtualbox-mouse-profile.json`; no broader runtime acceptance.

The first input invocation (`qemu-standard1`) failed importing `tools` before any
guest launch. Its log and nonzero result remain retained. The corrected runner
uses `-m tools.qualify_native_windows`; no execution-bound source changed.

The optical2 cohort passed all four checks before the next harness repair.
The qemu-standard2 guest completed its interaction and retirement, then failed
post-guest hostile validation because that call omitted the capacity flag. It
remains a failed qualification, not a pass. The same omission was repaired in
the keyboard-only qualifier and interactive VirtualBox launcher. A regression
checks that all three call sites propagate both enabled and default profiles;
the actual synthetic marker controls exercise both capacity acceptance and
ordinary rejection. Focused checks pass after this repair. Native binaries and
the kernel/user host suites are unaffected by this Python-only repair, but all
eight final-source guest checks are replayed because execution bindings changed.

Final acceptance verifies stale-authority/unsigned controls, exact challenge
output, all-six-role 4096-dispatch progress, pixels, both pointer/keyboard modes
and owned VM cleanup. Each input run checks 573 challenge characters, zero serial
input and 17 pointer steps. VirtualBox records 41 bounded movements at 1024x768;
QEMU records 50 at 1280x800. Focused nonterminal input is discarded. Actual guest
framebuffers were inspected; the existing Terminal and read-only result panes
remain unchanged. No new general desktop workflow is claimed.
The 240-second guest and 12-second per-pointer-observation bounds are unchanged.

## Artifacts And Closeout

The public receipt is `runs/native-window-capacity-readiness.json`, SHA256
`C599D79C38A9DDF1EC2F2127E4B95B8D007F361BE69968A584F6D97546043769`.
It binds all 973 execution sources, 87 program sources, exact mode transcripts,
native traces, screenshots, tool identities and retained failures. Native source
and ISO equality across the Python-only harness repair are independently checked.
VM identities, commands and raw helper diagnostics stay in local output only.
The immutable pre-refresh receipt SHA256 is
`98DECA8195FCBD564B6D1959418B574A6CC53769172814B25CC72865130ED41E`.

Unsigned optical ISO: `outputs/cycle298-optical4/PooleOS-UserSpace-Preview.iso`;
66109440 bytes, SHA256
`419C7CD084062B4AEF11D5D8664EB351EA6EF922D75ECFE3ACF610AA8BACFE52`.
The identical Downloads copy is `PooleOS-Native-Windows-Cycle298.iso`.
`outputs/native-userspace-preview.json` points to optical4. The launch guide
retains the exact VirtualBox configuration, COM2 requirement and limitations.
This is not an ISO/release publication or physical-media image qualification.

Closeout replays the overlapping metadata/integration suite, regenerated
architecture/roadmap, exact staged blobs, historical evidence, actual binaries,
guest pixels, runtime hashes, owner inputs and publication boundary. See local
`outputs/cycle298-metadata-final2.json`, `outputs/cycle298-finalverify2.json`,
`outputs/cycle298-finalcheck.json` and
`outputs/cycle298-publication.json` for terminal outcomes. The discovered Python
inventory is not a full canonical-suite execution; PR81 remains draft.

The first complete metadata run passes 411 tests in 118.344 seconds (wrapper
122.109 seconds), with unchanged execution sources and zero discovery errors.
It discovers 1566 Python tests; the architecture ledger binds 828 inputs.
The final refreshed-host metadata replay passes 411 tests in 119.104 seconds
(wrapper 122.250 seconds), with unchanged execution sources, 1566 discovered
tests and zero discovery errors. Its log SHA256 is
`C343A516B709DAAE732A060FEDA129ACCA968C6E59A206967A4A89FF999EA222`.
Final staged artifact, regenerated-ledger and publication checks remain mandatory
before commit. No full canonical replay ran.
Totals remain 40 phases, 301 subphases, 8996 requirements, 59 additions, 99 flags
(44 open), 20 native gaps, 24 partial/1 blocked/15 not-started/0 complete phases.

## Progress And Remaining Work

The master checklist and live PooleGlyph Phase65 ZIP/report hashes remain
unchanged; Phase65 is still the newest checkpoint. No PooleGlyph/PDC advance is
claimed. Existing flags remain open. No phase completion, full canonical pass,
main merge, signing, release, production promotion or physical-media action.

Next implement generation-bound surface retirement/status and stale-view removal,
then restart/resynchronization and general application input. Keep service
separation, native overload/reset telemetry, scalable address spaces, accessible
PooleGlass, useful apps, stage117/watchdog, five legacy entry failures and all
complete microkernel/PooleGlyph/PDC/N0-N39 requirements.
See [WC1 through WC6](../native-window-capacity.md) and the authoritative build plan.

Concrete next-code boundary: `desktop/surfaces.rs` already binds surfaces to the
kernel-attested client slot/generation, and `process/windows.rs` already closes
windows when a surface closes. The missing link is trustworthy app-lifecycle
notification or observation, including faults without client CLOSE. Do not give
applications authority to retire another generation or put compositor policy in
the kernel. Challenge stale generation delivery, in-flight RPC/backpressure,
focus/drag cancellation and another application's continued progress.
Enable larger lifecycle logic through an explicit capacity-build path or service
split. The shared ordinary window body still has a four-page linker ceiling;
its regression binary must not silently inherit the larger profile.

Next-step inspection found existing `capability_ipc/process.rs` Inspect-only
leases and PCOMP1 completion, separate from InspectTerminate. Consider reuse
before adding another authority mechanism. There are only four leases/two per
owner; restart must account for retained old-generation observer leases. PCOMP1
explicitly distinguishes attachment/detachment from successful reclamation.
Any surface policy must preserve that distinction, and observer handles must be
admitted and refreshed atomically with the exact app generation. This is a design
constraint for the next increment, not implemented lifecycle behavior.
