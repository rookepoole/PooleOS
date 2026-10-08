# Cycle257: Atomic Task Admission

2026-10-08. Result: PROGRESS; not production or interactive-ISO acceptance.
Selected move N13-CAPABILITY-IPC-001; USI-1/2 partial, USI-3/4/5 not started.
Owner direction remains usable original-native user-space ISO first, then the
complete robust PooleKernel microkernel. No Linux or kernel-shell substitution.

## Implementation

[PKADMIT1 contract](../native-task-admission.md) joins bounded IPC authority setup
and scheduler publication. One to four caller-owned prepared images and up to
sixteen endpoint/inheritance/export steps are validated under exclusive BSP/IF0.
Only a fully installed plan publishes the candidate scheduler. Failure removes
only newly attached members and newly created endpoints; existing source grants,
queued work, unrelated scheduler state and the owned clock lease remain intact.
Generation high-water marks never rewind. Raw identities/admissions are trusted
supervisor declarations, not user authority or transferable prepared-image owners.

Eight host tests exercise plan prefixes, malformed plans/rights, quota failures,
partial attach, source preservation, exported-capability revocation, generation
exhaustion and unrelated scheduler/clock state. Existing native exchange and
pressure bootstraps now use joint admission. Not every diagnostic bootstrap has
been migrated and general service startup remains unfinished.

The native exercise prepares generations13, deliberately exhausts endpoint quota
after four successful steps, verifies zero dispatches and an unchanged scheduler,
and denies same-generation retry. A memory-finish failure quarantines cleanup,
all five raw allocation frees reject, and explicit cleanup retry reclaims ownership.
Generation14 then admits two isolated timer-preempted tasks, exits42 and reclaims
all pages. The live receipt, not these intended checks, establishes execution.

## Qualification

Final receipt runs/native-user-entry-readiness.json:
BA8701DCAD3D4327692EF75C32FAF13549C81ED559F79E9BAC4C852B23EEA775.
787 source bindings; source and owner-report snapshots unchanged during capture.
All18 checks pass:451 debug kernel,138 optimized user-entry,57 optimized IPC,
24 VM,9 compile-fail,10 boot-exit and15 mapping tests total704 Rust executions,
not704 distinct tests.78 Python oracle tests and two incompatible-build rejections
also pass. Two fresh read-only software-emulated QEMU/OVMF boots each produce77
markers and reject1059 altered-evidence controls; ordinary unsigned denial passes.
Guest networking and host acceleration are disabled.

Each admission case records zero failed-start dispatches, one cleanup quarantine,
five retained-free denials, one cleanup retry,6 fresh dispatches/4 preemptions,
12 CR3 writes, two Exit42 outcomes,52 released/24 scrubbed pages, and2400239
runtime ticks per fresh task. Whole probe:447 CR3 writes,980 released/451 scrubbed
pages and one retained ACPI page. All earlier17 peer-containment cases remain.
These are emulated observations, not physical hardware benchmarks.

Canonical kernel747016 bytes/201 pages, SHA-256
6E5C871EB93951E902B122B01B5D9003309DE29B00F9DADA006B6DC51FDB715B.
Final nativefifth capture:378.484s, return0; log SHA-256
D32CF03F1A8EBD9A4E7016DB4B12543457F21E0D0C07737C205880A5CD370090.
Bounds unchanged:150s per guest,420s live child,900s outer capture.

## Failed Attempts And Repairs

- hostfirst,5.547s: missing std::vec macro import in no_std tests. Fixed import.
  Log52485293300CE7CDE28644E26080B07B1A243207A157CBD8712D346E0637E1B3.
- hostsecond,20.844s:451 debug tests pass; intermediate evidence only.
  Log5386611D243FB31D660AC11D4EF5A4CD28E042BD6E80002661C28AC2DE87266F.
- nativefirst,39.625s: freestanding adapter missed three TableMemory counter
  forwarders and a scheduler argument in pressure bootstrap; repaired both.
  Log85CDEEF567B775B319852C11E25E504800867E175DBED811ED58A09ED99FE224.
- nativesecond,64.297s:17 preboot checks passed, linker rejected RO0xC080 beyond
  0xC000 and text0x9F9EE beyond0x9E000. Reviewed layout grows to201 image pages:
  entry/text0xD000, data0xA1000, RELRO0xB3000, end0xC9000; capacity remains208.
  Log44D13637D6A87D24AFAF99FB8EFAB7D6657BF6C03B277FC497CED4A472757E4C.
