# hetero_doc_review.py — divergence log (CSR-I3, Phase-A interface-compat)

> Authority: `docs/proposal.md` §5 (the Phase-A compatibility constraint, per finding F3 recorded in `docs/proposal.convergence.md`), §9 Q3 (no
> loop_state dependency); `docs/iteration-plan.md` §CSR-I3 (Phase-A compat constraint).
>
> Purpose: list EVERY intentional divergence from `parallel-development`'s
> `infra/scripts/hetero_review.py` (the copy-pattern source — rule 7) and ASSERT the
> preserved function-signature contract, so the Phase-B B1/B3 decision (proposal §5)
> stays data-driven rather than invalidated by silent drift. A future maintainer can
> see the drift is deliberate.
>
> Source file baseline: `skills/parallel-development/infra/scripts/hetero_review.py` as of
> commit `e40f328` (the copy-pattern source — rule 7). Line counts are NOT tracked here —
> they drift on any reformat (csr-doc-1 caught a stale logged-vs-actual count pair). Re-derive
> structural compatibility via the preserved-signature table + the divergence list below,
> not line counts. (Net delta is negative — loop_state driving was removed, change #4.)

## Preserved function-signature CONTRACT (Phase-A compat — proposal §5 / finding F3)

The following signatures are preserved EXACTLY (interface-level, not implementation).
Phase-B B1 (pd imports this substrate) / B3 (shared lib) can rely on them.

| Function | Preserved signature | Body status |
| --- | --- | --- |
| `_materialize_profile` | `(name) -> <temp-path-str>` | near-verbatim (temp suffix + error message adapted — see the minor-divergence bullets) |
| `_claude_argv` | `(profile, model, schema_json, prompt, budget_usd, allowed_tools, observe_hooks, max_turns=40, stream=True) -> list[str]` | extended ADDITIVELY by the ADR #52 shared substrate extension (trailing kwargs — pre-#52 positional callers stay source-compatible); flag surface per the CC v2.1.238 manifest |
| `run_claude` | `(argv, timeout_s, dry_run, dry_findings, dry_malform=False, dry_budget=False, guards=None) -> dict` | signature extended ADDITIVELY (`guards` kwarg, ADR #52 — stream telemetry + byte cap, passes through to the fallback retry); DEGRADE handling EXACT (ADR #41); ADDED the `_stdout_indicates_success` success-quirk guard before the substrate-error parse (see minor divergence); docstring annotations adapted |
| `_parse_cc_substrate_error` | `(raw) -> (subtype\|None, errors[list])` | verbatim (ADR #41 — preserved EXACTLY) |
| `_validate_findings_shape` | `(obj) -> str` (malformation fingerprint, '' on success) | signature preserved; validation LOGIC diverges — see change #3 |

Also preserved verbatim (not in the explicit contract list, but part of the substrate):

- `_load_dotenv` / `_load_dotenv_file` / `_project_root_for_env` / `_ENV_VAR_RE` / `_expand_env_values` / `_resolve_token_var` — provider-template + token-injection pattern (ADR #40).
- `_parse_json_return` / `_parse_stream_json` / `_extract_text` / `_try_json` / `_extract_json_object` / `_JSON_FENCE_RE` — fence-aware JSON parse (`_parse_stream_json` gained the ADR #52 partial-event prefix skip, both sides).
- `_run_streamed` / `_emit_heartbeat` / `HEARTBEAT_INTERVAL_S` / `_PARTIAL_EVENT_PREFIX` — NEW shared substrate functions (ADR #52): incremental Popen stream read, stderr heartbeat, resolved-model capture, byte-cap breaker.
- `DEGRADABLE_CC_SUBTYPES` — frozenset of recoverable CC subtypes (ADR #41), byte-identical.
- `_read_schema` — trivial schema reader.
- The FLAG-SURFACE MANIFEST docstring block — structure preserved; the `--json-schema` line names `doc-findings.schema.json` (was `violation-log.schema.json`) — faithful doc-adaptation, not a drift.
- The `--dry-run` / `--dry-run-malform` / `--dry-run-budget` offline paths (needed by CSR-I5's offline gate).
- The multi-provider merge (`per_provider` loop + provider-tagging when >1 backend + aggregate).
- Self-contained, pure stdlib, exits 0 on success (rule 7).

## Intentional divergences (the 5 mandated CSR-I3 changes + minor consequences)

### Change 1 — CLI surface (doc-domain: a doc has no diff/blueprint)

- `--diff` (required) → REMOVED.
- `--blueprint` (required) → REMOVED.
- `--artifact` (required) → ADDED (the doc under review).
- `--authority` (optional, default `""`) → ADDED (the authoritative reference; empty = self-contained — verify against the doc's own internal consistency).
- `--task-id`, `--embedded`, `--project-dir` → REMOVED (loop_state args — see change #4).
- `--profile` env-var default → `HETERO_DOC_PROFILE` (was `HETERO_PROFILE`) — keeps the doc wrapper's provider selection independent from pd's. The flag name `--profile` is unchanged.
- `--timeout` env-var default → `int(os.environ.get("HETERO_DOC_TIMEOUT", "600"))` (was a bare `default=600`) — mirrors pd's `HETERO_TIMEOUT`; keeps the per-call wait cap configurable without touching model selection (ADR #43). The flag name + the 600 default (when the env is unset) are unchanged.
- KEPT: `--profile`, `--model`, `--budget-usd`, `--allowed-tools`, `--timeout`, `--observe-hooks`, `--round-index`, `--prior-findings`, `--findings-schema`, `--dry-run`, `--dry-run-malform`, `--dry-run-budget`.

### Change 2 — adversarial_prompt (CODE-shaped → DOC-shaped)

- pd's prompt hunts `correctness bugs, security issues, performance problems, maintainability defects, loading-chain / rule-5 reachability gaps` against a diff + blueprint.
- This copy hunts the Q2 6 doc defect kinds (`contradiction` / `authority-chain-break` / `scope-creep` / `structural-gap` / `citation-error` / `coverage-gap`) against `--artifact` (optionally checked against `--authority`, or self-contained).
- BARRED from outcome-axis (proposal §2): does NOT judge whether the doc is "right".
- Returns a doc-findings object (was violation-log).
- KEPT: the prior-findings framing ("find what the primary MISSED, not what it already found") fed via `--prior-findings`.
- Signature changed: `(diff_ref, blueprint_ref, prior_findings, round_no)` → `(artifact_ref, authority_ref, prior_findings, round_no)`. This function is NOT in the preserved-contract list.

### Change 3 — findings schema (violation-log → doc-findings)

- `FINDINGS_SCHEMA` default → `infra/schemas/doc-findings.schema.json` (was `violation-log.schema.json`).
- `_validate_findings_shape` — signature `(obj) -> str` PRESERVED; validation LOGIC diverges:
  - accepts top-level `outcome_axis_respected` (bool) + `findings` (list) — was just `findings` (list).
  - per-finding `severity` ∈ {blocker, warning, coverage} — was {blocker, warning}. The `coverage` severity is PRESERVED per proposal §9 Q2 / plan-reviewer novel-3 (the reviewer's honest-disclosure mechanism, rule 3; DISTINCT from the `coverage-gap` KIND).
  - per-finding `kind` ∈ the 6 Q2 doc kinds — NEW check (violation-log had no `kind`).
- Two NEW malformation fingerprints introduced (doc-domain): `hetero-missing-outcome-axis`, `hetero-bad-kind`. The existing fingerprints (`hetero-not-object`, `hetero-missing-findings`, `hetero-finding-malformed`, `hetero-bad-severity`) are preserved verbatim.
- The `dry_findings` canned return is doc-findings-shaped `{"outcome_axis_respected": True, "findings": []}` — was violation-log-shaped `{"gate", "passed", "coverage", "findings"}`.

### Change 4 — REMOVE loop_state driving (proposal Q3: no loop_state dependency)

The doc domain does NOT drive pd's `loop_state` state machine. The CSR-I4 convergence driver (built separately) calls this wrapper once per round and assembles the convergence-record itself.

- DELETED: `_run_loop_state`, `LOOP_STATE_PY` constant, `drive_lifecycle` function + its call.
- DELETED: the `glob` import (was only used inside `drive_lifecycle` for run-record path resolution).
- The wrapper now runs ONE 异源 review and PRINTS a clean result dict:
  `{verdict, degraded, degraded_providers, findings_count, findings, coverage, malformation, providers}`
  (pre-ADR-#52 shape — the shared substrate extension below later added `provider_runs`).
- The `notes` field (pd feeds it to loop_state `record-outer`) and `run_record` field are DROPPED from the result.

### Change 5 — module docstring updated

- Describes the doc-domain purpose; points to `proposal.md` §3/§5/§8/§9 Q2+Q3 and `iteration-plan.md` §CSR-I3; notes it is a copy-pattern of pd's `hetero_review.py` (rule 7); records the exit-code contract.

## Minor consequential divergences (drift hygiene — not CSR-I3 mandates)

- Exit code semantics. pd always exits 0 because its loop_state/driver interprets the verdict. This wrapper is STANDALONE (no loop_state — proposal Q3), so it surfaces malformation via exit 1 for the CSR-I4 subprocess contract: `0` = produced a usable result (pass OR rewrite-due-to-blocker OR degrade — read the structured fields for which); `1` = malformation (could NOT parse a usable return); `2` = argument/IO error.
- `_extract_coverage` NEW helper. Doc-domain: the reviewer's "could not verify X" disclosures arrive as `coverage`-severity findings (the schema has NO top-level `coverage` array, unlike violation-log). The helper collects their evidence/location strings for the coverage trail. `per_provider.model_coverage` is sourced via this helper (was `(findings_obj or {}).get("coverage", [])`).
- `_load_prior` fallback shape. On a non-JSON prior, the synthetic stub is doc-findings-shaped `[{severity, kind:"citation-error", location:"prior-findings", evidence}]` — was violation-log-shaped `[{severity, rule, detail}]`. Prior is prompt-context only (never validated); the shape change is cosmetic consistency.
- `_resolve_profile_path` error message. Dropped the pd-specific "see model-routing.md" reference (cross-source-review has no model-routing.md). Now reads "Committed templates live in infra/scripts/profiles/.".
- `_materialize_profile` temp suffix. `-hetero-doc-<name>.json` (was `-hetero-<name>.json`) — domain-distinct, helps debugging when both wrappers run in the same project.
- `_materialize_profile` missing-token error message. Dropped the pd-specific "See model-routing.md." trailer. The convention-explanation body is preserved.
- `run_claude` + `_parse_json_return` + `_parse_stream_json` docstring annotations. "violation-log-shaped" → "doc-findings-shaped"; "P1-7 wiring test" → "CSR-I5 wiring gate". The LOGIC is preserved exactly; only docstring prose adapts.
- `_load_dotenv` docstring reframed to host-generic language (was pd's "Solid Forge vars" / "arm-provisioned default" — solidforge-centric wording in portable code). The BODY is unchanged (still reads `<cwd>/.env.solidforge` then `<cwd>/.env`, CWD-based — portable: csr reads the invoking project's env). The provisioning model + custom-provider guide live in `references/install.md`.
- `run_claude` ADDED the `_stdout_indicates_success(raw)` guard before the substrate-error parse: a non-zero exit WITH a success envelope (CC `subtype:"success"`) short-circuits to the normal parse — the result is usable. Surfaced by the CSR-I6 dogfood on a long doc (a CC backend quirk: `subtype:"success"` + `is_error:true` + non-zero exit; the wrapper had malformationed `hetero-cc-error:success`, discarding the result). ADR #41 DEGRADE handling unchanged (a genuinely-degraded/error envelope still degrades/malforms). pd's copy does NOT have this guard yet — candidate B2 pattern-refresh if pd hits the same quirk on its domain. The `run_claude` SIGNATURE is unchanged (preserved-contract).

## Shared substrate extension (ADR #52, 2026-08-21) — csr-first port

The bounded-turns + streamed-observability extension originated in CSR (the
2026-08-21 third-party incident was a csr invocation) and ports to pd's
`hetero_review.py` IDENTICALLY — the csr→pd direction again (ADR #45's shim
precedent; the ORIGINAL copy was pd→csr at CSR-I3), same rule-7 lockstep.
NO new divergence is introduced; the shared
surface (both copies, equivalent modulo the documented domain divergences):

- `_claude_argv` always passes `--max-turns` (default 60; env
  `HETERO_DOC_MAX_TURNS` / pd `HETERO_MAX_TURNS`) — print-mode CC has NO default
  turn limit; the hit DEGRADES (`error_max_turns`, ADR #41).
- DEFAULT spawn = stream-json read incrementally (Popen + reader threads):
  `--verbose` (required by `-p + stream-json` since CC v2.1.238) +
  `--include-partial-messages` (token deltas → liveness BEFORE a message
  completes). stderr heartbeat every 30s; the first assistant event's
  `message.model` is captured as the resolved model.
- `--max-stream-bytes` runaway breaker (default 64MiB; env
  `HETERO_DOC_MAX_STREAM_BYTES` / pd `HETERO_MAX_STREAM_BYTES`; trip =
  malformation `hetero-stream-bytes-cap`, NOT degradable). `--no-stream`
  restores the legacy single-envelope json spawn (output-surface fallback).
- Result gains `provider_runs[]` (name / model / assistant_events / stream_bytes /
  elapsed_s, + `cc_stderr_tail` when present — CC's stderr was previously
  discarded).
- `--budget-usd` default 4.0 → 12.0 (ADR #42 amendment: CC v2.1.238 prices
  unrecognized models at premium fallback rates — measured $0.24 per tiny turn —
  so the cap is a coarse breaker on a mismeasure; the old "headroom under the
  global 5.0 cap" rationale presumed real USD, which ADR #42 already established
  is fictional for non-Anthropic backends).
- `_run_claude_once` / `run_claude` gain a trailing `guards=None` kwarg
  (ADDITIVE — positional compatibility preserved per the contract table above).

## Supporting infra created alongside the wrapper (rule 7 — mirror the exemplar)

- `infra/scripts/profiles/deepseek.json` — sanitized copy of pd's `profiles/deepseek.json` (routing-only, no secret). The `_comment` cites CSR-I3 / rule 7 (copy-pattern) and notes DeepSeek's auto-cache rate (cold-start transient; ADR #43).
- `../../ruff.toml` (skill root) — mirrors pd's `skills/parallel-development/ruff.toml` `[lint]` rule set: selects `E4/E7/E9/F` only (real bug-catchers, no style churn), ignores E501. Necessary so the substrate (which deliberately uses `try/except/pass` and an `if/else` for the ADR #41 fingerprint logic, exactly like pd's source) lints under the SAME standard as its pd source. The repo-root `pyproject.toml` selects the broader `E/F/W/I/UP/B/SIM` set; this per-skill override is deliberate and matches pd exactly. Do NOT "widen" it without re-deriving the rule-7 rationale.
- `open(..., "r", encoding="utf-8")` → `open(..., encoding="utf-8")` at 4 sites (`_read_schema`, `_load_prior`, `_load_dotenv_file`, `_materialize_profile`). Behavior-preserving (read is the default); the UP015 lint is enforced under the repo-root config but not under the per-skill override — this cleanup keeps the file clean under EITHER config.

## Verification (CSR-I3 DoD)

- `uv run --no-project --with ruff ruff check skills/cross-source-review/infra/scripts/hetero_doc_review.py` → `All checks passed!` (under the per-skill `ruff.toml`).
- `python3 -c "import ast; ast.parse(open(...).read())"` → `AST PARSE OK`.
- `--dry-run` → exit 0, `{verdict: pass, findings_count: 0, findings: [], degraded: false, ...}`.
- `--dry-run-malform` → exit 1, `verdict: rewrite`, `malformation: "dry-run-malform"`, coverage notes the malformation.
- `--dry-run-budget` → exit 0 (ADR #41 — degrade is NOT a malformation), `degraded: true`, `degraded_providers: [{provider: deepseek, subtype: error_max_budget_usd, ...}]`.
- `_materialize_profile("deepseek")` → resolves `profiles/deepseek.json` + reads `DEEPSEEK_ANTHROPIC_AUTH_TOKEN` from `.env.solidforge` (via `_load_dotenv`), writes a chmod-600 temp, injects the token, preserves BASE_URL routing (token NOT printed in the verification).


---

## PI PORT divergences (solidforge-pi, 2026-08-25)

Substrate swapped `claude -p` -> `pi --mode json -p --no-session -e <sf-providers>`.
The CSR-I3 interface-compat table above describes the CC-era contract; the pi-port
divergences from it (all deliberate, all logged for Phase-B viability):

| Surface | CC era | pi port |
| --- | --- | --- |
| argv builder | `_claude_argv(profile, model, schema_json, prompt, budget, tools, observe_hooks, max_turns, stream)` | `_pi_argv(profile, model_override, prompt, allowed_tools)` — caps moved OFF argv (wrapper-side) |
| budget cap | `--max-budget-usd` CLI flag | wrapper-side: `usage.cost.total` accumulated from JSONL `message_end` (degrades `error_max_budget_usd`) |
| turns cap | `--max-turns` CLI flag | wrapper-side: assistant `message_end` count (degrades `error_max_turns`) |
| schema enforcement | `--json-schema` + structured-output retry fallback | defensive `_extract_json_object` + `_validate_findings_shape` only (`fell_back_to_unstructured` retired) |
| error envelopes | stdout `{is_error, subtype}` parse | `message_end.errorMessage` capture (rc=0) + rc!=0 malform; new fingerprint `hetero-api-error` |
| stream events | CC `stream_event` / `assistant` / `result` | pi `message_update` (prefix-skipped) / `message_end` (assistant turns + model + cost) |
| retired flags | `--no-stream`, `--observe-hooks`, `--findings-schema` | removed (pi has one output mode; no CC hook surface) |
| telemetry | `cc_stderr_tail` | `pi_stderr_tail` + `cost_usd` per provider run |

`run_claude` / `_run_claude_once` / `adversarial_prompt` / `_validate_findings_shape` /
`_extract_json_object` signatures preserved; guard gate re-based on the pi event
format (8 checks incl. budget/turns/api-error classification).


---

## PI PORT v2 — catalog routes + credential bridge (2026-08-25, informed by solidforge-dsh)

The v1 port registered custom providers in sf-providers (duplicating model facts).
That was wrong twice, both caught live:

1. **Wrong endpoint+protocol for GLM**: a custom `bigmodel` provider on the CC-era
   `/api/anthropic` surface rejected `GLM-5.3`/`GLM-5.3[1M]` (400 modelCode). The
   v1 "calibration" to GLM-5.2 was a MISDIAGNOSIS — pi's built-in route
   `zai-coding-cn` serves `glm-5.3` (ctx 1M) on the CODING endpoint
   (`/api/coding/paas/v4`, openai-completions, thinkingFormat zai); verified live.
2. **`[1M]`/`[1m]` is a context-window parameter**, not part of a model id: under
   pi the window is the catalog model's `contextWindow` property. `_pi_argv`
   strips the suffix; profile `model` fields carry bare catalog ids.

v2 design (dsh's FILENAME=ROUTE + catalog-inherit principle):
- profiles/ = route-named files (`zai-coding-cn.json`, `deepseek.json`,
  `minimax-cn.json`, `qwen-token-plan-cn.json`) carrying `_provider` (route),
  `model` (catalog id), `_family` (model lineage: glm/deepseek/minimax/qwen),
  `_token_env` (CC-convention source var; EMPTY = auth.json route). The CC-era
  `env` tier-alias block is REMOVED (inert under pi).
- CC-era profile NAMES (bigmodel/minimax/qwen3) resolve via `_PROFILE_ALIASES`
  so existing `.env.solidforge` HETERO_DOC_PROFILE values keep working.
- sf-providers registers NOTHING — it is a pure CREDENTIAL BRIDGE (CC token vars
  -> pi-ai route env names, never overriding auth.json/shell/user env). Every
  model fact is catalog-inherited and cannot drift.
- `_load_profile` skips the env fail-fast when `_token_env` is empty (route
  authenticates via pi auth.json — the zai-coding-cn default-provider case).

Live verification (2026-08-25): zai-coding-cn/glm-5.3 (blocker found; auth.json),
minimax-cn/MiniMax-M3 (bridge credential; cost_usd $0.0074 — catalog pricing makes
the wrapper-side budget cap REAL), deepseek/deepseek-v4-flash ($0.0032),
qwen-token-plan-cn/qwen3.8-max -> hetero-api-error 401 (expired token-plan key,
disclosed honestly).


---

## PI PORT v2.1 — qwen-bailian (pay-as-you-go DashScope route, 2026-08-25)

User correction: the QWEN3_ANTHROPIC_AUTH_TOKEN credential is an Alibaba Bailian
PAY-PER-USE DashScope key, not a token-plan subscription key. pi's catalog carries
ONLY the three token-plan qwen routes (cn-beijing / ap-southeast-1 x2) — no
Bailian route — and the token-plan endpoint REJECTS the pay-per-use key (the
earlier "401 expired key" reading was wrong: the key was fine, the ROUTE was wrong;
verified live — qwen3.8-max / qwen3.7-max / qwen-max all pong on
dashscope.aliyuncs.com/compatible-mode/v1).

This is the ONE legitimate sf-providers registration (no catalog facts to
duplicate — registration adds new information):

- route `qwen-bailian`: baseUrl dashscope compatible-mode/v1, openai-completions,
  credential `$QWEN3_ANTHROPIC_AUTH_TOKEN`; registered ONLY when that var is set.
- model facts (ctx 1M / maxTokens 131072 / reasoning / input) copied from the
  catalog's qwen3.8-max entry (same model, other billing channel); pay-per-use
  pricing unknown -> cost stays 0 (telemetry honestly reads 0).
- compat is LOAD-BEARING and copied verbatim: without `supportsDeveloperRole:false`
  pi sends the system prompt as an OpenAI `developer` role, which DashScope rejects
  (400 "developer is not one of [...]" — observed live, fixed by the compat copy).
  reasoning_content is parsed generically by pi-ai (no compat needed for that).
- profiles: `qwen-bailian.json` (new default for the qwen3 alias — the observed
  credential type); `qwen-token-plan-cn.json` retargeted to the
  QWEN_TOKEN_PLAN_CN_API_KEY convention (subscription users).

Live verification: qwen3 alias -> qwen-bailian/qwen3.8-max, full review pass
(68.6s, 3 turns, release-freeze contradiction blocker caught, malformation '').
All four hetero routes now live-verified: zai-coding-cn/glm-5.3, minimax-cn/
MiniMax-M3, deepseek/deepseek-v4-flash, qwen-bailian/qwen3.8-max.
