# Arm-Tools External-Config Scaffolding Design (Gap A)

> Status: **IMPLEMENTED** (see `arm.py --scaffold-configs`). Scope was **Gap A only** (scaffold external-tool configs). Gap B (auto-write gate permissions to `.claude/settings.local.json`) was explored and **dropped** — gate permissions are left to Claude Code's first-allow-remembers mechanism (no settings mutation; ADR #19's "arm never touches settings" invariant stays intact). A hook-ification path was also evaluated and rejected (see Rejected). Grounded in the verified current state of `skills/parallel-development/`.
>
> Related: [external-skill-integration.md](external-skill-integration.md) (the external-skill adapter model this extends); [arm-tools-external-config-plan.md](arm-tools-external-config-plan.md) (the execution plan).

**File-reference convention** — this doc lives in `skills/parallel-development/docs/`; its subject is parallel-development's `arm.py`. All `file:line` refs are under `skills/parallel-development/` unless prefixed otherwise. ADR citations point to `references/design-decisions.md`.

## Context (verified current state)

### Gap A — external configs are hand-written; arm.py's own arch-configs are auto-copied

`copy_arch_configs` (`infra/install/arm.py:135`) `shutil.copy2`s `.importlinter.ini` / `clippy.toml` / `checkstyle.xml` / `.golangci.yml` / `.swiftlint.yml` / `.dependency-cruiser.cjs` from `infra/templates/` for detected languages. But the external-tool adapter configs (`.vale.ini`, `.semgrep.yml`, `.spectral.yaml`) are left to the user (`USER_GUIDE.md:102-103`). Of the six external adapters, only three need a config:

