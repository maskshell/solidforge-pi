/**
 * sf-providers — SolidForge hetero (different-family) provider registry.
 *
 * Registers the Anthropic-compatible endpoints SolidForge's different-family
 * review substrate (hetero_review.py / hetero_doc_review.py profiles) targets:
 * DeepSeek + MiniMax (+ BigModel when token present). Token resolution follows
 * the SolidForge convention (ADR #40): <NAME>_ANTHROPIC_AUTH_TOKEN from
 * <cwd>/.env.solidforge, then <cwd>/.env, then shell env — shell wins.
 *
 * Usage:
 *   pi -e ./extensions/sf-providers --model deepseek/deepseek-v4-flash -p "..."
 *   (hetero wrappers spawn: pi --mode json -p --no-session --model deepseek/deepseek-v4-flash ...)
 */

import * as fs from "node:fs";
import * as path from "node:path";
import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";

interface ProfileDef {
	id: string;
	baseUrl: string;
	tokenEnv: string;
	models: Array<{ id: string; contextWindow: number; maxTokens?: number }>;
}

// Model specs are PLACEHOLDERS (profiles/*.json carry routing only, no specs).
// TODO(M1): verify context windows / max output against provider docs and set costs.
const PROFILES: ProfileDef[] = [
	{
		id: "deepseek",
		baseUrl: "https://api.deepseek.com/anthropic",
		tokenEnv: "DEEPSEEK_ANTHROPIC_AUTH_TOKEN",
		models: [
			{ id: "deepseek-v4-flash", contextWindow: 128_000 },
			{ id: "deepseek-v4-flash[1m]", contextWindow: 1_000_000 },
		],
	},
	{
		id: "minimax",
		baseUrl: "https://api.minimaxi.com/anthropic",
		tokenEnv: "MINIMAX_ANTHROPIC_AUTH_TOKEN",
		models: [{ id: "MiniMax-M3[1m]", contextWindow: 1_000_000 }],
	},
	{
		id: "bigmodel",
		baseUrl: "https://open.bigmodel.cn/api/anthropic",
		tokenEnv: "BIGMODEL_ANTHROPIC_AUTH_TOKEN",
		models: [{ id: "GLM-5.2[1M]", contextWindow: 1_000_000 }],
	},
];

function loadEnvFile(file: string, into: NodeJS.ProcessEnv, overwrite: boolean): void {
	let text: string;
	try {
		text = fs.readFileSync(file, "utf-8");
	} catch {
		return;
	}
	for (const line of text.split("\n")) {
		const m = line.match(/^\s*(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*)\s*$/);
		if (!m) continue;
		const key = m[1];
		let val = m[2].trim();
		if ((val.startsWith('"') && val.endsWith('"')) || (val.startsWith("'") && val.endsWith("'"))) {
			val = val.slice(1, -1);
		}
		if (overwrite || !(key in into)) into[key] = val;
	}
}

export default function (pi: ExtensionAPI) {
	// SolidForge env precedence: .env.solidforge loads first, then .env; shell wins
	// (never overwrite an existing process env var).
	const cwd = process.cwd();
	loadEnvFile(path.join(cwd, ".env.solidforge"), process.env, false);
	loadEnvFile(path.join(cwd, ".env"), process.env, false);

	for (const p of PROFILES) {
		if (!process.env[p.tokenEnv]) continue; // provider without token stays unregistered (graceful)
		pi.registerProvider(p.id, {
			baseUrl: p.baseUrl,
			apiKey: `$${p.tokenEnv}`,
			api: "anthropic-messages",
			models: p.models.map((m) => ({
				id: m.id,
				name: `${p.id}/${m.id}`,
				reasoning: false, // TODO(M1): confirm thinking support per provider
				input: ["text"],
				cost: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0 }, // unknown — honest zero, TODO(M1)
				contextWindow: m.contextWindow,
				maxTokens: m.maxTokens ?? 8192,
			})),
		});
	}
}
