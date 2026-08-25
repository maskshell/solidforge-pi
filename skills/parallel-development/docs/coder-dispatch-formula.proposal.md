# Proposal: subagent_type dispatch formula at the plan-driven decision point

Fix target: `skills/parallel-development/references/plan-driven-mode.md`, chaining-loop steps 4 and 5.

## Context (the drift)

The plan-driven chaining loop dispatches each queue item's Coder as a subagent, but the doc never states which `subagent_type` to pass. The platform-to-agent formula exists in `role-agent-mapping.md` (language-agnostic — `extending.md:48`), the per-platform pattern docs (`rust-patterns.md:4`, `go-patterns.md:3`, `java-patterns.md:3` — each states its platform "uses `backend-developer`"), and the direct-mode Task Metadata Convention (`parallel-patterns.md` — the `agent_type` TaskCreate field). It is NOT present in `plan-driven-mode.md` — the one doc loaded at the plan-driven dispatch moment — so the orchestrator falls back to the `general-purpose` default.

Measured evidence: in the tianwang-waf consumer project (session transcripts at `~/.claude/projects/-Users-solosus-dev-ws-waf-tianwang-waf/`, main session 2026-08-18 to 2026-08-24), 22 of 94 subagent dispatches ran Rust implementation tasks as `general-purpose`. The same project correctly dispatched `solidforge:backend-developer` / `solidforge:frontend-developer` / `solidforge:devops-engineer` for three v0.6 tasks on 2026-08-22, then drifted to `general-purpose` for all v0.7/v0.8 implementation tasks from 2026-08-23 onward. `solidforge:tester` (whose role table row lists Rust `cargo test`) was used zero times despite test-harness items.

This conflicts with the skill's own doctrine:

- `rust-patterns.md:4` — Rust uses `backend-developer` (no special agent).
- `role-agent-mapping.md` Test Engineer row — test work routes to `solidforge:tester` (Web/Backend), `solidforge:ios-developer` (XCTest unit), `solidforge:ios-tester` (XCUITest).
- ADR #29 (`design-decisions.md` §29) — added `ios-developer`/`ios-tester` and explicitly REJECTED the alternative "keep `general-purpose` + prompt" because it has no routing trigger and no platform discipline.

## Root cause

The dispatch decision point (chaining-loop step 4) does not carry the type-selection formula. Knowledge exists but is unreachable at the point of need — the workspace rule 8 (loading chain / progressive disclosure) failure mode.

## Proposed fix

Two insertions in `plan-driven-mode.md`, chaining-loop section, plus an agent-name prefix fix in `role-agent-mapping.md` + `e2e-testing.md` (criterion-scoped, see the fix subsection), plus a rule-6 ADR entry in `design-decisions.md`.

### Step 4 (Coder dispatch)

Replace the current step-4 opening "Run the **existing** lifecycle ..." with a dispatch preamble naming the `subagent_type` derivation. The lifecycle sentence is absorbed into the preamble; the existing **Rich path (research→inform)** sentence follows it unchanged. Composed step 4:

