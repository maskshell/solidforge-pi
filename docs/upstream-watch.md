# upstream-watch — the solidforge (CC reference implementation) design-lineage ledger

> **Relationship contract (2026-08-29, supersedes the port/sync framing):** [solidforge](https://github.com/maskshell/solidforge) (the Claude Code reference implementation) is **NOT a git upstream** of this repo. It is the **design lineage**: its ADR numbering remains the shared design authority, and knowledge flows BOTH ways (upstream ADR #57 is explicitly "borrowed from the pi + dsh ports"). There is no merge tracking, no shared remote, no sync obligation — this ledger is the replacement: a deliberate, reviewable record of what design content flowed, which direction, and what was consciously declined.
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
| #58 | blueprint_guard append-only AC→test carve-out | ✅ absorbed (2026-09-03: guard + carveout test verbatim-aligned from upstream; bridge contract unchanged) |
| — | **DESIGN OUTFLOW (2026-09-04)**: SF_PROJECT_NODE_BIN opt-in (node_modules/.bin with realpath containment) + arm.py tool_present truthfulness + arm-tools $ARGUMENTS wiring | ✅ adopted upstream (CC `8a19c2e`, 2026-09-06, after 7-round cross-review of the adoption plan) — and EXTENDED there (see the #63–#66 row below) |
| — | **SECURITY OUTFLOW (2026-09-03)**: `detect_toolchain.resolve_tool` project-venv fallback (executes repo-committed `.venv/bin/<tool>` under the gate's authority) + `loop_state_path` project-dir fallback | **DIVERGED here → backported same day** — both repos now PATH-only (opt-in via `SF_PROJECT_VENV_TOOLS=1`) / fail-closed; CC reference fixed in its own commit |
| #59 | fast_gate scopes to project root | ✅ absorbed (2026-09-14) — _in_project_root scope gate + main() early-exit + SCOPE docstring verbatim; coexists with our #63-#66 resolver form. Live probe: terminal-state breaker inert (see #60) |
| #60 | breaker inert on terminal state | ✅ absorbed (2026-09-14) — no-active-loop guard in check_breakers verbatim (ADR #60 comment included); live probe: status=converged + exploded budget → action ok |
| #61 | run-progress sidecar (`csr_progress.py` + `--progress-file`) | ✅ absorbed 2026-08-29 — verbatim port + beyond (sf-progress footer strip; registry kept byte-identical so sidecars stay cross-readable) |
| #63–#66 | node-bin adoption scope extension: collapse the SEVEN ad-hoc project-local resolution sites into the canonical resolver (pi carries all seven verbatim — its 0.2.7 fixed only resolve_tool+arm.py+prompt); PATH-wins for version-coupled tsc/vitest; `npx --no-install` arm gated (a PATH tool is not PATH resolution); report/gate agreement extended to the pytest/coverage + pip-audit/govulncheck legs | ✅ absorbed (2026-09-07, #63-#66 mirror) — seven sites collapsed onto dt.resolve_tool; CC's 26-probe suite adopted verbatim; execution sites prefixed too. Formerly live at `arch_contract_web.py:70-78/167-171/202-207`, `arch_contract_tests.py:575-587` (+pytest/coverage legs), `spectral_adapter.py:124-133`, `arch_contract_python.py:83-97`, `fast_gate.py:215-216`; CC's `detect_toolchain_test.py` (26 probes) is substrate-neutral and directly portable |
| #62 | in-session narration via CC background task | ❌ **deliberately NOT adopted** — superseded on pi by substrate streaming (bash stderr live / sf-subagents event panels / sf-progress strip); an LLM-behavior polling loop would burn orchestrator context and depend on prompt compliance. `csr_progress_gates.py` check 9 asserts the CC mechanic stays absent. |

<!-- Watch 2026-09-07 (upstream 222986a..c127ef9) — candidates, evidence not intent: -->
| #67 | web-claim-verifier agent — the fourth seat, a dedicated web-grounded single-claim adjudicator wired into csr's reconcile moments (+ csr/psv SKILL.md wiring, plugin_layout, design-decisions; 222986a) | ✅ absorbed (2026-09-14, acd67e0) — contract verbatim + pi substrate adaptation (no native web tools: bash/curl fetch, caller-URL reliable path, TODO(M3)-class note); csr/psv SKILL wiring + ADR #67 + plugin_layout 23 |
| #68 | csr engine: `runs/LATEST` stable pointer + first-narration watch line (b9b4a2f); wrapper derives the sidecar round from prior-findings instead of labeling every leg round=1 (c46a8f5, + csr_progress_gates test additions) | ✅ absorbed (2026-09-14, f7b07cd) — round derivation + runs/LATEST verbatim mechanics; the CC narration-pointer test assertions deliberately NOT absorbed (check 9 forbids that mechanic; ledger #62) |
| #69 | profiles: qwen haiku alias qwen3.7-flash → qwen3.8-flash in both qwen profiles (db0d064); deepseek pinned to the official alias with EFFORT_LEVEL=max, qwen all-tiers flash, GLM-5.3-Flash (e737680) | ✅ absorbed (2026-09-14) — flash-family model ids switched in all 6 profile copies + README route table; EFFORT_LEVEL/deepseek-alias = CC-substrate shaping, n/a on pi; live pong pending credentials (upstream's same-endpoint run is the evidence) |
| — | docs: prompt-content-spec six-layer content contract (a069195); ODP-1 promotion — L4/L6 land as workspace rules 14/15 (1756134); external-reference candidates from four external evaluations, csr-converged (c127ef9) | ✅ disposed by citation (2026-09-14): prompt-content-spec + the ODP-1 promotion (L4 no-unlabelled-gate-duplication, L6 runtime-assembly discipline) cited as the AUTHORING AUTHORITY in our contributor checklist — semantics apply verbatim to this tree's artifacts; the spec itself stays CC-workspace-scoped (coupled to their CLAUDE.md rule numbering), not ported. external-reference-candidates cited as the SHARED adoption backlog (no port — living doc, dual-maintenance); its pi-applicable gap-fills: C1 record env-provenance, C3a pd trigger check, C4 rubric single-sourcing, C8 reviewer micro-adoptions — each waits for its natural touchpoint per the backlog's own policy |

<!-- Watch 2026-09-16 (upstream c127ef9..f5cf684, 13 commits) — candidates, evidence not intent: -->
| #69 (ADR) | csr execution-process observability: csr_progress `stream` + all-runs view (session-scoped pointers); wrapper-distilled `round<k>-<provider>.stream.jsonl`; doc-findings `execution_trace`; agent Narration-discipline sections (4c1fcca, +1596) | ✅ absorbed (2026-09-16, pi re-base) — adversarial triage review caught 2 blockers BEFORE landing (CC event gate never fires on the pi wire → silent-empty logs; trace-append omitted → execution_trace dead-on-arrival). Landed: stream/trace-append/all-runs; wrapper distiller re-based on tool_execution_start + assistant message_end (no schema marker — no --json-schema on pi); OPTIONAL execution_trace + trace_entry schema; agent narration-discipline (pi tool names); SKILL 3 persistence call sites + roundIndex instruction (latent corruption fixed) + LATEST caveat; anti-silent-empty probe (fake pi child) + mechanics probes 10a-10c; narration poll loop still NOT adopted (#62) |
| — | backlog C9 (review-loop ladder discipline) + C1 retrofit clause (127c039) | informational — updates the cited shared backlog (README checklist already points there); C1's retrofit clause reads at the next record-schema touchpoint |
| — | evaluation-protocol line: coding-pass verification v1.2→v1.3, D1–D3 executed, paper §6.5, start-from-requirements guide (12 docs commits) | informational — CC-workspace methodology/eval line; cite on relevant authoring |

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
