---
queue_version: v1
frozen_at: 2026-07-04
plan_ref: skills/parallel-development/references/design-decisions.md#40
authority_chain:
  - skills/parallel-development/references/design-decisions.md#40
  - skills/parallel-development/docs/hetero-orchestration-proposal.md
  - skills/parallel-development/docs/hetero-orchestration-iteration-plan.md
status: frozen
---

# Plan Queue — iteration-plan

FROZEN plan interpretation emitted by blueprint-crafting `freeze`. Read-only for the executor; revise only via the Revision Channel (`status` -> `revising` -> edit + queue_version bump -> `status: frozen`). See parallel-development `references/plan-driven-mode.md`.

## Summary (checkpoint view)

11 item(s). DoD source: skills/parallel-development/references/design-decisions.md#40.

## Items

```json
[
  {
    "item_id": "P1-1-schema-delta",
    "seq": 1,
    "depends_on": [],
    "dod_ref": "skills/parallel-development/docs/hetero-orchestration-iteration-plan.md#P1-1-schema-delta",
    "title": "schema delta — adversarial-stalemate verdict",
    "scope": "Add adversarial-stalemate to run-record.schema.json $defs/outer_verdict.verdict.enum and loop_state.py record-outer --verdict choices (one line each). The cap-hit verdict becomes recordable.",
    "blueprint_subset": [],
    "producer": "blueprint-crafting",
    "plan_model_version": "v1"
  },
  {
    "item_id": "P1-2-findings-schema",
    "seq": 2,
    "depends_on": [],
    "dod_ref": "skills/parallel-development/docs/hetero-orchestration-iteration-plan.md#P1-2-findings-schema",
    "title": "findings schema for the 异源 subprocess return",
    "scope": "Prefer reusing violation-log.schema.json shape so reconciliation compares like-shaped findings. DoD (load-bearing for P1-5 reconciliation): the chosen schema MUST share the finding-level fields reconciliation compares — severity, location, defect_kind — with violation-log.schema.json. If net-new is unavoidable, document the field diff and how P1-5's reconciliation maps the fields. Passed by the wrapper as --json-schema.",
    "blueprint_subset": [],
    "producer": "blueprint-crafting",
    "plan_model_version": "v1"
  },
  {
    "item_id": "P1-3-profile-deepseek",
    "seq": 3,
    "depends_on": [],
    "dod_ref": "skills/parallel-development/docs/hetero-orchestration-iteration-plan.md#P1-3-profile-deepseek",
    "title": "profiles/deepseek.json — sanitized 异源 provider profile",
    "scope": "Net-new infra/scripts/profiles/deepseek.json. Sanitized template from ~/.claude/settings-deepseek.json: env block with ANTHROPIC_BASE_URL + ANTHROPIC_AUTH_TOKEN placeholder + model alias map. NO real token committed.",
    "blueprint_subset": [],
    "producer": "blueprint-crafting",
    "plan_model_version": "v1"
  },
  {
    "item_id": "P1-4-wrapper-core",
    "seq": 4,
    "depends_on": [
      "P1-1-schema-delta",
      "P1-2-findings-schema",
      "P1-3-profile-deepseek"
    ],
    "dod_ref": "skills/parallel-development/docs/hetero-orchestration-iteration-plan.md#P1-4-wrapper-core",
    "title": "hetero_review.py — wrapper core (single-round)",
    "scope": "Spawn claude -p --settings profiles/<backend>.json --model <alias> --output-format json --json-schema <findings> --permission-mode bypassPermissions --no-session-persistence --max-budget-usd <cap> with an adversarial prompt. Capture typed findings. Drive loop_state around the subprocess (init/bump-iteration/gate-fail/set-snapshot/record-outer/mark-converged/run-record). Parse --include-hook-events to observe gates. Deliverable also includes a flag-surface manifest: a comment block atop hetero_review.py listing every CC flag used + the verified CC version, so a maintainer hitting flag drift has the manifest at the failure site (mitigates CC-upgrade flag drift; P1-7's offline-mocked test cannot catch it).",
    "blueprint_subset": [],
    "producer": "blueprint-crafting",
    "plan_model_version": "v1"
  },
  {
    "item_id": "P1-5-debate-cap",
    "seq": 5,
    "depends_on": [
      "P1-4-wrapper-core"
    ],
    "dod_ref": "skills/parallel-development/docs/hetero-orchestration-iteration-plan.md#P1-5-debate-cap",
    "title": "multi-round debate + cap + reconciliation",
    "scope": "Extend wrapper: alternate same-source primary and 异源 challenge. max_adversarial_rounds cap (count = 异源 invocations; same-source final word by construction). Three terminations: converge / no-movement early-exit (reuse loop_state thrashing-fingerprint breaker) / cap. Reconciliation per ADR #40 (b) over the shared finding-level fields (severity/location/defect_kind) established by P1-2. Cap-hit records adversarial-stalemate + escalates (NEVER silent-pick).",
    "blueprint_subset": [],
    "producer": "blueprint-crafting",
    "plan_model_version": "v1"
  },
  {
    "item_id": "P1-6-wiring-convergent-loop",
    "seq": 6,
    "depends_on": [
      "P1-5-debate-cap"
    ],
    "dod_ref": "skills/parallel-development/docs/hetero-orchestration-iteration-plan.md#P1-6-wiring-convergent-loop",
    "title": "convergent-loop.md — 异源 alternative spawn wiring",
    "scope": "references/convergent-loop.md Outer-ring-flow section: add hetero_review.py as an alternative spawn for high-stakes items. Default unchanged (in-process solidforge:code-reviewer).",
    "blueprint_subset": [],
    "producer": "blueprint-crafting",
    "plan_model_version": "v1"
  },
  {
    "item_id": "P1-7-dogfood-test",
    "seq": 7,
    "depends_on": [
      "P1-5-debate-cap"
    ],
    "dod_ref": "skills/parallel-development/docs/hetero-orchestration-iteration-plan.md#P1-7-dogfood-test",
    "title": "hetero_review_wiring.py — deterministic wiring test",
    "scope": "Net-new infra/test/hetero_review_wiring.py mirroring plan_queue_loop_state_wiring.py. Asserts wrapper drives loop_state truthfully (outer.iterations>=1, steps.inner>=1), adversarial-stalemate round-trips run-record.schema.json, and malformation trips gate-fail. Offline/deterministic via a --dry-run mode or mocked claude -p.",
    "blueprint_subset": [],
    "producer": "blueprint-crafting",
    "plan_model_version": "v1"
  },
  {
    "item_id": "P2-1-model-routing-md",
    "seq": 8,
    "depends_on": [
      "P1-6-wiring-convergent-loop"
    ],
    "dod_ref": "skills/parallel-development/docs/hetero-orchestration-iteration-plan.md#P2-1-model-routing-md",
    "title": "references/model-routing.md (net-new)",
    "scope": "Net-new references/model-routing.md: the proposal §3 routing-policy table (stage x mode x provider x always/opt-in x role) as source, plus 异源 priority ordering (reviewer > research > Coder). States explicitly that the opt-in trigger (ADR-level / security-correctness-sensitive / same-source low-confidence) is the ADR #40 (b) prose — a human-judged classifier, not an automated one (the per-item automation lands in P3-2).",
    "blueprint_subset": [],
    "producer": "blueprint-crafting",
    "plan_model_version": "v1"
  },
  {
    "item_id": "P2-2-rule5-ripple",
    "seq": 9,
    "depends_on": [
      "P1-6-wiring-convergent-loop"
    ],
    "dod_ref": "skills/parallel-development/docs/hetero-orchestration-iteration-plan.md#P2-2-rule5-ripple",
    "title": "rule-5 enumeration ripple (every decision-point doc that names the reviewer / outer ring / verdict enum)",
    "scope": "Update EVERY enumeration that names the reviewer / outer ring / verdict enum: (1) references/install.md What-each-gate-does +row; (2) references/maturity.md caveat 13 future->landed AND the Specification-Gaming row AND the Orthogonal-axis subsection (both currently say 'no first-class 异源-oracle gate today' — contradicted by ADR #40 landing); (3) references/convergent-loop.md reviewer-prompt template + the record-outer call site + the Reviewer verdict dispatch + every verdict-enum literal (add 异源 option + adversarial-stalemate); (4) agents/code-reviewer.agent.md ~line 75 future->available; (5) SKILL.md Tier-2 outer-ring section (the verdict dispatch + reviewer spawn — add 异源 option + adversarial-stalemate). disconnect_check.py + lint_self.py stay green; a grep for the capability finds it at every decision-point doc.",
    "blueprint_subset": [],
    "producer": "blueprint-crafting",
    "plan_model_version": "v1"
  },
  {
    "item_id": "P3-1-research-tier-routing",
    "seq": 10,
    "depends_on": [
      "P2-1-model-routing-md",
      "P1-7-dogfood-test"
    ],
    "dod_ref": "skills/parallel-development/docs/hetero-orchestration-iteration-plan.md#P3-1-research-tier-routing",
    "title": "research-tier routing to a cheap backend",
    "scope": "Route the researcher/Explore fan-out tier to a cheap backend (DeepSeek flash) via --settings profiles/deepseek.json --model flash. Documented in references/model-routing.md. GATED on P1-7 green (the wrapper is proven before any routing expansion lands).",
    "blueprint_subset": [],
    "producer": "blueprint-crafting",
    "plan_model_version": "v1"
  },
  {
    "item_id": "P3-2-per-item-plan-routing",
    "seq": 11,
    "depends_on": [
      "P3-1-research-tier-routing",
      "P1-5-debate-cap",
      "P1-7-dogfood-test"
    ],
    "dod_ref": "skills/parallel-development/docs/hetero-orchestration-iteration-plan.md#P3-2-per-item-plan-routing",
    "title": "plan-driven per-item routing (cap, backend)",
    "scope": "Pinned source (per outer-ring novel-4): the per-item selection rides the plan_queue item's risk field, AND P3-2 lands that field — add a 'hetero' routing hint to the plan_queue item input (values: off=cap0 same-source / on=cap>0 异源) reading the blueprint risk tier (high → on). plan_queue.py picks (cap, backend) from the hint; high-stakes items get 异源; default items stay same-source (zero added cost). Per-item choice recorded in the run-record. Item-kind note (per outer-ring novel-10, Phase 0 RESULT point 2): 异源 value is item-kind-dependent (high on doc/spec/mixed, near-zero on pure-code), so the routing hint is a recommendation the human-judged opt-in (P2-1) can override — a high-stakes pure-code item may stay same-source to avoid burning cost for near-zero value.",
    "blueprint_subset": [],
    "producer": "blueprint-crafting",
    "plan_model_version": "v1"
  }
]
```
