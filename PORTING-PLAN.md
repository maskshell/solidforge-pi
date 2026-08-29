# SolidForge → Pi 移植方案

> 状态：方案定稿（2026-08-22）｜**M0 spike 已完成（2026-08-23）**｜源：`/Users/solosus/dev/ws-ai/solidforge`（Claude Code 插件）｜目标：本仓库（pi package）
> 本文档由三轮分析沉淀：① 可行性分析 → ② 对抗性复查（3 处纠错）→ ③ pi-mcp-adapter 调研决策 → ④ M0 spike 实测（结果已回写 §6/§9/§10）。

---

## 与 solidforge-internal 的关系（2026-08-29 定案，取代"port/sync"心智）

**solidforge-internal 不是本仓库的 git 上游。** 它是**设计上游**（design lineage）：ADR 编号仍是双方共享的设计权威，知识双向流动（其 ADR #57 明言"borrowed from the pi + dsh ports"），但代码共享只按三层契约窄通道进行，永不 git 跟踪：

- **设计层**（ADR/proposal/方法论）：双向引用，谁的好流谁；
- **substrate-neutral 代码层**（纯 stdlib 引擎、schemas、agents）：允许 verbatim 对齐，方向按内容定；
- **substrate 层**（CC hooks/settings/Task ↔ pi extensions/JSONL/UI 面板）：永不互相同步代码，只交换问题清单。

证据与台账：[docs/upstream-watch.md](docs/upstream-watch.md)（每笔流入/流出/拒绝吸收都有记录；含 ⚠️ 待吸收候选）。实测依据：共享 substrate-neutral 文件分叉 0.1–3.3%，而 csr wrapper 到 12.4% 恰好是 pi 原生观测栈落点——结构性不可回流；历史 sync-1（`51bb3ca`）已是 hand-merge 而非 git merge。

**本文档自本节起冻结为 lineage + divergence ledger**：增量只记 divergence 决策与里程碑（见尾部 addenda），不再承担"同步计划"职能。

---


## 0. 结论速览

**无根本性障碍。** SolidForge 的灵魂——确定性收敛策略引擎（`converge.py` / `produce.py` / `loop_state.py` / `plan_queue.py` 等纯 stdlib Python CLI）和协议文本——完全 harness 无关，约 70% 资产可直接复用。Claude Code 插件外壳（agents / hooks / command / MCP 四件套）需按 Pi 的扩展模型重建，其中 **4 处为实质重写点**。

| 分级 | 内容 | 占比 |
|---|---|---|
| 直接复用 | 5 个 SKILL.md（文本替换后）、全部 Python infra、schemas、arch-configs、设计文档 | ~70% |
| 适配层 | agents 转换、hooks shim、arm-tools 命令、profiles | ~25% |
| 实质重写 | ① hetero 异族子进程 substrate ② playwright MCP 三件套（引入 adapter 后已减半）③ TaskCreate 调度/冲突检测层 ④ budget/turns 上限下沉 | ~5% |

**移植顺序**：csr → psv/pas → parallel-development（对 harness 依赖递增，先用 csr 打通"subagent 扩展 + hetero 子进程"全链路再铺开）。

---

## 1. 源项目盘点

SolidForge 是一个 Claude Code 插件（`.claude-plugin/plugin.json` + 自带 marketplace），捆绑：

- **5 个技能**：`cross-source-review`（文档收敛）、`blueprint-crafting`（上游工件）、`parallel-development`（并行开发编排 + 收敛环）、`primary-source-verification`（引用源核验）、`prior-art-search`（新颖性撞车检测）
- **22 个子代理**（`agents/*.agent.md`，作用域 `solidforge:<name>`）：architect、backend/frontend/ios-developer、code-reviewer、doc/plan-reviewer、claim-extractor/verifier、novelty-claim-extractor、collision-verifier、playwright-test 三件套、graphiti-config-generator 等
- **3 个 hooks**（Python stdlib-only）：`blueprint_guard.py` + `counters.py`（PreToolUse）、`fast_gate.py`（PostToolUse）
- **1 个命令**：`/solidforge:arm-tools`（Layer 2 项目武装）
- **MCP 依赖**（外部，不随包分发）：playwright-test（E2E 必需）、graphiti（可选，优雅降级）、ast-grep（可选，有 CLI 替代路径）、fedaot-wiki（1 处）
- **hetero 异族子进程**：`hetero_review.py` / `hetero_doc_review.py` spawn `claude -p --settings profiles/<backend>.json`（DeepSeek/BigModel/MiniMax/Qwen3 的 Anthropic 兼容端点），token 约定 `<NAME>_ANTHROPIC_AUTH_TOKEN`，`.env.solidforge` 自加载

---

## 2. 直接复用清单（不动或仅文本替换）

| 组件 | 复用方式 | 备注 |
|---|---|---|
| 5 个 `SKILL.md` | 复制 + 文本替换 | Pi 实现同一 Agent Skills 标准；技能名全部合规。**description 长度卡边**：parallel-development 1016/1024、psv 1011、pas 1014——**禁止加字**，Pi 适配说明写进正文而非 frontmatter |
| Python infra（全部 `infra/scripts/`、`infra/hooks/`、`infra/install/`） | 原样复用 | 均为 stdlib-only CLI，经 bash 调用，与宿主无关 |
| schemas / arch-configs / docs | 原样复用 | 纯文件 |

SKILL.md 文本替换项（全量）：

1. **60+ 处** `` `solidforge:<name>` `` 引用**保留原名**（M0.5 定案，见 §12）——仅改动词句：spawn → `call the subagent tool with agent="solidforge:<name>", task=...`
2. **16 处** `/solidforge:arm-tools` → `/arm-tools`
3. `${CLAUDE_PLUGIN_ROOT}` → 技能内相对路径（Pi progressive disclosure 规范：以 skill 目录为基准的相对引用）
4. `TaskCreate` / `TodoWrite`（parallel-development/SKILL.md 内 **22 处**）→ 见 §5.3 重写方案
5. `mcp__graphiti__*`（memory-protocol.md 43 处）→ proxy 调用格式（§6）
6. `mcp__ast-grep__*`（4 处）→ `sg` CLI（ast-grep 官方双路径之一）
7. `mcp__playwright-test__*` → §6 决策
8. `CLAUDE_PROJECT_DIR` 字样（csr SKILL.md 等）→ 语义等价改述（"项目根"）

