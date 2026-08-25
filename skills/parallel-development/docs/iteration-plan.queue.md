---
queue_version: v1
frozen_at: 2026-08-13
plan_ref: fast-gate-format-advisory-design.md
authority_chain:
  - fast-gate-format-advisory-design.md
  - fast-gate-format-advisory.plan.md
  - fast-gate-format-advisory.psv-full.md
status: frozen
---

# Plan Queue — iteration-plan

FROZEN plan interpretation emitted by blueprint-crafting `freeze`. Read-only for the executor; revise only via the Revision Channel (`status` -> `revising` -> edit + queue_version bump -> `status: frozen`). See parallel-development `references/plan-driven-mode.md`.

## Summary (checkpoint view)

10 item(s). DoD source: fast-gate-format-advisory-design.md.

## Items

```json
[
  {
    "item_id": "fast-gate-guidance-split",
    "seq": 0,
    "depends_on": [],
    "dod_ref": "fast-gate-format-advisory.plan.md#3-per-iteration-dod",
    "title": "fast_gate.py format-vs-lint remediation guidance split (Option C)",
    "scope": "In the block reason, differentiate format-tool failures (ruff format / google-java-format / gofmt / rustfmt) from lint-tool failures (ruff check / eslint / swift-format lint): format failures get commit-stratification guidance (C-pre: run the formatter, commit as a standalone style: commit, then redo the logic edit — do NOT inline-rewrite the whole file into the logic diff); lint failures keep the existing fix-in-ring guidance. Detection, breaker wiring, loop_state fingerprints unchanged. Format STAYS a Blocker. ADD behavioral coverage (bc outer-ring novel-2: no existing test invokes fast_gate): a test runs the guidance branch on a lint-failing fixture and a format-failing fixture, asserts the split wording, skips gracefully when tools are absent (rule-1 skip convention).",
    "source_location": "fast-gate-format-advisory-design.md §4 Option C Detection axis, §6 fast_gate.py bullet",
    "blueprint_subset": [],
    "producer": "blueprint-crafting",
    "plan_model_version": "v1"
  },
  {
    "item_id": "commit-stratification-doc",
    "seq": 1,
    "depends_on": [
      "fast-gate-guidance-split"
    ],
    "dod_ref": "fast-gate-format-advisory.plan.md#3-per-iteration-dod",
    "title": "references/commit-stratification.md protocol doc",
    "scope": "New reference prescribing C-pre canonical (detect → format-commit → logic-edit) + C-post fallback (split at per-stage commit); states the deterministic-detect vs heuristic-stratify split honestly (rule 3/4); records the per-mechanism authorization (novel-3): C-post splits the one per-stage commit into two at the same point, C-pre adds a NEW mid-stage style: commit point — an additional auto-per-stage extension, neither a rule-9 override; covers the INLINE-mode path (novel-4, ADR #39): when the orchestrator itself made the blocked edit, the orchestrator executes C-pre mid-loop with ADR #39 bookkeeping still driven; records C-wholesale default + C-range pointers (g-j-f --lines / google-java-format-diff.py, Spotless ratchetFrom). Linked from plan-driven-mode.md §Commit policy + fail-fast.md.",
    "source_location": "fast-gate-format-advisory-design.md §4 Option C Isolation axis + sub-variants, §6 protocol-doc bullet",
    "blueprint_subset": [],
    "producer": "blueprint-crafting",
    "plan_model_version": "v1"
  },
  {
    "item_id": "install-md-split",
    "seq": 2,
    "depends_on": [
      "fast-gate-guidance-split",
      "commit-stratification-doc"
    ],
    "dod_ref": "fast-gate-format-advisory.plan.md#3-per-iteration-dod",
    "title": "install.md fast-gate row split",
    "scope": "Fast-gate row: split 'lint/format' into lint (Blocker, fix-in-ring) + format (Blocker, commit-stratified remediation); keep the per-language classification accurate (format-emitting = Python/Java/Go/Rust; Swift/Web/Python = lint).",
    "source_location": "fast-gate-format-advisory-design.md §6 install.md bullet",
    "parallel_group": "docs",
    "blueprint_subset": [],
    "producer": "blueprint-crafting",
    "plan_model_version": "v1"
  },
  {
    "item_id": "convergent-loop-md-split",
    "seq": 3,
    "depends_on": [
      "fast-gate-guidance-split",
      "commit-stratification-doc"
    ],
    "dod_ref": "fast-gate-format-advisory.plan.md#3-per-iteration-dod",
    "title": "convergent-loop.md fast-gate description split",
    "scope": "Fast-gate description: lint blocks (fix-in-ring); format blocks with stratification guidance pointing to the protocol doc. Do not touch the snapshot/commit-policy prose beyond the link.",
    "source_location": "fast-gate-format-advisory-design.md §6 convergent-loop.md bullet",
    "parallel_group": "docs",
    "blueprint_subset": [],
    "producer": "blueprint-crafting",
    "plan_model_version": "v1"
  },
  {
    "item_id": "extending-md-formula",
    "seq": 4,
    "depends_on": [
      "fast-gate-guidance-split",
      "commit-stratification-doc"
    ],
    "dod_ref": "fast-gate-format-advisory.plan.md#3-per-iteration-dod",
    "title": "extending.md per-language formula + strength tables",
    "scope": "Record the lint-Blocker / format-stratified decision point in the per-language formula + strength tables; per-language rows corrected to format-emitting = Python/Java/Go/Rust, Swift/Web/Python = lint.",
    "source_location": "fast-gate-format-advisory-design.md §6 extending.md bullet",
    "parallel_group": "docs",
    "blueprint_subset": [],
    "producer": "blueprint-crafting",
    "plan_model_version": "v1"
  },
  {
    "item_id": "maturity-md-caveats",
    "seq": 5,
    "depends_on": [
      "fast-gate-guidance-split",
      "commit-stratification-doc"
    ],
    "dod_ref": "fast-gate-format-advisory.plan.md#3-per-iteration-dod",
    "title": "maturity.md caveats update",
    "scope": "Caveats record the split + the honest note: stratify discipline heuristic (model-executed, gate-nudged), detection deterministic; Java/Go/Rust format-only (their fast-gate Blocker IS the stratification trigger); Swift/Web/Python retain a lint Blocker; PLUS the Option-A coverage-gap clause (novel-5): under Option A, Java/Go/Rust would lose their ONLY fast-gate check — must be emitted as a coverage note, never silently greened.",
    "source_location": "fast-gate-format-advisory-design.md §6 maturity.md bullet + coverage note",
    "parallel_group": "docs",
    "blueprint_subset": [],
    "producer": "blueprint-crafting",
    "plan_model_version": "v1"
  },
  {
    "item_id": "hooks-reference-md-split",
    "seq": 6,
    "depends_on": [
      "fast-gate-guidance-split",
      "commit-stratification-doc"
    ],
    "dod_ref": "fast-gate-format-advisory.plan.md#3-per-iteration-dod",
    "title": "hooks-reference.md fast-gate row split",
    "scope": "hooks-reference.md (~line 26, 'per-file cheap lint/format; records fingerprint in loop-state; queries breaker; emits reason incl. the breaker action') — same lint/format split as install.md/convergent-loop.md; describes the changed emit-reason surface. Added per bc outer-ring novel-1: the design §6 file list omitted this enumeration; rule 5 wins over the design's file list.",
    "source_location": "bc outer-ring finding novel-1; fast-gate-format-advisory.plan.md §3 fg-7",
    "parallel_group": "docs",
    "blueprint_subset": [],
    "producer": "blueprint-crafting",
    "plan_model_version": "v1"
  },
  {
    "item_id": "format-stratification-adr",
    "seq": 7,
    "depends_on": [
      "fast-gate-guidance-split"
    ],
    "dod_ref": "fast-gate-format-advisory.plan.md#3-per-iteration-dod",
    "title": "design-decisions.md new ADR (≈#49)",
    "scope": "ADR per rule 6 (Context/Decision/Why/Rejected): Option C chosen (format stays Blocker, commit-stratified remediation); A documented fallback (no code); B rejected (precluded by C7 — no platform warn severity); the per-mechanism auto-per-stage authorization framing (C-post one→two at the same point; C-pre NEW mid-stage point — neither a rule-9 override); heuristic-enforcement caveat; rejected alternatives from design §5. NOTE (novel-6): record explicitly that the fast-gate /tmp lint gap (dogfood gap #4) remains OPEN and out of this change.",
    "source_location": "fast-gate-format-advisory-design.md §4, §5, §7 rule-6 bullet",
    "blueprint_subset": [],
    "producer": "blueprint-crafting",
    "plan_model_version": "v1"
  },
  {
    "item_id": "facade-scan",
    "seq": 8,
    "depends_on": [
      "install-md-split",
      "convergent-loop-md-split",
      "extending-md-formula",
      "maturity-md-caveats",
      "hooks-reference-md-split"
    ],
    "dod_ref": "fast-gate-format-advisory.plan.md#3-per-iteration-dod",
    "title": "facade doc scan (rule 5, advisory)",
    "scope": "Grep README.md / README.zh-CN.md / USER_GUIDE.md / USER_GUIDE.zh-CN.md for fast-gate/format-as-blocker prose; update only what misdescribes the new behavior (loop SHAPE unchanged — format still blocks; the user-visible change is the style: commit + remediation text). Record the sync decision either way. Advisory — never a Blocker (rule 5).",
    "source_location": "fast-gate-format-advisory.plan.md §9 facade-impact-assessment",
    "blueprint_subset": [],
    "producer": "blueprint-crafting",
    "plan_model_version": "v1"
  },
  {
    "item_id": "full-self-gates",
    "seq": 9,
    "depends_on": [
      "fast-gate-guidance-split",
      "commit-stratification-doc",
      "install-md-split",
      "convergent-loop-md-split",
      "extending-md-formula",
      "maturity-md-caveats",
      "hooks-reference-md-split",
      "format-stratification-adr",
      "facade-scan"
    ],
    "dod_ref": "fast-gate-format-advisory.plan.md#3-per-iteration-dod",
    "title": "full self-gate suite green (rule 1)",
    "scope": "Run the full parallel-development self-gate suite: disconnect_check, smoke_gates (incl. the new fast-gate behavioral case from fast-gate-guidance-split), lint_self, arm_copy_config, arm_report_gates, arm_revert, plugin_layout, run_record, plan_queue_detect, hetero_review_wiring, drift_check, adapter_shape_check. All green = definition of done for the whole plan.",
    "source_location": "fast-gate-format-advisory.plan.md §5 phase-acceptance-gates",
    "blueprint_subset": [],
    "producer": "blueprint-crafting",
    "plan_model_version": "v1"
  }
]
```
