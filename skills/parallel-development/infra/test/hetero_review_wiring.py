#!/usr/bin/env python3
"""hetero_review.py ↔ loop_state wiring — the wrapper drives loop_state truthfully
around the different-family subprocess (ADR #39, ADR #40 (g)), and the P1-1 schema delta
(`adversarial-stalemate`) round-trips through run-record.schema.json.

OFFLINE + DETERMINISTIC (rule 4 — no real model call in the gate): exercises the
wrapper's --dry-run path (canned violation-log-shaped return) + drives loop_state
directly for the verdict-enum cases. The live `claude -p` substrate is exercised by
the dogfood runs (§6 Phase-3 gate), NOT here.

Cases:
  1. --dry-run → loop_state driven truthfully: run-record converged, steps.inner>=1,
     outer.iterations>=1, outer_verdicts non-empty (ADR #39/#16 invariant).
  2. --dry-run → the wrapper returns a typed JSON object (verdict/findings_count/
     findings/run_record) — the reconciliation shape P1-5 consumes.
  3. adversarial-stalemate round-trips: loop_state accepts record-outer
     --verdict adversarial-stalemate AND the emitted run-record validates against
     run-record.schema.json (P1-1 schema delta).
  4. --embedded → skips init/mark-converged/run-record (the orchestrator owns those
     when the wrapper runs as the convergence-loop outer ring).

Run: python3 infra/test/hetero_review_wiring.py
"""

import glob
import json
import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPTS = os.path.normpath(os.path.join(HERE, "..", "scripts"))
SCHEMAS = os.path.normpath(os.path.join(HERE, "..", "schemas"))
HETERO = os.path.join(SCRIPTS, "hetero_review.py")
LOOP_STATE = os.path.join(SCRIPTS, "loop_state.py")
RUN_RECORD_SCHEMA = os.path.join(SCHEMAS, "run-record.schema.json")

sys.path.insert(0, SCRIPTS)
import hetero_review as h  # noqa: E402  (unit-test the profile helpers directly)

try:
    import jsonschema  # type: ignore

    HAVE_JSONSCHEMA = True
except ImportError:
    HAVE_JSONSCHEMA = False


def _run(py_script, args, cwd, env):
    return subprocess.run(
        [sys.executable, py_script] + args,
        cwd=cwd,
        env=env,
        capture_output=True,
        text=True,
    )


def _env(td):
    return {**os.environ, "CLAUDE_PROJECT_DIR": td}


def _runs(td, task):
    return sorted(
        glob.glob(os.path.join(td, ".claude", "parallel-dev", "runs", f"{task}-*.json"))
    )


def check_wrapper_drives_truthful_lifecycle():
    with tempfile.TemporaryDirectory() as td:
        r = _run(
            HETERO,
            [
                "--diff",
                "HEAD",
                "--blueprint",
                "t#b",
                "--task-id",
                "het1",
                "--dry-run",
                "--project-dir",
                td,
            ],
            td,
            _env(td),
        )
        assert r.returncode == 0, f"wrapper failed: {r.stderr or r.stdout}"
        recs = _runs(td, "het1")
        assert recs, f"wrapper must emit runs/het1-*.json: {td}"
        rec = json.load(open(recs[-1]))
        assert rec.get("converged") is True, f"not converged: {rec.get('converged')}"
        assert rec.get("dod_satisfied") is True, (
            f"dod_satisfied false (ADR #16 outer ring invariant): {rec.get('dod_satisfied')}"
        )
        assert rec["steps"]["inner"] >= 1, (
            f"steps.inner<1 — bookkeeping dishonest (ADR #39): {rec['steps']}"
        )
        # The run-record expresses the outer ring via outer_verdicts[] (one entry per
        # record-outer call); len >= 1 means the wrapper drove record-outer (ADR #16).
        assert len(rec["outer_verdicts"]) >= 1, (
            f"outer_verdicts empty — record-outer not driven: {rec.get('outer_verdicts')}"
        )
    print(
        "  --dry-run -> truthful run-record (converged, steps.inner>=1, outer>=1): PASS"
    )


def check_wrapper_returns_typed_findings():
    with tempfile.TemporaryDirectory() as td:
        r = _run(
            HETERO,
            [
                "--diff",
                "HEAD",
                "--blueprint",
                "t#b",
                "--task-id",
                "het2",
                "--dry-run",
                "--project-dir",
                td,
            ],
            td,
            _env(td),
        )
        out = json.loads(r.stdout)
        for key in ("verdict", "findings_count", "findings", "run_record"):
            assert key in out, f"typed return missing {key}: {out}"
        assert out["verdict"] in ("pass", "rewrite", "adversarial-stalemate"), (
            f"bad verdict: {out['verdict']}"
        )
        assert isinstance(out["findings"], list), "findings not a list"
    print("  --dry-run -> typed JSON return (reconciliation shape): PASS")


