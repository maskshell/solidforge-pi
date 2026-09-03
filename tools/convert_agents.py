#!/usr/bin/env python3
"""convert_agents.py — deterministic CC agent → Pi subagent conversion.

Rules (PORTING-PLAN.md §4.1, amended 2026-09-03 — pi packages spec):
  - frontmatter: emit BARE name (the `solidforge:` prefix is applied at load
    time by sf-subagents from package.json pi.namespace — single source of
    truth; do NOT hardcode it here), keep description,
    tools (mapped), model; strip CC-only fields
  - tool mapping: Read→read Grep→grep Glob→find LS→ls Edit→edit MultiEdit→edit Write→write Bash→bash
  - drop mcp__playwright-test__* (M3: adapter proxy), mcp__ast-grep__* (CLI path), WebSearch/WebFetch (no pi builtin; TODO)
  - body: `solidforge:<name>` references stay VERBATIM (runtime agent names
    carry the namespace, composed at load); backticked CC tool names → pi names
  - filename keeps source form `<name>.agent.md` (colon illegal-ish in filenames; name lives in frontmatter)
Re-runnable: output dir is regenerated (safe).
"""

import re
import sys
from pathlib import Path

SRC = Path("/Users/solosus/dev/ws-ai/solidforge/agents")
DST = Path(__file__).resolve().parent.parent / "agents"

TOOL_MAP = {
    "Read": "read",
    "Grep": "grep",
    "Glob": "find",
    "LS": "ls",
    "Edit": "edit",
    "MultiEdit": "edit",
    "Write": "write",
    "Bash": "bash",
    "WebSearch": None,
    "WebFetch": None,  # no pi builtin — dropped, TODO note
}
DROP_PREFIX = ("mcp__",)  # playwright (M3 adapter proxy) + ast-grep (CLI path)
AGENT_NAME_RE = re.compile(r"^([a-z0-9-]+)\.agent\.md$")


def map_tools(raw: str) -> list[str]:
    out, dropped = [], set()
    for tok in [t.strip() for t in raw.split(",") if t.strip()]:
        if any(tok.startswith(p) for p in DROP_PREFIX):
            dropped.add(tok)
            continue
        m = TOOL_MAP.get(tok)
        if m is None:
            dropped.add(tok)
        elif m not in out:
            out.append(m)
    return out, dropped


def convert(text: str, name: str) -> tuple[str, list[str]]:
    m = re.match(r"^---\n(.*?)\n---\n?(.*)$", text, re.DOTALL)
    if not m:
        raise ValueError(f"{name}: no frontmatter")
    fm_raw, body = m.group(1), m.group(2)
    notes: list[str] = []

    # parse simple frontmatter fields
    fields: dict[str, str] = {}
    for line in fm_raw.splitlines():
        km = re.match(r"^([A-Za-z_-]+):\s*(.*)$", line)
        if km:
            fields[km.group(1)] = km.group(2).strip()

    tools_line = fields.get("tools")
    if tools_line:
        mapped, dropped = map_tools(tools_line)
        if dropped:
            notes.append(
                f"# TODO(M3): dropped CC-only tools: {', '.join(sorted(dropped))}"
            )
    else:
        mapped = None

    # body: `solidforge:<name>` references stay verbatim — agent names keep the prefix.
    # (backticked CC tool-name cleanup is independent and still applies)
    for cc, pi in [
        ("Read", "read"),
        ("Grep", "grep"),
        ("Glob", "find"),
        ("LS", "ls"),
        ("MultiEdit", "edit"),
        ("Write", "write"),
        ("Bash", "bash"),
    ]:
        body = body.replace(f"`{cc}`", f"`{pi}`")

    fm_out = [f'name: "{name}"', f"description: {fields['description']}"]
    if mapped:
        fm_out.append(f"tools: {', '.join(mapped)}")
    if fields.get("model"):
        fm_out.append(f"model: {fields['model']}")
    return "---\n" + "\n".join(fm_out) + "\n---\n" + (
        "\n".join(notes) + "\n" if notes else ""
    ) + body, notes


def main():
    DST.mkdir(parents=True, exist_ok=True)
    for old in sorted(DST.glob("*.md")):
        old.unlink()
    count, flagged = 0, []
    for src in sorted(SRC.glob("*.agent.md")):
        name = AGENT_NAME_RE.match(src.name).group(1)
        out, notes = convert(src.read_text(encoding="utf-8"), name)
        (DST / f"{name}.agent.md").write_text(out, encoding="utf-8")
        count += 1
        if notes:
            flagged.append(f"solidforge:{name}: {'; '.join(notes)}")
    print(f"converted {count} agents -> {DST}")
    for f in flagged:
        print(f"  FLAG {f}")


if __name__ == "__main__":
    sys.exit(main())
