# sf-hetero — a dedicated different-family leg tool (proposal)

> Status: **PROPOSAL — csr-converged (substantive_converged: true, 2 rounds, record:
> [sf-hetero.convergence-record.json](sf-hetero.convergence-record.json), trail:
> [sf-hetero.convergence.md](sf-hetero.convergence.md)) and IMPLEMENTED 2026-08-29.** Authority: self-contained —
> verify internal consistency AND the repo files it cites. Sibling landing record: the 2026-08-29
> live-progress increment (PORTING-PLAN.md "csr live-progress disclosure" addendum) landed L1/L2;
> THIS proposal is the third layer.

## 1. Problem — what the bash-invoked wrapper still costs

The different-family leg is today invoked through pi's built-in `bash` tool
(SKILL.md step 2). The 2026-08-29 increment made that path LIVE (stderr streams into the
running tool panel), but three residual defects remain, all structural to bash:

- **P1 — merged streams reach the LLM.** pi's bash tool merges child stdout AND stderr into one
  accumulator (`dist/core/tools/bash.js`: `child.stdout?.on("data", onData)` +
  `child.stderr?.on("data", onData)`), and the accumulated text is the tool RESULT the orchestrator
  model reads. So every `leg-progress` / `hetero-heartbeat` line pollutes the orchestrator's context,
  and locating the result JSON rests on the SKILL.md convention "parse the LAST JSON object" — a
  prose contract the model can misapply under a long heartbeat tail.
- **P2 — no structured live panel.** The bash panel renders raw JSONL lines (collapsed preview =
  last few visual lines). The DATA is all there — heartbeats carry the resolved model, turn lines
  carry cost — but there is no per-provider AGGREGATION (multi-provider runs are sequential —
  `hetero_doc_review.py` main loops `for name in provider_names` — and phase transitions between
  providers are indistinguishable in a line tail), no derived per-provider model/turn-count/cost
  line, no idle-vs-elapsed distinction.
- **P3 — undifferentiated failure surface.** The wrapper's exit contract is 0 = usable result
  (pass OR rewrite-due-to-blocker OR degraded — a degraded provider contributes 0 findings and the
  verdict comes from the rest; `main()` returns `1 if any_malform else 0`), 1 = malformation
  (including pre-leg fail-fasts like a missing token, which `sys.exit("error: ...")` with EMPTY
  stdout and the cause on stderr), 2 = argument/IO error. Bash collapses all of these into
  `Command exited with code N` + text; the orchestrator must re-derive semantics.

## 2. Design — the `hetero_doc_review` extension tool

A new bundled extension `extensions/sf-hetero/` registering ONE tool, `hetero_doc_review`. It is a
**client of the wrapper** — the wrapper CLI (`hetero_doc_review.py`) stays the single substrate
contract, UNCHANGED (no flag is added or repurposed by this proposal).

**Spawn.** `spawn("python3", [<skill-dir>/infra/scripts/hetero_doc_review.py, ...])` with
`detached: true` (own process group), cwd = the session cwd (the wrapper self-loads
`<cwd>/.env.solidforge` — unchanged), env inherited. `<skill-dir>` resolves from the extension's own
location (`extensions/sf-hetero/ → ../../skills/cross-source-review/`), the same package-relative
resolution the wrapper uses for sf-providers — the wrapper's `_sf_providers_dir` climbs FIVE
dirnames from `<pkg>/skills/cross-source-review/infra/scripts/`; the extension climbs from
`<pkg>/extensions/sf-hetero/` — same PRINCIPLE (package-relative self-location), different depth). On abort (the `signal` pi passes
to every tool), kill the process GROUP with an EXPLICIT `SIGKILL`
(`process.kill(-pgid, "SIGKILL")`) so the wrapper AND its grandchild `pi` die together — the
grandchild inherits the wrapper's process group (the wrapper's `subprocess.Popen` sets no
`start_new_session`/`preexec_fn`, so the `pi` child — and anything it spawns without creating its
own session — stays in the killed group) — **exact parity with the bash tool's existing
`killProcessTree` POSIX branch (which sends `SIGKILL`, not the Node default `SIGTERM`) — not a
claimed improvement**; it is stated here because the tool, not bash, now owns the kill.

