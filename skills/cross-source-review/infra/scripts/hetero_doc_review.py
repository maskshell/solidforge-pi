#!/usr/bin/env python3
"""hetero_doc_review.py — doc-domain different-family (different-family) adversarial review.

Spawns a non-interactive Claude Code subprocess on a DIFFERENT model family (e.g.
DeepSeek) as an additive adversarial second opinion on a DOC-SHAPED artifact. The
same-family reviewer (the CSR-I2 `doc-reviewer` agent) stays PRIMARY; different-family is the
cross-family leg that hunts what same-family review misses. The orchestrator
(interactive CC) stays on its primary provider unchanged.

This is a DOC-DOMAIN copy-pattern of `parallel-development`'s
`infra/scripts/hetero_review.py` (workspace rule 7 — copy-patterns-not-code; NOT an
import). The substrate (provider-template + token-injection, the FLAG-SURFACE
MANIFEST, fence-aware JSON parse, CC substrate-error DEGRADE handling, multi-provider
merge) is copied near-verbatim from the proven pd source. The divergences are
doc-domain adaptations only — see `hetero_doc_review.divergence.md` for the full list
and the Phase-A function-signature contract (proposal §5 / F3).

Authority chain: `docs/proposal.md` §3 (different-family substrate), §5 (Phase-A interface-compat
constraint), §8 (bootstrap already used this raw-substrate pattern), §9 Q2 (doc-findings
kind enum) / Q3 (convergence-record, no loop_state dependency); `docs/iteration-plan.md`
§CSR-I3 (deliverable + Done-when + Phase-A compat constraint).

Proposal Q3 is load-bearing here: the doc domain does NOT drive pd's `loop_state`
state machine. This wrapper runs ONE different-family review and PRINTS a clean result dict
`{verdict, degraded, degraded_providers, findings_count, findings, coverage,
malformation, providers, provider_runs}` (provider_runs = per-run substrate telemetry —
resolved model / assistant events / stream bytes / elapsed, ADR #52). The CSR-I4 convergence driver
(built separately) calls this wrapper once per round and assembles the convergence-record
itself.

==============================================================================
PI-SUBSTRATE MANIFEST — the pi port of the CC wrapper. If a pi upgrade breaks
this wrapper, update this manifest + `_pi_argv`.

Divergences from the CC original (logged in hetero_doc_review.divergence.md):
  - spawn target: `claude -p --settings ...` -> `pi --mode json -p --no-session`
    + `-e <pkg>/extensions/sf-providers` (provider registry; token resolves from
    the SAME <NAME>_ANTHROPIC_AUTH_TOKEN convention var via inherited env — the
    wrapper loads .env.solidforge/.env before spawn, shell wins).
  - `--model <alias>` (CC tier alias via profile env) -> `--model <provider/model>`
    (pi native id, composed from the profile's _provider + model fields).
  - `--json-schema` has NO pi equivalent: shape enforcement is the wrapper's own
    `_validate_findings_shape` pre-check + the findings shape-contract gate. The
    CC structured-output-retry fallback (`fell_back_to_unstructured`) is retired.
  - `--max-budget-usd` / `--max-turns` have NO pi CLI equivalents: both caps are
    enforced WRAPPER-SIDE from the live JSONL stream (usage.cost.total accumulated
    on assistant message_end; assistant message_end count) and degrade via the
    SAME subtypes as CC (error_max_budget_usd / error_max_turns, ADR #41/#52).
  - `--permission-mode bypassPermissions`: pi -p print mode has no permission
    popups — no equivalent needed.
  - `--output-format stream-json --verbose --include-partial-messages` ->
    `--mode json` (JSONL events; message_update deltas are skipped by prefix,
    same hot-path optimization).
  - `--observe-hooks` / `--no-stream`: retired (no CC hook surface; pi has one
    output mode). Gate observability for pi lives in the sf-hooks extension.
Flags used:
  pi --mode json -p --no-session
    -e <sf-providers-dir>          provider registry (bundled with the package)
    --model <provider/model>       composed from profiles/<name>.json; precedence
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
  --profile <name[,name2...]> or $HETERO_DOC_PROFILE — select provider(s); comma-list
                               = dual-/multi-different-family (each backend runs independently,
                               findings merged + tagged with `provider`).
  token delivery — NO temp settings file under pi: the wrapper loads
                 .env.solidforge/.env into os.environ (shell wins) and the
                 spawned `pi` child INHERITS the env; the bundled sf-providers
                 extension reads the same convention var from process.env.
                 Fail-fast check stays in _load_profile.
  namespace isolation — the `_ANTHROPIC_AUTH_TOKEN` suffix is the SOLE token
                 source; the provider's native `<FILENAME>_API_KEY` is NEVER read
                 (it may serve another tool/SDK in the same env, so reading it
                 would risk a credential meant for a different use). See the
                 namespace-isolation ADR.

Findings schema (CSR-I1 / proposal Q2): `infra/schemas/doc-findings.schema.json`.
Its finding shape carries `defect_id` / `severity` / `kind` / `location` /
`evidence` / `suggestion`, where `kind` is the doc-domain enum
(`contradiction` / `authority-chain-break` / `scope-creep` / `structural-gap` /
`citation-error` / `coverage-gap`) and `severity` keeps bc's {blocker, warning,
coverage} — the `coverage` severity is the reviewer's honest disclosure "could not
verify X" (workspace rule 3), DISTINCT from the `coverage-gap` KIND (a defect in the
artifact). A different-family "could not verify X" disclosure maps to severity=coverage with the
evidence naming the unchecked area (rule 3/4 — never silent).

Substrate-error handling (ADR #41 — preserved EXACTLY from pd): a non-zero CC exit is
NOT automatically a malformation. CC puts recoverable substrate errors (budget cap,
turn cap, provider overwhelm) in STDOUT as a clean
`{"is_error":true,"subtype":...,"errors":[...]}` envelope (stderr stays empty).
`run_claude` parses it; subtypes in `DEGRADABLE_SUBTYPES` DEGRADE — the different-family leg
contributes 0 findings + a coverage note + a `hetero-degraded-<subtype>` note, and the
verdict stays pass/rewrite from the OTHER providers (different-family is additive — ADR #40).
Non-degradable subtypes (invalid-args, auth) and unparseable output still malform →
rewrite (never mask a regression — rule 3). The default `--budget-usd 4.0` leaves
headroom.

USD caveat (ADR #42, amended 2026-08-21): for non-Anthropic backends
`--max-budget-usd` is a COARSE runaway breaker, NOT real cost — the
Anthropic-compatible API returns tokens only (no price), and CC v2.1.238 prices
UNRECOGNIZED models at premium fallback rates (measured: $0.24 for ONE tiny turn),
so the cap fires on CC's mismeasure long before real provider spend matters (real
accounting is the provider's own dashboard). Provider-independent bounds, in firing
order: `--max-turns` per subprocess (ADR #52 — the OLD citation of "CC's turn limit
(`error_max_turns`)" was a PHANTOM boundary: print mode has no default turn limit and
the wrapper never passed the flag) + the stream-byte cap (ADR #52) + the wall-clock
`--timeout` (ADR #43) + `step_cap_S` globally (pd-side driver only).

Timeout (ADR #43): the per-subprocess wall-clock cap is `--timeout` (default 600, or
$HETERO_DOC_TIMEOUT). A cold large-doc review on the pro tier can exceed 600s — raise the
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
large-doc, ADR #43) can be line-silent for minutes — the heartbeat reports
idle_s for the OPERATOR to judge; killing on idle would false-abort cold starts.
`--no-stream` restores the legacy single-envelope json spawn (fallback if a CC
upgrade breaks the stream surface).

Live disclosure (PI-PORT additions over upstream, ADR #61 semantics): (1) every
grandchild `tool_execution_start` + every assistant turn ALSO emits a compact
`leg-progress` line to STDERR (event granularity — under pi the bash tool streams
child stderr live into the session, so "the reviewer is reading docs/x.md" is
visible mid-run, not just "alive 30s ago"); (2) `--progress-file <path>` tees
leg boundaries + heartbeats as JSONL into the csr run-progress sidecar
(`csr_progress.py status --watch` for an external observer). Both are additive:
stdout stays the single result JSON; without the flag the sidecar is inert.

Self-contained (workspace rule 7): pure stdlib, no imports from pd or any shared lib.
The script stays independently deployable. Exits 0 on a clean run (verdict pass OR
rewrite-due-to-blocker — the wrapper succeeded); exit 1 on a malformation (the wrapper
could NOT produce a usable result); exit 2 on argument/IO errors.
"""

