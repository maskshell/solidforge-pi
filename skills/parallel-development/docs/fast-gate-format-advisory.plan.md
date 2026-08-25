# Iteration Plan — Fast-Gate Format-Stratification (Option C)

Authority chain (master first):

1. `skills/parallel-development/docs/fast-gate-format-advisory-design.md` — the converged design (csr substantive_converged, same-family 4 rounds; psv full-M N=10/R=0/W=0/K=0)
2. `skills/parallel-development/docs/fast-gate-format-advisory.psv-full.md` — authoritative citation-coverage record
3. `skills/parallel-development/docs/fast-gate-format-advisory.convergence.md` — csr convergence trail

Conflict rule: the design doc wins; this plan defers to it.

Decision being implemented: **Option C (commit-stratified format)** — format STAYS a Blocker in the fast-gate; its remediation guidance changes from "inline-fix" to "stratify" (run the formatter, commit as a standalone `style:` commit, then redo the logic edit — C-pre canonical). Lint stays a Blocker with unchanged guidance. Option A (advisory demotion) is the documented fallback ONLY (no code this plan); Option B is rejected (precluded by C7 — no platform warn severity).

## 1. Complexity tiers

- fg-1 fast_gate guidance split — moderate (code + a NEW behavioral test; no existing test covers fast_gate)
- fg-2 protocol doc — light (new reference doc)
- fg-3..fg-7 doc enumerations (install / convergent-loop / extending / maturity / hooks-reference) — light each
- fg-8 ADR — light (writing)
- fg-9 facade assessment — light (advisory scan)
- fg-10 full self-gate suite — mechanical

## 2. Dependency edges

- fg-2 depends on fg-1 (the doc prescribes the behavior fg-1 implements)
- fg-3, fg-4, fg-5, fg-6, fg-7 each depend on fg-1 and fg-2 (they describe/enum the new behavior)
- fg-8 depends on fg-1 (ADR records the realized decision)
- fg-9 depends on fg-3, fg-4, fg-5, fg-6, fg-7 (facade scan after content settles)
- fg-10 depends on fg-1..fg-9

## 3. Per-iteration DoD

