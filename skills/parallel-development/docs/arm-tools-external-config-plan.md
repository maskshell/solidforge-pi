# Arm-Tools External-Config — Implementation Plan (Gap A)

> Status: **IMPLEMENTED** — the steps below landed in `arm.py` + templates + tests. Companion to [arm-tools-external-config-design.md](arm-tools-external-config-design.md) (the design decisions — Context / Decision / Why / Rejected). This doc was the **ordered execution plan**: steps, files, verification. Scope was **Gap A only** (Gap B dropped — see design doc).

## Scope (one line)

Add opt-in `--scaffold-configs [vale,semgrep,spectral]` to `arm.py`, scaffolding the 3 external-tool configs that need one (Vale hard-no-ops without config; Semgrep/Spectral gain offline-determinism / editability). No settings mutation; no hook-ification; ADR #19 invariant untouched.

## Steps (in order)

### 1. `arm.py` — registry + copy/uninstall functions

- Add `EXTERNAL_CONFIGS` immediately after `ARCH_CONFIGS` (`infra/install/arm.py:458`): `(filename, key, note)` 3-tuples, **no language predicate** (these tools cross-cut languages). Entries: `.vale.ini`/`vale`, `.semgrep.yml`/`semgrep`, `.spectral.yaml`/`spectral`.
- Add `copy_external_configs(project_dir, tools)` — mirror `copy_arch_configs` (`:135`): iterate `EXTERNAL_CONFIGS`, skip if `key not in selected`, skip-if-exists (never clobber), `shutil.copy2` from `TEMPLATES_SRC`, print `+ copied … (note)`.
- Add `uninstall_external_configs(project_dir, apply)` — mirror `uninstall_arch_configs` (`:822`): `_same_content` → remove; differs-from-template → KEPT + warn.

### 2. `arm.py` — flag parsing + wiring

- `main()` (`:936`): parse `--scaffold-configs [vale,semgrep,spectral]` (membership-test + `args.index`, mirroring `--lang` at `:942-951`); unknown key → exit 2 (mirror `:953-959`).
  - **Value parsing (m1, new shape)**: `--scaffold-configs` is an OPTIONAL-VALUE flag — the next arg is treated as the value only if it does NOT start with `--` AND is a known key (comma-split for multi); otherwise bare `--scaffold-configs` = all 3. arm.py has no existing optional-value flag (`--lang` is value-required, `--with-tools` is pure-switch) — implement the optional-value check explicitly, do not mirror an existing one.
  - **`--revert` interaction (B1 fix)**: ignored under `--revert` with a WARNING (NOT exit 2) — it is a forward-only arming flag and revert unconditionally removes what arming added (mirror `uninstall_arch_configs`). Do NOT mirror the `--lang`-needs-`--with-tools` exit-2 guard — `--scaffold-configs` is independent of `--with-tools` (design D1).
- Forward path: call `copy_external_configs(project_dir, selected)` right after `copy_arch_configs` (`:996`).
- **Vale sync (M1, auto)**: after `copy_external_configs`, if `vale` is in `selected` and `have("vale")` is true, subprocess `vale sync` (cwd=project_dir) to fetch the style packages into `.vale/styles/` — mirrors `--with-tools` subprocess-ing `uv add`/`npm install`. If `vale` is absent, print the install+sync step and skip (mirrors `--with-tools` for system tools). Without this the scaffolded `.vale.ini` leaves the Vale gate a no-op.
- `do_revert` (`:925`): call `uninstall_external_configs(project_dir, apply)` right after `uninstall_arch_configs` (`:930`).
- Update the module docstring usage block (`:20-24`) with the new flag.

### 3. Templates (new files under `infra/templates/`)

- `.vale.ini` — `StylesPath=.vale/styles`; `Vale: Microsoft/Google/Proselint/Vale.Terms/Alex`; `MinAlertLevel=suggestion`; header flags **STARTING POINT / styles-are-opinion / `vale sync` fetches packages** (subjective, no objective default — per `vale_adapter.py:30`; the gate no-ops until `vale sync` populates `.vale/styles/` — M1, which arming auto-runs when `vale` is on PATH).
- `.semgrep.yml` — OWASP-top-ten + security-audit starting rules; offline-deterministic (replaces `--config auto`); header flags advisory/extend-locally.
- `.spectral.yaml` — `extends: ["spectral:oas"]` + tunable defaults; header flags it replaces the adapter's synthesized temp default.

### 4. Tests

