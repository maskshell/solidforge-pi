/**
 * sf-hetero — the `hetero_doc_review` tool: the csr different-family leg as a
 * first-class tool instead of a bash invocation.
 *
 * Design authority: docs/sf-hetero.proposal.md (csr-converged 2026-08-29,
 * substantive_converged: true — record: docs/sf-hetero.convergence-record.json).
 * The wrapper CLI (skills/cross-source-review/infra/scripts/hetero_doc_review.py)
 * stays the single substrate contract — this tool is a CLIENT; no wrapper change.
 *
 * What it fixes over the bash path (proposal §1):
 *   P1 — stream separation: stdout (the single result JSON) is the tool `content`
 *        VERBATIM on exit 0; stderr progress lines are display-only and never
 *        enter LLM context.
 *   P2 — structured live panel: per-provider {model?, elapsedS, turns, idleS,
 *        currentTool?, costUsd?, heartbeats} derived from the wrapper's stderr
 *        events (leg-progress + hetero-heartbeat), streamed via onUpdate.
 *   P3 — exit semantics: 0 = usable result (pass/rewrite/degraded — isError NOT
 *        set for rewrite or degraded); 1 = isError (malformation fingerprint +
 *        stderr tail when stdout parses, else stderr verbatim — the pre-leg
 *        fail-fast shape); 2 = isError (stderr tail); exit-0 unparsable stdout =
 *        isError with the raw tail (never mask a substrate regression).
 *
 * Abort: the wrapper runs in its own process group (detached) and is killed with
 * an explicit SIGKILL to the GROUP — exact parity with the bash tool's
 * killProcessTree POSIX branch. The grandchild pi inherits the group (the
 * wrapper's Popen sets no start_new_session), so the whole tree dies. win32 is
 * out of scope (documented in the proposal's C3).
 */

import { spawn } from "node:child_process";
import * as fs from "node:fs";
import * as os from "node:os";
import * as path from "node:path";
import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";
import { Container, Spacer, Text } from "@earendil-works/pi-tui";
import { Type } from "typebox";

const LIVE_TICK_MS = Math.max(1000, Number(process.env.SF_HETERO_TICK_MS ?? 5000));
const STDERR_TAIL_MAX = 30;

interface ProviderState {
	name: string;
	model?: string;
	startedAt?: number;
	lastEventAt?: number;
	turns: number;
	currentTool?: string;
	costUsd?: number;
	heartbeats: number;
}

interface HeteroDetails {
	running: boolean;
	providers: ProviderState[];
	result?: Record<string, unknown>;
	stderrTail: string[];
	exitCode: number | null;
}

function wrapperScriptPath(): string {
	// <pkg>/extensions/sf-hetero/index.ts -> <pkg>/skills/cross-source-review/infra/scripts/
	// (the sf-subagents import.meta.url package-relative pattern — same principle as the
	// wrapper's _sf_providers_dir, different depth; proposal §2 'Spawn').
	const modulePath = decodeURIComponent(new URL(import.meta.url).pathname);
	const pkgRoot = path.dirname(path.dirname(path.dirname(modulePath)));
	return path.join(
		pkgRoot,
		"skills",
		"cross-source-review",
		"infra",
		"scripts",
		"hetero_doc_review.py",
	);
}

function fmtSecs(ms: number): string {
	const s = Math.max(0, Math.round(ms / 1000));
	if (s < 60) return `${s}s`;
	return `${Math.floor(s / 60)}m${String(s % 60).padStart(2, "0")}`;
}

function extractLastJsonObject(text: string): Record<string, unknown> | null {
	const trimmed = text.trim();
	if (!trimmed) return null;
	try {
		const obj = JSON.parse(trimmed);
		if (obj && typeof obj === "object") return obj as Record<string, unknown>;
	} catch {
		/* fall through to brace-balanced extract */
	}
	// Brace-balanced LAST object (defensive: stdout should be exactly one JSON doc;
	// a stray pre/postamble must not mask the envelope — proposal §2 completion).
	let start = trimmed.lastIndexOf("{");
	while (start !== -1) {
		let depth = 0;
		for (let i = start; i < trimmed.length; i++) {
			const ch = trimmed[i];
			if (ch === "{") depth++;
			else if (ch === "}") {
				depth--;
				if (depth === 0) {
					try {
						const obj = JSON.parse(trimmed.slice(start, i + 1));
						if (obj && typeof obj === "object") return obj as Record<string, unknown>;
					} catch {
						/* keep scanning */
					}
					break;
				}
			}
		}
		start = trimmed.lastIndexOf("{", start - 1);
	}
	return null;
}

