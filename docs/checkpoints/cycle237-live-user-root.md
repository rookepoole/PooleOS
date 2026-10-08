# Cycle 237: Live User Root Switch And Restore

Date: 2026-10-07. Pre-production. USI-1, N9/N12/N13.3,
`N13-USER-ENTRY-LIVE-001`. `FLAG-N13-USERSPACE-ISO-001` stays open.
No checklist item or production phase closes.

## Implemented

The development-only selector 23 connects PKUSER1/2/3 to actual CPL0 execution.
PooleBoot excludes all 22 other scenario features when user-root is selected;
the default image still stops before unsigned kernel transfer.

The new bootstrap access policy checks exact PMM handles, generations, owners,
shapes, DMA32 bounds and disjoint ranges. It allows writes only to the 13 owned
pages and read-only access to five boot table pages. The private physical adapter
checks the original CR3, IF-clear state and supervisor/write-back identity
translation before each word access. It installs no temporary mappings and is
never used while the task root is active. Existing firmware identity mappings
are a bootstrap precondition; they are not copied into the owned task root.

The probe allocates four task tables, one RX user-code page, one RW/NX user-stack
page, four guarded supervisor-entry-stack pages and three entry-stack tables.
It scrubs data, installs an unexecuted static UD2 payload, prepares the root and
proves all five retained allocations reject premature free. PKUSER3 re-audits
the complete mappings/retention/context and performs the actual CR3 write.

While on the candidate root, the kernel reads CR3 and writes/reads a sentinel at
the guarded supervisor-stack top. The sentinel binds candidate address and
allocation generation. Retirement performs a fresh flushing write of the boot
root before detaching, verifies the sentinel through the restored physical
adapter, scrubs six data pages and releases all 13 pages. Both guest runs finish
with zero allocated pages. Execution remains on the existing kernel stack;
writing the new stack is not a claim that an interrupt has entered through it.

The linker reserves 160 image pages instead of 149, within the unchanged
192-page boot mapping limit. Page alignment and R/RX/RW separation are preserved.
No boot/handoff/stack mapping-window limits were relaxed.

## Evidence And Repairs

The final receipt is `runs/native-user-entry-readiness.json`, SHA-256
`9D4AF96F0267010526F7BED917CF12546410379AB2EF97432244349E90AD3BCA`.
It binds 734 native/build/oracle inputs. Final retained capture:
`outputs/cycle237-nativecloseout.json`, 80.703 seconds, unchanged source and
owner report, log `37CD934A017B3C72169D05BF5048632CB88DADEA542BB330178CE43E95AFDB43`.

- 288 debug kernel tests, including four new bounded-access tests, pass.
- 42 repeated optimized user-entry tests and five compile-fail tests pass.
- Ten boot-exit and 13 Python oracle/regression tests pass.
- Two conflicting feature builds reject with the required compile error.
- Formatting and freestanding kernel/library checks pass.
- Two fresh QEMU/OVMF user-root guests emit 32 matching serial/debugcon markers
  each; 26 hostile marker mutations per run reject. Numeric binding tests also
  reject changed roots, generation, sentinel, resource counts and promoted claims.
- A third fresh default boot retains unsigned denial with no kernel entry.
- Both PooleBoot variants reproduce across two clean builds. Development media
  generation repeats byte-for-byte and is independently inspected. This is not
  two-builder reproduction of the complete OS.

The canonical kernel is 583,320 bytes in a 160-page image, SHA-256
`609BD44C16DF888776ED99E22E14FC8BEFBC9B6EFB5F54440B9CE54FFA126018`.
Guests use fresh copied firmware variables, read-only virtual media, headless
TCG, no guest network or host acceleration, loopback QMP and 45-second bounds.
This is virtual disk test media, not the requested optical ISO.

Failures are preserved under ignored outputs:

1. `cycle237-livefirst`: linker text capacity exceeded; no guest ran. Expanded
   the bounded image without changing its permission policy. Capture log:
   `0801A9CC298D94A77ED501B78E97F73CA0E18CB0C1AF44B4F16E21276A5F74D9`.
