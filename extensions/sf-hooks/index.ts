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
 *   tool_result (edit|write) → fast_gate.py (20s) →
 *                             {"decision":"block","reason"} ⇒ isError + feedback
 *
 * Env bridge: CLAUDE_PROJECT_DIR=ctx.cwd (the scripts' project-root resolution).
 * Tool-name mapping: pi edit/write → CC Edit/Write (MultiEdit folded into edit).
 */

import { spawn } from "node:child_process";
import * as fs from "node:fs";
import * as path from "node:path";
import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";

const HERE = path.dirname(new URL(import.meta.url).pathname);
const HOOKS_DIR = path.normalize(path.join(HERE, "..", "..", "skills", "parallel-development", "infra", "hooks"));

const PRE_HOOKS = ["blueprint_guard.py", "counters.py"];
const POST_HOOK = "fast_gate.py";
const PRE_TIMEOUT_MS = 5_000;
const POST_TIMEOUT_MS = 20_000;

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
		const text = `FAST-GATE BLOCK: ${block.reason}`;
		return {
			content: [{ type: "text", text }],
			isError: true,
		};
	});
}
