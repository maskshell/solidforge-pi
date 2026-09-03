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

import * as fs from "node:fs";
import { tmpdir } from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";

const { chmodSync, mkdirSync, mkdtempSync, readdirSync, readFileSync, rmSync, statSync, writeFileSync } = fs;

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
	// --- AC6: runCmd TIMEOUT is a hard bound (direct unit test of the exact
	// M1/M2 mechanics: a hung binary must resolve IMMEDIATELY, flagged, not
	// deny-shaped and not close-blocking) ---
	const fakeBin2 = path.join(tmp, "fakebin2");
	mkdirSync(fakeBin2);
	const hungRuff = path.join(fakeBin2, "hung");
	writeFileSync(hungRuff, "#!/bin/sh\nsleep 30\n");
	chmodSync(hungRuff, 0o755);
	const t0 = Date.now();
	const r6 = await ext.runCmd(hungRuff, ["--version"], tmp, 1_000);
	const r6ms = Date.now() - t0;
	check(
		"AC6 hung binary: timedOut flag + immediate resolve",
		r6 !== null && r6.timedOut === true && r6.ok === false && r6ms < 15_000,
		`result=${JSON.stringify(r6)} elapsed=${r6ms}ms`,
	);

	// --- AC7: runCmd ENOENT degrades to null (caller allows) ---
	const r7 = await ext.runCmd("definitely-not-a-binary-xyz", [], tmp, 1_000);
	check("AC7 absent binary (ENOENT) yields null", r7 === null, JSON.stringify(r7));

	// --- AC9: ruff resolution is cached ONCE — a later PATH strip cannot
	// un-resolve it (the deny still fires via the cached absolute binary) ---
	const realPath = process.env.PATH;
	process.env.PATH = tmp; // ruff's dir no longer on PATH
	let r9;
	try {
		r9 = await handlers.tool_call(
			{ toolName: "edit", input: { path: okPy, edits: [{ oldText: "a = 1", newText: "if True:a=1" }] } },
			ctx,
		);
	} finally {
		process.env.PATH = realPath;
	}
	check(
		"AC9 cached absolute ruff keeps the gate alive under a PATH strip",
		!!r9?.block && /pre-write lint/.test(String(r9?.reason ?? "")),
		JSON.stringify(r9 ?? "no-block"),
	);

	// --- AC10: literal splice — a $-crafted newText cannot make the probe
	// clean while the landed edit is red (String.replace with a string
	// replacement interprets $& $` $' $$; pi splices LITERALLY) ---
	const dollarPy = path.join(tmp, "dollar.py");
	writeFileSync(dollarPy, "import sys\nOK()\n");
	const r10 = await handlers.tool_call(
		{ toolName: "edit", input: { path: dollarPy, edits: [{ oldText: "import sys\n", newText: "import os\n$'" }] } },
		ctx,
	);
	check(
		"AC10 $-sequence newText denied (probe == literal landed content)",
		!!r10?.block,
		JSON.stringify(r10?.reason ?? "ALLOWED — $ interpretation divergence")
	);

	// --- AC11: ccPayload edit translation makes the ADR #58 carve-out
	// reachable through the bridge (CC-shape keys, Edit vs MultiEdit) ---
	const p1 = ext.ccPayload("Edit", { path: "/x/a.py", edits: [{ oldText: "a", newText: "b" }] });
	const p2 = ext.ccPayload("Edit", {
		path: "/x/a.py",
		edits: [
			{ oldText: "a", newText: "b" },
			{ oldText: "c", newText: "d" },
		],
	});
	const p3 = ext.ccPayload("Write", { path: "/x/a.py", content: "x = 1\n" });
	check(
		"AC11 single edit → CC Edit old_string/new_string",
		p1.tool_name === "Edit" && p1.tool_input.old_string === "a" && p1.tool_input.new_string === "b",
		JSON.stringify(p1)
	);
	check(
		"AC11 multi edit → CC MultiEdit with CC-shaped edits[]",
		p2.tool_name === "MultiEdit" && Array.isArray(p2.tool_input.edits) && p2.tool_input.edits[0].old_string === "a",
		JSON.stringify(p2)
	);
	check("AC11 write passes content through", p3.tool_input.content === "x = 1\n", JSON.stringify(p3));

	// --- AC12: temp hygiene — nothing at os.tmpdir() top level, ever ---
	// (runs LAST so every invocation above — including AC10's deny — had its
	// mkdtemp cleanup observed)
	const stray = readdirSync(tmpdir()).filter((f) => f.startsWith("sf-pre-lint-"));
	check("AC12 no predictable top-level sf-pre-lint files in tmpdir", stray.length === 0, stray.join(", "));
} finally {
	rmSync(tmp, { recursive: true, force: true });
}

const failed = results.filter((r) => !r.ok);
console.log(failed.length ? `\n${failed.length} FAILED / ${results.length}` : `\nALL ${results.length} PASS`);
process.exit(failed.length ? 1 : 0);
