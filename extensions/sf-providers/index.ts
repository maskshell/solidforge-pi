/**
 * sf-providers — SolidForge hetero credential bridge (pi port, v2).
 *
 * REDESIGN (M2.5, informed by solidforge-dsh's FILENAME=ROUTE + catalog-inherit
 * principle): pi's built-in catalog ALREADY carries most hetero target routes —
 * `zai-coding-cn` (glm-5.x, coding endpoint, openai-completions), `deepseek`
 * (v4-flash/pro, native endpoint), `minimax-cn` (MiniMax-M3, anthropic endpoint).
 * Registering custom providers for THOSE would duplicate model facts that can
 * then drift from the catalog — the M1 "GLM-5.2 calibration" misdiagnosis came
 * exactly from a custom bigmodel/anthropic-endpoint registration.
 *
 * So the default is: register NOTHING, bridge CREDENTIALS only (CC-convention
 * token vars -> pi-ai route env names, never overriding existing auth).
 *
 * THE ONE EXCEPTION — `qwen-bailian` (v2.1): Alibaba Bailian's pay-as-you-go
 * DashScope endpoint (`dashscope.aliyuncs.com/compatible-mode/v1`) has NO
 * built-in pi route (the three catalog qwen routes are token-plan SUBSCRIPTION
 * endpoints that reject pay-per-use keys — observed live: 401 on
 * token-plan.cn-beijing with a working Bailian key). Registering it adds NEW
 * information the catalog lacks — no duplication, no drift surface. Registered
 * ONLY when QWEN3_ANTHROPIC_AUTH_TOKEN is present (absent token = route absent,
 * graceful). Model facts are copied from the catalog's qwen3.8-max entry (same
 * model, different billing channel); pay-per-use pricing is UNKNOWN to the
 * catalog (token-plan entry says 0) so cost stays honest-zero — cost telemetry
 * for this route reads 0. The adapter parses reasoning_content generically
 * (verified in pi-ai api/openai-completions.js).
 */

import * as fs from "node:fs";
import * as path from "node:path";
import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";

/** CC-convention source var -> pi-ai route env var. Exported only if unset. */
const CREDENTIAL_BRIDGE: Record<string, string> = {
	BIGMODEL_ANTHROPIC_AUTH_TOKEN: "ZAI_CODING_CN_API_KEY",
	DEEPSEEK_ANTHROPIC_AUTH_TOKEN: "DEEPSEEK_API_KEY",
	MINIMAX_ANTHROPIC_AUTH_TOKEN: "MINIMAX_CN_API_KEY",
};

/** Bailian pay-as-you-go key var (the qwen-bailian route's credential). */
const BAILIAN_TOKEN_ENV = "QWEN3_ANTHROPIC_AUTH_TOKEN";

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

	// The ONE non-catalog route: Bailian pay-as-you-go DashScope. Registered only
	// when the token is present. Facts copied from the catalog's qwen3.8-max entry
	// (same model as the token-plan channel); pay-per-use pricing unknown -> 0.
	const bailianToken = process.env[BAILIAN_TOKEN_ENV];
	if (bailianToken) {
		pi.registerProvider("qwen-bailian", {
			baseUrl: "https://dashscope.aliyuncs.com/compatible-mode/v1",
			apiKey: `$${BAILIAN_TOKEN_ENV}`,
			api: "openai-completions",
			models: [
				{
					id: "qwen3.8-max",
					name: "Qwen3.8 Max (Bailian pay-as-you-go)",
					reasoning: true,
					input: ["text", "image"],
					cost: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0 },
					contextWindow: 1_000_000,
					maxTokens: 131_072,
					// compat + thinkingLevelMap copied VERBATIM from the catalog's
					// qwen3.8-max entry (same model). Load-bearing: without
					// supportsDeveloperRole:false pi sends the system prompt as an
					// OpenAI `developer` role, which DashScope rejects (400 "developer
					// is not one of [...]") — observed live.
					compat: {
						thinkingFormat: "qwen",
						supportsDeveloperRole: false,
						supportsStore: false,
						supportsReasoningEffort: true,
					},
					thinkingLevelMap: {
						minimal: null,
						low: "low",
						medium: "medium",
						high: null,
						xhigh: "xhigh",
						max: null,
					},
				},
				{
					id: "qwen3.7-max",
					name: "Qwen3.7 Max (Bailian pay-as-you-go)",
					reasoning: true,
					input: ["text"],
					cost: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0 },
					contextWindow: 262_144,
					maxTokens: 131_072,
					compat: {
						thinkingFormat: "qwen",
						supportsDeveloperRole: false,
						supportsStore: false,
						supportsReasoningEffort: true,
					},
				},
			],
		});
	}
}
