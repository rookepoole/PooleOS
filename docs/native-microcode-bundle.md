# PooleOS PMCU1 Microcode Package

Selected move: `N5-MICROCODE-SEMANTICS-001`

Phase boundary: N5.6 with future N7.2 and N24.4 dependencies

Contract: `PMCU1` version 1.0
Status: candidate, pre-ABI, synthetic-fixture-only, non-promoting

PMCU1 is the Poole-owned wrapper for an exact set of opaque CPU-vendor
microcode patch bytes. It freezes identity, trust, bounded selection, revision
floors, early-apply timing, all-processor verification, receipt, failure, and
reset-based known-good recovery rules before PooleBoot or PooleKernel is
permitted to interpret or apply such an artifact.

The parser cannot update a processor. The Python and Rust implementations have
no privileged revision probe, `WRMSR`, firmware call, CPU rendezvous, driver,
or physical-media writer. Every checked-in patch and revision is visibly
synthetic qualification data and must never be applied.

## Source And Target Boundary

The exact Tier 1 user-mode CPUID observation records `AuthenticAMD`, family
`0x1A`, model `0x44`, stepping `0`, encoded as CPUID signature `0x00B40F40`.
AMD identifies the Ryzen 7 9800X3D as a Zen 5 Granite Ridge AM5 product. The
current microcode revision, applicable errata floor, vendor patch bytes,
vendor-container authentication, redistribution rights, firmware reset
behavior, and privileged native observation remain open.

Primary research inputs are:

- AMD Ryzen 7 9800X3D product specification;
- AMD Family 1Ah revision guidance and AMD64 system-programming reference;
- Intel's public microcode update and minimum-runtime-revision guidance as a
  comparative x86 source, not as an AMD format claim;
- the UEFI PI multiprocessor-services boundary as firmware lifecycle context.

PMCU1 does not import Linux, Debian, Buildroot, or their userspace. Public OS
implementations may inform later clean-room review only under ADR-0002; they
are not a production dependency or evidence for AMD's private container.

## Binary Layout

All integers are unsigned little-endian values. The maximum PMCU1 payload fits
inside the existing one-MiB PBART1 envelope.

| Region | Bytes | Rule |
|---|---:|---|
| Header | 512 | Fixed PMCU1 identity, policy, table bounds, five evidence digests, body digest, and self digest |
| Patch table | `count * 128` | One to 32 dense records sorted by strictly increasing revision |
| Payload region | Bounded by envelope | Dense 16-byte-aligned opaque vendor payloads |

The header binds:

- exact architecture, vendor string, CPUID signature/mask, and platform mask;
- security floor, previous-known-good revision, and preferred revision;
- highest-eligible selection, early kernel apply, all-processor, resume,
  rollback, mixed-revision, post-verification, and failure policies;
- source, trust, license/redistribution, revocation, and hardware-profile
  evidence identities;
- SHA-256 over the complete table and payload region;
- SHA-256 over the complete header with its own digest field zeroed.

Each 128-byte record binds a sequential ID, required behavior flags, exact CPU
identity, revision, minimum current revision, security floor, payload offset,
size, alignment, opaque vendor-header length, payload SHA-256, and a metadata
SHA-256. Payloads are nonempty, bounded, nonoverlapping, and cover the payload
region exactly. Unknown flags, bytes, records, gaps, duplicate roles, and
trailing data fail closed.

## Selection

Selection is a pure bounded function. It neither probes nor mutates hardware.

Normal mode selects the highest compatible, non-revoked record that meets the
package security floor, authenticated rollback floor, CPU identity, platform
identity, and minimum-current-revision rule. An equal or newer accepted
revision is verified and skipped.

Previous-known-good mode selects only the one authenticated known-good record.
If the current session already carries a newer revision, PMCU1 returns
`reset_for_known_good`; it never plans an in-session downgrade. A later
production implementation must prove the exact processor and firmware reset
semantics before this recovery route may be enabled.

No match below a required floor is fatal or routes to bounded recovery. A
missing optional package can be tolerated only when separately authenticated
firmware evidence proves that every processor already satisfies the required
floor and revocation policy.

## Apply Ownership And Timing

PooleBoot may eventually authenticate and stage immutable PMCU1 bytes, but it
must not infer apply authority from parsing. The minimal privileged application
mechanism belongs in PooleKernel because it must coordinate bootstrap and
application processors before normal scheduling. Selection, revocation,
update-channel, and recovery policy remain outside the mechanism-oriented
kernel.

An apply plan requires all of the following:

1. Exact PBART1 role/version/hash and PMCU1 identity.
2. Verified outer, inner, manifest, vendor, and revocation trust evidence.
3. Approved redistribution or an approved user-supplied intake route.
4. Trusted exact CPU identity and per-processor current-revision observations.
5. Authenticated monotonic security and rollback floors.
6. Complete homogeneous processor inventory and a quiesced update set.
7. Early PooleKernel execution before affected features and user scheduling.
8. Bounded payload, patch, processor, and receipt capacities.
9. Explicit kernel apply authority with no firmware or media mutation request.

The planned production sequence applies on the bootstrap processor before
affected feature enablement and on each application processor before it enters
the online scheduling set. Resume and hotplug reapplication remain future
N24 work and require exact architecture guidance.

## Post-Apply Gate

Before user work can run, the implementation must:

- read and record every processor's before and after revisions;
- reject any regression, floor violation, revoked revision, failed processor,
  or mixed revision set;
- rerun CPUID and revalidate the exact feature and mitigation policy;
- retain artifact, payload, CPU, firmware, before/after, stage, and result
  identities in an authenticated receipt;
- quarantine or halt on mixed success without scheduling ordinary work;
- preserve a reset-based known-good recovery route.

A failed or mixed update cannot be repaired by attempting a lower revision in
the same session. The safe action is bounded halt/quarantine/recovery, followed
by a separately proved reset and known-good selection path.

## Qualification

`tools/qualify_native_microcode.py` requires:

- four Rust host tests, rustfmt, clippy, and both freestanding `no_std` targets;
- three exact synthetic golden bundles and their selection samples;
- independent Python and Rust agreement over malformed parser controls;
- 16,384 parser differential cases;
- 16,384 selection differential cases spanning apply, skip, reset, and reject;
- 8,192 post-apply differential cases including mixed-processor failures;
- independent failure of every activation precondition;
- an unsigned-development apply denial.

The all-true context is synthetic test scaffolding for a pure plan. It is not
vendor trust, authorization, target observation, or evidence that an update
can execute.

## Nonclaims

This slice does not provide a real AMD container parser, approved vendor bytes,
vendor authentication, redistribution permission, a measured revision, a
security floor, errata closure, a privileged probe, a kernel apply mechanism,
processor rendezvous, CPUID mitigation reconfiguration, resume/hotplug support,
target-firmware behavior, physical-hardware evidence, or recovery execution.

PooleBoot and PooleKernel do not enforce PMCU1. No CPU microcode, firmware,
driver, disk, boot setting, or physical medium is changed. N5, N7, N24, N38,
N39, the signed ISO, and production readiness remain open.
