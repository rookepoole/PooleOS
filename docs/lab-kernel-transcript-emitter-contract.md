# Lab Kernel Transcript Emitter Contract

Status: draft v0.2

The Buildroot overlay now includes `/usr/bin/pooleos-kernel-pgvm2-transcript-contract`. It is a disabled contract script for the future kernel PGVM2 loader transcript. It writes the exact markers consumed by `tools/verify_kernel_pgvm2_loader_transcript.py`, but the Lab smoke and init paths do not call it yet.

Default behavior:

```text
POOLEOS_KERNEL_TRANSCRIPT_ENABLE=0
```

With the default disabled setting, the script writes a non-claiming transcript to `/var/lib/pooleos/runs/kernel_pgvm2_loader.transcript.txt`, keeps `POOLEOS_KERNEL_BOOTED_PATH false`, keeps both enforcement claims false, and records `negative_claim_guard PASS`.

Enabled behavior is reserved for the future real kernel loader path:

```text
POOLEOS_KERNEL_TRANSCRIPT_ENABLE=1
POOLEOS_KERNEL_HANDOFF_SHA256=<sha256>
POOLEOS_POOLEGLYPH_SOURCE_ANCHOR_SHA256=<sha256>
POOLEOS_POOLEGLYPH_PARSER_PROMOTION_RECEIPT_SHA256=<sha256>
POOLEOS_KERNEL_EXPECTED_INSTRUCTIONS=<count>
POOLEOS_KERNEL_ACTUAL_INSTRUCTIONS=<count>
POOLEOS_KERNEL_BUILD_ID=<build-id>
```

The script refuses enabled emission if the handoff digest, either PooleGlyph digest, or expected count is missing. In both disabled and enabled modes it emits `POOLEOS_KERNEL_GUEST_ENV` audit lines containing the exact source-anchor and parser-promotion environment values used by the shell contract. The export receipt requires each line exactly once and compares both values to the host verifier's expected digest pair. The script is hashed by `qemu_boot_marker_image_binding` as a guest support file so rootfs continuity can later prove the emitted transcript contract came from the reviewed overlay.

After an operator or booted lab path runs the contract, regenerate `kernel_pgvm2_loader_output.json` with `tools/verify_kernel_pgvm2_loader_transcript.py`, then emit `lab_kernel_transcript_export_receipt.json` with `tools/emit_lab_kernel_transcript_export_receipt.py`. The receipt hash-binds the verifier output and transcript, records the exact guest PooleGlyph digest pair, and classifies the run as pending, disabled/non-claiming, or enabled and fully verified.

## Boundary

This contract does not prove a kernel loader exists. It only reserves the lab-side transcript surface and keeps the emitter out of autostart until a real kernel-owned path is implemented.
