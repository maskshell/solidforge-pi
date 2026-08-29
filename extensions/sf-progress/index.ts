/**
 * sf-progress — csr run-progress footer strip (L2 ambient observability).
 *
 * Tails the newest `workspace/cross-source-review/runs/<run>/progress.jsonl` (the
 * ADR #61 run-progress sidecar written by the csr orchestrator +
 * hetero_doc_review.py --progress-file) and renders ONE condensed status line
 * in the pi footer via ctx.ui.setStatus — run-level state (round k/cap, phase,
 * findings, reconcile totals, terminal outcome) that stays visible no matter
 * which tool is currently on screen: during the same-family subagent leg, the
 * hetero bash leg, or while the orchestrator itself is thinking.
 *
 * The pi-port replacement for upstream's ADR #62 in-session narration (CC
 * run_in_background + 2-minute orchestrator polls): substrate-level polling,
 * zero LLM behavior dependence, zero orchestrator context cost.
 *
 * Read-only + best-effort by contract (the sidecar's own rule): any IO error
 * degrades to "no status", never surfaces to the session.
 *
 * Polling (3s interval) instead of fs.watch deliberately — append visibility on
 * network filesystems is unreliable with watchers, run dirs hold few small
 * files, and the tick also drives the stale-run fade (last event > 30 min old
 * clears the strip).
 */

import * as fs from "node:fs";
import * as path from "node:path";
import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";

const STATUS_ID = "sf-csr";
const POLL_MS = 3000;
const STALE_CLEAR_MS = 30 * 60 * 1000; // fade the strip 30min after the last event

interface ProgressEvent {
	ts?: string;
	type?: string;
	[key: string]: unknown;
}

function globRunFiles(runsDir: string): string[] {
	let entries: fs.Dirent[];
	try {
		entries = fs.readdirSync(runsDir, { withFileTypes: true });
	} catch {
		return [];
	}
	const files: string[] = [];
	for (const e of entries) {
		if (!e.isDirectory()) continue;
		const p = path.join(runsDir, e.name, "progress.jsonl");
		try {
			const st = fs.statSync(p);
			if (st.isFile()) files.push(p);
		} catch {
			/* run dir without a progress file yet — skip */
		}
	}
	return files;
}

function newestByMtime(files: string[]): string | null {
	let best: string | null = null;
	let bestMtime = -1;
	for (const f of files) {
		try {
			const m = fs.statSync(f).mtimeMs;
			if (m > bestMtime) {
				bestMtime = m;
				best = f;
			}
		} catch {
			/* raced deletion — skip */
		}
	}
	return best;
}

export function parseCompleteLines(chunk: string): { events: ProgressEvent[]; consumed: number } {
	const events: ProgressEvent[] = [];
	const lines = chunk.split("\n");
	// The final element is the text AFTER the last newline — a possibly torn
	// tail line under a concurrent append; leave it unconsumed.
	const complete = lines.slice(0, -1);
	for (const line of complete) {
		const t = line.trim();
		if (!t) continue;
		try {
			const obj = JSON.parse(t);
			if (obj && typeof obj === "object") events.push(obj as ProgressEvent);
		} catch {
			/* torn/malformed — counted as noise, never fatal (sidecar AC-2) */
		}
	}
	let consumed = 0;
	for (const line of complete) consumed += Buffer.byteLength(line, "utf8") + 1;
	return { events, consumed };
}

function fmtAge(ms: number): string {
	const s = Math.max(0, Math.round(ms / 1000));
	if (s < 90) return `${s}s`;
	const m = Math.floor(s / 60);
	if (m < 90) return `${m}m`;
	return `${Math.floor(m / 60)}h`;
}

