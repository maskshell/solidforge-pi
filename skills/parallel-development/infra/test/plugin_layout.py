#!/usr/bin/env python3
"""Plugin-layout self-check for the Solid Forge plugin.

Loading-chain check for the PLUGIN BOUNDARY (the analog of disconnect_check.py for the new layout). Asserts the plugin's structural pieces exist and are well-formed so a model following progressive disclosure from plugin-enable never hits a dead end:

  - package.json parses and carries the pi manifest (pi.extensions incl. sf-hooks, pi.skills, pi.prompts, pi.namespace)
  - extensions/sf-hooks/index.ts wires the python hook bridge (tool_call/tool_result subscription, CLAUDE_PROJECT_DIR env bridge, the three hook scripts)
  - prompts/arm-tools.md exists (plain filename; the /solidforge:arm-tools invocation is namespace-composed from pi.namespace at load — literal-colon filename retired 2026-08-29)
  - agents/ contains EXACTLY the 22 plugin-bundled agents, by BARE frontmatter name (the solidforge: namespace is composed at load time by sf-subagents from pi.namespace, per the pi packages spec; amended 2026-09-03)
  - every agent that references a references/agent-patterns/<role>.md companion has that companion bundled under skills/parallel-development/references/agent-patterns/ (catches the loading-chain break where an agent points at a companion that was not copied)

The hook command PATHS use ${CLAUDE_PLUGIN_ROOT}/skills/parallel-development/... (resolved at runtime on plugin-enable). This check validates STRUCTURE (files present + well-formed), not runtime resolution.

Run:
    python3 infra/test/plugin_layout.py
"""

import glob
import json
import os
import re
import sys


# plugin_layout.py lives at <plugin-root>/skills/parallel-development/infra/test/.
# Locate the plugin root by walking up to .claude-plugin/plugin.json — depth-independent, so it survives the skill nesting introduced at the Phase 4 cutover (skill moved off the repo root).
def _find_plugin_root(start):
    # PI PORT: walk up to package.json (the pi manifest)
    cur = os.path.abspath(start)
    while True:
        if os.path.exists(os.path.join(cur, "package.json")):
            return cur
        parent = os.path.dirname(cur)
        if parent == cur:
            return None
        cur = parent
        cur = parent


_HERE = os.path.dirname(os.path.abspath(__file__))
PLUGIN_ROOT = _find_plugin_root(_HERE)
if PLUGIN_ROOT is None:
    print(f"FAIL: no package.json found walking up from {_HERE}")
    sys.exit(1)

PACKAGE_JSON = os.path.join(PLUGIN_ROOT, "package.json")
SF_HOOKS_EXT = os.path.join(PLUGIN_ROOT, "extensions", "sf-hooks", "index.ts")
ARM_TOOLS_MD = os.path.join(PLUGIN_ROOT, "prompts", "arm-tools.md")
AGENTS_DIR = os.path.join(PLUGIN_ROOT, "agents")

# The 22 plugin-bundled agents, BARE frontmatter names (sf-subagents composes
# the solidforge: namespace at load from pi.namespace — single source of truth).
EXPECTED_AGENTS = [
    "architect",
    "backend-developer",
    "claim-extractor",
    "claim-verifier",
    "code-reviewer",
    "collision-verifier",
    "devops-engineer",
    "doc-reviewer",
    "documentation-writer",
    "frontend-developer",
    "graphiti-config-generator",
    "ios-developer",
    "ios-tester",
    "novelty-claim-extractor",
    "plan-reviewer",
    "playwright-test-generator",
    "playwright-test-healer",
    "playwright-test-planner",
    "requirements-manager",
    "researcher",
    "security-specialist",
    "tester",
]

# The three hook scripts the hooks.json must wire (by basename substring in the command).
EXPECTED_HOOK_SCRIPTS = ["blueprint_guard", "counters", "fast_gate"]

# The two skills bundled under skills/ (Phase 4 cutover moved them off the repo root).
EXPECTED_SKILLS = [
    "parallel-development",
    "blueprint-crafting",
    "cross-source-review",
    "primary-source-verification",
    "prior-art-search",
]
SKILLS_DIR = os.path.join(PLUGIN_ROOT, "skills")

RESULTS = []


def check(name, cond, how):
    RESULTS.append((name, bool(cond), how))
    print(f"  {'ok' if cond else 'FAIL'}: {name}")
    return bool(cond)


def _frontmatter_name(text):
    """Extract the `name:` field from an agent file's YAML frontmatter."""
    if not text.startswith("---"):
        return None
    end = text.find("\n---", 3)
    fm = text[3:end] if end != -1 else text[3:]
    m = re.search(r"^name:\s*(.+?)\s*$", fm, re.MULTILINE)
    return m.group(1).strip().strip('"').strip("'") if m else None


