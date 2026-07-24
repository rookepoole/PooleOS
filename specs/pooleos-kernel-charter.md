# PooleKernel Native Microkernel Charter

Status: draft v0.2 native reset  
Date: 2026-07-16
Owner and IP steward: Rooke Poole  
Applies to: PooleOS v1, x86-64 UEFI  

## Authority and Precedence

This charter defines the intended privileged kernel boundary for native PooleOS. It is subordinate to `docs/production-goal-charter.md`, and its implementation sequence is governed by `docs/pdc-production-build-plan.md` phases N0-N39. The locked 8,996-item source checklist and `runs/pooleos_native_checklist_coverage.json` remain the complete requirement inventory. Cycle 91's deterministic N0 owner packet is a review surface, not ratification. A Cycle 92 response still contains one unresolved bounded-choice placeholder, so both proposed ADR dispositions, all 38 objective decisions, and custody remain `UNSELECTED` in the packet; no key, signature, merge, tag, publication, measurement, or production authority exists.

Linux, Debian, Buildroot, GRUB, Limine, and systemd are not PooleOS production foundations. QEMU, OVMF, EDK II, Windows, WSL, Linux, and Buildroot may be used only as development, reference, test, or historical evidence inputs. Their use does not make their kernels, bootloaders, userspaces, ABIs, or policies part of PooleOS.

## Kernel Mission

PooleKernel is an original capability-based microkernel. It provides the minimum privileged mechanisms required to:

1. establish and maintain CPU privilege and address-space isolation;
2. own physical pages and authorize mappings;
3. schedule threads without embedding application policy;
4. deliver exceptions, interrupts, timers, and inter-process messages;
5. mint, transfer, attenuate, derive, inspect, and revoke capabilities;
6. delegate IRQ, I/O-port, MMIO, DMA, and IOMMU resources to isolated user-space domains;
7. expose a small versioned syscall and IPC ABI;
8. fail deterministically with serial-first diagnostics and bounded crash records; and
9. provide the minimal audit hooks needed to prove which privileged decisions occurred.

PooleKernel is not PGVM2. PooleGlyph compilation, PGB2 loading, PGVM2 execution, PDC mathematics, desktop behavior, and device protocol policy run outside ring 0.

## Trusted Computing Base

### Ring 0

The v1 ring-0 TCB is limited to:

- x86-64 entry, descriptor tables, privilege transitions, exceptions, interrupt dispatch, timer primitives, SMP bring-up, and CPU lifecycle;
- physical-page ownership, virtual-address-space operations, guarded user copy, MMIO mapping control, and core allocators required by the kernel itself;
- thread contexts, neutral scheduling primitives, blocking/wakeup, IPC fast and slow paths, and bounded event delivery;
- kernel objects, capability tables, derivation and revocation bookkeeping, and resource-accounting enforcement;
- IRQ routing, I/O-port authorization, MMIO delegation, DMA-map authorization, IOMMU-domain control, and interrupt-remapping control;
- boot-info intake, early entropy intake, minimal monotonic time, panic, serial logging, crash capture, and audit sequencing.

### Privileged User Space

The initial system, process server, pager, device manager, service supervisor, policy authority, security services, VFS, storage stack, network stack, graphics stack, audio stack, input stack, update service, installer, recovery services, PDC services, PGVM2, and PooleGlass execute in separate user-space protection domains.

### Driver Domains

General device drivers are signed user-space services. Each driver receives only the capabilities for its assigned device resources and approved IPC peers. DMA-capable drivers require an IOMMU domain before production promotion. A driver crash must be restartable without corrupting kernel state or granting authority to its replacement implicitly.

Production loadable kernel modules are prohibited in v1. Reopening this rule requires a signed ADR, a revised TCB inventory, a threat-model update, and new assurance evidence.

## Capability Laws

The capability model must enforce all of the following:

1. No ambient authority: possession of a valid capability is required for every protected operation.
2. Unforgeability: user-space bytes cannot manufacture kernel authority.
3. Least privilege: capabilities encode object identity and bounded rights.
4. Attenuation: delegation may remove rights but may not add rights.
5. Controlled derivation: child capabilities retain auditable ancestry.
6. Explicit transfer: IPC transfer is validated by both endpoint and capability policy.
7. Revocation: authority can be invalidated with defined propagation and concurrency semantics.
8. Non-reuse safety: stale handles cannot acquire authority over a recycled object.
9. Bounded accounting: object, page, CPU, IPC, IRQ, and DMA consumption is charged to an accountable domain.
10. Recovery discipline: restarting a server or driver never silently restores revoked authority.

The executable capability model and its revocation state machine are N4/N13 prerequisites. Cycle 89 checks attenuation, ancestry, acyclic derivation, and transitive revocation over three capability IDs, two principals, two rights, and one object; it deliberately excludes IPC, handle reuse, concurrency, quotas, timing, kernel data structures, and implementation traces. This finite state-space result is not a theorem, ABI freeze, or kernel enforcement claim. Model and simulator receipts remain non-promoting until the same laws are enforced by a booted PooleKernel and cross-checked against exact implementation traces.