---

## 3. 复查纠错记录（已验证的事实，防方案回退）

> 本节是第二轮对抗性复查的产出，三条都是初版方案的错误判断，**后续执行时不得回退到初版结论**。

1. **CLAUDE.md：Pi 原生支持**（usage.md："Pi loads `AGENTS.md` or `CLAUDE.md`"）。arm.py 的 constitution 注入基本原样工作。残留风险：目标项目根已有 `AGENTS.md` 时，同目录 `CLAUDE.md` 是否被加载未明示（仅 `AGENTS.override.md` 取代机制有文档）。**修正动作**：arm.py 加 ~10 行——项目根存在 `AGENTS.md` 时优先追加到它。
2. **Pi 包无 `agents/` 资源类型**。约定目录仅 `extensions/ skills/ prompts/ themes/`；官方 subagent 扩展的 `discoverAgents()` 只扫 `~/.pi/agent/agents` 与 `.pi/agents`（向上爬树）。包内 `agents/` 目录**不会被任何机制发现**。**修正动作**：sf-subagents 扩展改 `discoverAgents()`，额外合并包自身 `agents/` 目录（~15 行 TS）；包根 `agents/` 仅作存储位置。
3. **TaskCreate 不是零散小项**。22 处引用且承担**并发冲突检测**功能（任务 metadata `files_touched` 判定并行任务是否触碰同一文件）。官方 todo.ts 示例无自定义 metadata 字段，装上不够用。**修正动作**：见 §5.3，二选一拍板。

---

## 4. 适配层设计

### 4.1 sf-subagents 扩展（基于官方示例裁剪）

以 `examples/extensions/subagent/` 为基础，三处修改：

1. **discoverAgents() 合并包内 `agents/`**（纠错 2）
2. **并发上限**：示例硬编码 8 任务/4 并发，对 pd 的大规模并行场景上调（8→可配置，默认 16；并发 4→8）
3. 工具名保持 `subagent`（`pi.registerTool({name:"subagent"})`），SKILL.md 重写时引用该名

**Agent 转换规则**（22 个 `.agent.md` → `.md`）：

- frontmatter：`name/description/tools/model` 四字段保留；CC 专属可选字段（`run_in_background` 等）剥除（Pi 忽略但不识别）
- 命名：**保留 `solidforge:<name>`**（M0.5 定案——agent 名只是 frontmatter 字符串 + Map 键，全链路无字符集校验；SKILL.md 60+ 处引用零改动；YAML 值加引号）。文件名保留 `<name>.agent.md`（冒号不入文件系统）。用户/项目同名 agent 覆盖包内 agent（后加载者优先）
- **工具名映射**：`Read→read, Grep→grep, Glob→find, LS→ls, Edit→edit, MultiEdit→edit（多 edits 数组）, Write→write, Bash→bash`
- description 无需重写：原风格（numbered use cases，50–500 字符）同时满足 CC 与 Pi 最佳实践（agent-crafter 规范对照通过）

**spawn 机制**（已验证）：`pi --mode json -p --no-session --model <m> --tools <list> --append-system-prompt <file>`，解析 JSON-lines 事件流（`message_end`/`tool_result_end`）；`--tools` 支持 built-in + extension + custom 工具；agent 无 `model` 字段时继承父会话模型与 thinking level。

**注意**：非交互子进程的项目信任依赖 `defaultProjectTrust` / `--approve` / 已存 trust 决策——CI 场景需在 README 写明（如 `defaultProjectTrust: "always"` 的安全权衡）。

### 4.2 sf-hooks 扩展（hook shim，零改动复用 Python）

~150 行 TS，把 Pi 事件转成 CC hook 协议喂给原 Python 脚本：

| Claude Code | Pi 对应物 |
|---|---|
| PreToolUse matcher `Edit\|Write` | `tool_call` 事件，`toolName ∈ {edit, write}` |
| PostToolUse matcher `Edit\|Write` | `tool_result` 事件（可改结果） |
| stdin payload `tool_input.file_path` | `event.input.path`（Pi 参数名不同） |
| `hookSpecificOutput.permissionDecision:"deny"`（PreToolUse，调用不执行） | `{block: true, reason}` 返回值 |
| `{"decision":"block","reason"}`（PostToolUse，编辑已发生，反馈自纠） | `tool_result` 返回 `{isError: true}` + reason 回注 |
| env `CLAUDE_PROJECT_DIR` | `ctx.cwd` 注入子进程环境 |
| env `CLAUDE_PLUGIN_ROOT` | 包根（`import.meta` 定位） |
| hooks.json timeout 5s/20s | `AbortSignal.timeout` 同值保留 |

三个脚本的协议已逐一核实（`read_payload()`=stdin JSON、`emit_block`/`deny_block` 输出格式）。shim 放 `extensions/sf-hooks/index.ts`。

### 4.3 arm-tools 命令

`commands/arm-tools.md` → `prompts/arm-tools.md`。Pi prompt templates 支持同样的 `description` / `argument-hint` / `$ARGUMENTS` frontmatter，近乎直接转换。两处内容修改：

- `${CLAUDE_PLUGIN_ROOT}` → 相对/包路径
- **Step 3 LSP 推荐段重写**：原推荐 claude-plugins-official 的 LSP 插件——Pi 无对应生态，改为直接推荐 language-server 二进制安装命令

arm.py 本体：加 AGENTS.md 优先逻辑（§3.1）；`plugin_layout.py` 自检更新为校验 pi package 结构。

### 4.4 profiles（hetero 的 provider 声明）

两条路径（token 约定 `<NAME>_ANTHROPIC_AUTH_TOKEN` 两条路径都保留）：

