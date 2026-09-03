#!/usr/bin/env python3
"""hetero_review.py — different-family (different-family) adversarial review wrapper.

Spawns a non-interactive Claude Code subprocess on a DIFFERENT model family (e.g.
DeepSeek) as an additive adversarial second opinion on the same-family reviewer.
The same-family reviewer (solidforge:code-reviewer, ADR #16 outer ring) stays
PRIMARY; different-family is opt-in, high-stakes items only. The orchestrator (interactive CC)
stays on its primary provider unchanged.

Decision anchor: ADR #40 (`references/design-decisions.md §40`). Operational plan:
`docs/hetero-orchestration-proposal.md`. This wrapper is Phase 1 deliverable P1-4
(single-round core) + P1-5 (multi-round debate + cap).

==============================================================================
PI-SUBSTRATE MANIFEST — the pi port of the CC wrapper (pd's different-family
review substrate). If a pi upgrade breaks this wrapper, update this manifest +
`_pi_argv`. The csr sibling (cross-source-review/infra/scripts/hetero_doc_review.py)
carries the same port; divergences stay logged in the divergence logs (rule 7).

Substrate: `pi --mode json -p --no-session -e <pkg>/extensions/sf-providers`
(provider registry + credential bridge; token resolves from the SAME
<NAME>_ANTHROPIC_AUTH_TOKEN convention via inherited env). `--model` is a pi
catalog route/model pair composed from profiles/<name>.json (_provider + model);
the CC-era [1M]/[1m] context-window suffix is STRIPPED (pi: contextWindow is a
catalog property). loop_state driving (_run_loop_state) is UNCHANGED — a local
python subprocess pair, harness-free. Budget/turn caps are WRAPPER-SIDE from the
live JSONL stream (pi has no --max-budget-usd/--max-turns flags); degrade
subtypes match the CC era (error_max_budget_usd / error_max_turns, ADR #41/#52).
pi surfaces provider errors on the assistant message (stopReason=error +
errorMessage, rc=0) — classified hetero-api-error WITH the cause surfaced.
Flags used:
  pi --mode json -p --no-session
    -e <sf-providers-dir>          provider registry (bundled with the package)
    --model <route/model>          composed from profiles/<name>.json; precedence
                                   --model flag > <NAME>_MODEL env > profile default
    [--tools read,grep,find,bash]  read-only review surface
    "<adversarial prompt>"         positional (print mode)
==============================================================================

PROVIDER-TEMPLATE + TOKEN-INJECTION PATTERN:
  profiles/<provider>.json — committed TEMPLATES with ROUTING ONLY (BASE_URL +
                               model aliases). NO `ANTHROPIC_AUTH_TOKEN` field, NO
                               `${...}` token ceremony — drop in a template + set one
                               env var, that's it.
  token-var convention — `<UPPERCASE-FILENAME>_ANTHROPIC_AUTH_TOKEN` (deepseek ->
                               `DEEPSEEK_ANTHROPIC_AUTH_TOKEN`, qwen3 ->
                               `QWEN3_ANTHROPIC_AUTH_TOKEN`). Override with the
                               template's optional `_token_env` for a non-convention name.
  model-var convention — optional `<UPPERCASE-FILENAME>_MODEL` (deepseek ->
                               `DEEPSEEK_MODEL`, omlx-local -> `OMLX_LOCAL_MODEL`)
                               pins the model id explicitly from .env.solidforge,
                               overriding the profile's `model` field; an explicit
                               `--model` flag still wins.
  --profile <name[,name2...]> or $HETERO_PROFILE — select provider(s); comma-list
                               = dual-/multi-different-family (each backend runs independently,
                               findings merged + tagged with `provider`).
  token delivery — NO temp settings file under pi: the wrapper loads
                 .env.solidforge/.env into os.environ (shell wins) and the
                 spawned `pi` child INHERITS the env; the bundled sf-providers
                 extension bridges the same convention var to the pi-ai route
                 (or registers the route when the catalog is silent, e.g.
                 qwen-bailian). Fail-fast check stays in _load_profile.
  namespace isolation — the `_ANTHROPIC_AUTH_TOKEN` suffix is the SOLE token
                 source; the provider's native `<FILENAME>_API_KEY` is NEVER read
                 (it may serve another tool/SDK in the same env, so reading it
                 would risk a credential meant for a different use). See the
                 namespace-isolation ADR.

Findings schema (P1-2 decision): REUSE `infra/schemas/violation-log.schema.json`.
Its finding shape carries `severity` / `rule` / `file` / `line` / `detail` /
`suggestion`, which map 1:1 to the reconciliation fields (severity / defect_kind /
location) the same-family reviewer emits — so P1-5 reconciliation compares
LIKE-SHAPED findings. A different-family "could not verify X" disclosure maps to
severity=warning with the detail naming the unchecked area (rule 3/4 — never silent).

loop_state driving (ADR #39, ADR #40 (g)): the wrapper drives loop_state around
the subprocess so the run-record is truthful from day one — `init` →
`bump-iteration` → `gate-fail <fingerprint>` on malformation → `record-outer`
→ `mark-converged` → `run-record` (full standalone cycle). `--embedded` skips
init/mark-converged/run-record (the orchestrator owns those when this wrapper runs
as the convergence-loop outer ring).

Substrate-error handling (ADR #41): a non-zero CC exit is NOT automatically a
malformation. CC puts recoverable substrate errors (budget cap, turn cap, provider
overwhelm) in STDOUT as a clean `{"is_error":true,"subtype":...,"errors":[...]}`
envelope (stderr stays empty). `run_claude` parses it; subtypes in
`DEGRADABLE_SUBTYPES` DEGRADE — the different-family leg contributes 0 findings + a coverage
note + a `hetero-degraded-<subtype>` fingerprint (so the thrashing breaker escalates
persistent degradation), and the verdict stays pass/rewrite from the OTHER providers
(different-family is additive — ADR #40). Non-degradable subtypes (invalid-args, auth) and
unparseable output still malform → rewrite (never mask a regression — rule 3). The
default `--budget-usd 4.0` leaves headroom under loop_state's global 5.0 cap.

USD caveat (ADR #42, amended 2026-08-21): for non-Anthropic backends
`--max-budget-usd` is a COARSE runaway breaker, NOT real cost — the
Anthropic-compatible API returns tokens only (no price), and CC v2.1.238 prices
UNRECOGNIZED models at premium fallback rates (measured: $0.24 for ONE tiny turn),
so the cap fires on CC's mismeasure long before real provider spend matters (real
accounting is the provider's own dashboard). Provider-independent bounds, in firing
order: `--max-turns` per subprocess (ADR #52 — the OLD citation of "CC's turn limit
(`error_max_turns`)" was a PHANTOM boundary: print mode has no default turn limit and
the wrapper never passed the flag) + the stream-byte cap (ADR #52) + the wall-clock
`--timeout` (ADR #43) + `step_cap_S` globally (the loop's own step accounting).

Timeout (ADR #43): the per-subprocess wall-clock cap is `--timeout` (default 600, or
$HETERO_TIMEOUT). A cold large-diff review on the pro tier can exceed 600s — raise the
timeout OR drop a tier (`--model haiku`), do NOT remap the profile alias (timeout ⊥ model
selection; cold-start is transient — DeepSeek auto-caches ~99% after the first call).

Observability + guards (ADR #52): the DEFAULT spawn is the pi JSONL stream read
INCREMENTALLY (Popen) — a heartbeat line to STDERR every 30s (provider /
elapsed_s / stream_bytes / events / assistant_events / model / idle_s / killed), so a
streaming review is distinguishable from a hang WITHOUT socket forensics, and
`model` names the model the backend actually resolved (result field
`provider_runs[].model`). Wrapper-side breakers CC does not offer mid-run:
`--max-turns` (unbounded agentic loop) and `--max-stream-bytes` (runaway
response stream — an endless stream is visible via partial deltas BEFORE any
message completes). NO idle-kill: a legitimately long single response (cold
large-diff, ADR #43) can be line-silent for minutes — the heartbeat reports
idle_s for the OPERATOR to judge; killing on idle would false-abort cold starts.
`--no-stream` restores the legacy single-envelope json spawn (fallback if a CC
upgrade breaks the stream surface).

Self-contained (workspace rule 7): duplicates the loop_state subprocess pattern
rather than importing a shared lib, so the script stays independently deployable.
Pure stdlib. Exits 0 on success; non-zero on argument/IO/parse errors or a
malformed subprocess return.
"""

