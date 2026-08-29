#!/usr/bin/env python3
"""csr_progress_gates.py — run-progress sidecar gate (BLOCKER; rule 4).

PI PORT of the upstream gate: offline checks for the ADR #61 run-progress
observability contract (sidecar + renderer + wrapper tee) PLUS the pi-port
live-disclosure additions (leg-progress stderr events; the ADR #62 narration
loop is NOT ported — pi has no background bash, and substrate streaming
replaces orchestrator polling). NO real model call (rule 4) — the wrapper half
runs via --dry-run / a faked pi JSONL child:

  1. registry-vocabulary-sync — csr_progress.EVENT_REGISTRY keys equal the
     SKILL.md event-vocabulary bullets EXACTLY (both directions; rule 5 drift
     is a Blocker, not advisory — the registry IS an enumeration).
  2. append-valid — `csr_progress.py append` lands one JSONL line with
     ts + type + coerced fields (cap=5 stays an int; a numeric-LOOKING string
     stays a string — spec-driven coercion).
  3. append-invalid — unknown type / missing required field / unknown field /
     non-enum run-end outcome each exit non-zero (loud misuse, rule 3).
  4. status-render — a full two-round fixture renders header / round-of-cap /
     phase+age / leg + reconcile totals / terminal state; a torn last line and
     a RUNNING (no run-end) file never crash.
  5. wrapper-flag-surface — wrapper --dry-run --progress-file appends
     hetero-leg-start + hetero-leg-end JSONL lines while stdout stays the
     single result JSON.
  6. wrapper-heartbeat-tee — a faked pi stream child's stderr heartbeats ALSO
     land in the progress file (module-global _PROGRESS_PATH seam).
  7. wrapper-best-effort — an unwritable progress path NEVER raises
     (observability failure cannot kill the review, ADR #61).
  8. enumeration-sync — divergence log records --progress-file + leg-progress;
     disconnect_check REQUIRED_FILES + SKILL.md/install.md enumerations carry
     the two new files (rule 5).
  9. live-disclosure-contract (pi replacement for upstream check 9) — SKILL.md
     step-2 different-family bullet passes --progress-file and documents the
     leg-progress stderr stream; the sidecar section names the three live
     layers; and the CC-era narration mechanics (run_in_background) are
     deliberately ABSENT under pi (anti-blind-sync guard).

Usage:
    python3 infra/test/csr_progress_gates.py
"""

import contextlib
import importlib.util
import io
import json
import os
import re
import subprocess
import sys
import tempfile

GATE = "csr-progress-gates"
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))  # skills/cross-source-review
SCRIPTS = os.path.join(ROOT, "infra", "scripts")
CSR_PROGRESS = os.path.join(SCRIPTS, "csr_progress.py")
HETERO = os.path.join(SCRIPTS, "hetero_doc_review.py")
SKILL = os.path.join(ROOT, "SKILL.md")

# Faked pi child (pi --mode json wire format; mirrors hetero_doc_guards'
# _FAKE_STREAM_OK shape): spans >1 heartbeat tick at the patched 0.3s interval,
# carries a resolvable model + one grandchild tool call.
_FAKE_STREAM_OK = r"""
import json, sys, time
print('{"type":"message_update","usage":{},"assistantMessageEvent":{"type":"text_delta","contentIndex":0,"delta":"tok"}}', flush=True)
print(json.dumps({"type": "tool_execution_start", "toolCallId": "t1", "toolName": "read", "args": {"path": "docs/x.md"}}), flush=True)
time.sleep(1.2)
msg = {"type": "message_end", "message": {"role": "assistant", "model": "fake-model-x", "content": [{"type": "text", "text": "review"}], "usage": {"cost": {"total": 0.01}}}}
print(json.dumps(msg), flush=True)
"""


