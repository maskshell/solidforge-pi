# Intent Blueprint (Read-Only Anchor)

The Intent Blueprint is the frozen, structured replacement for the ambiguous natural-language prompt. It anchors the convergence loop so the Coder cannot drift from the original intent across many inner/outer iterations.

## Format

Template: `infra/templates/intent-blueprint.template.md` (installed to `docs/intent-blueprints/_templates/`). A blueprint file is `docs/intent-blueprints/<task>-v<n>.blueprint.md` and contains:

- Frontmatter: `blueprint_version`, `frozen_at`, `task`, `status` (`frozen` | `revising`).
- Core Use Cases (UC): functional points the system MUST implement. Never deleted to satisfy a compile/test constraint.
- Acceptance Criteria (AC): BDD Given/When/Then, each mapping to an executable test. Each AC line carries a `seam:` field (see "AC seam field" below).
- Non-Functional Requirements (NFR): performance, external dependencies, capacity. A coverage floor bullet (e.g. `- NFR-2: line coverage >= 80%`) is read by the per-language coverage gate (P3) — the MAX such floor becomes the warning threshold; absent → measure-only.
- Optional: a `visual_ref` pointer to a frozen **DESIGN.md** (external-skill anchor; see [external-skills.md](external-skills.md)) — its design tokens / component inventory / a11y targets flow into the NFR + visual-AC. DESIGN.md is read-only-enforced by the same `blueprint_guard.py` (anchor kind `design`), but via a **side-car sentinel** (`.claude/parallel-dev/design.frozen`), not frontmatter `status` — its frontmatter is an external (Impeccable) token-export with no status.
- AC → test mapping (declared at RED phase; value is a test name/nodeid, not a file path; consumed by the test-name set gate — see "Acceptance-Criteria -> Test Mapping" below).

## Acceptance-Criteria -> Test Mapping

> **Section heading is regex-matched** — `parse_ac_test_map` matches `^##\s+Acceptance[\s-]+Criteria\s*(?:->|→)\s*Test\s+Mapping`. Use the **full** `## Acceptance-Criteria -> Test Mapping` form (copied verbatim from the template); the `AC → Test Mapping` shorthand does NOT match and the gate silently no-ops.

An optional but recommended field, declared at RED phase. For each AC, name the executable test(s) that verify it.

