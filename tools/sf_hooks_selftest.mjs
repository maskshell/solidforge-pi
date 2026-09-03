#!/usr/bin/env node
/**
 * sf_hooks_selftest.mjs — seam-level selftest for the sf-hooks bridge
 * (extensions/sf-hooks/index.ts), runnable under bare node >= 22.6 via
 * type-stripping: the extension's only non-node import is
 * `import type { ExtensionAPI }` which strips, so NO pi install is needed.
 *
 * AC seam under test (the tool_call / tool_result boundary pi actually
 * calls): a Python edit/write that ruff would flag must be DENIED at
 * tool_call time — BEFORE the write lands (the 2026-09-03 incident class:
 * FAST-GATE BLOCK fired post-write, the red edit had already been applied,
 * and a contaminated style commit nearly shipped). The post-write block
 * message must state honestly that the edit already landed.
 *
 * Usage: node tools/sf_hooks_selftest.mjs   (requires python3 + ruff on PATH)
 */

import { chmodSync, mkdirSync, mkdtempSync, readFileSync, rmSync, statSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import path from "node:path";

const results = [];
const check = (name, ok, detail = "") => {
	results.push({ name, ok });
	console.log(`${ok ? "PASS" : "FAIL"}  ${name}${detail ? ` — ${detail}` : ""}`);
};

const ext = await import(new URL("../extensions/sf-hooks/index.ts", import.meta.url).href);
const handlers = {};
const pi = { on: (evt, cb) => (handlers[evt] = cb) };
ext.default(pi);
check("extension registers tool_call + tool_result handlers", !!handlers.tool_call && !!handlers.tool_result);

const tmp = mkdtempSync(path.join(tmpdir(), "sf-hooks-selftest-"));
const ctx = { cwd: tmp };
try {
	// --- AC1: red python EDIT denied pre-write, file untouched ---
	const badPy = path.join(tmp, "bad.py");
	writeFileSync(badPy, "x = 1\n");
	const r1 = await handlers.tool_call(
		{ toolName: "edit", input: { path: badPy, edits: [{ oldText: "x = 1", newText: "if True:x=2" }] } },
		ctx,
	);
	check("AC1 red-python edit denied at tool_call", !!r1?.block, JSON.stringify(r1 ?? "no-block"));
	check("AC1 file untouched after deny", readFileSync(badPy, "utf8") === "x = 1\n");

	// --- AC2: red python WRITE denied ---
	const r2 = await handlers.tool_call(
		{ toolName: "write", input: { path: path.join(tmp, "w.py"), content: "def f( ) :\n  pass \n" } },
		ctx,
	);
	check("AC2 red-python write denied at tool_call", !!r2?.block, JSON.stringify(r2 ?? "no-block"));

	// --- AC3: clean python edit passes (no false positives) ---
	const okPy = path.join(tmp, "ok.py");
	writeFileSync(okPy, "a = 1\n");
	const r3 = await handlers.tool_call(
		{ toolName: "edit", input: { path: okPy, edits: [{ oldText: "a = 1", newText: "a = 2" }] } },
		ctx,
	);
	check("AC3 clean python edit allowed", !r3?.block, JSON.stringify(r3 ?? "allowed"));

	// --- AC4: non-python files are not pre-linted ---
	const js = path.join(tmp, "x.js");
	writeFileSync(js, "const x = 1\n");
	const r4 = await handlers.tool_call(
		{ toolName: "edit", input: { path: js, edits: [{ oldText: "const x = 1", newText: "if(true){const x=1}" }] } },
		ctx,
	);
	check("AC4 non-python edit allowed", !r4?.block);

	// --- AC5: post-write block message states the edit already landed ---
	// (fixture is a real red file, so fast_gate reports a genuine lint finding,
	// not a missing-file error — decouples AC5 from fast_gate's missing-file path)
	const postPy = path.join(tmp, "post.py");
	writeFileSync(postPy, "if True:a=1\n"); // the post-edit on-disk state: genuinely red
	const r5 = await handlers.tool_result(
		{ toolName: "edit", input: { path: postPy, edits: [{ oldText: "a = 1", newText: "if True:a=1" }] } },
		ctx,
	);
	const postText = Array.isArray(r5?.content) ? String(r5.content[0]?.text ?? "") : "";
	check(
		"AC5 post block message discloses edit-already-applied",
		r5?.isError === true && /already applied/i.test(postText),
		JSON.stringify(postText.slice(0, 120)),
	);
	// --- AC6: a HUNG ruff degrades to ALLOW (never deny on timeout) ---
	const fakeBin = path.join(tmp, "fakebin");
	mkdirSync(fakeBin);
	writeFileSync(path.join(fakeBin, "ruff"), "#!/bin/sh\nsleep 30\n");
	chmodSync(path.join(fakeBin, "ruff"), 0o755);
	const realPath = process.env.PATH;
	process.env.PATH = `${fakeBin}:${realPath}`;
	const t0 = Date.now();
	let r6;
	try {
		r6 = await handlers.tool_call(
			{ toolName: "edit", input: { path: okPy, edits: [{ oldText: "a = 1", newText: "a = 3" }] } },
			ctx,
		);
	} finally {
		process.env.PATH = realPath;
	}
	check(
		"AC6 hung ruff (timeout) degrades to allow",
		!r6?.block && Date.now() - t0 < 15_000,
		`block=${JSON.stringify(r6 ?? null)} elapsed=${Date.now() - t0}ms`,
	);

	// --- AC7: ruff ABSENT degrades to allow (ENOENT) ---
	process.env.PATH = tmp; // no ruff, no python3 — pre-hooks also degrade silently
	let r7;
	try {
		r7 = await handlers.tool_call(
			{ toolName: "edit", input: { path: okPy, edits: [{ oldText: "a = 1", newText: "a = 4" }] } },
			ctx,
		);
	} finally {
		process.env.PATH = realPath;
	}
	check("AC7 ruff absent (ENOENT) degrades to allow", !r7?.block, JSON.stringify(r7 ?? "allowed"));
} finally {
	rmSync(tmp, { recursive: true, force: true });
}

const failed = results.filter((r) => !r.ok);
console.log(failed.length ? `\n${failed.length} FAILED / ${results.length}` : `\nALL ${results.length} PASS`);
process.exit(failed.length ? 1 : 0);