import argparse
import collections
import json
import os
import re
import subprocess
import sys
import threading
import time

PROFILES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "profiles")

# CC substrate errors that DEGRADE (recoverable — the different-family leg contributed nothing; the
# same-family primary stands, per ADR #40 additive). Unknown subtypes + auth/invalid-args
# errors are NOT here — they malform (surface the cause), never silently mask a regression
# (rule 3; the FLAG-SURFACE MANIFEST above is the precedent for treating CC drift as
# non-silent). ADR #41. Preserved EXACTLY from pd's hetero_review.py.
DEGRADABLE_SUBTYPES = frozenset(
    {
        "error_max_budget_usd",
        "error_max_turns",
        "error_overwhelmed",
        "error_session_expired",
        "error_session_not_found",
    }
)

# The Morph-caveat signal (ADR #40): a heterogeneous backend exhausts CC's
# json-schema structured-output retries (CC demands the exact schema shape; a
# non-Claude backend may not comply within the retry budget). This is NOT degradable
# (it is a backend-capability gap, not a transient cap) BUT it IS recoverable via the
# wrapper's own defensive parse — retry once WITHOUT --json-schema (the live-substrate
# path; the wrapper's _extract_json_object + _validate_findings_shape handle a fenced /
# preamble-prose JSON return). See run_claude's auto-fallback. Verified CC v2.1.207.
# PI PORT: retired — pi has no --json-schema; the defensive parse is now the ONLY
# path (no structured mode to fall back from).
STRUCTURED_OUTPUT_RETRY_FP = "hetero-cc-error:error_max_structured_output_retries"

# --- Incremental-stream guards + observability (ADR #52) -----------------------
#
# The 2026-08-21 third-party incident (deepseek leg, same-task minimax control
# passed): a provider-side runaway stream burned the FULL wall-clock cap with 0
# bytes visible outside — CC's `-p` output is buffered until process exit AND
# subprocess.run buffers it again, so a 20-minute run was indistinguishable from
# a hang, and the model name actually resolved was unverifiable from outside.
# The DEFAULT spawn is therefore stream-json read INCREMENTALLY (Popen): a stderr
# heartbeat every HEARTBEAT_INTERVAL_S, the LIVE resolved model name (first
# assistant event's message.model), a byte-count runaway breaker, and an explicit
# --max-turns (print mode has NO default turn limit — `error_max_turns` fires
# only when the flag is passed; the docstring's old reliance on it was phantom).
HEARTBEAT_INTERVAL_S = 30.0

