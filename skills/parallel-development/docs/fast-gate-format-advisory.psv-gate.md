# psv GATE record — fast-gate-format-advisory-design.md

Mode: GATE (load-bearing-subset GO/NO-GO). NON-AUTHORITATIVE — the full-M run after csr is the only authoritative `oracle_verified_under_known_coverage` record.
Artifact: `skills/parallel-development/docs/fast-gate-format-advisory-design.md`
Authority: self-contained (external claims cited inline in §8).
Date: 2026-08-13.

## Load-bearing external subset (the gate verifies this only)

- C5 — google-java-format is whole-file by default; `--dry-run --set-exit-if-changed` (as the fast-gate invokes it, no range flag) reports whole-file reformatting. (Original wording claimed "no first-class range mode" — TOO STRONG.)
- C6 — Spotless `ratchetFrom` restricts formatting to files changed since a Git ref.
- C7 — Claude Code PostToolUse hooks gate via block/allow; no native warn-level severity.

## Verdicts (oracle = fetched source TEXT)

- **C5 — NARROWED (warning).** Fetched (`https://github.com/google/google-java-format`): "The formatter can act on whole files, on limited lines (`--lines`), on specific offsets (`--offset`)..." and "To reformat changed lines in a specific patch, use `google-java-format-diff.py`." The fetched source REFUTES the "no range mode" wording and supports the weaker form: whole-file behavior is how the fast-gate CALLS g-j-f, not a capability gap. Doc revised (C5 + §5) to the accurate form. Impact: weakens the old §5 rejection of scope-limited format; does NOT topple the core decision (rests on rule-4-spirit + the diff-inflation motivation, not on g-j-f lacking a range mode). Feeds the new Option C2 (range-scoped format commit) — C5 now EVIDENCES C's feasibility.
- **C6 — VERIFIED.** Fetched (`https://github.com/diffplug/spotless`): README links "git [ratcheting](...plugin-gradle#ratchet)". Feature existence + intent confirmed. Note: the exact keyword `ratchetFrom` and its file-granular semantics are inferred from the `#ratchet` anchor (the sub-section was not re-fetched); feature-level claim is supported.
- **C7 — VERIFIED.** Fetched (`https://docs.claude.com/en/docs/claude-code/hooks`): decision vocabulary is `permissionDecision: "deny"` (block) vs stay-silent (continue) — "can deny the call, but staying silent doesn't approve it." The only "warning" mention in the doc is a LOG warning about command-name whitespace, not a gate severity. No warn-level decision tier.

Tally: M_gate = 3. N=2 (C6, C7) / R=0 / W=1 (C5) / K=0.

## Gate decision: GO

Rule-13 discriminator: NO-GO iff any refuted/unverifiable OR ≥2 narrowed. Here 0 refuted, 0 unverifiable, 1 narrowed (< 2) → **GO**. The C5 narrowing is addressed by a pre-csr doc revision (above), so csr reviews the corrected artifact.

ODP-5 applicability: the doc's load-bearing citations are predominantly EXTERNAL (3/3 in the gate subset) → the gate is in its paying zone, and it PAID (caught a recall error on C5 that csr's recall-based legs would likely share). Confirms the gate's value on this doc class.

## Substrate note (rule 3 — state honestly)

The independent claim-extraction agent (`solidforge:claim-extractor`) FAILED with an API 400 `[modelCode：不存在]` routing error (the agent type has no `model:` pin and inherits the session model, but the subagent spawn resolved to a model code the backend rejects). Claim extraction + verdict were therefore performed INLINE by the orchestrator. The psv verdict invariant still holds — verdicts are grounded in FETCHED source quotes (the fetched text is the oracle, not model recall; the C5 narrowing proves the comparison is not rubber-stamping) — but the INDEPENDENCE of the extractor leg is lost for this gate run. The full-M run (Phase 3) will retry the verifier agents; if the substrate error persists, verdicts stay inline-grounded and the record will say so.

## Doc revisions driven by the gate

- C5 reworded to the accurate (weaker) form.
- §5 "scope-limited format" alternative removed from "rejected" (folded into Option C2).
- (Mid-gate design refinement from the user — commit-stratified format, Option C — folded into §4 as the recommended path; C5/C6 now evidence its feasibility. This is a design change, not a citation fix; csr reviews it.)