import argparse
import collections
import glob
import json
import os
import re
import subprocess
import sys
import threading
import time

# loop_state.py lives alongside this script (peer). Mirror plan_queue.py's pattern.
LOOP_STATE_PY = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "loop_state.py"
)
PROFILES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "profiles")

# CC substrate errors that DEGRADE (recoverable — the different-family leg contributed nothing; the
# same-family primary stands, per ADR #40 additive). Unknown subtypes + auth/invalid-args
# errors are NOT here — they malform (surface the cause), never silently mask a regression
# (rule 3; the FLAG-SURFACE MANIFEST above is the precedent for treating CC drift as
# non-silent). ADR #41.
DEGRADABLE_CC_SUBTYPES = frozenset(
    {
        "error_max_budget_usd",
        "error_max_turns",
        "error_overwhelmed",
        "error_session_expired",
        "error_session_not_found",
    }
)

# The Morph-caveat signal (ADR #40): a heterogeneous backend exhausts CC's
# --json-schema structured-output retries (CC demands the exact schema shape; a
# non-Claude backend may not comply within the retry budget). This is NOT degradable
# (it is a backend-capability gap, not a transient cap) BUT it IS recoverable via the
# wrapper's own defensive parse — retry once WITHOUT --json-schema (the live-substrate
# path; the wrapper's _extract_json_object + _validate_findings_shape handle a fenced /
# preamble-prose JSON return). See run_claude's auto-fallback. Verified CC v2.1.207.
# PI PORT: retired — pi has no --json-schema; the defensive parse is the ONLY path.
# Ported from csr's hetero_doc_review.py (ADR #45 — rule 7 copy-pattern).
STRUCTURED_OUTPUT_RETRY_FP = "hetero-cc-error:error_max_structured_output_retries"

# --- Incremental-stream guards + observability (ADR #52) -----------------------
#
# The 2026-08-21 third-party incident (csr's deepseek leg, same-task minimax
# control passed; reproduced live on the csr wrapper 2026-08-21 — 36 turns /
# 17.6MB stream in 9 min on a 113-line doc): a provider-side runaway stream
# burned the FULL wall-clock cap with 0 bytes visible outside — CC's `-p`
# output is buffered until process exit AND subprocess.run buffers it again,
# so a 20-minute run was indistinguishable from a hang, and the model name
# actually resolved was unverifiable from outside. The DEFAULT spawn is
# therefore stream-json read INCREMENTALLY (Popen): a stderr heartbeat every
# HEARTBEAT_INTERVAL_S, the LIVE resolved model name (first assistant event's
# message.model), a byte-count runaway breaker, and an explicit --max-turns
# (print mode has NO default turn limit — `error_max_turns` fires only when
# the flag is passed; the docstring's old reliance on it was phantom).
# Ported from csr's hetero_doc_review.py (ADR #52 — rule 7 lockstep).
HEARTBEAT_INTERVAL_S = 30.0

# stream-json partial-delta events (--include-partial-messages) carry no findings
# signal — skip their JSON parse by line prefix (hot path: one event per token
# delta; json.loads per delta would dominate parse time on a large review).
_PARTIAL_EVENT_PREFIX = '{"type":"message_update"'


def _run_loop_state(argv, project_dir):
    """subprocess `loop_state.py <argv>` rooted at project_dir. Returns (rc, output)."""
    env = dict(os.environ, CLAUDE_PROJECT_DIR=project_dir)
    proc = subprocess.run(
        [sys.executable, LOOP_STATE_PY] + argv,
        capture_output=True,
        text=True,
        env=env,
    )
    return proc.returncode, (proc.stdout + proc.stderr).strip()


def _pi_executable():
    """Resolve the pi binary. $SF_PI_BIN overrides (tests); else 'pi' from PATH."""
    return os.environ.get("SF_PI_BIN", "pi")


def _sf_providers_dir():
    """The bundled sf-providers extension dir, resolved from this file's location:
    <pkg>/skills/parallel-development/infra/scripts/ -> <pkg>/extensions/sf-providers."""
    pkg_root = os.path.dirname(
        os.path.dirname(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        )
    )
    d = os.path.join(pkg_root, "extensions", "sf-providers")
    if not os.path.isdir(d):
        sys.exit(
            f"error: sf-providers extension not found at {d} — the wrapper spawns "
            "`pi -e <sf-providers>` for the provider registry. Package layout broken?"
        )
    return d


def _load_prior(prior_arg):
    """Load prior-findings context: JSON string, `@file` path, or '' → None."""
    if not prior_arg:
        return None
    raw = prior_arg
    if prior_arg.startswith("@"):
        try:
            with open(prior_arg[1:], "r", encoding="utf-8") as fh:
                raw = fh.read()
        except FileNotFoundError:
            print(
                f"warn: prior-findings file not found: {prior_arg[1:]}; ignoring",
                file=sys.stderr,
            )
            return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        # Not fatal — degrade to a string hint in the prompt context.
        return [{"severity": "warning", "rule": "prior-context", "detail": raw}]


