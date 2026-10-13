# Native Process Completion

PCOMP1, Cycle271. A bounded extension to PPROC1/PLAUNCH1, not a general process
manager. PSABI1 call20 accepts an owned process capability; all remaining
arguments must be zero. It neither takes user pointers nor grants new authority.

## Wire Contract

`Denied/0` rejects an invalid owner, root generation, task generation, handle
generation, type, or slot. Both Inspect and InspectTerminate may query completion.
`Again/detail` reports incomplete state:1 attached,2 stop pending,3 stop claimed,
4 detached but no completion published. Attached does not mean runnable. None of
these states proves physical reclamation. Legacy call17 retains its attachment
semantics and still returns Revoked after detachment.

`Ok/value` is a retained terminal result. The upper32 bits are the reason tag;
the lower32 bits are the detail:

| Tag | Meaning | Detail |
| --- | --- | --- |
| 1 | Exit | Full u32 exit code |
| 2 | Fault | Validated exception vector |
| 3 | Invalid return | Instruction1, stack2, flags3 |
| 4 | Cancelled | 0 |
| 5 | Call limit | 0 |
| 6 | Call counter exhausted | 0 |
| 7 | Watchdog | 0 |

No fault address or instruction pointer is exposed. User code rejects unknown
tags and reserved details. Completion queries are non-consuming; old records
remain quota-charged until explicit revocation, launch supersession or owner death.

## Publication And Reuse

Only the trusted quiescent dispatcher publishes. It must finish accounting,
restore the kernel context, retire and scrub/free the owned image, and tear down
the scheduler task first. The API independently checks a detached target slot,
the exact scheduler generation in Dead state, a valid Outcome, and matching
retained target IDs/roots. Every observer is checked before any record changes.
Duplicate or conflicting publication rejects without overwriting completion.

Physical cleanup is a trusted caller obligation, not independently proved by the
completion table or by a user's request. In the qualified native adapter,
publication occurs only after successful `Peer::reap`, scheduler teardown and an
observed13-page allocation reduction. A cleanup error prevents publication.
General retained ownership/retry after partial cleanup remains unimplemented.

PLAUNCH1 next-sequence requests now remain Again while the old child is detached
but unpublished. They do not discard its process handle. A valid completion is
required before supersession; construction still requires an empty owned Slot.

The independently built PooleSupervisor polls call20 and records its typed result.
It advances restart policy only for terminal results, not revocation. The current
diagnostic program expects final exit100 from its fixed worker, exits0 on success,
170 on transport rejection and172 on an unexpected final reason. General restart
policy belongs in user space, not in the kernel.

## Evidence And Limits

[Cycle271](checkpoints/cycle271-native-process-completion.md) records two fresh
normal guests and one denied-owner guest. Each normal lifetime deliberately stays
unpublished across one full owner syscall-budget dispatch, then completes. Both
normal guests finish two lifetimes, all cleanup, and survivor execution.

Host tests cover fault/cancel/watchdog encodings and malformed/forged identities;
native injected fault/stop completion is not claimed yet. Shell lifecycle commands,
bundled files, useful apps, multipage executables and optical ISO remain open.
