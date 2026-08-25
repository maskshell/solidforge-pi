# External-Skill Integration into the Convergence Loop

- Status: Design (not yet implemented). Build plan recorded below.
- Date: 2026-06-24 (rev7: PIVOT → Impeccable; rev8: review fixes; rev9: detect --json schema resolved — open item closed).
- Scope: `skills/parallel-development/`. First registered instance: **Impeccable** (`pbakaus/impeccable`).

## Terminology & Disambiguation (two layers)

The word `design` is overloaded: software-architecture design is a different concept from frontend/visual design. This skill already uses `design` in the architecture/engineering sense (`convergent-loop.md` "design intent" = architecture intent; `role-agent-mapping.md` "Design system architecture" / "system design" = the `architect` role's triggers; `design-decisions.md` = the ADR log). Two distinct problems, both addressed:

- Layer 1 — canonical MACHINE identifiers (verdict, domain, reviewer line, test). MUST be unambiguous bare tokens. The visual concept uses `visual` internally (e.g. `visual-drift`, `domain: visual`, "visual line", `visual_ref` pointer). NOTE: the concrete design artifact is Impeccable's `DESIGN.md` — an external filename consumed by name (like `package.json`), NOT renamed.
- Layer 2 — human-facing vocabulary. Humans overload "design". Solved by context-based disambiguation at the user boundary, NOT by forcing humans to type a canonical term.

### Layer 2 — `design` disambiguation at the user boundary (three-role routing)

Bare "design" already routes to `architect` via existing triggers ("design architecture", "how to design", "system design"). That default is KEPT unchanged. With Impeccable, "design" is a fork into THREE routes:

| cues lean | route to | domain |
| --- | --- | --- |
| system / module / layer / service / data flow / API contract / "system design" / "design architecture" | `architect` (unchanged default) | software-architecture design |
| UI / page / screen / color / theme / token / layout / mockup / "design the UI" / "visual design" / "design tokens" | `/impeccable` (init / shape / critique / polish …) | UI/UX design (produces + governs DESIGN.md) |
| "build" / "implement" / React/Vue components (colloquial "design the frontend" = code it) | `frontend-developer` | frontend development (implements) |

Disambiguation protocol (advisory, rule 4; "restate plus correctable", never a hard block): detect "design" → score context (subject nouns, scope, active artifact, prior turn) → clear lean: route and inline-restate → genuinely ambiguous AND consequential: one cheap confirm → low-stakes: dominant cue and state assumption.

## Context

`parallel-development` converges on a frozen **Intent Blueprint** via a dual ring (inner deterministic gates + outer `code-reviewer`). It has NO runtime skill-to-skill collaboration mechanism today.

**The pivot (rev7).** The earlier design used Anthropic's `/frontend-design` (a demo skill — useful as a reference, uncertain broad production readiness) as the exemplar, and hand-rolled a parallel design artifact (`*.visual.md`), design gate (`arch_contract_visual.py` heuristics), and a wrapper subagent (`uiux-designer`). **Impeccable** (`pbakaus/impeccable`) is frontend-design's mature evolution AND a complete design-governance system:

- 1 skill, **23 commands** (`init`, `shape`, `craft`, `critique`, `audit`, `polish`, `extract`, …).
- a **44-rule deterministic detector** (`detect.mjs`, no LLM/network) + a **provider-native PostToolUse hook** that runs the detector on direct UI edits.
- `PRODUCT.md` + **`DESIGN.md`** artifacts (audience, brand/product lane, colors, type, components, anti-references) that every command reads.
- its own **`asset-producer` subagent**.

Impeccable ALREADY provides the artifact + gate + review we hand-designed — and a stronger gate (44 real deterministic rules vs token-presence heuristics). So the integration **LEVERAGES Impeccable's machinery** rather than reinventing a weaker parallel gate (which would also clash with Impeccable's own PostToolUse hook on the same edits).

## Goal and non-goals

- Goal: integrate Impeccable into the convergence loop across the four existing seams — its `DESIGN.md` as the frozen anchor, its detector/hook as the design gate, its commands mapped to the seams — with the loop adding convergence discipline (freeze / gate-orchestration / review).
- Non-goal: bundle, fork, or reimplement Impeccable. It is a black box (`npx impeccable install`); the contract is artifact+invocation based.