**Stream separation (fixes P1).** stdout and stderr are read on SEPARATE pipes:
- stdout accumulates silently and is returned VERBATIM as the tool's `content` **on the
  usable-result path (exit 0)** — the single result JSON the wrapper prints on exit
  (`main()` ends with `print(json.dumps(result ...))`).
- stderr is parsed line-by-line as progress events — the wrapper's documented stderr surface:
  `{"type":"leg-progress",...}` (per grandchild tool call + per turn) and
  `{"type":"hetero-heartbeat",...}` (every 30s). Progress NEVER enters `content`. **Non-progress
  stderr lines** (the wrapper's own plain-text warnings, e.g. `warn: prior-findings file not found`;
  `warning: progress file unwritable`) are collected into a bounded `stderrTail` shown in the
  expanded render, NEVER in `content` on the exit-0 path (diagnostics, display-only; the exit-1/2
  paths already surface the tail per §2's completion semantics). Unparseable lines are treated the
  same way — display-only, never a parser failure.

**Live panel (fixes P2).** Each parsed stderr event updates a per-provider state map keyed by the
event's `provider` field (both event kinds carry it), then calls `onUpdate` with
`details.providers[]` — `{name, model?, elapsedS, turns, idleS, currentTool?, costUsd?, heartbeats}`
(and the partial `content` is a one-line placeholder in sf-subagents' `(running...)` pattern, e.g.
`hetero minimax · turn 3 · idle 4s` — populated fully only at completion) —
which `renderResult` draws as a compact panel (collapsed: one line per provider
`⏳ deepseek · deepseek-v4-flash · turn 3 · $0.0123 · idle 4s · → read docs/x.md`; expanded adds the
heartbeat history tail). Resolution sources: `model` from the first heartbeat that carries it;
`turns`/`currentTool` from `leg-progress` phases `turn`/`tool`; **`costUsd?` parsed from the
`leg-progress` turn line's `detail` text (`"turn N · $X.XXXX"` — the wrapper's only per-turn cost
surface on stderr; the heartbeat carries no cost field — and OPTIONAL because the wrapper omits
the `$` segment when cumulative cost is 0, e.g. catalog-unpriced routes like zai-coding-cn / qwen-
bailian)**; **`heartbeats` = the count of parsed
`hetero-heartbeat` events for that provider**; `idleS` recomputed at render from the
last event timestamp; a 5s ticker re-emits during silent stretches (same L1 pattern as
`sf-subagents`). Event granularity is the wrapper's EXISTING surface — this proposal adds NO new
wrapper event kind.

**Completion semantics (fixes P3).** exit 0 → parse stdout's last JSON object; if it parses, content
stays verbatim and `details.result` carries the parsed envelope IN FULL (all nine keys:
`verdict`, `degraded`, `degraded_providers`, `findings_count`, `findings`, `coverage`,
`malformation`, `providers`, `provider_runs`); `isError` is NOT set for `verdict:"rewrite"` (a blocker finding is a usable
result — the wrapper's own exit contract says so) nor for `degraded: true` (degrade is a
coverage-noted usable outcome, not a tool error). exit 1 → `isError: true`; content = the parsed
`malformation` fingerprint + stderr tail WHEN stdout parses, else stderr VERBATIM (the pre-leg
fail-fast shape: empty stdout, cause on stderr — never silent, rule 3). exit 2 → `isError: true`,
content = stderr tail. Non-UTF8 or unparsable stdout on exit 0 → `isError: true` with the raw tail (a
substrate regression must surface loudly, never mask).

## 3. Parameters

`artifact` (required, string — path/ref passed through), `authority` (optional, string),
`priorFindings` (optional, string — JSON or `@file`, passed to `--prior-findings`),
`roundIndex` (optional, int), `progressFile` (optional, string — passed to `--progress-file`;
SKILL.md keeps passing the run-dir sidecar), `profile` (optional, string — DISCOURAGED; the wrapper
resolves `HETERO_DOC_PROFILE`, and SKILL.md's "do NOT pass --profile" discipline carries over to the
tool's parameter description), `dryRun` (optional, bool — passes `--dry-run` for the offline e2e
gate). NOT exposed: budget/turns/bytes/timeout caps — the wrapper owns them from its own defaults
(timeout / max-turns / max-stream-bytes env-overridable via `HETERO_DOC_TIMEOUT` /
`HETERO_DOC_MAX_TURNS` / `HETERO_DOC_MAX_STREAM_BYTES`; `--budget-usd` has a hardcoded 12.0 default
with no env var), and duplicating cap knobs into the tool would fork the substrate contract.

