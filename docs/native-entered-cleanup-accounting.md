# Entered Task Cleanup Accounting

Contract PENTEREDCLEANUP1, Cycle313. Kernel N13/N14 development, not promotion.

For an entered task, deferred reclamation requires both scheduler runtime ticks
and dispatch count to equal the Slot's charged ticks and charged slices. Check
before parking and again before ordinary deferred polling or closed-job rescue.
An equal tick total with a different number of charged slices is not equivalent
execution history. Reject without memory access or recovery-budget consumption.

Prepared/unentered tasks keep their existing special case: scheduler selection
may precede cancellation without user entry. Existing quiescence, pending-charge,
unmeasured-runtime, exact identity, closed membership and retained-token checks
remain. Three ordinary retries and the separate single post-exhaustion attempt
are unchanged. No additional authority or retry reset is introduced.

Host tests exercise two measured child slices, exit and supervisor cancellation,
successful and persistently failing recovery, mismatched one/three-dispatch
ledgers with equal ticks, runtime/outcome retention, no reentry, no repeated
revocation and no scheduler generation reuse before explicit teardown.
The mismatch is a kernel integration counterexample, not a demonstrated native
userspace exploit or proof that all foreign scheduler substitutions are detected.

Native regression uses the existing non-optical PCLEANUP2 profile: an actual
parent UD2, entered worker cancellation, two deferred attempts, an independent
denied-authority control and surviving services. Raw input/log, transcript,
paired kernel, media and program bindings must reconstruct. It does not exercise
exhaustion followed by the one-shot entered-child rescue; that combined native
path remains next, alongside multiple-owner progress and service supervision.

Desktop and ISO packaging remain deferred. Historical preview and readiness
receipts are preserved, not relabeled as current. No phase or flag closes.
