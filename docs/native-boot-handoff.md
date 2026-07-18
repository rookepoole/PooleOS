# PBP1 Poole Boot Handoff

Status: Cycle 104 qualified protocol plus temporary live pre-exit producer, pre-production and non-promoting
Requirement: `N5-BOOTPROTO-001`, `ADD-BOOT-001`, source section `014`, subphase `N5.8`

## Boundary

PBP1 is the byte contract that PooleBoot constructs and that the future PooleKernel consumer will reject before dereferencing untrusted boot data. It is not a Rust ABI structure. Every integer is manually encoded little-endian, every offset is relative to the start of the bounded container, and all persistent layout is independent of compiler structure padding.

`native/handoff` is the dependency-free `no_std` encoder and decoder. `native/livehandoff` adds a bounded allocation-free producer that honors the firmware-reported UEFI descriptor stride, normalizes and sorts every range, and builds a development-only pre-exit profile. `native/boot/src/livehandoff.rs` supplies the live UEFI allocation and transcript adapter. `runtime/native_boot_handoff.py` and `runtime/native_live_boot_handoff.py` are independent host oracles; neither enters the firmware chain.

## Wire Contract

The 64-byte header carries exact PBP1 magic, writer major/minor, minimum reader minor, total size, a 32-byte descriptor table geometry, present and required feature masks, and an IEEE CRC-32 over the complete message with the checksum field zeroed. The complete container is at most 1 MiB and has at most 32 records.

Descriptors and payloads are strictly ordered by record type. Each descriptor carries its own payload CRC-32. Offsets, 8-byte alignment, zero padding, zero reserved bytes, element geometry, and final container length are canonical. A decoder rejects overlaps, gaps, duplicate types, trailing data, integer overflow, unknown flags, incompatible known-record revisions, and any unknown required record or feature.

PBP1.0 defines core state, a normalized memory map, framebuffer metadata, canonical firmware-table references, loaded artifacts, UTF-8 command line, boot-device identity, a confidential random seed, early log, CPU bootstrap facts, timestamps, and a copied TCG event-log reference. Exact offsets and fields are in `specs/native-boot-handoff-contract.json`.

## Version Rules

Major versions are incompatible. A reader accepts major 1 only. It rejects a writer whose `minimum_reader_minor` is newer than the reader. A newer minor may append an optional extension record only in the `0x8000..0xFFFF` range; the record must still be bounded, checksummed, ordered, and structurally canonical. Unknown required records and unknown required feature bits always fail closed.

Known record layouts never change in place. A compatible addition receives a new record type. A semantic or transfer-convention break requires a new major version.

## Addresses And Transfer

Field names distinguish physical and virtual addresses. Memory-map, framebuffer, firmware-table, artifact-storage, TCG-log, CR3, and UEFI table addresses are physical. Kernel image, entry, stack, and the mapped handoff pointer are canonical x86-64 virtual addresses.

The future transfer convention is a direct jump after successful `ExitBootServices`: `RDI` is `handoff_virtual_base`, `RSI` is exact byte count, `RDX` is the little-endian PBP1 magic value, `RSP` is the 16-byte-aligned initial stack top, and `CR3` is `page_table_root_physical`. Interrupts and the direction flag are clear. Other registers and floating-point state are unspecified. The handoff mapping is read-only at entry.

PBP1 core state is phase-sensitive. Before `ExitBootServices`, `BOOT_SERVICES_EXITED` is clear and both stack and CR3 must be zero; such bytes are a construction snapshot and can never be transferred. After successful exit, both fields must be nonzero and correctly aligned. Cycle 104 exercises only the pre-exit form, verifies that the kernel-entry profile rejects it, transcripts and rechecks its exact bytes, and releases the temporary container.

PooleKernel's kernel-entry profile additionally requires core, normalized memory map, firmware tables, loaded artifacts, boot device, random seed, and CPU bootstrap records; successful boot-services exit; at least firmware-RNG entropy quality; and hash plus signature verification for the kernel and initial system. This validator is a policy precondition, not evidence that those actions occurred.