- **路径 A（零代码，用户侧配置）**：`~/.pi/agent/models.json`，每 provider 一段 `{baseUrl: ".../anthropic", apiKey: "$DEEPSEEK_ANTHROPIC_AUTH_TOKEN", api: "anthropic-messages", models: [...]}`。`.env.solidforge` 自加载逻辑照旧（models.json 的 `apiKey:"$VAR"` 在请求时解析 shell 环境变量——需确认 pi 对 `.env` 文件不自加载，wrapper 先 load 再 export 的模式可保留）。
- **路径 B（包自包含）**：sf-providers 扩展 `registerProvider`（参考 `custom-provider-anthropic` 示例），异步工厂可自读 `.env.solidforge`。

**首版决策：路径 B**（solidforge 的卖点是一体安装；models.json 把配置负担转嫁给用户，与原体验不符）。

---

## 5. 实质重写点（4 处）

### 5.1 hetero 异族子进程 substrate

`hetero_review.py` / `hetero_doc_review.py` / research tier 的 spawn 从 `claude -p --settings ...` 改为：

```
pi --mode json -p --no-session --model <provider>/<model> \
  --tools <allowed> --append-system-prompt <prompt-file> [-p "<prompt>"]
```

Pi 无对应物、需下沉实现的 CC flag：

| CC flag | Pi 替代 |
|---|---|
| `--settings profiles/<x>.json` | sf-providers 扩展注册的 provider（§4.4） |
| `--max-budget-usd <cap>` | **自行实现**：JSON 事件流含 `usage.cost.total`，wrapper 累计超限即 SIGKILL |
| `--max-turns <cap>` | **自行实现**：计数 `message_end`(assistant) 事件 |
| `--json-schema <violation-log.schema.json>` | **下沉**：schema 校验移入 `converge.py` / wrapper 层（psv/csr 本来就有 schema 校验环节，顺势收编） |
| `--permission-mode bypassPermissions` | Pi `-p` 模式无权限弹窗，天然等价 |
| `--output-format stream-json --verbose --include-partial-messages` | `--mode json`（逐行 JSON 事件） |

wrapper 的心跳（stderr 每 30s）、`provider_runs[]` 记账、`.env.solidforge` 加载序、ADR #52/#43 的 caps 语义全部保留——只换底层 spawn 命令与解析器。

### 5.2 playwright MCP 三件套（引入 adapter 后重写面减半）

见 §6 决策。三个 playwright agent 的 frontmatter `mcp__playwright-test__*` 工具列表（26+ 个）改写为 proxy 调用指引（或 directTools 命名，待实测）。

### 5.3 TaskCreate 调度/冲突检测层（需拍板 ⚖️）

两个方案：

- **方案一（SKILL.md 叙述几乎不动）**：sf-subagents 扩展顺带注册 `sf_task` 工具，schema 带 `files_touched[]`、`status`、`agent` 字段，复刻 TaskCreate/TodoWrite 语义。
- **方案二（更贴合项目"deterministic 优先"哲学）**：任务注册表下沉为 `.claude/parallel-dev/tasks.json` 状态文件，由现有 Python 层（`loop_state.py` 家族）管理 `task add/claim/conflict-check` 子命令；SKILL.md 调度段改写为 CLI 调用。冲突检测（`files_touched` 交集）在 Python 里做，可测试、可 golden。

**倾向方案二**（冲突检测是收敛环的正确性部件，应在确定性层），但方案二 SKILL.md 改写量大。**此项需在动 parallel-development 前拍板。**

### 5.4 budget/turns 上限

并入 §5.1 wrapper 实现，无独立工作面。

---

## 6. pi-mcp-adapter 决策（v2.27.0，已调研）

**体检**：MIT；官方 `@modelcontextprotocol/client 2.0.0`；月下载 58 万（pi 生态事实标准）；凭据入 OS keychain、OAuth URL 绑定、host 配置默认不自动加载（`hostConfigDiscovery:"off"`）。**风险**：单维护者（有活跃 fork 可自救）；peerDep 锁 `@earendil-works/pi-ai ^0.84.1`，pi 升级后可能短暂不兼容——**写入依赖风险清单**。

**按依赖分级**：

| solidforge 依赖 | 决策 | 模式 | 理由 |
|---|---|---|---|
| **graphiti**（可选） | ✅ 用 adapter | **proxy**（单个 `mcp` 代理工具，懒连接） | 调用稀疏，近零空闲成本；本来声明优雅降级 |
| **playwright-test**（E2E 必需） | ✅ 用 adapter | **proxy（已定案，见 §6 实测）** | 保住 MCP 语义与跨步骤浏览器会话态，重写面最小 |
| **ast-grep**（可选） | ❌ 不用 adapter | — | 官方 CLI（`@ast-grep/cli`）就是两条路径之一，不值得挂底座 |

**playwright 的真权衡（proxy vs directTools）**：

- proxy：上下文极省（~200 tokens vs 单 server 10k+），但三个 agent 的工具白名单从"26 个具名工具"退化为 1 个代理——**丢失细粒度工具纪律**（solidforge 的 model-routing.md 把 narrow tool surface 列为 reviewer tier 的可靠性依据）
- directTools（`directTools: true|[...]` + `toolPrefix:"mcp"` + `includeTools`）：逐工具注册，恢复具名粒度

**✅ M0 实测定案（2026-08-23）：proxy。** 对 adapter v2.27.0 源码验证：`formatToolName()` 以**单下划线**拼接（`` `${prefix}_${tool}` ``），`toolPrefix:"mcp"` 产出 `mcp__playwright-test_browser_click`，**与 CC 的双下划线 `mcp__playwright-test__browser_click` 不一致**——"frontmatter 近乎免改"的乐观假设被推翻，directTools 路径同样需要全量文本替换（且引入 schema 进上下文的代价）。加上下述信任问题，proxy 是两条路中改写面更小的那条。

**⚠️ 信任问题具体化（M0 发现）**：subagent 异构子进程（`pi --mode json -p`）非交互运行，项目级 `.mcp.json` 在 `defaultProjectTrust:"ask"`（默认）下**不被加载**。缓解（M3 验证）：① playwright-test server 配置在用户全局（`~/.config/mcp/mcp.json` 或 `~/.pi/agent/mcp.json`）；② 包内 `pi.mcp` 声明（adapter 的 package-mcp-loader 加载，包是用户级安装，理论不走项目信任——待实测）；③ CI 设 `defaultProjectTrust:"always"`。

