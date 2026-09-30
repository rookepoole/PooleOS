# PKSCHED4 Exact-Topology SMP Scheduler

PKSCHED4 covers one bounded development topology. Its earlier flag closure was reopened by Cycle 203; the current roadmap, not this profile description, controls closure. It composes the allocation-free PKSCHED1 task model with PKSMP5's exact BSP-0 and AP-1,2,3 legacy-xAPIC runtime. Selector 18 is isolated behind `development-scheduler-smp`; the default image still stops before transfer.

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

The qualifier requires two exact fresh-vars QEMU runs, the five-receipt host probe, ten focused Rust tests within the 246-test kernel suite, input hashes, exact marker equality, exact frame and PBP1 equality, source audits, and 32 control groups. Cycle 208 replaces sixteen constant-only control reports: thirteen groups execute 59 native scheduler boundary scenarios; three groups execute 51 source-audit mutations. Including existing marker/probe/input controls gives 303 cases, of which 244 are rejection cases and 59 include positive transitions and ownership conservation. Source mutations are not hardware fault injection. The host fixture compiles the actual native module, and disabled native checks must fail its assertions.

Recorded admission reparses both runs, exits, markers, summaries, digests and handoffs; checks exact types, observations, native/host probe output, source bindings, linked identity and per-group counts; and rejects malformed shapes without throwing. This establishes recorded consistency, not authentication or a substitute for fresh execution. AP register auditing distinguishes fourteen saved/restored registers from untouched RBP; preserving fifteen GPRs does not mean fifteen stack pushes. Full architectural state, live failure-path injection and production qualification remain unclaimed.

The scheduler pushed PKENTRY1 beyond its former text reservation, so Cycle 145 also requalifies a coherent page-aligned image layout: entry `0xA000`, text end `0x66000`, RELRO end and writable-data start `0x74000`, and unchanged image end `0x88000`. After the downstream stack repair, the canonical kernel is 476,808 bytes with 1,181 relocations and SHA-256 `9C23236E85A6D2C7AEEFDA12F3CEC202DC3BF34B89D9CEAEEBB7037A079DA168`; the in-memory image remains 557,056 bytes or 136 pages with no writable-executable mapping.

Cycle 157 replays this profile against the Cycle 153 retention kernel: 517,784 canonical bytes, 144 image pages, and SHA-256 `BDEECCB27B1B91406911F91169B9BF5F9DF0439BB39FA0E1882C07E1AF3B81EF`. The Cycle 145 identity above is historical; current acceptance requires a fresh source-bound readiness receipt and the aggregate gate.

## Nonclaims

This is not general topology, hotplug, NUMA, multi-socket, x2APIC, general SMP timer preemption, ring-3 execution, address-space switching, or complete per-task FS/GS, xstate, debug, and PMU ownership. No driver or service consumes the scheduler. Target hardware, N12 exit, release promotion, and production readiness remain open.