# --- provider-template + token-injection (the profiles/<provider>.json pattern) --
#
# profiles/<provider>.json files are COMMITTED TEMPLATES with ROUTING ONLY (BASE_URL
# + model aliases) — NO secret, NO `${...}` token ceremony. The auth token is read
# at runtime from the env var DERIVED BY CONVENTION from the filename:
# `<UPPERCASE-FILENAME>_ANTHROPIC_AUTH_TOKEN` (deepseek -> DEEPSEEK_ANTHROPIC_AUTH_TOKEN,
# qwen3 -> QWEN3_ANTHROPIC_AUTH_TOKEN). The wrapper injects it as ANTHROPIC_AUTH_TOKEN
# into a THROWAWAY temp settings file passed to `claude -p` (CC does NOT expand
# ${VAR} itself — verified CC v2.1.201). A template may override the var name via an
# optional `_token_env` field; other `${VAR}` refs (non-token fields) still expand.
# Selection: --profile <name[,name2...]> (multi = dual-/multi-different-family) or HETERO_PROFILE.


def _project_root_for_env():
    return os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd()


def _load_dotenv_file(path):
    """Load KEY=VALUE pairs from one file into os.environ (setdefault — shell wins).
    Best-effort: missing file / malformed line silently skipped."""
    if not os.path.exists(path):
        return
    with open(path, "r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def _load_dotenv():
    """Load <project>/.env.solidforge THEN <project>/.env into os.environ (setdefault —
    the shell always wins; between the two files, the FIRST loaded wins for a shared
    key, so .env.solidforge is authoritative for Solid Forge vars). Either file may
    carry the provider tokens — .env.solidforge is the arm-provisioned default, .env is
    the user's app env. Best-effort: missing files are silently skipped."""
    root = _project_root_for_env()
    _load_dotenv_file(os.path.join(root, ".env.solidforge"))
    _load_dotenv_file(os.path.join(root, ".env"))


_ENV_VAR_RE = re.compile(r"\$\{([A-Z_][A-Z0-9_]*)\}")


def _expand_env_values(obj):
    """Expand ${VAR} in every string value at ANY depth of `obj` from os.environ.
    Unset vars are left as-is (the token-presence check in _load_profile
    catches a missing _token_env value before the spawn). Recurses into nested
    dicts/lists — the profile shape is {env: {ANTHROPIC_AUTH_TOKEN: "${...}"}}."""

    def expand(node):
        if isinstance(node, str):
            return _ENV_VAR_RE.sub(
                lambda m: os.environ.get(m.group(1), m.group(0)), node
            )
        if isinstance(node, dict):
            return {k: expand(v) for k, v in node.items()}
        if isinstance(node, list):
            return [expand(x) for x in node]
        return node

    return expand(obj)


# CC-era profile NAME -> pi catalog ROUTE file (user .env.solidforge files still
# carry CC names in HETERO_PROFILE; resolve to the route-named FILENAME=ROUTE
# files — dsh principle). Mirrors csr's map (rule 7 copy-pattern).
_PROFILE_ALIASES = {
    "bigmodel": "zai-coding-cn",
    "minimax": "minimax-cn",
    "qwen3": "qwen-bailian",
}


def _resolve_profile_path(name):
    name = _PROFILE_ALIASES.get(name, name)
    p = os.path.join(PROFILES_DIR, f"{name}.json")
    if not os.path.exists(p):
        sys.exit(
            f"error: unknown provider profile '{name}' (no {p}). "
            "Committed templates live in infra/scripts/profiles/; see model-routing.md."
        )
    return p


def _resolve_token_var(name, template):
    """The env var holding the provider's auth token.

    Override: the template's optional `_token_env` field. Default (convention):
    `<UPPERCASE-FILENAME>_ANTHROPIC_AUTH_TOKEN` — e.g. `deepseek` ->
    `DEEPSEEK_ANTHROPIC_AUTH_TOKEN`, `qwen3` -> `QWEN3_ANTHROPIC_AUTH_TOKEN`,
    `openai-compat` -> `OPENAI_COMPAT_ANTHROPIC_AUTH_TOKEN`. The convention lets a user
    drop in `profiles/<name>.json` with ROUTING ONLY (no `_token_env`, no `${...}`) and
    the wrapper resolves the token var from the filename — zero ceremony per provider.
    """
    if "_token_env" in template:
        # An EXPLICIT empty string disables the env credential entirely (the
        # route authenticates via models.json/auth.json — e.g. omlx-local's
        # literal apiKey). `if template.get(...)` treated "" as absent and fell
        # through to the convention var, defeating the documented empty=skip
        # semantics (caught live with the omlx-local profile).
        return template["_token_env"]
    sanitized = re.sub(r"[^A-Za-z0-9]", "_", name).upper()
    return f"{sanitized}_ANTHROPIC_AUTH_TOKEN"


def _resolve_model_override(name):
    """Optional per-provider model override env var: <UPPERCASE-FILENAME>_MODEL.

    Same filename-sanitization as the token convention — `deepseek` ->
    DEEPSEEK_MODEL, `minimax-cn` -> MINIMAX_CN_MODEL, `omlx-local` ->
    OMLX_LOCAL_MODEL. Lets .env.solidforge pin the model id EXPLICITLY (swap a
    tier, pin a local quant) without editing the committed profile — the
    profile's `model` stays the packaged default. Precedence: an explicit
    `--model` flag beats the env var (per-invocation beats ambient); unset/empty
    falls through to the profile. Returns "" when unset.
    """
    sanitized = re.sub(r"[^A-Za-z0-9]", "_", name).upper()
    return os.environ.get(f"{sanitized}_MODEL", "").strip()


def _load_profile(name):
    """Load profiles/<name>.json, fail-fast on the token var, and return the dict.

    PI PORT: no temp settings file is materialized — the spawned pi child gets the
    provider registry from the bundled sf-providers extension (via -e), and the
    token travels via the INHERITED environment (this wrapper already loaded
    .env.solidforge/.env into os.environ with shell-wins semantics before any of
    this runs). The fail-fast check stays HERE so a missing token dies with the
    clear error (same UX as the CC era). An EMPTY `_token_env` skips the check —
    that route authenticates via pi's own auth.json (e.g. zai-coding-cn).
    Returns the parsed template (caller composes _provider + model into --model)."""
    src_path = _resolve_profile_path(name)
    with open(src_path, encoding="utf-8") as fh:
        tmpl = json.load(fh)
    token_var = _resolve_token_var(name, tmpl)
    if token_var:
        token = os.environ.get(token_var, "")
        if not token:
            sys.exit(
                f"error: provider '{name}' needs the env var ${token_var}. The wrapper reads it "
                "from <cwd>/.env.solidforge then <cwd>/.env (shell wins) — "
                "if you cd'd into the skill dir, re-run from the PROJECT ROOT (where .env.solidforge "
                "lives). Override or empty the template's `_token_env` (empty = auth.json route)."
            )
    return tmpl


def adversarial_prompt(diff_ref, blueprint_ref, prior_findings=None, round_no=0):
    """Build the ADVERSARIAL prompt (ADR #40 (c)).

    "Find what the primary reviewer missed or got wrong" — NOT "validate". Without
    this the loop degenerates into rubber-stamping (proposal §4 main failure mode).
    """
    prior_block = ""
    if prior_findings:
        prior_block = (
            "\n\nThe same-family primary reviewer already found:\n"
            f"{json.dumps(prior_findings, ensure_ascii=False, indent=2)}\n"
            "Your job is NOT to confirm these. Find what they MISSED or got WRONG — "
            "a defect category or code/doc location they did not cover. Restating "
            "the same defect on the same location is NOT a new finding."
        )
    return (
        f"You are an ADVERSARIAL code reviewer on a different model family than the "
        f"primary reviewer — your value is catching what same-family review misses "
        f"(enforcement gaps, silent failure modes, diagnostic UX). "
        f"Review the diff at `{diff_ref}` against the authoritative blueprint "
        f"`{blueprint_ref}`. Hunt for: correctness bugs, security issues, "
        f"performance problems, maintainability defects, and loading-chain / "
        f"rule-5 reachability gaps the primary reviewer did not surface.{prior_block}\n\n"
        f"Return a violation-log-shaped JSON object: "
        f'{{"gate": "hetero-review", "passed": <bool>, "coverage": [<what you checked>], '
        f'"findings": [{{"severity": "blocker"|"warning", "rule": "<defect-kind>", '
        f'"file": "<path>", "line": <int>, "detail": "<concrete quote + why>", '
        f'"suggestion": "<fix direction>"}}]}}. '
        f"A blocker requires concrete evidence (a quote). A guess is a warning. An "
        f"unchecked area is disclosed as a warning with detail, NEVER silenced "
        f"(rule 3/4). Round {round_no}."
    )


def _pi_argv(profile, model_override, prompt, allowed_tools):
    """Build the pi spawn argv. See PI-SUBSTRATE MANIFEST above (csr twin port).

    `--model` is composed from the profile's `_provider` + `model` fields as
    "<route>/<model-id>"; a `model_override` containing "/" is used verbatim
    (scoped otherwise). The CC-era [1M]/[1m] context-window suffix is STRIPPED.
    Budget/turn caps are NOT argv flags under pi — wrapper-side from the live
    stream (ADR #41/#52 semantics preserved via the SAME error subtypes)."""
    provider_id = profile.get("_provider")
    if not provider_id or not isinstance(provider_id, str):
        sys.exit(
            "error: profile template lacks a `_provider` field (the pi provider id "
            'or catalog route). Add "_provider": "<route>" to the profile.'
        )

    def _strip_ctx_suffix(mid):
        return re.sub(r"\[(1m|1M)\]$", "", mid)

    if model_override:
        model_id = (
            model_override
            if "/" in model_override
            else f"{provider_id}/{model_override}"
        )
        route, _, mid = model_id.rpartition("/")
        model_id = (
            f"{route}/{_strip_ctx_suffix(mid)}" if route else _strip_ctx_suffix(mid)
        )
    else:
        profile_model = profile.get("model")
        if not profile_model or not isinstance(profile_model, str):
            sys.exit(
                "error: profile template lacks a `model` field (the pi model id). "
                'Add "model": "<id>" to the profile or pass --model.'
            )
        model_id = f"{provider_id}/{_strip_ctx_suffix(profile_model)}"
    argv = [
        _pi_executable(),
        "--mode",
        "json",
        "-p",
        "--no-session",
        "-e",
        _sf_providers_dir(),
        "--model",
        model_id,
    ]
    if allowed_tools:
        argv += ["--tools", allowed_tools]
    argv.append(prompt)
    return argv


def _emit_heartbeat(provider, tele):
    """One progress line to STDERR (stdout stays the single result JSON). The
    heartbeat is the wrapper's liveness contract (ADR #52): an outer orchestrator
    (or a human at a terminal) distinguishes a streaming review from a hang
    WITHOUT socket-level forensics; `model` names the model the backend actually
    resolved (closes the 2026-08-21 incident's "cannot confirm the model name
    from outside" gap); `idle_s` reports line-silence for the OPERATOR to judge
    (deliberately NOT a kill condition — a cold-start single response can be
    legitimately line-silent for minutes, ADR #43)."""
    print(
        json.dumps(
            {
                "type": "hetero-heartbeat",
                "provider": provider,
                "elapsed_s": round(tele["elapsed_s"], 1),
                "stream_bytes": tele["stream_bytes"],
                "events": tele["events"],
                "assistant_events": tele["assistant_events"],
                "model": tele["model"],
                "idle_s": round(tele["idle_s"], 1),
                "killed": tele["killed"],
            },
            ensure_ascii=False,
        ),
        file=sys.stderr,
        flush=True,
    )


def _run_streamed(
    argv, timeout_s, max_stream_bytes, provider, budget_cap=None, turns_cap=None
):
    """Stream-mode spawn (ADR #52): Popen + incremental stdout read, so the
    wrapper has LIVE telemetry (stderr heartbeat every HEARTBEAT_INTERVAL_S) and
    two wrapper-side breakers CC does not offer mid-run:

      - wall-clock `timeout_s` (unchanged semantics — kill + the existing
        `hetero-subprocess-timeout` fingerprint);
      - `max_stream_bytes` on accumulated stdout INCLUDING token-delta partial
        events (kill + `hetero-stream-bytes-cap`) — an endless single response
        is visible via partial deltas BEFORE any message completes, which
        message-level stream-json would miss entirely.

    Reader THREADS drain stdout + stderr concurrently (an undrained pipe can
    block the child). The first assistant event's message.model is captured as
    the RESOLVED model (externally verifiable post-hoc). Returns
    `(raw_stdout, returncode, tele, stderr_tail)`; `tele["killed"]` is
    None | "timeout" | "bytes-cap" — the caller classifies, this never raises
    on kill paths. CC's own stderr (previously discarded) is tailed so substrate
    diagnostics (e.g. `[claude-code:unrecognized_model]` telemetry) survive.
    Ported from csr's hetero_doc_review.py (ADR #52 — rule 7 lockstep).
    """
    tele = {
        "model": None,
        "assistant_events": 0,
        "events": 0,
        "stream_bytes": 0,
        "cost_usd": 0.0,
        "assistant_error": None,
        "elapsed_s": 0.0,
        "idle_s": 0.0,
        "killed": None,
    }
    out_chunks = []
    err_tail = collections.deque(maxlen=24)
    lock = threading.Lock()
    started = time.monotonic()
    state = {"last_line_at": started}

    # stdin=DEVNULL is LOAD-BEARING (found live, 2026-08-25): pi -p with an
    # inherited non-TTY stdin that never reaches EOF BLOCKS reading prompts
    # from it — the child hung mid-review after session start. DEVNULL gives
    # it an immediately-closed stdin; the prompt rides the positional argv.
    proc = subprocess.Popen(
        argv,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )

    def stdout_reader():
        for line in proc.stdout or ():
            with lock:
                tele["stream_bytes"] += len(line.encode("utf-8", "replace"))
                tele["events"] += 1
                state["last_line_at"] = time.monotonic()
                if line.startswith(_PARTIAL_EVENT_PREFIX):
                    out_chunks.append(line)
                    continue
                evt = _try_json(line)
                if isinstance(evt, dict) and evt.get("type") == "message_end":
                    msg = evt.get("message")
                    if isinstance(msg, dict) and msg.get("role") == "assistant":
                        tele["assistant_events"] += 1
                        if tele["model"] is None and isinstance(msg.get("model"), str):
                            tele["model"] = msg["model"]
                        if msg.get("stopReason") == "error" and isinstance(
                            msg.get("errorMessage"), str
                        ):
                            tele["assistant_error"] = msg["errorMessage"]
                        usage = msg.get("usage")
                        if isinstance(usage, dict):
                            cost = (usage.get("cost") or {}).get("total")
                            if isinstance(cost, (int, float)):
                                tele["cost_usd"] += cost
                out_chunks.append(line)

    def stderr_reader():
        for line in proc.stderr or ():
            err_tail.append(line.rstrip("\n"))

    t_out = threading.Thread(target=stdout_reader, daemon=True)
    t_err = threading.Thread(target=stderr_reader, daemon=True)
    t_out.start()
    t_err.start()

    next_beat = started + HEARTBEAT_INTERVAL_S
    while True:
        if proc.poll() is not None:
            break
        now = time.monotonic()
        tele["elapsed_s"] = now - started
        with lock:
            tele["idle_s"] = now - state["last_line_at"]
        if tele["elapsed_s"] >= timeout_s:
            tele["killed"] = "timeout"
            proc.kill()
            break
        if max_stream_bytes and tele["stream_bytes"] > max_stream_bytes:
            tele["killed"] = "bytes-cap"
            proc.kill()
            break
        # WRAPPER-SIDE caps pi does not offer as CLI flags (PI-SUBSTRATE MANIFEST):
        # same degrade subtypes as the CC-era flags (ADR #41/#52).
        if budget_cap is not None and tele["cost_usd"] > budget_cap:
            tele["killed"] = "budget-cap"
            proc.kill()
            break
        if turns_cap is not None and tele["assistant_events"] > turns_cap:
            tele["killed"] = "turns-cap"
            proc.kill()
            break
        if now >= next_beat:
            _emit_heartbeat(provider, tele)
            next_beat = now + HEARTBEAT_INTERVAL_S
        time.sleep(0.5)

    try:
        proc.wait(timeout=15)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait(timeout=15)
    t_out.join(timeout=15)
    t_err.join(timeout=15)
    tele["elapsed_s"] = time.monotonic() - started
    # Final heartbeat so the tail state (esp. the kill reason) lands on stderr.
    _emit_heartbeat(provider, tele)
    return (
        "".join(out_chunks),
        proc.returncode,
        tele,
        "\n".join(list(err_tail)[-8:]),
    )


def _run_claude_once(
    argv,
    timeout_s,
    dry_run,
    dry_findings,
    dry_malform=False,
    dry_budget=False,
    guards=None,
):
    """Spawn the pi subprocess ONCE (or dry-run). Returns the CC-era dict shape:
    {findings, ok, fingerprint, error_subtype, errors, model, assistant_events,
    stream_bytes, elapsed_s, cost_usd, pi_stderr_tail}.

    PI PORT error taxonomy (DEGRADE semantics preserved, ADR #41; csr twin):
      killed=timeout -> hetero-subprocess-timeout (ADR #43)
      killed=bytes-cap -> hetero-stream-bytes-cap (ADR #52)
      killed=budget-cap/turns-cap -> DEGRADE error_max_budget_usd/error_max_turns
        (the WRAPPER-SIDE caps produce the SAME subtypes the CC CLI flags did)
      rc!=0 -> hetero-subprocess-rc{N}; rc=0 + assistant errorMessage ->
        hetero-api-error WITH the cause surfaced (rule 3)
      rc=0 -> _parse_pi_stream (defensive extract + _validate_findings_shape —
        pi has no --json-schema; the CC-era structured retry is retired)
    """
    base = {"findings": None, "error_subtype": None, "errors": []}
    if dry_run:
        if dry_malform:
            return {**base, "ok": False, "fingerprint": "dry-run-malform"}
        if dry_budget:
            return {
                **base,
                "ok": False,
                "fingerprint": "",
                "error_subtype": "error_max_budget_usd",
                "errors": ["Reached maximum budget ($0.05)"],
            }
        return {**base, "findings": dry_findings, "ok": True, "fingerprint": ""}

    g = guards or {}
    raw, rc_num, tele, err_tail = _run_streamed(
        argv,
        timeout_s,
        g.get("max_stream_bytes"),
        g.get("provider", "unknown"),
        budget_cap=g.get("budget_usd"),
        turns_cap=g.get("max_turns"),
    )
    tele_fields = {
        "model": tele["model"],
        "assistant_events": tele["assistant_events"],
        "stream_bytes": tele["stream_bytes"],
        "elapsed_s": round(tele["elapsed_s"], 1),
        "cost_usd": round(tele["cost_usd"], 4),
    }
    if err_tail:
        tele_fields["pi_stderr_tail"] = err_tail
    if tele["killed"] == "timeout":
        return {
            **base,
            "ok": False,
            "fingerprint": "hetero-subprocess-timeout",
            **tele_fields,
        }
    if tele["killed"] == "bytes-cap":
        return {
            **base,
            "ok": False,
            "fingerprint": "hetero-stream-bytes-cap",
            **tele_fields,
        }
    if tele["killed"] == "budget-cap":
        return {
            **base,
            "ok": False,
            "fingerprint": "",
            "error_subtype": "error_max_budget_usd",
            "errors": [
                "wrapper budget cap exceeded "
                f"(usage.cost.total={tele['cost_usd']:.2f} USD)"
            ],
            **tele_fields,
        }
    if tele["killed"] == "turns-cap":
        return {
            **base,
            "ok": False,
            "fingerprint": "",
            "error_subtype": "error_max_turns",
            "errors": [
                "wrapper turns cap exceeded "
                f"({tele['assistant_events']} assistant messages)"
            ],
            **tele_fields,
        }
    if rc_num != 0:
        return {
            **base,
            "ok": False,
            "fingerprint": f"hetero-subprocess-rc{rc_num}",
            **tele_fields,
        }
    findings, ok, fp = _parse_pi_stream(raw)
    if not ok and tele["assistant_error"]:
        return {
            **base,
            "ok": False,
            "fingerprint": "hetero-api-error",
            "errors": [tele["assistant_error"][:500]],
            **tele_fields,
        }
    return {
        **base,
        "findings": findings,
        "ok": ok,
        "fingerprint": fp,
        **tele_fields,
    }


def run_claude(
    argv,
    timeout_s,
    dry_run,
    dry_findings,
    dry_malform=False,
    dry_budget=False,
    guards=None,
):
    """PI PORT: the CC-era structured-output auto-fallback is retired (pi has no
    --json-schema). Thin pass-through KEEPING the positional signature (the
    wiring gate calls it positionally; divergence log contract)."""
    return _run_claude_once(
        argv, timeout_s, dry_run, dry_findings, dry_malform, dry_budget, guards=guards
    )


def _parse_pi_stream(raw):
    """Parse the `pi --mode json` JSONL return: the LAST non-empty assistant
    message_end text is the findings candidate (defensive fence-aware extract +
    _validate_findings_shape pre-check). message_update deltas are skipped by
    prefix BEFORE the JSON parse (hot path). Returns (findings, ok, fingerprint).
    (csr twin returns a 4-tuple with hook_count; pd never had hook events.)"""
    last_text = None
    for line in raw.splitlines():
        line = line.strip()
        if not line or line.startswith(_PARTIAL_EVENT_PREFIX):
            continue
        evt = _try_json(line)
        if isinstance(evt, dict) and evt.get("type") == "message_end":
            msg = evt.get("message")
            if isinstance(msg, dict) and msg.get("role") == "assistant":
                txt = _extract_text(msg.get("content"))
                if txt and txt.strip():
                    last_text = txt
    if last_text is None:
        return None, False, "hetero-stream-no-result"
    obj = _extract_json_object(last_text)
    if not isinstance(obj, dict):
        return None, False, "hetero-no-structured-output"
    fp = _validate_findings_shape(obj)
    if fp:
        return None, False, fp
    return obj, True, ""


def _extract_text(content):
    """PI PORT: one assistant message may carry MULTIPLE text parts (prose
    preamble before tool calls + the final structured answer in a later part).
    Concatenate ALL text parts — taking only the first lost the JSON when the
    model prefaced its tool use (found live in the pd smoke, 2026-08-25)."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = [
            part.get("text", "")
            for part in content
            if isinstance(part, dict) and part.get("type") == "text"
        ]
        parts = [p for p in parts if p and p.strip()]
        return "\n\n".join(parts) if parts else None
    return None


def _try_json(txt):
    try:
        return json.loads(txt)
    except (json.JSONDecodeError, TypeError):
        return None


# Live-substrate caveat (verified in the Phase-1 dogfood): under a complex review
# prompt, the non-Claude backend often returns the JSON inside a markdown code fence
# with preamble prose, and CC's `structured_output` comes back null. The wrapper must
# extract the JSON defensively from `result` (fence-aware, then brace-balanced).
_JSON_FENCE_RE = re.compile(r"```(?:json)?\s*\n(.*?)\n```", re.DOTALL)


def _extract_json_object(text):
    """Extract the first JSON object from text. Prefer a ```json fence; else the
    first brace-balanced `{...}` substring. Returns the parsed dict or None."""
    if not text:
        return None
    m = _JSON_FENCE_RE.search(text)
    candidate = m.group(1) if m else text
    obj = _try_json(candidate)
    if isinstance(obj, dict):
        return obj
    start = candidate.find("{")
    while start != -1:
        depth = 0
        for i in range(start, len(candidate)):
            ch = candidate[i]
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    obj = _try_json(candidate[start : i + 1])
                    if isinstance(obj, dict):
                        return obj
                    break
        start = candidate.find("{", start + 1)
    return None


def _validate_findings_shape(obj):
    """Return a malformation fingerprint if the shape violates violation-log; else ''."""
    if not isinstance(obj, dict):
        return "hetero-not-object"
    if "findings" not in obj or not isinstance(obj["findings"], list):
        return "hetero-missing-findings"
    for f in obj["findings"]:
        if not isinstance(f, dict) or "severity" not in f:
            return "hetero-finding-malformed"
        if f["severity"] not in ("blocker", "warning"):
            return "hetero-bad-severity"
    return ""


def drive_lifecycle(
    project_dir,
    task_id,
    round_verdict,
    findings_count,
    notes,
    embedded,
    hook_count,
    gate_fail_fp="",
):
    """Drive loop_state around the different-family subprocess (ADR #39, ADR #40 (g)).

    Full standalone cycle: init -> bump-iteration -> [gate-fail if malformation] ->
    record-outer -> mark-converged -> run-record. The gate-fail runs AFTER init so the
    fresh state is not wiped (loop_state `init` unconditionally re-defaults state; a
    pre-init gate-fail would be lost — found by the Phase-1 different-family dogfood). --embedded
    skips init/mark-converged/run-record (orchestrator-owned). Returns the run-record
    path (or '' if embedded/no-emission).
    """
    if not embedded:
        rc, out = _run_loop_state(["init", "--task-id", task_id], project_dir)
        if rc != 0:
            print(f"warn: loop_state init failed (continuing): {out}", file=sys.stderr)
    # One inner round per different-family invocation (the subprocess IS the inner work for this leg).
    _run_loop_state(["bump-iteration"], project_dir)
    if gate_fail_fp:
        # Post-init so the fingerprint survives to the run-record (the dogfood blocker).
        _run_loop_state(["gate-fail", gate_fail_fp], project_dir)
    # record-outer: the different-family verdict. outer.iterations += 1 satisfies the ADR #16 DoD guard.
    rc, out = _run_loop_state(
        [
            "record-outer",
            "--verdict",
            round_verdict,
            "--findings",
            str(findings_count),
            "--notes",
            f"{notes} hooks={hook_count}",
        ],
        project_dir,
    )
    if rc != 0:
        print(f"warn: loop_state record-outer failed: {out}", file=sys.stderr)
    run_path = ""
    if not embedded:
        rc, out = _run_loop_state(["mark-converged"], project_dir)
        if rc != 0:
            print(f"warn: loop_state mark-converged refused: {out}", file=sys.stderr)
        else:
            rc2, _ = _run_loop_state(["run-record"], project_dir)
            if rc2 == 0:
                # loop_state run-record writes <state_dir>/runs/<task_id>-<stamp>.json
                # and prints the JSON content. Glob for the freshest file for this task.
                runs_dir = os.path.join(project_dir, ".claude", "parallel-dev", "runs")
                matches = sorted(glob.glob(os.path.join(runs_dir, f"{task_id}-*.json")))
                run_path = matches[-1] if matches else ""
    return run_path


def main():
    # Load <project>/.env.solidforge + .env BEFORE argparse captures the os.environ.get
    # defaults below (--profile/$HETERO_PROFILE, --timeout/$HETERO_TIMEOUT). Previously
    # this ran AFTER parse_args, so an env var set ONLY in .env (not the shell) was
    # invisible to args -> --profile silently fell back to the hardcoded "deepseek",
    # dropping every other configured provider. Shell still wins (setdefault).
    _load_dotenv()
    ap = argparse.ArgumentParser(
        description="different-family adversarial review wrapper (ADR #40)."
    )
    ap.add_argument("--diff", required=True, help="Path/ref to the diff under review.")
    ap.add_argument(
        "--blueprint",
        required=True,
        help="Authoritative blueprint ref (doc + section).",
    )
    ap.add_argument("--task-id", default="hetero-review", help="loop_state task id.")
    ap.add_argument(
        "--profile",
        default=os.environ.get("HETERO_PROFILE", "deepseek"),
        help="Provider NAME (or comma-list for dual-/multi-different-family), resolved against "
        "profiles/<name>.json templates. Default: $HETERO_PROFILE or 'deepseek'. "
        "The token is read at runtime from the convention var "
        "<UPPERCASE-FILENAME>_ANTHROPIC_AUTH_TOKEN (e.g. "
        "DEEPSEEK_ANTHROPIC_AUTH_TOKEN) — the SOLE source (the suffix namespaces "
        "it to this substrate, NOT the provider's native <FILENAME>_API_KEY). "
        "Override via the template's _token_env. The committed profile carries no secret.",
    )
    ap.add_argument(
        "--model",
        default="",
        help="pi model id override ('route/model' verbatim, or a bare id scoped "
        "to the profile's _provider). Default: the profile's model field composed "
        "as <_provider>/<model>.",
    )
    ap.add_argument(
        "--budget-usd",
        type=float,
        default=12.0,
        help="Coarse runaway breaker per subprocess — NOT real spend. CC prices "
        "UNRECOGNIZED models (any non-Anthropic backend) at premium fallback rates "
        "(measured $0.24 for ONE tiny turn at CC v2.1.238 — ADR #42 amendment), so "
        "the cap fires on CC's mismeasure; real accounting is the provider's own "
        "dashboard (the old 'headroom under loop_state's global 5.0 cap' rationale "
        "presumed real USD, which ADR #42 established is fictional for non-Anthropic "
        "legs). Default 12.0 leaves a mid-size multi-turn review headroom under that "
        "mismeasure. If a review still trips the cap it DEGRADES (ADR #41), not "
        "rewrites.",
    )
    ap.add_argument(
        "--allowed-tools",
        default="read,grep,find,bash",
        help="Tools the different-family subprocess may wield (read-only review "
        "surface; pi builtin tool names, comma-joined for --tools).",
    )
    ap.add_argument(
        "--timeout",
        type=int,
        default=int(os.environ.get("HETERO_TIMEOUT", "600")),
        help="Subprocess wall-clock cap (seconds). Default 600, or $HETERO_TIMEOUT — "
        "raise it (or drop a tier via --model) for a cold large-diff review on the "
        "pro tier; do NOT remap the profile alias to dodge a timeout (ADR #43).",
    )
    ap.add_argument(
        "--max-turns",
        type=int,
        default=int(os.environ.get("HETERO_MAX_TURNS", "60")),
        help="Hard cap on CC agentic turns per subprocess. Print mode has NO default "
        "turn limit — an unbounded tool loop runs until the wall-clock cap (ADR #52). "
        "Tripping it DEGRADES (error_max_turns is degradable, ADR #41). Default 60, "
        "or $HETERO_MAX_TURNS. Dense diffs can legitimately spend dozens of turns; a fast-cycling runaway loop still dies early.",
    )
    ap.add_argument(
        "--max-stream-bytes",
        type=int,
        default=int(os.environ.get("HETERO_MAX_STREAM_BYTES", str(64 * 1024 * 1024))),
        help="Runaway breaker on accumulated JSONL stdout (bytes, INCLUDING "
        "token-delta partial events — an endless response stream is visible BEFORE "
        "any message completes; ADR #52). Tripping it MALFORMS loudly (the "
        "2026-08-21 incident class). Default 64MiB, or $HETERO_MAX_STREAM_BYTES.",
    )
    ap.add_argument(
        "--round-index",
        type=int,
        default=1,
        help="This leg's round number (label only; the debate loop is orchestrator-driven "
        "per ADR #40 (c)(d) — the orchestrator alternates same-family primary ↔ this "
        "wrapper, and `max_adversarial_rounds` = the count of wrapper invocations, "
        "queryable as loop_state `outer.iterations`).",
    )
    ap.add_argument(
        "--prior-findings",
        default="",
        help="Accumulated debate context (the same-family primary's latest findings) as "
        "JSON, or `@file` to read from a path. Fed to the adversarial prompt so the "
        "different-family leg hunts what the primary MISSED, not what it already found.",
    )
    ap.add_argument(
        "--embedded",
        action="store_true",
        help="Skip init/mark-converged/run-record (orchestrator owns those).",
    )
    ap.add_argument(
        "--dry-run",
        action="store_true",
        help="Offline mode: emit a canned return, no claude call (for the P1-7 test).",
    )
    ap.add_argument(
        "--dry-run-malform",
        action="store_true",
        help="Offline malformation: forces the gate-fail path (no claude call). For the "
        "gate-fail-survives-init test (locks the Phase-1 dogfood blocker fix).",
    )
    ap.add_argument(
        "--dry-run-budget",
        action="store_true",
        help="Offline budget-exhaustion: forces the DEGRADE path (no claude call). Returns a "
        "canned error_max_budget_usd envelope so the wiring test exercises degrade end-to-end "
        "(ADR #41).",
    )
    ap.add_argument(
        "--project-dir",
        default=os.getcwd(),
        help="Project root for loop_state state (CLAUDE_PROJECT_DIR).",
    )
    args = ap.parse_args()
    # The offline knobs (--dry-run-malform / --dry-run-budget) imply --dry-run — without
    # this, --dry-run-budget alone would skip run_claude's canned branch and fall through to
    # subprocess.run(None). Same footgun pre-existed for --dry-run-malform; closed here.
    if args.dry_run_malform or args.dry_run_budget:
        args.dry_run = True
    project_dir = os.path.abspath(args.project_dir)

    provider_names = [p.strip() for p in args.profile.split(",") if p.strip()]
    if not provider_names:
        print("error: --profile requires at least one provider name", file=sys.stderr)
        return 2
    # Validate every provider NAME up front (fail-fast on a typo / unknown template,
    # regardless of dry-run — _resolve_profile_path sys.exits with a clear error).
    for name in provider_names:
        _resolve_profile_path(name)

    # Canned return for dry-run (offline test path).
    dry_findings = {
        "gate": "hetero-review",
        "passed": True,
        "coverage": ["dry-run"],
        "findings": [],
    }

    # ONE different-family review per provider per invocation (faithful to ADR #40 (c)(d): the
    # same-family primary ↔ different-family alternation is ORCHESTRATOR-driven — this wrapper is
    # the different-family leg only; the orchestrator alternates + caps via outer.iterations).
    # Multi-provider (dual-/multi-different-family) runs each backend independently + merges; a
    # finding is tagged with its `provider` when >1 backend runs, so reconciliation
    # (ADR #40 (b)) can attribute it.
    prior = _load_prior(args.prior_findings)
    prompt = adversarial_prompt(args.diff, args.blueprint, prior, args.round_index)
    per_provider = []  # per-provider result dicts (keys: name/findings/model_coverage/...)
    for name in provider_names:
        argv = None
        if not args.dry_run and not args.dry_run_malform and not args.dry_run_budget:
            profile = _load_profile(name)  # fail-fast on missing token env var
            # Model precedence: --model flag > <NAME>_MODEL env > profile default.
            argv = _pi_argv(
                profile,
                args.model or _resolve_model_override(name),
                prompt,
                args.allowed_tools,
            )
        # All caps ride the live stream (PI-SUBSTRATE MANIFEST): byte cap + the
        # wrapper-side budget/turns caps pi does not offer as CLI flags.
        guards = {
            "provider": name,
            "max_stream_bytes": args.max_stream_bytes,
            "budget_usd": args.budget_usd,
            "max_turns": args.max_turns,
        }
        rc = run_claude(
            None if argv is None else argv,
            args.timeout,
            args.dry_run,
            dry_findings,
            args.dry_run_malform,
            dry_budget=args.dry_run_budget,
            guards=guards,
        )
        findings_obj = rc["findings"]
        pf = (findings_obj or {}).get("findings", []) if rc["ok"] else []
        if len(provider_names) > 1:
            for f in pf:
                f.setdefault("provider", name)
        per_provider.append(
            {
                "name": name,
                "findings": pf,
                "model_coverage": (findings_obj or {}).get("coverage", [])
                if rc["ok"]
                else [],
                "ok": rc["ok"],
                "fingerprint": rc["fingerprint"],
                "cost_usd": rc.get("cost_usd", 0.0),
                "error_subtype": rc["error_subtype"],
                "errors": rc["errors"],
                "model": rc.get("model"),
                "assistant_events": rc.get("assistant_events", 0),
                "stream_bytes": rc.get("stream_bytes", 0),
                "elapsed_s": rc.get("elapsed_s"),
                "pi_stderr_tail": rc.get("pi_stderr_tail", ""),
            }
        )

    # Aggregate across providers (single = classic different-family; multi = dual-/multi-different-family).
    all_findings = [f for p in per_provider for f in p["findings"]]
    # Genuine malformation = ok=False AND no degradable subtype (unparseable, or a
    # non-degradable CC error like invalid-args/auth). These surface a fingerprint + rewrite.
    malform_fps = [
        p["fingerprint"] for p in per_provider if not p["ok"] and not p["error_subtype"]
    ]
    # Degrade = a DEGRADABLE substrate error (ok=False, error_subtype set, fingerprint "").
    # The different-family leg contributed nothing; the same-family primary stands (ADR #40 additive).
    degraded_providers = [
        {"provider": p["name"], "subtype": p["error_subtype"], "errors": p["errors"]}
        for p in per_provider
        if p["error_subtype"]
    ]
    degrade_fps = [f"hetero-degraded-{d['subtype']}" for d in degraded_providers]
    any_malform = bool(malform_fps)
    degraded = bool(degraded_providers)
    blockers = [f for f in all_findings if f.get("severity") == "blocker"]
    # PI PORT: no CC hook events; the counter stays for the loop_state notes format.
    hook_count = 0
    malformation = ",".join(malform_fps)

    prov_list = ",".join(p["name"] for p in per_provider)
    if any_malform:
        # Genuine malformation / non-degradable CC error. gate-fail recorded inside
        # drive_lifecycle (post-init) so the fingerprint survives to the run-record
        # (ADR #39 truthfulness; never silent).
        verdict = "rewrite"
        notes = f"round={args.round_index} providers={prov_list} malformation={malformation}"
    else:
        # passed iff NO non-degraded provider surfaced a blocker (rule 4: warnings are
        # advisory). Degraded providers contribute 0 findings and never force a rewrite.
        gate_passed = len(blockers) == 0
        verdict = "pass" if gate_passed else "rewrite"
        per_counts = ",".join(f"{p['name']}={len(p['findings'])}" for p in per_provider)
        notes = (
            f"round={args.round_index} providers={per_counts} "
            f"findings={len(all_findings)} blockers={len(blockers)}"
        )

    # Degrade honesty (ADR #41; rule 3): stamp the subtype into the persisted notes AND a
    # gate-fail fingerprint so (a) the run-record shows WHY a leg contributed nothing, and
    # (b) the thrashing breaker can escalate persistent degradation across rounds instead of
    # it masquerading as clean convergence.
    if degraded:
        subtypes = ",".join(sorted({d["subtype"] for d in degraded_providers}))
        notes += f" degraded={subtypes}"

    # Combined gate-fail fingerprint: genuine malformation + degrade (both substrate issues).
    gate_fail_fp = ",".join(fp for fp in (malform_fps + degrade_fps) if fp)

    # coverage: the degrade-honestly trail (degrade + malform notes) + the model's own coverage.
    coverage = []
    for d in degraded_providers:
        detail = "; ".join(d["errors"]) if d["errors"] else "no detail"
        coverage.append(f"provider {d['provider']} degraded: {d['subtype']} ({detail})")
    for p in per_provider:
        if not p["ok"] and not p["error_subtype"] and p["fingerprint"]:
            detail = f" ({p['errors'][0][:160]})" if p.get("errors") else ""
            coverage.append(
                f"provider {p['name']} malformation: {p['fingerprint']}{detail}"
            )
    for p in per_provider:
        for c in p["model_coverage"]:
            if c not in coverage:
                coverage.append(c)

    run_path = drive_lifecycle(
        project_dir,
        args.task_id,
        verdict,
        len(all_findings),
        notes,
        args.embedded,
        hook_count,
        gate_fail_fp=gate_fail_fp,
    )

    # Per-run substrate telemetry (ADR #52): the resolved model name, agentic turns,
    # stream bytes, elapsed, cost — the post-hoc questions ("which model actually
    # ran? was the stream alive?") answered IN the record. pi_stderr_tail
    # (substrate diagnostics from the pi child) is included when present.
    provider_runs = []
    for p in per_provider:
        run_entry = {
            "name": p["name"],
            "model": p["model"],
            "assistant_events": p["assistant_events"],
            "stream_bytes": p["stream_bytes"],
            "elapsed_s": p["elapsed_s"],
            "cost_usd": p["cost_usd"],
        }
        if p["pi_stderr_tail"]:
            run_entry["pi_stderr_tail"] = p["pi_stderr_tail"][-500:]
        provider_runs.append(run_entry)

    result = {
        "verdict": verdict,
        "degraded": degraded,
        "degraded_providers": degraded_providers,
        "findings_count": len(all_findings),
        "findings": all_findings,
        "coverage": coverage,
        "malformation": malformation,
        "providers": [p["name"] for p in per_provider],
        "run_record": run_path,
        "provider_runs": provider_runs,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
