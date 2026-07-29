# PINIT1 Initial-System Declaration Bundle

Status: candidate pre-ABI, single-host qualified, non-promoting

`PINIT1` is the bounded inner format for the `initial_system` payload carried
inside the Cycle 108 `PBART1` envelope. It describes candidate components,
services, dependencies, abstract resources, capability routes, and lifecycle
policy. Parsing a bundle is deliberately separate from authorizing activation.

This slice belongs to N5.6 and `N5-INIT-BUNDLE-001`. It does not finish the
broader `N5-INIT-SEMANTICS-001` move because recovery, symbols, microcode,
firmware-manifest, and policy payloads still lack equivalent inner contracts.

## Authority Boundary

A valid declaration does not create a PooleKernel object, allocate a resource,
issue a capability, load an executable, start a service, or authorize an
instruction. Capability IDs and resource IDs are local declaration references,
not physical addresses, virtual addresses, kernel handles, or ambient rights.

Activation is denied unless a caller separately proves all of the following:

1. The outer artifact role and version match the bundle.
2. PBART1 payload and whole-file digests were verified.
3. The PBART1 artifact and PSM1 manifest signatures were verified.
4. Persistent rollback state is authenticated and permits the version.
5. The live kernel ABI and PBP version satisfy the declared floors.
6. Exactly one allowed boot mode is selected.
7. The capability allocator and resource broker are ready.
8. Every embedded component contract is independently verified.
9. Capacity exists to complete or fully roll back the transaction.

The current development media satisfies neither signature condition, has no
authenticated persistent rollback state, and has no running kernel allocator,
broker, or component verifier. Its activation result is therefore a mandatory
failure. The qualifier's all-true context is synthetic branch coverage only.

## Binary Layout

All integers are fixed-width little-endian. The format has a 192-byte header,
8-byte record alignment, exact fixed-size tables, a canonical ASCII name table,
zero alignment padding, and contiguous component blobs.

| Region | Record bytes | Maximum records |
| --- | ---: | ---: |
| Header | 192 | 1 |
| Component table | 80 | 32 |
| Service table | 96 | 32 |
| Dependency table | 16 | 128 |
| Resource table | 48 | 128 |
| Capability table | 48 | 256 |
| Name table | variable | 8,192 bytes |
| Component blobs | variable | 524,288 bytes |

The complete PINIT1 payload cannot exceed `PBART1`'s one-MiB envelope payload
limit. The header carries exact table offsets, counts, byte lengths, version
floors, allowed boot modes, ABI requirements, transaction timeouts, a restart
budget, and SHA-256 of every byte after the header. Unknown flags, versions,
offsets, padding, reserved bytes, counts, sizes, and digests fail closed.

Names are unique, sorted into one canonical NUL-terminated table, and limited
to lower-case ASCII letters, digits, `.`, `_`, and `-`. Empty names, traversal,
slashes, duplicate names, noncanonical ordering, and unreferenced bytes reject.

## Components

An executable component uses candidate format ID `PXABI1`; a data component
uses `PINITD1`. Each record binds exact embedded bytes, SHA-256, image-size
declaration, and destination-alignment requirement. Embedded bytes remain
opaque until the separately gated component contract is verified.

A service may reference only an executable component. This is checked by both
independent validators so a data declaration cannot become a launch target by
changing only a service ID.

## Services And Dependencies

Each service declares bounded start and stop timeouts, restart and failure
policy, explicit readiness, reverse-dependency shutdown, health timeout,
restart window and backoff, state schema, declaration budgets, and a canonical
startup rank.

The root service is required, critical, stateless, non-restarting, and the only
service allowed to hold and then drop bootstrap authority. It cannot depend on
another service. Required services roll back the bundle on failure; optional
services may continue only in the declared degraded mode.

Dependencies are sorted unique `(dependent, prerequisite)` records. The full
strong-plus-weak graph must be acyclic. Startup order is deterministic Kahn
ordering with the lowest ready service ID first. Every service must also be
reachable from the root through strong edges, and a required service cannot
make an optional prerequisite required by implication. Shutdown and rollback
use reverse dependency order.

## Abstract Resources

