# Kernel

PooleKernel common mechanisms and architecture-specific code live here. General drivers, filesystems, networking, storage policy, PGVM2, PDC policy, and desktop behavior do not.

The x86-64 implementation boundary is `arch/x86_64/`. The current `poolekernel-fixture` crate is an empty `x86_64-unknown-none` qualification input that spins at `_start`; it does not initialize hardware, enforce kernel policy, or satisfy any N6-N15 kernel gate.