## Drop / keep / add (vs the superseded rev1–rev6 design)

- DROP: `*.visual.md` artifact (use Impeccable `DESIGN.md`); `arch_contract_visual.py` heuristics (use Impeccable's 44-rule detector + hook); `uiux-designer` subagent (use Impeccable's `asset-producer` + `/impeccable` commands); `smoke_visual`; `visual-blueprint.template.md`.
- KEEP: the four-seam model; the frozen-anchor concept (`blueprint_guard`, a `design` anchor kind for `DESIGN.md`); the reviewer visual line; the convergence discipline; Fork 3 opt-in-strict (`visual-drift`); Fork 5 (fold into outer-verdict); the two-layer terminology.
- ADD: `npx impeccable install` as the design-gate arming step; the command→seam map; hook-as-gate; `DESIGN.md` freeze semantics (side-car sentinel); `critique`-score consumption in Seam D.

## Resolved integration facts (researched from the Impeccable repo)

- **detector** — `node skill/scripts/detect.mjs --json <targets>`: local, no LLM, no network. `npx impeccable detect --json` is the CLI equivalent. SCHEMA (rev9, read `cli/engine/cli/main.mjs`): a BARE JSON ARRAY of findings, each `{antipattern, name, description, severity, file, line, snippet}` (VERIFIED empirically — `severity` IS present, e.g. `"warning"`; `name` is the human rule name; `line` may be null for file-level findings); empty → `[]`; exit 2 (findings present) / 0 (none). The detector ALSO loads the local `DESIGN.md` / `design.json` as context by default (`--no-design-system` skips) — it already cross-checks against the design system. Maps to 越权日志 via a thin adapter: wrap the array into `{gate:"impeccable-detect", passed:true, coverage, findings[]}`; `antipattern → rule`, `file → file`, `line → line ?? 0`, `description → detail`; INHERIT `severity` (the source carries it — do NOT overwrite); optionally synthesize `suggestion` from the rule name → the matching `/impeccable` command. GAP (rule 3): no `suggestion` in source (adapter synthesizes / omits); some findings are file-level (no line → 0); exit 2 means "findings present", not a blocker.
- **hook (Claude Code)** — PostToolUse entry in `.claude/settings.local.json` (machine-local, gitignored) → `hook.mjs`; runs the detector on direct UI file edits and surfaces findings as system reminders (advisory, post-edit). Cursor blocks pre-write. **Coexists naturally with `fast_gate.py`** — design vs correctness, both PostToolUse, complementary (not conflicting).
- **DESIGN.md / PRODUCT.md** — written by `init` / `document` / `extract`; read by all commands; living by default. `DESIGN.md`'s frontmatter is a **machine-readable token export** (`colors` / `typography` / `spacing` / `components` in YAML) — `frontend-developer` consumes structured tokens directly, and the convergence `detect` sweep can cross-check CSS against declared tokens (a payoff of dropping the hand-rolled `*.visual.md`). The loop FREEZES `DESIGN.md` at Phase 0 via a SIDE-CAR sentinel (see Seam A / Fork 4) — NOT via frontmatter `status`, which `DESIGN.md` does not carry. `PRODUCT.md` (audience / brand-lane) is setup context, NOT frozen. Impeccable's design-evolution commands (`extract` / `document`) are pre-Phase-0 setup, not mid-loop.
- **subagent** — Impeccable ships `skill/agents/impeccable-asset-producer.md`, so a wrapper `uiux-designer` is redundant.

## The four seams (Impeccable leverage)

The four seams already exist in the loop; Impeccable operates each:

- **Seam A — artifact producer.** `/impeccable init` + `document` + `extract` + `shape` (and the Impeccable `asset-producer` subagent) produce `PRODUCT.md` + `DESIGN.md`. The loop freezes `DESIGN.md` at Phase 0 → the convergence anchor. FREEZE MECHANISM: a SIDE-CAR sentinel the loop controls (a loop-state flag or a `.design.frozen` marker), NOT frontmatter `status` — `DESIGN.md`'s frontmatter is an Impeccable token-export with no `status` field, so `blueprint_guard`'s frontmatter-`status` check would not fire. The `design` anchor kind in `blueprint_guard` recognizes `**/DESIGN.md` and denies edits while the sentinel is set (set at Phase 0, cleared at converge). A `visual_ref` pointer (DESIGN.md path) in the Intent Blueprint carries its tokens/components/a11y into the NFR.
- **Seam B — design gate.** Impeccable's PostToolUse design hook = the per-edit design gate (advisory; auto-installed). PLUS an optional convergence-point sweep: run `detect.mjs --json` and translate to 越权日志 via the thin adapter in "Resolved integration facts" (the `--json` output is a bare array; the adapter wraps it, maps `antipattern → rule` / `line → line ?? 0`, assigns `severity:"warning"`). No hand-rolled heuristics — the 44 real rules replace them.
- **Seam C — implementation.** `frontend-developer` (modified: faithful `DESIGN.md` consumption, no component-library-default substitution) implements at Phase 1 under the existing gates — an INDEPENDENT implementer, so the visual-fidelity check is not reflexive. Use `/impeccable shape` (design plan, Seam A) + `frontend-developer` (impl); do NOT use `/impeccable craft` in-loop — `craft` is shape→build (the designer builds → reflexive gate), so reserve it for standalone non-loop use. `polish` / `bolder` / `quieter` / `animate` (refinement of EXISTING code) are fine as gated ops.
- **Seam D — review.** The outer-ring reviewer's visual line is AUGMENTED by `/impeccable critique` (heuristic scoring, stored) and `audit` (technical quality). `visual-drift` verdict + Fork 3 opt-in-strict unchanged.

### Code-gen handling (independent implementer; `craft` reserved)

