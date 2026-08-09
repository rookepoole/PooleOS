# PKSCHED4 Exact-Topology SMP Scheduler

PKSCHED4 closes `FLAG-N12-SCHED-SMP-001` for one bounded development topology. It composes the allocation-free PKSCHED1 task model with PKSMP5's exact BSP-0 and AP-1,2,3 legacy-xAPIC runtime. Selector 18 is isolated behind `development-scheduler-smp`; the default image still stops before transfer.

## Ownership Contract

`native/kernel/src/scheduler_smp.rs` owns four fixed run queues, eight generation-tagged task slots, one current-task position per CPU, and one serialized transfer ticket. A wake, migration, or AP dispatch does not commit target ownership until an acknowledgement matches all of the following:

- task slot and generation;
- current owner epoch;
- source and target CPU;
- request attempt and sequence;
- allowlisted IPI operation, accepted status, zero error, and fixed result token.

The live profile wakes one blocked task from BSP ownership to CPU 1, migrates one runnable task from CPU 1 to CPU 2, and migrates one from CPU 2 to CPU 3. Each AP then dispatches two tasks from its local queue. The BSP dispatches two local tasks. Equal-priority queue members use bypass aging bounded by the eight-slot capacity.

## Live Boundary

The AP execution primitive is PKSMP5's existing allowlisted `CallFunction` no-op token. It is delivered three times per AP: once for the remote wake or migration transaction and twice for local task dispatch. The AP handler validates the capability, target, vector, attempt, sequence, payload, and checksum; executes on the AP-local guarded runtime; acknowledges; balances EOI; and restores its saved registers. PKSCHED4 does not add arbitrary callbacks.

An APIC-4 request deliberately times out. The scheduler retains the source queue and owner epoch, records one rollback, withholds target ownership, and rejects a simulated late acknowledgement. PKSMP5 separately retains its partial-start and remote-invalidation timeout controls.

## Shutdown

All eight tasks must be dead and all four idle owners visible before scheduler AP ownership is revoked. PKSMP5 then stops and quiesces all three APs, applies final INIT parking, validates the AP-local runtime pages, revokes aliases and MMIO, restores PIC and HPET state, and scrubs plus verifies 96 runtime pages and six frame pages. Exactly 102 pages or 417,792 bytes are released.

## Evidence

The independent Python oracle reproduces the queue transforms and traces:

- BSP: `0,7`;
- CPU 1: `2,1`;
- CPU 2: `4,3`;
- CPU 3: `6,5`.

The qualifier requires two exact fresh-vars QEMU runs, the five-receipt host probe, eight focused Rust tests within the 173-test kernel suite, input hashes, exact marker equality, exact frame and PBP1 equality, source audits, and 32 hostile-control categories covering 209 rejected cases. Both four-vCPU runs reproduce all 37 markers, six AP dispatches, two BSP dispatches, nine `CallFunction` executions, one timeout rollback, two stale-acknowledgement rejections, and complete cleanup.

The scheduler pushed PKENTRY1 beyond its former text reservation, so Cycle 145 also requalifies a coherent page-aligned image layout: entry `0xA000`, text end `0x66000`, RELRO end and writable-data start `0x74000`, and unchanged image end `0x88000`. After the downstream stack repair, the canonical kernel is 476,808 bytes with 1,181 relocations and SHA-256 `9C23236E85A6D2C7AEEFDA12F3CEC202DC3BF34B89D9CEAEEBB7037A079DA168`; the in-memory image remains 557,056 bytes or 136 pages with no writable-executable mapping.

## Nonclaims

This is not general topology, hotplug, NUMA, multi-socket, x2APIC, general SMP timer preemption, ring-3 execution, address-space switching, or complete per-task FS/GS, xstate, debug, and PMU ownership. No driver or service consumes the scheduler. Target hardware, N12 exit, release promotion, and production readiness remain open.
