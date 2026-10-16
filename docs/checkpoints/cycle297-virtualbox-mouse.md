# Cycle297: Owned VirtualBox Pointer Input

Date: 2026-10-15. Status: native replay passed, partial. Contract PVBMOUSE1.
Parent commit: `9de29cf63fdd788be9e4661df2c8d958c2e2edd5` (Cycle296).
Branch: `agent/userspace-integration-iso`; PR81 remains draft.

The previous goal turn made progress: pixel-equivalent rendering work and both
full QEMU pointer modes were qualified, committed and pushed. This cycle targets
the remaining VirtualBox mouse evidence, without expanding desktop code capacity
or claiming production completion.

## Implementation

The bounded per-event COM helper checks exact owned VM identity and running state,
uses a shared session, verifies unlock and rejects changed COM registration.
The parent pins PowerShell identity and never retries uncertain event effects.
The existing VM creation/configuration, 19-file visible runtime and cleanup
safeguards remain. Real PNG captures convert losslessly to the same pointer PPM
oracle used by QEMU. No host cursor input or arbitrary device/machine access.

11 new tests cover malformed/oversized motion, ownership/admission, precise ACKs,
timeouts and no retry, event quota, executable mutation, restricted operations,
capture paths/pixel preservation, actual helper rejection before VM access,
execution bindings and callback-failure cleanup. Focused replay:
`outputs/cycle297-focused3.json`, 118 pass. The preceding focused2 failure was an
incomplete listener mock, corrected by supplying its loopback address; the
failed log remains retained. No native execution result is inferred from mocks.

The first metadata replay executes 404 checks with two stale current-binding
count failures in historical Cycle288/295 tests. Their expected current count is
corrected from965 to969; historical receipt/hash comparisons and non-promotion
assertions are unchanged. `outputs/cycle297-metadata1.json` retains that failure.

The new PowerShell helper has a file-specific LF checkout rule, preserving its
qualified bytes and source hash across checkouts. The general PowerShell CRLF
rule is unchanged; no guest or execution-bound source changes follow qualification.

## Native Evidence

Both VirtualBox modes complete 17 pointer steps/41 observed movements at
1024x768; QEMU completes 17 steps/50 movements at 1280x800. Each full session
checks 573 challenge characters plus a discarded focus-probe key, exact app/file/
recovery responses, sustained progress and pixels. Visible VM cleanup and runtime
identity checks pass. The 240-second guest and 12-second observation bounds remain.

| Current Run | Result | Wrapper Seconds |
| --- | --- | --- |
| `outputs/cycle297-optical1/receipt.json` | Four optical checks pass | 591.640 |
| `outputs/cycle297-qemu-standard1/receipt.json` | Complete pointer/one-byte keyboard pass | 196.453 |
| `outputs/cycle297-qemu-burst1/receipt.json` | Complete pointer/burst keyboard pass | 192.078 |
| `outputs/cycle297-vbox-standard1/receipt.json` | Visible pointer/one-byte keyboard pass; cleanup verified | 206.968 |
| `outputs/cycle297-vbox-burst1/receipt.json` | Visible pointer/burst keyboard pass; cleanup verified | 192.906 |
| `outputs/cycle297-keyboardvbox1/receipt.json` | Visible keyboard-only regression pass; cleanup verified | 158.344 |

Total: six QEMU checks and three visible VirtualBox guests. Scripted device input
is not human-interaction, physical-device or unrestricted-input qualification.
Public receipt: `runs/native-virtualbox-mouse-readiness.json`. The three optical
application/control framebuffers are byte-identical to Cycle296, as are kernel
identities and the ISO. Every native source binding and all 84 program bindings
match. Reused program evidence is explicitly Cycle296: 182 host tests per profile
and 24 independent builds. The kernel host matrix is not rerun this cycle.
404 metadata/integration checks pass in `outputs/cycle297-metadata2.json` after
the two cardinality corrections. The test sets overlap; 1559 is discovered
inventory, not a full canonical execution. Architecture binds 821 sources and
execution binds 969. Older readiness receipts remain frozen.

Before commit, require the final staged 404-test replay in
`outputs/cycle297-metadata4.json` and the exact artifact/publication checks in
`outputs/cycle297-finalcheck.json` and `outputs/cycle297-publication.json`:
24 binary pairs, kernel pair/budgets, actual framebuffer identities and lossless
captures, runtime pins, owned cleanup, unchanged owner inputs and historical
receipts, reproducible ledgers and staged blobs. No full-suite pass is inferred.

## Handoff

The launcher selects `outputs/cycle297-optical1/receipt.json`.
ISO: `outputs/cycle297-optical1/PooleOS-UserSpace-Preview.iso`, 66109440 bytes.
SHA256: `8B4D32976D7C85E44F7D14915013AE4AB3EE4E28B392F0073F4318C8089881A2`.
The Downloads copy is named `PooleOS-Native-Windows-Cycle297.iso`. These are the
same guest bytes as Cycle296, not a new desktop feature release. Use the documented
local VM launcher/configuration, including COM2; no portable production or
physical-media qualification follows.

Master checklist and the live PooleGlyph Phase65 ZIP/report hashes were rechecked
unchanged. The newest checkpoint remains Phase65; no language/PDC advance is
claimed. No phase completion, full canonical pass, main merge, signing, release,
production promotion or physical-hardware action is authorized by this evidence.

Next resolve the tight desktop code budget, then surface lifecycle/recovery and
general input; retain any newly observed pointer failure and fix it first.
See [contract](../native-virtualbox-mouse.md) and the authoritative build plan.