/** One condensed footer line from the sidecar events (render_status's sibling). */
export function renderStrip(events: ProgressEvent[]): string | undefined {
	if (events.length === 0) return undefined;
	const runStart = events.find((e) => e.type === "run-start");
	const runEnd = [...events].reverse().find((e) => e.type === "run-end");
	const rounds = events.filter((e) => typeof e.round === "number").map((e) => e.round as number);
	const curRound = rounds.length ? Math.max(...rounds) : 0;
	const cap = typeof runStart?.cap === "number" ? runStart.cap : "?";

	const parts: string[] = [];
	if (runEnd) {
		const outcome = String(runEnd.outcome ?? "?").toUpperCase();
		const totalRounds = typeof runEnd.rounds === "number" ? runEnd.rounds : curRound;
		parts.push(`csr ${outcome} · r${totalRounds}`);
	} else {
		parts.push(`csr r${curRound || "-"}/${cap}`);
		// phase from the LAST event (hetero heartbeat carries live idle/model)
		const last = events[events.length - 1];
		const ts = typeof last.ts === "string" ? Date.parse(last.ts) : NaN;
		const age = Number.isFinite(ts) ? fmtAge(Date.now() - ts) : "?";
		switch (last.type) {
			case "hetero-heartbeat": {
				const model = typeof last.model === "string" ? last.model.split("/").pop() : "model…";
				const idle = typeof last.idle_s === "number" ? ` idle ${Math.round(last.idle_s)}s` : "";
				parts.push(`hetero ${last.provider ?? "?"} (${model}${idle}) ${age} ago`);
				break;
			}
			case "hetero-leg-start":
				parts.push(`hetero ${last.provider ?? "?"} started ${age} ago`);
				break;
			case "hetero-leg-end":
				parts.push(`hetero ${last.provider ?? "?"} ${last.outcome ?? "?"}`);
				break;
			case "same-family-spawn":
				parts.push(`same-family r${last.round ?? "?"} ${age} ago`);
				break;
			case "same-family-complete":
				parts.push(`same-family done (${last.findings ?? "?"} findings)`);
				break;
			case "reconcile":
				parts.push(`reconcile fx${last.fixed ?? 0}/rj${last.rejected ?? 0}/es${last.escalated ?? 0}`);
				break;
			case "round-end":
				parts.push(`round ${last.round ?? "?"} end · ${last.new_blockers ?? "?"} new blockers`);
				break;
			default:
				if (last.type) parts.push(`${last.type} ${age} ago`);
		}
	}

	// Totals (kept even post-run — the audit summary).
	const sfFindings = events
		.filter((e) => e.type === "same-family-complete")
		.reduce((a, e) => a + (typeof e.findings === "number" ? e.findings : 0), 0);
	const hetEnds = events.filter((e) => e.type === "hetero-leg-end");
	if (hetEnds.length > 0 || sfFindings > 0) {
		const ok = hetEnds.filter((e) => e.outcome === "ok").length;
		const deg = hetEnds.filter((e) => e.outcome === "degraded").length;
		parts.push(`sf ${sfFindings}f · het ok${ok}${deg ? ` deg${deg}` : ""}`);
	}
	return parts.join(" · ");
}

interface StatusUi {
	setStatus: (id: string, text?: string) => void;
}

export default function (pi: ExtensionAPI) {
	let timer: ReturnType<typeof setInterval> | undefined;
	let activeFile: string | null = null;
	let offset = 0;
	let events: ProgressEvent[] = [];
	let lastEventWall = 0;

	const tick = (ui: StatusUi, cwd: string) => {
		try {
			const runsDir = path.join(cwd, "workspace", "cross-source-review", "runs");
			const newest = newestByMtime(globRunFiles(runsDir));
			if (!newest) return; // no runs here — stay silent
			if (newest !== activeFile) {
				activeFile = newest;
				offset = 0;
				events = [];
			}
			const st = fs.statSync(activeFile);
			if (st.size > offset) {
				const fh = fs.openSync(activeFile, "r");
				try {
					const len = st.size - offset;
					const buf = Buffer.alloc(len);
					fs.readSync(fh, buf, 0, len, offset);
					const { events: newEvents, consumed } = parseCompleteLines(buf.toString("utf8"));
					events.push(...newEvents);
					offset += consumed;
				} finally {
					fs.closeSync(fh);
				}
			}
			const strip = renderStrip(events);
			if (strip) {
				const last = events[events.length - 1];
				const ts = typeof last?.ts === "string" ? Date.parse(last.ts) : NaN;
				if (Number.isFinite(ts)) lastEventWall = ts;
				if (Date.now() - lastEventWall > STALE_CLEAR_MS) {
					ui.setStatus(STATUS_ID, undefined); // stale run — fade out
				} else {
					ui.setStatus(STATUS_ID, strip);
				}
			}
		} catch {
			/* best-effort contract: observability never disturbs the session */
		}
	};

	pi.on("session_start", (_event, ctx) => {
		if (!ctx.hasUI || timer) return;
		const cwd = ctx.cwd;
		const ui = ctx.ui;
		timer = setInterval(() => tick(ui, cwd), POLL_MS);
		// one immediate pass so a resumed session shows existing run state at once
		tick(ui, cwd);
	});

	pi.on("session_shutdown", (_event, ctx) => {
		if (timer) {
			clearInterval(timer);
			timer = undefined;
		}
		try {
			ctx.ui.setStatus(STATUS_ID, undefined);
		} catch {
			/* already torn down */
		}
	});
}
