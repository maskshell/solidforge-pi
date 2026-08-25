#!/usr/bin/env python3
"""hetero_doc_guards.py — different-family substrate guard gate (BLOCKER; rule 4).

PI PORT of the CC-era guard gate: offline checks for the ADR #41/#43/#52 bounded
+ observable substrate on hetero_doc_review.py (the pi spawn). NO real model call
(rule 4) — the "pi" child is faked by sys.executable -c scripts emitting pi
--mode json JSONL events:

  1. argv guards — _pi_argv carries the pi spawn surface: --mode json, -p,
     --no-session, -e <sf-providers>, --model <provider/model> composed from the
     profile, --tools passthrough, prompt as the positional tail.
  2. streamed telemetry — a faked JSONL stream yields the resolved model (first
     assistant message_end's message.model), the assistant-turn count
     (message_update deltas excluded), the byte count, and a stderr heartbeat.
  3. byte-cap breaker — a runaway faked stream trips hetero-stream-bytes-cap
     (malformation, NOT a degrade) well before the wall-clock cap.
  4. wall-clock kill — a hung faked child trips hetero-subprocess-timeout at the
     cap with telemetry attached.
  5. budget-cap DEGRADE — pi has no --max-budget-usd; the wrapper-side cap
     watches usage.cost.total on assistant message_end and degrades via
     error_max_budget_usd (the SAME subtype the CC flag produced).
  6. turns-cap DEGRADE — pi has no --max-turns; the wrapper-side cap counts
     assistant message_end events and degrades via error_max_turns.
  7. api-error classification — pi surfaces provider errors on the assistant
     message (stopReason=error + errorMessage) with rc=0; the wrapper must
     classify hetero-api-error with the cause surfaced, never a misleading
     hetero-stream-no-result.
  8. result telemetry — the dry-run result envelope carries provider_runs[]
     (the post-hoc "which model actually ran" record).

Usage:
    python3 infra/test/hetero_doc_guards.py
"""

import contextlib
import importlib.util
import io
import json
import os
import subprocess
import sys

GATE = "hetero-doc-guards"
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))  # skills/cross-source-review
HETERO = os.path.join(ROOT, "infra", "scripts", "hetero_doc_review.py")

# Faked pi children (argv[0] is sys.executable; the code rides `-c`). Events use
# the pi --mode json wire format.
_FAKE_STREAM_OK = r"""
import json, sys, time
# message_update deltas: skipped by prefix BEFORE the JSON parse (hot path)
print('{"type":"message_update","usage":{},"assistantMessageEvent":{"type":"text_delta","contentIndex":0,"delta":"tok"}}', flush=True)
print('{"type":"message_update","usage":{},"assistantMessageEvent":{"type":"text_delta","contentIndex":0,"delta":"tok"}}', flush=True)
time.sleep(1.2)  # span >1 heartbeat tick at the patched 0.3s interval
msg = {"type": "message_end", "message": {"role": "assistant", "model": "fake-model-x", "content": [{"type": "text", "text": "review"}], "usage": {"cost": {"total": 0.01}}}}
print(json.dumps(msg), flush=True)
print(json.dumps(msg), flush=True)
"""

_FAKE_STREAM_RUNAWAY = r"""
import time
blob = '{"type":"message_update","assistantMessageEvent":{"delta":"' + ("x" * 2000) + '"}}'
while True:
    print(blob, flush=True)
    time.sleep(0.05)
"""

_FAKE_HUNG = r"""
import time
time.sleep(60)
"""

_FAKE_BUDGET_RUNAWAY = r"""
import json, time
msg = {"type": "message_end", "message": {"role": "assistant", "model": "fake", "content": [], "usage": {"cost": {"total": 99.0}}}}
while True:
    print(json.dumps(msg), flush=True)
    time.sleep(0.05)
"""

_FAKE_TURNS_RUNAWAY = r"""
import json, time
msg = {"type": "message_end", "message": {"role": "assistant", "model": "fake", "content": [], "usage": {"cost": {"total": 0.0}}}}
while True:
    print(json.dumps(msg), flush=True)
    time.sleep(0.05)
"""

_FAKE_API_ERROR = r"""
import json
print(json.dumps({"type": "message_start", "message": {"role": "assistant", "content": []}}), flush=True)
err = {"type": "message_end", "message": {"role": "assistant", "model": "fake", "content": [], "stopReason": "error", "errorMessage": "401 Invalid API-key", "usage": {"cost": {"total": 0.0}}}}
print(json.dumps(err), flush=True)
"""


def _load_module():
    spec = importlib.util.spec_from_file_location("hetero_doc_review", HETERO)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _finding(detail, suggestion):
    return {
        "severity": "blocker",
        "rule": "substrate-guards",
        "file": "infra/scripts/hetero_doc_review.py",
        "line": 0,
        "detail": detail,
        "suggestion": suggestion,
    }


