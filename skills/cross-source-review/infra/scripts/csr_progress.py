#!/usr/bin/env python3
"""csr_progress.py — run-progress sidecar writer + status renderer (ADR #61).

PI PORT (verbatim from the CC-era upstream ../solidforge — substrate-identical:
pure stdlib, no CC/pi surface involved; the only pi-side addition is the live
disclosure stack documented in SKILL.md's Run-progress sidecar section: pi's
bash tool streams the wrapper's stderr (heartbeats + leg-progress lines) live
into the invoking session, and the sf-progress extension renders this sidecar
as a footer status strip — external `status --watch` parity is preserved).

The run-progress observability contract: a csr run (same-family + different-family
multi-round review) appends ONE JSONL line per state boundary to a per-run progress
file (`workspace/cross-source-review/runs/<stamp>-<slug>/progress.jsonl` — gitignored,
workspace rule 11), so an EXTERNAL observer (a human at another terminal, or another
session) can watch live via `tail -f` or `csr_progress.py status --watch` — instead of
the pre-ADR-#61 opacity where the ADR #52 heartbeat lived only in the wrapper
subprocess's stderr, captured inside the invoking session's pending tool call.

Two halves:
  - ORCHESTRATOR boundary events (run-start / same-family legs / reconcile /
    round-end / run-end) — written by the csr orchestrator via `append` (this
    script; the SKILL.md Run-progress sidecar section is the contract).
  - WRAPPER events (hetero-leg-start / hetero-heartbeat / hetero-leg-end) — written
    by hetero_doc_review.py itself via `--progress-file` (its own tiny append helper;
    self-contained per rule 7 — the two scripts do NOT import each other).

EVERY progress write is BEST-EFFORT (ADR #61): an observability failure must never
kill or block a review. `append` exits non-zero on MISUSE (unknown type / missing
required field / unknown field — a strict vocabulary, rule 3) and the SKILL contract
tells the orchestrator to treat a failed append as non-fatal (note it in the
convergence-record coverage notes, never abort the run).

Self-contained (rule 7): pure stdlib, no skill imports, independently deployable.

Usage:
    csr_progress.py append --file <progress.jsonl> --type <event-type> \
        [--field key=value ...]
    csr_progress.py status <progress.jsonl | run-dir> [--watch <seconds>]
"""

import argparse
import json
import os
import re
import sys
import time
from datetime import datetime

# The event registry — the SINGLE SOURCE of the orchestrator vocabulary. Kept in
# lockstep with the SKILL.md "Run-progress sidecar" bullets (csr_progress_gates.py
# check 1 blocks drift in either direction, rule 5).
#
# Field specs: "str" | "int" | "num" (int/float) | "bool", optionally "|null"
# (the wrapper writes JSON nulls pre-resolution / offline — a dry-run leg-end
# carries model/elapsed_s = null). `required` must all be present with the right
# JSON type; `optional` may be present; ANY other key is rejected (strict
# vocabulary — a typo'd field name is loud, never silent).
EVENT_REGISTRY = {
    "run-start": {
        "required": {"artifact": "str", "tier": "str", "cap": "int"},
        "optional": {"authority": "str"},
    },
    "same-family-spawn": {
        "required": {"round": "int"},
        "optional": {},
    },
    "same-family-complete": {
        "required": {"round": "int", "findings": "int"},
        "optional": {},
    },
    "hetero-leg-start": {
        "required": {"round": "int", "provider": "str"},
        "optional": {},
    },
    # Written by the WRAPPER (bypasses this validation — its helper appends
    # directly); declared here so `status` + the SKILL vocabulary stay complete.
    # The "|null" specs tell the truth about the wrapper's JSON nulls (a
    # pre-resolution heartbeat carries model/killed = null).
    "hetero-heartbeat": {
        "required": {"provider": "str", "elapsed_s": "num"},
        "optional": {
            "idle_s": "num",
            "stream_bytes": "int",
            "events": "int",
            "assistant_events": "int",
            "model": "str|null",
            "killed": "str|null",
        },
    },
    "hetero-leg-end": {
        "required": {"round": "int", "provider": "str", "outcome": "str"},
        "optional": {
            "model": "str|null",
            "findings": "int",
            "degraded": "bool",
            "elapsed_s": "num|null",
        },
    },
    "reconcile": {
        "required": {
            "round": "int",
            "fixed": "int",
            "rejected": "int",
            "escalated": "int",
        },
        "optional": {},
    },
    "round-end": {
        "required": {"round": "int", "new_blockers": "int"},
        "optional": {},
    },
    "run-end": {
        "required": {"outcome": "str"},
        "optional": {"rounds": "int"},
    },
}

TERMINAL_OUTCOMES = ("converged", "adversarial-stalemate", "cap-hit", "aborted")

