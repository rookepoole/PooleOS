# Cycle268: Native User-Space Launch And Restart

2026-10-11. Previous goal turn: progress, Cycle267 commit fc9164d.
Owner priority: usable native user-space integration ISO first, then the complete
robust microkernel. No splash redesign, kernel command shell or usable-ISO claim.

## Implementation

[PLAUNCH1](../native-process-launch.md) adds two generation-bound launch leases,
PSABI1 call19 and numbered, idempotent launch requests. Trusted catalogue grants
pin owner identity and child slot. An exclusive permit and atomic admission join
the child, scheduler, IPC grants, process handle and completion without a dispatch
window. Failed admission rolls back grants without leaking quota or rewinding
generations. Cleanup failure must retain ownership/claim, never announce success.

PooleSupervisor is a separately compiled CPL3 program. Its bounded user-owned
policy requests a worker, observes attachment revocation, and requests a second
lifetime. First launch admits a preprepared, never-dispatched child; restart
constructs fresh ownership only after full prior cleanup. The worker/survivor are
diagnostic payloads, not the two useful applications. This supervisor currently
lacks interactive commands, general exit reasons, orphan handling and retry policy.

Eight new kernel tests cover strict ABI/identity, quotas/exhaustion, one-shot claims,
admission rollback, owner death/revocation and retained failure. Five new user
tests bring debug/release runtime suites to44 each. Six independently compiled
program ELF/code pairs match byte-for-byte and retain31 exact source bindings.
PooleSupervisor:936 code bytes,5248 ELF bytes, one RX page, no imports/final relocations.
Code SHA256: `5ACB48AFECE3B30B9C65BEF60BAF85DC146528F3EDC2397571D435959D86C137`.
ELF SHA256: `04D7AABC9276D6E7EB918473982C71B79B1014F4453E2D3E58DB0424B62E3738`.

## Final Native Evidence

Three fresh120-second-bounded PLAUNCH1 guests pass on the final208-page layout.
Both normal boots start/retire two lifetimes, return52 pages/scrub24 data pages,
and leave zero objects. Each records152 dispatches/304 root writes, supervisor
770 calls/exit0, child514 calls and survivor8193 calls, including123 survivor
dispatches after restart. Reused physical roots acquire distinct generations and
process handles. The denied-owner guest starts no child, cancels the prepared
image, supervisor-exits170 after2 calls, and preserves all8193 survivor calls.
It returns39 pages/scrubs18; no child execution is misreported as retirement.
Hostile marker cases rejected:83/83/64. Independent normal kernel builds match.

Final launch canonical SHA256:
`4ED976352746C8B85A91874CC0C42E6B217D2ACA40D47759D320AD20BDDA1E7B`.
Final linked SHA256:
`E910E7757C95BC863761273804F3BABB1C6B2B0090C8A30492671F879604AE48`.
Capture338.234s; log `0F2E695FF00EE8DEBEE15BD40F45D821D5FB20DB7FCC6F272453249A378D1A18`.

All27 default regression checks pass:1794 overlapping Rust executions and125
Python oracle tests, two containment boots and unsigned denial. Default host491,
IPC77, console505 per debug/release profile. Capture404.907s, log
`B7CC1A1AA360C8CF2F3FF509DE3B3C40AB5BCA677E02FA8CC5A6706579559383`.
Two fresh PPROC1 guests retain suspended/waiting-target stop and independent
survival, capture92.453s. Three fresh six-process guests retain console echo/close
and worker-failure isolation using this cycle's rebuilt program inputs,
capture74.562s. Their unchanged harness revision fields267/266 are not acquisition
dates: acquisition is268. Total final-layout guests11. No full canonical pass.

Public aggregate: `runs/native-process-launch-readiness.json`.
SHA256: `30F80AC83597B1AB1037B5ABE03AFEE56F90A97C484B3197E81BB5C01F9BB660`.
Bindings:845 launch,845 stop,852 capacity,845 default,31 program inputs.
All captures preserve source and owner-report guards. Earlier receipts stay immutable.

## Repaired Failures And Capacity

Preserved failures: an initial test incorrectly required Scheduler Eq/Debug;
storage preflight rejected less than512MiB free; supervisor linking exposed GOT
and panic-data dependencies, repaired with inlining/checked arithmetic; the first
default regression passed26 checks but could not link its final live profile.
Default text exceeded0xA5000 by782 bytes. Three successful207-page launch guests
are retained as superseded evidence, not final-layout qualification.

Review rejected stealing a RELRO page: the old default had only800 padding bytes.
The repaired linker moves text end to0xA6000, RELRO end/data to0xB8000, and image
end to0xD0000. Image208 pages uses the existing208-page reservation;36-page guarded
stack and W^X segmentation remain. Default RELRO padding is now152 bytes. Capacity
and profile review is required before further expansion, not automatic enlargement.
Default canonical SHA256:
`AE2433AD66346DBCA0C5E40640F2F6F59FE0F321054B36222733AFFF81C22D6B`.
Launch IPC static owner19592 bytes. Caller stack prologue0x8000+0x18; launch
0x8000+0x438 plus saved registers. These measurements are not a full stack proof.
Six simultaneous images still consume30 PMM records plus firmware against32 total.

45 additional scoped hash-verified archives preserve generated compiler/media
outputs, including five older failed compiler directories;163 archives total
across preservation cycles264-268. Canonical ELFs, raw logs, receipts and sources
remain local. General space reservation and restore qualification remain open.
Master checklist, PooleGlyph Phase65 checkpoint and owner conformance hashes remain
unchanged; Phase66 Core IR audit still gates native parser promotion.

## Metadata Closeout

All234 metadata checks pass in53.046s (54.141s capture), log SHA256
`AA6754EE1D798837D00E8A03A0DF22F9D3349FEC890E3BB355755F8DAA952305`.
All170 conservation checks pass in9.934s (11.437s capture), log SHA256
`18E4817A5CBDF8A422A517CB718990A1FDDA228FF486446A985076850E2DE329`.
Both captures preserve source and owner-report guards. These overlapping focused
checks are pre-closeout evidence, not final-commit or full canonical qualification.

## Next Move And Claim Boundary

Resolve image/profile capacity before kernel growth, then integrate bounded launch,
stop and console services into the real shell path. Preserve truthful exit results,
retained cleanup retry, prepared-task cancellation and owner-death race coverage.
Build USI-4 interactive shell, bundled read-only files and two useful applications;
USI-5 packages and tests that actual session from optical ISO. Efficient idle,
executable trust/loading and broader service supervision remain explicit gaps.

No phase/flag closes:40 phases301 subphases8996 requirements59 additions98 flags43
open20 gap groups.1389 discovered Python tests and629 architecture bindings are
inventory, not full-suite execution. Three known load/transfer readiness tests
and the exact-candidate canonical gates still block main. No ISO, release, signing,
physical-media/hardware action or production promotion. Full N0-N39 microkernel,
PooleGlyph/PDC and accessible PooleGlass remain required after the usable ISO.
