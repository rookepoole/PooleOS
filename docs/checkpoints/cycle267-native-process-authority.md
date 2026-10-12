# Cycle267: Native Process Stop Authority

2026-10-11. Previous goal turn: progress, Cycle266 commit8818417.
Owner priority remains usable native user-space integration ISO first, then the
complete robust microkernel. This is USI-3 kernel mechanism progress, not another
boot-screen redesign and not an assertion that a usable ISO exists.

## Implementation

[PPROC1](../native-process-authority.md) adds four global process leases, two per
owner, without changing IPC quotas. Trusted grants bind full owner/target task and
root generations and Inspect or InspectTerminate rights. PSABI1 calls17/18 reject
extra arguments and resolve only against an authenticated owned caller.

Stop requests are bounded and idempotent. The quiescent dispatcher claims once,
revalidates authority after current-slice accounting and root restoration, then
uses existing owned task cancellation/retirement. Revocation, owner death and target
reuse invalidate authority. A dropped claim stays retained rather than reissued.
Attachment inspection is deliberately not a claim of runnable state or freed memory.

Native qualification uses actual CPL3 assembly test programs in three private
images: controller, target and survivor. These are mechanism diagnostics, not the
future separately compiled supervisor or useful applications. No user-program
source changed. Existing five independent ELF/code pairs were reverified, not rebuilt.

## Executed Evidence

Two fresh120-second-bounded guests each pass two sequential lifetimes. Round1
stops a timer-suspended target; round2 stops an IPC waiter. Each round observes:

- 20 dispatches, controller66 syscalls/exit104, survivor1025 syscalls/exit100.
- 17 survivor dispatches after target stop and1024 checked self-memory copies.
- Forged-generation and insufficient-rights denial from CPL3; invalidated permit
after retirement; three distinct roots, with reused physical roots bound to new IDs.
- 41 actual CR3 writes:40 dispatch writes plus one mandatory retirement flush.
- 39 task pages returned and18 data pages scrubbed;78/36 across both rounds.

Both guests reject87 hostile observation mutations. Two independent kernel builds
match byte-for-byte. Canonical773192-byte kernel:
`78AD22AE4590810664B3513BBDE03D4989A28358D0920BF605E1D955557BF18F`.
Linked kernel:
`D5241F1D800A53AD25D4EF44D1811D9D2F4C7CD8BE3D96ACD490B8FFF383AD1C`.
Native capture93.078s, log
`6BD98209172214D9DAAC66D2C85DA89A2411F70DD2B06D52B3A09334F3BEBC9C`.

All26 default regression checks pass in405.235s:1762 Rust test executions and120
Python oracle tests, including two complete containment guests and unsigned denial.
Default host483, console debug/release497 each; counts overlap. Eight new kernel
tests and four parser tests cover the new surface. Each default guest retains all
existing17 peer-survival cases and reclaims1032 pages/scrubs475 data pages.
Regression log:
`B99CC40E9EED415C5C3AC178AFA2E60A9346D86CA6C1665FA3578545FB9C725B`.

Three fresh six-process guests pass real console echo/close and independent worker
failure, capture78.031s, log
`CC5725100BDFD18BDCABF52449E6D734298A60903FA0F78021538A9D9457CEC6`.
The unchanged capacity harness's revision field remains266; acquisition is267 and
is bound by current sources and capture. Four-process-only evidence remains historical.
Total fresh final guests:8. No full canonical-suite or main-merge qualification.

Public aggregate: `runs/native-process-authority-readiness.json`.
SHA256: `A66ADACCEFB84AD5085DCD76F0789A954C3151667BFDAE8F054287348690E8E0`.
Source bindings:837 process,844 capacity,837 default, plus29 unchanged program inputs.
Raw logs, images, capture guards and failures remain under explicit Cycle267 paths.

## Failures And Limits

Preserved failures: initial parser fixture used an obsolete boot layout; first
native compile exposed module visibility/unreachable-code errors; two subsequent
guests exposed the new harness's missing mandatory retirement-flush count. Failure
diagnostics showed all three tasks dead, pages restored,20 dispatches and41 writes.
The existing retirement implementation already required this flush and was not
weakened. The next guest completed both rounds but the LF-only completion detector
missed actual CRLF and timed out. Exact CRLF detection and unit expectation were
repaired, then two fresh guests qualified under the original120-second bound.

Image207/208 pages and36-page guarded stack remain unchanged. Process profile IPC
owner19480 bytes, console profile19520, a256-byte increase in matching profiles.
Disassembly records process-run stack allocation0x7000+0x648, round0xB48 and caller
0x8000+0x18, plus saved registers. This is not a maximum call-chain stack proof.
Six images still use30 PMM records plus firmware against32; eight images are not qualified.

31 new hash-verified scoped archives preserve generated objects/media, including
failures;118 total across264-267. Source/checkpoints and canonical ELFs/raw logs
remain local. Full evidence-space reservation and restore qualification stay open.
PooleGlyph's latest checkpoint remains Phase65, next Phase66 Core IR boundary audit;
checkpoint, owner conformance report and master checklist hashes are unchanged.

## Metadata Closeout

The first metadata capture retained two failures out of 228 tests because the
roadmap schema still pinned cycle266. Updating that exact version constraint to
267 repaired the mismatch. The second capture passed all 228 tests in 52.304s
(53.343s capture), log SHA256
`3A9D7666CBAFEC8CB9F134CFB2EC4C9968B307698ED9275CDC699B902FB4B364`.
All 164 conservation checks passed in 9.806s (11.297s capture), log SHA256
`62FCE9F980C73F16B3B00264488D7F2669CD8D09111C12326994F60F0F86CFA1`.
Both captures retained unchanged source and owner-report guards. These overlapping
focused checks are not the full canonical gate or final-commit qualification.

## Next Move

Add bounded generation-safe start/restart authority, atomic child/handle admission,
truthful completion/retry ownership, and real user-space supervisor policy. Native
prepared-task stop and owner-death/cleanup races need their own evidence. Keep
code-page capacity, PMM records, image headroom and full stack bounds under review
before expanding programs. Then USI-4 interactive shell, read-only bundled files,
two useful applications and fault survival; USI-5 boots that actual session from ISO.

No production phase/flag closes:40 phases301 subphases8996 requirements59 additions,
98 flags43 open20 gap groups.1383 Python tests and618 architecture bindings are
inventory, not a full-suite pass. Three known load/transfer readiness tests and
exact-candidate canonical gates still block main. No ISO, release, signing,
physical hardware/media action or production promotion. Full N0-N39 microkernel,
PooleGlyph/PDC and accessible PooleGlass remain required after the usable ISO.