The executable virtual-memory ownership model is an N4/N9 prerequisite. Cycle 90 checks page-table, TLB, and retired-translation ownership/generation agreement over two domains, two CPUs, two physical pages, one virtual address, and one generation-changing ownership reuse. The safe transfer path requires old page-table mappings, cached translations, and pending shootdown state to clear before ownership changes; independent stale-mapping and early-reuse mutants must violate `PageTableSafety` and `TlbSafety`. The model deliberately excludes page-table levels, PCID/ASID, weak-memory ordering, interrupt races, concurrent page-table writers, DMA/IOMMU, hardware page walks, huge pages, copy-on-write, swap, and NUMA. It is not a theorem, memory ABI freeze, kernel execution, or implementation-equivalence claim.

The executable scheduler model is an N4/N12 prerequisite. Cycle 95 checks run-state and queue agreement, one current task, blocked wait ownership, cancel and timeout wake delivery, no duplicate runnable entry, one-level priority inheritance, audited effective-priority dispatch, a two-bypass accounting bound, lock handoff, and teardown over three fixed-priority tasks, one CPU context, and one lock. Seven independent mutants must violate their exact wake, queue, inheritance, dispatch, bypass, or quiescence invariant. The bypass bound is a state-transition accounting rule only: `Idle` remains enabled, and no temporal fairness, eventual-dispatch, response-time, starvation-freedom, SMP, weak-memory, register-context, ABI, or implementation-equivalence claim follows.

The executable PooleFS transaction/recovery model is an N4/N19 prerequisite. Cycle 96 checks copy-on-write allocation roles, data/checksum agreement, ordered data/intent/commit persistence, commit-before-publication, old-or-new visibility, corruption rejection, crash and restart during mounted operation or recovery, replay idempotence, and mounted teardown over two abstract blocks and one update. Six independent mutants must violate their exact checksum, publication, allocation, replay, corruption-rejection, or quiescence invariant. Atomic flush/FUA edges do not model sector atomicity, device caches, controller ordering, concurrent transactions, VFS/page-cache behavior, on-disk ABI bytes, hardware durability, or implementation equivalence.

## Boot and Trust Boundary

PooleBoot is a separate Poole-authored PE32+ UEFI application. It owns firmware-facing boot duties, image and manifest verification, memory-map capture, entropy/firmware-table handoff, and `ExitBootServices`. PooleKernel accepts only the frozen Poole boot protocol and does not call UEFI boot services after takeover.

Secure Boot, measured boot, rollback protection, key rotation, revocation state, recovery authorization, and reproducible image identity are release requirements, not assumptions. Firmware, CPU microcode, platform keys, vendor option ROMs, and required binary firmware remain explicitly inventoried external trust dependencies.

## ABI and Versioning

Before implementation promotion, PooleOS must freeze independent version namespaces for:

- Poole boot protocol;
- kernel image and boot-info ABI;
- syscall ABI;
- IPC message and capability-transfer ABI;
- driver-domain resource protocol;
- executable and dynamic-link ABI;
- crash, trace, receipt, and audit formats;
- PGB2 and PGVM2; and
- system, recovery, package, update, filesystem, and release manifests.

Unknown versions, reserved bits, malformed lengths, arithmetic overflow, invalid user pointers, capability type mismatches, and unauthorized object operations fail closed.

## Kernel Invariants

1. No user mapping may access kernel-only memory.
2. No physical page has conflicting writable owners.
3. No user-supplied pointer is dereferenced without range, permission, and overflow checks.
4. No IRQ, port, MMIO range, DMA map, or IOMMU domain is usable without explicit authority.
5. No DMA-capable production device operates outside an assigned IOMMU domain unless a documented hardware exception blocks release promotion.
6. Every privilege transition restores a validated execution context.
7. IPC and capability transfer are atomic with respect to failure-visible state.
8. Revoked or stale capabilities cannot regain authority through races or object reuse.
9. Kernel allocation failure, interrupt storms, malformed IPC, and user faults cannot cause silent privilege expansion.
10. Kernel logs and receipts distinguish observed facts, simulator evidence, verified properties, and open claims.
11. Deterministic tests control nondeterministic inputs and report the exact build and machine identity.
12. A panic never claims successful persistence, rollback protection, or release readiness without a verified receipt.

## Failure and Recovery

Kernel faults stop or quarantine the affected execution context, emit bounded diagnostics, and preserve the earliest trustworthy failure record. User process and driver faults are contained to their protection domains. Recovery policy belongs to user-space supervisors except when kernel integrity itself is uncertain, in which case PooleKernel enters a minimal recovery or halt path.

