/**
 * Agent discovery and configuration
 */

import * as fs from "node:fs";
import * as path from "node:path";
import { CONFIG_DIR_NAME, getAgentDir, parseFrontmatter } from "@earendil-works/pi-coding-agent";

export type AgentScope = "user" | "project" | "both";

export interface AgentConfig {
	name: string;
	description: string;
	tools?: string[];
	model?: string;
	systemPrompt: string;
	source: "user" | "project" | "package";
	filePath: string;
}

export interface AgentDiscoveryResult {
	agents: AgentConfig[];
	projectAgentsDir: string | null;
	packageAgentsDir: string | null;
}

/**
 * Raw agent frontmatter. Values are `unknown` because `parseFrontmatter` runs a
 * real YAML parser, so any scalar or collection can appear here.
 *
 * A type alias rather than an interface: `parseFrontmatter` constrains its
 * parameter to `Record<string, unknown>`, and only an alias picks up the
 * implicit index signature that satisfies it.
 */
type AgentFrontmatter = {
	name?: unknown;
	description?: unknown;
	tools?: unknown;
	model?: unknown;
};

/**
 * Normalize a frontmatter `tools` value to a list of tool names.
 *
 * Both spellings are valid YAML and both are in use:
 *
 *     tools: read, bash        # string
 *     tools: [read, bash]      # array
 *
 * so accept either. Anything else (a number, a map, a nested list) yields no
 * tools rather than throwing: this runs inside agent discovery, where a single
 * bad file must not take down every other agent in the same directory.
 */
function parseToolList(value: unknown): string[] | undefined {
	const raw = Array.isArray(value) ? value : typeof value === "string" ? value.split(",") : [];
	const tools = raw
		.filter((t): t is string => typeof t === "string")
		.map((t) => t.trim())
		.filter(Boolean);
	return tools.length > 0 ? tools : undefined;
}

function loadAgentsFromDir(dir: string, source: "user" | "project" | "package"): AgentConfig[] {
	const agents: AgentConfig[] = [];

	if (!fs.existsSync(dir)) {
		return agents;
	}

	let entries: fs.Dirent[];
	try {
		entries = fs.readdirSync(dir, { withFileTypes: true });
	} catch {
		return agents;
	}

	for (const entry of entries) {
		if (!entry.name.endsWith(".md")) continue;
		if (!entry.isFile() && !entry.isSymbolicLink()) continue;

		const filePath = path.join(dir, entry.name);
		let content: string;
		try {
			content = fs.readFileSync(filePath, "utf-8");
		} catch {
			continue;
		}

		const { frontmatter, body } = parseFrontmatter<AgentFrontmatter>(content);

		if (typeof frontmatter.name !== "string" || typeof frontmatter.description !== "string") {
			continue;
		}

		agents.push({
			name: frontmatter.name,
			description: frontmatter.description,
			tools: parseToolList(frontmatter.tools),
			model: typeof frontmatter.model === "string" ? frontmatter.model : undefined,
			systemPrompt: body,
			source,
			filePath,
		});
	}

	return agents;
}

function isDirectory(p: string): boolean {
	try {
		return fs.statSync(p).isDirectory();
	} catch {
		return false;
	}
}

function findNearestProjectAgentsDir(cwd: string): string | null {
	let currentDir = cwd;
	while (true) {
		const candidate = path.join(currentDir, CONFIG_DIR_NAME, "agents");
		if (isDirectory(candidate)) return candidate;

		const parentDir = path.dirname(currentDir);
		if (parentDir === currentDir) return null;
		currentDir = parentDir;
	}
}

/**
 * Package root (solidforge-pi) — resolved relative to this module, so it
 * works regardless of where the package is installed.
 */
export function getPackageRoot(): string {
	const modulePath = decodeURIComponent(new URL(import.meta.url).pathname);
	return path.dirname(path.dirname(path.dirname(modulePath)));
}

/**
 * Package-bundled agents directory (solidforge-pi/agents).
 * Pi packages have no `agents/` resource type; this extension loads its own.
 */
export function getPackageAgentsDir(): string {
	return path.join(getPackageRoot(), "agents");
}

/** pi.namespace validity per the pi packages spec: lowercase a-z/0-9/hyphens,
 * <=64 chars, no leading/trailing or consecutive hyphens. */
const NAMESPACE_RE = /^[a-z0-9](?:[a-z0-9-]{0,62}[a-z0-9])?$/;

/**
 * The package's `pi.namespace` (package.json), read at load time so bundled
 * agent names follow the manifest — the pi packages spec's single source of
 * truth ("packages shipping subagents via their own extension should read
 * pi.namespace and prefix agent names with it"). Frontmatter stays bare;
 * an absent/invalid namespace loads agents un-prefixed (graceful).
 */
export function getPackageNamespace(): string | null {
	try {
		const manifest = JSON.parse(fs.readFileSync(path.join(getPackageRoot(), "package.json"), "utf-8"));
		const ns = (manifest as { pi?: { namespace?: unknown } })?.pi?.namespace;
		return typeof ns === "string" && NAMESPACE_RE.test(ns) ? ns : null;
	} catch {
		return null;
	}
}

export function discoverAgents(cwd: string, scope: AgentScope): AgentDiscoveryResult {
	const userDir = path.join(getAgentDir(), "agents");
	const projectAgentsDir = findNearestProjectAgentsDir(cwd);
	const packageAgentsDir = getPackageAgentsDir();

	const userAgents = scope === "project" ? [] : loadAgentsFromDir(userDir, "user");
	const projectAgents = scope === "user" || !projectAgentsDir ? [] : loadAgentsFromDir(projectAgentsDir, "project");
	// Package agents always load (they ship with the deliberately-installed package;
	// lowest precedence so user/project same-name agents override). Their names
	// carry the manifest namespace (pi packages spec) — prefix applied HERE from
	// pi.namespace, not hardcoded in frontmatter (single source of truth).
	// Idempotent: an already-prefixed name (legacy file) is not double-prefixed.
	const ns = getPackageNamespace();
	const packageAgents = loadAgentsFromDir(packageAgentsDir, "package").map((agent) =>
		ns && !agent.name.startsWith(`${ns}:`) ? { ...agent, name: `${ns}:${agent.name}` } : agent,
	);

	const agentMap = new Map<string, AgentConfig>();

	// Load order = precedence: later wins.
	for (const agent of packageAgents) agentMap.set(agent.name, agent);
	if (scope === "both") {
		for (const agent of userAgents) agentMap.set(agent.name, agent);
		for (const agent of projectAgents) agentMap.set(agent.name, agent);
	} else if (scope === "user") {
		for (const agent of userAgents) agentMap.set(agent.name, agent);
	} else {
		for (const agent of projectAgents) agentMap.set(agent.name, agent);
	}

	return { agents: Array.from(agentMap.values()), projectAgentsDir, packageAgentsDir };
}

export function formatAgentList(agents: AgentConfig[], maxItems: number): { text: string; remaining: number } {
	if (agents.length === 0) return { text: "none", remaining: 0 };
	const listed = agents.slice(0, maxItems);
	const remaining = agents.length - listed.length;
	return {
		text: listed.map((a) => `${a.name} (${a.source}): ${a.description}`).join("; "),
		remaining,
	};
}
