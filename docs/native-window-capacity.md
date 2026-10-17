# PWCODE1 Window-Service Capacity

Cycle298. Explicit development loader profile, not a production executable ABI
or a general increase in application authority. Results belong in the checkpoint
and readiness receipt; this document specifies the acceptance contract.

## Architecture

PUSERBIN1 and `Program::new` retain their four-code-page limit. The ordinary
PooleWindowConsole remains a separate build. `PooleWindowCapacity` uses PWCODE1,
selected explicitly by name during build-time inspection and by
`development-window-capacity` during kernel construction. Only trusted launch
slot2 uses `Program::window_service`; the other five roles use ordinary admission.
This is compiled-in launch policy, not authentication of a filename or ELF.

The opt-in image ceiling is seven RX pages, plus the existing one-page RW/NX user
stack. It fits the existing eight VM mapping slots. It does not enlarge the VM
mapping table, grant a writable code segment, remove stack guards, confer new
device authority, or make user-supplied ELF trusted. All normal code ownership,
full-tree readback, allocation retention, argument, root and retirement checks
remain applicable. The bootstrap access adapter accepts the larger code
allocation only in this feature profile, including rollback before activation.
Its embedded program requires a separate kernel read-only boundary at0x1A000;
the ordinary windows boundary remains0x18000. Kernel image capacity208 pages and
the36-page guarded bootstrap stack remain unchanged. The first attempted link
rejected the old boundary; it did not produce or execute a guest.

The new build shares the real window-service body with the ordinary binary. A
small non-inlined arithmetic startup check is linked at byte24576, on the seventh
code page. The linker rejects a missing, misplaced or oversized probe. The
service cannot enter its normal loop unless the check succeeds. Padding is
intentional test instrumentation, not useful UI logic or a memory optimization;
it demonstrates the upper page without claiming that existing code grew there.
Future service code may use this space only with a separately recorded build
and replay. The fixed-address probe may be relocated/replaced only with equivalent
evidence; deleting it does not retain its native qualification automatically.
The shared body is still compiled into the ordinary four-page regression binary.
Future larger functionality must use an explicit capacity-only instantiation/path
or service separation; simply growing shared code would still fail the ordinary
linker limit. Do not silently opt the legacy binary into PWCODE1 or discard it.

Cargo's [per-binary linker argument](https://doc.rust-lang.org/cargo/reference/build-scripts.html#rustc-link-arg-bin)
selects only this target. The installed pinned compiler/linker, exact binary
inspection and native replay are the compatibility evidence, not documentation
alone. No toolchain upgrade, global configuration or dependency is introduced.

## Invariants

- WC1: ordinary linking, extraction and `Program::new` reject byte16385; the
  explicit service profile rejects byte28673. Unknown profiles fail closed.
- WC2: executable pages are contiguous, owned RX; the stack is separate RW/NX
  with absent guards. Every code leaf, owner offset, alias and extra mapping is
  checked, including the added fifth through seventh pages.
- WC3: all bytes copy and the final partial word/page are zero-padded. Allocation
  counts remain exact. A copy/readback or scrub failure retains ownership until
  complete scrub/reclamation; no partial failure silently releases dirty pages.
- WC4: the capacity build executes its seventh-page startup function before the
  actual service. Both independent builds must be byte-identical. No imports,
  writable segments, non-local object relocations or linked relocations appear.
- WC5: the actual native optical app/file/fault/restart challenge, ordinary
  unsigned denial, sustained all-role progress and window pixels must pass.
  Pointer and keyboard backend/mode claims require their own current guest runs.
- WC6: four-page/default profiles retain independent host regressions. Prior
  receipts remain immutable; reused evidence is labelled, not counted as fresh.

## Scope And Next Work

This capacity profile is a bounded step toward useful application input and
surface lifecycle work. It does not itself add editors, a file manager, persistent
storage, compositor restart, general application input or PooleGlass. It is not
a substitute for eventual service separation, scalable address-space management,
isolated general drivers or the complete native microkernel and PooleGlyph/PDC
production requirements. Seven-page construction tests are not native evidence
unless the corresponding guest actually boots and completes the frozen checks.
