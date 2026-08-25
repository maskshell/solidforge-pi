# TDD improvement proposals (review-converged)

> Status: **PROPOSALS — not yet implemented.** Review-converged: the initial 6 proposals were reviewed, found to (a) have per-proposal gaps and (b) **omit the Specification-Gaming orthogonal axis** (ADR #38). Revised into two layers: same-source (blocks simple AI traps, has a hard ceiling) vs 异源 (defends test-quality spec gaming). Grounded in fedaot-wiki `ai-assisted-code-quality` + the current parallel-dev TDD state.
>
> Continuation: P7–P9 (seam doctrine + tracer-bullet-first decomposition + review-axis ODP) live in [tdd-seam-tracer-bullet.proposal.md](tdd-seam-tracer-bullet.proposal.md) — csr-converged 2026-08-24 (6 rounds, substantive_converged: true) and LANDED; see ADR #56. P7's bc-side follow-up (the spec declares the seam upstream — Option A) lives in [../../blueprint-crafting/docs/seam-upstream-anchor.proposal.md](../../blueprint-crafting/docs/seam-upstream-anchor.proposal.md) — csr-converged 2026-08-25 (12 rounds) and LANDED; see bc ADR #19 + the ADR #56 AMENDED note.

## Context: parallel-dev TDD state today

- **GREEN (test pass) = instrumented** (`arch_contract_tests.py` → Blocker on failing test; cross-ecosystem: pytest / vitest / cargo test / swift test / mvn·gradle / go test).
- **RED (test-first) + gate附加条件 (coverage / flaky / xfail / shrink) = prose** (`SKILL.md:142` describes them as gate, but `arch_contract_tests.py` only checks pass/fail). `maturity.md` caveat 13 honestly states the test-quality gap.
- **Parallel TDD scheduling** (`SKILL.md:287-359`): RED sequential (tests define contracts) → GREEN scheduled (parallel impl, no file overlap). A flow highlight, but agent-driven, not enforced.

## fedaot-wiki industry synthesis (ai-assisted-code-quality)

- **TDD amplification** (DORA 2025): AI amplifies existing practice — strong-TDD teams gain compound returns (tests = safety net). Red-green-refactor maps directly to agent: human writes test (intent) → agent generates minimal code → refactor under suite.
- **AI-specific traps** (GitHub Docs): hallucinated APIs, ignored constraints, **deleting tests instead of fixing them**, looks-correct-but-mismatches-intent.
- **Evaluator-optimizer pattern** (Augment 2026, production-ready): one LLM generates tests, another evaluates coverage + correctness — the most mature test-stage agent pattern.
- **4 AI-specific test techniques**: contract / property-based / metamorphic / tolerance-threshold.
- **Test pyramid matters more**: agents iterate fast, need per-step signal — fast unit feedback benefits most; slow integration/E2E background.

## Review: errors in the initial 6 proposals + the fundamental omission

1. **test-count comparison** — count misses name replacement (delete failing + add passing → count unchanged); baseline depends on Blueprint declaring a test set (which it doesn't — AC ≠ test name).
2. **reviewer as evaluator** — `code-reviewer` is **same-model** (shared blind spot) → defends Goal Drift, NOT Specification Gaming (ADR #38). Having it evaluate test quality = same-source verification of test quality = a carrier of spec gaming.
3. **coverage gate** — coverage measures **execution** not **assertion sufficiency**; 100% coverage still misses edge cases / weak assertions.
4. **Blueprint test set** — AC (behavior) ≠ test function name; deriving the name list is agent semantic inference (non-deterministic).
5. **fast_gate per-file test** — convention assumption (`tests/test_foo.py`) + timeout risk (DB/network fixtures) + too-frequent (per-edit). Unfit for a PostToolUse hook.
6. **Fundamental omission** — all 6 proposals were **same-source**. But test-quality spec gaming (delete test / weak assertion / overfit / swallowed exception) is **exactly** spec gaming — same-source can't defend it (reviewer shares the blind spot). The orthogonal 异源-oracle axis was just established in ADR #38 and was not connected to test quality.

## Revised proposals — two layers

### Same-source layer (blocks simple AI traps — deterministic or agent; does NOT defend spec gaming on test quality)

- **P1 (revised) — test-name set comparison, not count.** `arch_contract_tests.py` compares the terminal test-name set against the Blueprint's AC-test mapping (P4). Delete-a-failing-test → name missing → Blocker. Without the mapping, degrade to count + coverage note (honest, rule 3). Blocks naked "delete the failing test" — cross-language (name set, not count semantics).
- **P2 (revised) — outer-reviewer evaluator prompt.** Add an explicit test-quality dimension to `code-reviewer`'s prompt (coverage adequacy / are tests real AC checks or placeholders / signs of delete-or-weaken-to-pass). **Honestly marked same-source** — stronger than prose, defends Goal Drift + part of Error Compounding, does NOT defend spec gaming on test quality.
- **P3 (revised) — per-language coverage gate.** `check_pytest`/`check_vitest`/`check_rust`/`check_go` each add a coverage threshold (`pytest --cov --fail-under` / `vitest --coverage` / `cargo tarpaulin --fail-under` / `go test -cover`). Threshold: default + Intent Blueprint NFR override. **Marked "execution coverage, not assertion quality"**. Runs at the convergence gate (not fast_gate). Partial-closes caveat 13 (per-language, not cross-cutting canonical).
- **P4 (revised) — Blueprint AC-test mapping.** Agent declares `AC1 → test_user_registration` at RED phase. Gate checks the mapped test **exists** (deterministic). Whether the test actually verifies the AC stays outer-ring (semantic). This is the baseline P1 needs.
- **P5 (revised) — WITHDRAWN as a fast_gate hook** (convention/timeout/frequency risks). Instead: **SKILL.md guidance for the agent to run the relevant test each GREEN iteration** (agent behavior, not a hook). Fast-feedback gap addressed by agent self-discipline + reviewer, not enforced.

### 异源 layer (defends spec gaming on test quality — the real test-quality guarantee; future)

- **P6 (revised) — mutation testing is the first 异源 oracle.** `mutmut` / `stryker` / `cargo-mutants` — the engine injects faults, checks whether tests catch them. The mutation engine is **not the agent** → different blind-spot set → an oracle for test quality (does the test actually catch bugs, or does it just pass?). Per-language (caveat 13's "per-language tooling" is exactly right). This is the 异源 defense for test-quality spec gaming.
- **Contract testing (Pact / consumer-driven)** — component-level 异源 (consumer defines the contract, provider verifies). Different layer from `arch_contract_api` (API spec lint) — the latter is spec style, the former is consumer-provider contract (异源).
- **Ultimate 异源**: production regression / human semantic gate (the L4 orthogonal-axis oracle) — the last line for test-quality spec gaming, but long-term.

## The core insight (connects to ADR #38)

**TDD test-quality defense is two-layered, and the same-source layer has a hard ceiling.** Same-source (P1-P5 revised) blocks simple AI traps (naked delete / low coverage) via deterministic gates (test-name set, coverage) or agent (reviewer, self-run test). But **test-quality spec gaming (weak assertions, overfit, swallowed exceptions) same-source cannot defend** — the reviewer shares the blind spot, coverage measures execution not assertion. Crossing requires 异源 (mutation testing is the closest per-language 异源; contract testing is component 异源; production/human is ultimate). This is **exactly ADR #38's orthogonal axis**: L4's "proactive test self-verification" is same-source (a spec-gaming carrier); crossing needs 异源 oracle.

## Second-round review — implementation details + 近期 feasibility

A second review pass surfaces per-proposal implementation gaps the first pass missed, and one honest feasibility note on the 异源 layer:

- **P1**: test-name **extraction** is per-language (`pytest --collect-only` / `vitest --list` / `cargo test -- --list` / `go test -list`), even though the **comparison** is a cross-language set operation. The gate needs per-language collect dispatch (mirror `check_pytest`/`check_vitest`/...).
- **P2**: the reviewer evaluator dimension is a **`code-reviewer` agent-definition change** (its prompt), not a SKILL.md edit — find the agent def (`agents/` json/md) and add the test-quality dimension there.
- **P3**: coverage tools (`coverage.py` / `@vitest/coverage` / `cargo-tarpaulin` / `go cover`) are **dev deps not currently armed** by `arm.py --with-tools` — they need adding to the gate-deps, or the gate degrades to a coverage note on missing tool (rule 3).
- **P4**: the AC-test mapping needs a **storage location** — most natural is a new field in the Intent Blueprint (or the plan-model), declared at RED. The gate reads it; without it, P1 degrades to count.
- **P5**: "agent runs the relevant test each GREEN" still needs a **test→impl mapping** (convention `tests/test_foo.py` is an assumption; or the agent declares the mapping like P4). Without it, the guidance is "run what you think is relevant" — weaker than a hook, but the hook was infeasible (P5 original risks).
- **P6**: mutation testing is **extremely heavy** (each mutation runs the suite) — full mutation at the convergence gate would blow timeout. Needs **sampling** (mutation score on a sample, not exhaustive) or background/async. This tempers "first-of-异源": it's the first 异源 in principle, but its weight makes near-term 落地 non-trivial.

**Honest feasibility note (异源 layer)**: mutation testing is heavy (sampling needed), contract testing is project-dependent (opt-in), production regression / human semantic gate is long-term. ∴ **test-quality spec gaming has no near-term 落地 defense** — same-source has a hard ceiling (stated above), and 异源 options are all future / heavy / opt-in. This is an honest gap (rule 3): the proposals improve same-source (P1-P5, near-term) and chart the 异源 path (P6+, future), but do **NOT** claim to solve test-quality spec gaming now.

## Priority (revised)

| # | proposal | layer | leverage | difficulty | priority |
| --- | --- | --- | --- | --- | --- |
| P1+P4 | test-name set comparison + AC-test mapping | same-source | high (blocks naked delete) | low (name set, cross-lang) | **first** |
| P2 | reviewer evaluator prompt | same-source | medium (prompt change) | low (reviewer exists) | **first** |
| P3 | per-language coverage gate | same-source | high (caveat 13 partial-close) | medium (per-lang dispatch) | next |
| P5 | agent self-run test per GREEN (SKILL.md) | same-source | medium (fast feedback) | low (doc) | next |
| P6 | mutation testing | **异源** | high (real test-quality oracle) | high (per-lang, heavy) | first-of-异源 |
| — | contract / property / metamorphic | 异源 | low (optional, project-dependent) | high | future |

## Source

- fedaot-wiki `ai-assisted-code-quality` (TDD amplification, AI-specific traps, evaluator-optimizer, test pyramid, 4 AI-specific techniques).
- `references/maturity.md` caveat 13 (test-quality gap, honestly stated).
- `references/SKILL.md:11-17, :142, :287-359` (TDD Default, gate附加条件, TDD Examples).
- `infra/scripts/arch_contract_tests.py` (current test gate — pass/fail only).
- ADR #38 (capacity/demand + orthogonal axis — the spec-gaming ceiling same-source test-quality hits).
