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
import { fileURLToPath } from "node:url";
import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";

const HERE = path.dirname(fileURLToPath(import.meta.url)); // decode-safe (raw .pathname breaks on %20 paths)
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
		child.stdin.on("error", () => {
			/* EPIPE when the child exits before reading — not a gate signal */
		});
		let stdout = "";
		let settled = false;
		const settle = (r: HookOutput | null) => {
			if (settled) return;
			settled = true;
			resolve(r);
		};
		const timer = setTimeout(() => {
			try {
				child.kill("SIGKILL");
			} catch {
				/* already gone */
			}
			settle({ stdout, code: null, timedOut: true }); // hard bound — do not wait for close (fd-inheriting grandchildren)
		}, timeoutMs);
		child.stdout.on("data", (d) => (stdout += d.toString()));
		child.on("close", (code) => {
			clearTimeout(timer);
			settle({ stdout, code, timedOut: false });
		});
		child.on("error", () => {
			clearTimeout(timer);
			settle(null);
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

export function ccPayload(toolName: string, input: Record<string, unknown>): Record<string, unknown> {
	// pi edit/write input {path,...} → CC {tool_name, tool_input:{file_path}}.
	// Edit translation (2026-09-03, I-1): CC hook contract has Edit
	// {old_string,new_string} and MultiEdit {edits:[{old_string,new_string}]};
	// emitting pi's raw {edits:[{oldText,newText}]} under tool_name "Edit" left
	// blueprint_guard's ADR #58 mapping carve-out UNREACHABLE through this
	// bridge (the carve-out arms read the CC keys — missing keys ⇒ conservative
	// deny, so the documented append-open path never passed). counters.py and
	// fast_gate.py read only file_path — inert to the translation.
	const filePath = (input.path as string) ?? (input.file_path as string) ?? "";
	const toolInput: Record<string, unknown> = { file_path: filePath };
	if (input.content !== undefined) toolInput.content = input.content;
	let effectiveName = toolName;
	const edits = input.edits;
	if (Array.isArray(edits)) {
		const ccEdits = edits.map((e) =>
			e && typeof (e as Record<string, unknown>).oldText === "string"
				? {
						old_string: (e as Record<string, unknown>).oldText,
						new_string: (e as Record<string, unknown>).newText,
				}
				: e
		);
		if (ccEdits.length === 1) {
			toolInput.old_string = (ccEdits[0] as Record<string, unknown>).old_string;
			toolInput.new_string = (ccEdits[0] as Record<string, unknown>).new_string;
		} else {
			toolInput.edits = ccEdits;
			if (toolName === "Edit") effectiveName = "MultiEdit";
		}
	}
	return { tool_name: effectiveName, tool_input: toolInput };
}

const CC_NAMES: Record<string, string> = { edit: "Edit", write: "Write" };

interface CmdResult {
	ok: boolean;
	out: string;
	timedOut: boolean;
}

/**
 * Run a CLI command, capture combined output. null when the binary is absent
 * (ENOENT). The timeout resolves IMMEDIATELY (hard bound) — not waiting for
 * `close`, which can be held hostage by fd-inheriting grandchildren of the
 * killed child. Exported for the seam selftest (timeout/ENOENT paths).
 */
export async function runCmd(
	cmd: string,
	args: string[],
	cwd: string,
	timeoutMs: number,
): Promise<CmdResult | null> {
	return new Promise((resolve) => {
		const child = spawn(cmd, args, { cwd, stdio: ["ignore", "pipe", "pipe"] });
		let out = "";
		let settled = false;
		const settle = (r: CmdResult | null) => {
			if (settled) return;
			settled = true;
			resolve(r);
		};
		const timer = setTimeout(() => {
			try {
				child.kill("SIGKILL");
			} catch {
				/* already gone */
			}
			settle({ ok: false, out, timedOut: true });
		}, timeoutMs);
		child.stdout.on("data", (d) => (out += d.toString()));
		child.stderr.on("data", (d) => (out += d.toString()));
		child.on("close", (code) => {
			clearTimeout(timer);
			settle({ ok: code === 0, out, timedOut: false });
		});
		child.on("error", () => {
			clearTimeout(timer);
			settle(null); // binary not installed — degrade to post-gate only
		});
	});
}

/**
 * Nearest ruff config walking up from the target file: ruff.toml / .ruff.toml,
 * or a pyproject.toml carrying a [tool.ruff] table. Known limitation: ruff
 * `per-file-ignores` match the TEMP copy's /tmp path, not the real path — a
 * per-file-ignored violation can pre-deny; the post-gate (real path) stays
 * authoritative.
 */
function findRuffConfig(filePath: string): string | null {
	let dir = path.dirname(path.resolve(filePath));
	while (true) {
		for (const name of ["ruff.toml", ".ruff.toml"]) {
			const c = path.join(dir, name);
			if (fs.existsSync(c)) return c;
		}
		const pj = path.join(dir, "pyproject.toml");
		if (fs.existsSync(pj)) {
			try {
				if (fs.readFileSync(pj, "utf-8").includes("[tool.ruff]")) return pj;
			} catch {
				/* unreadable — keep walking */
			}
		}
		const parent = path.dirname(dir);
		if (parent === dir) return null;
		dir = parent;
	}
}

/**
 * The would-be file content after a pi edit/write tool call, or null when it
 * cannot be determined (write without content; edit against a missing file or
 * a stale oldText — the tool itself will error in those cases; also pi-side
 * CRLF/BOM/fuzzy-whitespace tolerance diverges from this exact match — those
 * paths return null and the post-write gate stays authoritative).
 * Caps: >200 edits or >5MB content bail to null (unbounded model-fabricated
 * arrays would otherwise freeze the event loop synchronously).
 */
function wouldBeContent(input: Record<string, unknown>): string | null {
	if (typeof input.content === "string") return input.content; // write
	const edits = input.edits;
	if (!Array.isArray(edits) || edits.length > 200) return null;
	let content: string;
	try {
		content = fs.readFileSync(String(input.path ?? ""), "utf-8");
	} catch {
		return null;
	}
	if (content.length > 5 * 1024 * 1024) return null;
	for (const e of edits) {
		if (!e || typeof e.oldText !== "string" || typeof e.newText !== "string") return null;
		if (!content.includes(e.oldText)) return null;
		// LITERAL splice via function replacement: String.replace with a string
		// replacement INTERPRETS $& $` $' $$ — a crafted newText could make the
		// probe clean while the landed (literal) edit is red. The function form
		// skips $ interpretation; first occurrence = the tool's unique-region
		// contract.
		content = content.replace(e.oldText, () => e.newText);
	}
	return content;
}

function tail(s: string, n = LINT_OUT_MAX): string {
	return s.length > n ? `${s.slice(0, n)}…` : s;
}

/**
 * Absolute ruff path, resolved ONCE via `which` and cached forever: the two
 * ruff calls per edit (check + format) then hit the same binary (no TOCTOU),
 * and no later PATH state can swap it mid-session. Trust boundary: `which`
 * runs against the pi process's startup PATH — the same trust level as the
 * python hooks and the post-gate (a binary found there is environment-trusted
 * by definition). null when ruff is absent (degrade to post-gate).
 */
let ruffBinCache: string | null | undefined;

async function resolveRuff(): Promise<string | null> {
	if (ruffBinCache !== undefined) return ruffBinCache;
	const out = await runCmd("which", ["ruff"], process.cwd(), 2_000);
	if (out === null) {
		// `which` itself absent/failed to spawn — definitive enough for this session
		ruffBinCache = null;
		return null;
	}
	if (out.timedOut) {
		// transient: do NOT cache — retry on the next edit (a hung moment must not
		// degrade the pre-gate for the whole session)
		return null;
	}
	const first = out.ok ? out.out.split("\n").map((l) => l.trim()).find(Boolean) : undefined;
	ruffBinCache = first || null;
	return ruffBinCache;
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
	const bin = await resolveRuff();
	if (bin === null) return null;
	// Private unpredictable dir per invocation — a predictable top-level
	// /tmp filename is a symlink/raid surface on shared machines.
	const dir = fs.mkdtempSync(path.join(os.tmpdir(), "sf-pre-lint-"));
	const tmp = path.join(dir, "probe.py");
	try {
		try {
			fs.writeFileSync(tmp, content);
		} catch {
			return null; // tmpdir unwritable — degrade to post-gate
		}
		try {
			const mode = fs.statSync(filePath).mode & 0o777;
			if (mode & 0o400) fs.chmodSync(tmp, mode); // preserve exec bit (EXE001 parity); skip unreadable modes
		} catch {
			/* new file — keep default mode */
		}
		const cfg = findRuffConfig(filePath);
		const common = cfg ? ["--config", cfg] : [];
		const chk = await runCmd(bin, [...common, "check", "--no-cache", "--output-format=concise", tmp], cwd, PRE_LINT_TIMEOUT_MS);
		if (chk === null || chk.timedOut) return null; // absent or hung ruff — degrade to post-gate
		if (!chk.ok) {
			return { reason: `pre-write lint: ruff check fails on the proposed edit — fix the edit itself and retry (the file has NOT been modified):\n${tail(chk.out)}` };
		}
		const fmt = await runCmd(bin, [...common, "format", "--check", tmp], cwd, PRE_LINT_TIMEOUT_MS);
		if (fmt === null || fmt.timedOut) return null; // absent or hung ruff — degrade to post-gate
		if (!fmt.ok) {
			return { reason: `pre-write lint: ruff format would reformat the proposed edit — wrap the lines inside the edit and retry (the file has NOT been modified):\n${tail(fmt.out)}` };
		}
		return null;
	} finally {
		try {
			fs.rmSync(dir, { recursive: true, force: true });
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
