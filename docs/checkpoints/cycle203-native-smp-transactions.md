# Cycle 203: Native SMP Transactions

Status date: 2026-09-29. Pre-production checkpoint; not main-merge qualification.
Parent: `f20c807ceaafb65db02d902d6b727811faf3ab46` (Cycle 202).
Selected move: `N12-SCHED-SMP-001`, N12.1-N12.7 / N36, with N6 image reproduction.
Requirements: `ADD-N12-SCHED-SMP-001`, `ADD-N36-RECEIPT-COVERAGE-001`.

## Native Repair

Inspection before SMP recorded-admission work found that checked-counter errors
could leave task ownership, queues, current task or pending ticket partially
mutated. The original kernel failed seven of eighteen native cases in both host
optimization profiles. `scheduler_smp.rs` now performs allocation-free copy/commit
for staging, exact acknowledgement, cancellation, timeout, completion and local
dispatch plus retirement. Pending-ticket installation validates a candidate and
preflights local commit/timeout on discarded copies before publication. It does
not fabricate or accept a remote acknowledgement.

The transaction assumes exclusive caller ownership. This is not a cross-CPU
atomicity, interrupt exclusion or general scheduler correctness proof.

## Evidence

- The same eighteen cases pass after repair; an added late-publication case makes
  nineteen native tests per debug/optimized profile (ten existing, nine new).
- Two Python SMP methods compile the actual native source with the private-state
  fixture. Nine disabled-repair variants are caught. State comparisons cover all
  task fields, every queue slot, current tasks, pending tickets, counters and
  validation, including valid retries after rejection.
- Existing deferred transactions remain covered: twenty-one native tests in both
  profiles and four disabled variants. Combined transaction run: four Python
  methods pass, zero skips, 21.406 seconds.
- Reclamation core: all seventeen stages pass, including 246 kernel regressions
  in debug/release, lifetime/stack/execution cases, borrow doctests, host and
  freestanding format/clippy/build checks, and exact linked-image validation.
- Final entry qualification: two clean matching builds, 246 kernel tests and
  43 image controls, 38.625 seconds. Entry-gate regression independently rejects
  twelve corrupt pins with the component validator bypassed.
- No new-kernel QEMU run was performed in this cycle. Existing positive boot
  receipts remain byte-identical historical evidence and are rejected as current.

Combined scoped regression passes **109/109**, zero skips, in 149.640 seconds.
It includes the corrected 58-test focused scope, one independent entry-gate test
and 50 metadata/checklist tests. Log SHA-256:
`8685E792EBA51FF228060100FFF386884F22B5B0C45179DB8A9255D44640FF70`.
Source and owner report were unchanged during execution. These counts overlap
other evidence and are not additive. This was not the full canonical suite.
Initial conservation passed: all 18 parent current records archived unchanged,
344 bindings verified, all prior boot receipts and protected artifacts preserved.

The initial focused run was 57/58, zero skips, because a frozen-image assertion
still expected the old hash. That assertion was corrected and the final entry
receipt reproduced with the updated test binding. Metadata initially passed
40/50, then 49/50: older tests accepted previous-image receipts and retained a
five-profile count. Corrected tests require stale-image rejection and fourteen
pending memory/scheduler profiles. Both failures remain in the machine ledger.

## Exact Identity

| Artifact | Identity |
| --- | --- |
| Build ID | `PKBUILD1-CYCLE203-N12-SMP-TXN-V1-00000000001` |
| Canonical kernel (530,072 bytes) | `A943DCB6E41A27F952868F05ED2B3523B47D9D7A7B5DB909EE385205F7CA3B31` |
| Linked kernel (7,046,784 bytes) | `557687A9F39EEECFFD839A8619D696CEBB4E391B229778162725752C72B4D9AA` |
| Loaded image (602,112 bytes) | `F4698CB6E7DE51E07041410A274E3BE08886D09F51E681290E743E1361858FFC` |
| Entry receipt | `E90F11157F3416CE2C78650C4605ADF92BF5D7AC19A293E0C105499EF17276A5` |
| Core receipt | `33EE501601ACB8109FA867C2634FAC1C04F43505B4DD6C6D75821545B120BDD8` |
| SMP source | `392A986CFEC545BB56A54A669005011096FAE243FB863036C6FC3F06909461D4` |
| Native fixture | `13C3D0934B6FE435404DABAA0D2B22F913B556AE4D0A25BD809972D435DC8F56` |
| SMP Python tests | `321374D12C8C113A4F6887E8255F9241FF005D0171A199419F4E2DB71667947F` |

Entry is at `0xA000`; 1,326 relocations. Entry binds 74 inputs including all
39 Rust crate sources. Matching builds are on one host, not independent builders.

## Preserved Failures

The first fault injector changed an owner epoch without matching the ticket, so
one test hit stale-generation rejection instead of the intended counter path.
The corrected pre-repair run still failed seven cases; this was a real native
state failure, not merely a test correction. The first entry attempt rejected a
stale manifest contract digest; the second rejected the live build-ID literal.
Neither was admitted. A preliminary kernel and intermediate entry receipt are
superseded, not erased. Log hashes and exact failure details are retained in the
machine ledger; local diagnostic logs remain under ignored `outputs/`.

## Progress and Next Move

Selected current-source readiness is **2/27**: entry and errata only. The changed
kernel invalidates twenty-five profiles: six boot-chain profiles (including
policy), five CPU profiles and fourteen memory/multiprocessor/scheduler profiles.
`FLAG-N12-SCHED-SMP-001` is reopened: 94 flags, 37 open. All forty phase statuses,
301 subphases, 8,996 locked checklist requirements and 57 additions are preserved.
Architecture bindings expand from 338 to 344; source test inventory is 1,084,
which is discovery, not a full-suite pass.

1. `N5-SYMBOLS-SEMANTICS-001`: qualify symbols and policy for the new exact image.
2. Replay boot/CPU/memory/scheduler dependencies without rebinding old receipts.
3. Repair SMP recorded admission and replace its sixteen constant-only controls;
   at least fifty-one groups remain across SMP, AP-worker and SMP-preemption lanes.
4. Complete later profiles and exact-candidate canonical, Doctor, release gate,
   publication scan, configured GitHub checks and review conditions before merge.

The branch in [PR #78](https://github.com/rookepoole/PooleOS/pull/78) is the cloud
checkpoint path. Cloud backup is not a passing merge gate. Main stays at the
previous qualified baseline until those conditions pass. No tag, release, key,
firmware, physical media, new ISO, N12 exit or production promotion is claimed.
The prior demo ISO and owner PooleGlyph changes are untouched; Phase 65 remains
metadata-only integration evidence and Phase 66 remains prospective.