<!-- markdownlint-disable MD029 — the numbering mirrors plan-driven-mode.md's real step numbers -->
> 4. **Dispatch the Coder with the platform-derived `subagent_type`** — derive from the PROJECT platform (detected once at plan interpretation per the role table's file-based auto-detection, [role-agent-mapping.md](role-agent-mapping.md)) and the item's DoD shape via the dispatch rows below; do not default to `general-purpose` (ADR #29: no routing trigger, no platform discipline). Then run the **existing** lifecycle (Phase 0 → phases → Convergent Fix Loop) to convergence for THIS item. **Rich path (research→inform)**: if a research artifact (bc's `.research.json` or any free-form research doc — R2: research is free-form input, not gated to bc's format) is referenced via the queue's `authority_chain`, surface its content to the Coder (`plan_queue.py research-content --research-ref <path>`) so implementation is informed by the rationale (charter R5).
>
> | Item platform / DoD shape | Coder `subagent_type` |
> | --- | --- |
> | Rust, Go, Java/Kotlin, Python, Node.js/TypeScript backend | `solidforge:backend-developer` |
> | Web / UI work (frontend) | `solidforge:frontend-developer` |
> | iOS / Apple platform | `solidforge:ios-developer` |
> | Test corpus, unit/integration tests, test coverage (Rust, Go, Java, Python, Web/Backend) | `solidforge:tester` |
> | iOS test, XCTest unit | `solidforge:ios-developer` |
> | iOS test, XCUITest | `solidforge:ios-tester` |
> | Browser E2E | `solidforge:playwright-test-*` (planner → generator → healer workflow; Playwright MCP absent → fall back to `solidforge:tester`) |
> | CI/CD, deploy, infra | `solidforge:devops-engineer` |
>
> Row matching: the DoD-shape rows (test / E2E / CI-CD) win over the platform rows. For Node.js/TypeScript projects, backend vs frontend resolves by the role table's trigger keywords (Backend Developer triggers are server-side, Frontend Developer triggers are UI-side). Apple-platform architecture / module-boundary DoD routes to `solidforge:architect` despite the iOS platform row (role table Apple Platform Architect split). This precedence rule is new doctrine — recorded in the rule-6 ADR entry.
>
> Items outside the Coder scope route per the role table: architecture → `solidforge:architect`; detailed design → `Plan`; requirements analysis → `solidforge:requirements-manager`; visual design → the `/impeccable` skill.
<!-- markdownlint-enable MD029 -->

### Step 5 (review-leg dispatch)

Extend the review-leg spawn instruction with the security-specialist carve-out:

> ... spawn the code-reviewer + `loop_state.py record-outer --verdict <v>` first ...

Appended as its own sentence immediately after the converge-branch sentence (after "+ `run-record` (per-item)."), before the "On block:" branch (the carve-out's "instead" referent stays adjacent; no nested parenthetical, no mid-sentence split):

> For a security-semantic DoD (auth/authz, pre-production security, threat model), spawn `solidforge:security-specialist` instead. The `loop_state.py record-outer --verdict <v>` step is unchanged.

### Agent-name prefix fix (role table + e2e-testing.md)

`role-agent-mapping.md` prints bare agent names that its own other lines prefix (the E2E row's iOS siblings carry `solidforge:`; the Test Engineer row uses `solidforge:tester`). `e2e-testing.md` prints the same names bare throughout its workflow lines. The dispatch table cites these files for the `solidforge:`-prefixed names, so both files are made self-consistent.

Fix criterion (count-immune): prefix every bare agent-name CITATION (excluding markdown TOC anchors and heading links) in `role-agent-mapping.md` and `e2e-testing.md` of a name cited by the dispatch table, the companion sentence, or the step-5 carve-out — `playwright-test-planner` / `-generator` / `-healer`, `tester`, `frontend-developer`, `backend-developer`, `ios-developer`, `ios-tester`, `architect`, `code-reviewer`, `security-specialist` (`devops-engineer` and `requirements-manager` have zero bare instances in both files — verified, no edits). Verified inventories at fix time (2026-08-24): role table 14 instances (6 `playwright-test-*` + `tester` line 371 + `backend-developer` line 230 + `frontend-developer` line 57 + `architect` line 57 + `code-reviewer` lines 411 + 417 ×2 + `security-specialist` line 417); e2e-testing.md 13 instances (9 `playwright-test-*` + `tester` line 21 + `frontend-developer`/`backend-developer` line 106 + `Task(frontend-developer)` line 207). No other role-table content changes.

## Consistency notes

- Formatting follows workspace rule 10: the 2-attribute platform mapping is a table (one routing rule per row — no multi-rule cells); the row-matching line is a single short sentence; cross-refs glossed inline (ADR #29 glossed with its rejection rationale). The step-5 carve-out sits in its own sentence at the end of the step-5 bullet — no nested parenthetical, no load-bearing em-dash chain.
- Rule 5 doc-audit surface: files that describe Coder dispatch and could need the same formula are `plan-driven-mode.md` (fixed), `SKILL.md` line 284 (sequential-vs-direct dispatch — names Coder A/B but does not set a type; left as-is because it cross-refs parallel-patterns, not the type-selection table), `parallel-patterns.md` Task Metadata Convention (`agent_type` field — left as-is; it is a direct-mode TaskCreate convention, not adopted here because the plan-driven Queue Format carries no `agent_type` field, and adding one is a separate schema change), `feature-dev.md` (`agent_type` / `Task(<agent>)` worked examples — audited, left as-is, consistent with the dispatch formula), `docs/plan-driven-loop-state-wiring-design.md` (hook wiring — no type selection).
- Rule 5 `Task(<agent>)` worked-example sweep (deferred, out of fix scope, enumerated for a follow-up): `refactoring.md:60-62` carries `Task(developer)` — an UNREGISTERED agent name (real doc defect, recorded; separate fix), `bug-fix.md` (`Task(tester)`, `Task(backend-developer)`), `documentation.md` (`Task(documentation-writer)`), `ast-grep-patterns.md:482-536` (`Task(code-reviewer)` ×3, `Task(architect)` ×3). Same disposition as the repo-root review-plan doc — deferred, not silent.
- Rule 5 agent-name audit (the prefix fix's own enumeration sweep): `e2e-testing.md` — bare instances IN fix scope per the criterion. `docs/subagent-review-plan.md` (repo root) — 2 lines carrying 21 bare roster names (line 20 alone lists 17: 13 existing + 4 new), knowingly out of scope (repo-root review-plan doc; deferred to a repo-wide naming sweep). `infra/test/plugin_layout.py` — bare base names by checker convention ("Solid Forge registers these as `solidforge:<name>`"), rule 2 never edit the checker, not touched. Project facade docs: repo-root `README.md:17` lists the agents bare but discloses the plugin scoping inline ("plugin-scoped as `solidforge:<name>`") — advisory, no change needed, listed for human awareness; `USER_GUIDE.md` — zero agent-name hits (verified 2026-08-24 with the correct repo-root paths); GitHub About is human-owned (advisory).
- Rule 6: a one-paragraph ADR entry in `design-decisions.md` records (a) why the formula must sit inline at the dispatch point rather than relying on the role table being loaded (decision-point reachability; the drift as evidence), (b) the new-doctrine precedence rule (DoD-shape rows win over platform rows; Node backend-vs-frontend trigger-keyword resolution; Apple architecture over the iOS platform row), and (c) the mixed-prefix convention (step-5's existing bare `code-reviewer` is not rewritten; the appended carve-out uses `solidforge:security-specialist` — rejected alternative: rewriting the step-5 text to prefix). The entry pins the evidence source and counting rule for auditability: session `5ebbbf1c-55f4-4cac-9ac8-41862772de4e` under `~/.claude/projects/-Users-solosus-dev-ws-waf-tianwang-waf/`, counted as `subagents/*.meta.json` `agentType` values in dispatch order, at the 2026-08-24 extraction snapshot (94 metas; the session has since grown).
- Mixed prefix convention accepted: the existing step-5 text prints `code-reviewer` bare and is not rewritten; the appended carve-out uses the prefixed `solidforge:security-specialist`. The prefix-fix criterion covers the two authority files only. Recorded in the ADR entry (c) above.
- Rule 1: verification = `python3 skills/parallel-development/infra/test/disconnect_check.py` (structure + loading chain; the change adds no new file and no new reference).

## Non-goals

- No role-table content change beyond the criterion-scoped prefix fix (the trigger-based routing doctrine in `role-agent-mapping.md` is correct; the role rows' example tasks are role descriptions, not routing rules).
- No new agent type (the roster is complete; the fix is routing, not capability).
- No behavior change to the hooks or `plan_queue.py`.
