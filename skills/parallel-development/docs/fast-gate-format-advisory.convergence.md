# Convergence-record — fast-gate-format-advisory-design.md

(conforms to the `cross-source-review/infra/schemas/convergence-record.schema.json` field set; recorded as markdown per the workspace's convergence-trail convention)

- **artifact**: `skills/parallel-development/docs/fast-gate-format-advisory-design.md`
- **authority_ref**: self-contained (no external authority doc; external claims cited inline in §8, psv-admissible)
- **size_tier**: focused (single design decision; ~8 atomic claims; <300 lines) → cap = 3
- **substantive_converged**: **true** (same-family axis; ≥2 consecutive blocker-free rounds — R3, R4)
- **rightness**: `human_confirm_required` (whether demoting/stratifying format is the right call is outcome-axis — human only)
- **stalemate**: false

## Legs run

- **same-family leg** (`solidforge:doc-reviewer`, fresh-context, read-only): 4 rounds. Substrate note: the `solidforge:*` agent type initially failed with a transient `[modelCode：不存在]` backend error (also hit `general-purpose`); resolved on retry — rounds 1–4 all completed. Tool-level read-only enforcement is native to the agent type (no fallback needed this run).
- **different-family leg** (`hetero_doc_review.py` → DeepSeek): **substrate-unavailable this run.** 3 cold-start timeouts (2 at default pro tier @ 420–600s, 1 at `--model haiku` @ 540s) — the documented ADR #43 transient, but persistent enough to defer the leg. **Consequence: single-leg (same-family) convergence — weaker than the designed dual-leg; no cross-family blind-spot hunt.** Recommendation: re-run the different-family leg when DeepSeek is warm and re-confirm; until then this record is same-family-only.

## Rounds + per-finding dispositions

- **Round 1 (same-family)** — 3 blockers + 4 warnings, all ACCEPTED and fixed:
  - B1 (contradiction, §8 C5 vs §3): §8 still said g-j-f "no range mode" after the psv-gate narrowed §3. → fixed: §8 C5 rewritten to match §3.
  - B2 (citation-error, Swift misclassified as format): `check_swift` runs `swift-format lint` (a LINT). → fixed: C1, §6 coverage note, §7 corrected — format-emitting = Python/Java/Go/Rust; FORMAT-ONLY = Java/Go/Rust; Swift/Web/Python = lint.
  - B3 (structural-gap, Option C cadence): per-edit `style:` commit unreconciled with the loop's cadence. → fixed: §4 rewritten with Detection/Isolation axes (round 2 sharpened the source).
  - W1 (Option B infeasible per C7): → fixed: moved to §5 Rejected. W2 (§6 omitted maturity.md): → fixed: added. W3 (§4 framed detection as PreToolUse): → fixed: reframed PostToolUse. W4 (editorial clutter): → fixed: deleted.
  - Coverage: C1 (external C5/C6/C7 not re-fetchable by this leg — psv authoritative), C2 (fail-fast.md link target — confirmed exists).
- **Round 2 (same-family)** — 1 blocker + 1 warning, both fixed:
  - F1 (authority-chain-break): §4 cited `convergent-loop.md` for "the loop commits per stage" but that file has 0× "commit" (snapshots only); rule 9 operative clause ("do not auto-commit") misframed. → fixed: distinguished snapshot-cadence (convergent-loop.md) from commit-cadence (plan-driven-mode.md §Commit policy + loop_state.py `auto-per-stage`); `style:` framed as an extension of auto-per-stage (one→two), not a rule-9 carve.
  - F2 (terminology): §4 reused C1/C2 for scope sub-variants, colliding with §3 claim IDs. → fixed: renamed C-wholesale / C-range; §6 back-ref updated.
- **Round 3 (same-family)** — 0 blockers (clean round #1); 2 warnings fixed:
  - R3-C5-C7-XREF: §2 parenthetical "Claim C5" → "Claims C2/C7". R3-CPOST-SKETCH-ASYMMETRY: §6 protocol-doc bullet now describes both C-pre (canonical) and C-post (fallback).
- **Round 4 (same-family)** — 0 blockers, 0 warnings (clean round #2). Both R3 fixes verified held; C1–C4 source-verified; doc internally consistent §2–§8. Sole finding: coverage-severity disclosure that C5/C6/C7 (external) rest on psv-gate/full-M, not re-fetched by this leg.

## Core-claims coverage

- C1–C4 (internal): coverage-verified against source across 4 same-family rounds (fast_gate.py, detect_toolchain.py, arch_contract_*.py, convergent-loop.md, plan-driven-mode.md, loop_state.py, install.md).
- C5/C6/C7 (external): psv-gate verified Phase 1 (C5 NARROWED, C6/C7 VERIFIED); authoritative full-M record Phase 3.
- C8 (interpretive): non-load-bearing motivation; unverifiable, escalated to human.

## Substrate incidents (rule 3 — honest log)

1. `solidforge:*` + `general-purpose` Agent-tool spawns failed transiently with `[modelCode：不存在]`; resolved on retry.
2. different-family `hetero_doc_review.py` cold-start timeout ×3 (pro + haiku) — leg deferred; single-leg convergence.