Version 1 admits only bounded declarations for memory pages, thread slots,
endpoint slots, one address space, and one log sink. Every resource is
revocable and exactly one of shareable or exclusive. Only memory pages may
request zero-on-revoke. Address spaces and log sinks have an exact quantity of
one. No resource record can contain a physical or virtual address.

## Capability Routes

Every capability is revocable and lifecycle-bound. Root capabilities may be
declared only by the bootstrap root or by the resource's provider. Derived
capabilities name an earlier parent, retain its resource and revoke group, and
may only reduce rights and availability. Required availability cannot be
derived from optional availability.

Provider-backed resources may be routed to another service only when that
service directly depends on the provider and the provider starts first. Service
records bind the exact number of held capabilities, distinct resources, and
incoming dependencies, preventing hidden declaration growth.

These checks constrain a future transaction plan. They do not prove the future
PooleKernel capability implementation, handle generations, transitive
revocation, IPC transfer, quota enforcement, or teardown behavior.

## Transaction Model

The future activator must validate the complete bundle and every activation
precondition before allocating or launching anything. It then prepares all
resources, creates all capability routes with attenuation, starts services in
canonical order, waits for readiness, and commits only after every required
service succeeds and the root has dropped bootstrap authority.

Any allocation, route, launch, health, timeout, or readiness failure must stop
started services in reverse dependency order, revoke all issued descendants,
release every resource, and leave no partial committed system. That execution
engine belongs to later PooleKernel and N21 work and does not exist yet.

## Qualification

`native/initsys` is an allocation-free `no_std` Rust validator built for the
UEFI and freestanding kernel targets. `runtime/native_initial_system.py` is an
independent Python encoder and oracle. The host-only line probe exists solely
to compare the implementations.

Qualification requires three Rust tests, two `no_std` target builds, three
golden vectors, 120 normal and hostile controls, explicit unsigned-development
activation denial, and 16,384 deterministic differential cases. The readiness
receipt remains single-host, synthetic, and `production_ready=false`.

The canonical integrated bundle is 1,764 bytes with SHA-256
`FFE7243CEE75963D84905E6C9BF9F0D04310EEDBF097757C32E0EBE30FA0C3ED` and
body SHA-256
`8AFA5770DBAC77ACB2D38A9B72C8AC663843A342759678B8DB3A667CD4AD7EA9`.
It declares three components, three services, three dependency edges, four
resources, eleven capabilities, root service 1, and startup order `1,2,3`.
Live PooleBoot reparses those exact retained bytes from `INITIAL.PBA`,
cross-binds the inner and outer version, and requires development activation to
fail first at the missing outer signature. The independent host oracle
reconstructs the same retained-set result. The aggregate artifact marker keeps
`semantics=not_applied` because parsing and mandatory denial do not authenticate
or activate the declarations; the later boundary marker reports
`semantics=parsed_live_unsigned_denied`.

## Research Basis

The declaration-versus-realization distinction and explicit capability
distribution follow the security lessons in the [seL4 capDL language
specification](https://docs.sel4.systems/projects/capdl/lang-spec.html). Routing,
required-versus-optional availability, and lifecycle ordering are informed by
the [Fuchsia capability](https://fuchsia.dev/fuchsia-src/concepts/components/v2/capabilities),
[availability](https://fuchsia.dev/fuchsia-src/concepts/components/v2/capabilities/availability),
and [lifecycle](https://fuchsia.dev/fuchsia-src/concepts/components/v2/lifecycle)
contracts. Signature, version-floor, and rollback preconditions retain the
separation required by [The Update Framework specification](https://theupdateframework.github.io/specification/v1.0.26/).

These references inform the Poole-authored format; they are not production
dependencies and do not imply API or implementation compatibility.

## Nonclaims

PINIT1 is not signed or ratified. PooleBoot reparses the development bytes;
Cycle 117 adds the independent PooleKernel parser; and Cycle 118 executes that
parser only to reach terminal unsigned denial under the opt-in QEMU transfer.
The kernel does not activate the declarations. No PXABI1
executable ABI is frozen, no embedded component is authenticated, no
service runs, and no capability or resource is created. No persistent rollback
state, kernel transfer, target-firmware result, physical-media result, N5 exit,
ISO, or production readiness follows from this receipt.
