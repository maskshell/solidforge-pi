# Heterogeneous-source (异源) orchestration — Iteration Plan (Phase 1+2+3)

> Execution blueprint for landing ADR #40. Structured like `blueprint-crafting`'s plan-driven mode: complexity tier + dependency edges + validation gate = the only "done" criterion (no day counts).
>
> **Authority chain**: `references/design-decisions.md §40` (ADR #40, the decision — **master**) > `docs/hetero-orchestration-proposal.md` (operational plan + Phase 0 result — arch-equivalent; **on conflict, ADR #40 / the proposal wins**) > this `iteration-plan.md` (executable breakdown). This doc carries the items + DoD; the proposal carries architecture + rationale (no duplication).
>
> **Revision note**: v2 incorporates the outer-ring (plan-reviewer) findings — the DAG now enforces the P1-7→Phase-3 gate (was prose-only); the rule-5 ripple widens to every decision-point doc that names the verdict enum / outer ring; cost-over-reporting + flag-drift + item-kind routing are now explicit.

## 0. Background and scope

- Phase 0 is COMPLETE — PROCEED verdict (proposal §6 Phase 0 RESULT). 异源 value is COMPLEMENTARY not superior; cross-family tool-call reliability 12/12 clean; DeepSeek auto-caches. The decision is settled (ADR #40); this plan does NOT re-debate it.
- Scope: land Phase 1 (core landing) + Phase 2 (codify) + Phase 3 (expand) — 11 items. The wrapper is proven by its own dogfood test (P1-7) BEFORE Phase 3 routing lands — this gate is DAG-enforced (P3-1 and P3-2 both `depends_on` P1-7), not merely prose.
- Substrate (ADR #40 (a)): a thin wrapper (`infra/scripts/hetero_review.py`) spawns a non-interactive Claude Code subprocess (`claude -p --settings profiles/<backend>.json --model <alias> --output-format json --json-schema <findings> --permission-mode bypassPermissions --no-session-persistence --max-budget-usd <cap>`). The subprocess inherits SKILL.md / hooks / Skills / MCP — the skill substrate is NOT stranded.
- Additive, not substitutive (ADR #40 (b)): the same-source reviewer (`solidforge:code-reviewer`, ADR #16 outer ring) stays PRIMARY and always runs; 异源 is opt-in, high-stakes items only.

## 1. Estimation gauge (no day counts)

| Dimension | Meaning | Use |
| --- | --- | --- |
| **Complexity tier** S/M/L/XL | intrinsic difficulty: substrate novelty × integration surface × rule-5 ripple width | per-item risk + dogfood density |
| **Dependency edge** | "X must exist before Y" | execution order + critical path |
| **Validation gate** | an objective "done" criterion: test passes / schema validates / self-gate green / loading-chain reachable | the unit of progress — no gate, no delivery |

Tier definitions: S = single small change, few edge cases; M = several subtleties or one non-trivial script; L = many subtleties stacked; XL = broad coverage + high integration. No XL items in this plan.

## 2. Overview: items, complexity, dependencies, gates

| seq | item_id | Complexity | Deps | Key validation gate (summary) |
| --- | --- | --- | --- | --- |
| 1 | P1-1-schema-delta | S | — | `adversarial-stalemate` accepted by `record-outer --verdict` AND validates against `run-record.schema.json` |
| 2 | P1-2-findings-schema | S | — | the findings schema validates a sample 异源 return AND shares reconciliation fields (severity/location/defect_kind) with `violation-log.schema.json` |
| 3 | P1-3-profile-deepseek | S | — | `profiles/deepseek.json` loads via `claude -p --settings` with an env-placeholder token (NO real secret committed) |
| 4 | P1-4-wrapper-core | M | P1-1, P1-2, P1-3 | `hetero_review.py` on a synthetic diff returns typed findings AND emits a truthful run-record (`outer.iterations≥1`, `steps.inner≥1`); flag-surface manifest present atop the script |
| 5 | P1-5-debate-cap | M | P1-4 | multi-round debate terminates on converge / no-movement / cap; cap-hit records `adversarial-stalemate` + escalates (never silent-pick) |
| 6 | P1-6-wiring-convergent-loop | S | P1-5 | `convergent-loop.md` documents 异源 as an alternative outer-ring spawn; default unchanged |
| 7 | P1-7-dogfood-test | M | P1-5 | `hetero_review_wiring.py` green: wrapper drives loop_state truthfully + `adversarial-stalemate` round-trips the schema |
| 8 | P2-1-model-routing-md | S | P1-6 | net-new `references/model-routing.md` carries the proposal §3 routing-policy table + the opt-in-trigger provenance |
| 9 | P2-2-rule5-ripple | M | P1-6 | install.md / maturity.md (caveat 13 + Specification-Gaming row + Orthogonal-axis) / convergent-loop.md (prompt + record-outer + verdict dispatch + enum literals) / code-reviewer.agent.md / SKILL.md Tier-2 all updated; `disconnect_check.py` + grep stay green |
| 10 | P3-1-research-tier-routing | M | P2-1, **P1-7** | researcher/Explore fan-out tier routable to a cheap backend (DeepSeek flash) via the profile; **gated on P1-7 green** |
| 11 | P3-2-per-item-plan-routing | M | P3-1, P1-5, **P1-7** | `plan_queue.py` per-item hetero hint (landed here) → picks (cap, backend); high-stakes get 异源, default stay same-source; **gated on P1-7 green** |

> **First package**: P1-1, P1-2, P1-3 are independent roots — do them together (all S). Then P1-4 (the wrapper core) chains on all three; P1-5 extends the wrapper; {P1-6, P1-7} follow P1-5. Phase 2 (P2-1, P2-2) follows P1-6. Phase 3 (P3-1, P3-2) follows Phase 2 AND P1-7 (DAG-enforced).

## 3. Phase 1 — core landing (P1-1 … P1-7)

### P1-1 schema delta — S

- **Goal**: make the cap-hit verdict recordable (ADR #40 (f) — the earlier "no schema change" framing was wrong; this is the honest, minimal delta).
- **Deliverables**: add `adversarial-stalemate` to (a) `infra/schemas/run-record.schema.json` `$defs/outer_verdict.verdict.enum`; (b) `infra/scripts/loop_state.py` `record-outer` subparser `--verdict` choices. One line each.
- **Done when**: `loop_state.py record-outer --verdict adversarial-stalemate` is accepted; a run-record carrying that verdict validates against `run-record.schema.json`; existing verdict values still validate (no regression).
- **Basis**: ADR #40 (e) cap-hit policy + (f) schema delta; proposal §6 Phase 1 "Schema delta".

### P1-2 findings schema — S

- **Goal**: the typed shape the 异源 subprocess returns via `--output-format json --json-schema`, with reconciliation-comparable fields.
- **Deliverables**: prefer reusing the existing `violation-log.schema.json` shape (the same-source reviewer already emits it) so P1-5's reconciliation compares like-shaped findings; OR net-new `infra/schemas/review-findings.schema.json` IF the 异源 return needs fields violation-log lacks. **Load-bearing DoD**: the chosen schema MUST share the finding-level fields reconciliation compares — `severity`, `location`, `defect_kind` — with `violation-log.schema.json`. If net-new is chosen, document the field diff and how P1-5's reconciliation maps the fields.
- **Done when**: the chosen schema validates a representative 异源 findings payload; the shared reconciliation fields are present (or the field-diff mapping is documented); the wrapper passes it as `--json-schema`.
- **Basis**: proposal §6 Phase 1 "findings schema"; ADR #40 (a) structured I/O + (b) reconciliation. Outer-ring novel-7.

### P1-3 profile — deepseek.json — S

- **Goal**: the per-process 异源 provider config the wrapper passes via `--settings`.
- **Deliverables**: net-new `infra/scripts/profiles/deepseek.json` — sanitized template (env block: `ANTHROPIC_BASE_URL` + `ANTHROPIC_AUTH_TOKEN` placeholder + `ANTHROPIC_DEFAULT_*_MODEL` / model alias map), modeled on `~/.claude/settings-deepseek.json`. The real token stays in the user-only settings file; the committed profile uses an env-placeholder (e.g. `${ANTHROPIC_AUTH_TOKEN}`) and is documented as "bring your own key".
- **Done when**: `claude -p --settings profiles/deepseek.json ...` loads without config error in a dry check; no secret material is committed (grep-clean).
- **Basis**: ADR #40 (a); `hetero-review-setup` memory (the invocation pattern).

### P1-4 wrapper core — hetero_review.py — M

- **Goal**: the thin wrapper that spawns the 异源 subprocess and captures typed findings (ADR #40 (a), (g)).
- **Deliverables**: net-new `infra/scripts/hetero_review.py` (self-contained, mirroring the per-script convention — workspace rule 7). Given a diff + blueprint ref + findings-schema, it spawns `claude -p --settings profiles/<backend>.json --model <alias> --output-format json --json-schema <findings> --permission-mode bypassPermissions --no-session-persistence --max-budget-usd <cap> -p "<adversarial prompt>"`. The prompt is ADVERSARIAL ("find what the primary reviewer missed or got wrong", NOT "validate"). The wrapper drives `loop_state` around the subprocess from day one (ADR #39, ADR #40 (g)): `init → bump-iteration → gate-fail <fingerprint> on malformation → set-snapshot <ref> → record-outer → mark-converged → run-record`. `--include-hook-events` is parsed to observe the deterministic gates. Single-round in this item (multi-round is P1-5). **Flag-surface manifest** (outer-ring novel-5): a comment block atop the script lists every CC flag used + the verified CC version, so a maintainer hitting flag drift has the manifest at the failure site (P1-7's offline-mocked test cannot catch live-substrate flag drift).
- **Done when**: on a synthetic small diff with a small `--max-budget-usd`, the wrapper returns typed findings AND the emitted run-record shows `outer.iterations≥1` and `steps.inner≥1` (truthful bookkeeping, the ADR #39 invariant); the flag-surface manifest comment is present.
- **Basis**: ADR #40 (a) substrate + (g) loop_state driving; proposal §2, §6 Phase 1.

### P1-5 multi-round debate + cap — M

- **Goal**: the realistic debate pattern — single-round rarely converges (ADR #40 (c), (d), (e)).
- **Deliverables**: extend `hetero_review.py`: alternate same-source primary ↔ 异源 challenge; `max_adversarial_rounds` cap where the count = **异源 invocations** (the same-source primary always responds after each challenge, so the same-source final word is guaranteed by construction — no odd/even parity). Three terminations: (1) converge (≥1 round with zero new findings); (2) no-movement early-exit (same disagreement fingerprint ≥2 rounds — REUSE `loop_state`'s thrashing-fingerprint breaker); (3) cap. Reconciliation per ADR #40 (b) over the shared finding-level fields (`severity`/`location`/`defect_kind`) established by P1-2: both-report → high-confidence; same-source-only → adopt; 异源-only → escalate; neither → pass. Cap-hit → `record-outer --verdict adversarial-stalemate` + escalate to human (NEVER silent-pick — ADR #40 Rejected (f)).
- **Done when**: a constructed debate reaches each of the three terminations; cap-hit records `adversarial-stalemate` and does NOT adopt either side silently.
- **Basis**: ADR #40 (c)(d)(e); proposal §4.

### P1-6 wiring — convergent-loop.md — S

- **Goal**: make the 异源 path REACHABLE at the decision-point doc (rule 8 loading chain).
- **Deliverables**: in `references/convergent-loop.md` §"Outer ring flow", add 异源 as an ALTERNATIVE spawn for high-stakes items (the orchestrator picks: default = in-process `solidforge:code-reviewer`; opt-in = `hetero_review.py` subprocess). Default behavior unchanged. (The full verdict-enum + prompt-template ripple is P2-2; this item is the spawn-point wiring only.)
- **Done when**: the doc names `hetero_review.py` + the opt-in trigger condition (ADR #40 (b) prose: ADR-level / security-correctness-sensitive / same-source low-confidence); the default same-source path is still clearly primary.
- **Basis**: ADR #40 (b) additive/opt-in; proposal §5; rule 8.

### P1-7 dogfood test — hetero_review_wiring.py — M

- **Goal**: a deterministic test that the wrapper is wired correctly (the inner-ring self-gate for this feature).
- **Deliverables**: net-new `infra/test/hetero_review_wiring.py` mirroring `plan_queue_loop_state_wiring.py` (subprocess-based wiring test). Asserts: (a) the wrapper drives `loop_state` truthfully (`outer.iterations≥1`, `steps.inner≥1` — ADR #39); (b) `adversarial-stalemate` round-trips through `run-record.schema.json`; (c) a stubbed/mocked backend malformation trips `gate-fail` (not a silent crash). Uses a mocked `claude -p` (or a `--dry-run` mode in the wrapper) so the test is offline + deterministic (rule 4 — no real model call in the gate).
- **Done when**: the test is green offline; it is listed in the skill's self-gate set (CLAUDE.md §1).
- **Basis**: proposal §6 Phase 1 "Dogfood"; rule 1 (self-gates are the definition of done). NOTE: by design this test does NOT exercise the live substrate — the flag-surface manifest (P1-4) + the dogfood runs (§6 Phase-3 gate) carry the live-substrate evidence.

## 4. Phase 2 — codify (P2-1, P2-2)

### P2-1 model-routing.md (net-new) — S

- **Goal**: a single source-of-truth for the per-stage routing policy + the opt-in-trigger provenance.
- **Deliverables**: net-new `references/model-routing.md` — the proposal §3 routing-policy table (stage × mode × provider × always/opt-in × role) as the source, plus the 异源 priority ordering (reviewer > research > Coder). States explicitly that the opt-in trigger (ADR-level / security-correctness-sensitive / same-source low-confidence) is the ADR #40 (b) prose — a **human-judged classifier**, not an automated one (the per-item automation lands in P3-2).
- **Done when**: the file exists, carries the table + the opt-in-trigger provenance, and is referenced from the relevant decision-point docs (install.md / convergent-loop.md).
- **Basis**: proposal §3; ADR #40 (b). Outer-ring novel-9.

### P2-2 rule-5 enumeration ripple — M

- **Goal**: a capability ripples through every enumeration (rule 5); a doc-audit pass is a required step, not an afterthought.
- **Deliverables**: update EVERY enumeration that names the reviewer / outer ring / verdict enum (outer-ring novel-2 widened the set from 4 to all decision-point docs):
  - `references/install.md` "What each gate does" — add a row for the 异源 reviewer (opt-in; mechanism = `hetero_review.py` subprocess; failure behavior = `adversarial-stalemate` + escalate).
  - `references/maturity.md` — (a) caveat 13 future→landed; (b) the **Specification-Gaming row** (currently says SolidForge has no first-class 异源-oracle gate — directly contradicted by ADR #40 landing); (c) the **Orthogonal-axis subsection** (same contradiction).
  - `references/convergent-loop.md` — (a) reviewer-prompt template (+ 异源 option + `adversarial-stalemate` verdict); (b) the **`record-outer --verdict` call site** (add `adversarial-stalemate` to the literal); (c) the **Reviewer verdict dispatch**; (d) **every verdict-enum literal** in the doc.
  - `agents/code-reviewer.agent.md` (~line 75) — same-source-ceiling note future→available + 异源 path.
  - `SKILL.md` — the **Tier-2 outer-ring section** (verdict dispatch + reviewer spawn): add the 异源 option + `adversarial-stalemate` verdict.
- **Done when**: all touch-points updated; `disconnect_check.py` + `lint_self.py` stay green; a grep for the capability (verdict enum / `hetero_review` / 异源) finds it at every decision-point doc. The disconnect_check catches structural broken links, NOT stale enum contents — so the grep is load-bearing, not the checker.
- **Basis**: rule 5 (enumerate then doc-audit); rule 8 (loading chain); ADR #40.

## 5. Phase 3 — expand (P3-1, P3-2)

> Both Phase-3 items carry a **DAG-enforced** `depends_on` edge to P1-7 (outer-ring novel-1): the wrapper must be proven by its dogfood test before any routing expansion lands.

### P3-1 research-tier routing — M

- **Goal**: extend 异源 beyond the reviewer to the cost-dominated research fan-out tier.
- **Deliverables**: route the researcher / Explore fan-out tier to a cheap backend (DeepSeek flash) via `--settings profiles/deepseek.json --model flash`. Documented in `references/model-routing.md` (P2-1).
- **Done when**: a research-tier spawn can target the cheap backend through the profile; the routing is documented; P1-7 is green (DAG gate).
- **Basis**: proposal §3 (research stage row) + §6 Phase 3.

### P3-2 per-item plan-driven routing — M

- **Goal**: in plan-driven mode, pick the routing per item (not a blanket global), with the selection source pinned and the Phase-0 item-kind finding encoded.
- **Deliverables**: **land the per-item selection field** (outer-ring novel-4): add a `hetero` routing hint to the `plan_queue` item input (values: `off` = cap0 same-source / `on` = cap>0 异源), sourced from the blueprint risk tier (high → `on`). `plan_queue.py` picks (cap, backend) from the hint; high-stakes items get 异源; default items stay same-source (zero added cost). The per-item choice is recorded in the run-record. **Item-kind note** (outer-ring novel-10, Phase 0 RESULT point 2): 异源 value is item-kind-dependent (high on doc/spec/mixed, near-zero on pure-code), so the hint is a RECOMMENDATION the human-judged opt-in (P2-1) can override — a high-stakes pure-code item may stay same-source to avoid burning cost for near-zero value.
- **Done when**: a plan-queue item with `hetero=on` routes to 异源; a default item routes same-source; the per-item choice is in the run-record; P1-7 is green (DAG gate).
- **Basis**: proposal §6 Phase 3; ADR #40 (b) opt-in; Phase 0 RESULT point 2.

## 6. Phase acceptance gates

- Phase 1 gate: P1-7 green (the wrapper is wired truthfully); the schema delta round-trips; the wrapper returns typed findings on a synthetic diff.
- Phase 2 gate: every rule-5 enumeration updated (the grep finds the capability at every decision-point doc); `disconnect_check.py` green (no loading-chain break); `references/model-routing.md` exists and is reachable.
- Phase 3 gate: P3-1 + P3-2 land on a wrapper already proven by P1-7 (DAG-enforced, not prose); **N≥2 items dogfooded through the wrapper itself** (outer-ring novel-6 — n=1 is the weakness Phase 0 RESULT point 4 calls out; the gate strengthens the evidence before production routing ships).
- Whole-iteration gate: all parallel-dev self-gates green (CLAUDE.md §1), including the net-new `hetero_review_wiring.py`.

## 7. Dependencies and parallelism (DAG)

```text
P1-1 schema-delta ─┐
P1-2 findings-schema ─┼─▶ P1-4 wrapper-core ─▶ P1-5 debate-cap ─┬─▶ P1-6 wiring ─▶ P2-1 model-routing ─┐
P1-3 profile ─────┘                                          └─▶ P1-7 dogfood-test ─────────────────────┼─▶ P3-1 research-tier ─▶ P3-2 per-item-routing
                                                                                            ▲─────────── P2-2 rule5-ripple (from P1-6) ─┘
```

**Parallel fan-out points**: P1-1, P1-2, P1-3 are independent roots (parallelizable). After P1-5, P1-6 and P1-7 can parallelize. P2-1 and P2-2 both follow P1-6 (parallelizable). **P3-1 depends on {P2-1, P1-7}; P3-2 depends on {P3-1, P1-5, P1-7}** — the P1-7 edge is the DAG-enforced wrapper-proven gate (outer-ring novel-1). The Phase 1 core chain (P1-4 → P1-5) is sequential (tight coupling — the wrapper IS the 异源 engine).

## 8. Risks and mitigations

| Risk | Item | Mitigation |
| --- | --- | --- |
| Morph caveat bites (异源 tool-call flakiness) | P1-4 | Phase 0 already proved 12/12 clean; wrapper trips `gate-fail` on malformation, never silent-crashes; same-source primary retained = the floor |
| real secret committed in `profiles/deepseek.json` | P1-3 | env-placeholder only; grep-clean gate; real token stays in user-only `~/.claude/settings-deepseek.json` |
| run-record dishonesty (`steps.inner=0` with real work) | P1-4 | wrapper drives `loop_state` from day one (ADR #39, ADR #40 (g)); P1-7 asserts `steps.inner≥1` |
| silent-pick on cap-hit (trust same-source on timeout) | P1-5 | `adversarial-stalemate` + escalate is the only cap-hit policy (ADR #40 Rejected (f)); P1-5 DoD asserts it |
| **cost-breaker over-reports** (CC `total_cost_usd` uses Anthropic pricing; DeepSeek auto-caches — ADR #40 (h)(i), Phase 0 RESULT point 3) | P1-4, P1-5 | `--max-budget-usd` is the breaker BUT it fires on the inflated cost → set the cap with headroom for the over-report factor measured in Phase 0; record the actual DeepSeek-dashboard cost in run-record `notes` so the cap is calibrated against real billing, not the over-reported figure |
| rule-5 ripple misses an enumeration | P2-2 | grep the capability across ALL decision-point docs (not just the 4 originally named); `disconnect_check.py` catches broken links, the grep catches stale enum contents — both load-bearing |
| Phase 3 routing lands on an unproven wrapper | P3-1, P3-2 | DAG-enforced `depends_on` P1-7 edge (not prose); Phase-3 gate requires N≥2 dogfooded items |
| `claude -p` flag drift on a CC upgrade | P1-4 | flag-surface manifest atop `hetero_review.py` (flags + verified CC version); P1-7's mocked substrate cannot catch this — the manifest is the at-failure-site reference; `--bare` as the floor |
| 异源 cost runaway | P1-4, P1-5 | `--max-budget-usd` hard breaker per subprocess (calibrated for over-report — see above); default cap conservative (2); opt-in only |
| P1-7 does not exercise the live substrate | P1-7 | acknowledged: live-substrate evidence = the flag-surface manifest (P1-4) + the N≥2 dogfood runs (§6 Phase-3 gate); P1-7 proves bookkeeping, not substrate reliability |

## 9. Out of scope

- Re-debating ADR #40 (the decision is settled; this plan only operationalizes it).
- The rejected custom-Agent-SDK-harness path (proposal "No Phase 4"; ADR #40 Rejected (a)). If non-interactive CC + the LiteLLM fallback prove insufficient at scale, revisit the ADR then — do not pre-plan a harness here.
- Mutation testing (the eventual engine-level 异源 — ADR #38; maturity.md caveat 13 keeps it as the long-term engine, complementary to this orchestration-layer 异源).
- **ADR #40 (h) session-lifecycle refinements** (outer-ring novel-8) — consciously deferred, NOT silently dropped: the warmed-session pool; the stateless-vs-reuse A/B test (ADR #40 (h)(iii) deferred it to Phase 0, but Phase 0 measured cache + reliability, not the A/B, so the A/B remains open); the reuse-exception opt-in paths (human-driven interactive 异源 `--resume`; cumulative multi-file 异源 Coder; same-model-family determinism replay). Stateless default (`--no-session-persistence`) is what P1-4 delivers; these refinements re-surface if a consistency-review or determinism-replay use case binds.
- Outcome-axis judgment (is 异源 *correct* / does it improve the product) — human only.

## 10. Cross-cutting tasks (across items)

| Task | Starts at | Note | Workspace rule |
| --- | --- | --- | --- |
| dogfooding self-gate | P1-7 | the wrapper's own wiring test is the inner-ring gate for this feature | rule 1 |
| rule-5 doc-audit | P2-2 | grep the capability across every decision-point doc (the widened set); doc-audit is a required step | rule 5 |
| ADR already landed | — | ADR #40 IS the decision anchor — no new ADR needed unless a non-obvious sub-decision arises during implementation | rule 6 |
| match the closest exemplar | P1-4 | `hetero_review.py` mirrors the self-contained per-script convention; `hetero_review_wiring.py` mirrors `plan_queue_loop_state_wiring.py` | rule 7 |
| loading-chain reachability | P1-6, P2-2 | the 异源 path must be reachable at the decision-point doc a model reads at the point of need | rule 8 |
| commit only when asked | all | `parallel-dev:` prefix, direct-to-main, one commit per logical change, `Co-Authored-By`; no auto-commit | rule 9 |
| agent-oriented doc voice | all | enumerations as bullet lists; one term per concept; gloss inline cross-references | rule 10 |

## Appendix: execution notes

- **First action**: P1-1, P1-2, P1-3 together (independent S roots). Then P1-4.
- **Highest-stakes items**: P1-4 and P1-5 (the wrapper IS the 异源 engine). Their outer ring is same-source `solidforge:code-reviewer` PLUS an additive 异源 second opinion (headless `claude -p --settings ~/.claude/settings-deepseek.json`) per the staged-dogfood plan — same-source primary retained.
- **After P1-7**: the wrapper itself becomes an outer-ring option for Phase 2/3 items (true dogfood); the Phase-3 gate requires N≥2 such dogfooded items before P3-2 ships.
- **Profile reuse**: `~/.claude/settings-deepseek.json` is the template for `profiles/deepseek.json`; the committed profile carries no real token.
