# PKSCHED6 Exact-Topology SMP Preemption

PKSCHED6 closes `FLAG-N12-SCHED-SMP-PREEMPT-001` only for the frozen four-vCPU development profile. Selector 20 composes PKSCHED2 timer/wakeup semantics, PKSCHED4 exact-topology run-queue ownership, PKSCHED5 AP ownership boundaries, and PKSMP5 fixed-vector IPI delivery. The default image still stops before kernel transfer.

## Implemented Boundary

- Four allocation-free CPU lanes bind CPU/APIC identity, timer epoch, interrupt-frame epoch, current task, private 8 KiB IST range, and run queue.
- Four fixed event queues contain at most sixteen typed cancel, wake, or migration events. Equal deadlines use the frozen `cancel -> wake -> migration -> sequence` order.
- Remote wake, migration, initial AP dispatch, and quantum preemption publish the PKSMP5 reschedule request. Task ownership remains unchanged until the exact AP acknowledgement is validated.
- Two-tick quanta, one-tick event-latency allowance, equal-priority bypass accounting, and a two-tick runnable-peer watchdog bound the qualified trace.
- One APIC-4 timeout preserves source ownership and rejects a late acknowledgement.
- Shutdown retires all eight task identities, revokes all three AP timer/frame owners, parks all APs, and scrubs, verifies, and releases 96 runtime pages plus six frame pages.

## Evidence Shape

The independent Rust host probe emits seven receipts. The Python oracle reconstructs the same event order, frame/timer epochs, owner trace, five model acknowledgements, three quantum switches, and cleanup state. Five focused tests within 214 kernel host tests pass. Two QEMU runs emit the same 38-marker transcript and retain exact screenshot and PBP1 bytes. Thirty-four negative-control categories mutate marker order and fields, selector isolation, frame/timer ownership, acknowledgement binding, rollback, watchdog/fairness bounds, cleanup, and source bindings; all 232 cases are rejected.

The historical Cycle 147 PKENTRY1 product was a 513,672-byte canonical kernel in a 585,728-byte, 143-page image, with entry `0xA000`, text end `0x70000`, RELRO end and writable-data start `0x7D000`, 1,264 relocations, and SHA-256 `FCE5C1F2478651D010A2F2781B80494FD0D9721880D33CE8C66A499B35C8DAB6`. PKMAP2 uses two retained leaf tables and five table pages so this expansion does not consume a guard or collide with retained stack, handoff, allocator, ledger, or IRQ-MMIO roles.

Cycle 157 replays this profile against the Cycle 153 retention kernel: 517,784 canonical bytes, 144 image pages, and SHA-256 `BDEECCB27B1B91406911F91169B9BF5F9DF0439BB39FA0E1882C07E1AF3B81EF`. Current acceptance requires a fresh source-bound readiness receipt and the aggregate gate, not the historical identity above.

## Claim Boundary

PKSCHED6 does not install AP-local hardware timer interrupt delivery. Its per-CPU timer and frame lanes are bounded semantic inputs, while the AP-side reschedule handler and acknowledgement are live. It does not implement general topology, hotplug, x2APIC, NUMA, ring 3, address-space switching, full per-task architectural state, physical-target qualification, the N12 exit gate, or production readiness.
