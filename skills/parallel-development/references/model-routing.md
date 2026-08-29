# Model routing — per-stage provider policy

> Single source of truth for WHICH model family runs at WHICH stage of the convergence loop. Authority: ADR #40 (`design-decisions.md §40`) + the operational plan (`docs/hetero-orchestration-proposal.md §3`). On conflict, ADR #40 wins.

## Profile naming — the three-level doctrine (borrowed from/with the pi+ds ports; ROUTE and FAMILY are DIFFERENT axes and never mix)

| Level | Carrier | Examples (pi routes) | Role |
| --- | --- | --- | --- |
| ROUTE | the profile FILENAME | `zai-coding-cn` / `qwen-bailian` / `minimax-cn` / `deepseek` | the credential+endpoint CHANNEL; the token var derives from it |
| FAMILY | the `_family` FIELD | `qwen` / `glm` / `minimax` / `deepseek` | the MODEL LINEAGE — the same/different-family judgment unit |
| MODEL | the `model` FIELD | `qwen3.8-max` / `glm-5.3` / `MiniMax-M3` | the pinned per-generation id, editable per generation, NEVER part of the filename |

Relations: one family rides MANY routes (`qwen`: the token-plan subscription channel + the Bailian pay-per-use channel; `glm`: pi's zai-coding-cn coding route — zai/bigmodel/zhipu are brands of ONE lineage); one route may serve MANY families (the token-plan channel serves qwen/glm/deepseek/kimi — `_family` names the PINNED MODEL's lineage, not the route's); profile names are version-free (the generation lives in `model`). The same-family/different-family judgment reads `_family` — never the route name.

## Routing policy (per stage)

| Stage | Mode | Provider (example) | Always? | Role |
| --- | --- | --- | --- | --- |
| author (main orchestrator) | interactive CC, unchanged | GLM 5.2 (BigModel) | yes | deep reasoning + format-reliable; no added risk |
| adversarial review (same-family) | in-process Agent tool | GLM (primary) | **yes (primary)** | fast, cheap, Claude-grade tool discipline, reliable floor |
| adversarial review (different-family) | non-interactive subprocess (`hetero_review.py`) | DeepSeek v4 pro | **opt-in (high-stakes)** | adversarial second opinion; cross-family blind-spot check |
| research (researcher / Explore fan-out) | non-interactive subprocess or tier | DeepSeek flash / GLM-4.7 | as needed | fan-out; cost-dominated |
| normalize / constraints-check / freeze / fast_gate / arch-contract | deterministic code | — (no model) | — | model-independent |
| inner-ring Coder (GREEN) | same-family (default) | GLM | yes | highest tool-call-reliability risk (Morph caveat); consider different-family LAST |

## different-family priority

**reviewer > research > Coder.** The reviewer is the safest different-family entry point (read-only + structured findings, narrow tool surface, tolerable occasional malformation). The inner-ring Coder carries the highest tool-call-reliability risk and is the LAST different-family candidate — it is same-family by default.

## Research-tier routing (Phase 3, P3-1)

The research / Explore fan-out tier is cost-dominated (multi-source gathering, broad read) — a cheap backend is the right tier. Route it to DeepSeek flash by reusing the SAME non-interactive-CC substrate as the different-family reviewer (proven by `hetero_review.py` Phase 1):

```bash
# PI PORT: same substrate family as hetero_review.py (PI-SUBSTRATE MANIFEST);
# budget/turn caps are enforced wrapper-side from the live JSONL stream.
pi --mode json -p --no-session -e <pkg>/extensions/sf-providers \
  --model deepseek/deepseek-v4-flash \
  --tools read,grep,find \
  "<research prompt>"
```

Notes:

- This is NOT a new engine — it reuses the deepseek route profile + the `pi --mode json` spawning pattern. The orchestrator spawns it directly for research fan-out (analogous to how it spawns `hetero_review.py` for the different-family review).
- The research prompt is NOT adversarial (unlike the reviewer) — it gathers + cites. Trust/provenance on research findings stays the blueprint-crafting `research_constraints.py` oracle (sources-cited / staging / cost-bounded), NOT the cheap backend's judgment.
- The per-item binding (WHICH plan-queue items route research to the cheap backend) is the Phase 3 P3-2 `hetero` hint on plan-queue items.
- Reliability caveat: the cheap-backend tool-call reliability on research tools (WebSearch/WebFetch) is a measured-by-dogfood property, not assumed (the Morph caveat, generalized from the reviewer tier).

## Opt-in trigger (the different-family reviewer)

The different-family reviewer runs ONLY on high-stakes items; default items pay zero added cost (same-family only). The trigger conditions (ADR #40 (b)):

- ADR-level decisions.
- security- or correctness-sensitive diffs.
- a same-family verdict that is partially-satisfied or low-confidence.

This trigger list is the ADR #40 (b) prose — a **human-judged classifier, NOT an automated one**. The orchestrator (interactive CC) decides per item; there is no deterministic gate that forces different-family. Per-item automation (a `hetero` hint on plan-queue items) lands in Phase 3 (P3-2) and is itself a recommendation the human judge can override.

## Substrate

different-family runs as a non-interactive Claude Code subprocess spawned by `infra/scripts/hetero_review.py`:

```bash
claude -p --settings profiles/<backend>.json --model <alias> \
  --output-format stream-json --verbose --include-partial-messages \
  --json-schema <violation-log.schema.json> \
  --permission-mode bypassPermissions --no-session-persistence \
  --max-budget-usd <cap> --max-turns <cap> [-p "<adversarial prompt>"]
```

(The argv is built by `_claude_argv` — the wrapper's FLAG-SURFACE MANIFEST is the
authority. The stream mode emits a progress heartbeat to STDERR every 30s and the
result carries `provider_runs[]` telemetry; stdout stays the single result JSON.
`--no-stream` restores the legacy json envelope. ADR #52.)

The subprocess inherits SKILL.md / hooks / Skills / MCP — the skill substrate is NOT stranded. Provider config is process-level (`--settings`), so the different-family backend crosses providers without an aggregator proxy. The wrapper drives `loop_state` truthfully around the subprocess (ADR #39, ADR #40 (g)). See [convergent-loop.md](convergent-loop.md) § different-family adversarial review for the multi-round debate loop + cap + termination semantics.

**Provider profile + API key** (provider-template + token-injection pattern):

- `profiles/<provider>.json` (committed templates — `deepseek`, `bigmodel`, `qwen3`, `minimax`, ...). Each carries ROUTING ONLY (`ANTHROPIC_BASE_URL` + model aliases) — NO `ANTHROPIC_AUTH_TOKEN` field, NO `${...}` ceremony.
- **Responses API surface (deepseek)**: NOT a registered route — pi-side opt-in only, via same-id upsert in the user's `~/.pi/agent/models.json` (CC structurally cannot speak it; `_family` unchanged so zero hetero-axis gain). See PORTING-PLAN.md §17 for the decision, the code-verified upsert merge semantics, the official-docs cross-check, and the ready-to-use facts snapshot.
- **Token var = convention**: `<UPPERCASE-FILENAME>_ANTHROPIC_AUTH_TOKEN` — `deepseek` → `DEEPSEEK_ANTHROPIC_AUTH_TOKEN`, `qwen3` → `QWEN3_ANTHROPIC_AUTH_TOKEN`, `openai-compat` → `OPENAI_COMPAT_ANTHROPIC_AUTH_TOKEN`. Override the name via the template's optional `_token_env` (rarely needed).
- The token is NOT in the profile. Set it in your shell (`export DEEPSEEK_ANTHROPIC_AUTH_TOKEN=...`), in the arm-provisioned `.env.solidforge` (shell wins), or in your app `.env`. The wrapper reads all three (`shell > .env.solidforge > .env`), INJECTS the token as `ANTHROPIC_AUTH_TOKEN` into a throwaway chmod-600 temp settings file, passes it to `claude -p`, and unlinks it (Claude Code does NOT expand `${VAR}` itself — verified CC v2.1.201). `cp .env.solidforge.example .env.solidforge` to start (the `.example` is committed; `.env.solidforge` is gitignored).
- **Namespace isolation (sole source)**: the `_ANTHROPIC_AUTH_TOKEN` suffix is the ONLY var the wrapper reads for a provider's token. The provider's native `<FILENAME>_API_KEY` (e.g. `DEEPSEEK_API_KEY`) is NEVER read — it may be set in the same env for a different tool/SDK (possibly a different key/quota), so reading it would risk a credential meant for another use. A project may carry both `DEEPSEEK_API_KEY` (its own native-SDK use) and `DEEPSEEK_ANTHROPIC_AUTH_TOKEN` (this substrate) without collision — by design. See the namespace-isolation ADR.
- **Provider selection**: `--profile deepseek` (a NAME, not a path) or `export HETERO_PROFILE=deepseek`. Default `deepseek`.
- **Add a provider** (zero code change): drop `profiles/<name>.json` with routing only + `export <UPPERCASE_NAME>_ANTHROPIC_AUTH_TOKEN=...` → `hetero_review.py --profile <name>` works. See `profiles/qwen3.json` for a worked example.
- **Dual-/multi-different-family** (extensibility): `--profile deepseek,qwen3` runs each backend independently and merges findings (omit `--profile` to fall back to `HETERO_PROFILE` from `<project>/.env.solidforge` / env, default `deepseek` — a hardcoded `--profile` silently drops other configured providers, ADR #48/#5) (each finding tagged with its `provider` for N-way reconciliation). Pick two providers NEITHER of which is the orchestrator's primary — e.g. in a GLM-orchestrated project, `deepseek` + `qwen3` (BigModel is same-family there, so it is not a true different-family in that project).
- Set `--budget-usd` as a COARSE breaker (default 12.0) — NOT real cost: for non-Anthropic backends the API returns tokens only (no price field), so CC's USD is structurally disconnected from provider spend (ADR #42; and CC v2.1.238 prices unrecognized models at premium fallback rates — measured $0.24 for ONE tiny turn — so the old default 4.0 held only ~16 tiny turns of headroom; ADR #42 amendment). If a review still trips the cap it DEGRADES (verdict stays pass/rewrite from the other providers; ADR #41), not rewrites — except the stream-byte cap, which MALFORMS loudly (a runaway stream is the 2026-08-21 incident class; ADR #52).
- The reliable provider-independent bounds, in firing order (ADR #52):
  - `--max-turns` — default 60, or `$HETERO_MAX_TURNS`; print-mode CC has NO default turn limit
  - `--max-stream-bytes` — default 64MiB, or `$HETERO_MAX_STREAM_BYTES`
  - the wall-clock `--timeout` (ADR #43)
  - `step_cap_S` globally (the loop's own step accounting)
- **Subprocess timeout**: `--timeout <seconds>` (default 600, or `$HETERO_TIMEOUT`). A cold large diff can exceed 600s and return a `hetero-subprocess-timeout` malformation. For a known-cold large review: raise `--timeout` (e.g. 1200–1800s). Do NOT remap a profile alias to dodge a timeout — cold-start is transient (DeepSeek auto-caches ~99% after the first call; ADR #40 (h)(i)), and a global alias remap permanently sacrifices review depth on warm calls (ADR #43; the ONE measured exception: the deepseek profile's pro→flash demotion, ADR #53 — persistent pathology, not transient cold-start). Set `HETERO_TIMEOUT` in `.env.solidforge` to fix the cap per-project. While a subprocess runs, the wrapper heartbeats to stderr every 30s (elapsed / stream bytes / assistant events / the RESOLVED model / idle) — a live stream and a hang are distinguishable without socket forensics (ADR #52).

## Reconciliation (same-family + different-family findings)

| Findings | Action |
| --- | --- |
| both same-family + different-family report | high-confidence; adopt |
| same-family only | adopt (primary status) |
| different-family only | strong signal (cross-family independent find = same-family blind spot); escalate for adjudication |
| neither | pass |
| different-family DEGRADED (substrate error: budget/turn cap, provider overwhelm) | adopt the same-family primary (different-family contributed nothing); `degraded:true` + a persisted `hetero-degraded-<subtype>` fingerprint distinguish it from a clean pass (ADR #41) |

## Cost model

- Default item (low/medium risk): same-family reviewer only — zero added cost.
- Opt-in item (high-stakes): same-family + different-family × ≤ cap rounds + reconciliation.
- Deterministic stages, author, research: unchanged (same-family) except the opt-in research-tier routing (Phase 3, P3-1).

Note (ADR #42 / #41 / #52): `--budget-usd` is a runaway breaker, not an accounting figure — for non-Anthropic backends CC's `total_cost_usd` is structurally fictional (the API returns tokens, not price; the earlier "over-reports vs DeepSeek cache-aware billing" framing, ADR #40 (h)(i), was a DeepSeek-specific understatement of a general truth). It defaults to 12.0 — CC v2.1.238 prices unrecognized models at premium fallback rates (measured $0.24 for one tiny turn), so the cap fires on a mismeasure (ADR #42 amendment); the reliable provider-independent bounds are the wrapper's `--max-turns` + `--max-stream-bytes` + `--timeout` + `step_cap_S` (ADR #52); DeepSeek auto-caches (~99% hit rate via its own Context Caching — Phase 0 RESULT). A review that still trips the cap DEGRADES (`degraded:true`, persisted `hetero-degraded-error_max_budget_usd` fingerprint), not rewrites.

## Out of scope

- different-family as the PRIMARY reviewer (rejected — it would drop the reliability + cost floor; ADR #40 (b) Rejected).
- cap-hit silent-pick ("timeout → trust same-family") — rejected; cap-hit escalates to human (ADR #40 Rejected (f)).
- The inner-ring Coder as an different-family candidate before the reviewer + research tiers are proven.
