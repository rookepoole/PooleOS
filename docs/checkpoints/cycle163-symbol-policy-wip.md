# Cycle 163: Partial Symbol and Policy Replay

Status: unfinished cloud checkpoint on draft PR #75, not merge qualification.
Scope: N5.6 `N5-SYMBOLS-SEMANTICS-001` and dependent policy binding.

## Why Main Has Not Advanced

Main already includes the qualified Cycle 161 checkpoint through merged
PR #74, commit `a4c3c27fdfb5447e2a458066f97c62e5634962d4`. Older visible
agent branches have merged PRs; their existence does not mean their work was
left out. PR #75 is the only open PR at this checkpoint.

Cycle 162 source commit `7035d26dda223e024e5e4acf2877833726a88f8a` was
already pushed. Its pre-closeout audit passed 81/105 gates, with 23 stale
native dependencies and a failed aggregate gate. Doctor reported 683/706;
optional PooleGlyph runtime checks were excluded and passed separately.
Those figures describe that historical failed audit, not this WIP tree.
No current full-suite pass or waiver is claimed. Saving a branch on GitHub
does not require merging it to main.

## Work Preserved

PSYM1 now describes the measured Cycle 162 kernel geometry and split-debug
identity. The Rust lookup regression checks the new entry and rejects the
previous kernel's address. PPOL1 fixtures and its receipt bind the new
symbol artifact. The kernel executable source is unchanged in this increment.
Canonical kernel SHA-256:
`D0AA3295F66AF02D48476BCEDC44D962A873E98FBA21F48A6753AA7BB9B24EA4`.

The official symbol qualification passed four Rust tests, 158 negative
controls, 16,384 parser differential cases, 16,384 lookup differential cases,
and two identical debug builds. The official policy qualification passed
116 controls and 32,768 differential cases with zero mismatches. A fresh
backup preflight passed all 23 Python symbol/policy tests, including generated
fixture consistency and receipt/source binding checks.

Receipt SHA-256 values:

- `runs/native_symbol_readiness.json`:
  `38CA1F7D1C3FB7A2C69A9185AFA73717509724E6F56B382CF2D897CC0CFEC8EA`
- `runs/native_policy_readiness.json`:
  `5D10ED417B85088BB37D936BD11097CBD8887943754E3A65021DB9E8EDC3E605`

An initial symbol attempt rejected the old debug identity. After independent
measurement, another attempt found the obsolete Rust test address; correcting
that test produced the passing qualifier above. Failed attempts are retained
locally and are not added to successful counts.

PKREVAL1's expected host-test count is updated from 219 to the measured
228-test kernel suite. Its qualifier has not yet run against this change;
that edit is explicitly unfinished, not a passing revalidation receipt.

## Remaining Integration

1. Measure the current serialized artifact, manifest and retained-set digests.
   Update the fixed synthetic loader/transfer markers for the actual 146-page,
   1,319-relocation kernel geometry. Keep synthetic markers distinct from
   measured boot evidence.
2. Execute PKLOAD6, PooleBoot, PKREVAL1 and PKXFER1 qualifiers in dependency
   order. Update current gate pins only from successful measured results.
3. Requalify affected CPU, memory, VM, IRQ/SMP, scheduler and lock dependencies.
   A replaced transfer receipt also invalidates dependent VM evidence even
   when the kernel bytes stay unchanged.
4. Reconcile the roadmap, architecture bindings and all progress authorities;
   run exact-candidate canonical qualification with bundle, replay and optional
   runtime inputs, then publication and GitHub merge/review checks.
5. Only merge PR #75 when every required merge condition passes. Resume N12.3
   execution-stack and general CPU-retirement ownership after qualification.

Cycle 162 remains the last reconciled machine-ledger cycle. This interrupted
Cycle 163 checkpoint advances no phase, closes no flag and makes no production
claim. Private logs, build products, local temporary folders, signing material
and the unchanged demo ISO are excluded from this source backup.