def t_plugin_manifest():
    print("package.json (pi manifest):")
    if not check(
        "package.json exists", os.path.exists(PACKAGE_JSON), f"create {PACKAGE_JSON}"
    ):
        return
    try:
        data = json.load(open(PACKAGE_JSON, encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        check("package.json parses", False, f"fix JSON: {exc}")
        return
    check(
        "pi-package keyword",
        "pi-package" in data.get("keywords", []),
        'add "pi-package" to keywords',
    )
    pi = data.get("pi", {})
    for key, entry in (
        ("extensions", "extensions"),
        ("skills", "skills"),
        ("prompts", "prompts"),
    ):
        check(
            f"pi.{key} declares ./{entry}",
            any(str(x).lstrip("./").startswith(entry) for x in pi.get(key, [])),
            f'add "./{entry}" to pi.{key}',
        )


def _hook_commands(hooks_obj):
    cmds = []
    for event in ("PreToolUse", "PostToolUse"):
        for grp in hooks_obj.get(event, []):
            for h in grp.get("hooks", []):
                cmds.append(h.get("command", ""))
    return cmds


def t_hooks_json():
    print("extensions/sf-hooks/index.ts (pi hook wiring):")
    if not check(
        "sf-hooks exists", os.path.exists(SF_HOOKS_EXT), f"create {SF_HOOKS_EXT}"
    ):
        return
    text = open(SF_HOOKS_EXT, encoding="utf-8").read()
    check("subscribes tool_call", '"tool_call"' in text, 'pi.on("tool_call", ...)')
    check(
        "subscribes tool_result", '"tool_result"' in text, 'pi.on("tool_result", ...)'
    )
    check(
        "sets CLAUDE_PROJECT_DIR (env bridge)",
        "CLAUDE_PROJECT_DIR" in text,
        "the python hooks resolve the project root via CLAUDE_PROJECT_DIR",
    )
    for script in EXPECTED_HOOK_SCRIPTS:
        check(
            f"wires hook script {script}.py",
            f'"{script}.py"' in text,
            f"add {script}.py to the shim's script list",
        )


def t_arm_tools_command():
    print("prompts/arm-tools.md:")
    check("arm-tools.md exists", os.path.exists(ARM_TOOLS_MD), f"create {ARM_TOOLS_MD}")


def t_agents():
    print("agents/:")
    if not check(
        "agents/ dir exists", os.path.isdir(AGENTS_DIR), f"create {AGENTS_DIR}"
    ):
        return
    agent_files = [
        f
        for f in glob.glob(os.path.join(AGENTS_DIR, "*.md"))
        if not f.endswith(".patterns.md")
    ]
    names = {}
    for f in agent_files:
        text = open(f, encoding="utf-8").read()
        nm = _frontmatter_name(text)
        if nm:
            names[nm] = f
    # PI PORT (amended 2026-09-03): agents carry BARE names in frontmatter;
    # sf-subagents composes <pi.namespace>:<name> at load (pi packages spec).
    for expected in EXPECTED_AGENTS:
        check(
            f"agent present: {expected}",
            expected in names,
            f"copy {expected}.agent.md into agents/ (BARE frontmatter name "
            f'"{expected}" — the solidforge: prefix is composed at load)',
        )
    # bidirectional: a stray agent outside EXPECTED_AGENTS would silently ride
    # the package (mirror of pi_loader_smoke extensions-registered direction B)
    extras = sorted(set(names) - set(EXPECTED_AGENTS))
    check(
        "no unexpected agents",
        not extras,
        f"remove {extras} or register them in EXPECTED_AGENTS (a stray agent "
        "silently ships to every user)",
    )
    # companion coverage: any agent referencing a references/agent-patterns/<role>.md
    # companion must have it bundled under skills/parallel-development/references/agent-patterns/.
    # The agent link form is ../skills/parallel-development/references/agent-patterns/<role>.md
    # (contains slashes, so the old [\w-]+\.patterns.md class no longer matches). Structural move,
    # not a decision-point addition (rule 2): the check's purpose is unchanged, only the location.
    ref_re = re.compile(r"parallel-development/references/agent-patterns/([\w-]+)\.md")
    referenced = set()
    for f in agent_files:
        referenced.update(ref_re.findall(open(f, encoding="utf-8").read()))
    companion_dir = os.path.join(
        SKILLS_DIR, "parallel-development", "references", "agent-patterns"
    )
    for comp in sorted(referenced):
        check(
            f"companion bundled: agent-patterns/{comp}.md",
            os.path.exists(os.path.join(companion_dir, comp + ".md")),
            f"copy {comp}.md into skills/parallel-development/references/agent-patterns/ (an agent references it)",
        )


def t_skills():
    print("skills/:")
    for skill in EXPECTED_SKILLS:
        skill_md = os.path.join(SKILLS_DIR, skill, "SKILL.md")
        check(
            f"skill bundled: {skill}/SKILL.md",
            os.path.exists(skill_md),
            f"move {skill}/ under {SKILLS_DIR} (Phase 4 cutover)",
        )


def main():
    for fn in (
        t_plugin_manifest,
        t_hooks_json,
        t_arm_tools_command,
        t_skills,
        t_agents,
    ):
        print(f"\n{fn.__name__}:")
        fn()
    failed = [(n, how) for n, ok, how in RESULTS if not ok]
    print(
        f"\n{'PASS' if not failed else 'FAIL'} ({len(RESULTS) - len(failed)}/{len(RESULTS)})"
    )
    if failed:
        for n, how in failed:
            print(f"  FAILED: {n} -> {how}")
        sys.exit(1)


if __name__ == "__main__":
    main()