def _load_module(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _finding(detail, suggestion, file_=None):
    return {
        "severity": "blocker",
        "rule": "progress-guards",
        "file": file_ or "infra/scripts/csr_progress.py",
        "line": 0,
        "detail": detail,
        "suggestion": suggestion,
    }


def _check(name, ok, detail, suggestion, findings, coverage, file_=None):
    if ok:
        coverage.append(f"{name}: PASS")
    else:
        findings.append(_finding(f"{name}: {detail}", suggestion, file_=file_))
        coverage.append(f"{name}: FAIL")


def _read(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def _append(prog, tmpdir, etype, fields):
    """Run csr_progress.py append; return CompletedProcess."""
    argv = [sys.executable, prog, "append", "--file", tmpdir, "--type", etype]
    for k, v in fields.items():
        argv += ["--field", f"{k}={v}"]
    return subprocess.run(argv, capture_output=True, text=True)


def _skill_vocabulary(skill_text):
    """The `- `type`` bullets under the Run-progress sidecar section of SKILL.md."""
    sec = re.search(
        r"###\s+Run-progress sidecar.*?(?=\n###\s|\n##\s)", skill_text, re.DOTALL
    )
    if not sec:
        return None
    return set(re.findall(r"^- `([a-z-]+)`", sec.group(0), re.MULTILINE))


def run():
    """Nine checks (incl. the RUNNING render variant). Returns (findings, coverage)."""
    coverage = [
        "csr-progress-gates (BLOCKER, rule 4 codifiable; PI PORT): the ADR #61 "
        "run-progress observability contract + the pi live-disclosure additions "
        "— registry sync, append shape, status render, wrapper tee + best-effort, "
        "leg-progress events, enumeration sync, step-2 wiring."
    ]
    findings = []
    mod = _load_module(CSR_PROGRESS, "csr_progress")
    skill_text = _read(SKILL)

    # --- check 1: registry <-> SKILL.md vocabulary sync ------------------
    reg_keys = set(mod.EVENT_REGISTRY.keys())
    skill_keys = _skill_vocabulary(skill_text)
    ok1 = skill_keys is not None and reg_keys == skill_keys
    _check(
        "registry-vocabulary-sync",
        ok1,
        f"registry={sorted(reg_keys)} skill={sorted(skill_keys or [])}",
        "the event vocabulary is single-sourced: keep EVENT_REGISTRY keys and the "
        "SKILL.md Run-progress sidecar bullets in lockstep (rule 5)",
        findings,
        coverage,
    )

    with tempfile.TemporaryDirectory() as td:
        prog_file = os.path.join(td, "runs", "demo", "progress.jsonl")

        # --- check 2: append-valid --------------------------------------
        p2 = _append(
            CSR_PROGRESS,
            prog_file,
            "run-start",
            {"artifact": "docs/x.md", "tier": "long", "cap": "5"},
        )
        line = None
        try:
            with open(prog_file, encoding="utf-8") as fh:
                line = json.loads(fh.readline())
        except (OSError, json.JSONDecodeError):
            pass
        ok2 = (
            p2.returncode == 0
            and line is not None
            and line.get("type") == "run-start"
            and isinstance(line.get("ts"), str)
            and line.get("cap") == 5
            and isinstance(line.get("cap"), int)
        )
        p2b = _append(
            CSR_PROGRESS,
            os.path.join(td, "numstr.jsonl"),
            "run-start",
            {"artifact": "123", "tier": "long", "cap": "5"},
        )
        line_b = None
        try:
            with open(os.path.join(td, "numstr.jsonl"), encoding="utf-8") as fh:
                line_b = json.loads(fh.readline())
        except (OSError, json.JSONDecodeError):
            pass
        ok2b = (
            p2b.returncode == 0
            and line_b is not None
            and line_b.get("artifact") == "123"
            and isinstance(line_b.get("artifact"), str)
        )
        _check(
            "append-valid",
            ok2 and ok2b,
            f"rc={p2.returncode} line={line} numstr={line_b}",
            "append must land one JSONL line with ts + type + coerced fields; "
            "spec-driven coercion keeps numeric-LOOKING strings as strings (AC-1)",
            findings,
            coverage,
        )

        # --- check 3: append-invalid (4 sub-cases) ----------------------
        p3a = _append(CSR_PROGRESS, prog_file, "no-such-event", {"round": "1"})
        p3b = _append(CSR_PROGRESS, prog_file, "reconcile", {"round": "1"})
        p3c = _append(
            CSR_PROGRESS, prog_file, "round-end", {"round": "1", "bogus": "x"}
        )
        p3d = _append(CSR_PROGRESS, prog_file, "run-end", {"outcome": "convergedd"})
        ok3 = (
            p3a.returncode != 0
            and p3b.returncode != 0
            and p3c.returncode != 0
            and p3d.returncode != 0
        )
        _check(
            "append-invalid",
            ok3,
            f"unknown={p3a.returncode} missing={p3b.returncode} "
            f"extra-field={p3c.returncode} bad-outcome={p3d.returncode}",
            "unknown type / missing required field / unknown field / non-enum "
            "run-end outcome must each exit non-zero — the registry is a strict "
            "vocabulary (rule 3)",
            findings,
            coverage,
        )

        # --- check 4: status-render (fixture + torn line + RUNNING) -----
        seq = [
            ("run-start", {"artifact": "docs/x.md", "tier": "long", "cap": "5"}),
            ("same-family-spawn", {"round": "1"}),
            ("same-family-complete", {"round": "1", "findings": "3"}),
            ("hetero-leg-start", {"round": "1", "provider": "deepseek"}),
            (
                "hetero-heartbeat",
                {"provider": "deepseek", "elapsed_s": "12.5"},
            ),
            (
                "hetero-leg-end",
                {
                    "round": "1",
                    "provider": "deepseek",
                    "outcome": "ok",
                    "findings": "2",
                },
            ),
            (
                "reconcile",
                {"round": "1", "fixed": "4", "rejected": "1", "escalated": "1"},
            ),
            ("round-end", {"round": "1", "new_blockers": "1"}),
            ("same-family-spawn", {"round": "2"}),
            ("same-family-complete", {"round": "2", "findings": "0"}),
            ("hetero-leg-start", {"round": "2", "provider": "deepseek"}),
            (
                "hetero-leg-end",
                {
                    "round": "2",
                    "provider": "deepseek",
                    "outcome": "ok",
                    "findings": "0",
                },
            ),
            (
                "reconcile",
                {"round": "2", "fixed": "0", "rejected": "0", "escalated": "0"},
            ),
            ("round-end", {"round": "2", "new_blockers": "0"}),
            ("run-end", {"outcome": "converged"}),
        ]
        for etype, fields in seq:
            _append(CSR_PROGRESS, prog_file, etype, fields)
        with open(prog_file, "a", encoding="utf-8") as fh:
            fh.write('{"type":"hetero-heartbe')  # torn tail (concurrent tail -f)
        p4 = subprocess.run(
            [sys.executable, CSR_PROGRESS, "status", prog_file],
            capture_output=True,
            text=True,
        )
        out = p4.stdout
        ok4 = (
            p4.returncode == 0
            and "docs/x.md" in out
            and "2 of 5" in out
            and "CONVERGED" in out
            and "unparsed: 1" in out
            and "same-family" in out
            and "reconcile" in out
        )
        _check(
            "status-render",
            ok4,
            f"rc={p4.returncode} out={out[:400]!r}",
            "status must render header / round-of-cap / terminal state from the "
            "fixture and count (not crash on) the torn last line (AC-2)",
            findings,
            coverage,
        )
        # RUNNING variant: strip the run-end + torn lines into a fresh file.
        running_file = os.path.join(td, "running.jsonl")
        with open(prog_file, encoding="utf-8") as fh:
            good_lines = [
                ln
                for ln in fh.read().splitlines()
                if ln.strip()
                and not ln.startswith('{"type":"hetero-heartbe')
                and json.loads(ln).get("type") != "run-end"
            ]
        with open(running_file, "w", encoding="utf-8") as fh:
            fh.write("\n".join(good_lines) + "\n")
        p4b = subprocess.run(
            [sys.executable, CSR_PROGRESS, "status", running_file],
            capture_output=True,
            text=True,
        )
        ok4b = p4b.returncode == 0 and "RUNNING" in p4b.stdout
        _check(
            "status-render-running",
            ok4b,
            f"rc={p4b.returncode} out={p4b.stdout[:200]!r}",
            "a file with no run-end renders RUNNING (AC-2)",
            findings,
            coverage,
        )

        # --- check 5: wrapper --progress-file flag surface ---------------
        wrap_prog = os.path.join(td, "wrap.jsonl")
        p5 = subprocess.run(
            [
                sys.executable,
                HETERO,
                "--dry-run",
                "--artifact",
                "SKILL.md",
                "--profile",
                "deepseek",
                "--progress-file",
                wrap_prog,
            ],
            capture_output=True,
            text=True,
            cwd=ROOT,
        )
        wrap_lines = []
        try:
            with open(wrap_prog, encoding="utf-8") as fh:
                wrap_lines = [json.loads(ln) for ln in fh if ln.strip()]
        except (OSError, json.JSONDecodeError):
            pass
        types = [e.get("type") for e in wrap_lines]
        stdout_json = None
        try:
            stdout_json = json.loads(p5.stdout)
        except json.JSONDecodeError:
            pass
        ok5 = (
            p5.returncode == 0
            and stdout_json is not None
            and "hetero-leg-start" in types
            and "hetero-leg-end" in types
            and any(
                e.get("type") == "hetero-leg-end" and e.get("outcome") == "ok"
                for e in wrap_lines
            )
        )
        _check(
            "wrapper-flag-surface",
            ok5,
            f"rc={p5.returncode} types={types}",
            "wrapper --progress-file must append hetero-leg-start/-end while "
            "stdout stays the single result JSON (AC-3)",
            findings,
            coverage,
            file_="infra/scripts/hetero_doc_review.py",
        )

        # --- check 6: wrapper heartbeat tee + leg-progress stderr --------
        hmod = _load_module(HETERO, "hetero_doc_review_tee")
        hmod.HEARTBEAT_INTERVAL_S = 0.3
        beat_file = os.path.join(td, "beats.jsonl")
        hmod._PROGRESS_PATH = beat_file
        err_buf = io.StringIO()
        with contextlib.redirect_stderr(err_buf):
            hmod._run_streamed(
                [sys.executable, "-c", _FAKE_STREAM_OK],
                30,
                10 * 1024 * 1024,
                "fake",
            )
        beats = []
        try:
            with open(beat_file, encoding="utf-8") as fh:
                beats = [
                    json.loads(ln)
                    for ln in fh
                    if ln.strip() and json.loads(ln).get("type") == "hetero-heartbeat"
                ]
        except (OSError, json.JSONDecodeError):
            pass
        leg_prog = [
            json.loads(ln)
            for ln in err_buf.getvalue().splitlines()
            if '"leg-progress"' in ln
        ]
        phases = [e.get("phase") for e in leg_prog]
        ok6 = (
            len(beats) >= 1
            and all(b.get("provider") == "fake" for b in beats)
            and all(isinstance(b.get("elapsed_s"), (int, float)) for b in beats)
            and all(isinstance(b.get("ts"), str) for b in beats)
            and "tool" in phases
            and "turn" in phases
            and any("read docs/x.md" in str(e.get("detail")) for e in leg_prog)
            # leg-progress is stderr-ONLY — the sidecar keeps the strict
            # boundary+heartbeat vocabulary (registry parity with upstream).
            and not any(
                json.loads(ln).get("type") == "leg-progress"
                for ln in open(beat_file)
                if ln.strip()
            )
        )
        _check(
            "wrapper-heartbeat-tee",
            ok6,
            f"beats={len(beats)} leg_progress_phases={phases}",
            "streamed heartbeats must ALSO land in the progress file, and "
            "grandchild tool calls + turns must emit leg-progress stderr lines "
            "(the pi live-disclosure addition; sidecar stays boundary-only)",
            findings,
            coverage,
            file_="infra/scripts/hetero_doc_review.py",
        )

        # --- check 7: best-effort (unwritable path never raises) ---------
        blocker_file = os.path.join(td, "afile.txt")
        with open(blocker_file, "w", encoding="utf-8") as fh:
            fh.write("i am a file, not a dir")
        hmod._PROGRESS_PATH = os.path.join(blocker_file, "sub", "p.jsonl")
        raised = False
        try:
            with contextlib.redirect_stderr(io.StringIO()):
                hmod._progress_append(
                    "hetero-leg-end", provider="deepseek", outcome="ok"
                )
                hmod._emit_heartbeat(
                    "deepseek",
                    {
                        "elapsed_s": 1.0,
                        "stream_bytes": 1,
                        "events": 1,
                        "assistant_events": 0,
                        "model": None,
                        "idle_s": 0.0,
                        "killed": None,
                    },
                )
        except Exception:
            raised = True
        _check(
            "wrapper-best-effort",
            not raised,
            "progress write to an unwritable path raised",
            "an observability failure must NEVER kill the review — catch OSError, "
            "warn once on stderr, continue (ADR #61; AC-3)",
            findings,
            coverage,
            file_="infra/scripts/hetero_doc_review.py",
        )

    # --- check 8: enumeration sync (rule 5) -------------------------------
    divergence = _read(os.path.join(SCRIPTS, "hetero_doc_review.divergence.md"))
    disconnect = _read(os.path.join(ROOT, "infra", "test", "disconnect_check.py"))
    install = _read(os.path.join(ROOT, "references", "install.md"))
    ok8 = (
        "--progress-file" in divergence
        and "leg-progress" in divergence
        and "infra/scripts/csr_progress.py" in disconnect
        and "infra/test/csr_progress_gates.py" in disconnect
        and "csr_progress_gates.py" in skill_text
        and "csr_progress.py" in install
        and "csr_progress.py" in skill_text
    )
    _check(
        "enumeration-sync",
        ok8,
        "divergence/--progress-file+leg-progress, disconnect REQUIRED_FILES x2, "
        "SKILL.md self-check + contract, install.md observability mention — some "
        "missing",
        "adding a capability ripples through EVERY enumeration (rule 5): "
        "divergence log, disconnect REQUIRED_FILES, SKILL.md self-check list, "
        "install.md observability section",
        findings,
        coverage,
    )

    # --- check 9: pi live-disclosure contract (replaces upstream #62) -----
    # Scoped to the step-2 DIFFERENT-FAMILY BULLET: the disclosure contract is
    # wired AT that decision point. Under pi there is NO background-task
    # narration loop — the bash tool streams stderr live + the sidecar feeds
    # the sf-progress footer strip. `run_in_background` must stay ABSENT (an
    # anti-blind-sync guard against future upstream merges).
    bullet = re.search(
        r"- Run the \*\*different-family leg\*\*(.*?)(?=\n   - |\n3\. )",
        skill_text,
        re.DOTALL,
    )
    bullet_text = bullet.group(0) if bullet else ""
    sec = re.search(r"###\s+Run-progress sidecar.*?(?=\n##\s)", skill_text, re.DOTALL)
    sec_text = sec.group(0) if sec else ""
    ok9 = (
        bool(bullet)
        and "hetero_doc_review" in bullet_text
        and "progressFile" in bullet_text
        and "FALLBACK" in bullet_text
        and "--progress-file" in bullet_text
        and "leg-progress" in bullet_text
        and "sf-progress" in sec_text
        and "csr_progress.py status" in bullet_text
        and "run_in_background" not in skill_text
    )
    _check(
        "live-disclosure-contract",
        ok9,
        "step-2 different-family bullet: hetero_doc_review tool primary + "
        "progressFile / bash FALLBACK with --progress-file / leg-progress stderr "
        "/ status --watch; sidecar section: sf-progress strip; CC-era "
        "run_in_background absent — some missing",
        "the pi zero-interaction disclosure contract lives in the step-2 "
        "different-family bullet + the sidecar section: the hetero_doc_review "
        "tool as the primary path (its own live stderr-derived panel, stdout "
        "verbatim as content), the bash invocation as the documented fallback "
        "(--progress-file wired, leg-progress stderr streamed live, "
        "parse-last-JSON), sidecar status watchable externally, sf-progress "
        "footer strip; the upstream ADR #62 narration loop (run_in_background "
        "polling) is deliberately NOT ported",
        findings,
        coverage,
        file_="SKILL.md",
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