**对移植的直接增益**：

- 包内分发：`package.json` `"pi": {"mcp": "./mcp.json"}` 可随包发 playwright-test server 定义（自动 `包名__` 前缀），用户零配置
- 存量兼容：宿主项目已有 `.mcp.json`（给 CC 配的）直接被识别——CC 迁来项目无缝
- 运行时注册：`registerMcpServer({pi, name, definition})` 可编程式按需注册，session 级隔离

**前置声明**：solidforge-pi README 需写明 `pi install npm:pi-mcp-adapter` 为可选前置（graphiti/playwright 用到时）——peer 关系，不静默替用户装第三方。

---

## 7. 目标形态（修正版）

```
solidforge-pi/
├── package.json              # pi manifest: extensions/skills/prompts + pi.mcp
├── mcp.json                  # playwright-test server 定义（随包分发）
├── skills/                   # 5 个技能：原样复制 + §2 文本替换
├── prompts/arm-tools.md      # 原 command 转换 + Step3 重写
├── agents/                   # 22 个转换后 agent（solidforge: 命名，.agent.md 文件名）——仅存储，由扩展加载
└── extensions/
    ├── sf-subagents/index.ts # 官方示例裁剪：包内 agents 发现 + 并发上调 + (可选 sf_task)
    ├── sf-hooks/index.ts     # tool_call/tool_result → CC hook 协议 shim（§4.2）
    └── sf-providers/index.ts # registerProvider: deepseek/bigmodel/minimax/qwen3
```

安装：`pi install git:github.com/<you>/solidforge-pi`（git/npm 包替代 plugin marketplace；npm 发布需带 `pi-package` keyword）。

---

## 8. 移植顺序与里程碑

| 阶段 | 内容 | 打通验证 |
|---|---|---|
| **M0 spike** ✅ | sf-subagents 扩展跑通 + directTools 命名实测 + models.json/registerProvider 对 DeepSeek 端点连通性 | `subagent` 工具调 `solidforge:doc-reviewer` 返回结构化结果 |
| **M1 csr** ✅（2026-08-25） | skills/cross-source-review 移植：hetero_doc_review.py spawn 层 pi 化（`pi --mode json -p -e sf-providers`）+ guard 测试重写（8 检查）+ SKILL.md/install.md/divergence.md 适配 | **实弹**：bigmodel(GLM-5.2) 抓到植入矛盾（blocker+双行引文）；qwen3 401 被 `hetero-api-error` 如实披露；离线 6/6 测试全绿（含 budget/turns 熔断 degrade） |
| **M2 psv/pas** ✅（2026-08-25） | 两个 outcome-axis 技能（无 hooks 依赖，最快） | psv e2e：BERT 误归属被 **refuted**（带抓取引文），覆盖记录 1V/1R/0W/0K of 2；pas e2e：3 新颖性声明全 clear-under-search（含诚实盲区披露）；两技能离线 14/14 绿 |
| **M3 pd** ✅（2026-08-25） | sf-hooks shim（三 deny/block 路径实弹验证）+ hetero_review spawn 层 pi 化（复用 csr 模式）+ TaskCreate 方案二（loop_state task-* 子命令族，冲突检测确定性层）+ SKILL.md/references 改写 + playwright 三件套 adapter-proxy 化 + plugin_layout 适配 pi manifest + **补漏 blueprint-crafting**（里程碑漏项，开箱全绿） | pd 异源腿实弹：13 轮工具调用、$0.0102 cost、wall-clock 熔断诚实 malform、run-record 落盘；task 注册表冲突阻断 exit 3 验证；pd 38/38 + bc 全绿 |
| **M4 arm + 收尾** ✅（2026-08-25） | arm-tools 命令全量移植（LSP 段改二进制推荐、`${CLAUDE_PLUGIN_ROOT}`→`<skill-dir>`）+ arm.py `_context_md_path` AGENTS.md 优先补丁（双路径实弹验证）+ tasks.json 入 gitignore + README（安装/adapter 前置/路由表/CI trust） | 沙盒 arm 双路径验证（写 CLAUDE.md vs 追加 AGENTS.md）；**全包终验 52/52 门禁绿** |

---

## 9. 风险清单

| 风险 | 影响 | 缓解 |
|---|---|---|
| SKILL.md description 卡 1024 上限（1016/1014/1011） | Pi 适配说明无处加 | 写进正文，不碰 frontmatter；替换文本时监控长度 |
| pi-mcp-adapter 单维护者 + peerDep `^0.84.1` | pi 升级后 adapter 断连 → playwright/graphiti 降级 | 锁 adapter 精确版本；graphiti 本来优雅降级；playwright 有 CLI 兜底预案 |
| 非交互子进程项目信任（subagent `pi -p` 不弹信任框） | CI/新环境子代理加载不到项目资源 | README 写明 `--approve` / `defaultProjectTrust` 权衡 |
| `toolPrefix:"mcp"` 命名与 CC 不一致（**M0 已实测确认**：`mcp__playwright-test_browser_click` 单下划线） | playwright frontmatter 无论哪条路都要改写 | 已定案 proxy：三 agent 提示词改写为 `mcp({search})/mcp({tool})` 指引（M3） |
| 项目级 `.mcp.json` 在非交互子进程不可用（defaultProjectTrust 默认 ask） | CI/新环境子代理看不到 playwright server | M3 验证包内 `pi.mcp` 路径 + README 全局配置指引 |
| 同目录 AGENTS.md + CLAUDE.md 并存优先级未明示 | arm.py 写 CLAUDE.md 但项目读 AGENTS.md → constitution 不加载 | arm.py AGENTS.md 优先补丁（§3.1） |
| subagent 官方示例并发 8/4 | pd 大规模并行受限 | sf-subagents 上调并加配置 |
| Pi 无 budget/turns/spending 内建上限 | ADR #52/#43 的 caps 语义弱化 | wrapper 自实现（§5.1）——这是硬性移植要求，不可省 |

