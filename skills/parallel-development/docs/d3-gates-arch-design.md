# D3 Gates — Architecture Design (copy-paste-drift detection + adapter-shape contract test)

> Status: **arch-design spec (upstream artifact), authored via blueprint-crafting, for parallel-development to implement.** Derived from `docs/design-pattern-review-value.md` § D3 + Recommended actions. Authority chain: this doc is master (arch-design wins on conflict); `docs/design-pattern-review-value.md` is the upstream analysis it lands; `CLAUDE.md` is the workspace-rule floor. Outcome axis (are these the right two gates to build) is `human_confirm_required` — this skill converges the process axis only.
>
> Authority chain: this `d3-gates-arch-design.md` > `docs/design-pattern-review-value.md` (D3) > `CLAUDE.md` (rules 1, 2, 3, 4, 5, 7).

## 1. Positioning

Two new infra gates under `skills/parallel-development/infra/test/`, both **self-gates** (they validate the skill's own source, alongside `disconnect_check` / `smoke_gates` / `lint_self` / `run_record` / `arm_*` / `plugin_layout` / `plan_queue_detect` / `hetero_review_wiring` — the full self-gate roster, which the rule-5 ripple in §6 must grep, not assume). They land TWO of the three consistency audits `design-pattern-review-value.md` § D3 names as new gates; the third (per-language capability-matrix alignment) is already governed by the existing `platforms.json` registry per that analysis, and is not re-implemented here.

- **`drift_check.py`** — detects divergence in the duplicated boilerplate that workspace rule 7's self-contained-script convention mandates. The convention deliberately duplicates a SUBSET of `run` / `have` / `emit` / `find_marker_dirs` and per-language detection stubs so each script stays independently deployable. The duplication is partial per-helper (verified by grep): `emit` appears across the whole family (17 files); `have` in 13/17; `run` in the `arch_contract_*.py` + lifecycle scripts but NONE of the `*_adapter.py`; `find_marker_dirs` in only 4. Drift = a sibling set (the files that share a given helper) has copy-paste-diverged (a bug fixed in one but not the others). The registry enumerates the VERIFIED per-helper sibling sets, not an idealized "all four everywhere" convention. This gate surfaces the drift.
- **`adapter_shape_check.py`** — verifies all 7 `*_adapter.py` follow the same shape: external-tool invocation → normalize → emit a `violation-log.schema.json`-shaped finding. A contract test over the adapter family.

Both are inputs the convergence loop and `disconnect_check` cannot currently produce: `disconnect_check` verifies file presence + loading-chain references; it does not compare file contents for divergence, and it does not assert adapter output shape.

## 2. What it does NOT do

- Does NOT replace or duplicate `arch_contract_tests.py`. That gate runs the **host project's** test suite (pytest / vitest / cargo / swift / mvn); these two gates inspect the **skill's own** infra source. Different object, different layer.
- Does NOT judge code correctness, only structural drift and shape. A divergent block is reported as drift; whether either branch is "right" is the outcome axis (human/`parallel-development` Coder).
- Does NOT Block on a drift hit. Drift detection is heuristic (rule 4: heuristics are advisory, never Blocker) → `drift_check.py` emits `warning` findings only, exits 0. Only `adapter_shape_check.py` (a codifiable contract) may emit `blocker` / exit non-zero.
- Does NOT auto-fix drift. It points at the divergent siblings; reconciliation is a Coder task.
- Does NOT introduce a shared library to eliminate the duplication. That would violate rule 7 (the duplication-for-independent-deployability is the point). The gate's job is to make the trade-off's drift visible, not to undo the trade-off.

## 3. Layering

Both gates sit at the **self-gate layer** of `parallel-development`'s inner ring — the same layer as `disconnect_check.py` (structure + loading-chain), `smoke_gates.py` (gate behavior), `lint_self.py` (ruff on own infra), `run_record.py` (run-record / L4 pipeline). They are plain stdlib Python scripts (workspace rule 7: self-contained, no shared lib, independently deployable), so like the other self-gates they need no convergence loop to be trustworthy — the recursion bottoms out here.

They run BEFORE the architecture-contract gates (`arch_contract_*.py`) in the self-edit flow, because they validate the gate scripts themselves: a drift or shape defect in `arch_contract_*.py` / `*_adapter.py` is a defect in the checker, found before the checker runs on a host project.

They are NOT hook-enforced. Per `extending.md:145`, the hook-enforced outer shell does not self-apply onto the skill source; these gates run via the deterministic self-gate command set (`extending.md:149`'s self-edit practice) and CI, not via a `PostToolUse` hook on the skill's own edits.

## 4. Key decisions + rationale

- **D1 — Drift is advisory; shape is Blocker.** The drift diff itself is exact-after-normalization (ODP-2), not fuzzy. Drift is advisory for two reasons: (a) the SET of sites that should match is a human-curated registry (the heuristic surface is the registry, not the diff) — a registry omission is a guess, not a proven defect; (b) cost-asymmetry — a false positive is cheap (a warning the maintainer dismisses), a false Blocker would block convergence on a guess (rule 4: no Blocker on a heuristic surface). So drift → `warning`, exit 0. `adapter_shape_check.py` asserts a crisp, codifiable contract (each adapter exposes a violation-log-shaped emit path — top-level `gate` / `passed` / `coverage` / `findings[]`, with `severity` nested in each finding, per `violation-log.schema.json`) — a missing field is a real, proven defect, so it → `blocker`, exit non-zero. This split mirrors the workspace's own determinism boundary (codable → Blocker; heuristic surface → warning).
- **D2 — Drift detection targets NAMED duplication sites, not free-form clone detection.** Rather than a generic code-clone tool, `drift_check.py` enumerates the specific boilerplate the convention mandates: the `run` / `have` / `emit` helpers, `find_marker_dirs`, and the per-language detection stubs (e.g. the `check_<lang>` shape across `arch_contract_*.py`). Each site is a registry entry (the registry is data, not code — rule 2). Named sites avoid the noise of generic clone detection (which would flag intended variation) and make the gate's coverage explicit.
- **D3 — Both gates follow rule 7 (self-contained).** Each is a standalone stdlib script duplicating the `run` / `have` / `emit` / `find_marker_dirs` pattern — the very pattern `drift_check.py` audits. This is deliberate: the gates must be deployable alongside the scripts they check, and they dogfood the convention they enforce (`drift_check.py` is itself a drift target for future siblings).
- **D4 — Registry-driven DRIFT-SITE list (rule 2).** The drift sites (the named boilerplate blocks to compare) live in a registry `drift_check.py` reads, not hardcoded in the checker. Adding a new duplicated boilerplate site = edit the registry, not the checker — the same convention as `platforms.json` + `disconnect_check.py`. The registry holds DRIFT SITES ONLY; adapter-family membership is NOT enumerated there (see D5).
- **D5 — adapter_shape_check.py is NO-TOOL (isolated-dynamic); adapter-family membership is glob-derived.** The shape check imports each `*_adapter.py` and invokes its `emit(findings, coverage)` with MOCK inputs (a synthetic findings list + coverage list) — bypassing the external-tool subprocess — then captures `emit()`'s stdout (`contextlib.redirect_stdout` + catch `SystemExit`, since the adapters' `emit()` prints and `sys.exit`s rather than returning — verified against `vale_adapter.py:49-63` / `license_adapter.py:102-116`) and validates that captured JSON object against `violation-log.schema.json`. This is isolated-DYNAMIC (it executes `emit`), NOT strict-static AST inspection: "valid severity enum" and "findings[] is a list" are runtime properties of the emitted JSON, only checkable by producing it. The real distinction from `smoke_gates.py` is "no external-tool subprocess": `smoke_gates` runs the adapter with its real tool armed (or skips); this gate runs `emit` with mocks. The two compose (smoke_gates = dynamic-with-tool, this gate = isolated-without-tool). Adapter-family membership is glob-derived (`infra/scripts/*_adapter.py`) — adding an adapter = adding a file the glob picks up, so a registry entry would be redundant.

## 5. Cross-boundary contracts

- **vs `disconnect_check.py`** — `disconnect_check` answers "do the files the registry names exist, and does the loading-chain reach them?" (presence + reference integrity, driven by `platforms.json` decision_points). `drift_check.py` answers "do the sibling files that SHOULD contain matching boilerplate still match?" (content divergence). `adapter_shape_check.py` answers "do the adapters emit the contract shape?" Boundary: `disconnect_check` = presence/references; the two new gates = content/shape. No overlap; the three compose.
- **vs `arch_contract_tests.py`** — different object entirely (host-project test suite vs skill-own source). No overlap.
- **vs `violation-log.schema.json`** — both new gates EMIT violation-log-shaped findings (so they integrate with the convergence loop like every other gate). `adapter_shape_check.py` additionally ASSERTS that the adapters emit this shape — it is both a consumer and a checker of the contract.
- **vs `smoke_gates.py`** — `smoke_gates` DYNAMICALLY validates gate/adapter output shape: `assert_conforms` → `validate_violation_log` runs the full violation-log validator on each gate's emitted output (`smoke_gates.py:69-72`, invoked per language at `:82/:102/:128/:166/:198/:241` + deps/tests). It needs the external tool armed (or skips). `adapter_shape_check.py` is NO-TOOL / isolated-DYNAMIC (imports the adapter, invokes `emit` with mock inputs — D5) and needs no tool. Partial overlap, deliberate composition: isolated-dynamic-without-tool (always runs) + dynamic-with-tool (`smoke_gates`, tool-gated).
- **vs `lint_self.py`** — `lint_self` runs ruff (E4/E7/E9/F) on own infra; it catches style/syntax/error-class lint. Drift and shape are structural concerns ruff cannot express. No overlap.
- **Host gate contract (read-only)** — both new gates read skill source under `skills/parallel-development/infra/`; they never mutate it. `files_touched` for a run = empty (they are checkers, not fixers).

## 6. Parallel boundaries (files_touched + rule-5 ripple)

New files (the implementation, `parallel-development`'s job):

- `skills/parallel-development/infra/test/drift_check.py`
- `skills/parallel-development/infra/test/adapter_shape_check.py`
- a registry `drift_check.py` reads (drift sites ONLY — adapter-family membership is glob-derived per §4 D5, NOT registry-enumerated). Candidate location: sibling file `infra/test/drift_registry.json` (ODP-1 recommendation). `adapter_shape_check.py` does NOT read this registry.
- a contract test for EACH new gate (rule 1: a gate ships with its own contract test) — `drift_check_test.py` (plants divergent boilerplate, asserts a warning is emitted, asserts exit 0) and `adapter_shape_check_test.py` (plants a malformed adapter, asserts a blocker + non-zero exit).

Rule-5 ripple is **grep-driven, not count-driven**: the self-gate roster is longer than `extending.md`'s four named gates — `CLAUDE.md` §1 and `install.md` Self-checks together enumerate ~10-11 self-gates. The audit must grep BOTH gate names AND count-words ("four deterministic", "4 deterministic", "self-gate") — a gate-name grep alone misses stale counts like `extending.md:149`'s "four" that must become the post-ripple total. Add the two new gates to every list that enumerates self-gates (and record a coverage note for each that does not). The candidates (checked, updated only if they enumerate self-gates):

- `CLAUDE.md` §1 (the self-gate command list) — add the two new gates if the list is meant to be exhaustive.
- `references/extending.md` — the per-language formula + self-gate roster (the four deterministic gates named at `extending.md:138-141`); add the two new gates to the roster.
- `references/install.md` **Self-checks** list (§ "Self-checks — the skill's own definition of done", ~line 136) — add two bullets. The "What each gate does" table (~line 86) is HOST gates (`fast_gate` / `blueprint_guard` / `arch_contract_*` / `loop_state` / `hetero_review`) — the new SELF-gates do NOT belong there; no row added.
- `references/maturity.md` — caveats; add a caveat if the gates introduce a new limitation class (e.g. "drift detection is advisory").
- `references/golden-paths.md` — domain enums; add if self-gates are enumerated here.
- `references/role-agent-mapping.md` — role triggers; likely no change (gates are not roles).
- `references/arch-contracts.md` — per-platform rows; likely no change (these are skill-self gates, not host-platform gates).
- `infra/test/platforms.json` — only if the registry is extended here (ODP-1).
- `infra/test/disconnect_check.py` — only if the new gates must appear in the loading-chain the checker walks (they are self-gates the checker may need to know about); decide at implementation.

The implementation must grep for each capability name (`drift_check`, `adapter_shape_check`) across these docs and update the ones that enumerate self-gates. A doc-audit pass is a required step (rule 5), not an afterthought.

## 7. Failure modes + degradation

- **Drift false positive** (the dominant risk) — the gate flags boilerplate as "diverged" when the variation is intended (e.g. a language-specific stub legitimately differs). Mitigation: the registry names the sites and may mark a site as `variation_allowed`; unmatched named sites are the only thing compared. And because drift is `warning` (D1), a false positive never blocks. A coverage note records which sites were compared.
- **Drift false negative** — a real divergence the registry did not name goes undetected. Mitigation: the registry is the explicit coverage surface; an unnamed site is an honest gap (rule 3: the gate states what it checked, not "all drift"). Extending coverage = add a registry entry.
- **Adapter-shape false negative** — an adapter emits a structurally valid but semantically wrong violation-log object (right shape, wrong content). Mitigation: the shape contract checks structure (required fields, valid `severity` enum, `findings[]` is a list); semantic correctness of adapter output is the outcome axis (the host-project arch-contract gates catch downstream effects). Stated as a coverage note.
- **Tool missing** — both gates are pure-stdlib and NO-TOOL: `drift_check.py` reads source files; `adapter_shape_check.py` imports adapters and invokes `emit` with mock inputs (D5), never the external-tool subprocess. So there is no "tool absent" degradation path (unlike `arch_contract_*.py` which wrap ruff/clippy/etc, or `smoke_gates.py` which skips when a tool is absent). They either run (green/red) or fail to import (a hard error, not a degrade). This gate's coverage note states "isolated (no-tool) shape only — dynamic-with-tool emission covered by `smoke_gates`".
- **Heuristic-miss framing** (rule 4) — drift detection is heuristic and tagged as such in its coverage; it never produces a Blocker, so an undetected drift degrades to a coverage note, never a silent green that masks a real divergence (rule 3).

## 8. Version strategy

- **Additive.** New drift sites are registry additions (rule 2), not checker edits. New adapter members are glob additions (a new `*_adapter.py` file under `infra/scripts/`), NOT registry entries — D5. A new gate criterion (e.g. checking a new boilerplate kind) = add a registry entry + a contract-test case.
- **The registry is the contract surface.** Schema evolution of the registry is additive (new optional keys); removing a site or changing its semantics needs a deprecation note in the registry `_comment`.
- **No round-trip contract with `plan_queue.py`** for these gates — they are self-gates, not plan items. The frozen plan-model this arch-design produces is consumed by `parallel-development` as the authoritative reference for implementing the gates; the gates themselves are not part of the executable-subset handshake.

## 9. Open Decision Points

| ODP | Question | Status |
| --- | --- | --- |
| ODP-1 | registry location: extend `infra/test/platforms.json` with `drift_sites`, OR a sibling registry file (e.g. `infra/test/drift_registry.json`) holding DRIFT SITES ONLY (adapter-family membership stays glob-derived per D5) | resolve-now — blocks convergence of this spec's plan-model until decided. Recommendation: sibling file `drift_registry.json`, because `platforms.json`'s concern is per-language decision-point routing (a different axis); mixing concerns would muddy the registry's single-purpose. |
| ODP-2 | drift-comparison algorithm: exact-text diff of the named block, normalized (whitespace/comment-stripped) diff, or AST-shape diff | resolve-now. Recommendation: normalized-text diff (strips comments/whitespace, keeps the comparison readable and debuggable; AST diff is over-engineering for boilerplate that is, by definition, text-level duplication). |
| ODP-3 | should `drift_check.py` also compare the new gates against their own future siblings (self-dogfood) | deferred — yes in principle (D3 rationale), but only once a second sibling exists; a one-member family has nothing to drift against. |