- `infra/test/arm_copy_config.py` — add `EXT_CASES` / `EXT_ALL`; coverage guard mirroring `CASES`/`ALL_CONFIGS` (`:33-41`, `:118-132`): every `EXTERNAL_CONFIGS` entry has a template AND a test case (declared == tested); structural guard (3-tuple). Add `run_ext_case(key, expected)`; multi-tool case (vale+semgrep); bare-flag case (None → all 3); skip-if-exists case (pre-created `.vale.ini` not clobbered). Extend `t_arm_idempotent` to run with `--scaffold-configs` and assert idempotency.
- `infra/test/arm_revert.py` — add `t_external_config_user_edit_kept` (arm → edit `.vale.ini` → `--revert --apply` → KEPT + warn) and `t_external_config_template_removed` (arm → no edit → `--revert --apply` → all 3 removed). The "never touch settings" invariant is **unchanged** (Gap B dropped).

### 5. Docs (workspace rule 5 doc-audit — grep + update every enumeration)

- `commands/arm-tools.md` — frontmatter `argument-hint` (`:3`) + Step 1 (`:10-20`).
- `references/install.md` — Layer 2 arming list (`:40-47`); "What each gate does" Vale/Semgrep/Spectral rows (`:96-98`) note config source; revert removal list (`:114-119`); **first-allow note** (Gap B dropped — on first convergence run, allow `Bash(python3:*)`, Claude Code remembers).
- `USER_GUIDE.md` — Scenario 5 Step 2 (`:102-103`) add `--scaffold-configs` shortcut; quick-ref table (`:147`).
- `references/external-skills.md` — Vale/Semgrep/Spectral `ruleset` fields → `--scaffold-configs` pointer.
- `references/maturity.md` / `SKILL.md` / `references/extending.md` — caveats + note that `EXTERNAL_CONFIGS` has its own coverage guard in `arm_copy_config.py` (NOT `disconnect_check.py`'s platform checks).

## Files

| Action | Path |
| --- | --- |
| modify | `skills/parallel-development/infra/install/arm.py` |
| modify | `skills/parallel-development/infra/test/arm_copy_config.py` |
| modify | `skills/parallel-development/infra/test/arm_revert.py` |
| add | `skills/parallel-development/infra/templates/.vale.ini` |
| add | `skills/parallel-development/infra/templates/.semgrep.yml` |
| add | `skills/parallel-development/infra/templates/.spectral.yaml` |
| modify | `commands/arm-tools.md` |
| modify | `skills/parallel-development/references/install.md` |
| modify | `USER_GUIDE.md` |
| modify | `skills/parallel-development/references/external-skills.md` |
| modify | `skills/parallel-development/references/maturity.md` |
| modify | `skills/parallel-development/SKILL.md` |
| modify | `skills/parallel-development/references/extending.md` |

## Reused patterns (mirror, don't reinvent)

- `copy_arch_configs` / `uninstall_arch_configs` (`arm.py:135` / `:822`) — copy + `_same_content` revert.
- `ARCH_CONFIGS` + `arm_copy_config.py` CASES coverage-guard (`:33-41`, `:118-132`) — registry + test-coverage enforcement.
- `--lang` parsing/validation in `main()` (`arm.py:942-959`) — flag + unknown-value → exit 2.

## Verification checklist

- [ ] `python3 skills/parallel-development/infra/test/disconnect_check.py` — green, **unchanged** (Gap A is not a platform).
- [ ] `python3 skills/parallel-development/infra/test/arm_copy_config.py` — green (new EXT coverage guard + cases).
- [ ] `python3 skills/parallel-development/infra/test/arm_revert.py` — green (new revert cases; settings invariant unchanged).
- [ ] Full `infra/test/` suite green (rule 1): smoke_gates, lint_self, plugin_layout, run_record, plan_queue_detect, arm_report_gates.
- [ ] Manual e2e (temp project): `arm.py <tmp> --scaffold-configs` → 3 configs; `--scaffold-configs vale` → 1; idempotent re-run; pre-existing `.vale.ini` not clobbered; edit `.vale.ini` → `--revert --apply` removes template-matching configs, keeps the edited one.
- [ ] Doc-audit (rule 5): grep `--scaffold-configs` / external-tool config / arming; every enumeration updated; terminology consistent (rule 10).

## Open questions (non-blocking)

1. **Semgrep template offline form** — `extends: [p/owasp-top-ten, p/security-audit]` (post one-time `semgrep sync`) vs explicit `rules:`. Verify which the target Semgrep version resolves offline; the adapter accepts `.semgrep.yml` either way. Decide at step 3.
2. **(Incidental, separate pass — NOT in this plan's scope)** Gate-execution path discrepancy: `arch-contracts.md:121` + L4 patterns say `.claude/parallel-dev/scripts/`; `install.md:8` / `README.md:13` / `hooks.json` say plugin root; `scope_check.py:62` lists `.claude/parallel-dev/scripts/loop_state.py` as sacred. The bc-orchestrator review this session reinforced the plugin-root side (`hooks/hooks.json` fires hooks via `${CLAUDE_PLUGIN_ROOT}/...` with no per-project copy), but `scope_check.py`'s sacred-path evidence still contradicts. Trace one real convergence run to reconcile. Filed in the design doc; fix independently once confirmed.
