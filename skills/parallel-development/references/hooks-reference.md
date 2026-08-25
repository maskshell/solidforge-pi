# Hooks Reference (Claude Code Hook Mechanics)

On-demand reference. The verified Claude Code Hook mechanics this skill's hooks rely on. Read before editing any file under `infra/hooks/`. Semantics were confirmed against `code.claude.com/docs/en/hooks`.

## How Claude Code runs hooks

Hooks are ordinary commands configured in `.claude/settings.json` under `hooks.<Event>`. They receive a JSON payload on stdin, run as a subprocess, and signal back via exit code and/or stdout JSON. They can read/write files freely (this is how `loop-state.json` persists).

| Mechanism | Verified behavior |
| --- | --- |
| PostToolUse (`matcher: "Edit\|Write"`) | Runs AFTER the tool executed. Cannot undo the edit. Exit 2 → stderr shown to Claude. Exit 0 + stdout JSON `{"decision":"block","reason":"..."}` → reason fed back, conversation continues. |
| PreToolUse (`matcher: "Edit\|Write"`) | Runs BEFORE the tool, can truly block. Exit 2 → call blocked, stderr to Claude. Exit 0 + JSON `{"hookSpecificOutput":{"hookEventName":"PreToolUse","permissionDecision":"deny"\|"allow"\|"ask","permissionDecisionReason":"..."}}`. |
| matcher | Regex over the tool name. `Edit\|Write` matches both. Optional `if:` adds a permission-rule sub-filter (e.g. `Write(*.blueprint.md)`). |
| stdin payload | JSON: `session_id`, `transcript_path`, `cwd`, `hook_event_name`, `tool_name`, `tool_input` (`file_path`; for Edit also `old_string`/`new_string`). |
| Settings scopes | `.claude/settings.json` (project, committed) > `.claude/settings.local.json` (project, gitignored) > `~/.claude/settings.json` (user, global). User-scoped fires for ALL projects — unacceptable for a distributed skill, so this skill installs project-scoped only. |
| `${CLAUDE_PROJECT_DIR}` | Env var for the project root, usable in a hook `command:` for portability. |

## The one unavoidable gap and its faithful alternative

PostToolUse cannot prevent an edit, only react to it. So "the fast gate blocks bad edits" is realized as: the hook runs the gate after the edit; on failure it emits `decision:block` + reason so Claude self-corrects on the next turn, and the orchestrator treats any block as "inner red — short-circuit, do not enter the outer ring". This preserves the spec's fast-fail semantics. PreToolUse (true pre-block) is reserved for where it is genuinely needed: the frozen-blueprint guard.

## Per-hook contract (what each script fulfills)

| Hook | Event | Mechanism | Contract |
| --- | --- | --- | --- |
| `fast_gate.py` | PostToolUse | `decision:block` on failure | per-file cheap lint/format; records fingerprint in loop-state; queries breaker; emits reason incl. the breaker action; the reason's remediation SPLITS by tool — lint failures (`ruff check`/`eslint`/`swift-format`) → fix-in-ring, format failures (`ruff format`/`google-java-format`/`gofmt`/`rustfmt`) → commit-stratification guidance ([commit-stratification.md](commit-stratification.md)) |
| `blueprint_guard.py` | PreToolUse | `permissionDecision:deny` | blocks Edit/Write to a `status:frozen` blueprint; the only legitimate change path is the revision channel |
| `counters.py` | PreToolUse | `permissionDecision:deny` when terminal | stops edits once loop-state is `suspended`/`hard_terminated`, so a stalled task cannot keep thrashing |

Shared library: `infra/hooks/lib/detect_toolchain.py` (`classify`, `resolve_tool`, `read_payload`, `emit_block`, `deny_block`, `loop_state_path`, `project_root`).

## How to test a hook

Pipe a JSON payload on stdin. A pass is silent (exit 0); a block prints the decision JSON.

```bash
echo '{"tool_name":"Edit","tool_input":{"file_path":"/abs/path/app/bad.py"}}' \
  | CLAUDE_PROJECT_DIR=/abs/path python3 infra/hooks/fast_gate.py
```

## Live verification (that hooks actually fire per-edit)

The stdin simulation above proves the hook LOGIC. To prove hooks FIRE in a real Claude Code process (project-scoped), run a headless session IN the project — its `.claude/settings.json` hooks load and execute:

```bash
cd <project-with-infra-installed>
pi -e <pkg>/extensions/sf-hooks -p --model <model> "<prompt that triggers the hook>"
```

Two conclusive checks (verified):

- **PreToolUse blueprint_guard**: ask it to edit a `status:frozen` blueprint. The guard denies; the model receives the denial reason and the file is unchanged (md5 identical before/after).
- **PostToolUse fast_gate**: ask it to add an unused `import` to a `.py` file. ruff catches F401; the hook emits `decision:block` and the model receives "fast gate hook is blocking because ruff detected … unused".

PI PORT: the sf-hooks extension bridges pi's `tool_call` event to the same PreToolUse guards — a deny still blocks the tool call before it executes (which is exactly how the guard stays authoritative). This method is deliberately NOT in `smoke_gates.py` (it spawns a full `claude -p` per check — too slow for the fast suite); run it manually when you change hook wiring.

For the full loop (settings wiring + install), see [install.md](install.md). For how the gates fit the convergence loop, see [convergent-loop.md](convergent-loop.md). For why the hooks are Python/stdlib and other non-obvious choices, see [design-decisions.md](design-decisions.md).