2. `cycle237-hostandlive`: host checks passed but first guest denied activation.
   `cycle237-diagnosed` narrowed this to the initial CPU snapshot. The adapter
   used capability-mask value `CPU_MSR_APIC_BASE` as an RDMSR address. Replaced
   it with the existing `read_apic_base()` accessor for MSR 0x1B. This is a real
   privileged-adapter defect that host mocks did not detect. Capture logs:
   `D35B5CE1B4A9105E5F12BAC8A7E1837846E926D70ED95A122CB49CCE8D4F9B53`
   and `2C2C716CB74564FF0F4BFF2D70369864D08DA93B3E5518A2253C2FCCFA18E34F`.
3. `cycle237-apicfix`: both probes succeeded, but the host default-denial runner
   referenced a nonexistent extractor. It failed rather than declaring success.
   Reused the existing transfer marker extractor and reran all three guests.
   Log `FD5B6440FC7F00B80E5B6E0A69C1AF3C727FB6377BBEF783B4F1581BEBE37A63`.
4. `cycle237-nativefinal`: all checks passed. Final review added the missing
   emergency-panic mapping for 0x101F and replayed the entire focused suite into
   `cycle237-nativecloseout`; only that last source-bound receipt is current.

A format invocation initially supplied the wrong toolchain directory and failed
before editing; the pinned local toolchain environment then succeeded. No tool
installation or global PATH change occurred. Historical Cycle 236 receipt is
frozen byte-for-byte in `tests/fixtures/cycle236-user-entry-readiness.json`, hash
`0CE9612DEF69AA63110F6E5A6D4D016DDE8D8F2D7E62A95E36938930D873CAE8`.
The captured marker fixture is only parser-test input, not current execution.

The register-address repair agrees with [AMD64 System Programming revision 3.44,
Figure 16-2](https://docs.amd.com/v/u/en-US/24593_3.44_APM_Vol2), which specifies
the APIC base MSR at 0x1B and bootstrap-core indication at bit 8. This reference
does not externally validate the implementation.

## Remaining Work

This is actual CPL0 address-space integration, not ring-3 task execution. Timer
and MMIO mappings, user descriptors/TSS/IRETQ, scrubbed architectural state,
fault containment and preemptive recovery are next. The static user payload is
not executed. No interrupts, user faults, concurrent CPUs, DMA, general physical
access, syscalls, capability IPC, native shell, new ISO or production readiness
are established by this profile. Trusted physical/CPU adapters still rely on the
serialized one-BSP lease and retained supervisor mappings.

Next move: extend owned supervisor mappings with narrowly permitted timer/MMIO
lifetime and cache policy, prove timer recovery under the candidate root, then
enter a sanitized user context with contained faults. Keep kernel mechanisms
separate from later user-space services and shell. Full N0-N39 development
continues after the integration ISO.

All 8,996 locked requirements, 59 additions, 40 phases and 301 subphases remain.
PooleGlyph Phase 65 archive and the owner's modified conformance report remain
unchanged; Phase 66 is not implemented by this work. The 25 stale component
admissions remain stale and the full exact-candidate suite has not run. No merge,
release, signing, key operation, privileged host probe, firmware modification or
physical-media write is authorized by this focused result.

The added development feature changes the shared boot qualifier. Consequently
22 of the 27 retained Python source closures are now stale as well; only entry,
symbols, policy, revalidation and errata-policy source closures remain current.
The aggregate source guard correctly fails. The original execution-source ledger
is preserved byte-for-byte, not rebound to unexecuted inputs. This distinction is
recorded separately from the 25 stale native admissions and the new PKUSER3
source-bound guest receipt.

The first metadata run passed 94/98 tests in 49.471 seconds (capture 50.312),
log `C7429478FB6B23C52327EA7E8DA756C451606D29D75D618AD243DFC5B66D7E66`.
It exposed a stale expected status and three assertions assuming boot-trust and
shared-loader receipts still applied after the boot manifest changed. Their
actual gates reject stale bindings; those production prerequisites are now
explicitly marked pending rather than requalified by editing receipt hashes.
The firmware prerequisite remains current. Historical evidence bytes are intact.

Corrected metadata replay passes 98/98 in 49.382 seconds (capture 50.204), with
unchanged source and owner report, log
`FDA9613EBD5AA6242C80691959CD7D181ED721997AE1F6236A7AE9EDF2C6A758`.
The architecture baseline binds 433 files and discovery finds 1,253 Python test
methods. Discovery is an inventory, not a claim that the entire suite ran.