# stream-json partial-delta events carry no findings signal — skip their JSON
# parse by line prefix (hot path: one event per token delta; json.loads per delta
# would dominate parse time on a large review). PI PORT: pi's JSONL equivalent is
# the message_update delta event (same hot-path skip).
_PARTIAL_EVENT_PREFIX = '{"type":"message_update"'


# --- Run-progress sidecar (ADR #61, ported from upstream csr) + leg-progress ----
#
# When --progress-file is given, this wrapper's leg boundaries + heartbeats ALSO
# land as JSONL in that file — the external observability contract, extending the
# ADR #52 stderr heartbeat (which under pi streams LIVE into the invoking session:
# pi's bash tool merges child stderr into its throttled partial-result render) to
# any outside observer (`tail -f` / `csr_progress.py status --watch`). BEST-EFFORT
# by contract: an observability failure NEVER kills the review — OSError is caught,
# warned ONCE on stderr, and the run continues. The append helper is deliberately
# self-contained (rule 7 — the wrapper does NOT import csr_progress; each script
# stays independently deployable).
_PROGRESS_PATH = None
_PROGRESS_WARNED = False


def _progress_append(event_type, **fields):
    global _PROGRESS_WARNED
    if not _PROGRESS_PATH:
        return
    event = {
        "ts": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "type": event_type,
        **fields,
    }
    try:
        parent = os.path.dirname(os.path.abspath(_PROGRESS_PATH))
        os.makedirs(parent, exist_ok=True)
        with open(_PROGRESS_PATH, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(event, ensure_ascii=False) + "\n")
            fh.flush()
    except OSError as exc:
        if not _PROGRESS_WARNED:
            print(
                f"warning: progress file unwritable ({exc}); continuing without it",
                file=sys.stderr,
            )
            _PROGRESS_WARNED = True


# leg-progress events (PI-PORT ADDITION beyond upstream): EVENT-granularity live
# disclosure to STDERR — one line per grandchild tool_execution_start + one per
# assistant turn. Under pi's bash tool these stream live into the session's tool
# panel ("the reviewer is reading docs/x.md", not just "alive, 30s ago"), and a
# human tailing stderr sees the review's actual process. Deliberately NOT written
# to the progress sidecar — the sidecar keeps upstream's strict boundary+
# heartbeat vocabulary (csr_progress.py EVENT_REGISTRY parity); stderr is the
# in-session channel, the sidecar the external one.
def _emit_leg_progress(provider, phase, detail):
    print(
        json.dumps(
            {
                "type": "leg-progress",
                "provider": provider,
                "phase": phase,
                "detail": detail,
            },
            ensure_ascii=False,
        ),
        file=sys.stderr,
        flush=True,
    )


def _tool_preview(tool_name, args):
    """One-line compact preview of a grandchild tool call (for leg-progress)."""
    name = tool_name if isinstance(tool_name, str) else "tool"
    if not isinstance(args, dict):
        return name
    if name == "bash":
        s = str(args.get("command", "")).replace("\n", " ; ").strip()
    elif name in ("read", "write", "edit", "ls"):
        s = str(args.get("path") or args.get("file_path") or "")
    elif name == "grep":
        s = f"/{args.get('pattern', '')}/"
    else:
        s = json.dumps(args, ensure_ascii=False)
    s = s.strip()[:100]
    return f"{name} {s}" if s else name


def _pi_executable():
    """Resolve the pi binary. $SF_PI_BIN overrides (tests); else 'pi' from PATH."""
    return os.environ.get("SF_PI_BIN", "pi")


def _sf_providers_dir():
    """The bundled sf-providers extension dir, resolved from this file's location:
    <pkg>/skills/cross-source-review/infra/scripts/ -> <pkg>/extensions/sf-providers.
    The spawned pi child loads it via -e so the provider registry (deepseek/minimax/
    bigmodel) is available WITHOUT requiring the package to be installed."""
    # scripts -> infra -> cross-source-review -> skills -> <pkg root> (5 dirnames:
    # __file__ is the FILE, so the first dirname lands in scripts/)
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
            with open(prior_arg[1:], encoding="utf-8") as fh:
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
        # Not fatal — degrade to a doc-shaped hint in the prompt context.
        return [
            {
                "severity": "warning",
                "kind": "citation-error",
                "location": "prior-findings",
                "evidence": raw,
            }
        ]


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
# Selection: --profile <name[,name2...]> (multi = dual-/multi-different-family) or HETERO_DOC_PROFILE.


def _project_root_for_env():
    return os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd()


