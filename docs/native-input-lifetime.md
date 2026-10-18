# Native Input Lifetime Boundaries

Cycle301 extends the opt-in PWS1 interactive window service. It does not change
the user ABI, device grants, process leases, mapping count or code/stack budgets.
The original native PooleBoot/PooleKernel architecture remains the foundation.

## Ownership Policy

An asynchronous focused-surface retirement or identity replacement removes
keyboard focus and drag capture. Neither Terminal nor a surviving app inherits
pending input. The service clears decoded ownership and enters raw-controller
quarantine. A fresh valid pointer press after observed release selects focus.
If no release packet arrives after the boundary, an initial click-and-release is
consumed; the following press selects focus. This conservative interaction is
explicit, not a claim of seamless one-click recovery in every pointer state.

Each service turn still reads at most32 device values. Quarantine persists across
quota exhaustion and transport errors; only an actual empty read ends it. Raw
keyboard makes/breaks update the held-key fence without delivering characters.
At quiescence, observed held keys and partial prefixes remain fenced. Mouse
packets update cursor position and physical release but cannot click, drag,
minimize or restore a window during quarantine. Controller reset uses the same
policy and cancels affected input queues. Surface generations remain trusted
lifecycle observations, never application claims.

Interactive polling returns a bounded three-region damage plan before rendering.
The polling stack frame therefore expires before nested drawing begins. Ordinary
profiles retain their original rendering path. No framebuffer mapping is added
to application address spaces; applications continue to submit authenticated
bounded text-surface messages.

## Failure Diagnostics

Unexpected critical-service termination retains the unconditional kernel stop.
Immediately before that stop, bounded numeric records distinguish exit, fault,
invalid return, cancellation, call-limit/counter exhaustion and watchdog reason.
Fault diagnostics include the instruction, address, error and vector already
recorded by the trap handler. They do not resume exceptions or dump live memory.

Native candidates exposed real user-stack overflows despite passing host tests.
The exact instruction/address and disassembly are retained in the checkpoint.
Moving polling alone was insufficient; separating polling from composition was
required. This repair preserves the one-page guarded user stack,36-page guarded
kernel stack,208-page kernel image capacity, four/seven code-page profiles,
eight VM mappings and four total/two-per-owner process leases.

## Verification Contract

Eight Rust regressions cover unread keys after retirement, quota versus empty
reads, held pointer capture, partial key/mouse streams, controller reset, errors,
and identity replacement without disturbing the peer queue. The initial host
counterexample delivered an unread A to Terminal after focused-app retirement.
The bounded quarantine repair rejects that transfer.

The native challenge performs two controlled retirements: Numbers faults and
Text exits, each while focused with a drag and Shift held. It observes drag
movement and return, an uppercase A draft, retirement, no implicit focus or peer
draft input, held-pointer motion, release, fresh-click focus and exact lowercase
status commands before releasing Shift. The two control commands use exactly24
serial bytes; the remaining308 bytes of the332-byte shell workflow use device
keyboard input. These channels must never be conflated in evidence.

Each native run requires24 ordered lifetime observations and six existing
lifecycle barriers, exact transcript and marker validation, source/ISO identity,
bounded captures/actions and owned-VM cleanup. QEMU is headless; VirtualBox uses
an explicitly owned disposable visible VM with no physical disks, network,
shared folders, USB or host-cursor movement. Diagnostic runs are separately
labelled and cannot qualify a preview. Final qualification additionally replays
independent optical builds and controls, ordinary interactive input and legacy
capacity regressions. The checkpoint and build plan record actual results.

## Remaining Work

An empty i8042 poll is a software observation, not proof that a physical device
has no internally buffered future report. Native arbitrary controller backlog,
continuous typematic stress and transport-reset injection remain unqualified.
Host reset tests are not native reset qualification. The serial control channel
is test instrumentation, not a proposed graphical application control API.
One final VirtualBox ordinary-input attempt loses the COM1 observation stream
mid-record while COM2 reports the app fault, and correctly fails qualification.
Its cause remains unproven; the bounded transmitter's disable-on-timeout policy
is a candidate. An unchanged replay is not a diagnostic-repeatability guarantee.
Reliable bounded diagnostic delivery remains required under the N3 preview flag.

Two archived intermediate application-movement frames contain partial cursor
repainting. Their immediate next recorded movement frames at the same positions
contain complete cursors; the evidence package binds both hashes. This is not
atomic presentation. The separate pointer and lifetime probes retain their
full cursor-pixel checks. Double buffering/presentation atomicity remains open.

Compositor restart/resynchronization, event-driven waits, fairness under rendering
load, measured latency, production stack-depth/high-water accounting and scalable
address-space layouts remain required. So do graphical application launch,
persistent files/editing, richer input, accessible PooleGlass, isolated drivers,
PooleGlyph/PDC integration and all open N0-N39 production gates. No signing,
release publication, full canonical replay or production readiness is implied.
