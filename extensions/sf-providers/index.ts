/**
 * sf-providers — SolidForge hetero credential bridge (pi port, v2).
 *
 * REDESIGN (M2.5, informed by solidforge-dsh's FILENAME=ROUTE + catalog-inherit
 * principle): pi's built-in catalog ALREADY carries every hetero target route —
 * `zai-coding-cn` (glm-5.x, coding endpoint, openai-completions), `deepseek`
 * (v4-flash/pro, native endpoint), `minimax-cn` (MiniMax-M3, anthropic endpoint),
 * `qwen-token-plan-cn` (aggregated fleet incl. qwen3.8-max). Registering custom
 * providers here would DUPLICATE model facts that can then drift from the
 * catalog — the M1 "GLM-5.2 calibration" misdiagnosis came exactly from a custom
 * bigmodel/anthropic-endpoint registration (wrong endpoint+protocol for pi; the
 * CC-era `/api/anthropic` surface is not pi-ai's glm route).
 *
 * So this extension registers NOTHING. It only bridges CREDENTIALS: SolidForge's
 * CC-convention token vars (loaded from <cwd>/.env.solidforge then <cwd>/.env,
 * shell wins) are exported under the pi-ai route env names — but ONLY when the
 * target var is not already set (auth.json / shell / user env take precedence).
 * Model facts (baseUrl, protocol, contextWindow — the CC-era `[1M]` suffix is a
 * context-window parameter carried by the catalog's contextWindow field, never
 * part of a pi model id) all come from the catalog.
 *
 * Route env conventions (pi-ai env-api-keys):
 *   zai-coding-cn -> ZAI_CODING_CN_API_KEY    (CC source: BIGMODEL_ANTHROPIC_AUTH_TOKEN)
 *   deepseek      -> DEEPSEEK_API_KEY         (CC source: DEEPSEEK_ANTHROPIC_AUTH_TOKEN)
 *   minimax-cn    -> MINIMAX_CN_API_KEY       (CC source: MINIMAX_ANTHROPIC_AUTH_TOKEN)
 *   qwen-token-plan-cn -> QWEN_TOKEN_PLAN_CN_API_KEY (CC source: QWEN3_ANTHROPIC_AUTH_TOKEN)
 *
 * Notes:
 * - zai-coding-cn usually authenticates via pi's auth.json (the user's default
 *   provider); the bridge is a fallback, and it never overrides existing auth.
 * - A bridge value that the endpoint rejects surfaces in the wrapper as
 *   hetero-api-error with the provider's message (honest disclosure, rule 3).
 */

import * as fs from "node:fs";
import * as path from "node:path";
import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";

/** CC-convention source var -> pi-ai route env var. Exported only if unset. */
const CREDENTIAL_BRIDGE: Record<string, string> = {
	BIGMODEL_ANTHROPIC_AUTH_TOKEN: "ZAI_CODING_CN_API_KEY",
	DEEPSEEK_ANTHROPIC_AUTH_TOKEN: "DEEPSEEK_API_KEY",
	MINIMAX_ANTHROPIC_AUTH_TOKEN: "MINIMAX_CN_API_KEY",
	QWEN3_ANTHROPIC_AUTH_TOKEN: "QWEN_TOKEN_PLAN_CN_API_KEY",
};

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

	// Credential bridge: CC-convention token -> pi-ai route env, never overriding.
	for (const [src, dst] of Object.entries(CREDENTIAL_BRIDGE)) {
		const token = process.env[src];
		if (token && !process.env[dst]) {
			process.env[dst] = token;
		}
	}
}