## 4. SKILL.md step-2 rewrite

The different-family bullet switches its primary path from the bash invocation to the tool:
"invoke the `hetero_doc_review` tool with `artifact` / `authority` / `priorFindings` /
`progressFile: <run-dir>/progress.jsonl`". The three-view disclosure sentence is preserved and
sharpened: view (1) becomes the tool's own live panel (no longer "pi's bash tool streams stderr");
the `leg-progress` / `hetero-heartbeat` vocabulary, `--progress-file` wiring, and
`csr_progress.py status <run-dir> --watch 5` external view are unchanged, and the bash invocation
remains the DOCUMENTED FALLBACK for harnesses without the extension (non-interactive `pi -p` without
`-e`, plain shells). The `csr_progress_gates.py` check-9 assertions stay true against the rewritten
bullet (`--progress-file`, `leg-progress`, `csr_progress.py status`, no `run_in_background`), and
check 9 additionally asserts the bullet names the `hetero_doc_review` tool as the primary path with
the bash fallback retained.

## 5. Non-goals

- No cap/budget/degrade logic in the tool — the wrapper owns all breakers (ADR #41/#43/#52); the tool
  reports, never judges.
- No sidecar writes — `--progress-file` passes through; `csr_progress.py` vocabulary stays
  orchestrator+wrapper-owned.
- Not a general subprocess runner — one wrapper, one leg; nothing else routes through this tool.
- No same-family changes — `sf-subagents` L1 (landed) is complete for that leg.

## 6. Core claims (the convergence coverage prong checks these)

- **C1** — client-only: the tool spawns the wrapper with its EXISTING CLI surface; no wrapper
  behavior, flag, or event-kind change is required by this proposal.
- **C2** — stream separation on the usable-result path: when the wrapper exits 0, the
  orchestrator-visible `content` is its stdout verbatim; stderr progress lines are display-only and
  never enter LLM context. (The error paths deliberately diverge — exit-1 WITH parsable stdout →
  malformation fingerprint + stderr tail; exit-1 with empty stdout → stderr verbatim; exit-2 →
  stderr tail — the rule-3 never-silent exception, stated in §2.)
- **C3** — abort tree-kill parity (POSIX): on non-win32 the tool kills the wrapper's detached
  process group with `process.kill(-pgid, "SIGKILL")`, matching (not exceeding) the bash tool's
  existing `killProcessTree` POSIX branch (also `SIGKILL`); win32 is out of scope for this
  substrate's testing surface (the package's dogfooded substrate requires `python3` CLIs on
  `$PATH`; win32 parity is untested and unstated).
- **C4** — the live panel derives solely from the wrapper's documented stderr events
  (`leg-progress` + `hetero-heartbeat`); no new event kind, no stdout peeking mid-run. KNOWN DERIVED
  LIMIT (stated, not hidden): stderr carries NO provider-END signal (`hetero-leg-end` is
  sidecar-only), so mid-run the panel marks the most-recently-active provider as current; a
  multi-provider run's earlier providers show as "seen" with their last state, and their final
  outcomes arrive only in the completion envelope. No gap-detection heuristic, no sidecar reads.
- **C5** — offline testability: `dryRun` passes the wrapper's `--dry-run` (canned doc-findings, no
  model call), enabling an end-to-end tool gate without credentials.
- **C6** — the SKILL.md disclosure contract survives the step-2 rewrite intact (gate check 9 green,
  extended with the tool-primary assertion).

## 7. Testing and landing steps

Registration is an explicit landing step: `package.json` → `pi.extensions` gains
`./extensions/sf-hetero` (the extension is inert without it), and the e2e below loads it via `-e`.
Typecheck: generate a TEMP `tsconfig` covering `extensions/sf-hetero/index.ts` with `paths` mapping
the `@earendil-works/*` bare imports to the installed pi package's type roots (the pattern used for
`sf-subagents`/`sf-progress` during the 2026-08-29 increment — a /tmp-generated config, not a
committed repo convention), then `tsc --noEmit`. Offline e2e: `pi --mode json -p` with the extension
loaded, prompting a `dryRun` invocation, asserting the tool result carries the canned doc-findings
verbatim and NO stderr line in content. The full csr gate suite re-runs green after the SKILL.md
rewrite (check 9 extended as §4 states).