The kernel must support watchdog integration, crash-loop limits, priority-inversion controls, deadlock diagnostics, allocation-failure injection, interrupt-storm containment, and deterministic fault injection before production promotion.

## PooleGlyph and PDC Boundary

PooleGlyph and PDC remain first-class PooleOS workloads and policy services, not privileged kernel mechanisms.

- PGB2 and PGVM2 must be frozen, verifier-backed, resource-bounded, and capability-confined before system-policy promotion.
- PDC contracts must preserve exact source, representation, units, domain, sign, matrix, benchmark, and claim-lane bindings.
- PDC GPU, CPU, RAM-lane, hash-route, and tax-optimizer work may become guarded user-space backends only after portable-reference equivalence and fallback proofs.
- PDC control or actuator lanes require independent safety bounds and cannot acquire unrestricted device authority.

PooleGlyph Phase 65 evidence is current; Phase 66 remains a prerequisite for parser-to-kernel promotion. Existing PGB2/PGVM2 and isolation artifacts are draft or simulator evidence until native execution receipts exist.

## Promotion Gates

PooleKernel is not production-ready until:

1. N0-N39 exit gates pass with no unresolved stop-ship flag;
2. PooleBoot reproducibly loads and verifies PooleKernel on QEMU/OVMF and the exact Tier 1 machine;
3. ring 3, syscalls, IPC, capabilities, revocation, scheduling, memory isolation, IRQ delegation, and IOMMU confinement are demonstrated under negative tests;
4. reference VIRTIO drivers and required Tier 1 drivers run in isolated user-space domains;
5. property, model, mutation, fuzz, symbolic, schedule, fault, power-loss, security, conformance, and soak evidence meets frozen thresholds;
6. the TCB, threat model, assumptions, proof boundaries, SBOM, provenance, keys, revocations, and external dependencies are independently reviewable;
7. the signed ISO is reproducible and free of prohibited production substitutes; and
8. clean-media QEMU and physical-machine receipts bind the exact source, toolchain, binaries, configuration, keys, and hardware identity.

Current state: PooleKernel is implemented only as a bounded early freestanding product and is not production-ready. Cycles 97-118 establish unsigned PooleBoot intake, exact retained PKMAP2/PBLIVE3/PBEXIT1 state, a reproducible PKELF1 image, allocation-free nine-file PKREVAL1, and opt-in QEMU-only PKXFER1 with no authority. Cycles 119-124 add bounded BSP trap, qemu64 CPU observation, exact-target rejection policy, eager x87/SSE ownership/exceptions, and privileged-MSR observation. Cycles 125-127 add PKPMM1 generation-safe physical ownership, PKVM1 inactive four-level transactions, and one bounded PKVM2 active root with a nine-page direct map, exact CR3 restoration, and three local invalidation receipts. Cycle 128 adds PKPMM2 scrubbed lifecycle transactions, and Cycle 129 adds the PKPMM3 retained five-page guarded metadata arena. Cycle 130 upgrades selector 8 to PKPMM4: monotonic stages admit Boot Services only after `ExitBootServices` and reserve ACPI admission for explicit table release; a scalar cursor streams complete capacity/arithmetic/retained-overlap preflight, full zero/readback, and infallible metadata commit; exact repeat requests are idempotent; and content faults preserve ownership metadata. Seventy-nine kernel host tests, two exact fresh-vars qemu64 runs with 42 markers, and 109 hostile controls pass. The runs admit 70 Boot Services records as 12 ranges and 11,250 pages, finish with 129,168 managed pages while 11 ACPI pages remain held, protect 825 loader pages, scrub and verify 11,263 pages and 46,133,248 bytes, and perform 5,767,680 physical writes, 5,768,704 reads, and 22,543 temporary-PTE writes and invalidations. The current kernel is 70 pages with 593 relocations and SHA-256 `20BCE1C7501BC2344A6D7505BCDA749D9B2738A8435255D0EC2EF5A3E177CC4C`. This is not authenticated boot, production transfer, target qualification, direct per-processor microcode evidence, syscall or GS/TSC_AUX activation, machine-check handling, PMU ownership, AVX/extended-state qualification, scheduler or user-task delivery, AP/migration integration, complete per-CPU descriptor state, scalable allocator metadata, complete ACPI consumer integration, complete generation-owned address spaces, SMP shootdown, huge pages, PCID, COW, user faults, pager IPC, heaps, MMIO/cache qualification, concurrent/SMP allocation, pressure/OOM policy, capabilities, ring 3, N5/N6/N7/N9 exit, or production readiness. The applicable Model 40h-4Fh errata source and a direct numeric client microcode floor or ratified replacement remain stop-ship gaps. The selected FIDO2 key remains physically unavailable despite authorization for acquisition and later key/signing operations. The immediate external move is `N0-HW-KEY-ACQUIRE-001`; the next owner-independent engineering move is `N9-PMM-GROWTH-001`.
