# Cycle 249: Unknown Runtime Recovery

Date: 2026-10-08. Result: PROGRESS, not a phase exit or production readiness.
Selected move: N13-USER-ENTRY-LIVE-001, USI-1 / N8, N12, N13.
Next move: N13-CAPABILITY-IPC-001, USI-2 groundwork. A usable native user-space
ISO remains the immediate deliverable; complete robust N0-N39 development follows.
No new interactive ISO is claimed.

## Implemented And Verified

PKUSER15 adds explicit unmeasured-dispatch recording without tick fabrication.
The current scheduler owner cannot requeue or accept new charges after that
record. Slot retirement remains contingent on device/entry/root cleanup; unknown
time does not become an application exit status. Failed cleanup is retryable with
the exact owner retained. [Mechanism and invariants](../native-user-unknown-runtime.md).

Final qualification passes14 checks in304.453s:379 debug kernel tests,124 repeated
user-release tests,24 repeated VM-release tests,8 compile-fail tests and10 boot-exit
tests, totaling545 Rust executions rather than545 distinct tests. All40 Python
oracle tests, format checks, freestanding library/adapter builds and two rejected
incompatible feature combinations pass.

Two fresh61-marker QEMU guests and an ordinary unsigned-denial boot pass. Each
guest preserves the previous16 containment cases,156 measured-suite dispatches,
30 terminal samples,156 duplicate-charge denials and HPET-backup recovery. The
separate17th case executes a real quantum, loses its returned sample, refuses
zero charging and requeueing, retains13 pages through pending-IRQ cleanup failure,
then recovers. Its peer makes six observed preemptions and exits84. This adds eight
dispatches,16 CR3 writes,26 released pages and12 scrubbed data pages. Full totals:
339 root writes,590 released pages,271 scrubbed data pages.630 altered-evidence
controls reject per guest. The failed task's total runtime remains unknown/null.

All758 native/build/oracle bindings, the full source snapshot and owner-modified
PooleGlyph report are unchanged during the final capture. Fresh firmware-variable
copies, read-only virtual media, no guest network/acceleration, serial/debugcon
equality and orderly QMP quit remain required. Bounds stay120s per user guest,
45s ordinary denial,360s live child and900s outer capture.

- Receipt: `runs/native-user-entry-readiness.json`, SHA-256 `08F3170877F13DD5A0171AFB26DCF959B1597D2AA7AC3BFCFBAAA1A774519185`.
- Kernel:667624 bytes,182 pages, entry0xC000, SHA-256 `88CE0AD89B9EEF10680FFFA453B891F88197E3845C26F6DC7F6CD99726CCC4DB`.
- Linked kernel: `DF9CB6E2A6A759D5F08AF7B99C0DFBBB3724527AAE4C5FE77D00B6C70170E053`.
- Final capture log: `2E27EC4C1413B13D419390A91A1C01D42861A3E4D61679829D489FDE982F10F5`.
- Frozen Cycle248 receipt: `tests/fixtures/cycle248-user-entry-readiness.json`, SHA-256 `1182CB4054D0882F07AD51DD96097CC5C49E4AC999D9E1621D47E547FB91CE15`.

## Failure History

1. Native attempt1 failed linking after75.047s. Text0x9196E exceeded0x91000 by2414
   bytes. Text/data moves to0x92000, RELRO to0xA2000 and image end to0xB6000, within
   the unchanged192-page cap. Entry0xC000, permissions, contiguity and stack guards
   are unchanged. Log: `DD5ED5FA1139D45046D71EE86BD2D4627699A2EDE3B4B5C53DEDE6A66E32830A`.
2. Attempt2 failed in217.172s after passing the16 measured cases. The new test
   nested another constructor under the still-live measured-suite frame. A #PF
   at kernel RIP0xFFFFFFFF800709DA wrote the low stack guard at0xFFFFFFFF800C03E8.
   Exact failed-binary disassembly identifies a stack-probe write inside
   `PhysicalMemoryManager::direct_map_manifest`. The guard correctly stopped it.
   Log: `37D363BD7B0F63BBF4FE401409DB6325A9F608D1C94DD88899BE01F85126EF9D`.
3. The repair calls the two non-inlined suites as siblings. The first frame is
   gone before the second constructor runs. A structural regression and both
   fresh native boots verify this candidate; the36-page bootstrap stack is not
   enlarged. General static stack-bound qualification remains open.

Earlier checks:379 host tests in13.99s/21.703s capture, log
`DDF064E863C380FB7C1E726CDE57108FBC6FF4C0D42EABF3D64F56378967A3BB`;
39 then-current parser tests in0.131s/0.672s capture, log
`6D930A3444F6DDA7C82041730FB28E964604FF9A798B61E61612CE35087CD7B7`.
The final parser count40 includes the new non-nested-call regression.

## Remaining Path

Next: original capability tables, typed object rights, generation-safe handles,
quotas, revocation, then bounded IPC between real isolated user tasks. Follow with
init/executable loading, confined console/input, shell/read-only bundled files/two
applications and optical packaging with actual interactive acceptance. This is
not a switch to Linux or a kernel-hosted command interpreter.

USI-1/N12/N13 remain partial; USI-2 through5 remain not started until implementation.
General program admission, persistent quarantine/audit history, actual clock
failure, NMI/shared-controller/IF0 recovery, simultaneous-source hardware races,
partial timer configuration, complete stack/exception/XSAVE/SMAP/SMP/async coverage
remain under FLAG-N13-USERSPACE-ISO-001. Kernel text capacity and diagnostic stack
composition need continued measured review as IPC is added. No phase or flag closes.

The build plan conserves40 phases,301 subphases,8996 requirements,59 additions,
97 flags/42 open and20 gaps. Phase65 remains the observed PooleGlyph checkpoint;
Phase66 Core IR audit is next there, and its owner report is untouched. The locked
master checklist hash remains `A8C94719FAF9428C1F133010BA2603C0270C4E1EFD7327AF8EAB9C8C362ABB3D`.
Product-contract migration for182 pages and full exact-candidate qualification
remain necessary before merge. No signing, release, firmware or physical-media
operation occurs in this cycle.

Metadata regression passes137/137 with zero skips in51.281s/52.141s capture,
source and owner state unchanged. Log:
`E51FE5AC8597BD5E919B0EA04E9341FA538F4665BDDC5A0590F335CE83DDB7B3`.
Architecture binds490 files; kernel source inventory is71 Rust files. Read-only
gate projection remains2/27 current native admissions and5/27 static closures,
with25/22 stale respectively. Firmware is current; boot-trust and ELF prerequisites
remain stale. This is not new guest execution or a full canonical-suite pass.

After recording metadata and regenerating the ledgers, conservation regression
passes73/73 in8.030s/8.907s capture with source and owner data unchanged. Log:
`F48F169CF6109E9A3C37E640E56F31602D0DFFC26A54C6738BFC1F8DE28E32FE`.
Historical fixtures remain frozen, not relabeled as current execution.