- **Vale** — `vale_adapter.py:82` `has_config` looks for `.vale.ini` / `_vale.ini` / `.vale`, **no fallback**; no config → no-op. Hard gate — dead on arrival without scaffolding.
- **Semgrep** — `semgrep_adapter.py:83` `resolve_ruleset` falls back to `--config auto` (registry fetch, network). Scaffolding buys offline determinism.
- **Spectral** — `spectral_adapter.py:135` `resolve_ruleset` synthesizes a temp `extends: ["spectral:oas"]` when no project ruleset exists (the adapter's fallback). Scaffolding a `.spectral.yaml` with the same default is only worth it when the user wants to customize; otherwise the fallback already covers it.
- **oasdiff / Checkov (`iac_adapter.py`) / Trivy (`license_adapter.py`)** — **no config file** (git-diff / built-in framework policy / dep markers). Not scaffolded.

### Gap B — explored, then dropped (gate permissions)

- Every convergence-point gate/adapter runs via the orchestrator agent's **Bash tool** → first / un-allowed invocation prompts for permission.
- `arm.py` never pre-clears (ADR #19 invariant, asserted by `infra/test/arm_revert.py`).
- **But Claude Code remembers a first "always allow"** — once the user approves `Bash(python3:*)` (or a narrower prefix), it is persisted to `settings.local.json` and never re-prompts on that machine. So Gap B's real incremental value was only "skip that one first manual click per user/machine".
- **Hook-ification** (PostToolUse/PreToolUse hooks run by the harness, bypassing Bash permission) was evaluated to eliminate prompts another way. Rejected: the hook-able surface is **already** occupied by `fast_gate.py` (`infra/hooks/fast_gate.py:4` — "The heavier … checks belong to the arch-contract gate … NOT here"). The remaining gates are heavy whole-project / convergence-point scans (import-linter / clippy / semgrep / test-suite / dep-CVE >20s, need full context, take dynamic args) that cannot be per-edit hooks — hook-ifying them means running a full-project scan on every Edit (slow, costly, timeout). `arch-contracts.md:118` states this explicitly.
- **Decision: drop Gap B.** Neither auto-writing settings (breaks ADR #19 for a one-click saving) nor hook-ification (infeasible for heavy gates) is worth it. Document the first-allow mechanism instead.

## Decision

**D1 — Gap A: opt-in `--scaffold-configs [vale,semgrep,spectral]` templates the three configs that need one.**

- New `EXTERNAL_CONFIGS` registry mirrors `ARCH_CONFIGS` (`arm.py:451`) but as `(filename, key, note)` 3-tuples with **no language predicate** — these tools cross-cut languages (Vale = any docs, Semgrep = any source, Spectral = any OpenAPI spec). Selection is by the flag value; bare `--scaffold-configs` = all three.
- New `copy_external_configs(project_dir, tools)` mirrors `copy_arch_configs` (`arm.py:135`): skip-if-exists, never clobber. Three templates land in `infra/templates/` (`.vale.ini` / `.semgrep.yml` / `.spectral.yaml`), each header-flagged **STARTING POINT**. Vale's is explicitly subjective (styles are opinion, no objective default) AND incomplete on its own — the template references style packages (`Microsoft`/`Google`/...) the user must fetch with `vale sync` (the adapter no-ops until then), so arming runs `vale sync` automatically when `vale` is on PATH (mirrors `--with-tools` running `uv add`/`npm install`); if `vale` is absent it prints the install+sync step and skips (mirrors `--with-tools` for system tools). Spectral's default content equals the adapter's synthesized fallback (`extends: ["spectral:oas"]`) — scaffolding it is only worth it when the user wants to customize; otherwise the fallback already covers the default.
- Revert: `uninstall_external_configs` mirrors `uninstall_arch_configs` (`arm.py:822`) — `_same_content` keeps user-edited configs.
- Flag interactions: default OFF; independent of `--with-tools`; composable; ignored under `--revert` (revert unconditionally removes what arming added — mirroring `uninstall_arch_configs`); unknown tool key → exit 2 (mirrors `--lang` validation, `arm.py:953`).

**D2 — Gap B dropped; document the first-allow mechanism instead.** No `--allow-gates`, no settings mutation, no ADR #36. `USER_GUIDE.md` Scenario 5 + `references/install.md` add a one-line note: on the first convergence run, allow `Bash(python3:*)` when prompted — Claude Code remembers it. ADR #19 invariant untouched.

## Why

- Gap A: Vale is a hard no-op without config — and even with `.vale.ini` scaffolded it stays dead until `vale sync` fetches the style packages (see D1; arming runs `vale sync` automatically when `vale` is on PATH) — so the prose-quality gate is dead on arrival for every new project without scaffolding (+ the sync step). Semgrep scaffolding buys offline determinism (replaces the `--config auto` network fetch). Spectral scaffolding's value is only customization (its default equals the adapter's fallback). oasdiff/Checkov/Trivy have no config to scaffold.
- Gap B dropped: the saving (one first manual allow per machine) does not justify reversing ADR #19's "arm never touches settings" invariant (which `arm_revert.py` asserts and which protects user-owned settings). Hook-ification is infeasible for the heavy gates that actually prompt. Claude Code's native first-allow-remembers already solves the prompt friction after one click.
- Gap A reuses existing patterns (`copy_arch_configs` / `uninstall_arch_configs`) — no new paradigm (workspace rule 7).

## Rejected

- **Scaffold all six adapters** — three have no config (oasdiff/Checkov/Trivy); impossible/meaningless.
- **Make templates authoritative defaults** — Vale styles are opinion; an authoritative default would be a false default. Templates are STARTING POINTS; adapters stay advisory (severity collapses to `warning`, never `blocker`).
- **Gate scaffolding on a language predicate (like `ARCH_CONFIGS`)** — these tools cross-cut languages; a Vale config is wanted iff there are docs, regardless of Python/Rust/etc.
- **Gap B — auto-write `Bash(python3:*)` to `settings.local.json`** — reverses ADR #19 for a one-click saving; the invariant protects user-owned settings. First-allow-remembers already handles the friction natively.
- **Gap B — write `.claude/settings.json` (team-shared)** — forces the rule on all contributors; violates per-user consent + the `hooks-reference.md:15` scope model. (Moot now — Gap B dropped.)
- **Hook-ify the heavy gates** — `fast_gate.py` already occupies the only hook-able surface (lightweight per-file checks); the rest are >20s whole-project scans needing full context + dynamic args, unsuitable as PostToolUse hooks (per `arch-contracts.md:118`). Hook-ifying them = a full-project scan per Edit.

## Implementation surface

**Code:**

- `skills/parallel-development/infra/install/arm.py` — `EXTERNAL_CONFIGS` registry; `copy_external_configs`; `uninstall_external_configs`; `main()` `--scaffold-configs` parsing + wiring; `do_revert` wiring; docstring usage block.
- `skills/parallel-development/infra/test/arm_copy_config.py` — `EXT_CASES` / `EXT_ALL` + coverage guard (mirror `CASES` / `ALL_CONFIGS`: every `EXTERNAL_CONFIGS` entry has a template AND a test case); `run_ext_case`; multi-tool / bare-flag / skip-if-exists cases; extend `t_arm_idempotent` to include `--scaffold-configs`.
- `skills/parallel-development/infra/test/arm_revert.py` — add `t_external_config_user_edit_kept`, `t_external_config_template_removed`. (The "never touch settings" invariant stays **unchanged** — Gap B is dropped.)

**Templates (new):** `infra/templates/.vale.ini`, `.semgrep.yml`, `.spectral.yaml`. Concrete contents: Vale = `StylesPath=.vale/styles` + Microsoft/Google/Proselint/Vale.Terms/Alex + `MinAlertLevel=suggestion`, **header notes `vale sync` fetches the packages; arming auto-runs it when `vale` is on PATH (the gate no-ops otherwise)**; Semgrep = OWASP-top-ten + security-audit (offline-deterministic); Spectral = `extends: ["spectral:oas"]` + tunable defaults.

**Docs (workspace rule 5 doc-audit):** `commands/arm-tools.md` (argument-hint + Step 1), `references/install.md` (arming list + gate table Vale/Semgrep/Spectral rows + revert list + **first-allow note**), `USER_GUIDE.md` Scenario 5 + quick-ref, `references/external-skills.md` (ruleset fields → `--scaffold-configs` pointer), `references/maturity.md` caveats, `SKILL.md`, `references/extending.md` (`EXTERNAL_CONFIGS` has its own coverage guard in `arm_copy_config.py`, NOT part of `disconnect_check.py`'s platform checks).

**Reused patterns:** `copy_arch_configs` / `uninstall_arch_configs` (`arm.py:135` / `:822`); `ARCH_CONFIGS` + `arm_copy_config.py` CASES coverage-guard.

## Verification

- Self-tests green (workspace rule 1, full suite before commit): `infra/test/arm_copy_config.py`, `arm_revert.py`, `disconnect_check.py` (should pass **unchanged** — Gap A is not a platform), and the rest of `infra/test/`.
- Manual e2e (temp project): `arm.py <tmp> --scaffold-configs` → 3 configs present (bare flag) / subset (named); second run idempotent; pre-existing `.vale.ini` not clobbered; edit `.vale.ini` then `--revert --apply` → template-matching configs removed, edited `.vale.ini` KEPT.
- Doc-audit pass (rule 5): grep every enumeration mentioning external-tool config / arming; confirm all updated, terminology consistent (rule 10).

## Open questions

1. **Semgrep template offline form** — `extends: [p/owasp-top-ten, p/security-audit]` (post one-time sync) vs explicit `rules:`; verify which the target Semgrep version resolves offline. The adapter accepts `.semgrep.yml` either way.
2. **(Incidental, NOT blocking Gap A)** Gate-execution path discrepancy: `references/arch-contracts.md:5/:121` + the six L4 `*-patterns.md` cite `python3 .claude/parallel-dev/scripts/<script>.py`, while `references/install.md:8` + `README.md:13` + `hooks/hooks.json` (`${CLAUDE_PLUGIN_ROOT}`) say scripts run from the plugin root and are NOT copied — yet `infra/test/scope_check.py:62/70/128` lists `.claude/parallel-dev/scripts/loop_state.py` as "sacred", implying that path exists. Evidence conflicts; reconcile by tracing one real convergence run (which command the orchestrator actually issues). The bc-orchestrator review this session reinforced the plugin-root side (`hooks/hooks.json` invokes hooks via `${CLAUDE_PLUGIN_ROOT}/...` with no per-project copy, and they fire), but `scope_check.py`'s sacred-path evidence still contradicts. This is a pre-existing doc/consistency question independent of Gap A; fix it in a separate pass once confirmed.

## Risks

- A scaffolded default could run a gate stricter than expected (e.g. Vale `MinAlertLevel=suggestion` is noisy) — mitigated: all three adapters are advisory (severity collapses to `warning`, never `blocker`), so scaffolding cannot block convergence; template headers flag STARTING POINT.
- **Vale scaffold needs `vale sync`** (M1) — the template references style packages but does not fetch them. Arming runs `vale sync` automatically when `vale` is on PATH (mirrors `--with-tools`); if `vale` is absent the gate stays a no-op until the user installs vale + syncs — the adapter coverage-notes the missing styles, arming prints the step (never silent).
