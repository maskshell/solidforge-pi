# csr convergence-record — arm placeholder arch-config fix

- artifact: `docs/arm-placeholder-config-fix.proposal.md`
- size tier: short (cap 2)
- authority: self-contained (code-behavior claims, verified against `arm.py` / gate source — no external citation authority)
- rounds: 2
- `substantive_converged`: **true** (process-axis; core claims coverage-verified AND no new Blocker in round 2)
- `rightness`: human_confirm_required (outcome-axis — whether this is the right fix stays human)

## Findings trend

- **r1 same-family** (solidforge:doc-reviewer): 2 blockers + 2 warnings — all adopted after independent source-verification.
  - B1: ARCH_CONFIGS = 6 (Go `.golangci.yml` omitted) → fixed "3 of 6" + Go in unchanged.
  - B2: `check_import_linter` line 143 unconditional "checked" → fix scope expanded to a gate-side 0-active detect/skip/distinct-note.
  - W3: revert §3.4 "unchanged" contradiction → restated as widened matches-template.
  - W4: `.swiftlint.yml` is `included:[Sources,Tests]` → fixed.
- **r1 异源** (deepseek via hetero_doc_review.py, fed same-family as prior): 7 findings — all adopted after adjudication (异源-only → escalate).
  - configparser inline-comment blocker → verify-me note is a full-line comment, not inline; `__REPLACE_ME__` literal fallback.
  - skip lint-imports for 0-active; Swift `custom_rules` layer contracts also neutralized; `.dependency-cruiser.cjs` keeps universal `no-circular`; Swift scan-all (not Sources-detect); 0-active parse handles all config locations; revert mechanism specified (normalize token).
- **r2 same-family confirm**: 0 blockers, 1 advisory warning (0-active detection must be format-aware: INI `[importlinter:contract:…]` vs TOML `[[tool.importlinter.contracts]]`, + `find_importlinter_config` returns `"__auto__"` sentinel) → adopted into §3.3. Core claims coverage-verified. **Converged.**

## Coverage notes

- The 异源 leg went deeper into source than the same-family leg (the configparser inline-comment blocker is 异源-only) — the additive cross-family pass earned its cost this run.
- 异源 r1 `verdict: rewrite` (a blocker) was adjudicated + adopted, not silent-accepted; r2 confirmed resolution.
- web gate (`arch_contract_web.py`) found already-honest (count-based) by r2; no gate-side change needed there beyond verification.

## psv (Stage 2) — M=0, no admissible surface

The doc's claims are code-behavior (arm.py `shutil.copy2`, gate line 143, ARCH_CONFIGS count,
configparser semantics) verified against the SolidForge source by BOTH csr legs — they are NOT
citation claims against fetchable external primary sources. psv's admissible surface = 0 → psv
returns `no admissible surface` (escalate-to-human note). This is honest (rule 13: psv is optional
additive; a code-fix design doc is low-citation/interpretive → csr alone suffices). psv's value here
would be if the doc cited external specs (e.g. import-linter's docs on configparser behavior) — it
does not lean on such; the one external-adjacent claim (configparser no-inline-comments) is Python
stdlib semantics, not a fetchable-citation claim.