---

## 10. 待拍板事项 → 已拍板（M0，2026-08-23）

| 事项 | 决策 | 依据 |
|---|---|---|
| 1. TaskCreate 层 | **方案二**：Python tasks.json 状态文件（`loop_state.py` 家族管理 `task add/claim/conflict-check`） | 冲突检测是收敛环正确性部件，应在确定性层（可测试、可 golden）；M3 执行 |
| 2. playwright proxy vs directTools | **proxy**（adapter v2.27.0 源码实测：directTools 命名单下划线，与 CC 不一致，免改假设不成立） | 见 §6 |
| 3. providers 路径 A/B | **路径 B**（registerProvider 扩展），已实现于 `extensions/sf-providers`，DeepSeek 连通已验证 | 一体安装体验 |
| 4. agent 前缀 | **修订（M0.5）：保留 `solidforge:<name>`**，废弃 M0 的 `sf-` 决策 | 见 §12：命令链源码验证 + 双冒烟通过；`sf-` 改名收益归零（SKILL.md 引用零改动 > 潜在同名冲突，后者由加载优先级兼底） |

---

## 11. M0 spike 结果（2026-08-23）

| 验证项 | 结果 |
|---|---|
| sf-subagents 扩展（包内 agents 发现 + spawn 链路） | ✅ 冒烟通过：`-e` 加载 → 发现 `sf-doc-reviewer`（package source）→ spawn 子进程 → 正确抓到植入的 zero-downtime 矛盾，按 schema 返回 4 findings |
| directTools 命名实测 | ✅ 完成（源码验证，未装 adapter）：**不一致**（单下划线），决策定 proxy |
| DeepSeek 连通性（sf-providers + `.env.solidforge` 自加载） | ✅ `--model deepseek/deepseek-v4-flash` 返回正常 |
| 已落盘资产 | `package.json`（pi manifest）、`agents/sf-*.md` ×22（5 个带 M3 TODO 旗标）、`extensions/sf-subagents/`、`extensions/sf-providers/`、`tools/convert_agents.py`（可重跑） |
| 遗留 → M1 | ① MiniMax 连通（同机制复制）② sf-providers 模型规格（contextWindow/maxTokens/costs）按 provider 文档校准 ③ reasoning 标志确认 ④ agent 正文 prose 工具名清洗（非反引号处） |

### M1 实施记录（2026-08-25）

- **hetero_doc_review.py pi 化**（外科手术式，CLI 契约与输出 JSON 形状不变）：`_pi_argv`（spawn `pi --mode json -p --no-session -e <sf-providers>`；provider/model 由 profile `_provider`+`model` 组合）；`_run_streamed` 解析 pi JSONL（assistant turn = `message_end.role=assistant`，cost 累计自 `usage.cost.total`）+ **wrapper-side budget/turns 熔断**（pi 无 CLI flag，degrade subtype 与 CC 时代一致：`error_max_budget_usd`/`error_max_turns`）；新增 **`hetero-api-error` 分类**（pi 把 provider 错误放 `message_end.errorMessage` 且 rc=0，实测曾误报 no-result）；`_parse_pi_stream` 防御性 fence 提取（pi 无 `--json-schema`，防御解析成为唯一路径）；退役 `--no-stream`/`--observe-hooks`/`--findings-schema` 与 structured-retry fallback；`cc_stderr_tail`→`pi_stderr_tail`，provider_runs 增 `cost_usd`。
- **guard 测试重写**（8 检查）：argv 面、telemetry（pi 事件）、bytes/wall/budget/turns 四熔断、api-error 分类、provider_runs；fake child 发 pi JSONL 事件。
- **环境校准（M1，后被 M2.5 判定为误诊）**：bigmodel 自造 provider 走 CC 时代 `/api/anthropic` 端点拒 `GLM-5.3[1M]`（400），当时"校准"为 GLM-5.2。**M2.5 修订**（参照 solidforge-dsh 的 FILENAME=ROUTE + catalog-inherit 原则）：pi 内置 catalog 本就含全部四条异源路由——`zai-coding-cn`（glm-5.3, ctx 1M, **coding 端点 + openai 协议**，非 anthropic 端点）、`deepseek`（v4-flash/pro，原生端点）、`minimax-cn`（MiniMax-M3）、`qwen-token-plan-cn`（qwen3.8-max）。`[1M]` 是上下文窗口参数（pi 中由 catalog `contextWindow` 承载，id 不带后缀，`_pi_argv` 剥离）。**sf-providers v2 = 纯凭据桥**（CC 约定 token var → pi-ai 路由 env，不覆盖既有 auth；零 provider 注册，模型事实 catalog 继承不可漂移）；profiles 重写为路由命名文件（`_provider`/`model`/`_family` 谱系/`_token_env`，空值=auth.json 路由跳过 fail-fast）+ CC 名 alias（bigmodel→zai-coding-cn 等）。**实弹四路由**：zai glm-5.3 ✅（auth.json，抓 blocker）、minimax-cn ✅（桥，cost $0.0074——catalog 价格使 budget cap 首次有真实数据）、deepseek ✅（$0.0032）、qwen3 → hetero-api-error 401（token 失效，如实披露）。
- **已知限制**：BigModel 端点不回报 usage cost（`cost_usd=0`，budget cap 对其无效——telemetry 如实为 0）；resolved model 实测显示 `glm-5.3`（端点侧路由，telemetry 价值正在于此）。
- disconnect_check 适配：agent frontmatter 检查从 name/description/tools/disallowedTools → 前三（pi 用正面 tools 白名单）。

---

## 12. M0.5：`solidforge:` 前缀保留定案（2026-08-23）

**问题**：能否保留 CC 风格的 `solidforge:` 作用域前缀？附带键入 `/solidforge:` 后的自动补全是否可用？

**结论：可行，已定案采用。** 两类对象分开看：

