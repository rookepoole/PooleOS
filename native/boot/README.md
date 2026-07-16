# Boot

PooleBoot, raw reviewed UEFI bindings, boot manifest verification, boot protocol generation, and firmware-handoff tests live here. No third-party production bootloader may be substituted.

The current `pooleboot-fixture` crate is an empty `x86_64-unknown-uefi` qualification input. It returns success immediately and does not discover firmware protocols, load PooleKernel, or satisfy any N5 boot gate.
