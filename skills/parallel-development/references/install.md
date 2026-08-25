# Deterministic Infrastructure (Plugin Layers)

The convergence loop's deterministic gates ship inside the skill at `infra/` and are activated OPT-IN via the **Solid Forge plugin**. There are two layers:

- **Layer 1 — Enable the plugin.** Activates the skills, the scoped subagents, and the hooks (the global plugin never fires hooks until it is enabled in a project).
- **Layer 2 — Arm the project** (`/solidforge:arm-tools`, backed by `arm.py`). Provisions the PROJECT-SIDE files the gates and loop need. Plugins do not mutate host-project build files, so this is a deliberate per-project command, not part of enable.

The hook + orchestration scripts run from the **plugin root** and operate on `$CLAUDE_PROJECT_DIR` — they are NOT copied into each target project. Only the project-side artifacts (arch-configs, constitution note, templates, gate dev-deps) are provisioned by Layer 2.

## Prerequisite

`python3` on PATH (required). All hook/script logic is stdlib-only; external tooling (ruff, import-linter, swiftlint, dependency-cruiser, ...) is detected at run time and a missing tool degrades its gate to a documented no-op (never a silent green).

## Layer 1 — Enable the plugin

Local dev (no marketplace):

```bash
claude --plugin-dir <path-to-solidforge>
```

Or via a marketplace / `--plugin-url`. Then enable per project (`/plugin`) or globally. Enabling activates the three hooks (`blueprint_guard.py`, `counters.py` PreToolUse; `fast_gate.py` PostToolUse), the 13 scoped subagents, and the two skills. Plugin agents are priority 5; user `~/.claude/agents/` same-named globals take precedence, so the skills spawn the plugin agents by their scoped names (`solidforge:<name>`).

## Layer 2 — Arm a project

```cli
/solidforge:arm-tools [--with-tools]
```

Or directly:

```bash
python3 <plugin-root>/skills/parallel-development/infra/install/arm.py <project-dir> [--with-tools]
```

`<project-dir>` defaults to `$CLAUDE_PROJECT_DIR` or the current directory.

`--with-tools` (optional): add the gate tools to the PROJECT's own dev dependencies so the gates are armed. Project-local (no global install). See [Gate tools (--with-tools)](#gate-tools---with-tools) below.

What arming does (idempotent — safe to re-run):