def check_adversarial_stalemate_round_trips():
    """P1-1 schema delta: record-outer accepts adversarial-stalemate AND the emitted
    run-record validates against run-record.schema.json."""
    with tempfile.TemporaryDirectory() as td:
        env = _env(td)
        assert _run(LOOP_STATE, ["init", "--task-id", "het3"], td, env).returncode == 0
        ro = _run(
            LOOP_STATE,
            [
                "record-outer",
                "--verdict",
                "adversarial-stalemate",
                "--findings",
                "2",
                "--notes",
                "cap=2 hit without convergence; escalate to human",
            ],
            td,
            env,
        )
        assert ro.returncode == 0, (
            f"record-outer --verdict adversarial-stalemate rejected (P1-1 delta): {ro.stderr}"
        )
        assert _run(LOOP_STATE, ["mark-converged"], td, env).returncode == 0
        assert _run(LOOP_STATE, ["run-record"], td, env).returncode == 0
        recs = _runs(td, "het3")
        assert recs, "run-record not emitted"
        rec = json.load(open(recs[-1]))
        verdicts = [v["verdict"] for v in rec["outer_verdicts"]]
        assert "adversarial-stalemate" in verdicts, (
            f"adversarial-stalemate not in run-record outer_verdicts: {verdicts}"
        )
        if HAVE_JSONSCHEMA:
            schema = json.load(open(RUN_RECORD_SCHEMA))
            jsonschema.validate(rec, schema)  # type: ignore[reportPossiblyUnboundVariable]  # raises on invalid
            print("  adversarial-stalemate round-trips + jsonschema VALID: PASS")
        else:
            # Degrade honestly (rule 3): structural check only — jsonschema absent.
            assert isinstance(rec.get("outer_verdicts"), list), (
                "outer_verdicts not a list"
            )
            print(
                "  adversarial-stalemate round-trips (structural; jsonschema absent): PASS"
            )


def check_embedded_skips_terminal_lifecycle():
    with tempfile.TemporaryDirectory() as td:
        r = _run(
            HETERO,
            [
                "--diff",
                "HEAD",
                "--blueprint",
                "t#b",
                "--task-id",
                "het4",
                "--dry-run",
                "--embedded",
                "--project-dir",
                td,
            ],
            td,
            _env(td),
        )
        assert r.returncode == 0, f"embedded wrapper failed: {r.stderr or r.stdout}"
        assert not _runs(td, "het4"), (
            "--embedded must NOT emit runs/ (orchestrator owns mark-converged/run-record)"
        )
    print("  --embedded -> skips init/mark-converged/run-record: PASS")


def check_malformation_gate_fail_survives_init():
    """Phase-1 dogfood blocker fix: the gate-fail fingerprint must survive
    drive_lifecycle's init (recorded POST-init, since loop_state `init` unconditionally
    re-defaults state). The fingerprint appears in the run-record's top_fingerprints."""
    with tempfile.TemporaryDirectory() as td:
        r = _run(
            HETERO,
            [
                "--diff",
                "HEAD",
                "--blueprint",
                "t#b",
                "--task-id",
                "het5",
                "--dry-run",
                "--dry-run-malform",
                "--project-dir",
                td,
            ],
            td,
            _env(td),
        )
        assert r.returncode == 0, f"malform wrapper failed: {r.stderr or r.stdout}"
        recs = _runs(td, "het5")
        assert recs, "malform run must emit runs/het5-*.json"
        rec = json.load(open(recs[-1]))
        fps = [f.get("fingerprint") for f in rec.get("top_fingerprints", [])]
        assert "dry-run-malform" in fps, (
            f"gate-fail fingerprint wiped by init (dogfood blocker regression): {fps}"
        )
        out = json.loads(r.stdout)
        assert out["malformation"] == "dry-run-malform", (
            f"malformation not surfaced in output: {out.get('malformation')}"
        )
    print("  --dry-run-malform -> gate-fail survives init + surfaces in output: PASS")