| 对象 | 前缀 | 依据 |
|---|---|---|
| **agent 名**（subagent 工具参数） | ✅ 保留 `solidforge:<name>` | agent 名只是 frontmatter 字符串 + `discoverAgents()` 的 Map 键，全链路无字符集校验；不进 CLI 参数（系统提示走临时文件）；冒烟通过（`solidforge:doc-reviewer` 抓到植入矛盾） |
| **命令**（`/solidforge:arm-tools`） | ✅ 保留 | 源码级验证 + `-p` 模式执行路径冒烟通过 |
| **技能名**（skills） | ❌ 保持现状无前缀 | Agent Skills 标准强制小写连字符，冒号违规；技能名本就全称唯一（cross-source-review 等） |

**`/solidforge:` 自动补全链路（pi 0.84.2 源码逐层验证）**：

1. 命令注册（extensions/loader.js L249）：name 原样入 Map，**无字符集校验**
2. 命令解析（agent-session.js L930）：`slice(1, spaceIndex)` 到首个空格，**冒号零特殊处理**
3. 冲突后缀（extensions/runner.js L402–429）：仅在完全同名时追加 `:N`，不会遮蔽带命名空间的名
4. 补全触发（pi-tui autocomplete.js L205）：行首 `/` 且无空格 → 命令列表模式
5. 补全过滤（fuzzy.js L81–84）：查询按 `[\s/]+` 分词——**斜杠/空白是分隔符，冒号是普通字符**；键入 `/solidforge:` 即 fuzzy 匹配到 `solidforge:arm-tools`，无脚本/补丁
6. prompt template（prompt-templates.js L85）：name = 文件名去 `.md` 无清洗；冒号文件名在 POSIX/APFS/git/npm 均合法（仅 macOS Finder 显示不佳）

**已实施**：`convert_agents.py` 改为保留 `solidforge:` 名（YAML 加引号）+ 文件名保留源形式 `<name>.agent.md`；`prompts/solidforge:arm-tools.md` 占位模板已验证展开与 `$ARGUMENTS` 替换。上轮一次失败的 edit 调用导致的静默半途编辑（并发上限/接口字段未改）已在本轮补齐。

**附带验证：argument-hint（CC 同名同渲染）**。prompt template 的 frontmatter `argument-hint` 在补全列表内渲染为 `${hint} — ${desc}`（autocomplete.js L209-214，与 CC 一致）；`/solidforge:arm-tools` 保留 CC 原版 hint。注意分档：扩展命令（registerCommand）**无** argumentHint 字段（types.d.ts RegisteredCommand），只有空格后的动态参数候选（getArgumentCompletions → AutocompleteItem{value,label,description}）——因此 arm-tools 保持 template 路线，不转扩展命令（两者不能同名共存，会触发 :1/:2 冲突后缀）。


---

## 13. M3 实施记录（2026-08-25）

- **sf-hooks 扩展**（§4.2 落地）：`tool_call`(edit|write) → blueprint_guard.py + counters.py pre（5s），deny ⇒ `{block:true, reason}`；`tool_result` → fast_gate.py（20s），`decision:block` ⇒ isError + FAST-GATE 反馈。env 桥 `CLAUDE_PROJECT_DIR=ctx.cwd`；工具名映射 edit/write→Edit/Write（MultiEdit 并入 edit）、`input.path`→`tool_input.file_path`。**实弹三路径**：suspended 断路器 deny、frozen blueprint deny、ruff lint 反馈自纠。
- **hetero_review.py pi 化**：重放 csr 模式（manifest/_load_profile/_pi_argv/_run_streamed/_run_claude_once/_parse_pi_stream/main）；pd 特有 `_run_loop_state` 生命周期记账原样保留（本地 subprocess，harness 无关）；wiring 测试适配（envelope parser 断言 → wrapper-cap 映射断言；_materialize → _load_profile 路由组合断言）。
- **M3 实弹排障三连**（全部真 bug，全修复）：① pd `--allowed-tools` 默认仍是 CC 空格大写名（Stage D 漏项）→ 子进程无工具，deepseek 退化吐 DSML 原文一轮即停；② `_extract_text` 只取第一个 text part → 工具前导 prose 后的 JSON 被漏（csr/pd 双修：拼接全部 text parts）；③ **子进程继承 wrapper stdin（非 TTY 不关）→ `pi -p` 阻塞读 stdin**（手动跑通、wrapper 挂起的根因）→ `stdin=DEVNULL`（双 wrapper 同修，load-bearing 注释入档）。
- **TaskCreate 方案二**：loop_state.py 新增 `task-add/list/claim/conflict/complete` 子命令族，状态文件 `.claude/parallel-dev/tasks.json`；冲突检测 = files_touched 与 **in_progress** 任务交集（pending 为 advisory）；claim 冲突 exit 3 + conflicts[]，`--force` 编排者裁决。SKILL.md 调度环与 20 个示例行全部改写为 CLI 形式。
- **playwright 三件套**：M0 TODO 旗标落地为「Browser automation surface (PI PORT)」节——`mcp({search})`/`mcp({tool,args})` proxy 指引 + adapter 缺席时 Playwright CLI 兜底（诚实声明交互式会话不可用，不编造）。
- **plugin_layout 适配**：root 发现 `.claude-plugin/plugin.json` → `package.json`（pi manifest）；manifest 断言 → pi-package keyword + pi.extensions/skills/prompts；hooks.json 断言 → sf-hooks 扩展接线断言；arm-tools 路径 → prompts/；agent 名适配 `solidforge:` 命名空间。**bc（blueprint-crafting）补漏复制**——原里程碑表漏列（M1-M4 无 bc 行），其确定性管线开箱全绿，SKILL.md 仅 3 处 spawn 措辞适配。
- 其余：`.markdownlint.json` 随包复制（lint_self 需要）；pd profiles 同步 csr 路由集；model-routing/convergent-loop/hooks-reference 三个可执行 reference 更新为 pi substrate（design-decisions.md 是 ADR 历史档案，保留 CC 叙述）。


---

## 14. M4 实施记录 + 移植收官（2026-08-25）

