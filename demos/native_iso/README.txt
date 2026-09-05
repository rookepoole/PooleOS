PooleOS Native Demo 0.1.0
Copyright Rooke Poole. Source available; commercial rights reserved.

This is an unsigned, emulator-only engineering demo of original PooleBoot
and PooleKernel. It is not Linux, a desktop, an installer or a production OS.

The frozen profile runs on QEMU/OVMF with four SandyBridge virtual CPUs,
512 MiB RAM, no network, no host disk, and read-only optical media. Secure
Boot is not enabled in this development VM. No host firmware is modified.

The display shows the demo-only PooleGlass static optical-glass emblem and
wordmark. Production PooleBoot source and kernel bytes are unchanged.
Serial diagnostics show
native kernel entry and the bounded PKLOCK1 multi-CPU lock exercise. A final
POOLEOS:KERNEL:LOCKS-RESULT PASS contract=PKLOCK1 marks successful completion.
The static logo is not a desktop, compositor or animated boot transition.

Use the accompanying host demo launcher and its exact qualification receipt.
This ISO is optical-only, not a hybrid USB image. Do not install or flash it.
Physical hardware, persistent storage, interactive applications and live
reclamation integration are not qualified by this demo.

Native source baseline: 73cfdb1a903c73f5e20c4b4cc78ccf9cab150d78
Source: https://github.com/rookepoole/PooleOS
See LICENSE.TXT and MANIFEST.JSON for rights and exact component identities.
