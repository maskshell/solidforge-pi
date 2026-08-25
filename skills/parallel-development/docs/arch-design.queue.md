---
queue_version: v1
frozen_at: 2026-07-07
plan_ref: d3-gates-arch-design.md
authority_chain:
  - d3-gates-arch-design.md
  - docs/design-pattern-review-value.md
  - CLAUDE.md
status: frozen
---

# Plan Queue — arch-design

FROZEN plan interpretation emitted by blueprint-crafting `freeze`. Read-only for the executor; revise only via the Revision Channel (`status` -> `revising` -> edit + queue_version bump -> `status: frozen`). See parallel-development `references/plan-driven-mode.md`.

## Summary (checkpoint view)

3 item(s). DoD source: d3-gates-arch-design.md.

## Items

```json
[
  {
    "item_id": "drift-check-gate",
    "seq": 0,
    "depends_on": [],
    "dod_ref": "d3-gates-arch-design.md#1-positioning",
    "title": "drift_check.py self-gate",
    "scope": "Self-contained drift-detection gate over rule-7 duplicated boilerplate — a SUBSET of {run/have/emit/find_marker_dirs} present per-helper across arch_contract_*.py and *_adapter.py (emit family-wide; have/run/find_marker_dirs partial — verified by grep). The registry enumerates the verified per-helper sibling sets, not an idealized convention. Emits advisory warnings only, exits 0 (rule 4).",
    "source_location": "d3-gates-arch-design.md §1, §2, §4(D1,D2), §7",
    "parallel_group": "gates",
    "open_decisions": [
      {
        "id": "ODP-1",
        "kind": "resolve-now",
        "resolution": "Sibling file infra/test/drift_registry.json, holding DRIFT SITES ONLY (not adapter-family membership — that is glob-derived per arch-design §4 D5). Keeps platforms.json single-purpose: per-language decision-point routing is a different axis from drift-site enumeration."
      },
      {
        "id": "ODP-2",
        "kind": "resolve-now",
        "resolution": "Normalized-text diff: strip comments and whitespace, then compare. AST diff is over-engineering for boilerplate that is text-level duplication by definition."
      },
      {
        "id": "ODP-3",
        "kind": "deferred",
        "resolution": "Self-dogfood (compare the gate against its own future siblings) applies in principle once a second sibling exists; a one-member family has nothing to drift against."
      }
    ],
    "blueprint_subset": [],
    "producer": "blueprint-crafting",
    "plan_model_version": "v1"
  },
  {
    "item_id": "adapter-shape-check-gate",
    "seq": 1,
    "depends_on": [],
    "dod_ref": "d3-gates-arch-design.md#4-key-decisions--rationale",
    "title": "adapter_shape_check.py contract test",
    "scope": "Deterministic shape contract over the 7 *_adapter.py (membership glob-derived per arch-design D5, NOT registry): each must emit a violation-log.schema.json-valid object (top-level gate/passed/coverage/findings[] + per-finding severity/rule/file/line/detail/suggestion). Blocker + non-zero exit on violation (codifiable, so rule 4 permits Blocker). The shape check does NOT read drift_registry.json.",
    "source_location": "d3-gates-arch-design.md §1, §4(D1), §5(vs violation-log schema), §7",
    "parallel_group": "gates",
    "blueprint_subset": [],
    "producer": "blueprint-crafting",
    "plan_model_version": "v1"
  },
  {
    "item_id": "rule5-doc-audit",
    "seq": 2,
    "depends_on": [
      "drift-check-gate",
      "adapter-shape-check-gate"
    ],
    "dod_ref": "d3-gates-arch-design.md#6-parallel-boundaries-files_touched--rule-5-ripple",
    "title": "rule-5 doc audit across the 9 self-gate enumerations",
    "scope": "Grep BOTH gate names (drift_check, adapter_shape_check) AND count-words ('four deterministic', '4 deterministic', 'self-gate') across CLAUDE.md §1, extending.md, install.md (Self-checks list ~line 136, NOT the host-gate 'What each gate does' table ~line 86), maturity.md, golden-paths.md, role-agent-mapping.md, arch-contracts.md, platforms.json, disconnect_check.py. Fix stale counts too (e.g. extending.md:149 'four' -> post-ripple total), not only gate-name mentions. The self-gate roster is 10 in CLAUDE.md §1, 10 in install.md Self-checks (a different set), 4 in extending.md:138-141; union = 13 distinct pre-ripple, 15 post-ripple (grep-driven, not count-driven); update each enumeration that lists self-gates; record a coverage note for each that does not.",
    "source_location": "d3-gates-arch-design.md §6 (the ripple list)",
    "blueprint_subset": [],
    "producer": "blueprint-crafting",
    "plan_model_version": "v1"
  }
]
```
