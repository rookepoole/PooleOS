# Cycle316: Bounded Kernel Job Registry

Status: partial native development. Parent commit
`be9105f08fb9536e34d9d5747659d2b1c80aee12`. Previous turn: verified progress.
Microkernel-first direction remains; desktop/ISO packaging is deferred.

## Implemented

- Bounded registry owns job records; temporary Owner views preserve records
  between dispatches and cannot expose mutable Job references.
- Managed slot claims prevent standalone/cross-registry enrollment from bypassing
  ancestry checks. Duplicate slot/root aliases and multi-level cycles reject
  before claims commit. Capacity and stale identity failures remain atomic.
- Round-robin orphan selection rotates across closed owners and their children,
  including after cleanup failure. Selection changes no task/runtime/retry state.
- Closed, drained record retirement supports fresh owner generations. Nested
  obligations remain reachable after an intermediate owner's memory is reclaimed.
- Native supervisor creation, enrollment and cleanup now use registry-owned views.
  Its current profile retains one parent job; native multi-owner selection is next.

## Evidence

Eight new host tests cover registry bounds/capacity; multi-hop cycles; standalone
and cross-registry escape; aliases; two-owner/four-child selection plus failed
cleanup; view reacquisition/whole-registry loss; retirement/generations; and nested
obligations. Initial host run passes 632 tests. The final profiles pass 632 debug,
632 release and 650 ordinary-profile tests; 36 focused native-oracle checks pass.
Nine headless QEMU guests pass: successful exhausted recovery, persistent
retention and ordinary deferred cleanup, each with two controls and a separate
denied-authority kernel. These exercise registry-owned admission/closure/cleanup,
not native multi-owner round-robin dispatch. Paired kernels match; both raw logs,
console input/output, linked/packed kernels and boot media reconstruct exactly.
The fixed 208-page image budget and 36-page guarded-stack layout remain unchanged.

Execution bindings: 1,020; selected paired user programs: five; program bindings:
111. PooleGlyph/owner input pins, Cycle308's pointer and both ISO copies match.
Aggregate: `runs/native-job-registry-readiness.json`, SHA256
`D54D4060BFF37B5F848C8B859F13A37A8986E9CE43E6ABA499C5E15C02652AB2`.
Selected integration/roadmap rerun: 514/514 pass. Publication tests: 9/9 pass.
The 1,662 discovered Python tests are inventory, not complete canonical execution.
Final serialization uses 16 targeted checks; the exact staged audit reconstructs
929 architecture bindings, all 100 historical receipts and the retained preview
before committing the 26-file candidate. Keep PR81 draft; no merge qualification.

The first 514-check integration run passes 513 and fails one historical inventory
assertion: current kernel source count is 138, not 136, because of the registry
and its test module. Update that count and its explicit two-file delta without
changing the old 79-input receipt or weakening stale-source rejection. Preserve
`outputs/cycle316-metadata1.log`, SHA256
`4FB3A42B526066B92743C63291363389663DA610D189AF487ED72DE00AD39BF0`.
Corrected rerun log SHA256:
`917D739BAF55153958228B5773D70056270F27019FBB0BE6A5F5B0AF2BD9F1DD`.
The later metadata failure is checkpoint-bound separately from the earlier native
aggregate. Local final audit: `outputs/cycle316-finalcheck.json`.

No new userspace program, syscall, unsafe code, heap, retry reset or expanded
process/resource quota is introduced. The private slot's managed marker and new
registry APIs extend the existing generation-bound task ownership boundary.

## Next Work

Integrate the selector into bounded native multi-owner cleanup dispatch, with
simultaneous stopped owners, a persistently retained child and a reclaimable
independent child. Verify native selection order and independent progress without
weakening deferred/recovery budgets. Current host selection evidence is not a
native fairness or wall-clock bound; its multi-owner cleanup uses prepared tasks,
not concurrently executing userspace. Dropped views recover; loss of the entire
registry still retains resources and needs a separate recovery design.

Then continue capability/IPC revocation, bounded service restart/rebinding,
partial allocator release, construction/committed-handoff recovery and all-path
stack/SMP isolation. All 40 phases, 301 subphases and 101 flags (46 open) remain;
PooleGlyph Phase65 pins and the owner's dirty report are preserved, with Phase66
promotion pending. No GUI/ISO/VirtualBox replay, main merge, full canonical pass
or production promotion is claimed.

Contract: [Native Job Registry](../native-job-registry.md).
