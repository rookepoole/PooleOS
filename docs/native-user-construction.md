# Transactional Native User Construction

PKUSER11 is a bounded one-BSP construction mechanism, not a public spawn ABI.
Both sequential-task and preemptive-peer native constructors use it.

## Ownership

`Construction` owns five non-clone retention tokens: four user page-table pages,
one code page, one user-stack page, four entry-stack pages and three supervisor
table pages. Allocation reserves a unique retention identity before allocating;
there is no successful allocation without a token. Copied allocation handles
cannot free retained memory. Tokens, not structurally identical handles from
another allocator, identify the owner.

Construction validates ownership before physical access. Payload bounds and
alignment are checked, data pages are cleared/read back, payload words are
copied/read back, and user/supervisor mappings are built. Successful preparation
transfers the existing tokens directly into `PreparedImage`; it never releases
retention and reacquires it. Failed preparation returns the same token set.
The partially written root has never been published to a CPU owner.

Abort clears and reads back the entire owned batch, then finishes the memory
access operation, before freeing any allocation. Failed memory access or
readback retains all pages. Failed allocator release returns its exact token;
already released members are removed from the owner. Cleanup can retry without
releasing a stale handle. Construction cannot restart after abort or transfer.
No fallible cleanup is hidden in `Drop`.

`Access::partial` gives the native cleanup adapter access only to present,
correctly shaped allocations. Original-root identity, cache, supervisor and
write permissions remain checked before every physical dereference. A native
constructor failure carries its owner and optional adapter even when cleanup
fails. Slot-insertion failure also carries the CPU image, driver and adapter.

## Executed Coverage

Seven host tests cover each allocation boundary, wrong-manager identity,
payload shape, failure after writes have taken effect, corrupted readback,
read/finish failure, cleanup retry and successful ownership transfer.

Each fresh native guest keeps the original 32-page quota. With two live tasks,
a third construction exhausts that quota after five pages and rolls them back.
After the first task exits, six later construction failures occur while its
healthy peer remains suspended. Each follows a real physical write, each then
encounters an injected cleanup failure, and each retries successfully. All
83 construction pages are scrubbed/read back and released. The peer resumes
and exits84. The original14 peer-containment cases remain required.

## Stack Failure And Repair

The first integrated construction path overflowed the existing bootstrap stack.
A native diagnostic recorded kernel #PF(2) at RIP `FFFFFFFF8006B39D`, with RSP
and CR2 `FFFFFFFF800C0578`, inside the unmapped lower guard. Disassembly identifies
the faulting store as a stack probe in PMM `direct_map_manifest`, nested below
the constructor's mapping validation.

Separating task installation from construction, and keeping fault-case execution
in a separate frame, reduces the overlapping constructor temporaries. In the
inspected repair binary, `Peer::new` reserves `0x2988` instead of `0x4838` bytes;
the peer runner reserves `0x5358` instead of `0x5D98`. Guard pages, the36-page
bootstrap stack, memory validation and quotas were not relaxed. Fresh guest
execution validates these tested paths, not a whole-program stack bound.

## Remaining Work

USI-1 remains partial. General executable/service admission, recovery from
unexpected persistent quarantine, final slot-commit recovery, and automatic
resource growth are not qualified by these fixed tasks. The original one-shot
boot probe still has its older fatal-on-construction-error path. No public spawn
capability, arbitrary executable, IPC or user session is enabled.

Complete stack-depth/high-water evidence across constructors, cleanup and trap
nesting remains required under N3.7 and the open N13 integration flag. Native
fault injection covers quota and writes/cleanup; other host-covered failures
are not silently promoted to native coverage. A deliberately injected allocator
failure after partial batch freeing is not covered by this new suite.

Next: pending/late timer shutdown recovery, terminal-subquantum accounting and
independent missing-IRQ recovery, then capability IPC and confined services.
Native #SS delivery, XSAVE/SMP/async/SMAP, hardware and full release qualification
remain open. The usable ISO milestone does not replace the full N0-N39 goal.
