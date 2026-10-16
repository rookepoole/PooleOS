# Cycle269: Kernel Capacity And Entry Stack

2026-10-11. Previous goal turn: progress, Cycle268 commit0a27cdf.
Owner priority remains usable native user-space integration ISO first, followed
by the complete robust microkernel. No shell, new useful application or ISO was
added in this prerequisite checkpoint.

## Implementation

[PKBUDGET1](../native-kernel-budget.md) replaces fixed text/RELRO/BSS ends with
page-aligned actual use and audits12 linker markers in every shared product build.
The fixed0xD000 entry,208-page reservation,36-page guarded stack, W^X, compiler
profile, overflow checks and ordinary unsigned denial are preserved.

The entry function no longer reserves diagnostic-only local storage when entering
user space. A non-inlined diagnostic function preserves the existing diagnostic
body without adding unsafe code. Default entry local frame drops from29656 to840
bytes;48 saved-register bytes and all callees remain separate. This is not proof
of the maximum kernel/interrupt call chain.

| Final Profile | Image Pages | Remaining Of208 |
| --- | --- | --- |
| Default diagnostics/containment | 207 | 1 |
| User supervisor launch/restart | 110 | 98 |
| Denied launch authority | 109 | 99 |
| Process stop | 184 | 24 |
| Six-process console and bad worker | 113 | 95 |

Default RO padding2512 bytes, text padding1538, RELRO padding152, BSS padding1640.
Launch RO padding19512 bytes; six-process RO padding12664. These are individual
layout margins, not blanket permission to grow another region. Existing fixed
layouts made every profile208 pages. Per-build measurement now exposes actual use.

## Evidence

All28 default checks pass:1794 overlapping Rust executions and133 Python oracle
tests, including8 new budget tests. Thirteen final-candidate guests pass: two
containment plus ordinary denial, three launch/restart/invalid-authority, two stop,
three six-process console/bad-worker, and two physical-memory diagnostics.
Independent launch, stop and capacity kernel pairs match byte-for-byte. The six
retained Cycle268 user ELF/code pairs and31 source bindings were reverified,
not rebuilt. All source and owner-report guards pass.

Default canonical SHA256:
`A0A7A958E3877DC82381A1586D3AFFA5D6DF8BC465B17E95D1AA16CC9382E170`.
Launch canonical SHA256:
`7EB43AB2C0C6385EB54B1F2268367B05BB88D9B00A659D2857EA0FC5F73275D2`.
Aggregate `runs/native-kernel-budget-readiness.json`, SHA256:
`F157C18FD979702BA86EC030ADAF9B54DDC120FC3926634BE3E28E8EF082940C`.
Bindings847 default/launch/stop/PMM and854 capacity. Embedded harness revision
fields268/267/266/261 are historical implementation revisions; capture cycle269
is recorded separately. Fresh run bounds remain150s containment,120s lifecycle/
console,45s denial and180s PMM. No time limit was raised after a failure.

| Capture | Seconds | Log SHA256 |
| --- | --- | --- |
| Default repaired | 400.250 | `3934DE8A81E0C1BA832140C3052857BF4311081B831856AAB896DA493E04FEC6` |
| Launch | 339.000 | `0F2E695FF00EE8DEBEE15BD40F45D821D5FB20DB7FCC6F272453249A378D1A18` |
| Stop | 92.453 | `6BD98209172214D9DAAC66D2C85DA89A2411F70DD2B06D52B3A09334F3BEBC9C` |
| Capacity | 75.266 | `CC5725100BDFD18BDCABF52449E6D734298A60903FA0F78021538A9D9457CEC6` |
| PMM diagnostics | 22.313 | `3EF5BA353802207095CB0FBADB1F5F609305677827C374EDCF11F69553AAF54A` |

## Rejected Experiments

Marker-only and adaptive-layout controls under the original compiler settings
reproduce the previous default canonical image exactly. Adaptive padding alone
cannot shrink that already-tight default. A kernel-only `z` compiler experiment
first failed fixed RELRO placement. Adaptive layout yielded202 pages, but its
native boot faulted on the lower stack guard in PMM construction before user entry.
The entry/user-root/PMM local frames alone were71592/46872/30392 bytes against a
147456-byte stack. #PF vector14/error2, RIP FFFFFFFF800788D2 and CR2 FFFFFFFF800D09C8
are retained, along with the failed capture and disassembly. No guard was enlarged.

Separating diagnostics produces a202-page static `z` candidate, but that candidate
was not natively qualified or selected. Existing `s` plus the structural repair
produces the final207-page default and compact integration profiles. Failure
history remains explicit; smaller bytes are not evidence of native correctness.

## Metadata Closeout

The corrected243 metadata checks pass in53.277s (54.329s capture), log
`CB04D82FB8EBF36A70035E6F8DED02C56F8A641E05257D2385FAA1054626CB68`.
All179 conservation checks pass in10.149s (11.657s capture), log
`28772727A558084BAAAC7756C79C2BC13A3E7E74F4CE594D95E4C2DEE57CDB8E`.
Both captures preserve source/owner guards. These overlapping focused checks
precede closeout serialization and are not a final-commit or canonical suite pass.

## Progress And Next Move

Metadata initially failed13/243 checks: a leftover trailing LF in the workspace
Cargo manifest invalidated older policy/symbol bindings, and two architecture
inventory checks still expected629 instead of634. Restoring the exact Cycle268
manifest removes that accidental change. Six current-source linked/canonical
kernel profiles and three bootloader profiles then rebuild byte-for-byte equal
to the tested archives. Ten reconstructed guest media inputs also compare equal.
No new guest runs are claimed for this exact-byte identity check. Only this one
LF difference is bridged; every other native source binding must still match.
No product admission check is relaxed and all original capture records remain.
Identity capture102.875s, log
`ADD6835A9A5D53137FBE6EA518C9904E6C04FBE0639B8B653C636972076EA406`;
media capture2.094s, log
`7FB246A2B5E87CF70EC8832992A1A39BFF39F969421D953061716F640436BC2E`.

46 additional hash-verified compiler/media archives bring preservation cycles
264-269 to209 archives. Two extracted diagnostic ELF duplicates were removed only
after comparison with their already-preserved archive members. Raw captures,
canonical images and manifests remain; general storage reservation/restore is open.
Master checklist and PooleGlyph Phase65/owner report are unchanged; Phase66 remains
required. Inventory1398 Python tests and634 architecture bindings is not a full run.

Integrate the actual user-space shell with existing console and generation-bound
launch/stop. Preserve truthful completion, retained cleanup ownership and native
owner-death/failure controls. Then bundled read-only files/two useful applications,
optical packaging and interactive/sustained-session ISO acceptance. Per-profile
budgets now support that lane; default image growth, code pages,32 PMM records,
full stack bounds, general supervision, executable trust/loading and efficient
idle remain explicit gaps. Replaying every other diagnostic profile and the three
known load/transfer readiness tests remains necessary for canonical qualification.

No production phase/flag closes:40 phases301 subphases8996 requirements59 additions,
98 flags43 open20 gap groups. No merge to main, release, signing, physical-media or
hardware action, or production promotion. Complete N0-N39, PooleGlyph/PDC and
accessible PooleGlass remain required after the usable ISO.
