# SolidForge-pi

**SolidForge for the [Pi](https://github.com/earendil-works/pi-mono) coding agent** — the pi port of the [SolidForge](../solidforge) Claude Code plugin: a Loop Engineering system bundling the **converge → specify → implement** pipeline plus two additive **outcome-axis** layers (cited-source verification + uncited prior-art collision).

- **Skills (5)** — `cross-source-review`, `blueprint-crafting`, `parallel-development`, `primary-source-verification`, `prior-art-search` (invoke `/skill:<name>`)
- **Agents (22)** — plugin-scoped as `solidforge:<name>`, dispatched via the bundled `subagent` tool (isolated context; single / parallel / chain)
- **Guards** — the convergence-loop hooks (`blueprint_guard` / `counters` / `fast_gate`) bridged to pi's `tool_call` / `tool_result` events by the `sf-hooks` extension
- **Heterogeneous (异源) review substrate** — the different-family review legs spawn stateless `pi --mode json` subprocesses on provider routes **different** from the orchestrator's family, with wrapper-side budget/turn/bytes/wall-clock breakers (ADR #41/#43/#52 semantics preserved)

## Install

```bash
pi install git:github.com/<you>/solidforge-pi      # or: pi install ./solidforge-pi
```

Requires `python3` on `$PATH` (all gate/policy scripts are Python stdlib-only CLIs).

**Optional prerequisite — [pi-mcp-adapter](https://www.npmjs.com/package/pi-mcp-adapter)**, only for the Playwright E2E trio and Graphiti memory:

```bash
pi install npm:pi-mcp-adapter
# then configure the playwright-test server, e.g. in .mcp.json:
# { "mcpServers": { "playwright-test": { "command": "npx", "args": ["-y", "@playwright/test-mcp"] } } }
```

Without the adapter, the playwright agents fall back to the Playwright CLI (`npx playwright codegen|test`), and Graphiti memory ops degrade gracefully (the skill skips them).

## Arm a project (Layer 2)

Enabling the package does NOT mutate host-project build files. In a target project run:

```
/solidforge:arm-tools              # provision arch-configs + constitution + templates
/solidforge:arm-tools --with-tools # also add version-matched gate tools to dev deps
```

`arm.py` appends the L1 Constitution to the project's **AGENTS.md** (when present) or **CLAUDE.md** — pi loads either. Reversible: `arm.py --revert` (dry-run; `--apply` to execute).

## Heterogeneous review routes

Profiles are pi **catalog routes** (model facts catalog-inherited; the CC-era `[1M]` suffix is a context-window parameter and never appears in a pi model id):

| profile (alias) | route | model | credential |
|---|---|---|---|
| `zai-coding-cn` (`bigmodel`) | zai-coding-cn — GLM coding endpoint, openai-completions | `glm-5.3` | pi `auth.json` (default provider) or `ZAI_CODING_CN_API_KEY` |
| `deepseek` | deepseek — native endpoint | `deepseek-v4-flash` | `DEEPSEEK_API_KEY` ← bridged from `DEEPSEEK_ANTHROPIC_AUTH_TOKEN` |
| `minimax-cn` (`minimax`) | minimax-cn — anthropic endpoint | `MiniMax-M3` | `MINIMAX_CN_API_KEY` ← bridged from `MINIMAX_ANTHROPIC_AUTH_TOKEN` |
| `qwen-bailian` (`qwen3`) | **custom route** (pi catalog has only token-plan subscription qwen routes; Bailian pay-per-use key registered by `sf-providers` when present) | `qwen3.8-max` | `QWEN3_ANTHROPIC_AUTH_TOKEN` (the DashScope pay-per-use key) |
| `qwen-token-plan-cn` | qwen-token-plan-cn — token-plan subscription | `qwen3.8-max` | `QWEN_TOKEN_PLAN_CN_API_KEY` |

Put tokens in the target project's `.env.solidforge` (shell env wins; `arm-tools` provisions the `.env.solidforge.example` placeholder). Select legs via `HETERO_DOC_PROFILE` / `HETERO_PROFILE` (comma-list = multi-different-family). CC-era profile names (`bigmodel`, `minimax`, `qwen3`) keep working via aliases.

**Budget/cost note**: routes with catalog pricing (deepseek, minimax-cn) feed real `usage.cost.total` into the wrapper-side budget breaker; zai-coding-cn and qwen-bailian report cost 0 (unknown to the catalog) — the budget cap is inert there, wall-clock/turns/bytes caps still apply.

## CI / non-interactive subprocesses

The `subagent` tool and the hetero wrappers spawn `pi --mode json -p` children. Non-interactive runs do not show the project-trust prompt: without a saved trust decision they follow `defaultProjectTrust` (`ask` default = project-local `.pi` resources ignored). For CI, either save a trust decision interactively first (`/trust`) or set `defaultProjectTrust: "always"` in `~/.pi/agent/settings.json` (weigh the security tradeoff), or pass `--approve`.

## Layout

```text
solidforge-pi/
├── package.json              # pi manifest (pi.extensions / pi.skills / pi.prompts)
├── skills/                   # 5 skills (SKILL.md + stdlib python infra + self-gates)
├── prompts/solidforge:arm-tools.md
├── agents/                   # 22 solidforge:<name> agent definitions (loaded by sf-subagents)
└── extensions/
    ├── sf-subagents/         # subagent tool + package agents discovery (16/8 concurrency, env-tunable)
    ├── sf-hooks/             # tool_call/tool_result → python hook bridge (CLAUDE_PROJECT_DIR env)
    └── sf-providers/         # credential bridge + the qwen-bailian route registration
```

Port provenance and per-milestone decisions: [PORTING-PLAN.md](PORTING-PLAN.md) (M0 spike → M4). Each skill's `docs/` retains the upstream convergence trail; substrate divergences are logged in the skills' `*.divergence.md`.
