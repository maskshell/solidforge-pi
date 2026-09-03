# pi-internals-anchors — substrate behaviors this package deliberately relies on

> Verified against **pi 0.84.x** (source: `dist/core/package-manager.js`, `dist/core/extensions/loader.js`, `dist/core/pi-manifest.js`). Pi is an external substrate moving on its own cadence; these are INTERNALS, not contract. **Re-verify on every pi major/minor bump** (the CI pins — `PI_REF` in `.github/workflows/ci.yml` and `npm-publish.yml` — are the bump points). Each anchor names the package behavior that depends on it.

## A1 — Manifest entries are the ONLY discovery universe for packages

`collectFilesFromManifestEntries` expands manifest entries (non-glob → path resolve; glob → `expandPackageGlob` with explicit `.sort()`); nothing enumerates `extensions/` unless an entry points at it. Consequences we rely on:

- An **unlisted extension dir is structurally invisible**: silent no-load, AND invisible to a user's settings `+path` force-include (the filter universe `collectManifestFiles` is itself manifest-derived).
- Guard: `pi_loader_smoke.py` check `extensions-registered` (direction B) blocks a release with an unregistered discoverable unit.

## A2 — Directory entries: index-first, one level, no sort

`resolveExtensionEntries(dir)`: a dir's own `package.json`(pi) or `index.ts` wins, no descent; otherwise `collectAutoExtensionEntries` walks ONE level in `readdirSync` order (**unsorted, filesystem-dependent** — the docs' "lexical order" promise is carried only by glob entries via `.sort()`).

- Our enumerated manifest keeps **author-controlled load order**; a single `./extensions` entry would not (and on Linux hash-order readdir it can be arbitrary).
- **Barrel hijack**: a top-level `extensions/index.ts` collapses a `./extensions` entry to count=1 (all `sf-*` silently unload). The enumerated form is immune — this is a deliberate reason we do NOT use `"./extensions"`.

## A3 — `pi.namespace` semantics

`readPiManifest` passes `pi.namespace` through; resource loaders compose `/<ns>:<name>` for skills/prompts at load; agent definitions are NOT a core resource type — extensions ship their own agents and should read `pi.namespace` themselves (packages.md). We do: `sf-subagents/agents.ts` `getPackageNamespace()` composes `<ns>:<name>` for package-source agents (idempotent vs legacy prefixed files); frontmatter stays bare.

## A4 — Extension loading: jiti transpile + factory init

`loadExtensions(paths, cwd)` imports each entry through jiti and calls the default-export factory; errors land in `result.errors` (non-fatal to the session). Guards: `tools/pi_extensions_load_smoke.mjs` (headless, CI `loader-e2e` job) + the authenticated `pi -e <repo> -p` probe (manual).

## A5 — PostToolUse blocks cannot un-write

pi's `tool_result` handler return (`isError` + feedback) informs the NEXT turn — the write has already landed. That is why `sf-hooks` runs its python pre-lint at `tool_call` (deny BEFORE the write) and why the post-path `fast_gate` message explicitly discloses "the edit already applied" (2026-09-03 contaminated-commit incident class).