- nativethird,21.094s: entry-offset guard caught stale runtime0xC000. Updated
  runtime to0xD000 without weakening the guard.450 tests passed/one failed.
  Log02C1D2D35C9A0DEE686AB5D37E77FED6D5E66196209388C7AF9E4A210FC867CE.
- nativefourth,210.656s:17 preboot checks and prior deadline markers passed,
  then a kernel stack probe hit the guard at RSP/CR2=0xFFFFFFFF800D09A8,
  RIP=0xFFFFFFFF8007EF11 in PhysicalMemoryManager::direct_map_manifest.
  Disassembly identified the added admission frame beneath image preparation.
  Moved preparation into the existing outer persistent-slot driver and split
  rollback/execution checks. The36-page guarded stack was not enlarged.
  Log34B6E20F0FFDFCA34F8DEE375F9BFBAA96EAE69447C3CE57947C7F972523E4E8.

An overbroad read-only tool search encountered old inaccessible evidence folders;
it was stopped and replaced with a scoped pinned-toolchain search. One formatting
invocation omitted PYTHONPATH and was corrected. Neither changed source or policy.
All capture failures retain exact logs under ignored outputs/cycle257-*.

## Limits And Next Move

Next: sustained service budgets instead of fixed lifetime syscall limits, owned
service-image/argument bootstrap and interrupt-driven idle. Then init/confined
console/input, interactive shell, bundled read-only files, two real user apps,
and optical ISO interaction, sustained-session and fault-containment acceptance.

Admission is exclusive-BSP only, not a user spawn syscall or signed loader.
Cleanup retry is a bounded injected case, not general supervisor recovery at
every scrub/free boundary. Idle still polls HPET; unexpected native clock faults
still halt with ownership retained. CPU-runtime samples are not wall-clock time.
One unmeasured dispatch remains unknown, not zero or an invented runtime total.

The qualification workload must be separated from future normal demo startup.
201/208 image pages leaves7 pages: flag diagnostic/profile separation or reviewed
capacity migration before exhaustion, without silently removing required checks.
The three product-readiness failures remain:
- tests.test_native_kernel_load.NativeKernelLoadTests.test_contract_and_readiness_pass_semantic_validation
- tests.test_native_kernel_load.NativeKernelLoadTests.test_readiness_detects_stale_input_and_oracle_divergence
- tests.test_native_kernel_transfer.NativeKernelTransferTests.test_contract_and_generated_readiness_are_current

Migrate product contracts and replay the full exact-candidate canonical suite
before main. Focused results are not full-suite, merge, release or production
approval. No ISO, key, signature, tag, release, firmware or physical-media action.
Full microkernel, PooleGlyph/PDC and accessible PooleGlass obligations remain.

## Conservation

Cycle256 receipt frozen byte-exact at tests/fixtures/cycle256-user-entry-readiness.json:
D0E940208AC74CDA069AAFAD2FED93E3C5F1B97AF8A9E38C592C6E277D72AAA8.
Master checklist rechecked:8996 requirements across40 phases/301 subphases,
59 additions,97 flags/42 open and20 gaps. No phase/flag closure.
Checklist hash A8C94719FAF9428C1F133010BA2603C0270C4E1EFD7327AF8EAB9C8C362ABB3D.
PooleGlyph Phase65 checkpoint reread; Phase66 Core IR audit remains next. Archive
hash F3CCEB701CF76274D9464A0958BF6106888FB34F3C0BFBD55DE4ACE03C427ABC.
Owner's preexisting report is unchanged:
F75E4836FAA9DDD59BA62648FE9542415F2119B659A583FB3F5959F2F5CAE87B.
Historical execution ledger unchanged:
65155E981FA217BD9D78218A4E0C0537A574D613ED9FB3E1EBD16511B6A1EA5D.
Metadata closeout passes161 tests with zero skips,52.457s unittest/53.312s capture.
Source and owner snapshots remain unchanged. Log SHA-256
CFB9BDFB95E72807E712EA5AEA161C816F401522D36A2CEC49149C6344A44015.
Architecture inventory binds536 paths. Static retained-admission projection is
2/27 passing with four static source closures; it is not new guest execution.
Conservation passes97 tests with zero skips,8.237s unittest/9.547s capture,
source and owner snapshots unchanged. Log SHA-256
3FC0EAD5EC9CF34136223DE65DA598F091C9A4D19DD121FB5AF0FE38AE49A6C2.
Final staged-blob, native-binding, generated-artifact,1316-test discovery and
staged-path publication checks are retained separately under outputs/cycle257-*.
Discovery is not execution and none of these bounded checks is full canonical
qualification. The development branch remains unqualified for main or release.
