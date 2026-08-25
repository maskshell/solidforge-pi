# psv FULL-M coverage-record (AUTHORITATIVE) — fast-gate-format-advisory-design.md

This is the ONLY authoritative `oracle_verified_under_known_coverage` record. The gate record (`fast-gate-format-advisory.psv-gate.md`) was explicitly non-authoritative.
NEVER `correctness_converged` — whether the design is RIGHT stays human (`rightness: human_confirm_required`).
Run: 2026-08-13, after csr substantive convergence (same-family, 4 rounds).

## Coverage disclosure

**oracle_verified_under_known_coverage = 10 verified / 0 refuted / 0 narrowed / 0 unverifiable of M = 10 external-fetchable claims (E1–E10).**

Extraction: independent `solidforge:claim-extractor` run (post-substrate-fix) — confirmed §8's cited surface (E1–E7) AND surfaced 3 additional uncited-but-load-bearing external claims (E8/E9/E10, the tool classifications), which were then fetched and verified. Atomicity: C5 split → E1–E4; C7 split → E6–E7; C6 → E5.

### Per-claim verdicts (oracle = FETCHED source text)

| id | claim (abridged) | verdict | adjudicating source (fetched) |
| --- | --- | --- | --- |
| E1 | g-j-f is whole-file formatter by default | verified | g-j-f README |
| E2 | `--dry-run --set-exit-if-changed` (no range flag) reports whole-file reformattal | verified | g-j-f README |
| E3 | g-j-f CLI supports range via `--lines`/`--offset` | verified | g-j-f README |
| E4 | `google-java-format-diff.py` reformats changed lines of a patch | verified | g-j-f README |
| E5 | Spotless `ratchetFrom` restricts formatting to files changed since a Git ref | verified | spotless main README + plugin-gradle `#ratchet` (deeper hop; see narrowing note) |
| E6 | PostToolUse gates via block/allow decision | verified | CC hooks docs |
| E7 | No built-in warn-level severity for PostToolUse | verified | CC hooks docs |
| E8 | swift-format `lint` = linter; `format` = formatter | verified | swift-format README |
| E9 | `ruff check` = lint ("primary entrypoint to the Ruff linter"); `ruff format` = formatter | verified | docs.astral.sh/ruff/linter |
| E10 | eslint = linter; gofmt/rustfmt/g-j-f = formatters | verified | eslint.org, pkg.go.dev/cmd/gofmt, rust-lang/rustfmt README, (g-j-f via E1 fetch) |

Verdict-method disclosure (rule 3): E1–E7 verdicted by independent `solidforge:claim-verifier` agents against fetched text passed inline. E8–E10 verdicted inline by the orchestrator against fetched quotes (trivially-decidable tool classifications; quotes recorded in the doc §8). The gate run (Phase 1) had done extraction+verdict inline due to the then-broken subagent substrate; the full-M re-ran both through the agents.

### Narrowing resolved (no finding survives)

- **E5/C6 was initially NARROWED** by the verifier (main README confirms "git ratcheting" but not the literal `ratchetFrom` keyword/semantics — they live in the linked `plugin-gradle#ratchet` section). Resolved by fetching the deeper hop: `ratchetFrom 'origin/main'` with "limit format enforcement to just the files changed by this feature branch" → **upgraded to verified**. Doc §8 updated to cite the deeper source.

### Doc revisions driven by the full-M

- §8: E8/E9/E10 tool-classification citations added (were uncited-but-load-bearing).
- §3: C4 reclassified Internal → Interpretive (the rule-4 text is internal; the "aligns with spirit" application is a value judgment).
- §2/C2/C3: citation-precision fixes (`infra/hooks/lib/detect_toolchain.py:113`; `emit()` defined at `arch_contract_api.py:74`, `:189` is an example finding).
- Not restructIVE → no csr re-convergence required (pipeline rule: re-converge only if restructured).

## Internal claims (NOT psv-external-admissible; recorded for audit)

I1–I14 (fast-gate behavior per language, emit_block-only surface, severity tier, snapshot-vs-commit cadence, `auto-per-stage` policy, install/convergent-loop descriptions) are verifiable-by-source-read and were source-verified across csr same-family rounds 1–4 plus the extractor's anchor verification. psv does not adjudicate them (no external fetchable source); their oracle is the repo source itself.

## Volatile-authority registry (re-fetchability signals)

- I1–I5 (current `fast_gate.py` behavior): VOLATILE — §6 lists `fast_gate.py` as a touch-point; this record describes the PRE-change behavior.
- I10 (install.md / convergent-loop.md "lint/format" descriptions): VOLATILE — rule-5 doc-audit will update them.
- E1–E10, I8, I9, I11–I13: non-volatile (external docs / stable infra surfaces).

## Interpretive claims (escalate to human)

- V1 (=C4): the rule-4-spirit application — value judgment.
- V2 (=C8): format-on-touch as dominant diff-inflation cause — folk knowledge, motivation-only.
- V3: Option C recommended / A fallback / B rejected — the proposal itself (outcome-axis: human).

## Extractor blind-spot caveat (rule 3)

Claims neither author nor extractor can see are absent from M; the N/R/W/K counts are conditional on what was extracted and compared, not a completeness guarantee. `verified` = the comparison found no contradiction in the fetched text, not a proof of none.
