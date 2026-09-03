#!/usr/bin/env node
/**
 * pi_namespace_smoke.mjs — namespace composition smoke against a
 * pi.namespace-CAPABLE build. The package's flagship surface (every SKILL.md
 * reference, the /solidforge:arm-tools invocation, the install instructions)
 * depends on `pi.namespace: "solidforge"` composing `solidforge:<base>` skill
 * names — but the OFFICIAL pi (as of 0.84.4) lacks pi.namespace; the feature
 * ships in the maskshell/pi fork (earendil-works/pi#8834). The other smokes
 * run namespace-blind against official pi; this one closes that gap at the
 * resource-loader layer.
 *
 * #8834 landing detector: when official pi gains pi.namespace, point this
 * job's install at the official package — the assertions are build-agnostic.
 *
 * Usage: PI_PKG_ROOT=<namespace-capable pi package root> node tools/pi_namespace_smoke.mjs
 */

import * as fs from "node:fs";
import * as path from "node:path";
import { pathToFileURL } from "node:url";

const repo = path.dirname(path.dirname(new URL(import.meta.url).pathname));
const piRoot = process.env.PI_PKG_ROOT;
if (!piRoot || !fs.existsSync(path.join(piRoot, "dist", "core", "skills.js"))) {
	console.error("PI_PKG_ROOT must point at an installed pi package (dist/core/skills.js)");
	process.exit(1);
}

const EXPECTED_BASES = new Set([
	"blueprint-crafting",
	"cross-source-review",
	"parallel-development",
	"primary-source-verification",
	"prior-art-search",
]);

const results = [];
const check = (name, ok, detail = "") => {
	results.push({ name, ok });
	console.log(`${ok ? "PASS" : "FAIL"}  ${name}${detail ? ` — ${detail}` : ""}`);
};

const manifest = JSON.parse(fs.readFileSync(path.join(repo, "package.json"), "utf-8"));
const ns = manifest.pi?.namespace;
check("manifest declares pi.namespace", ns === "solidforge", `ns=${JSON.stringify(ns)}`);

const skills = await import(pathToFileURL(path.join(piRoot, "dist", "core", "skills.js")).href);
if (typeof skills.validateNamespaceValue !== "function" || typeof skills.loadSkills !== "function") {
	console.error(
		"FAIL the PI_PKG_ROOT build has no namespace support (validateNamespaceValue/loadSkills signature) — official pi without pi.namespace? This smoke needs the namespace-capable build; when earendil-works/pi#8834 lands, repoint the job at official pi."
	);
	process.exit(1);
}

check("namespace value validates", skills.validateNamespaceValue(ns).length === 0);
check(
	"invalid namespace is rejected (negative control)",
	skills.validateNamespaceValue("Bad__ns").length > 0
);

const skillsDir = path.join(repo, "skills");
const opts = {
	cwd: repo,
	agentDir: path.join(repo, ".ns-smoke-no-agent-dir"),
	skillPaths: [skillsDir],
	includeDefaults: false,
};

const composed = skills.loadSkills({ ...opts, namespaces: [{ path: skillsDir, namespace: ns }] });
check("composed load: zero diagnostics", composed.diagnostics.length === 0);
check("composed load: exactly 5 skills", composed.skills.length === 5);
const allComposed = composed.skills.every(
	(s) => s.name === `${ns}:${s.baseName}` && s.namespace === ns && EXPECTED_BASES.has(s.baseName)
);
check(
	"every skill name is solidforge:<base> with namespace metadata",
	allComposed,
	composed.skills.map((s) => s.name).join(", ")
);

const bare = skills.loadSkills({ ...opts, namespaces: [] });
check(
	"negative control: without the association the SAME loader yields bare names",
	bare.skills.length === 5 && bare.skills.every((s) => s.name === s.baseName || !s.name.includes(":")),
	bare.skills.map((s) => s.name).join(", ")
);

const failed = results.filter((r) => !r.ok);
console.log(failed.length ? `\n${failed.length} FAILED / ${results.length}` : `\nALL ${results.length} PASS`);
process.exit(failed.length ? 1 : 0);
