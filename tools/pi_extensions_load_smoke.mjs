#!/usr/bin/env node
/**
 * pi_extensions_load_smoke.mjs — load ALL package extensions through pi's
 * REAL extension loader (jiti transpile + factory init), headless — no model
 * auth, no TUI. Complements pi_loader_smoke.py (skills/prompts/manifest):
 * that gate proves resource discovery; this one proves the extension FILES
 * import and initialize (activate) under pi's own transpiler.
 *
 * The authless approximation of the `pi -e` install-path probe (which needs
 * model credentials and therefore cannot run in CI): same loader, same
 * transpiler, same factory-init call — minus the LLM turn.
 *
 * Setup: the repo needs @earendil-works/pi-coding-agent resolvable from the
 * extension files (bare-specifier imports). CI/locally:
 *   mkdir -p node_modules/@earendil-works
 *   ln -sfn "$PI_PKG_ROOT" node_modules/@earendil-works/pi-coding-agent
 *
 * Usage: PI_PKG_ROOT=<pi package root> node tools/pi_extensions_load_smoke.mjs
 */

import * as fs from "node:fs";
import * as path from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

const repo = path.dirname(path.dirname(fileURLToPath(import.meta.url)));
const piRoot = process.env.PI_PKG_ROOT;
if (!piRoot || !fs.existsSync(path.join(piRoot, "dist", "core", "extensions", "loader.js"))) {
	console.error("PI_PKG_ROOT must point at an installed @earendil-works/pi-coding-agent (dist/core/extensions/loader.js)");
	process.exit(1);
}

// Manifest extension dirs -> entry files (mirrors pi's resolveExtensionEntries:
// dir with index.ts; pi receives FILES at this stage, not dirs).
const manifest = JSON.parse(fs.readFileSync(path.join(repo, "package.json"), "utf-8"));
const entryFiles = [];
for (const entry of manifest.pi?.extensions ?? []) {
	const dir = path.join(repo, entry.replace(/^\.\//, ""));
	for (const index of ["index.ts", "index.js"]) {
		const p = path.join(dir, index);
		if (fs.existsSync(p)) {
			entryFiles.push(p);
			break;
		}
	}
}
if (entryFiles.length === 0) {
	console.error("FAIL no extension entry files resolved from pi.extensions");
	process.exit(1);
}

const { loadExtensions } = await import(
	pathToFileURL(path.join(piRoot, "dist", "core", "extensions", "loader.js")).href
);

// Explicit exit below: some extensions may arm timers at init (sf-progress
// poller); the assertions must terminate the process regardless.
const result = await loadExtensions(entryFiles, repo);
const loaded = result.extensions ?? [];
const errors = result.errors ?? [];
for (const e of loaded) console.log(`loaded: ${String(e.path ?? e.name ?? "?").replace(`${repo}/`, "")}`);
for (const e of errors) console.error(`error: ${e.path}: ${e.error}`);

const ok = loaded.length === entryFiles.length && errors.length === 0;
console.log(ok ? `ALL ${entryFiles.length} EXTENSIONS LOAD+INIT CLEAN` : `FAIL ${loaded.length}/${entryFiles.length} loaded, ${errors.length} errors`);
process.exit(ok ? 0 : 1);
