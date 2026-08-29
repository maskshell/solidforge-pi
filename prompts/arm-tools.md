---
description: "Arm the current project for Solid Forge — provision arch-configs, optional gate dev-deps, constitution, templates, gitignore; report gate status. Layer 2 (explicit per-project opt-in; the package does not mutate host-project build files, so this is a command, not install)."
argument-hint: "[--with-tools [--lang python|web|rust|swift|java]] [--scaffold-configs [vale,semgrep,spectral]] [--revert [--apply]]"
---

# arm-tools — arm a project for Solid Forge

You are arming the project at the current working directory for the Solid Forge convergence loop. This is **Layer 2** — the explicit, per-project provisioning step. Layer 1 (installing/enabling the solidforge-pi package) already activated the sf-hooks guard + the `solidforge:` agents + the skills; this command provisions the **project-side** files the gates and loop need.

> pi reads the project context file `AGENTS.md` **or** `CLAUDE.md` at startup (same layering). `arm.py` appends to `AGENTS.md` when the project already has one, else `CLAUDE.md` — either lands in the context.

## Step 1 — run the arming script

Run exactly one command. If the user passed `--with-tools` (or asked to install/add the gate tools), append `--with-tools`; otherwise omit it.

```bash
python3 "<skill-dir>/infra/install/arm.py" --with-tools
```

(Without `--with-tools`: `python3 "<skill-dir>/infra/install/arm.py"`.)

`<skill-dir>` is this skill's location as shown in the loaded-skill header above — resolve it from there; do NOT `cd` into the skill dir.

For a polyglot repo where the user wants only ONE language's gate tools, append `--lang <python|web|rust|swift|java>` (only valid with `--with-tools`; default = all detected ecosystems). Example — arm only Python: `python3 "<skill-dir>/infra/install/arm.py" --with-tools --lang python`

If the user wants external-tool configs scaffolded (Vale prose-lint / Semgrep SAST / Spectral OpenAPI), append `--scaffold-configs [vale,semgrep,spectral]` (bare flag = all three; comma-list = subset; independent of `--with-tools`).

The script provisions, for each detected ecosystem at the project root OR nested (bounded walk, depth ≤ 4):

- arch-configs copied to the project root (`.importlinter.ini` Python, `.dependency-cruiser.cjs` Web, `.swiftlint.yml` Swift, `clippy.toml` Rust, `checkstyle.xml` Java) — only for detected languages; never clobbers an existing edited file.
- `--scaffold-configs` only: external-tool config templates copied to the project root (`.vale.ini` / `.semgrep.yml` / `.spectral.yaml`) — sensible STARTING POINTS; never clobbers an existing file. (Vale: run `vale sync` after, or let arming do it.)
- `--with-tools` only: version-matched gate tools added to the project's OWN dev deps (uv/poetry/pipenv/pip/npm/pnpm/yarn) — reversible, idempotent. System-only tools (swiftlint/clippy/cargo-audit/gitleaks/...) are printed as install commands, not mutated.
- L1 Constitution + Gate-Toolchain sections appended to the project context file (once; idempotent).
- intent-blueprint template + cold-start-patterns copied to `docs/intent-blueprints/_templates/`.
- `.gitignore` entries added for the convergence-loop runtime state (`.claude/parallel-dev/loop-state.json`, `.claude/parallel-dev/runs/`, `.claude/parallel-dev/tasks.json`).
- `.env.solidforge.example` — the different-family (异源) adversarial-review secrets placeholder (fill tokens or export them; see the cross-source-review skill's install.md).

## Step 2 — read the gate-status report the script prints

The script prints a toolchain/gate status block (present vs absent per gate tool). Summarize for the user which gates are armed and which degrade (a gate that is absent degrades gracefully — it never reports a silent green).

## Step 3 — language-server advisory (do NOT install yourself)

Solid Forge does NOT install language servers. For each detected language, recommend the matching language-server **binary** install command (the binary must be on `$PATH`; pi does not wire LSP automatically — the per-tool CLI gates in the convergence loop are the deterministic floor):

- Python: `npm install -g pyright` (or `pipx install pyright`).
- Rust: `rustup component add rust-analyzer`.
- Swift: ships with Xcode — `xcrun sourcekit-lsp`.
- Java: Eclipse JDT.LS or `brew install jdtls`.
- TypeScript/Web: `npm install -g typescript typescript-language-server`.

State clearly that installing any of them is optional — opt in per language this project uses.

## Step 4 — report

Tell the user concisely: what was armed (configs, deps if `--with-tools`, constitution, templates, gitignore, and the `.env.solidforge.example` secrets placeholder), which gates are still absent, and the language-server recommendation(s) for this project's languages. Note that the Solid Forge guards are already active (Layer 1) and that `arm.py --revert` (dry-run; add `--apply` to execute) removes only the template-matching provisioned files, preserving any user edits.

Describe each armed artifact by what the tooling itself says about it. The `arm.py` print line names the artifact and the action; if a provisioned template file exists, read its opening comment (the first comment block at the top of the file) for its purpose; otherwise (no template was provisioned, or the header states no purpose) report the artifact by the `arm.py` print line alone — do not guess. Do not relabel an artifact or substitute a concept borrowed from another file in the project; an artifact's identity comes from the tooling, not from a neighboring file.

## Step 5 — optional suggested cross-skill routing snippet (do NOT write it yourself)

Read `<skill-dir>/references/host-routing.md` and print its contents verbatim. Frame it as an OPTIONAL suggested addition to the project's context file: bc / pd / csr self-route via their own Scope Guards regardless, and this snippet only surfaces the csr explicit-invocation gap (csr is explicit-invocation only in Phase A; neither bc nor pd auto-routes to it). arm-tools does NOT write this snippet — unlike the L1 Constitution (which `arm.py` appends), this is print-only and opt-in; the user copies it into their context file only if they want the convention.