_INT_RE = re.compile(r"^-?\d+$")
_FLOAT_RE = re.compile(r"^-?\d+\.\d+$")


def _coerce_for_spec(raw, spec):
    """SPEC-DRIVEN coercion (the registry names the expected type per field — no
    value-sniffing, so a numeric-LOOKING string like artifact=123 stays a string).
    Returns (value, error) — error '' on success."""
    base = spec.split("|", 1)[0]
    if raw == "null" and spec.endswith("|null"):
        return None, ""
    if base == "str":
        return raw, ""
    if base == "bool":
        if raw in ("true", "false"):
            return raw == "true", ""
        return None, f"wants bool (true/false), got {raw!r}"
    if base == "int":
        if _INT_RE.match(raw):
            return int(raw), ""
        return None, f"wants int, got {raw!r}"
    if base == "num":
        if _INT_RE.match(raw):
            return int(raw), ""
        if _FLOAT_RE.match(raw):
            return float(raw), ""
        return None, f"wants num, got {raw!r}"
    return None, f"unknown spec {spec!r}"


def _validate(etype, raw_fields):
    """Return (fields, error): spec-driven coercion + strict vocabulary check.
    Unknown type / unknown field / bad value / (run-end) a non-enum outcome all
    return a non-empty error ('' + coerced fields on success)."""
    if etype not in EVENT_REGISTRY:
        known = ", ".join(sorted(EVENT_REGISTRY))
        return None, f"unknown event type '{etype}' (known: {known})"
    spec = EVENT_REGISTRY[etype]
    fields = {}
    for name, raw in raw_fields.items():
        tag = spec["required"].get(name) or spec["optional"].get(name)
        if tag is None:
            return None, f"unknown field '{name}' for '{etype}' (strict vocabulary)"
        value, err = _coerce_for_spec(raw, tag)
        if err:
            return None, f"field '{name}' of '{etype}' {err}"
        fields[name] = value
    for name in spec["required"]:
        if name not in fields:
            return None, f"missing required field '{name}' for '{etype}'"
    if etype == "run-end" and fields.get("outcome") not in TERMINAL_OUTCOMES:
        return None, (
            f"field 'outcome' of 'run-end' wants one of "
            f"{', '.join(TERMINAL_OUTCOMES)}, got {fields['outcome']!r}"
        )
    return fields, ""


def _now_ts():
    return datetime.now().isoformat(timespec="seconds")


def cmd_append(args):
    """Append ONE validated JSONL line. Exit 2 on misuse (argument-error class);
    exit 1 on an unwritable target — a clean one-line error, never a traceback
    (NFR-4: every progress-write path degrades honestly; the review itself is
    never killed — ADR #61)."""
    raw_fields = {}
    for pair in args.field or []:
        if "=" not in pair:
            print(f"error: --field wants key=value, got {pair!r}", file=sys.stderr)
            return 2
        k, v = pair.split("=", 1)
        raw_fields[k] = v
    fields, err = _validate(args.type, raw_fields)
    if err:
        print(f"error: {err}", file=sys.stderr)
        return 2
    event = {"ts": _now_ts(), "type": args.type, **(fields or {})}
    try:
        parent = os.path.dirname(os.path.abspath(args.file))
        os.makedirs(parent, exist_ok=True)
        with open(args.file, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(event, ensure_ascii=False) + "\n")
            fh.flush()
    except OSError as exc:
        print(f"error: cannot write progress file: {exc}", file=sys.stderr)
        return 1
    return 0


