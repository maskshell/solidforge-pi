/**
 * sf-hooks — the pi port of SolidForge's convergence-loop hooks.
 *
 * CC era: hooks.json wired PreToolUse (blueprint_guard.py + counters.py) and
 * PostToolUse (fast_gate.py) to Edit|Write tool calls. Pi has no hooks.json;
 * this extension bridges pi's tool_call / tool_result events to the SAME
 * python scripts (zero script changes — they speak the CC hook protocol):
 *
 *   tool_call (edit|write)  → stdin {tool_name, tool_input:{file_path}} →
 *                             blueprint_guard.py, counters.py pre (5s) →
 *                             deny ⇒ {block:true, reason}
 *   tool_call (edit|write, *.py) → pre-write ruff lint on the WOULD-BE
 *                             content (temp copy, file's own ruff config,
 *                             mode preserved for EXE001 parity) → deny ⇒
 *                             {block:true, reason}. Born from the 2026-09-03
 *                             incident: a post-write-only gate BLOCKs but the
 *                             red edit has already landed — a contaminated
 *                             style commit nearly shipped. Pre-write denial
 *                             closes that class at the seam.
 *   tool_result (edit|write) → fast_gate.py (20s) →
 *                             {"decision":"block","reason"} ⇒ isError + feedback
 *                             (message discloses the edit already landed)
 *
 * Env bridge: CLAUDE_PROJECT_DIR=ctx.cwd (the scripts' project-root resolution).
 * Tool-name mapping: pi edit/write → CC Edit/Write (MultiEdit folded into edit).
 */

import { spawn } from "node:child_process";
import * as fs from "node:fs";
import * as os from "node:os";
import * as path from "node:path";
import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";

const HERE = path.dirname(new URL(import.meta.url).pathname);
const HOOKS_DIR = path.normalize(path.join(HERE, "..", "..", "skills", "parallel-development", "infra", "hooks"));

const PRE_HOOKS = ["blueprint_guard.py", "counters.py"];
const POST_HOOK = "fast_gate.py";
const PRE_TIMEOUT_MS = 5_000;
const POST_TIMEOUT_MS = 20_000;
const PRE_LINT_TIMEOUT_MS = 5_000;
const LINT_OUT_MAX = 1500;

interface HookOutput {
	stdout: string;
	code: number | null;
	timedOut: boolean;
}

function runHook(
	script: string,
	args: string[],
	payload: unknown,
	cwd: string,
	timeoutMs: number,
): Promise<HookOutput | null> {
	const scriptPath = path.join(HOOKS_DIR, script);
	if (!fs.existsSync(scriptPath)) return Promise.resolve(null);
	return new Promise((resolve) => {
		const child = spawn("python3", [scriptPath, ...args], {
			cwd,
			env: { ...process.env, CLAUDE_PROJECT_DIR: cwd },
			stdio: ["pipe", "pipe", "pipe"],
		});
		child.stdin.write(JSON.stringify(payload));
		child.stdin.end();
		let stdout = "";
		let timedOut = false;
		const timer = setTimeout(() => {
			timedOut = true;
			child.kill("SIGKILL");
		}, timeoutMs);
		child.stdout.on("data", (d) => (stdout += d.toString()));
		child.on("close", (code) => {
			clearTimeout(timer);
			resolve({ stdout, code, timedOut });
		});
		child.on("error", () => {
			clearTimeout(timer);
			resolve(null);
		});
	});
}

/** Parse a CC hook deny/block from stdout. Returns {reason} when the call must be blocked. */
function parseDeny(stdout: string): { reason: string } | null {
	for (const line of stdout.split("\n")) {
		const t = line.trim();
		if (!t) continue;
		try {
			const obj = JSON.parse(t);
			// PreToolUse deny (permissionDecision)
			const hso = obj?.hookSpecificOutput;
			if (hso?.permissionDecision === "deny" && hso.permissionDecisionReason) {
				return { reason: hso.permissionDecisionReason };
			}
			// PostToolUse block
			if (obj?.decision === "block" && obj?.reason) {
				return { reason: obj.reason };
			}
		} catch {
			/* not json — ignore */
		}
	}
	return null;
}

function ccPayload(toolName: string, input: Record<string, unknown>): Record<string, unknown> {
	// pi edit/write input {path,...} → CC {tool_name, tool_input:{file_path}}
	const filePath = (input.path as string) ?? (input.file_path as string) ?? "";
	const toolInput: Record<string, unknown> = { file_path: filePath };
	if (input.content !== undefined) toolInput.content = input.content;
	if (input.edits !== undefined) toolInput.edits = input.edits;
	return { tool_name: toolName, tool_input: toolInput };
}

const CC_NAMES: Record<string, string> = { edit: "Edit", write: "Write" };

/** Run a CLI command, capture combined output; null when the binary is absent (ENOENT). */
function runCmd(cmd: string, args: string[], cwd: string, timeoutMs: number): Promise<{ ok: boolean; out: string } | null> {
	return new Promise((resolve) => {
		const child = spawn(cmd, args, { cwd, stdio: ["ignore", "pipe", "pipe"] });
		let out = "";
		let timedOut = false;
		const timer = setTimeout(() => {
			timedOut = true;
			child.kill("SIGKILL");
		}, timeoutMs);
		child.stdout.on("data", (d) => (out += d.toString()));
		child.stderr.on("data", (d) => (out += d.toString()));
		child.on("close", (code) => {
			clearTimeout(timer);
			resolve({ ok: !timedOut && code === 0, out });
		});
		child.on("error", () => {
			clearTimeout(timer);
			resolve(null); // binary not installed — degrade to post-gate only
		});
	});
}

