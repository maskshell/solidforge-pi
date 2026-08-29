---
name: cross-source-review
description: cross-source-review — a same-family (同源, fresh-context) + different-family (异源) cross multi-round review engine that drives a doc-shaped artifact to SUBSTANTIVE convergence. Use it when a high-quality document needs adversarial cross-source review to convergence — "cross-review this requirements doc", "converge this design doc", "异源 review this spec/wiki page", "drive 同源+异源 review on this artifact". Produces a converged artifact + an honest convergence-record. NOT for code review (route to parallel-development), spec/arch-design authoring (blueprint-crafting), or research gathering (blueprint-crafting researcher). Does NOT judge whether the doc is "right" (outcome-axis — human). Phase A activation is EXPLICIT invocation (`/cross-source-review`); auto-routing is deferred.
---

# Cross Source Review

Drives **same-family** (same-family, fresh-context) + **different-family** (different-family, different-family) LLM cross multi-round review to **substantive convergence** on doc-shaped artifacts — a requirements input before `blueprint-crafting`, a design doc, a wiki page. It is the missing convergence layer upstream of `blueprint-crafting` (which is process-axis, same-family only) and reusable externally (e.g. fedaot wiki review).

## Core Positioning

### Substantive convergence, not zero-finding

A persistent adversarial reviewer always finds finer citation flaws; demanding zero findings loops forever. **Substantive convergence** = the core claims are coverage-verified AND no new BLOCKER-class finding appears for ≥2 rounds. Advisory findings never block (workspace rule 4). Caps bound the loop; cap-hit escalates to the human, never silent-pick (pd ADR #40 (e)).

### Process-axis, not outcome-axis

The skill converges a doc's PROCESS-AXIS quality (well-formed, internally consistent, citation-accurate, coverage-complete). Whether the doc captures the RIGHT requirement is OUTCOME-AXIS — human only. The convergence-record carries `substantive_converged` (process) and never claims outcome correctness.

### Same-family primary; different-family additive

The same-family leg (fresh-context, same family) is PRIMARY and always runs. The different-family leg (cross-family, e.g. DeepSeek) is an opt-in adversarial second opinion that catches same-family blind spots. Both legs are read-only and barred from outcome-axis judgment.

## Scope

- **In**: drive same-family + different-family cross multi-round review of a doc-shaped artifact to substantive convergence; emit the converged artifact + a convergence-record.
- **Out**: code review (`parallel-development`); spec/arch-design authoring (`blueprint-crafting`); research gathering (`blueprint-crafting` researcher); outcome-axis judgment (human).

### Scope Guard (entry-time detection)

- Deliverable is source/test code, or a code diff under review → route to `parallel-development`.
- Deliverable is authoring/rewriting a spec, arch-design, iteration-plan, or research → route to `blueprint-crafting`.
- The request is "is this the right requirement / right conclusion?" → outcome-axis, human only.

The guard is soft (remind + route, not refuse). Phase A relies on **explicit invocation** (`/cross-source-review`); the 3-way `trigger_check` activation partition is DEFERRED to maturation (proposal §9 Q4) — explicit invocation minimizes, but does not zero, routing collision, which is why a Scope Guard still ships.

## Quick Start

You are the orchestrator. The legs are read-only agents/subprocesses; the driver alternates them. Run in order; do not wait for the user between rounds.

**Act from this Quick Start — don't reverse-engineer the legs.** The protocol is this section; the legs are INVOKED, not read: invoke the `subagent` tool with `agent="solidforge:doc-reviewer"` (its system prompt is its own — do NOT open the agent file); run `hetero_doc_review.py` (the different-family leg — throughout this skill, the `hetero_*` code prefix names the different-family substrate) via the step-2 CLI (do NOT read its source — the CLI is the contract). Do not hand-validate the schemas — `converge.py` does that; you pass each leg's findings to it. Open `references/install.md` ONLY on a first run in a new project if the provider token/profile is not already clear from the env. The different-family leg's provider(s) are selected by the wrapper from `HETERO_DOC_PROFILE` (settable in `<cwd>/.env.solidforge`; comma-list = dual-different-family; default `deepseek`) — do NOT pass a hardcoded `--profile`. Each profile's token is its `<NAME>_ANTHROPIC_AUTH_TOKEN` env var (e.g. `DEEPSEEK_ANTHROPIC_AUTH_TOKEN`) — the SOLE source for that profile; do NOT look for or set `<NAME>_API_KEY` (namespace isolation — the `_ANTHROPIC_AUTH_TOKEN` suffix scopes the credential to this substrate; see install.md). The wrapper self-loads `<cwd>/.env.solidforge` then `<cwd>/.env` (shell wins) before reading the token, so a token set in `.env.solidforge` is absent from the shell env — do NOT preflight the token via `echo $VAR` / `os.environ` (a false negative); run the step-2 wrapper directly, which fail-fasts with a clear error if the token is genuinely missing.

1. **Frame** — identify the artifact under review + its authoritative reference (a source doc, or "self-contained / no external authority"). **Enumerate the core claims** (the load-bearing assertions each leg must verify — the coverage-verified prong checks these; omit them and that prong is vacuously true). **Declare the size tier**: short (cap=2) for a single-section / few-claim doc; long (cap=5–7) for a multi-section doc (heuristic: ≥~5 sections or ≥~300 lines — orchestrator judgment, stated in the record). Then open the run-progress sidecar (see the section below): create the run dir and append `run-start` (artifact / tier / cap).

2. **Round loop** (same-family ↔ different-family, orchestrator-driven) — each round:
   - Run the **same-family leg** — invoke the `subagent` tool with `agent="solidforge:doc-reviewer"` (a fresh, independent context; it returns a doc-findings object). Append `same-family-spawn` before and `same-family-complete` (with the findings count) after (run-progress sidecar, below). The subagent tool streams the child's live internals into its tool panel while it runs (current tool call, turn count, elapsed/idle — the sf-subagents extension); you do NOT need to narrate it yourself.
   - Reconcile: revise the artifact per accepted findings, or reject a finding with rationale. RECORD each finding's disposition at reconcile time (the producing step for the record's per-round dispositions — fix A): `fixed` = accepted, artifact revised; `rejected` = declined, with rationale (incl. coverage disclosures — not defects, carried in coverage notes); `escalated` = different-family-only findings, escalating to the human (the skill's only named escalation target). Append `reconcile` (fixed / rejected / escalated counts) to the sidecar at each reconcile.
   - Run the **different-family leg** — from the **project root** (the wrapper reads `<cwd>/.env.solidforge`), invoke the `hetero_doc_review` TOOL with `artifact: <doc>`, `authority: <ref-or-empty>`, `priorFindings: <round-json>` (fed the same-family findings as prior, so it hunts the gap, not restatements), and `progressFile: "<run-dir>/progress.jsonl"` → doc-findings. **Do NOT pass `profile`** — the wrapper resolves the provider(s) from `HETERO_DOC_PROFILE` (loaded from `<cwd>/.env.solidforge`, shell wins; comma-list = dual-different-family; default `deepseek`); a hardcoded profile silently drops every other configured provider. Run from the project root — do NOT `cd` into the skill dir — or the token will not resolve. While it runs you have THREE live views, all zero-interaction: (1) the tool's own live per-provider panel — `leg-progress` events at event granularity (every grandchild tool call + turn: `read docs/x.md`, `turn 3 · $0.0123`) plus an ADR #52 `hetero-heartbeat` every 30s (elapsed / stream bytes / assistant events / the RESOLVED model / idle), derived from the wrapper's stderr and DISPLAY-ONLY — the tool result is the wrapper's stdout result JSON VERBATIM (`provider_runs[]` stamped in it), with progress lines never entering it; (2) the run-progress sidecar + the sf-progress footer strip (below); (3) `csr_progress.py status <run-dir> --watch 5` from any second terminal. FALLBACK (harnesses without the sf-hetero extension — plain `pi -p` without `-e`, non-pi shells): run `python3 "<skill-dir>/infra/scripts/hetero_doc_review.py" --artifact <doc> --authority <ref-or-empty> --prior-findings <round-json> --progress-file "<run-dir>/progress.jsonl"` via bash — there the tool RESULT merges stderr with stdout, so treat leading `leg-progress` / `hetero-heartbeat` lines as progress, not errors, and parse the LAST JSON object on stdout; a pre-leg fail-fast (missing token / unknown profile) surfaces as a non-zero exit with the cause in that same output (via the tool: a clean `isError` result).
   - Reconcile again. Apply the per-round reconciliation table (both-report→adopt; same-family-only→adopt; different-family-only→escalate; neither→pass; DEGRADED→adopt same-family).

3. **Convergence judgment** — substantive_converged when core claims are coverage-verified AND no new Blocker for ≥2 rounds. If the cap is hit without convergence → `adversarial-stalemate`, escalate to human (never silent-pick). Verify each leg's factual/citation claims against source independently — do not blind-trust either source. Append `round-end` (round / new_blockers) after each round, and `run-end` (outcome: converged or adversarial-stalemate or cap-hit or aborted) at the terminal judgment (run-progress sidecar, below).

4. **Emit** — the converged artifact + a `convergence-record` (`infra/schemas/convergence-record.schema.json`): rounds — each carrying the reconciled findings AND their per-finding dispositions, so a reader can list what was found and what was done about it (retention fix A; the counts-only record is obsolete) — `substantive_converged`, coverage notes, stalemate flag.

The pluggable seam: the driver takes `findings-schema` as a parameter (default doc-findings; a future code-shaped caller passes `violation-log`) and the same-family leg as a callback (default `solidforge:doc-reviewer`). This keeps a future code-domain caller a thin adaptation, not a rewrite (proposal §3).

### Run-progress sidecar (ADR #61) — live + external observability

A csr run is observable end to end at THREE layers, all zero-interaction (the pi-port replacement for upstream's ADR #62 narration loop — pi has no background bash, and substrate-level streaming needs no orchestrator polling): (1) IN-SESSION, PER-LEG — pi's bash tool streams the wrapper's stderr live (event-granularity `leg-progress` lines + the 30s heartbeat), and the `subagent` tool streams the same-family child's internals itself; (2) IN-SESSION, RUN-LEVEL — the `sf-progress` extension (bundled) tails the newest `progress.jsonl` and renders a condensed footer strip (`ctx.ui.setStatus`) — round k/cap, phase, findings, terminal state — visible no matter which tool is on screen; (3) EXTERNAL — any second terminal: `tail -f <run-dir>/progress.jsonl`, or `csr_progress.py status <run-dir> [--watch 5]` for a one-screen render (round k of cap, phase + last-event age, leg + reconcile totals, terminal state; torn last lines counted, never fatal).

At Frame, create a run dir `workspace/cross-source-review/runs/<stamp>-<slug>/` (gitignored, workspace rule 11) and append ONE JSONL event per state boundary via `csr_progress.py append --file <run-dir>/progress.jsonl --type <t> [--field k=v ...]` (strict registry — unknown type or field exits non-zero; bool/int/float coerced).

Event vocabulary (single-sourced with `csr_progress.py` EVENT_REGISTRY — the self-gate blocks drift in either direction):

- `run-start` — artifact / tier / cap (+authority) — writer: orchestrator, once at Frame
- `same-family-spawn` — round
- `same-family-complete` — round / findings
- `hetero-leg-start` — round / provider — writer: the WRAPPER
- `hetero-heartbeat` — provider / elapsed_s / model / idle_s / stream_bytes / events / assistant_events / killed — writer: the WRAPPER (stream mode, every 30s)
- `hetero-leg-end` — round / provider / outcome: ok or degraded or malformed (+findings / model / elapsed_s / degraded) — writer: the WRAPPER
- `reconcile` — round / fixed / rejected / escalated
- `round-end` — round / new_blockers
- `run-end` — outcome: converged or adversarial-stalemate or cap-hit or aborted (+rounds)

Best-effort contract: a failed progress append NEVER aborts the review — note it in the convergence-record coverage notes and continue. Pass `--progress-file <run-dir>/progress.jsonl` on every wrapper invocation; the wrapper appends its own leg + heartbeat events there (its stderr heartbeat + leg-progress events, ADR #52 + the pi live-disclosure addition, are unchanged). `leg-progress` lines are deliberately NOT sidecar events — stderr is the in-session channel, the sidecar keeps the strict boundary vocabulary above.

## Authority Chain

- `docs/proposal.md` = authoritative design (master; SUBSTANTIVE-CONVERGED).
- `docs/iteration-plan.md` = execution blueprint (Phase A work-items CSR-I0–CSR-I6).
- `docs/proposal.convergence.md` = the proposal's own cross-review trail (the skill dogfooded on its own design).

## Coordination with blueprint-crafting / parallel-development

- `primary-source-verification` (psv) is the outcome-axis additive layer (per-claim fetched-source verification). GATE MODE: when rule-13 conditions hold, psv runs FIRST as a load-bearing-claims gate (GO/NO-GO batch signal; the gate record is NOT a coverage record); its load-bearing list becomes this skill's core-claims frame; the authoritative full-M psv record follows this skill's convergence. See the psv SKILL.md.

- `blueprint-crafting` stays PURE (process-axis, same-family `plan-reviewer`, deterministic inner ring). It MAY call this skill for a different-family outer pass on its draft — calling a skill, not importing code.
- `parallel-development` owns code review. The different-family substrate here is a copy-PATTERN of pd's `infra/scripts/hetero_review.py` (workspace rule 7 — self-contained deployability; proposal §5 — Phase-B copy-vs-share is evidence-gated, NOT pre-committed); the function-signature contract is preserved + divergences logged for Phase-B viability.
- **Phase-A coordination note**: the bc/pd routing + call relationships above are CSR-side design intent. The reciprocal bc/pd Scope-Guard hints are DEFERRED per proposal §7 / Q4 (Phase A is explicit-invocation only); a reader following these claims into bc/pd will not yet find them mirrored there.
- `files_touched` boundary: this skill owns `cross-source-review/`. It does not modify bc or pd. Phase B (pd adopting this substrate: B1 import / B2 copy / B3 shared-lib) is evidence-gated and out of Phase-A scope.

## Self-Checks (Definition of Done)

A skill change is not done while any self-check fails (workspace rule 1). Run before commit:

```bash
python3 skills/cross-source-review/infra/test/disconnect_check.py        # structure + loading-chain
python3 skills/cross-source-review/infra/test/plugin_layout.py           # plugin.json + hooks.json + agents well-formed
python3 skills/cross-source-review/infra/test/findings_shape_check.py    # every leg emit path produces a doc-findings-valid object (mirror adapter_shape_check)
python3 skills/cross-source-review/infra/test/hetero_doc_guards.py       # different-family substrate guards: max-turns argv, streamed telemetry + heartbeat + leg-progress, byte-cap, wall-clock kill (ADR #52)
python3 skills/cross-source-review/infra/test/csr_progress_gates.py     # run-progress sidecar + live-disclosure contract: registry sync, append shape, status render, wrapper tee, step-2 wiring (ADR #61; pi live-disclosure)
python3 skills/cross-source-review/infra/test/convergence_policy_check.py # offline caps + stalemate + reconcile + core-claims-coverage round-trip (mirror hetero_review_wiring)
python3 skills/cross-source-review/infra/test/lint_self.py               # dogfood: lints this skill's own infra (ruff)
python3 skills/cross-source-review/infra/test/dogfood.py                 # runs the skill's own convergence loop on its own SKILL.md (skips gracefully when no API tokens; recorded log substitutes)
```

## Reference Files

- [proposal.md](docs/proposal.md) — authoritative design (the 3-skill inventory, non-goals, Phase-A ownership, Phase-B landing points, the §9 locked decisions).
- [iteration-plan.md](docs/iteration-plan.md) — Phase-A execution blueprint (CSR-I0–CSR-I6, DoD, DAG, risks).
- [install.md](references/install.md) — provisioning: the one token var, `.env` resolution, adding a custom provider profile + the token-var naming rule. csr is env-armed (no arm command — its gates are self-gates).