- **fg-1**: `fast_gate.py` distinguishes format-tool failures from lint-tool failures in the block guidance — format failures (ruff format / google-java-format / gofmt / rustfmt) get stratification guidance (C-pre: format → standalone `style:` commit → redo logic edit); lint failures (ruff check / eslint / swift-format lint) keep the existing fix-in-ring guidance. Detection, breaker wiring, and loop_state fingerprints unchanged. **Behavioral coverage (bc outer-ring novel-2 — no existing test invokes fast_gate):** add a test (extend `smoke_gates.py` or a sibling) that runs the fast-gate guidance branch on two fixtures — a lint-failing file and a format-failing file — and asserts the split guidance (format fixture → stratification wording; lint fixture → fix-in-ring wording); skips gracefully when the tools are absent (rule-1 skip convention). `disconnect_check.py` + `lint_self.py` green. NOTE (novel-6): the known fast-gate /tmp lint gap (dogfood gap #4) is ORTHOGONAL and stays OPEN — do not bundle a fix.
- **fg-2**: new `references/commit-stratification.md` (name may shorten) — prescribes C-pre canonical (detect → format-commit → logic-edit) + C-post fallback (split at per-stage commit); states the deterministic-detect vs heuristic-stratify split honestly (rule 3/4); records the per-mechanism authorization (novel-3): C-post splits the one per-stage commit into two at the same point; C-pre adds a NEW mid-stage `style:` commit point — an additional `auto-per-stage` extension, still not a rule-9 override; covers the INLINE-mode execution path (novel-4, ADR #39): when the orchestrator itself made the blocked edit, the orchestrator executes C-pre mid-loop, with ADR #39 bookkeeping (bump-iteration / gate-fail) still driven; records C-wholesale default + C-range pointers (g-j-f `--lines`/`google-java-format-diff.py`, Spotless `ratchetFrom`). Linked from `plan-driven-mode.md` §Commit policy + `fail-fast.md`.
- **fg-3**: `install.md` fast-gate row — split "lint/format" into lint (Blocker, fix-in-ring) + format (Blocker, commit-stratified remediation).
- **fg-4**: `convergent-loop.md` fast-gate description — same split; format failure guidance points to the protocol doc.
- **fg-5**: `extending.md` — per-language formula + strength tables record the lint-Blocker/format-stratified decision point; per-language rows corrected (format-emitting = Python/Java/Go/Rust; Swift/Web/Python = lint).
- **fg-6**: `maturity.md` — caveats record the split + the honest note that the stratify discipline is heuristic (model-executed, gate-nudged), detection deterministic; PLUS the Option-A coverage-gap clause (novel-5): under Option A, Java/Go/Rust would lose their ONLY fast-gate check — must be emitted as a coverage note, never silently greened (design §6 coverage note + §7 rule-3).
- **fg-7**: `hooks-reference.md` fast-gate row (line ~26, "per-file cheap lint/format") — same split as fg-3/fg-4; describes the changed emit-reason surface (bc outer-ring novel-1: this enumeration was missing from the design §6 list; rule 5 wins over the design's file list per the conflict rule).
- **fg-8**: `design-decisions.md` new ADR (next number, ≈#49) — Context/Decision/Why/Rejected per rule 6: C chosen, A fallback documented, B rejected (C7); the per-mechanism `auto-per-stage` authorization framing (C-post one→two at same point; C-pre new mid-stage point — neither a rule-9 override); heuristic-enforcement caveat; rejected alternatives from design §5. NOTE (novel-6): record explicitly that the fast-gate /tmp lint gap remains OPEN and out of this change.
- **fg-9**: facade scan (rule 5, advisory — never a Blocker): grep README/USER_GUIDE(.zh-CN) for fast-gate/format descriptions; update if they misdescribe the new behavior; record the sync decision either way.
- **fg-10**: full self-gate suite green (workspace rule 1): disconnect_check, smoke_gates (incl. the new fast-gate behavioral case), lint_self, arm_copy_config, arm_report_gates, arm_revert, plugin_layout, run_record, plan_queue_detect, hetero_review_wiring, drift_check, adapter_shape_check.

## 4. DAG

fg-1 → fg-2 → {fg-3, fg-4, fg-5, fg-6, fg-7} → fg-9; fg-1 → fg-8; all → fg-10.

## 5. Phase acceptance gates

- After fg-1: the new fast-gate behavioral test + disconnect_check + lint_self green.
- After fg-2..fg-7: drift_check green (rule-7 boilerplate drift advisory) + disconnect_check green (loading chain preserved — fg-2's links reachable).
- After fg-8..fg-9: doc-audit complete (rule 5 enumerations all updated or explicitly n/a — install, convergent-loop, extending, maturity, hooks-reference, README/USER_GUIDE facade).
- fg-10: the full suite = the definition of done for the whole plan.

## 6. Risks + mitigations

- smoke_gates asserts old guidance strings → update expectations in fg-1, not the gate semantics (never "delete the error" — L1).
- Stratification discipline is heuristic (model-executed) → the docs must NOT claim it as a deterministic gate (rule 3/4); the ADR records the caveat.
- fast-gate /tmp lint gap (known open dogfood gap #4) is ORTHOGONAL — do not silently bundle it; note it, leave it open.
- Doc drift: any "lint/format" prose left unsplit after fg-3..fg-6 → drift_check + fg-8 grep sweep.

## 7. Out of scope

- Option A implementation (advisory demotion at convergence; `arch_contract_*` warning finding) — documented fallback only.
- Option B (hook-helper `emit_advisory`) — rejected, precluded by C7.
- C-range per-language wiring (g-j-f `--lines` etc.) — pointers only in fg-2; actual wiring deferred until C-wholesale proves insufficient.
- The fast-gate /tmp lint gap; any lint-check additions for Java/Go/Rust.

## 8. Cross-cutting tasks

- Terminology: use exactly "lint" / "format" / "commit-stratification" / "C-pre" / "C-post" / "C-wholesale" / "C-range" (rule 10 — one term per concept; no C1/C2-style collisions).
- Every enumeration the capability touches must be updated (rule 5): install.md, convergent-loop.md, extending.md, maturity.md, design-decisions.md, README/USER_GUIDE facade (fg-8).

## 9. Facade impact assessment

- USER_GUIDE.md (EN + zh-CN): describes the convergence loop as "lint → architecture-contract → supply-chain → tests → AI review" — the loop SHAPE is unchanged (format stays Blocker); the remediation-behavior change is user-visible at the commit level (a `style:` commit may appear) → likely a small USER_GUIDE note, advisory judgment in fg-8.
- README.md (EN + zh-CN): mentions gates behavior — scan for format-as-blocker prose; update only if it misdescribes.
- GitHub About / marketplace description: no change expected (the pipeline shape is unchanged).

## 10. Open Decision Points — all RESOLVED (resolve-now)

- ODP-1 Option C vs A vs B → RESOLVED: C (design §4; csr-converged).
- ODP-2 C-pre vs C-post → RESOLVED: C-pre canonical, C-post documented fallback.
- ODP-3 C-wholesale vs C-range → RESOLVED: C-wholesale default; C-range deferred (out of scope §7).