/** Nearest ruff config (ruff.toml / .ruff.toml) walking up from the target file. */
function findRuffConfig(filePath: string): string | null {
	let dir = path.dirname(path.resolve(filePath));
	while (true) {
		for (const name of ["ruff.toml", ".ruff.toml"]) {
			const c = path.join(dir, name);
			if (fs.existsSync(c)) return c;
		}
		const parent = path.dirname(dir);
		if (parent === dir) return null;
		dir = parent;
	}
}

/**
 * The would-be file content after a pi edit/write tool call, or null when it
 * cannot be determined (write without content; edit against a missing file or
 * a stale oldText — the tool itself will error in those cases).
 */
function wouldBeContent(input: Record<string, unknown>): string | null {
	if (typeof input.content === "string") return input.content; // write
	const edits = input.edits;
	if (!Array.isArray(edits)) return null;
	let content: string;
	try {
		content = fs.readFileSync(String(input.path ?? ""), "utf-8");
	} catch {
		return null;
	}
	for (const e of edits) {
		if (!e || typeof e.oldText !== "string" || typeof e.newText !== "string") return null;
		if (!content.includes(e.oldText)) return null;
		content = content.replace(e.oldText, e.newText); // first occurrence = the tool's unique-region contract
	}
	return content;
}

function tail(s: string, n = LINT_OUT_MAX): string {
	return s.length > n ? `${s.slice(0, n)}…` : s;
}

/**
 * Pre-write ruff gate for .py targets: lint/format the WOULD-BE content on a
 * temp copy (mode preserved from the original so EXE001 verdicts match), using
 * the file's own ruff config. Returns a deny reason, or null to allow.
 * Best-effort by contract: ruff absent, timeout, or indeterminate content →
 * allow (the post-write fast_gate still covers those).
 */
async function preLintPython(input: Record<string, unknown>, cwd: string): Promise<{ reason: string } | null> {
	const filePath = String(input.path ?? input.file_path ?? "");
	if (!filePath.endsWith(".py")) return null;
	const content = wouldBeContent(input);
	if (content === null) return null;
	const tmp = path.join(os.tmpdir(), `sf-pre-lint-${process.pid}-${Date.now()}.py`);
	try {
		fs.writeFileSync(tmp, content);
		try {
			fs.chmodSync(tmp, fs.statSync(filePath).mode & 0o777);
		} catch {
			/* new file — keep default mode */
		}
		const cfg = findRuffConfig(filePath);
		const common = cfg ? ["--config", cfg] : [];
		const chk = await runCmd("ruff", [...common, "check", "--no-cache", "--output-format=concise", tmp], cwd, PRE_LINT_TIMEOUT_MS);
		if (chk === null) return null;
		if (!chk.ok) {
			return { reason: `pre-write lint: ruff check fails on the proposed edit — fix the edit itself and retry (the file has NOT been modified):\n${tail(chk.out)}` };
		}
		const fmt = await runCmd("ruff", [...common, "format", "--check", tmp], cwd, PRE_LINT_TIMEOUT_MS);
		if (fmt === null) return null;
		if (!fmt.ok) {
			return { reason: `pre-write lint: ruff format would reformat the proposed edit — wrap the lines inside the edit and retry (the file has NOT been modified):\n${tail(fmt.out)}` };
		}
		return null;
	} finally {
		try {
			fs.rmSync(tmp, { force: true });
		} catch {
			/* best effort */
		}
	}
}

export default function (pi: ExtensionAPI) {
	pi.on("tool_call", async (event, ctx) => {
		const ccName = CC_NAMES[event.toolName];
		if (!ccName) return;
		const payload = ccPayload(ccName, event.input as Record<string, unknown>);
		for (const script of PRE_HOOKS) {
			const out = await runHook(script, script === "counters.py" ? ["pre"] : [], payload, ctx.cwd, PRE_TIMEOUT_MS);
			if (!out || out.timedOut) continue; // never let the shim break the tool
			const deny = parseDeny(out.stdout);
			if (deny) return { block: true, reason: deny.reason };
		}
		// Pre-write python lint: deny BEFORE a red edit can land.
		const lintDeny = await preLintPython(event.input as Record<string, unknown>, ctx.cwd);
		if (lintDeny) return { block: true, reason: lintDeny.reason };
	});

	pi.on("tool_result", async (event, ctx) => {
		const ccName = CC_NAMES[event.toolName];
		if (!ccName) return;
		const input = (event.input ?? {}) as Record<string, unknown>;
		const payload = ccPayload(ccName, input);
		const out = await runHook(POST_HOOK, [], payload, ctx.cwd, POST_TIMEOUT_MS);
		if (!out || out.timedOut) return;
		const block = parseDeny(out.stdout);
		if (!block) return;
		// fast_gate semantics: the edit already happened; feed the failure back so
		// the model self-corrects (CC: conversation continues with decision:block).
		// The disclosure prefix is load-bearing: a bare BLOCK reads as "write
		// prevented" — the 2026-09-03 incident showed agents (and humans) then
		// commit the red file believing it never changed.
		const text = `FAST-GATE BLOCK (note: the edit already applied — fix inline or revert before committing): ${block.reason}`;
		return {
			content: [{ type: "text", text }],
			isError: true,
		};
	});
}
