---
queue_version: v1
frozen_at: 2026-06-22
plan_ref: docs/iteration-plan.md
authority_chain:
  - docs/arch-design.md
  - docs/iteration-plan.md
  - docs/design-decisions.md
status: frozen
---

# Plan Queue — blueprint-crafting (I0 → I7)

FROZEN plan interpretation (Phase −1 normalizer output). Read-only for the executor; revise only via the Revision Channel (`status` -> `revising` -> edit + `queue_version` bump -> `status: frozen` -> `plan_queue.py sync`). See `parallel-development/references/plan-driven-mode.md`.

Authority: arch-design.md wins on conflict; design-decisions.md is the ADR log. Per-item convergence gate = the blueprint-crafting workspace self-checks (rule 1: self-checks are DoD). Golden-first TDD per item. Workspace rules 2 (registry/checker split), 4 (heuristics never blocker), 7 (copy-not-import) apply throughout.

## Summary (checkpoint view)

8 items at **iteration grain** (plan-native: I0 → I7). Dependency DAG: I0 → I1 → {I2 → I3 → I4, I5} → I6 → I7. No XL iterations.

**Resume point (this is a resume, not a fresh start):**

- I0 scaffold + activation — **CONVERGED** (commit 4976642).
- I1 plan-model schema + round-trip — **CONVERGED** (commit 4976642).
- I5 outer-ring plan-reviewer — **CONVERGED** (commit dd8b565).

Remaining chain (strictly sequential once I2 starts; I5 already feeds I6): **I2 → I3 → I4 → I6 → I7**.

**DAG deviation to flag at checkpoint:** the plan lists I5's dep as I2, but I5 was completed ahead of I2 (commit dd8b565). Justified: I5's deliverable (agent + fixtures + precision check) is self-contained against the I1 plan-model schema — it does not require the I2 normalizer to build. The "dep I2" in the plan was a runtime-pipeline assumption (reviewer consumes normalizer output at execution time), not a build dependency. Kept depends_on=[I2] in the queue to stay faithful to the plan; status=converged reflects reality. pick_next ignores terminal items' deps, so chaining is unaffected.

DoD source = `docs/iteration-plan.md` §3–§5 (per-iteration Done-when) + §6 (process-axis acceptance gate).

## Items