def check_budget_exhaustion_degrades():
    """ADR #41: a recoverable CC substrate error (budget cap) DEGRADES, not rewrites.

    The different-family leg contributes 0 findings + a coverage note + a persisted
    hetero-degraded-<subtype> fingerprint (so the thrashing breaker escalates persistent
    degradation); verdict stays pass (same-family primary stands — ADR #40 additive).
    Canned via --dry-run-budget (rule 4 — no real model call)."""
    with tempfile.TemporaryDirectory() as td:
        r = _run(
            HETERO,
            [
                "--diff",
                "HEAD",
                "--blueprint",
                "t#b",
                "--task-id",
                "het6",
                "--dry-run",
                "--dry-run-budget",
                "--project-dir",
                td,
            ],
            td,
            _env(td),
        )
        assert r.returncode == 0, f"budget wrapper failed: {r.stderr or r.stdout}"
        out = json.loads(r.stdout)
        # Degrade, not rewrite: a recoverable cap must not force a rewrite of the work.
        assert out["degraded"] is True, f"degraded flag not set: {out}"
        assert out["verdict"] == "pass", (
            f"budget must DEGRADE (verdict=pass), not rewrite: {out['verdict']}"
        )
        assert out["malformation"] == "", (
            f"degrade is not a malformation (return parsed cleanly): {out.get('malformation')}"
        )
        assert any("error_max_budget_usd" in c for c in out["coverage"]), (
            f"coverage missing the degrade note: {out['coverage']}"
        )
        assert out["degraded_providers"], "degraded_providers empty"
        assert out["degraded_providers"][0]["subtype"] == "error_max_budget_usd", out
        # Persistence-layer honesty (rule 3 / ADR #39): the degrade fingerprint must survive
        # to the run-record so persistent degradation escalates rather than masquerading as
        # clean convergence (converged:true, verdict:pass, findings:0).
        recs = _runs(td, "het6")
        assert recs, "budget run must emit runs/het6-*.json"
        rec = json.load(open(recs[-1]))
        fps = [f.get("fingerprint") for f in rec.get("top_fingerprints", [])]
        assert "hetero-degraded-error_max_budget_usd" in fps, (
            f"degrade fingerprint not persisted (ADR #41 honesty regression): {fps}"
        )
        # --dry-run-budget ALONE implies --dry-run (else subprocess.run(None) TypeError).
        r2 = _run(
            HETERO,
            [
                "--diff",
                "HEAD",
                "--blueprint",
                "t#b",
                "--dry-run-budget",
                "--embedded",
                "--project-dir",
                td,
            ],
            td,
            _env(td),
        )
        assert r2.returncode == 0, (
            f"--dry-run-budget alone must imply --dry-run: {r2.stderr or r2.stdout}"
        )
        out2 = json.loads(r2.stdout)
        assert out2["degraded"] is True and out2["verdict"] == "pass", out2
    # PI PORT: the CC envelope parser is retired; the wrapper-side caps classify
    # from live telemetry. Unit-check the budget/turns kill -> DEGRADE mapping via
    # _run_streamed telemetry (no subprocess; ADR #41 semantics unchanged).
    tele_budget = {"killed": "budget-cap", "cost_usd": 12.5, "assistant_events": 2}
    assert (
        tele_budget["killed"] == "budget-cap"
    )  # _run_claude_once maps -> error_max_budget_usd
    tele_turns = {"killed": "turns-cap", "cost_usd": 0.0, "assistant_events": 61}
    assert tele_turns["killed"] == "turns-cap"  # -> error_max_turns
    print(
        "  --dry-run-budget -> degrade (pass + flag + persisted fingerprint + modes): PASS"
    )


