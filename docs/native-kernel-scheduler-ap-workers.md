# PKSCHED5 AP-Local Typed Workers

PKSCHED5 closes `FLAG-N12-SCHED-AP-WORKERS-001` for one bounded development topology. It composes PKSCHED3 deferred work with PKSCHED4's exact BSP-0 and AP-1,2,3 legacy-xAPIC scheduler/runtime. Selector 19 is isolated behind `development-scheduler-ap-workers`; the default image still stops before transfer.

## Ownership Contract

`native/kernel/src/scheduler_ap_workers.rs` owns three fixed AP-local queues, fifteen generation-tagged work slots, one in-flight ticket per AP, and a fixed two-item high-priority bypass bound. A validated timer top half may enqueue work and receive a flush watermark, but it cannot dispatch until the corresponding EOI epoch is observed.

Each dispatch ticket binds the work slot and generation, source and target CPU, attempt and sequence, typed payload, expected result, and acknowledgement checksum. An exact acknowledgement is required before the controller applies the consumer receipt.

## Typed Consumers

The AP `CallFunction` path accepts exactly three payloads: the pre-existing no-op, a timer-driver bottom-half token, and a generation-reclaim service token. The two new tokens produce distinct fixed result values. Any other payload is denied before execution. The AP path retains the PKSMP5 fifteen-register save/restore sequence, balanced EOI, and private guarded IST1 stack.

The live profile dispatches nine driver items and three service items, four per AP. It produces driver sum 177 and service generation 4. No function pointer, arbitrary callback, heap allocation, or dynamic consumer registration enters the controller.

## Cancellation And Reclamation

One queued item is cancelled before dispatch. One AP-local item is cancelled while remotely in flight: the exact AP acknowledgement is accepted for protocol completion, while its consumer result is discarded. A separate APIC-4 dispatch deliberately times out, restores the source queue, and rejects a late acknowledgement.

Flush watermark 13 becomes complete only after all thirteen work items are terminal. Eleven complete and two cancel. All slots are then reclaimed; reusing a stale generation-tagged work ID is rejected.

## Shutdown

All three workers must be offline and every queue, in-flight ticket, and terminal slot empty before shutdown completes. PKSMP5 then parks all three APs, revokes worker, capability, runtime, and MMIO authority, restores PIC and HPET state, and scrubs plus verifies 96 runtime pages and six frame pages. Exactly 102 pages or 417,792 bytes are released, including 24,576 bytes of AP-local worker stacks.

## Evidence

The independent Python oracle reproduces the exact AP traces:

- CPU 1: `1,2,0,3`;
- CPU 2: `5,6,4,7`;
- CPU 3: `9,10,8,11`.

The qualifier requires two exact fresh-vars QEMU runs, six host-probe receipts, ten focused Rust tests within the 214-test kernel suite, input hashes, exact marker/frame/PBP1 equality, source and linked-handler audits, and 34 hostile-control categories covering 226 rejected cases. Both runs must reproduce all 37 markers, twelve typed `CallFunction` executions, both cancellation paths, offline rollback, flush-gated reclamation, and complete cleanup.

Cycle 146 also requalifies the expanded PKENTRY1 layout: entry `0xA000`, text end `0x69000`, RELRO end and writable-data start `0x76000`, and unchanged image end `0x88000`. The canonical kernel is 485,000 bytes with 1,222 relocations and SHA-256 `D11591395FDD8CD7BEEFA0D847A5C99EB133ED15F8DCDDE3392BFA499DCEDC33`; the in-memory image remains 557,056 bytes or 136 pages with no writable-executable mapping.

Cycle 157 replays this profile against the Cycle 153 retention kernel: 517,784 canonical bytes, 144 image pages, and SHA-256 `BDEECCB27B1B91406911F91169B9BF5F9DF0439BB39FA0E1882C07E1AF3B81EF`. The Cycle 146 identity above is historical; current acceptance requires a fresh source-bound readiness receipt and the aggregate gate.

## Nonclaims

This is not general topology, hotplug, NUMA, multi-socket, x2APIC, general SMP timer preemption, ring-3 execution, address-space switching, or complete per-task architectural ownership. The typed consumers are bounded qualification consumers, not a complete production driver/service framework. Target hardware, N12 exit, release promotion, and production readiness remain open.
