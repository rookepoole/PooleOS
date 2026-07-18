# Native Boot-Services Exit Contract

`PBEXIT1` is the bounded Cycle 106 contract, reused and requalified by Cycle 107, for leaving UEFI boot services without yet entering PooleKernel. It is an N5.8 development proof, not a production boot claim.

## Ordered Boundary

All allocation, page-table construction, retained-range validation, and fixed-buffer setup finish before the first exit attempt. Each attempt then performs exactly:

1. `GetMemoryMap` into a preallocated 1 MiB buffer.
2. Descriptor-stride-aware normalization and final `PBLIVE3`/`PBP1` construction in the retained handoff pages.
3. `ExitBootServices` with the map key returned by that capture.

Only `EFI_INVALID_PARAMETER` may retry, with a fresh map, and at most four attempts are allowed. Any other failure after the first attempt is terminal. The loader never returns to UEFI after an exit attempt begins.

## Success State

On success, PooleBoot disables interrupts, rechecks the retained PBP1 bytes, emits evidence through direct COM1 and QEMU debugcon port I/O, records zero firmware calls after exit, and halts forever at `STOP BEFORE TRANSFER`.

The retained objects are the loaded kernel pages, six distinct PBART1 page ranges, four private page-table pages, eight guarded stack pages, and 256 read-only handoff pages. Their exact addresses, artifact roles/digests, and mapping fingerprint are cross-bound between `PKMAP2`, the final PBP1 core/artifact/memory-map records, and the live marker transcript.

## Non-Claims

The exited handoff remains development-only. It has no verified manifest or artifact signature, required entropy record, kernel-entry profile, or transfer authorization. The initial-system and other PBART1 bytes are loaded but untrusted and unapplied; no PooleKernel or initial-system instruction executes and no microcode is applied. Target firmware, physical hardware, signing, ISO publication, and the N5 exit gate remain open.
