# Cycle270: Native Command Shell

Date: 2026-10-11. USI-4 starts; no phase or implementation flag closes.
The immediate owner priority remains a usable user-space integration ISO,
followed by the complete robust native microkernel, PooleGlyph/PDC and PooleGlass.

## Delivered

PooleShell now runs as a separate CPL3 process over the existing confined console
service. It executes `help`, `version`, `echo TEXT`, `exit`, bounded editing,
interrupt and empty-line EOF. Invalid and overlong lines never execute a truncated
prefix. The kernel does not parse commands. No kernel implementation changed.

Seven user programs reproduce byte-for-byte in independent builds. All58 host
runtime tests pass debug/release, including14 shell tests. The six prior binaries
remain byte-identical to Cycle268. Shell code3569 bytes; ELF7880 bytes:

- Code SHA256: `AD2B9AD6DE7E96E5AA018C4A127D0F9AAC4A446BC1276F357FDE3BD6BA6EA67E`.
- ELF SHA256: `C548313524AC78017239CBCCA22F99390EAE40B77F09F5935EC8755F580D9B0E`.
- Published evidence: `runs/native-shell-readiness.json`.
- Evidence SHA256: `913AC77D04DE70F625377DF8E6093616FF6239F232D556C0D9C27DBC6944EF55`.

The receipt binds860 native/build/oracle inputs and34 user-program inputs. Those
counts are inventories, not independent passing tests. Build provenance is pinned
conventional Rust compilation, not freehand binary or PooleGlyph compilation.

## Native Results

Three fresh QEMU/OVMF guests pass under a frozen120-second per-guest bound:

1. Commands: fresh16-hex-character echo challenge, help/version, forged diagnostic
   text as untrusted application output, unknown command, invalid exit prefix,
   blank line and real exit. Thirteen64-dispatch samples,832 dispatches total.
2. Editing: independent challenge, backspace/delete, CRLF normalization,64-byte
   accepted line,65th-byte rejection that persists through backspace, Ctrl-C reset,
   nonempty EOF ignored and empty EOF close. Twenty-two samples,1408 dispatches.
3. Denied peer: console exits152 and shell consumes revocation/exits163, with no
   application output. Eight samples,512 dispatches; independent pair survives.

Both normal sessions retire console/shell with exit0 and return26 image pages.
Kernel marker accounting and private roots are validated independently of COM2.
The surviving init/counter pair continues; retired processes never resume. This
does not prove general service restart, application fault recovery, or a usable ISO.
All shell kernel profiles use113/208 image pages;36-page guarded stack unchanged.
Two normal linked/canonical kernels reproduce exactly. Fresh bootloader builds,
media/transcript binding and hostile marker controls also pass.

Independent post-build verification rechecks the seven ELF/code pairs, relocation
definitions, kernel budgets, literal input/output and all guest marker oracles.
Its71 focused Python tests pass. Capture log SHA256:
`12F7B34B650D0745BDA777AC4D7543F4FE3FD60D47060FB53243DB6B829BFFAE`.
Native capture79.422s, log SHA256:
`313BCAD767A623C7A7B257C549DA21F0BA160B24091FAEF5C14C57D7199A224B`.

## Preserved Failures And Repairs

Six rejected build receipts and unchanged-source logs remain preserved. Initial
inlining introduced forbidden panic/cross-crate relocations and exceeded one
code page. Checked accesses removed panic dependencies; shared request assembly
alone still exceeded the cap. A non-inlined bounded poll produced3569 bytes.
The extractor then rejected LLD's SHF_MERGE metadata. Exact flags6/22 acceptance
was added with permission/metadata negative tests; RX, single-page, zero-data and
relocation requirements were not relaxed. The old symbol-prefix audit then
rejected local `.Lanon` constants. Actual defined-local/read-only symbol validation
replaced that naming assumption, with hostile tests. No failed build was executed.
A rejected wrapper invocation used a hyphenated capture tag; an alphanumeric tag
was used for the real bounded capture. It did not build or execute anything.

The first251-test metadata replay retained two failures: an old Cycle268 test
still compared historical program-source hashes to current source, and the new
historical Cycle269 assertion confused847 identity bindings with854 capacity
bindings. Historical artifacts remain frozen by their full published hashes;
tests now distinguish their old source bindings from the current shell receipt
and compare the six unchanged executable identities across both records. These
were evidence-test defects, not native shell failures. Initial log SHA256:
`5E9DF16D95D345ED1F25B5A3F83EC16FA33E873EF76F08EAFF6665E65F4B2DF0`.

Repaired metadata251/251 passes in52.967s (capture54.031s), log:
`2DA0859A55540D35DB476DAD473DF83FCB2E5EDA51CF617A60B376D6E1E2117C`.
Conservation187/187 passes in10.125s (capture11.625s), log:
`A90C2EDFA3B5A147AB9524452BB7BF0B163A38CF1D5A87F52A1CEDC374EFA5C5`.
These suites overlap; they are not a full canonical replay or final-commit claim.

Thirty-seven fresh archives preserve generated evidence on the existing dedicated
evidence volume:22 current compiler/media paths, six prior layout experiments and
nine older failed compiler directories. All members were hash-verified before
scoped removal of generated originals. Current receipts, raw guest observations,
canonical kernels and both copies of all seven user ELFs/code remain local.
No owner `.tmp` material was removed. Full automated restore/reservation remains
open; the512MiB build preflight was not lowered.

## Scope And Next Move

USI-4 is partial: a serial command shell, not files/apps/desktop/ISO. Builtins do
not count as the two useful separate applications. The shell still occupies the
existing console-client bootstrap role; it does not yet hold process-launch or
process-control capabilities. Next integrate truthful start/stop/status and
completion/cleanup with the user-space supervisor, add read-only bundled-file
service and two useful apps, then corrected optical media and sustained acceptance.

Retain generation checks, no authority through raw task IDs, failed-cleanup
ownership, owner-death controls, full stack bounds, code-page/PMM-record budgets,
efficient idle, executable trust and robust service supervision as explicit gaps.
The one-page executable limit will need reviewed multipage admission for growth;
do not silently enlarge it or remove checks to fit applications.

Cycle269 default/kernel regressions remain historical, not freshly replayed in
this user-only increment. Full canonical qualification and the three tracked
load/transfer readiness failures still block main-merge qualification. No new
ISO, tag, release, signing, physical-media operation or production promotion.

Owner master checklist and PooleGlyph Phase65 ZIP/conformance hashes are unchanged.
The six newest live checkpoint files still end at Phase65; Phase66 CoreIR audit
remains next. Counts remain40 phases301 subphases8996 requirements59 additions98
flags43 open20 gap groups. Current Python test and architecture-source inventories
are recorded in the regenerated roadmap, not claimed as full-suite execution.