def _load_dotenv_file(path):
    """Load KEY=VALUE pairs from one file into os.environ (setdefault — shell wins).
    Best-effort: missing file / malformed line silently skipped."""
    if not os.path.exists(path):
        return
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def _load_dotenv():
    """Load the INVOKING project's env files into os.environ (setdefault — shell always
    wins; between files the first-loaded wins for a shared key). Reads
    <cwd>/.env.solidforge (the host workspace's arm-env IF present — the solidforge arm
    convention; absent + silently skipped in external projects) THEN <cwd>/.env (generic).
    Either may carry the provider token. Best-effort: missing files silently skipped.
    Portable — CWD-based, so csr reads the env of wherever it is invoked. See
    references/install.md."""
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
# carry CC names in HETERO_DOC_PROFILE, e.g. "bigmodel,qwen3"; resolve to the
# route-named FILENAME=ROUTE files — dsh principle).
_PROFILE_ALIASES = {
    "bigmodel": "zai-coding-cn",
    "minimax": "minimax-cn",
    "qwen3": "qwen-bailian",  # Bailian pay-as-you-go (the observed default);
    # token-plan subscription users edit HETERO_DOC_PROFILE to qwen-token-plan-cn
}


def _resolve_profile_path(name):
    name = _PROFILE_ALIASES.get(name, name)
    p = os.path.join(PROFILES_DIR, f"{name}.json")
    if not os.path.exists(p):
        sys.exit(
            f"error: unknown provider profile '{name}' (no {p}). "
            "Committed templates live in infra/scripts/profiles/."
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
    this runs; sf-providers reads the same convention var from process.env).
    The fail-fast check stays HERE so a missing token dies with the clear error
    (same UX as the CC era) instead of an opaque provider-auth failure in the child.
    Returns the parsed template (caller composes _provider + model into --model)."""
    src_path = _resolve_profile_path(name)
    with open(src_path, encoding="utf-8") as fh:
        tmpl = json.load(fh)
    token_var = _resolve_token_var(name, tmpl)
    if token_var:
        # CC-convention env credential: fail fast with the clear error. An EMPTY
        # `_token_env: ""` means the route authenticates via pi's own auth.json /
        # route env (e.g. zai-coding-cn, typically the default provider) — skip
        # the check; a bad credential then surfaces honestly as hetero-api-error.
        token = os.environ.get(token_var, "")
        if not token:
            sys.exit(
                f"error: provider '{name}' needs the env var ${token_var}. The wrapper reads it "
                "from <cwd>/.env.solidforge then <cwd>/.env (shell wins) — "
                "if you cd'd into the skill dir, re-run from the PROJECT ROOT (where .env.solidforge "
                "lives). Override or empty the template's `_token_env` (empty = auth.json route)."
            )
    return tmpl


def adversarial_prompt(artifact_ref, authority_ref, prior_findings=None, round_no=0):
    """Build the DOC-domain ADVERSARIAL prompt (proposal §3; Q2 kind enum).

    Replaces pd's CODE-shaped adversarial prompt with a DOC-shaped one. "Find what
    the primary reviewer missed or got wrong" — NOT "validate". Without this the loop
    degenerates into rubber-stamping. Hunts the Q2 6 doc defect kinds, is BARRED from
    outcome-axis (proposal §2), returns a doc-findings object. Keeps the prior-findings
    framing (fed via --prior-findings) so the different-family leg hunts the gap, not restatements.
    """
    prior_block = ""
    if prior_findings:
        prior_block = (
            "\n\nThe same-family primary reviewer already found:\n"
            f"{json.dumps(prior_findings, ensure_ascii=False, indent=2)}\n"
            "Your job is NOT to confirm these. Find what they MISSED or got WRONG — "
            "a defect kind or doc location they did not cover. Restating the same "
            "defect on the same location is NOT a new finding."
        )
    authority_clause = (
        f" against the authoritative reference `{authority_ref}`"
        if authority_ref
        else (
            " (the doc is self-contained — verify claims against the doc's own "
            "internal consistency)"
        )
    )
    return (
        f"You are an ADVERSARIAL doc reviewer on a different model family than the "
        f"primary reviewer — your value is catching what same-family review misses "
        f"(contradictions the author is blind to, citation drift, scope creep, "
        f"unstated load-bearing concepts). Review the doc at `{artifact_ref}`"
        f"{authority_clause}. Hunt for these defect kinds and NOTHING else:\n"
        f"- contradiction — two claims conflict, or a claim conflicts with a cited source\n"
        f"- authority-chain-break — a claim cites a source that does not say what the doc says\n"
        f"- scope-creep — the doc over-reaches its stated non-goals or conflates domains\n"
        f"- structural-gap — a load-bearing concept is undefined or a step is missing\n"
        f"- citation-error — a file/section/field citation is wrong or unverifiable\n"
        f"- coverage-gap — something that should be addressed for soundness is absent\n"
        f"\nYou are BARRED from OUTCOME-AXIS judgment: do NOT judge whether the doc is "
        f"'right', whether the requirement is correct, or whether the conclusion is "
        f"true — those are human-only. You converge PROCESS-AXIS quality only "
        f"(well-formed, consistent, citation-accurate, coverage-complete).{prior_block}\n\n"
        f"Return a doc-findings-shaped JSON object:\n"
        f'{{"outcome_axis_respected": true, "findings": [{{"defect_id": "<short id>", '
        f'"severity": "blocker"|"warning"|"coverage", "kind": "contradiction"|'
        f'"authority-chain-break"|"scope-creep"|"structural-gap"|"citation-error"|'
        f'"coverage-gap", "location": "<doc section/line/anchor>", "evidence": '
        f'"<concrete quote from the doc AND from the source you verified against>", '
        f'"suggestion": "<optional one-line fix direction>"}}]}}\n\n'
        f"A blocker requires concrete evidence (a quote from source). A guess is a "
        f"warning. An area you could not verify is a coverage-severity finding naming "
        f"it — NEVER silenced (rule 3/4). Note: the coverage SEVERITY (your honest "
        f"disclosure) is DISTINCT from the coverage-gap KIND (a defect in the artifact). "
        f"Round {round_no}."
    )


def _pi_argv(profile, model_override, prompt, allowed_tools):
    """Build the pi spawn argv. See PI-SUBSTRATE MANIFEST above.

    `--model` is composed from the profile's `_provider` + `model` fields as
    "<route>/<model-id>" (e.g. zai-coding-cn/glm-5.3 — a pi catalog route); a
    `model_override` containing "/" is used verbatim; one without "/" is scoped
    to the profile's `_provider`. The CC-era [1M]/[1m] context-window suffix is
    STRIPPED (under pi the window is the catalog model's contextWindow property,
    never part of the id). Budget/turn caps are NOT argv flags under pi — they
    are enforced wrapper-side from the live stream (_run_streamed; ADR #41/#52
    semantics preserved via the SAME error subtypes as the CC era)."""
    provider_id = profile.get("_provider")
    if not provider_id or not isinstance(provider_id, str):
        sys.exit(
            "error: profile template lacks a `_provider` field (the pi provider id "
            'registered by sf-providers). Add "_provider": "<name>" to the profile.'
        )

    def _strip_ctx_suffix(mid):
        # The CC-era [1M]/[1m] suffix is a CONTEXT-WINDOW parameter; under pi the
        # window is a catalog model property (contextWindow), never part of the id.
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
    # ADR #61 sidecar tee: the same heartbeat lands in the progress file too.
    _progress_append(
        "hetero-heartbeat",
        provider=provider,
        elapsed_s=round(tele["elapsed_s"], 1),
        stream_bytes=tele["stream_bytes"],
        events=tele["events"],
        assistant_events=tele["assistant_events"],
        model=tele["model"],
        idle_s=round(tele["idle_s"], 1),
        killed=tele["killed"],
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
        # PI PORT: pi JSONL events — assistant turns are message_end events whose
        # message.role == "assistant"; the resolved model rides the first one; the
        # cumulative cost rides each one's usage.cost.total (the WRAPPER-SIDE budget
        # cap's data source — pi has no --max-budget-usd). message_update deltas
        # are skipped by prefix BEFORE the JSON parse (hot path, same as CC).
        for line in proc.stdout or ():
            with lock:
                tele["stream_bytes"] += len(line.encode("utf-8", "replace"))
                tele["events"] += 1
                state["last_line_at"] = time.monotonic()
                if line.startswith(_PARTIAL_EVENT_PREFIX):
                    out_chunks.append(line)
                    continue
                evt = _try_json(line)
                if isinstance(evt, dict) and evt.get("type") == "tool_execution_start":
                    # leg-progress (PI-PORT ADDITION): the grandchild's tool call at
                    # START time — the "what is the reviewer DOING" signal, live.
                    _emit_leg_progress(
                        provider,
                        "tool",
                        _tool_preview(evt.get("toolName"), evt.get("args")),
                    )
                if isinstance(evt, dict) and evt.get("type") == "message_end":
                    msg = evt.get("message")
                    if isinstance(msg, dict) and msg.get("role") == "assistant":
                        tele["assistant_events"] += 1
                        if tele["model"] is None and isinstance(msg.get("model"), str):
                            tele["model"] = msg["model"]
                        # pi surfaces provider/API errors on the assistant
                        # message itself (stopReason="error" + errorMessage)
                        # while the PROCESS still exits 0 — capture the last one
                        # so _run_claude_once can classify it instead of a
                        # misleading hetero-stream-no-result.
                        if msg.get("stopReason") == "error" and isinstance(
                            msg.get("errorMessage"), str
                        ):
                            tele["assistant_error"] = msg["errorMessage"]
                        usage = msg.get("usage")
                        if isinstance(usage, dict):
                            cost = (usage.get("cost") or {}).get("total")
                            if isinstance(cost, (int, float)):
                                tele["cost_usd"] += cost
                        _emit_leg_progress(
                            provider,
                            "turn",
                            f"turn {tele['assistant_events']}"
                            + (
                                f" · ${tele['cost_usd']:.4f}"
                                if tele["cost_usd"]
                                else ""
                            ),
                        )
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
        # WRAPPER-SIDE caps pi does not offer as CLI flags (PI-SUBSTRATE MANIFEST).
        # Both kill MID-STREAM from live telemetry and DEGRADE via the SAME error
        # subtypes as the CC era (error_max_budget_usd / error_max_turns — ADR
        # #41/#52 semantics preserved).
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
    {findings, hook_count, ok, fingerprint, error_subtype, errors, model,
    assistant_events, stream_bytes, elapsed_s, cost_usd, pi_stderr_tail}.

    PI PORT error taxonomy (DEGRADE semantics preserved, ADR #41):
      - killed=timeout    -> fingerprint hetero-subprocess-timeout (malform; ADR #43)
      - killed=bytes-cap  -> fingerprint hetero-stream-bytes-cap (malform; ADR #52)
      - killed=budget-cap / turns-cap -> DEGRADE via error_subtype
        error_max_budget_usd / error_max_turns — the WRAPPER-SIDE caps produce the
        SAME subtypes the CC CLI flags did (PI-SUBSTRATE MANIFEST)
      - rc != 0 (natural exit) -> malform hetero-subprocess-rc{N} + pi stderr tail
        (pi has no CC-style stdout error envelope; fail loudly, never mask)
      - rc == 0 -> _parse_pi_stream (defensive fence-aware extract +
        _validate_findings_shape pre-check — pi has no --json-schema)
    """
    base = {"findings": None, "hook_count": 0, "error_subtype": None, "errors": []}
    if dry_run:
        if dry_malform:
            # Offline malformation path (CSR-I5 offline gate; dogfood blocker).
            return {**base, "ok": False, "fingerprint": "dry-run-malform"}
        if dry_budget:
            # Offline budget-exhaustion (degrade test; rule 4 — no real call). ok=False +
            # fingerprint="" + error_subtype set => main classifies DEGRADED.
            return {
                **base,
                "ok": False,
                "fingerprint": "",
                "error_subtype": "error_max_budget_usd",
                "errors": ["Reached maximum budget ($0.05)"],
            }
        # Offline path for the CSR-I5 wiring test (rule 4: no real model call in the gate).
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
    findings, hook_count, ok, fp = _parse_pi_stream(raw)
    if not ok and tele["assistant_error"]:
        # The stream carried a provider/API error (pi: stopReason=error on the
        # assistant message, rc=0). Surface the CAUSE (rule 3) — a bare
        # hetero-stream-no-result would mislead. Auth/model errors are NOT
        # degradable (CC-era invalid-args/auth semantics) — malform loudly.
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
        "hook_count": hook_count,
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
    """PI PORT: the CC-era one-shot structured-output auto-fallback is retired
    (pi has no --json-schema; the defensive parse is the ONLY path). This is now
    a thin pass-through that KEEPS the positional signature — the CSR-I5 wiring
    gate and divergence.md contract call it positionally."""
    return _run_claude_once(
        argv, timeout_s, dry_run, dry_findings, dry_malform, dry_budget, guards=guards
    )


