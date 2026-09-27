# Cycle 192: Bounded Mailbox Qualification Cloud Backup

Status date: 2026-09-26
Status: unfinished development checkpoint; not merge-qualified
Move: `N8-SMP-MAILBOX-ORACLE-001`, N8.5/N8.6 supporting N36
Requirement: `ADD-N36-RECEIPT-COVERAGE-001`
Open flag: `FLAG-N36-RECEIPT-COVERAGE-001`
Parent backup: `e6caf65615d74705efb6bac20473a786ecd3eb6d`
Branch: `agent/n12-dispatch-execution-holds`
Pull request: [draft PR #78](https://github.com/rookepoole/PooleOS/pull/78)

## Cloud Storage And Main Merge

The owner requested cloud storage and merging if no reason remained to hold it.
This checkpoint preserves further implementation tests and freshly generated
bounded receipts on the existing GitHub branch. Main remains the Cycle 176
qualified commit `ac15d1da5304eab19ae3ed098d26cdcadfa78156`.

PR #78 is the only open PR and is mechanically mergeable, but GitHub reports no
status-check results. Neither fact supplies the project's missing qualification.
The current selected readiness projection is 9/27, with 18 profiles still pending
against the new kernel. Full canonical/Doctor and all other merge requirements
have not passed for this candidate. At least 65 scheduler control-execution
evidence gaps remain. These are engineering blockers, not missing authorization.

The [initial backup](cycle192-unfinished-cloud-backup.md) remains unchanged as
historical evidence. Its 4/27 projection and unrun-mailbox status are superseded
by this checkpoint, not silently rewritten.

## Completed Bounded Work

Native `PKMBX1` exports saved quiesced AP inputs: five context, fifteen baseline
and thirty-eight runtime words. The host independently recomputes both checksums
and checks identity, placement, CPU/control state, descriptors, stacks, ownership,
interrupt state and timing before normalization. This is consistency validation,
not authentication or proof against every coherently forged transcript.

The final IPI qualifier passes two four-vCPU boots, forty markers per boot,
609 rejection cases in 33 groups and 246 native kernel host tests. Each boot
exercises three APs, six operation classes per AP, nine accepted and three denied
deliveries, twelve EOIs, timeout/rollback/retry, three remote invalidations and
one retired generation. Verified release covers 96 resource and six frame pages,
417,792 bytes. Bounded PKAPOWN1 checks run twice per boot; general CPU retirement
and task-stack live retirement remain unproved.

Eight final QEMU executions are retained across loader, PooleBoot, transfer and
IPI. Two earlier passing IPI boots are superseded because adding the disabled-
oracle regression changed an input bound by the IPI receipt. The final qualifier
actually reran; old evidence was not rebound to the changed test source.

The last scoped run passes 57 tests, zero skips, in 189.518 seconds: ten mailbox,
33 IPI, four boot-chain, one entry-gate and nine publication-boundary methods.
It includes 906 recorded-evidence mutations and 360 raw mailbox mutations through
runtime and the actual release gate, and detects a deliberately disabled oracle.
Log SHA-256: `10F42ABFF988C39A72B1AF910A01825D4D1AFCFB1AAD267FC3DAC225B8A80FE6`.
Source and owner-report snapshots were unchanged during this run.

## Exact Evidence

Build ID: `PKBUILD1-CYCLE192-N8-MBX-ORCL-V01-0000000001`.
Canonical kernel: 530,072 bytes, 1,327 relocations, SHA-256
`B9AF7DFB13472C0A0D3CBE70036EFAD7C3B792F13FC9944ACEC935B362F0FBA8`.
The original core, entry, symbols and policy receipts remain admitted.
Newly admitted receipt SHA-256 values:

- Loader: `F51E811F7DA5C771BAEFA6437E27D6B48B96035D85AFC9757F2B55AC90C3C0FD`.
- PooleBoot: `25959CA635B90E27AC3AABCB03300DD1EB1C3F6B3B0664B1B3EDEB29BFE8C248`.
- Revalidation: `DF72365F4583614401500AEC332725DC7B63558EA2C63C0E1F55764EF7B1EF6A`.
- Transfer: `132A97CD727B3A135501B5932B75D7ED33CAEA7204B5F0E8F762CA167B65983A`.
- Final IPI: `D302E39890B500E1D8B732EDE823A62893A0C6453E5E78FC0747FE91DF7CF2F7`.

Final IPI qualification took 319.219 seconds, including the linked-image audit
and two real guest boots. Log SHA-256:
`4B314EC1800F8184E16D843D507E35981A96115FE26798BD1E83E590C3FE2EF3`.

## Repairs And Retained Failures

The private loader admission helper's missing root argument and the PooleBoot
validator dispatch were repaired. The already-passing loader candidate was
admitted without rerunning it just to fix orchestration.

The first selected projection passed only 6/27 because boot-chain gate pins
still described prior evidence. An initial repair confused the minimal ELF
fixture's trust hashes with the real image's hashes, yielding 4/6 tests passing.
Independent reconstruction from the actual kernel corrected those pins; all six
then passed, followed by the final 57-test run. Negative tests explicitly reject
both prior-image identities and fixture-only identities in the real boot gate.
The live retained set is 11,952 bytes with a 2,615-byte manifest, not the golden
fixture's 11,950 and 2,613 bytes. Both still deny unsigned policy with zero
authority grants, authorized actions and state writes. No trust check was relaxed.

Initial implementation failures, failed pin tests, stale-input projection
attempts, prior receipts and superseded boots remain preserved locally. None
are counted as passing final evidence or erased to improve the result.

## Remaining Work In Order

1. Reconcile Cycle 192 machine-roadmap, architecture bindings, checkpoint and
   historical assertions while preserving prior records. They remain explicitly
   historical Cycle 191 snapshots in this unfinished backup.
2. Requalify the eighteen affected profiles, starting with `N7-TRAP-001`: trap,
   CPU policy, xstate policy, xstate exceptions, privilege/MSR policy, physical
   memory, virtual memory, interrupt/time, first AP, per-CPU runtime, scheduler,
   preemption, deferred work, SMP scheduler, AP workers, SMP preemption, atomics
   and locks. Prior VM/CPU evidence is not current-image evidence.
3. Resolve the scheduler control-execution gaps and pass full exact-candidate
   canonical/Doctor, publication, configured GitHub and review requirements
   before marking PR #78 ready and merging.

No phase, flag, checklist item, normative charter condition or production gate
is closed here. Frozen coverage, historical full gate, demo ISO and PooleGlyph
owner data remain unchanged. No new ISO, hardware action, signing, release or
production promotion occurs. Private logs, keys, research, tools, media and
unrelated temporary directories are excluded from the source backup.
