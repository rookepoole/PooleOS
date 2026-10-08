# Atomic Task Admission

PKADMIT1 is an original, bounded supervisor mechanism for the one-BSP native
integration lane. It connects IPC bootstrap to scheduler publication. It is not
an executable loader, user-callable spawn operation, stable ABI or complete
service supervisor. Existing prepared-image and task-slot ownership remain required.

## Transaction

`Space::admit` accepts one to four member identities/admissions and at most sixteen
declarative capability steps. Members must name caller-owned, never-dispatched
prepared images. This precondition belongs to the trusted supervisor; a copied
ImageAdmission or raw TaskId is not user authority or a transferable ownership token.

The original scheduler is validated, copied as pure bounded queue/task state, and
the new members are created/activated on that private candidate. No device or
non-copyable resource owner is copied. Invalid scheduler configuration therefore
leaves the IPC Space and original scheduler unchanged.

The exclusive IPC owner then attaches members and executes the bounded plan:
- Endpoint creates an object owned by a new member.
- Inherit attenuates an existing GRANT-capable handle into a new member's table.
- Grant exports an earlier newly-created Endpoint to an authenticated live target.
  It cannot re-export an Inherit result or refer forward to a future plan step.

Only after every step succeeds is the candidate scheduler published. There are
no callbacks, hardware writes or fallible operations between the final authority
step and publication. Under the caller's exclusive BSP/IF0 ownership, incomplete
members cannot run or expose partially installed authority to another task.

## Abort And Retention

On failure, reverse-order detach removes only newly attached tables and their
new endpoints. Grants exported from these new endpoints are revoked everywhere;
inherited grants disappear with the new recipient without destroying the source.
No existing queue, waiter, request, running peer or clock lease is rolled back.
The original scheduler remains unchanged, including counters and queue order.

Task, capability and object generation high-water marks are never rewound. A
partially attached task identity is consumed even if it never ran. Its prepared
image remains with the original task-slot owner for explicit retirement. Retrying
the same identity rejects; cleanup and a fresh slot generation permit a new attempt.
This is observable generation consumption, not byte-identical Space rollback.

Memory cleanup is a separate, fallible ownership operation. Admission does not
free a page or convert uncertain cleanup into success. Existing Slot::abandon
retains a quarantined CPU/prepared-image owner if retirement fails and supports
retry before scrubbing/releasing the detached memory. The native check injects
an error after a real memory-finish boundary and proves all five allocations are
still protected against free before retry.

## Qualification And Boundaries

Host checks cover every prefix of the exchange plan, endpoint/table quota,
partial attachment, root collisions, invalid priorities, duplicate/existing tasks,
overlong plans, invalid/forward references, missing targets, rights amplification,
inherited-source preservation, exported-grant revocation and generation exhaustion.
Current native exchange and pressure bootstrap use the joint admission mechanism.

The native admission exercise consumes generation13 in a failed four-step startup,
keeps the scheduler unchanged, denies stale retry and completes one quarantined
cleanup retry. Generation14 then starts two actual isolated tasks and verifies
their timer preemption, successful exits and complete reclamation. A fresh boot
must reproduce this together with all prior containment/IPC/deadline tests and
ordinary unsigned denial. The checkpoint carries the observed counts and hashes.

The trusted declaration does not independently authenticate a manifest, image
signature or arbitrary service layout. General executable loading, bootstrap
argument delivery, resource policy, repeated start/restart supervision, sustained
budgets, interrupt-driven idle and SMP admission remain open. Some older diagnostic
paths still use their own explicit bootstrap sequence. The native retirement test
does not qualify every possible later scrub/free failure as generally supervised.
No service isolation or usable ISO is inferred solely from this admission API.

Next: sustained execution policy and init/service ownership, confined console/input,
shell, read-only bundled files and two applications before optical ISO acceptance.
Full microkernel, PooleGlyph/PDC, accessible PooleGlass and production gates remain.

The qualification profile is not the future demo startup path. Keep exhaustive
diagnostic workloads out of normal session boot, with a separately selected
qualification image/profile and unchanged evidence requirements. At201 of208
bootstrap pages, diagnostic/code layout separation or a reviewed capacity migration
must precede exhaustion; do not silently remove checks to make room for services.