The visual-fidelity check needs an INDEPENDENT implementer (else it is reflexive — the designer won't drop their own tokens). So `frontend-developer` implements; Impeccable's design commands produce the spec. CAVEAT: `/impeccable craft` is shape→build — it conflates design + implementation, which would make the check reflexive, so the loop uses `shape` (Seam A) + `frontend-developer` (Seam C) and reserves `craft` for standalone non-loop use. The aesthetic-EXECUTION know-how rides on Impeccable's own `polish` / `critique` commands (gated refinement of existing code), so there is no need to hand-extract execution patterns into `references/agent-patterns/frontend-developer.md`. `frontend-developer` only needs the faithful-DESIGN.md clause.

## Decided design (the contract)

Doc-only for v1: a reference doc + ADR IS the registry; no `infra/external-skills.json` (Fork 1 — the orphan-check `disconnect_check.py:289-290` enforces reachability). Impeccable is declared as one row in `references/external-skills.md`:

| Field | Impeccable value |
| --- | --- |
| `skill_ref` | `impeccable` (`pbakaus/impeccable`, installed via `npx impeccable install`) |
| `skill_domain` | UI/UX (visual) design governance — artifact + deterministic gate + review commands |
| `artifact` | `DESIGN.md` (+ `PRODUCT.md`); DESIGN.md frozen at Phase 0 via side-car sentinel |
| `artifact_consumption` | NFR (visual-AC) + a `visual_ref` pointer in the Intent Blueprint |
| `design_gate` | Impeccable 44-rule detector: PostToolUse hook (per-edit advisory) + convergence `detect.mjs --json` sweep (越权日志) |
| `implementer_role` | `solidforge:frontend-developer` (modified: faithful DESIGN.md consumption, no library-default substitution) |
| `review_augment` | `/impeccable critique` (scored) + `audit` |
| `maturity_tier` | the 44 rules are deterministic; on Claude Code the hook SURFACES them advisory (post-edit reminders, non-blocking — only Cursor blocks pre-write); the loop treats design findings advisory by default (Fork 3), opt-in strict |
| `coverage_gap` | visual fidelity beyond the 44 rules + runtime a11y → outer-ring (`critique` / `audit`) |

### Decided forks

- Fork 1 — registry vs doc-only → doc-only.
- Fork 2 — dispatch role → LEVERAGE Impeccable: no wrapper subagent (use Impeccable's `asset-producer` and `/impeccable` commands for design production); `frontend-developer` (modified) implements. (Supersedes the rev4 `uiux-designer` decision.)
- Fork 3 — visual-drift severity → default advisory rewrite; opt-in `enforcement: strict` → hard rollback. On Claude Code the hook is advisory (post-edit), so strict-rollback is an orchestrator action on `critique`/`detect` findings. `enforcement` is orchestrator-interpreted (no hook validates it; the freeze sentinel is loop-controlled, not frontmatter).
- Fork 4 — artifact guard → ride `blueprint_guard.py` as a `design` anchor kind for `DESIGN.md`, but the freeze signal is a SIDE-CAR sentinel (loop-state flag / `.design.frozen`), NOT frontmatter `status` — `DESIGN.md` is Impeccable-owned and its frontmatter is a token-export with no `status` field. First anchor whose freeze signal is not its own frontmatter (ADR #21).
- Fork 5 — run-record → fold `visual-drift` into the outer-verdict enum (schema + `loop_state.py`).
- Fork 6 — leverage vs reinvent → LEVERAGE Impeccable's artifact/gate/review (the pivot).

## Honest open items (rule 3 — confirm at build)

- Convergence `detect` sweep: translate to 越权日志 (unified output for run-record + reviewer) recommended; per-edit hook stays native (Impeccable system-reminders).
- Side-car freeze sentinel: decide the concrete form (loop-state flag vs `.design.frozen` file) at build; both decouple the freeze from DESIGN.md's Impeccable-owned frontmatter and survive an Impeccable `document`/`extract` regen.

## File-by-file build plan (deferred implementation)

Skill root is `skills/parallel-development/`. Every change mirrors the nearest exemplar (rule 7); the enumeration sweep (rule 5) covers the ripple.

- **Arming** — document `npx impeccable install` as the design-gate arming step (the hook lands in `.claude/settings.local.json`). Parallel to `/solidforge:arm-tools --with-tools`.
- `infra/hooks/blueprint_guard.py` — add a `design` anchor kind for `DESIGN.md` (`DESIGN_RE`, a `"design"` branch in `anchor_kind()`), but the freeze check reads a SIDE-CAR sentinel (loop-state flag or `.design.frozen`), NOT frontmatter `status` (`DESIGN.md`'s frontmatter is an Impeccable token-export with no `status`). Deny message → Blueprint Revision Channel. Set the sentinel at Phase 0; clear at converge.
- `agents/frontend-developer.agent.md` — conditional faithful-DESIGN.md-consumption clause: derive all visual tokens from a frozen `DESIGN.md`; do NOT substitute component-library defaults (Shadcn/AntD/Element Plus/Naive UI). Plain React/Vue dev with no spec is unaffected.
- `references/role-agent-mapping.md` — route "design the UI / visual / design tokens" → `/impeccable` (directly or via its `asset-producer` subagent; NOT a wrapper subagent). The three-role `design` fork note (architect / `/impeccable` / frontend-developer).
- `references/convergent-loop.md` — Seam D: augment the visual line with `/impeccable critique` (scored) + `audit`; add the `visual-drift` verdict + opt-in-strict dispatch. Seam B: note the Impeccable PostToolUse hook as the per-edit design gate (coexists with `fast_gate.py`).
- `references/intent-blueprint.md` — a `visual_ref` pointer (DESIGN.md path) as an authoritative reference; read-only cross-ref (same `blueprint_guard`, anchor kind `design`, side-car sentinel).
- `references/scope.md` — authoring a visual design stays out of scope (route to `/impeccable`); a FROZEN `DESIGN.md` is an in-scope authoritative reference.
- NEW `references/external-skills.md` (the contract doc) — Impeccable: `DESIGN.md` anchor (side-car freeze); detect/hook gate; command→seam map (shape for design, NOT craft in-loop); the install/ arming step; honest coverage gap.
- `references/design-decisions.md` — ADR #21: the pivot (frontend-design → Impeccable), the leverage decision, hook-coexistence finding, the `DESIGN.md` freeze wrinkle (first anchor whose freeze signal is NOT its own frontmatter — DESIGN.md is Impeccable-owned; use a side-car sentinel), and the `craft`-reflexivity caveat (use `shape` + frontend-developer, not `craft`, in-loop). Rejected: a parallel hand-rolled gate (weaker + clashes with Impeccable's hook); a `uiux-designer` wrapper (redundant with Impeccable's `asset-producer`); frontmatter-`status` freeze for DESIGN.md (won't fire — no `status` field); `/impeccable craft` in-loop (reflexive).
- `references/golden-paths.md` — add `visual` to the domain enum.
- Run-record (Fork 5): `infra/schemas/run-record.schema.json` + `loop_state.py` `record-outer` choices add `"visual-drift"` (both together; enum value, no validator change).
- `SKILL.md` — Reference Files list; design-gate bullet (Impeccable hook); Layer table L3 row gains `external-skills.md`; Scope Guard note.
- NO `arch_contract_visual.py`, NO `smoke_visual`, NO `*.visual.md` template, NO `uiux-designer.agent.md`.

## Reused utilities / exemplars (do not re-implement)

- `infra/hooks/blueprint_guard.py` — extend (multi-kind `anchor_kind()`) for `DESIGN.md` (side-car freeze).
- `loop_state.py` `record-outer` / `mark-rollback` — reuse for `visual-drift` + opt-in rollback.
- Impeccable's own `detect.mjs` / hook / `asset-producer` / commands — the design engine (do not reimplement).
- `agents/backend-developer.agent.md` — convention model (only if any new agent is ever needed; under leverage, none is).

## Verification (definition of done for the deferred build — rule 1)

This turn: NONE (only `docs/` changes; `disconnect_check.py` does not scan `docs/`). When the build runs, the full self-gate set from `CLAUDE.md:18-27` must be green:

```bash
python3 skills/parallel-development/infra/test/disconnect_check.py    # orphan-check reaches external-skills.md; loading-chain green
python3 skills/parallel-development/infra/test/plugin_layout.py       # manifest + hooks + agents well-formed
python3 skills/parallel-development/infra/test/run_record.py          # passes after adding "visual-drift" (schema + loop_state.py) + the existing fast_gate / arch_contract / arm / smoke suites unchanged
```

NEW detect-integration smoke (build): run `detect.mjs --json` on a fixture UI file with a known anti-pattern → assert the adapter: the finding's `antipattern` → `rule`, `file` → `file`, `line` → `line ?? 0`, `description` → `detail`, an assigned `severity:"warning"`, wrapped into `{gate:"impeccable-detect", passed:true, coverage, findings[]}`. Arming: assert `npx impeccable install` wrote the `.claude/settings.local.json` PostToolUse entry. Side-car freeze: assert `blueprint_guard` denies a DESIGN.md edit while the sentinel is set, allows it when cleared.

End-to-end (manual): `/impeccable init` → frozen `DESIGN.md` (sentinel set) → `frontend-developer` implements → hook surfaces design findings post-edit → convergence `detect` sweep → `/impeccable critique` → `visual-drift` dispatch (advisory rewrite; `enforcement: strict` → hard rollback).

### Honest coverage gaps (rule 3)

- Visual fidelity beyond the 44 deterministic rules (does the rendered UI match the design intent pixel-for-pixel?) is NOT enforced — outer-ring (the visual line + `critique`).
- Runtime a11y (screen-reader, keyboard nav) is `/impeccable audit` + outer-ring/test-gate, not the detector.
- The detector is a far stronger codable gate than the presence-heuristics it replaces, but it is still not full visual-fidelity enforcement.

## Build sequencing (deferred)

1. ADR #21 (pivot + leverage + freeze wrinkle + craft caveat) + new `external-skills.md`.
2. `blueprint_guard.py` `DESIGN.md` anchor (side-car sentinel freeze).
3. `frontend-developer.agent.md` faithful-DESIGN.md clause.
4. `convergent-loop.md` Seam D (critique/audit + visual-drift + opt-in-strict) + Seam B hook note.
5. `role-agent-mapping.md` (`/impeccable` routing + three-role fork).
6. Enumeration sweep (rule 5): `intent-blueprint.md`, `scope.md`, `arch-contracts.md`, `install.md`, `maturity.md`, `README.md`, `extending.md`, `golden-paths.md`, `SKILL.md`.
7. Document `npx impeccable install` as the arming step.
8. Full self-gate run + detect-integration smoke + side-car-freeze test.

## Permanent gap (not a defect)

Visual fidelity is never fully deterministically enforceable — an honest outer-ring concern by design (rule 4). The mechanism closes the codable gap with Impeccable's 44 deterministic rules (a real, maintained, no-LLM gate) and defers the uncodable gap to the reviewer visual line + `/impeccable critique`. Stricter teams opt in via `enforcement: strict` (hard rollback on drift).
