# arm placeholder arch-config fix — design proposal (csr r2 input)

> Status: csr round-1 reconciled (same-family 4 + 异源 7 findings, all adopted after independent
> verification); round-2 confirm pending. Process-axis only; soundness human.

## 1. Problem

`arm.py::copy_arch_configs` → `shutil.copy2` (**verbatim, no substitution**). Templates ship
hardcoded example structure → freshly-armed project has an ineffective/misleading gate. The only
current hint is a generic copy-time print, not a gate-status advisory.

`ARCH_CONFIGS` = **6** templates. Classification:

| template | status | why |
| --- | --- | --- |
| `.importlinter.ini` | **fix** | hardcoded `root_package = app` + example layers |
| `.dependency-cruiser.cjs` | **fix (partial)** | example layer rule (`src/core→src/(ui\|server)`) commented; the UNIVERSAL `no-circular` rule KEPT (it's structural, not example layering) |
| `.swiftlint.yml` | **fix (expanded)** | hardcoded `included: [Sources, Tests]` AND active layer contracts under `custom_rules` (codable-decodable boundary) — BOTH neutralized |
| `.golangci.yml` | unchanged | already neutral (depguard commented; govet+gofmt only) |
| `checkstyle.xml` | unchanged | generic lint rules, no package/layer assumption |
| `clippy.toml` | unchanged | commented thresholds; Rust has no layer enforcer |

So **3 of 6** templates need changes.

## 2. The split

- **Root package / source root** (`root_package`; web `src/`) — **determinable** → automate.
  (Swift: NOT source-root-substituted — see §3.1; `Sources/` is SPM-only and detection is brittle, so
  Swift uses a scan-all default instead. This resolves the §2-vs-§3.1 contradiction flagged in r1.)
- **Layer decomposition** (api/services/…; core/ui/…; Swift custom_rules) — **human design decision**
  → neutral (commented) + advisory.

## 3. Solution

1. **Neutral-by-default templates**:
   - `.importlinter.ini`: set `root_package = <detected>` (detection failure → the literal placeholder
     `__REPLACE_ME__`, NOT an inline comment — Python configparser does NOT support inline comments,
     so `root_package = x  # comment` parses the value as `"x  # comment"`, breaking it; the
     verify-me note goes on a SEPARATE full-line comment ABOVE the key); **comment out** the
     `[importlinter:contract:layers]` + `[importlinter:contract:forbidden-…]` blocks.
   - `.dependency-cruiser.cjs`: KEEP the universal `no-circular` `forbidden` rule (structural);
     comment only the example layer `forbidden`/`layers` rules.
   - `.swiftlint.yml`: drop `included: [Sources, Tests]` → scan-all default + excludes (`.build`,
     `DerivedData`, `build`, `Pods`); AND comment out the active `custom_rules` layer/boundary
     contracts (they're example layering, same class as the others).
2. **`arm.py`**: stdlib `detect_root_package` (Python; parse pyproject `[tool.setuptools.packages]`/
   `name`, src-layout `src/<pkg>/__init__.py`, flat-layout) + web `src/` detection; on copy,
   `shutil.copy2` then a single targeted `str.replace` of the root/source-root token. Swift: no
   substitution (scan-all template).
3. **Gate-side (Python) coverage-note + skip refinement**: `arch_contract_python.py::check_import_linter`
   currently appends `"import-linter: layer/forbidden contracts checked"` unconditionally (line 143) →
   under 0 active contracts that's misleading. Fix: detect active contracts by parsing the RESOLVED
   config **format-aware** — `find_importlinter_config` returns the path for `.importlinter.ini` but
   the sentinel `"__auto__"` for `setup.cfg`/`pyproject.toml`, so re-resolve `"__auto__"` to the
   actual file, then parse with the FORMAT-SPECIFIC contract shape: INI (`.importlinter.ini`,
   `setup.cfg`) uses `[importlinter:contract:…]` sections; TOML (`pyproject.toml`) uses
   `[[tool.importlinter.contracts]]` array-of-tables. If 0 active → **SKIP the lint-imports
   invocation** (don't run it for nothing) + emit a DISTINCT coverage note `"import-linter: 0 active
   contracts — layering NOT enforced; uncomment + edit to opt in"`; N-active → run + keep the
   existing "... contracts checked" note. Swift gate already honest (count-based);
   `arch_contract_web.py` checked for the same unconditional-note pattern + fixed if present.
4. **arm report advisory**: per affected config, a gate-status advisory line.
5. **Reversibility (`--revert`)**: `uninstall_arch_configs` uses byte-for-byte `_same_content`; after
   on-copy substitution the bytes differ by the root token. Mechanism (specified, not deferred):
   normalize the substituted token back to the template's placeholder before `_same_content` compare
   (i.e. compare `actual_with_root_unsubstituted == template`); a config differing ONLY by the root
   token = "still template" → removable; any other diff = user-edited → kept + warned.

## 4. Scope

- Templates: `.importlinter.ini`, `.dependency-cruiser.cjs`, `.swiftlint.yml` (3 of 6).
- `arm.py`: detect helper + substitute-on-copy (.importlinter.ini, .dependency-cruiser.cjs) + report advisory + revert normalization.
- Gates: `arch_contract_python.py` 0-active-contracts detect+skip+distinct-note; `arch_contract_web.py` same if affected; Swift unchanged.
- Unchanged: `.golangci.yml`, `checkstyle.xml`, `clippy.toml`, `arch_contract_swift.py`.

## 5. Risks / mitigations

| Risk | Mitigation |
| --- | --- |
| root-package mis-detect | full-line verify-me comment ABOVE `root_package` (NOT inline — configparser); `__REPLACE_ME__` literal fallback + advisory. |
| substitution breaks `--revert` | normalize the root token before `_same_content`; any non-token diff = user-edited. |
| neutral layers silently remove protection | advisory + gate's DISTINCT 0-active note (rule 3); human opts IN. |
| gate change regresses active path | only adds a 0-active skip+note branch; N-active path unchanged. Covered by `arm_report_gates` + new unit case. |
| 0-active detection misses a config location | parse the RESOLVED config (`find_importlinter_config` → .importlinter.ini/setup.cfg/pyproject `[tool.importlinter]`), not just .importlinter.ini. |
| detection adds deps | pure-stdlib; arm.py stays stdlib. |

## 6. Out of scope

- A general templating engine (one-token substitution).
- Auto-detecting the user's layer decomposition (impossible — their architecture).

## 7. Definition of done (Phase A)

- 3 templates neutral-by-default; arm substitutes detected root (literal `__REPLACE_ME__` fallback +
  full-line verify comment); Swift scan-all + custom_rules commented; .dependency-cruiser keeps no-circular.
- `arch_contract_python.py` skips lint-imports + emits a distinct 0-active-contracts note (resolved-config parse); web same if affected.
- arm report per-config placeholder advisory.
- Freshly-armed Python project (no `app`, lint-imports installed) = **green + honest** gate (0-active note, not red, not misleading "checked").
- `--revert` normalizes the root token (widened matches-template).
- ADR (rule 6): "placeholder arch-configs = green-by-default neutral + auto-detected root + layering human opt-in + gate 0-active detect/skip/note."
- Existing arm self-gates green + new coverage for `detect_root_package` + the 0-active gate branch.