- Copies each language's arch-contract config template to the project root **only if that language's toolchain is detected** (`.importlinter.ini` for Python, `.dependency-cruiser.cjs` for Web/TS, `.swiftlint.yml` for Swift, `clippy.toml` for Rust, `checkstyle.xml` for Java, `.golangci.yml` for Go); configs for absent languages are skipped. Detection is recursive — a marker at the repo root OR nested (a `frontend/` subdir, a `backend/` subdir, a monorepo package) counts, so a mixed-layout repo gets every side's config. Existing files are never clobbered. **Neutral by default (ADR #49):** `.importlinter.ini`, `.dependency-cruiser.cjs`, `.swiftlint.yml` ship with their layer/boundary contracts COMMENTED OUT — a freshly-armed gate is GREEN (0 active contracts = nothing to violate). The Python root package is auto-detected (`pyproject.toml [project] name` / src-layout / flat-layout) and substituted into `.importlinter.ini`'s `root_package`; detection failure leaves `__REPLACE_ME__` (set it manually). Uncomment + edit the `[importlinter:contract:*]` / layer-rule / `custom_rules` blocks to enforce YOUR architecture — the gate is green until you opt in.
- `--scaffold-configs [vale,semgrep,spectral]` only: copies external-tool config templates (`.vale.ini` / `.semgrep.yml` / `.spectral.yaml`) to the project root — sensible STARTING POINTS for the Vale/Semgrep/Spectral gates (Vale hard-no-ops without one; Semgrep/Spectral gain offline-determinism / editability). Bare flag = all three; NOT language-bound, opt in explicitly. When `vale` is scaffolded and `vale` is on `$PATH`, arming also runs `vale sync` to fetch the style packages (the gate no-ops without them). Existing files are never clobbered; `--revert --apply` removes only those still matching the template.
- Copies the Intent Blueprint template + cold-start patterns -> `<project>/docs/intent-blueprints/_templates/`.
- Appends the L1 Constitution section to `<project>/CLAUDE.md` if absent (and, with `--with-tools`, the Gate-Toolchain note).
- Adds `.claude/parallel-dev/loop-state.json`, `.claude/parallel-dev/runs/`, `.env`, and `.env.solidforge` to `.gitignore` (derived loop state + the secrets files, never committed).
- Copies `.env.solidforge.example` to the project root (the Solid Forge different-family secrets placeholder — namespaced so it never collides with your own `.env.example`). Opt into different-family by `cp .env.solidforge.example .env.solidforge` + filling `<UPPERCASE-PROVIDER>_ANTHROPIC_AUTH_TOKEN` — the SOLE token source (the provider's native `<FILENAME>_API_KEY` is never read; see namespace isolation in [model-routing.md](model-routing.md)) — or put the vars in your shell / `.env` (the wrapper reads all three). The `.example` is committed (no real tokens); `.env.solidforge` is gitignored.
- Prints an LSP / code-intelligence advisory: per detected language, recommends the matching official LSP **plugin** (a Claude Code plugin whose install state arm cannot probe — shown even when already installed; ignore if so) and the LSP **binary** install command only when that binary is not already on `$PATH` (avoids a redundant hint — `report_gates` separately covers the gate type-checkers pyright/tsc). Does NOT install language servers.
- Reports which gates are active vs degraded.

## Gate tools (--with-tools)

The gates must run the SAME tool versions the project declares, so `--with-tools` adds the gate tools to the project's own dev dependencies (version-matched, reversible) rather than installing a global copy (`uv tool install` / `brew` / `npm -g` would version-diverge from the project).

Per detected ecosystem:

- Python (uv): `uv add --dev ruff import-linter pylint pyright pip-audit pytest-json-report` (creates `uv.lock`; installs into `.venv`).
- Python (poetry): `poetry add --group dev ruff import-linter pylint pyright pip-audit pytest-json-report`.
- Python (pipenv): `pipenv install --dev ruff import-linter pylint pyright pip-audit pytest-json-report`.
- Python (pip): appends those packages to `requirements-dev.txt` (or `requirements.txt`) if present; otherwise prints the line to add.
- Web (npm/pnpm/yarn): `<pm> add -D dependency-cruiser eslint typescript vitest` (project-local, not global).
- Swift: SwiftLint is a system linter, not a project dep — arming prints the install command (`brew install swiftlint` or `mint install realm/swiftlint`) without running it.
- Rust (system toolchain, printed not run): `rustup component add clippy rustfmt`, plus `cargo install cargo-audit` (supply-chain gate) and `cargo install cargo-nextest` (test gate, structured JUnit XML).
- Go (system toolchain, printed not run): `brew install go` (or the official installer; ships `gofmt`/`go vet`/`go build`/`-race`), `brew install golangci-lint` or `go install github.com/golangci/golangci-lint/cmd/golangci-lint@latest` (arch gate: depguard layer rules), `go install golang.org/x/vuln/cmd/govulncheck@latest` (supply-chain gate).
- Cross-language (system, printed not run): `brew install gitleaks` (or `cargo install gitleaks`) — secrets gate; runs for any ecosystem.

The gate scripts resolve project-pinned tools so the gate runs the project's declared version: **Python** tools resolve PATH first (an activated venv is on PATH), then the project's local venv bins (`.venv/bin`, `venv/bin`, `env/bin`) as a fallback when the venv isn't active; **Web** tools resolve the project's `node_modules/.bin` FIRST (`node_modules/.bin` is never on PATH, unlike an activated venv), then PATH. A tool still absent degrades its gate to a documented no-op (never silently green). (External-skill companion gates resolve PATH/global — those tools aren't version-coupled to the project; see "Arming external-skill gates" below.)

Re-run `--with-tools` any time; the package managers are idempotent on already-present deps.

## Arming external-skill gates (companion system tools)

Unlike the first-party gates above (project-pinned via `--with-tools` so they match the project's declared versions), the external-skill gates wrap **companion system tools** — standalone linters/scanners reused across projects. Install these **globally** (not project-local); where a Homebrew formula exists, **prefer `brew install`**. The adapters detect the tool on PATH and degrade to a coverage-noted no-op when absent (never silently green).

| Tool | Gate | Preferred (Homebrew) | Global alternative |
| --- | --- | --- | --- |
| Spectral | `spectral-openapi` | `brew install spectral-cli` | `npm install -g @stoplight/spectral-cli` |
| Semgrep | `semgrep-sast` | `brew install semgrep` | `pip install semgrep` |
| Vale | `vale-prose` | `brew install vale` | GitHub release (vale.sh) |
| oasdiff | `openapi-breaking` | `brew install oasdiff` | `go install github.com/oasdiff/oasdiff@latest` |
| Trivy | `license-compliance` | `brew install trivy` | install script (aquasecurity.github.io/trivy) |
| Checkov | `iac-misconfig` | `brew install checkov` | `pip install checkov` |

Impeccable is the exception — it is a skill (not a standalone CLI): arm it via `npx impeccable install` into the project's `.claude/skills/impeccable/`. Its detector (`detect.mjs`) is not a global binary.

## What each gate does

| Gate | When | Mechanism | Failure behavior |
| --- | --- | --- | --- |
| Fast gate (`fast_gate.py`) | Every Edit/Write | PostToolUse hook; per-file lint (Blocker, fix-in-ring) + format (Blocker, commit-stratified remediation — [commit-stratification.md](commit-stratification.md)); format-emitting checks: Python/Java/Go/Rust; Swift/Web/Python are lint | `decision:block` + reason; Claude self-corrects next turn; inner short-circuit |
| Blueprint guard (`blueprint_guard.py`) | Edit/Write to a frozen blueprint | PreToolUse hook | `permissionDecision:deny`; edit blocked |
| Counters (`counters.py`) | Edit/Write while terminal | PreToolUse hook | `permissionDecision:deny`; a suspended/hard_terminated task cannot keep editing |
| Architecture-contract gate (`arch_contract_<platform>.py`) | Inner convergence point (explicit) | Script | Blocker exit + 越权日志; stays inner. Python/Web also run a type-check (pyright / tsc); Go's type-check is the compiler (`go build`/`go vet`). Detection is recursive (root OR nested); a nested frontend/backend is gated per-marker-dir. |
| Supply-chain gate (`arch_contract_deps.py`) | Inner convergence point (explicit) | Script | leaked secrets (gitleaks) + dep vulnerabilities (pip-audit / npm audit / cargo audit / OWASP dependency-check for Java / govulncheck for Go); Blocker exit + 越权日志. Secret values are redacted. Per-marker-dir. |
| Test gate (`arch_contract_tests.py`) | Inner convergence point (explicit) | Script | failing tests (pytest --json-report / vitest --reporter=json / nextest --junit-out or cargo test / swift test / mvn or gradle test via JUnit XML / go test -race -json for Go) → Blocker; AND the AC→test-name set gate — reads the frozen Intent Blueprint's AC→test mapping, collects per-language test names (pytest --collect-only / cargo test -- --list / go test -list / vitest list), Blocks on any declared name missing from the collected set (rule `test-name-missing`; blocks naked "delete the failing test"); degrades to a coverage-noted no-op when the blueprint has no mapping (rule 3); AND the per-language coverage gate (P3) — measures execution coverage (pytest-cov / go test -coverprofile / cargo tarpaulin / vitest --coverage), emits a `coverage-below-threshold` WARNING only when the blueprint declares an NFR coverage floor (measure-only default; rule 3; warning not Blocker — execution coverage, not assertion quality). 越权日志. Per-marker-dir. |
| API-contract gate (`arch_contract_api.py`) | Inner convergence point (explicit; mixed FE+BE repos) | Script | frontend↔backend API consistency: OpenAPI presence, generated-client freshness, fetch/axios path consistency. `warning`-level 越权日志 (advisory v1). |
| External-skill design gate (`impeccable_detect_adapter.py` + Impeccable hook) | Inner convergence point + per-edit (when armed) | External skill | `npx impeccable install` arms a 44-rule deterministic detector (PostToolUse hook, per-edit advisory) + the convergence adapter (`impeccable_detect_adapter.py` shells out to the armed `detect.mjs --json`, loads the frozen DESIGN.md, → 越权日志). `warning`-level (advisory). See [external-skills.md](external-skills.md). |
| External-skill API-ruleset gate (`spectral_adapter.py`) | Inner convergence point (when armed) | External skill | `brew install spectral-cli` (or `npm i -g @stoplight/spectral-cli`) arms Stoplight Spectral; the convergence adapter (`spectral_adapter.py` shells out to `spectral lint -f json`, → 越权日志) lints the OpenAPI/Swagger spec against `spectral:oas` + `.spectral.yaml`. `warning`-level (advisory); complementary to `arch-contract-api` (presence/path). See [external-skills.md](external-skills.md). |
| External-skill SAST gate (`semgrep_adapter.py`) | Inner convergence point (when armed) | External skill | `brew install semgrep` (or `pip install semgrep`) arms Semgrep; the convergence adapter (`semgrep_adapter.py` shells out to `semgrep --json --config <ruleset>`, → 越权日志) scans source for CVE-pattern code (`.semgrep/` ruleset or `--config auto`). `warning`-level (advisory); complementary to `/security-review` (LLM) + `arch-contract-deps` (secrets/CVEs). See [external-skills.md](external-skills.md). |
| External-skill prose gate (`vale_adapter.py`) | Inner convergence point (when armed) | External skill | `brew install vale` / GitHub release arms Vale; the convergence adapter (`vale_adapter.py` shells out to `vale --format=JSON`, → 越权日志) lints docs prose (terminology/voice/spelling/inclusiveness) against `.vale.ini` + `styles/`. `warning`-level (advisory); fills the docs-quality axis (blueprint-crafting checks doc structure, not prose). See [external-skills.md](external-skills.md). |
| External-skill breaking-change gate (`oasdiff_adapter.py`) | Inner convergence point (when armed) | External skill | `brew install oasdiff` arms oasdiff; the convergence adapter (`oasdiff_adapter.py` shells out to `oasdiff breaking --format json`, → 越权日志) diffs each tracked OpenAPI/Swagger spec against its git HEAD version. `warning`-level (advisory); complementary to Spectral (style) + `arch-contract-api` (presence/path) — the backward-compat axis. See [external-skills.md](external-skills.md). |
| External-skill license gate (`license_adapter.py`) | Inner convergence point (when armed) | External skill | `brew install trivy` arms Trivy; the convergence adapter (`license_adapter.py` shells out to `trivy fs --scanners license --format json`, → 越权日志) inventories dependency licenses from lockfiles. `warning`-level (advisory); complementary to `arch-contract-deps` (secrets/CVEs) — the license-compliance axis. See [external-skills.md](external-skills.md). |
| External-skill IaC gate (`iac_adapter.py`) | Inner convergence point (when armed) | External skill | `brew install checkov` / `pip install checkov` arms Checkov; the convergence adapter (`iac_adapter.py` shells out to `checkov --directory <root> --output json`, → 越权日志) scans Terraform/K8s/Dockerfile for misconfig. `warning`-level (advisory); no-op when no IaC files (opt-in for infra-bearing projects). See [external-skills.md](external-skills.md). |
| loop-state (`loop_state.py`) | Orchestrator + gates | State file | Breaker -> degrade/escalate/suspend/hard-terminate |
| snapshot (`snapshot.py`) | Inner convergence / drift rollback | Script (git refs) | restore working tree to snapshot |
| different-family adversarial review (`hetero_review.py`) | Outer ring, **opt-in** (high-stakes items only; ADR #40) | Non-interactive CC subprocess on a DIFFERENT model family (e.g. DeepSeek via `profiles/<backend>.json`) — additive second opinion over the same-family `code-reviewer` primary | findings → reconciliation (both/same-family-only/different-family-only/neither); cap-hit → `record-outer --verdict adversarial-stalemate` + escalate to human (NEVER silent-pick). See [model-routing.md](model-routing.md) + [convergent-loop.md](convergent-loop.md) § different-family adversarial review. |

## Revert (project-side inverse of arming)

`arm.py --revert` removes ONLY the project-side files arming provisioned. DRY-RUN by default; `--apply` executes:

```bash
python3 <plugin-root>/skills/parallel-development/infra/install/arm.py <project> --revert
python3 <plugin-root>/skills/parallel-development/infra/install/arm.py <project> --revert --apply
```

`--revert --apply` removes:

- arch-configs (`.importlinter.ini` etc.) — ONLY if they still match the template (the auto-detected `root_package` token in `.importlinter.ini` is normalized back to `__REPLACE_ME__` for the compare, so a freshly-armed unedited config IS removable; any OTHER edit = customized). A config you edited is yours: it is KEPT and the revert warns about it; remove it manually if you want.
- The L1 Constitution and Gate-Toolchain sections in `CLAUDE.md`.
- The arming-copied blueprint templates under `docs/intent-blueprints/_templates/`.
- The `.gitignore` parallel-dev entries (loop-state + runs/) + the `.env` + `.env.solidforge` entries.
- The provisioned `.env.solidforge.example` (ONLY if it still matches the template byte-for-byte; one you edited is KEPT + warned).

`--revert` is exclusive of `--with-tools`; `--apply` only takes effect under `--revert`.
It does NOT touch the hooks (those are plugin-level — disable the plugin for that) or any user-owned file.

## Disable hooks

To stop the hooks firing, disable the Solid Forge plugin (project or user scope) via `/plugin`. Disabling touches nothing on disk — it just deactivates the hooks/agents/skills. The skill's prompt-based loop still runs without the plugin (it just loses determinism).

## Upgrade

There is no per-project reconciler. The plugin model replaces the old vendored-snapshot upgrade with **plugin update**: bump the plugin (marketplace re-install, or re-`--plugin-dir` from the updated repo), then re-arm each project (`/solidforge:arm-tools`) to re-provision arch-configs / constitution / templates if the skill text changed. arch-configs you edited are preserved (re-arm never clobbers an existing file).

## Self-checks (the skill's own definition of done)

Before committing a skill change, the deterministic inner ring must pass green:

- `python3 infra/test/disconnect_check.py` — structural + loading-chain integrity.
- `python3 infra/test/smoke_gates.py` — arch-gate behavior (skips languages whose tools are absent).
- `python3 infra/test/lint_self.py` — the skill lints its own infra (Python with `ruff`; markdown docs with `markdownlint`). Both are dev tools that SKIP with a coverage note when absent (never silently green): `brew install ruff markdownlint-cli`.
- `python3 infra/test/arm_copy_config.py` — arch-config gating + arm idempotency.
- `python3 infra/test/arm_report_gates.py` — gate-status report + LSP advisory.
- `python3 infra/test/arm_revert.py` — `--revert` reversibility (keeps user edits).
- `python3 infra/test/plugin_layout.py` — plugin.json + hooks.json + agents well-formed.
- `python3 infra/test/violation_log_schema.py` — violation-log schema validator self-test.
- `python3 infra/test/arch_deps_parsers.py` — supply-chain gate parsers (offline canned JSON).
- `python3 infra/test/arch_tests_parsers.py` — test gate parsers (offline canned JSON/JUnit/text).
- `python3 infra/test/drift_check.py` — rule-7 boilerplate drift across duplicated helpers (advisory warning; `docs/design-pattern-review-value.md` D3).
- `python3 infra/test/adapter_shape_check.py` — `*_adapter.py` violation-log shape contract (blocker).
- `python3 infra/test/arch_contract_java_test.py` — `arch_contract_java` checkstyle rc-handling (no silent green on rc>=2 / non-XML).

## Customize architecture contracts

Edit the copied configs in the project root:

- Python layers/forbidden: `.importlinter.ini`.
- Web circular/layer rules: `.dependency-cruiser.cjs`.
- Swift custom rules: `.swiftlint.yml`.
- Rust clippy lints: `clippy.toml`.
- Go layer rules + linters: `.golangci.yml` (depguard layer rules complement Go's `internal/` compiler boundary).

These are the codable L1 red lines for THIS project. Tune them to match the project's layering; the gate enforces whatever they declare.

## Budgets and thresholds

Defaults (overridable via `loop_state.py init` flags):

- Inner iteration cap M = 8
- Thrashing threshold N = 3 (same fingerprint)
- Token cap T = 2,000,000 (approximate — see note)
- Time cap W = 1800s (reliable axis)
- Cost cap C = 5.0

Token budget cannot be read precisely by hooks; the time budget is the reliable hard axis. Tune `--time-cap` / `--cost-cap` per project. For different-family (non-Anthropic) legs the `--cost-cap` USD is a structural fiction (the API returns tokens, not price; CC's USD ≠ provider spend) — it is a runaway backstop, not real cost; the provider-independent bounds are the step cap + round count (ADR #42).