def _parse_pi_stream(raw):
    """Parse the `pi --mode json` JSONL return: the LAST non-empty assistant
    message_end text is the findings candidate (defensive fence-aware extract +
    _validate_findings_shape pre-check — pi has no --json-schema enforcement,
    so EVERY return goes through the defensive path the CC era reserved for
    non-compliant backends). message_update deltas are skipped by line prefix
    BEFORE the JSON parse (hot path: one event per token delta).
    Returns (findings, hook_count, ok, fingerprint); hook_count is always 0
    (pi has no CC hook events — gate observability lives in sf-hooks)."""
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
        return None, 0, False, "hetero-stream-no-result"
    obj = _extract_json_object(last_text)
    if not isinstance(obj, dict):
        return None, 0, False, "hetero-no-structured-output"
    fp = _validate_findings_shape(obj)
    if fp:
        return None, 0, False, fp
    return obj, 0, True, ""


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


# Live-substrate caveat (verified in pd's Phase-1 dogfood; carries over): under a
# complex review prompt, the non-Claude backend often returns the JSON inside a
# markdown code fence with preamble prose, and CC's `structured_output` comes back
# null. The wrapper must extract the JSON defensively from `result` (fence-aware,
# then brace-balanced).
_JSON_FENCE_RE = re.compile(r"```(?:json)?\s*\n(.*?)\n```", re.DOTALL)


