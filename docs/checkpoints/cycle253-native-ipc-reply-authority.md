# Cycle253 Native Sender And Reply Authority

Result: PROGRESS toward the usable native user-space ISO, followed by the complete
robust N0-N39 microkernel, PooleGlyph/PDC and PooleGlass. No interactive ISO yet.

## Implementation

Kernel-stamped sender TaskId at enqueue; bounded metadata receive and task-local
typed generational one-use replies. Calls6/7/8/9 request, receive metadata, reply
and discard. Return routes bind requester/root/root-generation, owned RECEIVE
handle/object and original request object. Successful copy-out mints authority;
successful snapshot/enqueue consumes it. Input/output faults, short buffers,
full queues and reply-slot exhaustion preserve ownership and queued data.
Close/destroy/detach prune invalid tokens without resetting generations. Reply
tokens cannot grant permanent SEND permission. Explicit discard recovers capacity.

Thirteen new host tests exercise spoofed callers, types/rights/ownership, replay,
all64 input-fault offsets for request and reply, all96 envelope-output offsets,
short output, legacy request-receive denial, full mailboxes, reply quota, discard,
generation exhaustion, dead requester/server, revocation and syscall argument bounds.

PKIPC3 adds a sixth lifetime to the same two persistent native slots. The client
has a reply endpoint and a SEND grant; the server has only its request endpoint,
not a permanent SEND grant to the client. Actual CPL3 syscalls prove identities,
two requests,8-byte partial-copy retry, unminted-token denial, wrong-type denial,
input-fault retry, one successful transformed reply, replay denial and generation2
token discard/replay denial. Caller-owned mailbox wait/wake continues to work.

## Verification

Final native capture: outputs/cycle253-nativesecond.json/.log;15 checks PASS,
317.046s.416 debug kernel tests,130 user-entry release,30 IPC release,24 VM release,
8 compile-fail and10 boot-exit:618 Rust executions.48 Python oracle tests;
two incompatible development feature combinations reject.

Two fresh68-marker QEMU/OVMF boots,835 altered-evidence rejections each. All17 older
containment cases, original3-wait/2-wake/1-cancel exchange and five pressure/death
lifetimes pass. Ordinary unsigned boot still denies execution. Media read-only,
fresh firmware variables, no guest network, host acceleration or filesystem share.
All769 native/oracle source bindings and captured sources unchanged; owner report
unchanged. No source edits during bounded captures.

Each new native round: task generation6;3 dispatches,0 preemptions,1 wait/1 wake,
calls[8,11], measured ticks[1533,2294],6 root writes. Clients exit95, servers94;
26 pages released/12 data pages scrubbed. Whole probe391 root writes,
772 released/355 scrubbed pages. Measured subtotal143832590 ticks; one older
unmeasured dispatch remains unknown. This is not complete global accounting.

Kernel705752 canonical bytes,191 pages, entry0xC000, unchanged36-page guarded stack.
Canonical SHA256: `ACCF2218076DAEBA43604F0AE9E6DA15FCFB78DD6ADF10D2138985272557CAE7`.
Linked SHA256: `0BDD9F65A86078923054B80136FCD3DA45E78BEB217D679D0ABFF789C55CFAE7`.
Receipt `runs/native-user-entry-readiness.json` SHA256:
`3C3125DE00C104025DFE2BC19B1FE0013B26988FD7730DA497A741F0EA30BC31`.
Capture log SHA256: `80B2E37841BC3EBF0D0A6D1352F569F29DE67329E8D2BCE5120335B5E1161B8D`.

## Failure History

Initial format-helper invocation omitted PYTHONPATH and failed importing tools;
no source change occurred. Corrected its environment before qualification.
Preflight host capture passed416 tests,21.109s:
`FCE4D2B1EBC7459712BEFFCF2FCC0B1B59FBBB8AEB309E6F620FCB44F12F84DA`.

First native attempt:14 checks passed; linker rejected text0x98C3E beyond0x97000
and BSS0xBC198 beyond0xBC000.75.265s; retained log SHA256:
`13A7A0B9E8BFAB516EC678353135C4ABB8FAD9010C438C548667E76CA3342FBE`.
Repair: text/data0x99000, RELRO0xAA000, image0xBF000 within the unchanged192-page
bootstrap cap. Entry and stack unchanged. Final attempt passed. Only one page of
image capacity remains; further growth needs explicit layout/capacity qualification,
not deletion of prior controls. Guest120s/ordinary45s/live360s/outer900s unchanged.

## Continuity And Next Work

Cycle252 receipt frozen byte-for-byte in tests/fixtures/cycle252-user-entry-readiness.json:
`DF8F0D515B1DB8817F65F3159B76FAC33C0A73568A92BCEFF7EFB82C210D79F9`.
PooleGlyph Phase65 checkpoint/manifest reread; Phase66 Core IR boundary audit next.
Owner report SHA256: `F75E4836FAA9DDD59BA62648FE9542415F2119B659A583FB3F5959F2F5CAE87B`.
Master checklist SHA256: `A8C94719FAF9428C1F133010BA2603C0270C4E1EFD7327AF8EAB9C8C362ABB3D`.
Main remains507782d, qualified through233; later branch work is not main-qualified.

Next N13-CAPABILITY-IPC-001: request/deadline/cancellation ownership and dead-service
notification, then transactional bootstrap/admission and sustained service budgets.
Then init, confined console/input, shell/files/two actual user programs and optical
ISO acceptance. Full microkernel, PooleGlyph/PDC and PooleGlass work continues.

Not synchronous Call, per-request correlation, donation, reserved reply capacity,
guaranteed delivery or caller wake on reply discard/service death. Sender metadata
describes enqueue identity, not current liveness or ambient authority. Native
replies do not prove all host revocation/quota cases or arbitrary races/SMP. Fixed
four tasks/64 lifetime calls and halt-on-bootstrap-error remain development limits.

No phase/flag closes:40 phases,301 subphases,8996 requirements,59 additions,
97 flags/42 open,20 gaps. USI-1/2 partial;3-5 not started.191-page product-contract
migration and full exact-candidate canonical replay remain before main merge.
No signing, release, production promotion, firmware or physical-media operation.
Final metadata/conservation/publication checks follow this native recording.

## Metadata Closeout

149 checklist/architecture/roadmap/oracle tests PASS in51.861s (52.734s capture),
with source and owner report unchanged. Log SHA256:
`7B1ACC47581F01FE71B11C671D9989E415D9B8F5AFE886CB8EF61D19D20539D1`.
Architecture binds510 paths. Python inventory1304 means discovery, not a full
suite pass. Regeneration and final conservation/staged-byte/publication checks
follow this recording; no native or oracle source changes after qualification.