- Value = a test name or nodeid the per-language collector emits (e.g. `test_user_registration`, `tests/test_auth.py::test_user_registration`), NOT a bare file path. The test-name set gate (`arch_contract_tests.py` → `parse_ac_test_map`) verifies each mapped test **exists** in the collected set — a missing declared name is a Blocker. One bullet per test; multiple bullets may share an AC id (each name collected). Comma-listing multiple names on one line is NOT supported (read as one name).
- Absent mapping → the gate degrades to an **inactive coverage note** (no name comparison runs — count comparison was rejected: it misses name replacement). It is optional precisely so a minimal blueprint does not block on it; declare a mapping to enable the set-diff.
- Whether the mapped test **actually verifies** the AC is semantic residue — outer-ring (the reviewer's diff-to-blueprint check), not this gate's claim. Name-presence and execution coverage are same-source signals with a hard ceiling against test-quality spec gaming (ADR #38: same-source verification cannot defend spec gaming on test quality).

Template: `infra/templates/intent-blueprint.template.md`.

## AC seam field

Each AC line declares its seam at Phase 0 freeze: `AC-1 <Given/When/Then> — seam: <public-boundary-name>`. The seam is the substitution point the test exercises; the name is the public boundary the caller actually uses, never an internal helper (the RED phase consumes the seam — see [feature-dev.md](feature-dev.md) Phase 4; ADR #56). The declaration carries a one-clause catch/miss note (what this boundary catches, what it misses — a bare name is label-blind-picking). The `AC → test mapping` line format is UNCHANGED: the seam lives on the AC line, not the mapping line, so `parse_ac_test_map` is untouched (rule 2, never edit the checker).

Absent seam on the AC line → **no gate consequence** (advisory doctrine; the name-set gate is unaffected — it reads the mapping section only). RED identifies the seam mid-phase per feature-dev.md Phase 4; NO schema'd record carrier exists for that identification (the run-record schema has no notes field; `loop_state.py summary()` is deterministic; the folded inner summary is produced by the GREEN-phase Coder; `record-outer --notes` bumps `outer.iterations` and is unusable at RED) — the degrade is unverifiable at the producer end, stated honestly. The consumer end closes the loop via the reviewer's seam-conformance check (tests sit at a public boundary; the absent declaration flagged as its own finding at warning severity — never blocks by workspace rule 4). The identification is NEVER written into the frozen blueprint (blueprint_guard.py denies edits to a `status: frozen` blueprint). A systematic absent seam is a defect, not the norm — see the rich-path rule below.

**Rich path**: when the blueprint is derived from a bc spec (`plan_queue.detect_producer` reports `blueprint-crafting`), the pd Planner **LATCHES** the seam the spec declares — each spec AC's `— seam: <public-boundary-name>` tail (the AC-ENTRY shape bc's arch-design §3 defines) is an explicit marker; latch-grade confidence, per the anchors-map latch notion as an analogy (the anchors map is a bc-side structure at section granularity; no `ref`/anchors-map entry is created at pd — the latch is the Phase-0 act, recorded on the blueprint AC line itself). When the spec AC carries NO seam, the Planner derives it AT Phase-0 derivation from the AC's Given/When/Then boundary (the external call boundary the scenario names) and writes it into the derived blueprint — the absent-spec-seam fallback, coverage-noted. Derive, don't re-imagine — the anchor stays upstream and real. Precedence: when the refinement's inferred boundary differs from the declared seam, the DECLARED seam wins (upstream anchor authority) — the precedence rule governs differences among legitimate PUBLIC-boundary choices; a declaration failing the public-boundary or observability criterion is NOT a precedence case. Declared-but-WRONG seam — two sub-cases with different catches: (i) internal-helper name — the primary catches are bc's plan-reviewer seam-quality checks (advisory) and the pd Planner's PRE-freeze refusal; post-freeze, check (g) is NOT a detector for this sub-case (tests written AT the declared internal helper CONFORM — a conforming-wrong-seam hole, stated honestly). (ii) boundary the AC's observable outcome cannot be observed at — the structural catch is the PRE-freeze refusal; post-freeze the mechanism is INDIRECT: the Coder's tests must relocate to observe the outcome, the relocation is a check (g) conformance violation, and the reviewer raises the revision channel's third trigger (check (g) itself tests conformance, not observability — no direct observability check exists at either skill, stated not overclaimed). PRE-freeze refusal, specified honestly: the pre-freeze phase has NO loop-state machinery (init + `--blueprint-ref` run AT freeze), so the refusal is an LLM-act convention, best-effort with no guarantee, coverage-noted per rule 3 — the Planner does not run `loop_state.py init`, reports the named seam defect + the spec AC location to the orchestrator/user, and yields; the bc re-invocation is a USER act. Endpoint: the escalation reaches bc's spec re-open lifecycle (bc SKILL.md "Spec re-open" — trigger/re-open/propagation semantics). Refactoring runs freeze blueprints whose ACs are the existing behavior-locking tests ([refactoring.md](refactoring.md) Phase 0 — the acceptance criteria = the existing tests, which Phase 2 produces; if tests are missing at freeze, Phase 2 writes them first); a refactoring spec's ACs DECLARE the seam from the locked tests' observed boundary (the tests themselves are the seam evidence — the spec-declares principle; when the locking tests do not yet exist at freeze, the seam is declared from the boundary the Phase-2 tests will lock). The declaration is present at freeze, so the reviewer's seam-conformance check applies and no systematic absent-seam noise is produced.

Deliberate design consequence: the seam field is declared PRE-freeze at Phase 0 precisely to avoid the AC→test mapping's unreconciled post-freeze write path — the mapping is declared at RED (post-freeze) yet blueprint_guard.py wholesale-denies frozen blueprints; how the mapping section enters the frozen blueprint is a pre-existing repo question, recorded in ADR #56 as an implementation-time open question.

## Phase 0 (freeze)

At the start of a task, the Planner (`requirements-manager` / `Plan`) converts the request into a blueprint, sets `status: frozen`, and records its path in loop-state (`loop_state.py init --blueprint-ref <path> --blueprint-version v1`).
No GREEN work begins until a frozen blueprint exists.

## Rich path — seeding from a blueprint-crafting spec

When the input is a blueprint-crafting artifact (its `.queue.md` carries the `producer: blueprint-crafting` marker — `plan_queue.detect_producer` — and the spec is reachable via the queue's `authority_chain`), the Planner **derives the Intent Blueprint from the spec rather than from the raw request** (odp1-blueprint-collapse-design D1: seed, don't alias). The spec and the Blueprint are different artifact kinds at different AC abstraction levels, so the Blueprint is a **derivative** of the spec, not an alias:

- spec `acceptance-criteria` → Blueprint AC, refined into BDD Given/When/Then (each → an executable test).
- spec `jtbd` + `scope-boundary` → Blueprint UC.
- spec `constraints-assumptions` → Blueprint NFR.
- spec `non-goals` → Blueprint scope (explicit exclusions).
- spec `desired-outcome-metrics` + `decisions` → authority context the Planner references but does not replicate (no Blueprint counterpart).

This collapses the authority (one source: the spec), not the artifacts. The Planner still does the refinement (product AC → BDD → test mapping) — the Blueprint remains parallel-development's technical/executable artifact.

Fail-safe: no spec in the chain (free path) → the Planner derives the Blueprint from the raw request, unchanged (today's behavior).

**Coverage note** — the Planner is an agent (an LLM act); this seeding is guided by this section, not enforced by a deterministic gate. Its fidelity (does the Planner actually seed from the spec rather than re-imagine?) is an outer-ring/eval concern, like `plan_reviewer` precision (ADR #10), not a deterministic self-check.

## Read-only enforcement (three layers)

1. Deterministic guard: PreToolUse hook `blueprint_guard.py` DENIES any Edit/Write/MultiEdit to a `**/intent-blueprints/*.blueprint.md` whose frontmatter `status` is `frozen`. The Coder cannot bypass it.
2. Revision channel: the ONLY way to change a blueprint (see below).
3. Reviewer check: the outer-ring reviewer is prompted to verify no blueprint was silently modified outside the revision channel.

## Blueprint Revision Channel (the only change path)

If implementation or review discovers the blueprint is:

- unreachable (a use case is physically impossible),
- self-contradictory (NFR conflicts with a use case), or
- has acceptance criteria that cannot be satisfied (incl. an AC whose declared seam boundary cannot observe its outcome),

the Coder MUST NOT edit the blueprint. Instead:

1. Set the blueprint frontmatter `status: revising` (the guard now allows edits).
2. Raise a suspend with a blueprint-defect flag: `loop_state.py mark-suspend --blueprint-defect --reason "<what is unreachable/contradictory>"`.
3. Escalate to the Planner (`requirements-manager` / `Plan`) + a human. Revise explicitly. A declared-seam defect escalates to bc's spec re-open lifecycle — the spec is re-opened and corrected bc-side BEFORE the re-freeze steps below can run (the anchor authority forbids fixing the blueprint's seam while the spec still declares the wrong one; the corrected spec propagates via the queue's authority_chain re-read at the re-latch — see bc SKILL.md "Spec re-open").
4. Bump `blueprint_version`; record it: `loop_state.py set-blueprint-version v<n>`. For a path-versioned re-freeze (`<task>-v<n>.blueprint.md`), also update the recorded ref: `loop_state.py set-blueprint-ref <path>` (records a `blueprint-ref-updated` event, preserving the `blueprint-revised`/`blueprint_revision` bookkeeping shape).
5. Set `status: frozen` again (the guard re-locks).
6. The loop restarts at Phase 1 with the new blueprint ref.

The blueprint changes ONLY through this channel — no silent edits. This is the rigid-constraint escape hatch required by the spec.

## Diff-to-blueprint check (outer ring)

Performed by the outer-ring reviewer (see [convergent-loop.md](convergent-loop.md) reviewer prompt). For each Core Use Case and AC, state satisfied | partially-satisfied | missing, with file:line evidence. Flag any value hardcoded to bypass a failing test. A "missing" or "hardcoded" verdict triggers the intent-drift hard-rollback path.
