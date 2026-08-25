# arm placeholder arch-config fix — iteration plan (bc-frozen, pd input)

> Frozen from `arm-placeholder-config-fix.proposal.md` (csr SUBSTANTIVE-CONVERGED r2; psv M=0 — no
> admissible surface). Authority chain: on conflict, the csr-converged proposal + source win.
> Grain: ACF-I0..I5. Validation gate = each item's self-gates green (the only "done").

## Items

| ID | iteration | complexity | deps | DoD (the validation gate) |
| --- | --- | --- | --- | --- |
| ACF-I0 | neutral-by-default templates | M | — | `.importlinter.ini` layers/forbidden commented + `root_package = __REPLACE_ME__` + full-line verify comment; `.dependency-cruiser.cjs` keeps `no-circular`, comments the layer example; `.swiftlint.yml` scan-all (no `included`) + excludes + `custom_rules` layer contracts commented |
| ACF-I1 | arm.py detect + substitute | M | ACF-I0 | stdlib `detect_root_package` (pyproject/src-layout/flat) + web `src/` detection; `copy_arch_configs` substitutes the token (.importlinter.ini, .dependency-cruiser.cjs) via `shutil.copy2` + one `str.replace`; `__REPLACE_ME__` on detect-failure; Swift no-substitution |
| ACF-I2 | arm report placeholder advisory | S | ACF-I1 | `copy_arch_configs` prints a per-affected-config gate-status advisory ("layering is a PLACEHOLDER — uncomment + edit to opt in; gate green until then") |
| ACF-I3 | revert token normalization | S | ACF-I1 | `uninstall_arch_configs` widens matches-template: normalize the substituted root/src token back to the template placeholder before `_same_content` (1-token delta = still template/removable; any other diff = user-edited/kept+warned) |
| ACF-I4 | gate 0-active detect/skip/note (Python) | L | ACF-I0 | `arch_contract_python.py::check_import_linter`: format-aware active-contract detect (re-resolve `find_importlinter_config` `"__auto__"` to the file; INI `[importlinter:contract:…]` vs TOML `[[tool.importlinter.contracts]]`); 0-active → SKIP lint-imports + distinct note `"0 active contracts — layering NOT enforced; uncomment to opt in"`; N-active → run + existing note. Verify `arch_contract_web.py` (already count-honest) |
| ACF-I5 | ADR + doc-audit + self-gates | M | ACF-I0–I4 | ADR #49 (placeholder configs neutral-default + auto-detected root + layering human opt-in + gate 0-active note); install.md/arm guidance doc-audit; existing arm self-gates (`arm_copy_config`/`arm_revert`/`arm_report_gates`/`disconnect_check`/`plugin_layout`) green; NEW coverage for `detect_root_package` + the 0-active gate branch |

## DAG

```text
ACF-I0 templates ─▶ ACF-I1 detect+substitute ─┬─▶ ACF-I2 advisory
                                               └─▶ ACF-I3 revert ─▶ ACF-I5 ADR+gates
ACF-I0 ─▶ ACF-I4 gate 0-active ──────────────────────────────────▶ ACF-I5
```

## Risks (carried from csr-converged proposal §5)

- root-package mis-detect → full-line verify comment (NOT inline — configparser) + `__REPLACE_ME__` fallback.
- 0-active detection cross-format → format-aware parse (INI vs TOML) + re-resolve `"__auto__"`.
- substitution vs revert → token normalization before `_same_content`.
- gate change regresses active path → only a 0-active branch added; covered by `arm_report_gates` + new unit case.

## Phase-A acceptance

- A freshly-armed Python project (no `app` package, `lint-imports` installed) has a **green + honest** gate right after arm (0-active note, not red, not misleading "checked").
- `--revert` removes an armed, unedited config (token-normalized match) and keeps+warns a user-edited one.
- All arm/pd self-gates green; ADR #49 recorded.