export default function (pi: ExtensionAPI) {
	const params = Type.Object({
		artifact: Type.String({ description: "Path/ref of the DOC under review (passed to --artifact)." }),
		authority: Type.Optional(
			Type.String({ description: "Authoritative reference doc+section; empty/omitted = self-contained." }),
		),
		priorFindings: Type.Optional(
			Type.String({ description: "Prior findings as JSON, or `@file` (passed to --prior-findings)." }),
		),
		roundIndex: Type.Optional(Type.Number({ description: "This leg's round number (passed to --round-index)." })),
		progressFile: Type.Optional(
			Type.String({ description: "Run-progress sidecar path (passed to --progress-file)." }),
		),
		profile: Type.Optional(
			Type.String({
				description: "DISCOURAGED — the wrapper resolves providers from HETERO_DOC_PROFILE; pass only with cause.",
			}),
		),
		dryRun: Type.Optional(
			Type.Boolean({ description: "Pass --dry-run (canned doc-findings, no model call; offline gate path)." }),
		),
	});

	pi.registerTool({
		name: "hetero_doc_review",
		label: "hetero review",
		description: [
			"The csr different-family (异源) leg: spawns hetero_doc_review.py on cross-family provider routes.",
			"stdout (the result JSON) returns verbatim; stderr progress (leg-progress tool calls/turns + 30s heartbeats) renders as a live per-provider panel and never enters the result text.",
			"Providers/caps resolve exactly as the CLI: HETERO_DOC_PROFILE from <cwd>/.env.solidforge; budget/turns/bytes/timeout stay wrapper-owned env defaults.",
			"Run from the project root (the wrapper self-loads .env.solidforge).",
		].join(" "),
		parameters: params,

		async execute(_toolCallId, p, signal, onUpdate, ctx) {
			const details: HeteroDetails = {
				running: true,
				providers: [],
				stderrTail: [],
				exitCode: null,
			};
			const providersByName = new Map<string, ProviderState>();

			const getProvider = (name: unknown): ProviderState | null => {
				if (typeof name !== "string" || !name) return null;
				let st = providersByName.get(name);
				if (!st) {
					st = { name, turns: 0, heartbeats: 0 };
					providersByName.set(name, st);
					details.providers.push(st);
				}
				return st;
			};

			const emitUpdate = () => {
				if (!onUpdate) return;
				// Partial content: the one-line running placeholder (sf-subagents'
				// "(running...)" pattern — proposal §2 live panel).
				const now = Date.now();
				const current = details.providers.filter((s) => s.lastEventAt);
				const last = current[current.length - 1];
				let text = "(running...)";
				if (last) {
					const parts = [`hetero ${last.name}`, `turn ${last.turns}`];
					if (last.costUsd !== undefined) parts.push(`$${last.costUsd.toFixed(4)}`);
					parts.push(`idle ${fmtSecs(now - (last.lastEventAt ?? now))}`);
					text = parts.join(" · ");
				}
				onUpdate({
					content: [{ type: "text", text }],
					details: { ...details, providers: details.providers.map((s) => ({ ...s })) },
				});
			};

			const argv = ["python3", wrapperScriptPath(), "--artifact", p.artifact];
			if (p.authority !== undefined) argv.push("--authority", p.authority);
			if (p.priorFindings !== undefined && p.priorFindings !== "") {
				// argv-limit robustness (mechanical, not a contract change): an inline
				// JSON blob over 8 KiB rides a 0600 temp file as @ref, exactly like
				// sf-subagents' long prompts.
				let prior = p.priorFindings;
				if (!prior.startsWith("@") && prior.length > 8192) {
					const dir = await fs.promises.mkdtemp(path.join(os.tmpdir(), "sf-hetero-"));
					const fp = path.join(dir, "prior-findings.json");
					await fs.promises.writeFile(fp, prior, { encoding: "utf-8", mode: 0o600 });
					prior = `@${fp}`;
				}
				argv.push("--prior-findings", prior);
			}
			if (p.roundIndex !== undefined) argv.push("--round-index", String(Math.trunc(p.roundIndex)));
			if (p.progressFile !== undefined && p.progressFile !== "") argv.push("--progress-file", p.progressFile);
			if (p.profile !== undefined && p.profile !== "") argv.push("--profile", p.profile);
			if (p.dryRun) argv.push("--dry-run");

			const child = spawn(argv[0], argv.slice(1), {
				cwd: ctx.cwd,
				detached: process.platform !== "win32", // own process group — the SIGKILL parity anchor
				stdio: ["ignore", "pipe", "pipe"],
				env: process.env,
			});

			let stdoutChunks: Buffer[] = [];
			let stderrBuffer = "";
			let stderrLines: string[] = [];

			const processStderrLine = (line: string) => {
				if (!line.trim()) return;
				let evt: any;
				try {
					evt = JSON.parse(line);
				} catch {
					evt = null;
				}
				if (evt && typeof evt === "object" && evt.type === "leg-progress") {
					const st = getProvider(evt.provider);
					if (!st) return;
					st.lastEventAt = Date.now();
					st.startedAt ??= st.lastEventAt;
					if (evt.phase === "tool" && typeof evt.detail === "string") {
						st.currentTool = evt.detail.slice(0, 100);
					} else if (evt.phase === "turn" && typeof evt.detail === "string") {
						st.turns++;
						st.currentTool = undefined;
						// costUsd from the turn detail "turn N · $X.XXXX" — OPTIONAL: the
						// wrapper omits the $ segment at cumulative 0 (catalog-unpriced routes).
						const m = evt.detail.match(/· \$([0-9.]+)/);
						if (m) st.costUsd = Number(m[1]);
					}
					emitUpdate();
					return;
				}
				if (evt && typeof evt === "object" && evt.type === "hetero-heartbeat") {
					const st = getProvider(evt.provider);
					if (!st) return;
					st.lastEventAt = Date.now();
					st.startedAt ??= st.lastEventAt;
					st.heartbeats++;
					if (typeof evt.model === "string" && evt.model) st.model = evt.model;
					emitUpdate();
					return;
				}
				// Non-progress stderr lines (the wrapper's own plain-text warnings):
				// bounded display-only tail, never content on the exit-0 path.
				stderrLines.push(line);
				if (stderrLines.length > STDERR_TAIL_MAX) stderrLines.shift();
			};

			const ticker = onUpdate
				? setInterval(() => {
						if (details.running) emitUpdate();
					}, LIVE_TICK_MS)
				: undefined;

			const killGroup = () => {
				try {
					if (child.pid) {
						if (process.platform !== "win32") process.kill(-child.pid, "SIGKILL"); // group, explicit parity
						else child.kill("SIGKILL"); // documented out-of-scope fallback (proposal C3)
					}
				} catch {
					/* already gone */
				}
			};
			if (signal) {
				if (signal.aborted) killGroup();
				else signal.addEventListener("abort", killGroup, { once: true });
			}

			const exitCode = await new Promise<number>((resolve) => {
				child.stdout?.on("data", (d: Buffer) => {
					stdoutChunks.push(d);
				});
				child.stderr?.on("data", (d: Buffer) => {
					stderrBuffer += d.toString("utf-8");
					const lines = stderrBuffer.split("\n");
					stderrBuffer = lines.pop() || "";
					for (const line of lines) processStderrLine(line);
				});
				child.on("close", (code) => {
					if (stderrBuffer.trim()) processStderrLine(stderrBuffer);
					resolve(code ?? (signal?.aborted ? 1 : 0));
				});
				child.on("error", () => resolve(2));
			});

			if (ticker) clearInterval(ticker);
			signal?.removeEventListener("abort", killGroup);
			details.running = false;
			details.exitCode = exitCode;
			details.stderrTail = stderrLines.slice(-8);

			const stdoutText = Buffer.concat(stdoutChunks).toString("utf-8");
			const parsed = extractLastJsonObject(stdoutText);
			if (parsed) details.result = parsed;

			// Completion semantics — proposal §2 (fixes P3), exactly as converged.
			if (exitCode === 0) {
				if (!parsed) {
					return {
						content: [
							{
								type: "text",
								text: `hetero-substrate: exit 0 with unparsable stdout (raw tail):\n${stdoutText.slice(-2000)}`,
							},
						],
						details,
						isError: true,
					};
				}
				// Usable result: content = stdout VERBATIM (stream separation, C2).
				return { content: [{ type: "text", text: stdoutText }], details };
			}
			const tail = details.stderrTail.join("\n");
			if (exitCode === 1) {
				const fingerprint =
					parsed && typeof parsed.malformation === "string" ? parsed.malformation : null;
				const text = fingerprint
					? `hetero malformation (${fingerprint})${tail ? `\n${tail}` : ""}`
					: tail || stdoutText.slice(-2000) || "(no output)";
				return { content: [{ type: "text", text }], details, isError: true };
			}
			return {
				content: [{ type: "text", text: tail || stdoutText.slice(-2000) || `(exit ${exitCode})` }],
				details,
				isError: true,
			};
		},

		renderCall(args, theme) {
			let text =
				theme.fg("toolTitle", theme.bold("hetero_doc_review ")) +
				theme.fg("accent", String(args.artifact ?? "..."));
			if (args.dryRun) text += theme.fg("muted", " --dry-run");
			return new Text(text, 0, 0);
		},

		renderResult(result, { expanded }, theme) {
			const details = result.details as HeteroDetails | undefined;
			if (!details) {
				const t = result.content[0];
				return new Text(t?.type === "text" ? t.text : "(no output)", 0, 0);
			}
			const now = Date.now();
			const provLine = (s: ProviderState) => {
				const parts = [s.name];
				if (s.model) parts.push(s.model.split("/").pop() ?? s.model);
				parts.push(`turn ${s.turns}`);
				if (s.costUsd !== undefined) parts.push(`$${s.costUsd.toFixed(4)}`);
				if (s.heartbeats) parts.push(`${s.heartbeats}♥`);
				if (details.running && s.lastEventAt) {
					parts.push(`idle ${fmtSecs(now - s.lastEventAt)}`);
					if (s.currentTool) parts.push(`→ ${s.currentTool}`);
				}
				return parts.join(" · ");
			};

			if (details.running || details.exitCode === null) {
				const container = new Container();
				container.addChild(new Text(theme.fg("warning", "⏳ different-family review running"), 0, 0));
				for (const s of details.providers) container.addChild(new Text(theme.fg("muted", `  ${provLine(s)}`), 0, 0));
				if (details.providers.length === 0)
					container.addChild(new Text(theme.fg("muted", "  (spawning wrapper...)"), 0, 0));
				return container;
			}

			const isError = (result as { isError?: boolean }).isError === true;
			const res = details.result as { verdict?: string; findings_count?: number; degraded?: boolean } | undefined;
			const icon = isError ? theme.fg("error", "✗") : theme.fg("success", "✓");
			const head =
				res && typeof res.verdict === "string"
					? `${res.verdict}${res.degraded ? " (degraded)" : ""} · ${res.findings_count ?? 0} findings`
					: `exit ${details.exitCode}`;

			if (expanded) {
				const container = new Container();
				container.addChild(new Text(`${icon} ${theme.fg("toolTitle", theme.bold("hetero "))}${theme.fg("accent", head)}`, 0, 0));
				for (const s of details.providers) container.addChild(new Text(theme.fg("muted", `  ${provLine(s)}`), 0, 0));
				if (details.stderrTail.length) {
					container.addChild(new Spacer(1));
					for (const l of details.stderrTail.slice(-5))
						container.addChild(new Text(theme.fg("dim", `  ${l.slice(0, 160)}`), 0, 0));
				}
				const cov = details.result?.coverage;
				if (Array.isArray(cov) && cov.length) {
					container.addChild(new Spacer(1));
					for (const c of cov.slice(0, 6))
						container.addChild(new Text(theme.fg("dim", `  · ${String(c).slice(0, 160)}`), 0, 0));
				}
				return container;
			}

			let text = `${icon} ${theme.fg("toolTitle", theme.bold("hetero "))}${theme.fg("accent", head)}`;
			for (const s of details.providers) text += `\n${theme.fg("muted", `  ${provLine(s)}`)}`;
			if (details.stderrTail.length) text += `\n${theme.fg("dim", `  ${details.stderrTail[details.stderrTail.length - 1].slice(0, 120)}`)}`;
			return new Text(text, 0, 0);
		},
	});
}