def _check(name, ok, detail, suggestion, findings, coverage):
    if ok:
        coverage.append(f"{name}: PASS")
    else:
        findings.append(_finding(f"{name}: {detail}", suggestion))
        coverage.append(f"{name}: FAIL")


def _flag_value(argv, flag):
    return argv[argv.index(flag) + 1] if flag in argv else None


def run():
    """Eight checks. Returns (findings, coverage)."""
    coverage = [
        "hetero-doc-guards (BLOCKER, rule 4 codifiable; PI PORT): the ADR "
        "#41/#43/#52 substrate guards — pi argv surface, streamed telemetry + "
        "heartbeat, byte/budget/turns/wall-clock breakers, api-error "
        "classification, provider_runs telemetry."
    ]
    findings = []
    mod = _load_module()

    # --- check 1: argv guards -------------------------------------------
    profile = {"_provider": "deepseek", "model": "deepseek-v4-flash[1m]"}
    argv = mod._pi_argv(profile, "", "prompt", "read,grep,find,bash")
    argv_nomodel = mod._pi_argv(profile, "minimax/M3", "prompt", None)
    ok1 = (
        argv[0] == "pi"
        and _flag_value(argv, "--mode") == "json"
        and "-p" in argv
        and "--no-session" in argv
        and "-e" in argv
        and _flag_value(argv, "--model") == "deepseek/deepseek-v4-flash[1m]"
        and _flag_value(argv, "--tools") == "read,grep,find,bash"
        and argv[-1] == "prompt"
        and _flag_value(argv_nomodel, "--model") == "minimax/M3"
        and "--tools" not in argv_nomodel
        and os.path.isdir(_flag_value(argv, "-e"))
    )
    _check(
        "argv-guards",
        ok1,
        f"argv={argv}",
        "restore the pi spawn surface in _pi_argv (PI-SUBSTRATE MANIFEST)",
        findings,
        coverage,
    )

    # --- check 2: streamed telemetry + heartbeat ------------------------
    mod.HEARTBEAT_INTERVAL_S = 0.3
    err_buf = io.StringIO()
    with contextlib.redirect_stderr(err_buf):
        raw, rc2, tele, _tail = mod._run_streamed(
            [sys.executable, "-c", _FAKE_STREAM_OK],
            30,
            10 * 1024 * 1024,
            "fake",
        )
    beats = [ln for ln in err_buf.getvalue().splitlines() if "hetero-heartbeat" in ln]
    ok2 = (
        rc2 == 0
        and tele["model"] == "fake-model-x"
        and tele["assistant_events"] == 2
        and tele["events"] == 4
        and tele["stream_bytes"] > 0
        and abs(tele["cost_usd"] - 0.02) < 1e-9
        and tele["killed"] is None
        and len(beats) >= 2
        and '"model": "fake-model-x"' in err_buf.getvalue()
    )
    _check(
        "streamed-telemetry",
        ok2,
        f"tele={tele} beats={len(beats)} rc={rc2}",
        "the stream reader must capture resolved model / assistant turns / bytes "
        "/ cost and emit stderr heartbeats (ADR #52; pi message_end events)",
        findings,
        coverage,
    )

    # --- check 3: byte-cap breaker ---------------------------------------
    rc3 = mod._run_claude_once(
        [sys.executable, "-c", _FAKE_STREAM_RUNAWAY],
        25,
        False,
        None,
        guards={"provider": "fake", "max_stream_bytes": 4000},
    )
    ok3 = (
        rc3["ok"] is False
        and rc3["fingerprint"] == "hetero-stream-bytes-cap"
        and rc3["error_subtype"] is None
        and rc3["stream_bytes"] > 4000
        and rc3["elapsed_s"] is not None
        and rc3["elapsed_s"] < 20
    )
    _check(
        "bytes-cap-breaker",
        ok3,
        f"rc3={rc3.get('fingerprint')} bytes={rc3.get('stream_bytes')}",
        "a runaway stream must die at --max-stream-bytes with the "
        "hetero-stream-bytes-cap malformation, NOT burn the wall-clock cap",
        findings,
        coverage,
    )

    # --- check 4: wall-clock kill ----------------------------------------
    rc4 = mod._run_claude_once(
        [sys.executable, "-c", _FAKE_HUNG],
        1,
        False,
        None,
        guards={"provider": "fake", "max_stream_bytes": 10 * 1024 * 1024},
    )
    ok4 = (
        rc4["ok"] is False
        and rc4["fingerprint"] == "hetero-subprocess-timeout"
        and rc4.get("elapsed_s") is not None
        and rc4["elapsed_s"] < 10
    )
    _check(
        "wall-clock-kill",
        ok4,
        f"rc4={rc4.get('fingerprint')} elapsed={rc4.get('elapsed_s')}",
        "a hung child must die at the wall-clock cap with telemetry attached",
        findings,
        coverage,
    )

    # --- check 5: budget-cap DEGRADE (wrapper-side; pi has no flag) ------
    rc5 = mod._run_claude_once(
        [sys.executable, "-c", _FAKE_BUDGET_RUNAWAY],
        25,
        False,
        None,
        guards={
            "provider": "fake",
            "max_stream_bytes": 10 * 1024 * 1024,
            "budget_usd": 12.0,
        },
    )
    ok5 = (
        rc5["ok"] is False
        and rc5["fingerprint"] == ""
        and rc5["error_subtype"] == "error_max_budget_usd"
        and rc5["errors"]
        and "budget cap" in rc5["errors"][0]
    )
    _check(
        "budget-cap-degrade",
        ok5,
        f"rc5={rc5.get('error_subtype')}/{rc5.get('fingerprint')}",
        "usage.cost.total over --budget-usd must DEGRADE via "
        "error_max_budget_usd (ADR #41 — same subtype as the CC flag)",
        findings,
        coverage,
    )

    # --- check 6: turns-cap DEGRADE (wrapper-side; pi has no flag) -------
    rc6 = mod._run_claude_once(
        [sys.executable, "-c", _FAKE_TURNS_RUNAWAY],
        25,
        False,
        None,
        guards={
            "provider": "fake",
            "max_stream_bytes": 10 * 1024 * 1024,
            "max_turns": 2,
        },
    )
    ok6 = (
        rc6["ok"] is False
        and rc6["fingerprint"] == ""
        and rc6["error_subtype"] == "error_max_turns"
        and rc6["assistant_events"] > 2
    )
    _check(
        "turns-cap-degrade",
        ok6,
        f"rc6={rc6.get('error_subtype')}/{rc6.get('fingerprint')}",
        "assistant message_end count over --max-turns must DEGRADE via "
        "error_max_turns (ADR #41/#52 — same subtype as the CC flag)",
        findings,
        coverage,
    )

    # --- check 7: api-error classification -------------------------------
    rc7 = mod._run_claude_once(
        [sys.executable, "-c", _FAKE_API_ERROR],
        25,
        False,
        None,
        guards={"provider": "fake", "max_stream_bytes": 10 * 1024 * 1024},
    )
    ok7 = (
        rc7["ok"] is False
        and rc7["fingerprint"] == "hetero-api-error"
        and rc7["errors"]
        and "401 Invalid API-key" in rc7["errors"][0]
        and rc7["error_subtype"] is None
    )
    _check(
        "api-error-classification",
        ok7,
        f"rc7={rc7.get('fingerprint')} errors={rc7.get('errors')}",
        "a stopReason=error assistant message (rc=0) must classify "
        "hetero-api-error WITH the cause surfaced (rule 3), never a misleading "
        "hetero-stream-no-result",
        findings,
        coverage,
    )

    # --- check 8: provider_runs telemetry --------------------------------
    p8 = subprocess.run(
        [
            sys.executable,
            HETERO,
            "--dry-run",
            "--artifact",
            "SKILL.md",
            "--profile",
            "deepseek",
        ],
        capture_output=True,
        text=True,
        cwd=ROOT,
    )
    runs = None
    try:
        runs = json.loads(p8.stdout).get("provider_runs")
    except json.JSONDecodeError:
        pass
    ok8 = (
        p8.returncode == 0
        and isinstance(runs, list)
        and len(runs) == 1
        and runs[0].get("name") == "deepseek"
        and {"name", "model", "assistant_events", "stream_bytes", "elapsed_s"}
        <= set(runs[0])
    )
    _check(
        "provider-runs-telemetry",
        ok8,
        f"runs={runs}",
        "the result envelope must carry provider_runs[] (ADR #52 post-hoc "
        "observability: resolved model / assistant turns / bytes / elapsed / cost)",
        findings,
        coverage,
    )

    return findings, coverage


def emit(findings, coverage):
    """Codifiable contract: blocker on violation -> exit non-zero (rule 4)."""
    passed = not any(f.get("severity") == "blocker" for f in findings)
    print(
        json.dumps(
            {
                "gate": GATE,
                "passed": passed,
                "coverage": coverage,
                "findings": findings,
            },
            indent=2,
            ensure_ascii=False,
        )
    )
    sys.exit(0 if passed else 1)


def main():
    findings, coverage = run()
    emit(findings, coverage)


if __name__ == "__main__":
    main()