```json
[
  {
    "seq": 0,
    "item_id": "I0",
    "title": "scaffold + activation/routing (M)",
    "scope": "SKILL.md (constrained-production scope, scope guard, routes to docs) + trigger_check.py + disconnect_check.py + activation.json. Activation boundary: no collision with parallel-development.",
    "source_location": "docs/iteration-plan.md section 3 (I0)",
    "depends_on": [],
    "dod_ref": "docs/iteration-plan.md section 3 I0 Done: SKILL.md loadable; trigger test both directions; scope guard emits out-of-scope for implement code",
    "blueprint_subset": ["trigger_check.py", "disconnect_check.py"],
    "parallel_group": null,
    "open_decisions": []
  },
  {
    "seq": 1,
    "item_id": "I1",
    "title": "plan-model spec + schema + round-trip (M)",
    "scope": "plan-model.schema.json (executable subset + tagged upstream/downstream) + plan_model_schema.py (stdlib validator) + plan_model.py (lift/project) + round_trip.py. ADR #1, #9.",
    "source_location": "docs/iteration-plan.md section 3 (I1)",
    "depends_on": ["I0"],
    "dod_ref": "docs/iteration-plan.md section 3 I1 Done: schema passes stdlib validator; round-trip lossless on executable subset (not globally)",
    "blueprint_subset": ["plan_model_schema.py", "round_trip.py"],
    "parallel_group": null,
    "open_decisions": []
  },
  {
    "seq": 2,
    "item_id": "I2",
    "title": "normalizer — heterogeneous format -> plan-model (L)",
    "scope": "normalizer.py + 3 source-format goldens (rich md / Cursor .plan.md / work-package). Graded extraction: prose dependency inference tagged semantic-infer (low-confidence); frontmatter todos[] tagged latch (high-confidence). Heuristics NEVER blocker (rule 4).",
    "source_location": "docs/iteration-plan.md section 4 (I2)",
    "depends_on": ["I1"],
    "dod_ref": "docs/iteration-plan.md section 4 I2 Done: all 3 format goldens complete; prose inference tagged semantic-infer low-confidence; frontmatter todos[] tagged latch high-confidence",
    "blueprint_subset": ["normalizer.py", "normalizer_goldens"],
    "parallel_group": null,
    "open_decisions": []
  },
  {
    "seq": 3,
    "item_id": "I3",
    "title": "constraints-checker — anchors + authority + ODP (L)",
    "scope": "constraints_check.py + constraints.json (registry, rule 2 — profiles NOT hardcoded in the checker). Runs the artifact's constraints-profile on the plan-model. Inner-ring deterministic gate for non-research profiles. Dogfooded on this skill's own docs.",
    "source_location": "docs/iteration-plan.md section 4 (I3)",
    "depends_on": ["I1", "I2"],
    "dod_ref": "docs/iteration-plan.md section 4 I3 Done: 6 physics_schema_mcp exemplars pass; one anchor removed -> fail + names the missing anchor; authority-chain contradiction -> fail",
    "blueprint_subset": ["constraints_check.py", "constraints.json"],
    "parallel_group": null,
    "open_decisions": []
  },
  {
    "seq": 4,
    "item_id": "I4",
    "title": "research-constraints — v1 subset (L)",
    "scope": "research_constraints.py implementing ADR #7 v1: sources-cited(b) / staging-via-convergence(b) / cost-bounded(b when exceeded) / provenance-tag(w). Idempotency + full trust-tier DEFERRED; fedaot-kb purity DROPPED.",
    "source_location": "docs/iteration-plan.md section 4 (I4)",
    "depends_on": ["I3"],
    "dod_ref": "docs/iteration-plan.md section 4 I4 Done: unsourced claim -> Blocker; research frozen without convergence -> Blocker; fedaot-kb research golden passes the v1 profile",
    "blueprint_subset": ["research_constraints.py"],
    "parallel_group": null,
    "open_decisions": []
  },
  {
    "seq": 5,
    "item_id": "I5",
    "title": "outer-ring plan-reviewer (L)",
    "scope": "plan_reviewer.agent.md (independent context, report-only, adversarial) + review-findings.schema.json + 3 planted-defect fixtures + plan_reviewer_precision.py. ADR #10.",
    "source_location": "docs/iteration-plan.md section 5 (I5)",
    "depends_on": ["I2"],
    "dod_ref": "docs/iteration-plan.md section 5 I5 Done: >=3 planted-defect fixtures where the reviewer hits the CORRECT defect (precision); schema'd findings output",
    "blueprint_subset": ["plan_reviewer.agent.md", "plan_reviewer_precision.py"],
    "parallel_group": null,
    "open_decisions": []
  },
  {
    "seq": 6,
    "item_id": "I6",
    "title": "verdict-emitter + spec run-record (M)",
    "scope": "verdict.py: process_converged + rightness:human_confirm_required (CONSTANT). spec run-record schema + validator. Field-isolation assertion (process-axis green never changes rightness).",
    "source_location": "docs/iteration-plan.md section 5 (I6)",
    "depends_on": ["I3", "I4", "I5"],
    "dod_ref": "docs/iteration-plan.md section 5 I6 Done: run-record passes schema; field-isolation assertion (a green process axis NEVER changes the rightness field — it is a constant)",
    "blueprint_subset": ["verdict.py"],
    "parallel_group": null,
    "open_decisions": []
  },
  {
    "seq": 7,
    "item_id": "I7",
    "title": "end-to-end: produce + converge + repair (M-L)",
    "scope": "Take an incomplete physics_schema_mcp artifact (or seed), author/research it to convergence within its constraints-profile, emit plan-model + run-record. Plus a defect-injected fixture -> process_converged:false -> repair -> flip true. Re-run round_trip.py for the executable subset.",
    "source_location": "docs/iteration-plan.md section 5 (I7) + section 6",
    "depends_on": ["I3", "I4", "I5", "I6"],
    "dod_ref": "docs/iteration-plan.md section 5 I7 Done + section 6 process-axis acceptance gate",
    "blueprint_subset": ["e2e_fixture"],
    "parallel_group": null,
    "open_decisions": []
  }
]
```
