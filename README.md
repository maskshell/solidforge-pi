# SolidForge-pi

**SolidForge for the [Pi](https://github.com/earendil-works/pi-mono) coding agent** — an independent, pi-native implementation of the SolidForge Loop Engineering system: the **converge → specify → implement** pipeline plus two additive **outcome-axis** layers (cited-source verification + uncited prior-art collision). Design lineage: [solidforge](https://github.com/maskshell/solidforge) (the Claude Code reference implementation) — its ADRs remain the shared design authority and knowledge flows both ways, but there is **no git upstream/sync relationship**; code sharing is narrow, deliberate, and ledgered in [docs/upstream-watch.md](docs/upstream-watch.md).

- **Skills (5)** — `cross-source-review`, `blueprint-crafting`, `parallel-development`, `primary-source-verification`, `prior-art-search` (invoke `/skill:solidforge:<name>` or the bare `/solidforge:<name>` on a pi.namespace-capable pi; `/skill:<name>` on stock pi)
- **Agents (22)** — plugin-scoped as `solidforge:<name>`, dispatched via the bundled `subagent` tool (isolated context; single / parallel / chain)
- **Guards** — the convergence-loop hooks (`blueprint_guard` / `counters` / `fast_gate`) bridged to pi's `tool_call` / `tool_result` events by the `sf-hooks` extension
- **Heterogeneous (异源) review substrate** — the different-family review legs spawn stateless `pi --mode json` subprocesses on provider routes **different** from the orchestrator's family, with wrapper-side budget/turn/bytes/wall-clock breakers (ADR #41/#43/#52 semantics preserved)

## Install

```bash
pi install npm:solidforge-pi                     # npm registry (unscoped; formerly @maskshell/solidforge-pi — that name stays published as a deprecated pointer)
pi install git:github.com/maskshell/solidforge-pi      # or: from git / a local path
```

Requires `python3` on `$PATH` (all gate/policy scripts are Python stdlib-only CLIs) and `ruff` for the lint gates. Gates run in CI on every push/PR ([`.github/workflows/ci.yml`](.github/workflows/ci.yml)): per-skill structural gates, `pi_loader_smoke.py` (the package loads under pi's REAL resource loaders — 7 checks: exact 5-skill set, zero diagnostics, prompt/manifest/agents/extensions-registered consistency), the sf-hooks seam selftest, markdownlint, an npm-pack leak check, and a headless loader-e2e that imports + initializes all extensions through pi's own loader. Release publishing additionally re-runs the loader smoke (see `npm-publish.yml`).

**Optional prerequisite — [pi-mcp-adapter](https://www.npmjs.com/package/pi-mcp-adapter)**, only for the Playwright E2E trio and Graphiti memory:

```bash
pi install npm:pi-mcp-adapter
# then configure the playwright-test server, e.g. in .mcp.json:
# { "mcpServers": { "playwright-test": { "command": "npx", "args": ["-y", "@playwright/test-mcp"] } } }
```

Without the adapter, the playwright agents fall back to the Playwright CLI (`npx playwright codegen|test`), and Graphiti memory ops degrade gracefully (the skill skips them).

## Arm a project (Layer 2)

Enabling the package does NOT mutate host-project build files. In a target project run:

```text
/solidforge:arm-tools              # pi.namespace-capable pi — provision arch-configs + constitution + templates
/solidforge:arm-tools --with-tools # …also add version-matched gate tools to dev deps
/arm-tools                         # stock-pi fallback (no namespace: template name = filename)
```

The namespace form requires a pi build with `pi.namespace` support — this package declares `"namespace": "solidforge"`. Easiest install (prebuilt, release-tracked): `npm install -g https://github.com/maskshell/pi/releases/latest` asset one-liner from [maskshell/pi Releases](https://github.com/maskshell/pi/releases) (see [FORK.md](https://github.com/maskshell/pi/blob/main/FORK.md)); source patches + lifecycle rules on the [`namespace-patch` branch](https://github.com/maskshell/pi/tree/namespace-patch/patch); proposal trail: [earendil-works/pi#8834](https://github.com/earendil-works/pi/issues/8834).

`arm.py` appends the L1 Constitution to the project's **AGENTS.md** (when present) or **CLAUDE.md** — pi loads either. Reversible: `arm.py --revert` (dry-run; `--apply` to execute).

## Heterogeneous review routes

Profiles are pi **catalog routes** (model facts catalog-inherited; the CC-era `[1M]` suffix is a context-window parameter and never appears in a pi model id):

| profile (alias) | route | model | credential |
| --- | --- | --- | --- |
| `zai-coding-cn` (`bigmodel`) | zai-coding-cn — GLM coding endpoint, openai-completions | `glm-5.3` | pi `auth.json` (default provider) or `ZAI_CODING_CN_API_KEY` |
| `deepseek` | deepseek — native endpoint | `deepseek-v4-flash` | `DEEPSEEK_API_KEY` ← bridged from `DEEPSEEK_ANTHROPIC_AUTH_TOKEN` |
| `minimax-cn` (`minimax`) | minimax-cn — anthropic endpoint | `MiniMax-M3` | `MINIMAX_CN_API_KEY` ← bridged from `MINIMAX_ANTHROPIC_AUTH_TOKEN` |
| `qwen-bailian` (`qwen3`) | **custom route** (pi catalog has only token-plan subscription qwen routes; Bailian pay-per-use key registered by `sf-providers` when present) | `qwen3.8-max` | `QWEN3_ANTHROPIC_AUTH_TOKEN` (the DashScope pay-per-use key) |
| `qwen-token-plan-cn` | qwen-token-plan-cn — token-plan subscription | `qwen3.8-max` | `QWEN_TOKEN_PLAN_CN_API_KEY` |

Put tokens in the target project's `.env.solidforge` (shell env wins; `arm-tools` provisions the `.env.solidforge.example` placeholder). Select legs via `HETERO_DOC_PROFILE` / `HETERO_PROFILE` (comma-list = multi-different-family). CC-era profile names (`bigmodel`, `minimax`, `qwen3`) keep working via aliases.

**Budget/cost note**: routes with catalog pricing (deepseek, minimax-cn) feed real `usage.cost.total` into the wrapper-side budget breaker; zai-coding-cn and qwen-bailian report cost 0 (unknown to the catalog) — the budget cap is inert there, wall-clock/turns/bytes caps still apply.

## CI / non-interactive subprocesses

The `subagent` tool and the hetero wrappers spawn `pi --mode json -p` children. Non-interactive runs do not show the project-trust prompt: without a saved trust decision they follow `defaultProjectTrust` (`ask` default = project-local `.pi` resources ignored). For CI, either save a trust decision interactively first (`/trust`) or set `defaultProjectTrust: "always"` in `~/.pi/agent/settings.json` (weigh the security tradeoff), or pass `--approve`.

## Development

Run the full CI gate set locally:

```bash
ruff check tools skills/*/infra && ruff format --check tools skills/*/infra
for s in skills/*/; do (cd "$s" && python3 infra/test/lint_self.py && python3 infra/test/disconnect_check.py && [ -f infra/test/plugin_layout.py ] && python3 infra/test/plugin_layout.py); done
PI_LOADER_ROOT=<pi package root> python3 tools/pi_loader_smoke.py
node tools/sf_hooks_selftest.mjs
PI_PKG_ROOT=<pi package root> node tools/pi_extensions_load_smoke.mjs
./tools/e2e_probe.sh  # authenticated install-path probe (needs model creds; CI-infeasible)
```

Contributor checklist (the non-obvious invariants the gates enforce):

- **New extension dir** (`extensions/sf-*/`): MUST be registered in `pi.extensions` — pi expands manifest entries only, an unlisted dir silently no-loads (`extensions-registered` blocks the release). The enumerated manifest form is deliberate: it is immune to the `extensions/index.ts` barrel hijack and acts as an explicit publish gate — do NOT collapse it to `"./extensions"` (see [docs/pi-internals-anchors.md](docs/pi-internals-anchors.md)).
- **Agent files** (`agents/*.agent.md`): BARE lowercase-hyphen frontmatter `name:` — the `solidforge:` namespace is composed at load by `sf-subagents` from `pi.namespace` (single source of truth).
- **Python edits**: ruff check + format must pass — the in-session gate denies red edits BEFORE they land (and post-write blocks disclose that the edit already applied).
- **pi version bumps**: re-verify the internals anchors in [docs/pi-internals-anchors.md](docs/pi-internals-anchors.md) and move `PI_REF` in BOTH workflows together.

## Layout

```text
solidforge-pi/
├── package.json              # pi manifest (pi.extensions / pi.skills / pi.prompts)
├── skills/                   # 5 skills (SKILL.md + stdlib python infra + self-gates)
├── prompts/arm-tools.md           # /solidforge:arm-tools via pi.namespace
├── agents/                   # 22 agent definitions (BARE names; sf-subagents composes solidforge:<name> from pi.namespace at load)
└── extensions/
    ├── sf-subagents/         # subagent tool + package agents discovery (16/8 concurrency, env-tunable); live streaming of child internals (tool calls / turns / elapsed / idle / text tail)
    ├── sf-hooks/             # tool_call/tool_result → python hook bridge (CLAUDE_PROJECT_DIR env)
    ├── sf-providers/         # credential bridge + the qwen-bailian route registration
    ├── sf-progress/          # csr run-progress footer strip (tails the ADR #61 sidecar; ambient run-level status)
    └── sf-hetero/            # the hetero_doc_review tool — the different-family leg as a first-class tool (live per-provider panel; stdout verbatim as content)
```

Port provenance and per-milestone decisions: [PORTING-PLAN.md](PORTING-PLAN.md) (M0 spike → M4; now frozen as the lineage + divergence ledger). Live relationship contract with the CC reference implementation: [docs/upstream-watch.md](docs/upstream-watch.md). Each skill's `docs/` retains the upstream convergence trail; substrate divergences are logged in the skills' `*.divergence.md`.
