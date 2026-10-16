# Native User Runtime Accounting

PKUSER13 is the single-BSP development peer path, not complete production CPU
accounting. The charge is HPET ticks from one-shot arming through the terminal
event measurement. It includes dispatch-to-user and in-quantum syscall/exception
handling overhead, and excludes later timer draining, descriptor detachment,
memory scrubbing and scheduler work. It is not pure user-instruction time.

## Ownership And Invariants

| ID | Predicate | Verification |
| --- | --- | --- |
| RT1 | Every authenticated returned quantum, terminal or preempted, has measured ticks | Host slice validation and native all-dispatch totals |
| RT2 | Measurement enters the persistent slot before fallible cleanup or root suspension | Injected cleanup/suspend errors; native cleanup quarantine |
| RT3 | Pending charges block resume, cancel, detach and abandonment | Host negative cases and retained PMM handles |
| RT4 | Settlement matches task generation, running CPU, dispatch ordinal and prior total | Scheduler rejection/overflow tests; native snapshot comparison |
| RT5 | All fallible scheduler checks precede mutation; a failure leaves the charge retryable | Exact snapshot/sequence host checks |
| RT6 | The slot consumes a charge once; zero-duration dispatches are also replay-protected | Host zero/nonzero sequences and duplicate settlement after every native dispatch |
| RT7 | Missing/malformed measurements remain unknown, not zero; memory stays retained | Host execution errors and forged observations |
| RT8 | Cleanup retry never measures or charges the quantum again | Host repeated cleanup failure and native retry after settlement |
| RT9 | Charged per-task totals equal scheduler totals and the sum of event classes | Native per-dispatch and final checks; independent Python oracle |
| RT10 | Existing containment, construction, drain, unsigned-denial and production boundaries persist | Full focused qualification and ordinary-boot denial |

The slot owns the pending `Slice`; copying a public outcome does not allow charge
submission. A runtime snapshot is observation only. `account_slice` settles into
the running scheduler task under exclusive mutable ownership. The scheduler
records the charged ordinal even for zero ticks. Checked counters never wrap.
The peer runner settles before yielding or deleting a scheduler task, including
when `run_slice` fails after an authenticated measurement. It never invents an
application result for that failed cleanup.

An execution error without a valid sample is deliberately not recoverable through
ordinary abandonment: the slot remains quarantined with unknown runtime. A
separate emergency accounting/recovery policy is required, rather than silently
freeing the task with zero charge. This is a fail-closed limitation, not proof of
general fault recovery. Unmeasured legacy one-shot diagnostic tasks are outside
the resumable peer profile and do not gain an accounting claim.

## Clock Contract

Counter-mask modular subtraction handles one bounded wrap. The existing100ms
elapsed bound is preserved; multiple wraps and an independently stalled clock
are not diagnosed by subtraction. Partial terminal samples allow zero ticks at
counter resolution; interrupt-preempted samples still require positive ticks.
The native adapter checks the configured HPET period. No minimum tick is forged.

The Intel HPET specification describes current-counter reads, repeated values
within counter resolution, and the risk that some platforms split64-bit reads
across rollover. See sections2.3.7 and2.4.7 of the
[official HPET specification](https://www.intel.com/content/dam/www/public/us/en/documents/technical-specifications/software-developers-hpet-spec-1-0a.pdf).
This work retains the existing QEMU MMIO read adapter; coherent physical-hardware
sampling, cross-CPU clocks, clock reset/drift, pure user/kernel attribution and
independent missing-interrupt recovery remain separate qualifications.

## Design Alternatives

Returning ticks only in a successful slice loses charges on cleanup errors.
Charging during cleanup risks duplication on retry and includes cleanup time.
Transferring an unconstrained copyable receipt lets callers replay or misroute it.
A global mutable billing counter obscures per-task lifetime and failure ownership.
The selected retained slot charge and atomic scheduler settlement preserve those
boundaries. Measurement failure remains an explicit unknown alternative rather
than being interpreted as a successful zero sample.

Qualification must use two fresh native guests plus ordinary denial. Existing
120-second guest and360-second live-qualifier bounds are unchanged. All15 peer
survival and construction/timer-drain cases remain; no interactive ISO or phase
exit is implied. Results and failed attempts belong in the Cycle247 checkpoint.