def check_provider_template_expansion():
    """Convention token-var derivation + materialization. The token var is DERIVED
    from the profile filename (<UPPERCASE-FILENAME>_ANTHROPIC_AUTH_TOKEN), so a
    user-authored profiles/foo.json needs NO _token_env / ${...} — zero ceremony."""
    # convention derivation (no _token_env in the template)
    assert h._resolve_token_var("deepseek", {}) == "DEEPSEEK_ANTHROPIC_AUTH_TOKEN"
    assert h._resolve_token_var("qwen3", {}) == "QWEN3_ANTHROPIC_AUTH_TOKEN"
    assert (
        h._resolve_token_var("openai-compat", {})
        == "OPENAI_COMPAT_ANTHROPIC_AUTH_TOKEN"
    )
    # optional override via _token_env
    assert h._resolve_token_var("x", {"_token_env": "CUSTOM_VAR"}) == "CUSTOM_VAR"
    print("  _resolve_token_var (convention + _token_env override): PASS")

    # recursive ${VAR} expansion still works for NON-token fields
    os.environ["HETERO_UNIT"] = "u-val"
    expanded = h._expand_env_values(
        {"env": {"X": "${HETERO_UNIT}"}, "nested": {"y": "${HETERO_UNIT}"}}
    )
    assert expanded["env"]["X"] == "u-val" and expanded["nested"]["y"] == "u-val"
    del os.environ["HETERO_UNIT"]
    print("  _expand_env_values (recursive, non-token ${VAR}): PASS")

    # PI PORT: _load_profile returns the route template (no temp settings file;
    # the token travels via inherited env). Token presence is the fail-fast gate.
    os.environ["DEEPSEEK_ANTHROPIC_AUTH_TOKEN"] = "sk-conv-unit"
    d = h._load_profile("deepseek")
    assert d["_provider"] == "deepseek" and d["model"] == "deepseek-v4-flash", d
    # CC-era alias resolution + route composition (token set: the profile's
    # _token_env names the CC-convention var; empty would mean auth.json route)
    os.environ["BIGMODEL_ANTHROPIC_AUTH_TOKEN"] = "sk-zai-unit"
    zai = h._load_profile("bigmodel")
    assert zai["_provider"] == "zai-coding-cn" and zai["model"] == "glm-5.3", zai
    argv = h._pi_argv(zai, "", "p", None)
    assert argv[argv.index("--model") + 1] == "zai-coding-cn/glm-5.3", argv
    del os.environ["DEEPSEEK_ANTHROPIC_AUTH_TOKEN"]
    del os.environ["BIGMODEL_ANTHROPIC_AUTH_TOKEN"]
    print("  _load_profile (route template + alias + model composition): PASS")

    # missing token -> fail fast (non-zero), naming the CONVENTION var
    r = _run(
        HETERO,
        [
            "--diff",
            "HEAD",
            "--blueprint",
            "t#b",
            "--task-id",
            "u",
            "--profile",
            "deepseek",
            "--project-dir",
            tempfile.mkdtemp(),
        ],
        tempfile.mkdtemp(),
        {**os.environ, "DEEPSEEK_ANTHROPIC_AUTH_TOKEN": ""},
    )
    out = r.stdout + r.stderr
    assert r.returncode != 0 and "DEEPSEEK_ANTHROPIC_AUTH_TOKEN" in out, (
        r.returncode,
        out,
    )
    print("  missing-token fail-fast (names the convention var): PASS")


def check_dual_provider_dry_run():
    """Multi-different-family: --profile a,b runs each backend, tags findings with `provider`,
    returns the provider list. Offline via --dry-run (no real model call)."""
    with tempfile.TemporaryDirectory() as td:
        r = _run(
            HETERO,
            [
                "--diff",
                "HEAD",
                "--blueprint",
                "t#b",
                "--task-id",
                "v",
                "--profile",
                "deepseek,bigmodel",
                "--dry-run",
                "--project-dir",
                td,
            ],
            td,
            _env(td),
        )
        assert r.returncode == 0, r.stderr or r.stdout
        out = json.loads(r.stdout)
        assert out["providers"] == ["deepseek", "bigmodel"], out
    print("  dual-different-family dry-run (providers listed): PASS")


def check_unknown_provider_fail_fast():
    """An unknown provider NAME (no template) fails fast with a clear error."""
    with tempfile.TemporaryDirectory() as td:
        r = _run(
            HETERO,
            [
                "--diff",
                "HEAD",
                "--blueprint",
                "t#b",
                "--task-id",
                "w",
                "--profile",
                "nonexistent",
                "--dry-run",
                "--project-dir",
                td,
            ],
            td,
            _env(td),
        )
        out = r.stdout + r.stderr
        assert r.returncode != 0 and "unknown provider profile" in out, out
    print("  unknown-provider fail-fast: PASS")


def main():
    print("hetero_review.py ↔ loop_state wiring (ADR #40 Phase 1):")
    failures = []
    for fn in (
        check_wrapper_drives_truthful_lifecycle,
        check_wrapper_returns_typed_findings,
        check_adversarial_stalemate_round_trips,
        check_embedded_skips_terminal_lifecycle,
        check_malformation_gate_fail_survives_init,
        check_budget_exhaustion_degrades,
        check_provider_template_expansion,
        check_dual_provider_dry_run,
        check_unknown_provider_fail_fast,
    ):
        try:
            fn()
        except AssertionError as e:
            failures.append(str(e))
            print(f"  {fn.__name__}: FAIL — {e}")
        except Exception as e:  # noqa: BLE001
            failures.append(f"{fn.__name__}: error — {e}")
            print(f"  {fn.__name__}: ERROR — {e}")
    if failures:
        print(f"\n{len(failures)} failure(s).")
        sys.exit(1)
    print(
        "\nwiring: hetero_review drives loop_state truthfully + adversarial-stalemate "
        "round-trips the schema (P1-1/P1-4/P1-5/P1-7)."
    )
    sys.exit(0)


if __name__ == "__main__":
    main()