- **arm-tools**：CC 命令全量移植为 `prompts/solidforge:arm-tools.md`（description/argument-hint 原样，冒烟占位替换为真实内容）；Step 3 从 claude-plugins-official LSP 插件推荐改写为 language-server 二进制推荐（pi 无 LSP 插件生态；确定性 CLI 门禁为底线）；`${CLAUDE_PLUGIN_ROOT}` → `<skill-dir>`（与 csr 同款措辞）；AGENTS.md/CLAUDE.md 双读语义在命令头部说明。
- **arm.py**：新增 `_context_md_path()` helper（项目根有 AGENTS.md 优先，否则 CLAUDE.md——§3.1 决策落地），`append_constitution`/`write_toolchain_note`/revert 报告三处接入；`.claude/parallel-dev/tasks.json` 入 GITIGNORE_ENTRIES（M3 新状态文件）。沙盒双路径实弹：无 AGENTS.md → 写 CLAUDE.md ✅；有 AGENTS.md → 追加且不创建 CLAUDE.md ✅。
- **README**：安装、python3/pi-mcp-adapter 前置声明（playwright/graphiti 依赖面）、arm 双层说明、五路由凭据表（含 qwen-bailian 自注册与 cost 为 0 的诚实说明）、CI 非交互 trust 三选项、目录树、PORTING-PLAN 链接。
- **终验**：5 技能 52/52 离线门禁全绿；实弹链路全数通过（subagent 双跳、四异源路由、sf-hooks 三路径、task 注册表、pd 异源腿含 run-record、psv/pas e2e、arm 双路径）。

**收官状态**：五技能全部在位且门禁绿；四个 CC 外壳件（agents/hooks/command/substrate）全部按 pi 模型重建；方案文档与 divergence 日志全程同步。后续可选：npm 发布（pi-package keyword 已就位）、M0.5 agent prose 工具名残留清洗、sf-providers 模型规格进一步校准。


---

## 15. Upstream 同步记录（2026-08-25，sync-1）

比对本移植复制基线（08-25 11:54）与 upstream `../solidforge` HEAD（45f596b）：

**已命中（无需动作）**：
- `29c5e13` TDD 三件套 / `5af48fe` GLM-5.3 / `5d0b493`+`dbbce21`+`082bc7b` 命名清扫 / `5656ef7` rustfmt edition / ADR #53 flash 默认 —— 全部在复制基线内（早前 `grep "seam:"` 带冒号属误判，正文为 "seam —"）。
- `8255b34`+`45f596b` ADR #57 三级命名 —— **upstream 反向采纳了本移植的学说**（commit 自述 "borrowed from the pi + dsh ports"）；pi 侧 profiles 全部合规（`_provider`==文件名、`_family` 齐、qwen-bailian/minimax-cn 同名、qwen3 双侧退役）。FABLE tier 全路由钉死为 CC env 阶梯概念，pi 无对应机制（`_pi_argv` 直连 route/model）→ N/A。
- `3a93109` docs/papers 快照 → pi 包范围外（只带 skills；技能内链接不涉）。

**同步落地（本次）**：
- `ca9edc5`（bc seam Option A）：loop_state.py **手工合并** `set-blueprint-ref` + fresh-state 崩溃修复（与 task 注册表共存，沙盒验证 ref/rev 双写）；bc SKILL.md seam-aware spawn；bc docs 4 件 wholesale（arch-design §3 AC-ENTRY、seam-upstream-anchor proposal+record）；plan-reviewer agent 增 seam-quality (a/b/c) 检查。
- `5b06dd3`+`8255b34`：csr install.md 家族列表（pi 路由版）；pd model-routing.md 三级学说表（pi 路由示例）；`.env.solidforge.example` 双 qwen 凭据通道（bailian 按量 vs token-plan 订阅）+ alias 说明。
- **有意 divergence 保留**：qwen3 alias → qwen-bailian（本环境 key 为按量制；upstream 扫向 qwen-token-plan-cn）；zai 路由 = pi coding 端点（upstream bigmodel.json 留 CC `/api/anthropic` 端点）——双平台各正。

**终验**：52/52 门禁绿（五技能全量）。


---

## 16. 三端 `.env.solidforge` 统一（2026-08-25，env-unify）

**复验结论**：文件发现逻辑三端兼容——CC/pi 逐字一致（`<project-root>/.env.solidforge` → `.env`，shell wins）；dsh 同两层 + preset-root 第三层兜底（且 dsh harness 擦 shell 凭据，文件即权威源）。差异仅在**变量名消费**：

| 路由 | CC | pi | dsh |
|---|---|---|---|
| deepseek | `DEEPSEEK_ANTHROPIC_AUTH_TOKEN`（convention）| 同（`_token_env`）| 同（convention；dsh 已移除该 profile——同源）|
| glm | `BIGMODEL_ANTHROPIC_AUTH_TOKEN` | 同（桥→`ZAI_CODING_CN_API_KEY`）| 原 `<ROUTE>_API_KEY` → **已对齐** `BIGMODEL_...` |
| minimax-cn | `MINIMAX_ANTHROPIC_AUTH_TOKEN` | 同 | 原 `MINIMAX_CN_API_KEY` → **已对齐** |
| qwen-bailian | `QWEN_BAILIAN_ANTHROPIC_AUTH_TOKEN` | **已修**（原 `QWEN3_` 过时）| —（无此 profile）|
| qwen-token-plan-cn | `QWEN_TOKEN_PLAN_CN_ANTHROPIC_AUTH_TOKEN` | **已修**（原 `..._API_KEY` 不一致）| 同（convention）|

**落地**：① pi 两个 qwen profile `_token_env` 对齐 upstream 文件名约定；sf-providers 桥表加 `QWEN_TOKEN_PLAN_CN_`→`..._API_KEY`、Bailian 现行名 `QWEN_BAILIAN_` + legacy `QWEN3_` 双认；example 模板同步。② dsh 四个 DSH-NATIVE/外部 profile（zai/minimax-cn/qwen，pd+csr 双拷贝）加 `_token_env`/`_credential_env` 指向共享文件的 CC 约定名（dsh 的 escape-hatch 字段，语义即为此）。③ **部署**：一份物理文件 `solidforge/.env.solidforge` + symlink（pi 根 `../solidforge/.env.solidforge`；dsh preset 根绝对链接）。

