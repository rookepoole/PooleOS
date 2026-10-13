# Owned Startup Handoff

Cycle281 adds `Slot::replace_startup_arguments` for the application integration
lane. It is a trusted kernel dispatcher operation, not a new user syscall. It
requires a Prepared, never-exposed CPU image with no prior outcome, slice or
accounting state, exact TaskId and construction-bound PSTART1 metadata.

## Mechanism

The original and replacement `Arguments` must have the same encoded byte count,
matching the already-bound startup registers. The method derives the physical
stack page from the owned CPU image; callers cannot supply an arbitrary target
address. It verifies the complete expected block before any write, replaces only
that block, completes the memory operation, verifies all replacement words and
completes access again. It does not change mappings, registers, code or stack tail.

Before memory access, the slot becomes Quarantined. Only a fully successful
handoff restores Prepared. Read failure, mismatched original data, after-effect
write failure, corrupt readback or failed finish leaves the exact owner retained.
No retry, activation or fabricated exit is possible. Existing explicit abandon
and retirement paths remain responsible for recovery; dropping an owner is not
permission to free retained memory.

The memory/CPU adapters remain trusted boundaries, including exclusive access
and `finish` not mutating persistent mappings. Host tests exercise adapters and
state machines; they do not independently prove physical memory behavior.

## Application Grants

The existing `Space::admit_launch` transaction supports two `Inherit` steps:
control endpoint SEND and file endpoint SEND, followed by the parent's process
lease. Use the returned handles, not predicted vacancy generations. Three host
restart generations verify that old handles deny and service endpoints survive.
Neither app gains RECEIVE, GRANT, DESTROY or an owned endpoint. Failure at the
second grant or later process quota rolls back newly installed authority and
scheduler changes; consumed generations remain consumed.

Admission commits before the startup-byte handoff. They are deliberately **not**
claimed to be one failure-atomic transaction. The native integration must hold
exclusive BSP/IF0 dispatch ownership across both operations. On handoff error it
must not resume the parent or dispatch the child; retain owners/authority and
fail closed until explicit cleanup. General asynchronous rollback/recovery is
still a gap, not silently implemented by this byte replacement helper.

## Evidence And Remaining Work

Seven new startup tests cover96-byte empty, normal application and512-byte maximum
blocks, unchanged neighboring memory/registers, every original/read/write/readback
word, both finish failures, stale identity, wrong image/length, exposed states,
retained ownership and an actual admission-to-startup host composition. Four new
capability tests cover minimal rights, restart generations, source failure and
process-quota rollback.551 default/567 file-profile tests pass per debug/release;
26 whole-kernel ownership doctests pass. [Checkpoint](checkpoints/cycle281-startup-handoff.md).

Native caller integration, bounded file-server app authorization, shell job/result
multiplexing, real app CPU execution, native failure injection, resource/stack
measurement and optical packaging remain. No new VM or ISO is produced here.
