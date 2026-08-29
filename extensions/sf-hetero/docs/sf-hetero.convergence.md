# sf-hetero proposal — convergence trail

> The proposal (`sf-hetero.proposal.md`) was itself reviewed by the cross-source-review loop it
> serves (dogfood). **substantive_converged: true, 2 rounds, cap 5** — both prongs passed
> (core-claims 6/6 coverage-verified; rounds 1–2 each 0 new Blockers). Record (audit-ready, schema
> `skills/cross-source-review/infra/schemas/convergence-record.schema.json`):
> [sf-hetero.convergence-record.json](sf-hetero.convergence-record.json). Live run dir (progress
> sidecar + wrapper stderr, gitignored): `workspace/cross-source-review/runs/<stamp>-sf-hetero-tool/`.

## Legs

| Round | Leg | Provider / model | Turns | Findings | Verdict |
| --- | --- | --- | --- | --- | --- |
| 1 | same-family (fresh-context `solidforge:doc-reviewer`) | zai-coding-cn / glm-5.3 | — | 7 (6 warning + 1 coverage) | pass |
| 1 | different-family (`hetero_doc_review.py`) | minimax-cn / MiniMax-M3 | 39 | 5 warning | pass |
| 2 | same-family | zai-coding-cn / glm-5.3 | 13 | 7 (5 warning + 2 coverage) | pass |
| 2 | different-family | minimax-cn / MiniMax-M3 | 21 | 6 (4 warning + 2 coverage) | pass |

## Escalated findings (different-family-only — human confirmation requested)

Per the reconcile table, different-family-only findings escalate to the human. Amendments were
drafted and applied in-round; confirmation is requested (veto = revert the corresponding proposal
hunk + the matching implementation):

- **sfh-d3** non-progress stderr lines: display-only `stderrTail`, never in exit-0 content (r1).
- **sfh-d4** `heartbeats` = count of parsed heartbeat events per provider (r1).
- **sfh-d5** abort kill = explicit `SIGKILL` on the process group, exact bash parity (r1).
- **panel-no-provider-end-signal** C4 known-derived-limit: no stderr provider-end signal; the panel
  marks the most-recently-active provider current; outcomes arrive at completion (r2).
- **c2-overclaims-exit12-composition** C2 parenthetical restated to match §2's exact branching (r2).
- **details-result-providers-omitted** `details.result` = the full nine-key envelope (r2).
- **onupdate-content-undefined** partial `content` = one-line running placeholder (sf-subagents
  pattern) (r2).
- **skilldir-resolution-conflation** "same principle, different depth" wording (r2).
- **kill-grandchild-assumption-unverified** pgroup-inheritance grounding (Popen sets no
  `start_new_session`) (r2).

Rejected (with rationale, recorded in the record's dispositions): sfh-d7 / tsconfig-precedent /
static-review-only (reviewer coverage disclosures, carried in coverage notes); sfh-d1/d2 (stale-prior
noise quoting pre-revision text).
