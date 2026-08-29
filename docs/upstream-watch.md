# upstream-watch — the solidforge-internal design-lineage ledger

> **Relationship contract (2026-08-29, supersedes the port/sync framing):** [solidforge-internal](https://github.com/maskshell/solidforge-internal) (the Claude Code reference implementation) is **NOT a git upstream** of this repo. It is the **design lineage**: its ADR numbering remains the shared design authority, and knowledge flows BOTH ways (upstream ADR #57 is explicitly "borrowed from the pi + dsh ports"). There is no merge tracking, no shared remote, no sync obligation — this ledger is the replacement: a deliberate, reviewable record of what design content flowed, which direction, and what was consciously declined.
>
> Maintained on every cross-repo absorption/outflow. An entry is evidence, not intent — "pending" rows are candidates discovered by watching upstream's ADR log, not commitments.

## The three-layer contract

| Layer | Content | Rule |
| --- | --- | --- |
| **Design** | ADRs, proposals, convergence methodology, defect taxonomies | Bidirectional citation; adopt the better argument regardless of origin. |
| **Substrate-neutral code** | Pure-stdlib engines (`converge.py`, `csr_progress.py`, `loop_state.py`, gates), schemas, fixtures, `agents/*.agent.md` | Verbatim alignment allowed, direction decided per-content (whoever's implementation is better wins; the loser aligns). Never renamed "for consistency". |
| **Substrate-bound code** | CC: `hooks/`, settings-file provider wiring, `claude -p` spawn surface, `--json-schema`, Task/background-task narration. pi: `extensions/` (sf-subagents / sf-hooks / sf-providers / sf-progress / sf-hetero), `pi --mode json` JSONL contracts, `onUpdate`/renderResult, `ctx.ui` surfaces | **Never cross-synced.** Only the PROBLEM LIST crosses: incident classes, breaker semantics, failure modes (e.g. ADR #52's runaway-stream incident class applies to both substrates; its mechanism does not). |

Rationale (measured 2026-08-29): shared substrate-neutral files diverge 0.1–3.3%; the csr wrapper diverged to 12.4% precisely where pi-native disclosure landed — structurally unreturnable to CC (no bash-stderr live streaming, no `onUpdate`, no footer status). The historical "sync" (commit `51bb3ca`) was already hand-merge, not git merge.

## Inflow ledger (upstream ADR → this repo)

Individually verified rows carry ✅/❌/⚠️; range rows ride the shared engine-file base (bc/psv/pas ≈0.1%, pd ≈3.3% divergence) without per-ADR forensics — the base IS the absorption evidence.

| Upstream ADR | Topic | Status |
| --- | --- | --- |
| #1–18 | engine core: stdlib-only, distribution, breakers/budgets, gates, run-record, L4, subagent model | absorbed (base) |
| #19–20 | plugin-model install, manifest author object | adapted (pi package manifest + `plugin_layout` gate) |
| #21–31 | external-skill gates (Spectral/Semgrep/Vale/oasdiff/Trivy/Checkov), agent roster | absorbed (base; agents 22/22 identical set) |
| #32–39 | loop-vs-engineering convergence, plan-queue→loop_state driving, inline-mode doctrine | absorbed (base / design) |
| #40–43 | 异源 substrate: additive review, DEGRADE semantics, USD-fiction caveat, timeout⊥tier | ✅ absorbed with pi adaptation (PI-SUBSTRATE MANIFEST in `hetero_doc_review.py`; same error subtypes, different spawn surface) |
| #44 | no LangGraph | absorbed (design) |
| #45 | CC `--json-schema` regressions, adapt-at-edge | n/a — pi has no `--json-schema`; the defensive parse is the ONLY path (divergence logged in the wrapper) |
| #46 | plugin = terminal product form | adapted (pi package is the terminal form; same conclusion, different plugin host) |
| #47 | token namespace isolation (`<NAME>_ANTHROPIC_AUTH_TOKEN` sole source) | ✅ absorbed (wrapper + sf-providers bridge keep the isolation) |
| #48 | dotenv loads before argparse env-default capture | ✅ absorbed (pi wrapper `_load_dotenv()` at top of `main()`) |
| #49–51 | neutral placeholders, format-commit stratification, logical-change commits | absorbed (base / practice) |
| #52 | bounded + observable substrate (streamed telemetry, heartbeat, breakers) | ✅ absorbed with pi adaptation (JSONL events; wrapper-side caps; heartbeat cadence identical) |
| #53 | deepseek review default → v4-flash | ✅ absorbed (`profiles/deepseek.json`) |
| #54 | rust edition derived from nearest manifest | absorbed (base) |
| #55 | dispatch names the agent AT the decision point | adapted (pi: `subagent` tool params in SKILL.md step tables) |
| #56 | TDD trinity (seam freeze / tracer-bullet / review-axis) | ✅ absorbed via sync-1 hand-merge + skill-level ODP |
| #57 | ROUTE/FAMILY/MODEL three-level naming | **OUTFLOW** — upstream borrowed it from this port (see below) |
| #58 | blueprint_guard append-only AC→test carve-out | ⚠️ **pending** — verified ABSENT here (upstream `blueprint_guard.py` 7 carve hits, ours 0; file drifted 159 lines). Candidate: port the carve-out semantics onto the pi file. |
| #59 | fast_gate scopes to project root | ⚠️ pending — fast_gate drift is only 17 lines; needs a deliberate next-watch check (absorbed vs adapted-out) |
| #60 | breaker inert on terminal state | ⚠️ pending — same check pass as #59 |
| #61 | run-progress sidecar (`csr_progress.py` + `--progress-file`) | ✅ absorbed 2026-08-29 — verbatim port + beyond (sf-progress footer strip; registry kept byte-identical so sidecars stay cross-readable) |
| #62 | in-session narration via CC background task | ❌ **deliberately NOT adopted** — superseded on pi by substrate streaming (bash stderr live / sf-subagents event panels / sf-progress strip); an LLM-behavior polling loop would burn orchestrator context and depend on prompt compliance. `csr_progress_gates.py` check 9 asserts the CC mechanic stays absent. |

## Outflow ledger (this repo → upstream)

| What | Evidence | Upstream disposition |
| --- | --- | --- |
| ROUTE/FAMILY/MODEL three-level profile naming (ADR #57) | upstream commit 2026-08-25: "borrowed from the pi + dsh ports" | adopted upstream |
| Live-disclosure problem statement (the `Working...` opacity class; event-granularity disclosure beats 30s liveness) | this repo's 2026-08-29 live-progress increment; upstream's #61/#62 solve the same need with CC mechanisms | open — upstream's #62 narration is their substrate's answer; if CC ever grows native tool-stream rendering, this design is the reference |
| sf-hetero stream-separation contract (stdout=content verbatim, stderr=display-only progress) | `extensions/sf-hetero/` + csr-converged proposal | open — CC Task tool equivalent would need the same separation |

## Substrate problem-list exchange (never code)

| Problem class | CC mechanism (theirs) | pi mechanism (ours) |
| --- | --- | --- |
| Runaway provider stream / hang indistinguishable | stream-json incremental + stderr heartbeat (ADR #52) | JSONL incremental + heartbeat + `leg-progress` events, client-side idle ticker |
| Credential namespacing per provider | settings-file injection | sf-providers env bridge (`*_ANTHROPIC_AUTH_TOKEN`) |
| Review-leg visibility in-session | background task + narration (ADR #62) | tool `onUpdate` panels + footer status strip |
| Guard rails on the loop | CC hooks (`hooks.json`) | sf-hooks `tool_call`/`tool_result` event bridge |

## Maintenance

- Update on every absorption/outflow event (new row + status), and on every watch pass over upstream's ADR log (resolve ⚠️ pending rows or leave them with a note).
- A watch pass is triggered by: upstream activity of interest (new ADR numbering beyond the last row here), or before any deliberate re-alignment of substrate-neutral files.
- This file is the single place the relationship is described; README and PORTING-PLAN link here instead of restating it.