def _read_events(path):
    """Streaming single pass. Returns (events, unparsed) — malformed lines (a
    torn tail under concurrent `tail -f`) are COUNTED, never fatal (AC-2)."""
    events, unparsed = [], 0
    with open(path, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                unparsed += 1
                continue
            if isinstance(obj, dict) and isinstance(obj.get("type"), str):
                events.append(obj)
            else:
                unparsed += 1
    return events, unparsed


def _age_s(ts):
    try:
        dt = datetime.fromisoformat(ts)
        return max(0, int(time.time() - dt.timestamp()))
    except (TypeError, ValueError):
        return None


def _phase_label(evt):
    t = evt.get("type")
    if t == "hetero-heartbeat":
        model = evt.get("model") or "model unresolved"
        return f"hetero-heartbeat {evt.get('provider', '?')} ({model}, idle {evt.get('idle_s', '?')}s)"
    if t == "hetero-leg-start":
        return f"hetero-leg start {evt.get('provider', '?')}"
    if t == "hetero-leg-end":
        return f"hetero-leg end {evt.get('provider', '?')} ({evt.get('outcome', '?')})"
    if t == "same-family-complete":
        return f"same-family complete ({evt.get('findings', '?')} findings)"
    if t == "reconcile":
        return (
            f"reconcile (fixed {evt.get('fixed', '?')}, "
            f"rejected {evt.get('rejected', '?')}, "
            f"escalated {evt.get('escalated', '?')})"
        )
    if t == "run-end":
        return f"run-end ({evt.get('outcome', '?')})"
    return t or "?"


def render_status(path):
    """One-screen state from the progress file. Read-only (AC-2)."""
    if not os.path.exists(path):
        return f"csr progress: no file at {path} (no run started here yet)"
    events, unparsed = _read_events(path)

    run_start = next((e for e in events if e.get("type") == "run-start"), None)
    rounds = [e.get("round") for e in events if isinstance(e.get("round"), int)]
    cur_round = max(rounds) if rounds else None
    last = events[-1] if events else None

    sf_legs = [e for e in events if e.get("type") == "same-family-complete"]
    sf_findings = sum(e.get("findings", 0) for e in sf_legs)
    het = [e for e in events if e.get("type") == "hetero-leg-end"]
    het_ok = sum(1 for e in het if e.get("outcome") == "ok")
    het_deg = sum(1 for e in het if e.get("outcome") == "degraded")
    het_mal = sum(1 for e in het if e.get("outcome") not in ("ok", "degraded"))
    fixed = sum(e.get("fixed", 0) for e in events if e.get("type") == "reconcile")
    rejected = sum(e.get("rejected", 0) for e in events if e.get("type") == "reconcile")
    escalated = sum(
        e.get("escalated", 0) for e in events if e.get("type") == "reconcile"
    )
    blockers = [
        f"r{e.get('round')}={e.get('new_blockers')}"
        for e in events
        if e.get("type") == "round-end"
    ]
    run_end = next((e for e in reversed(events) if e.get("type") == "run-end"), None)

    lines = []
    if run_start:
        lines.append(
            f"csr run: {run_start.get('artifact', '?')} "
            f"(tier {run_start.get('tier', '?')}, cap {run_start.get('cap', '?')})"
        )
    else:
        lines.append("csr run: (no run-start event yet)")
    lines.append(
        f"round: {cur_round if cur_round is not None else '-'}"
        f" of {run_start.get('cap', '?') if run_start else '?'}"
    )
    if last:
        age = _age_s(last.get("ts"))
        age_txt = f"{age}s ago" if age is not None else "age unknown"
        lines.append(f"phase: {_phase_label(last)} — {age_txt}")
    else:
        lines.append("phase: (no events)")
    lines.append(f"same-family: {len(sf_legs)} legs, {sf_findings} findings")
    lines.append(
        f"hetero: {len(het)} legs (ok {het_ok}, degraded {het_deg}, "
        f"malformed {het_mal})"
    )
    lines.append(
        f"reconcile: fixed {fixed}, rejected {rejected}, escalated {escalated}"
    )
    lines.append(f"new-blockers: {' '.join(blockers) if blockers else '-'}")
    if run_end:
        outcome = str(run_end.get("outcome", "?")).upper()
        lines.append(f"state: {outcome}")
    else:
        lines.append("state: RUNNING")
    lines.append(f"unparsed: {unparsed}")
    return "\n".join(lines)


def _resolve_status_path(target):
    if os.path.isdir(target):
        return os.path.join(target, "progress.jsonl")
    return target


def cmd_status(args):
    if args.watch < 0:
        print(
            "error: --watch wants seconds > 0 (or omit it for a single render)",
            file=sys.stderr,
        )
        return 2
    path = _resolve_status_path(args.target)
    if args.watch:
        while True:
            print(render_status(path), flush=True)
            print("---", flush=True)
            time.sleep(args.watch)
    print(render_status(path))
    return 0


def main():
    ap = argparse.ArgumentParser(
        description="csr run-progress sidecar writer + status renderer (ADR #61)"
    )
    sub = ap.add_subparsers(dest="cmd", required=True)

    ap_append = sub.add_parser(
        "append", help="append ONE validated progress event (orchestrator half)"
    )
    ap_append.add_argument("--file", required=True, help="progress.jsonl path")
    ap_append.add_argument("--type", required=True, help="event type (registry key)")
    ap_append.add_argument(
        "--field",
        action="append",
        default=[],
        help="key=value payload field (repeatable; bool/int/float coerced)",
    )
    ap_append.set_defaults(func=cmd_append)

    ap_status = sub.add_parser(
        "status", help="render one-screen run state (read-only observer half)"
    )
    ap_status.add_argument(
        "target", help="progress.jsonl path OR a run dir containing one"
    )
    ap_status.add_argument(
        "--watch",
        type=float,
        default=0,
        help="re-render every N seconds until interrupted",
    )
    ap_status.set_defaults(func=cmd_status)

    args = ap.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