def _extract_json_object(text):
    """Extract the first JSON object from text. Prefer a ```json fence; else the
    first brace-balanced `{...}` substring. Returns the parsed dict or None.
    Preserved verbatim from pd's hetero_review.py."""
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
    """Return a malformation fingerprint if the shape violates doc-findings; else ''.

    Signature `(obj) -> str` preserved per the Phase-A compat constraint (proposal
    §5 / F3). The VALIDATION LOGIC diverges from pd's hetero_review.py: this accepts
    the doc-findings shape (top-level `outcome_axis_respected` bool + `findings` list;
    per-finding `severity` ∈ {blocker,warning,coverage} — coverage preserved per Q2;
    `kind` ∈ the 6 Q2 doc kinds). The full JSON-schema validation lives in the
    findings shape-contract gate (CSR-I5); this is a fast pre-check so run_claude can
    distinguish a usable return from model junk.
    """
    if not isinstance(obj, dict):
        return "hetero-not-object"
    if "findings" not in obj or not isinstance(obj["findings"], list):
        return "hetero-missing-findings"
    if not isinstance(obj.get("outcome_axis_respected"), bool):
        return "hetero-missing-outcome-axis"
    for f in obj["findings"]:
        if not isinstance(f, dict) or "severity" not in f:
            return "hetero-finding-malformed"
        if f["severity"] not in ("blocker", "warning", "coverage"):
            return "hetero-bad-severity"
        if f.get("kind") not in (
            "contradiction",
            "authority-chain-break",
            "scope-creep",
            "structural-gap",
            "citation-error",
            "coverage-gap",
        ):
            return "hetero-bad-kind"
    return ""


def _extract_coverage(findings_obj):
    """Doc-domain: the reviewer's 'could not verify X' disclosures arrive as
    coverage-severity findings (the doc-findings schema has no top-level coverage
    array — unlike pd's violation-log). Collect their evidence/location strings for
    the coverage trail. Returns a de-duplicated list."""
    if not isinstance(findings_obj, dict):
        return []
    findings = findings_obj.get("findings", [])
    if not isinstance(findings, list):
        return []
    cov = []
    for f in findings:
        if isinstance(f, dict) and f.get("severity") == "coverage":
            note = f.get("evidence") or f.get("location") or "undisclosed"
            if note not in cov:
                cov.append(note)
    return cov