## Firmware Rationale

UEFI's memory-map descriptor size is explicitly extensible, and the current map key must be used for `ExitBootServices`. PBP1 therefore does not expose the volatile map key or copy raw descriptor strides into the kernel ABI. PBLIVE3 uses the returned descriptor size and version, preserves source type and attributes, rejects malformed or overlapping ranges, requires the exact artifact roles 1 through 7, and records no volatile key. PKLOAD6 allocates the final kernel, six auxiliary artifact, table, stack, and handoff objects; recaptures the map after those allocations; uses that map's current key for bounded `ExitBootServices`; makes no later firmware call; and retains read-only PBP1 bytes. PBTRUST1 separately parses policy and acceptance-state development candidates and denies the unsigned policy before exit; neither candidate is embedded as self-authenticating PBP1 authority. The current bytes remain a nontransferable development profile because signatures and an authenticated monotonic backend are absent. The official UEFI 2.11 requirements are [GetMemoryMap and ExitBootServices](https://uefi.org/specs/UEFI/2.11/07_Services_Boot_Services.html).

UEFI configuration tables are GUID/pointer pairs and may grow over time. PBP1 retains canonical GUID bytes plus validated physical range metadata instead of fixing ACPI and SMBIOS to host-language pointer structures. See the [UEFI System Table and Configuration Table](https://uefi.org/specs/UEFI/2.11/04_EFI_System_Table.html).

## Ownership

PooleBoot owns the container until the transfer jump; PooleKernel owns it afterward. The container and embedded records are immutable after finalization. Pointed-to external physical ranges transfer to PooleKernel and remain reserved until a later typed owner copies, parses, or delegates them. No UEFI boot-service pointer is retained. Runtime-service pointers are both present only when the retained-runtime flag is set.

The Cycle 104 PBLIVE1 container has a narrower lifetime: PooleBoot owns it, performs no writes after logical finalization, proves its bytes unchanged across transcript emission, and then frees it before returning. This is logical immutability evidence, not a hardware read-only mapping or ownership transfer.

Random-seed bytes are confidential and marked `redact`. They must never enter diagnostics, crash records, receipts, or public evidence and must be zeroized after key derivation. Golden-vector seed bytes are deterministic public test data, not entropy.

## Qualification

Run:

```powershell
python tools/generate_native_boot_handoff_vectors.py --check
python tools/qualify_native_boot_handoff.py
```

Qualification compiles and tests the Rust codec on the pinned host target, builds the same `no_std` library for UEFI and freestanding kernel targets, reconstructs three exact golden vectors, runs 32 semantic negative controls, and sends 16,384 deterministic mutations to both decoders. The full vector's kernel-entry state is synthetic.

## Nonclaims

PKLOAD6 separately proves that PooleBoot opens live PBC1/PSM1/PKELF1/PBART1/PBTP1/PBTS1 inputs, retains kernel/six-artifact/table/guarded-stack/handoff pages, reparses all six exact retained inner files with mandatory development denial and zero effects, cross-binds fourteen PBTRUST1 policy/state facts and denies the unsigned policy, produces exact PBLIVE3 bytes from the final map, reconstructs identical bytes from serial and debugcon, cross-binds every retained range, calls `ExitBootServices`, makes zero later firmware calls, and halts before transfer. It does not authenticate the manifest, artifacts, trust policy, revocation state, or acceptance state; provide a monotonic writable backend; authorize or apply auxiliary payload semantics; independently reparse the exact retained bytes and selected trust state in PooleKernel; install the retained CR3/RSP as final state; execute transfer assembly; consume PBP1 in PooleKernel; test target firmware; or satisfy N5. CRC-32 and FNV are corruption/equality checks, not authentication. Finite corpus and differential agreement is not a proof over every input. No production, signing, Secure Boot, measured-boot, TPM, release, or physical-hardware claim follows.