**验证**：14 个消费点矩阵全 OK（dry-check）；dsh `_materialize_profile` fail-fast 实测读通共享文件；pi qwen3 alias 实弹（认证+路由+模型解析正常；该次运行的 no-structured-output 为 provider 输出形态波动，`_parse_pi_stream` 最小回归测试证明解析器无回归——多 part/fence/前后 prose 均正确提取）；csr 6/6 + pd wiring 绿。

## Post-M4 addendum — csr live-progress disclosure (2026-08-29)

Upstream's ADR #61/#62 (run-progress sidecar + in-session narration) had NOT been
ported — under pi a csr review showed only the `Working...` spinner for both legs.
This increment lands a three-layer disclosure stack that is STRICTLY stronger than
the upstream mechanics (event granularity, zero LLM-behavior dependence, both legs
covered, ambient run-level strip — none of which CC offers):

**L1 — per-leg live panels (event-driven).**
- `sf-subagents` (同源): the child `pi --mode json` stream is now consumed at
  event granularity — `tool_execution_start` (current action), throttled
  `message_update` text_delta probes (live text tail; prefix-check before the
  JSON parse, hot-path preserved), and a `SF_SUBAGENT_TICK_MS` ticker (5s) that
  re-emits elapsed/idle during silent stretches (long provider latency stops
  being indistinguishable from a hang — ADR #52's concern, moved client-side).
  Renderers in all three modes (single/chain/parallel) show a live block
  (`⏳ 42s · turn 3 · → read docs/x.md · ↓2.1k`) and running-aware icons (the old
  partial showed a misleading ✓). `running/startedAt/lastEventAt/endedAt/
  currentToolCall/streamPreview` ride the details; frozen in the final result.
- `hetero_doc_review.py` (异源): NEW `leg-progress` stderr events beyond upstream
  — one compact line per grandchild `tool_execution_start` + one per assistant
  turn (with running cost). pi's bash tool streams child stderr live (100ms
  throttle) into the running tool panel, so the reviewer's actual process (not
  just 30s liveness) is visible mid-run through PLAIN bash — no new tool needed.

**L2 — run-progress sidecar (upstream #61 ported verbatim + ambient strip).**
- `csr_progress.py` ported verbatim (pure stdlib, zero CC surface; EVENT_REGISTRY
  identical → sidecar files are cross-readable with upstream).
- wrapper `--progress-file` (upstream semantics: leg boundaries + heartbeat tee,
  best-effort, module-global seam — function-signature contract untouched;
  divergence logged in `hetero_doc_review.divergence.md` v2.2).
- NEW `extensions/sf-progress/`: polls the newest
  `workspace/cross-source-review/runs/<run>/progress.jsonl` (3s; torn-tail-safe
  incremental read) and renders ONE condensed footer line via `ctx.ui.setStatus`
  — round k/cap · phase (+live idle/model from heartbeats) · findings · reconcile
  totals · terminal outcome. Fades 30min after the last event. Read-only,
  best-effort; inert without a runs dir.

**Deliberately NOT ported**: upstream ADR #62's narration loop (CC
`run_in_background` + ~2-minute orchestrator polls + assistant-text narration) —
pi has no background bash, the loop burns orchestrator context, and it is pure
LLM-behavior contract; every layer above is substrate. The
`csr_progress_gates.py` check 9 asserts `run_in_background` stays ABSENT
(anti-blind-sync guard for future upstream merges).

**Gates**: new `csr_progress_gates.py` (10 checks — upstream 1–8 adapted to the pi
wrapper/wire format + the pi disclosure contract as check 9);
`disconnect_check.py` REQUIRED_FILES + SKILL.md self-check list + install.md
observability section updated (rule 5); `hetero_doc_guards.py` unchanged and
green (behavior-identical without the new flag). Deferred: the `sf-hetero`
dedicated tool (separates wrapper stderr/stdout channels properly + structured
per-provider panel) — rides a csr convergence round before landing, per the
skill's own discipline.

---

## Post-M4 addendum — sf-hetero: the different-family leg as a first-class tool (2026-08-29, later)

The deferred third layer, landed AFTER its proposal converged through csr itself (dogfood —
the artifact `extensions/sf-hetero/docs/sf-hetero.proposal.md` was reviewed by 2× same-family
(fresh-context doc-reviewer) + 2× different-family (minimax-cn/MiniMax-M3) legs;
**substantive_converged: true, 2 rounds, 0 new blockers each** — record
`extensions/sf-hetero/docs/sf-hetero.convergence-record.json`, trail `.convergence.md`;
9 different-family-only findings escalated per the reconcile table with amendments applied —
human confirmation pending, veto = revert the matching proposal hunk + implementation).

What landed:

- `extensions/sf-hetero/` — the `hetero_doc_review` tool, a pure CLIENT of the wrapper (no
  wrapper change): stdout = tool `content` VERBATIM on exit 0 (stream separation — progress
  stderr never enters LLM context, fixing the bash path's parse-last-JSON convention);
  structured live per-provider panel (model/turns/idle/currentTool/costUsd?/heartbeats from
  leg-progress + heartbeat stderr events, 5s ticker); completion semantics per the wrapper's
  exit contract (0 = usable incl. rewrite/degraded — no isError; 1 = fingerprint+tail or
  stderr-verbatim fail-fast; 2 = tail); abort = SIGKILL to the detached process group (exact
  killProcessTree POSIX parity; grandchild inherits the group). Registered in package.json.
- SKILL.md step-2: the tool is the primary path (`artifact`/`authority`/`priorFindings`/
  `progressFile`); the bash invocation stays the documented FALLBACK (harnesses without the
  extension). csr_progress_gates check 9 extended: asserts tool-primary + progressFile +
  FALLBACK + the old assertions.
- e2e verified offline via `dryRun` (C5): content = canned result JSON verbatim, zero
  stderr/progress leakage, isError false; one transient spawn failure surfaced honestly as
  isError exit-2 (empty-output path). tsc strict clean; csr gates 8/8 green post-rewrite.