def main():
    # Load <project>/.env.solidforge + .env BEFORE argparse captures the os.environ.get
    # defaults below (--profile/$HETERO_DOC_PROFILE, --timeout/$HETERO_DOC_TIMEOUT).
    # Previously this ran AFTER parse_args, so an env var set ONLY in .env (not the
    # shell) was invisible to args -> --profile silently fell back to the hardcoded
    # "deepseek", dropping every other configured provider (e.g. HETERO_DOC_PROFILE
    # =deepseek,minimax ran only deepseek). Shell still wins (setdefault).
    _load_dotenv()
    ap = argparse.ArgumentParser(
        description="different-family doc-domain adversarial review wrapper (CSR-I3)."
    )
    ap.add_argument(
        "--artifact",
        required=True,
        help="Path/ref to the DOC under review (a doc has no diff/blueprint).",
    )
    ap.add_argument(
        "--authority",
        default="",
        help="Optional authoritative reference (doc + section) to verify claims "
        "against. Empty (default) = the doc is self-contained; verify against its "
        "own internal consistency.",
    )
    ap.add_argument(
        "--profile",
        default=os.environ.get("HETERO_DOC_PROFILE", "deepseek"),
        help="Provider NAME (or comma-list for dual-/multi-different-family), resolved against "
        "profiles/<name>.json templates. Default: $HETERO_DOC_PROFILE or 'deepseek'. "
        "The token is read at runtime from the convention var "
        "<UPPERCASE-FILENAME>_ANTHROPIC_AUTH_TOKEN (e.g. "
        "DEEPSEEK_ANTHROPIC_AUTH_TOKEN) — the SOLE source (the suffix namespaces "
        "it to this substrate, NOT the provider's native <FILENAME>_API_KEY). "
        "Override via the template's _token_env. The committed profile carries no secret.",
    )
    ap.add_argument(
        "--model",
        default="",
        help="pi model id override ('provider/model' verbatim, or a bare id scoped "
        "to the profile's _provider). Default: the profile's model field composed "
        "as <_provider>/<model>.",
    )
    ap.add_argument(
        "--budget-usd",
        type=float,
        default=12.0,
        help="Coarse runaway breaker per subprocess — WRAPPER-SIDE under pi (pi "
        "has no --max-budget-usd; the cap watches usage.cost.total accumulated "
        "from the live JSONL stream). NOT real spend; real accounting is the "
        "provider's own dashboard. Tripping it DEGRADES (error_max_budget_usd — "
        "the same subtype the CC flag produced; ADR #41), not rewrites.",
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
        default=int(os.environ.get("HETERO_DOC_TIMEOUT", "600")),
        help="Subprocess wall-clock cap (seconds). Default 600, or $HETERO_DOC_TIMEOUT — "
        "raise it (or drop a tier via --model) for a cold large-doc review on the "
        "pro tier; do NOT remap the profile alias to dodge a timeout (ADR #43).",
    )
    ap.add_argument(
        "--max-turns",
        type=int,
        default=int(os.environ.get("HETERO_DOC_MAX_TURNS", "60")),
        help="Hard cap on assistant turns per subprocess — WRAPPER-SIDE under pi "
        "(pi has no --max-turns; the cap counts assistant message_end events from "
        "the live JSONL stream). Tripping it DEGRADES (error_max_turns — the same "
        "subtype the CC flag produced; ADR #41). Default 60, or $HETERO_DOC_MAX_TURNS.",
    )
    ap.add_argument(
        "--max-stream-bytes",
        type=int,
        default=int(
            os.environ.get("HETERO_DOC_MAX_STREAM_BYTES", str(64 * 1024 * 1024))
        ),
        help="Runaway breaker on accumulated JSONL stdout (bytes, INCLUDING "
        "token-delta partial events — an endless response stream is visible BEFORE "
        "any message completes; ADR #52). Tripping it MALFORMS loudly (the "
        "2026-08-21 incident class). Default 64MiB, or $HETERO_DOC_MAX_STREAM_BYTES.",
    )
    ap.add_argument(
        "--progress-file",
        default="",
        help="Run-progress sidecar (ADR #61): append this leg's boundary events "
        "(hetero-leg-start/-end) + streamed heartbeats as JSONL to this path, in "
        "addition to the stderr heartbeat + leg-progress events. Best-effort — an "
        "unwritable path warns once and never fails the review.",
    )
    ap.add_argument(
        "--round-index",
        type=int,
        default=1,
        help="This leg's round number (label only; the convergence loop is "
        "CSR-I4-driver-driven per proposal §3 — the driver alternates same-family ↔ this "
        "wrapper, and the cap = the count of wrapper invocations).",
    )
    ap.add_argument(
        "--prior-findings",
        default="",
        help="Accumulated debate context (the same-family primary's latest findings) as "
        "JSON, or `@file` to read from a path. Fed to the adversarial prompt so the "
        "different-family leg hunts what the primary MISSED, not what it already found.",
    )
    ap.add_argument(
        "--dry-run",
        action="store_true",
        help="Offline mode: emit a canned doc-findings return, no claude call "
        "(for the CSR-I5 wiring gate).",
    )
    ap.add_argument(
        "--dry-run-malform",
        action="store_true",
        help="Offline malformation: forces the malformation path (no claude call). "
        "For the CSR-I5 offline convergence-policy gate.",
    )
    ap.add_argument(
        "--dry-run-budget",
        action="store_true",
        help="Offline budget-exhaustion: forces the DEGRADE path (no claude call). "
        "Returns a canned error_max_budget_usd envelope so the wiring gate exercises "
        "degrade end-to-end (ADR #41).",
    )
    args = ap.parse_args()
    # Run-progress sidecar (ADR #61): module-global, NOT a run_claude kwarg, so the
    # preserved function-signature contract (divergence.md) stays untouched.
    global _PROGRESS_PATH
    _PROGRESS_PATH = args.progress_file or None
    # The offline knobs (--dry-run-malform / --dry-run-budget) imply --dry-run — without
    # this, --dry-run-budget alone would skip run_claude's canned branch and fall through to
    # subprocess.run(None). Same footgun pre-existed in pd for --dry-run-malform; carried over.
    if args.dry_run_malform or args.dry_run_budget:
        args.dry_run = True
    provider_names = [p.strip() for p in args.profile.split(",") if p.strip()]
    if not provider_names:
        print("error: --profile requires at least one provider name", file=sys.stderr)
        return 2
    # Validate every provider NAME up front (fail-fast on a typo / unknown template,
    # regardless of dry-run — _resolve_profile_path sys.exits with a clear error).
    for name in provider_names:
        _resolve_profile_path(name)

    # Canned doc-findings-shaped return for dry-run (offline test path).
    dry_findings = {
        "outcome_axis_respected": True,
        "findings": [],
    }

    # ONE different-family review per provider per invocation (faithful to proposal §3: the same-family
    # primary ↔ different-family alternation is CSR-I4-DRIVEN — this wrapper is the different-family leg only;
    # the driver alternates + caps). Multi-provider (dual-/multi-different-family) runs each backend
    # independently + merges; a finding is tagged with its `provider` when >1 backend
    # runs, so reconciliation (proposal §3 table) can attribute it.
    prior = _load_prior(args.prior_findings)
    prompt = adversarial_prompt(args.artifact, args.authority, prior, args.round_index)
    per_provider = []  # per-provider result dicts
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
        _progress_append("hetero-leg-start", round=args.round_index, provider=name)
        rc = run_claude(
            None if argv is None else argv,
            args.timeout,
            args.dry_run,
            dry_findings,
            args.dry_run_malform,
            dry_budget=args.dry_run_budget,
            guards=guards,
        )
        _progress_append(
            "hetero-leg-end",
            round=args.round_index,
            provider=name,
            outcome=(
                "ok"
                if rc["ok"]
                else ("degraded" if rc["error_subtype"] else "malformed")
            ),
            findings=len((rc["findings"] or {}).get("findings", [])) if rc["ok"] else 0,
            model=rc.get("model"),
            elapsed_s=rc.get("elapsed_s"),
            degraded=bool(rc["error_subtype"]),
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
                "model_coverage": _extract_coverage(findings_obj) if rc["ok"] else [],
                "ok": rc["ok"],
                "fingerprint": rc["fingerprint"],
                "hook_count": rc["hook_count"],
                "error_subtype": rc["error_subtype"],
                "errors": rc["errors"],
                "model": rc.get("model"),
                "assistant_events": rc.get("assistant_events", 0),
                "stream_bytes": rc.get("stream_bytes", 0),
                "elapsed_s": rc.get("elapsed_s"),
                "cost_usd": rc.get("cost_usd", 0.0),
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
    # The different-family leg contributed nothing; the same-family primary stands (proposal §3 reconcile table).
    degraded_providers = [
        {"provider": p["name"], "subtype": p["error_subtype"], "errors": p["errors"]}
        for p in per_provider
        if p["error_subtype"]
    ]
    any_malform = bool(malform_fps)
    degraded = bool(degraded_providers)
    blockers = [f for f in all_findings if f.get("severity") == "blocker"]
    malformation = ",".join(malform_fps)

    if any_malform:
        # Genuine malformation / non-degradable CC error. Never silent (rule 3).
        verdict = "rewrite"
    else:
        # passed iff NO non-degraded provider surfaced a blocker (rule 4: warnings/coverage
        # are advisory). Degraded providers contribute 0 findings and never force a rewrite.
        gate_passed = len(blockers) == 0
        verdict = "pass" if gate_passed else "rewrite"

    # coverage: the degrade-honestly trail (degrade + malform notes) + the reviewer's own
    # coverage-severity disclosures (doc-domain: those arrive as findings, extracted per
    # provider — the schema has no top-level coverage array).
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

    # Per-run substrate telemetry (ADR #52): the resolved model name, agentic turns,
    # stream bytes, elapsed, cost — the 2026-08-21 incident's post-hoc questions
    # ("which model actually ran? was the stream alive?") answered IN the record.
    # pi_stderr_tail (substrate diagnostics from the pi child) is included when
    # present.
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
        "provider_runs": provider_runs,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    # Exit code: 0 = the wrapper produced a usable result (pass OR rewrite-due-to-blocker
    # OR degrade — read the structured fields for which). 1 = malformation (the wrapper
    # could NOT parse a usable return). 2 = argument/IO error. pd always exits 0 because
    # its loop_state/driver interprets the verdict; the doc-wrapper is standalone (no
    # loop_state — proposal Q3), so it surfaces malformation via exit 1 for the CSR-I4
    # subprocess contract.
    return 1 if any_malform else 0


if __name__ == "__main__":
    sys.exit(main())
