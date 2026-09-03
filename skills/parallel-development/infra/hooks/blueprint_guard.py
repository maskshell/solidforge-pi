#!/usr/bin/env python3
"""blueprint_guard.py — PreToolUse hook: enforce frozen read-only anchors.

Guards FOUR anchor kinds (distinct freeze signals, one deny path):
  - Intent Blueprint: paths under any `intent-blueprints/` dir ending in `.blueprint.md` (the Phase-0 convergence anchor).
    Freeze = frontmatter `status: frozen`.
  - Plan Queue: paths under any `plan-queues/` dir ending in `.queue.md` (plan-driven-mode anchor).
    Freeze = frontmatter `status: frozen`.
  - Design (external skill): any `DESIGN.md` (Impeccable; see references/external-skills.md).
    Freeze = side-car sentinel `.claude/parallel-dev/design.frozen` (DESIGN.md's frontmatter is an external token-export with no `status` field).
  - OpenAPI spec (external skill, Depth 2): any `openapi.{json,yaml,yml}` / `swagger.{json,yaml,yml}` (Spectral; see references/external-skills.md, ADR 23).
    Freeze = side-car sentinel `.claude/parallel-dev/openapi.frozen` (the spec is external-authored; frozen at Phase 0 so the implementer codes against a stable contract).

Each is FROZEN after its freeze step and must be read-only for the Coder mid-loop. The only legitimate change path is the Revision Channel — with ONE carve-out (ADR #58): a frozen Intent Blueprint's `## Acceptance-Criteria -> Test Mapping` section is APPEND-OPEN. The mapping records RED-phase observations (real test names exist only after RED writes the tests), so a wholesale deny left the mapping section unreachable as documented and the test-name set gate dormant. An Edit/Write/MultiEdit to a frozen blueprint is allowed iff BOTH hold:
  (1) old and new content are byte-identical after stripping the mapping region — the section's H2 header line, its `- AC-x -> test` bullet lines, and blank runs adjacent to them, with symmetric EOF trailing-blank normalization (section-aware, mirroring parse_ac_test_map's H1/H2 toggle; prose inside the section and everything outside it stay frozen);
  (2) the (ac_id, test_name) pair set only grows — no removal, no value rename — and the mapping-header count does not decrease (deleting the heading would silently re-dormant the gate).
A mapping bullet correction therefore goes through the Revision Channel like any intent change. Plan-queues / DESIGN.md / openapi specs keep the wholesale deny (no mapping semantics).

Deterministic guard (freeze signal differs per kind):
  - blueprint / plan-queue: DENY if the target's YAML frontmatter has `status: frozen` (`status: revising` / missing / other, or a brand-new Write -> allow) — except the blueprint mapping carve-out above.
  - design (DESIGN.md): DENY if the side-car sentinel `.claude/parallel-dev/design.frozen` exists (DESIGN.md's frontmatter is an external token-export with no `status`).
  - openapi (spec): DENY if the side-car sentinel `.claude/parallel-dev/openapi.frozen` exists (same side-car model as design; the spec is external-authored).
"""

import json
import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "lib"))
import detect_toolchain as dt  # noqa: E402

BLUEPRINT_RE = re.compile(r"(^|/)intent-blueprints/.+\.blueprint\.md$")
PLAN_QUEUE_RE = re.compile(r"(^|/)plan-queues/.+\.queue\.md$")
DESIGN_RE = re.compile(r"(^|/)DESIGN\.md$")
OPENAPI_RE = re.compile(r"(^|/)(openapi|swagger)\.(json|ya?ml)$")
FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*(?:\n|$)", re.DOTALL)
STATUS_RE = re.compile(r"^\s*status\s*:\s*['\"]?(\w+)['\"]?\s*$", re.MULTILINE)

# Mapping-carve-out shapes (ADR #58) — duplicated from arch_contract_tests.py's
# parse_ac_test_map on purpose (self-contained-script convention, rule 7): the
# guard's open region must match the parser's read region EXACTLY, byte-shape
# included, or the carve-out drifts from the gate it feeds.
AC_TEST_MAP_HEADER_RE = re.compile(
    r"^##\s+Acceptance[\s-]+Criteria\s*(?:->|→)\s*Test\s+Mapping", re.IGNORECASE
)
AC_TEST_LINE_RE = re.compile(
    r"^\s*[-*]\s+([A-Za-z][\w-]*)\s*(?:->|→)\s*(\S(?:.*\S)?)\s*$"
)


def anchor_kind(path):
    """Return 'blueprint' | 'plan-queue' | 'design' | 'openapi' | None for a path."""
    if not path:
        return None
    if BLUEPRINT_RE.search(path):
        return "blueprint"
    if PLAN_QUEUE_RE.search(path):
        return "plan-queue"
    if DESIGN_RE.search(path):
        return "design"
    if OPENAPI_RE.search(path):
        return "openapi"
    return None


def frozen_status(path):
    if not path or not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as fh:
            head = fh.read(4096)
    except OSError:
        return None
    fm = FRONTMATTER_RE.match(head)
    if not fm:
        return None
    m = STATUS_RE.search(fm.group(1))
    return m.group(1) if m else None


def design_is_frozen():
    """The design anchor (DESIGN.md) is external/Impeccable-owned — its frontmatter has no `status`, so its freeze is a side-car sentinel next to loop-state, not frontmatter. Set at Phase 0, cleared at converge (orchestrator manages the sentinel). See references/external-skills.md."""
    return os.path.exists(os.path.join(dt.state_dir(), "design.frozen"))


def openapi_is_frozen():
    """The OpenAPI-spec anchor (Spectral, Depth 2) is external-authored, so its freeze is a side-car sentinel next to loop-state, not frontmatter. Set at Phase 0, cleared at converge (orchestrator manages the sentinel). See references/external-skills.md, ADR 23."""
    return os.path.exists(os.path.join(dt.state_dir(), "openapi.frozen"))


def _walk_mapping_section(text):
    """Yield (line, in_section) per line, toggling section state exactly like
    parse_ac_test_map: an H1/H2 heading closes (or re-opens, if it is the
    mapping header) the section; deeper headings are content. The carve-out's
    open region mirrors the parser's read region — same walk, same shapes."""
    in_section = False
    for line in (text or "").splitlines():
        if line.startswith("#"):
            level = len(line) - len(line.lstrip("#"))
            if level <= 2:
                in_section = level == 2 and bool(AC_TEST_MAP_HEADER_RE.match(line))
            yield line, in_section
            continue
        yield line, in_section


def _strip_mapping_region(text):
    """Remove the section's H2 header line, its AC-test bullet lines, and blank
    runs ADJACENT to them (insertion-point formatting noise — a section added
    mid-file carries its own surrounding blanks). Prose inside the section and
    every line outside it STAY — they are compared byte-for-byte, so only
    header+bullets(+their adjacent blanks) are malleable (ADR #58)."""
    lines = text.splitlines()
    strippable = [False] * len(lines)
    for i, (line, in_section) in enumerate(_walk_mapping_section(text)):
        if in_section and (line.startswith("#") or AC_TEST_LINE_RE.match(line)):
            strippable[i] = True
    # A blank line strips iff its nearest non-blank neighbor above OR below is
    # strippable — that makes it boundary formatting, not content. A blank
    # between two frozen lines (kept neighbors on both sides) stays frozen.
    changed = True
    while changed:
        changed = False
        for i, line in enumerate(lines):
            if strippable[i] or line.strip():
                continue
            up = next((j for j in range(i - 1, -1, -1) if lines[j].strip()), None)
            down = next((j for j in range(i + 1, len(lines)) if lines[j].strip()), None)
            if (up is not None and strippable[up]) or (
                down is not None and strippable[down]
            ):
                strippable[i] = True
                changed = True
    kept = [line for i, line in enumerate(lines) if not strippable[i]]
    # Symmetric EOF normalization: drop the trailing blank run from BOTH
    # residuals. A file frozen with trailing blanks would otherwise deny every
    # section append (old keeps its EOF blank, new absorbs it as boundary
    # formatting) — and blanks-at-EOF carry no content, so nothing is hidden.
    while kept and not kept[-1].strip():
        kept.pop()
    return "\n".join(kept)


def _mapping_pairs(text):
    """Set of (ac_id, test_name) from AC-test bullets INSIDE the section — the
    same pairs parse_ac_test_map would collect (order-free compare is enough
    for the no-removal invariant)."""
    pairs = set()
    for line, in_section in _walk_mapping_section(text):
        if in_section and not line.startswith("#"):
            m = AC_TEST_LINE_RE.match(line)
            if m:
                pairs.add((m.group(1), m.group(2).strip()))
    return pairs


def _mapping_header_count(text):
    """Number of H2 mapping headers — deleting the heading unmapped the section
    (the gate would go dormant), so the count must not decrease."""
    return sum(
        1
        for line, _ in _walk_mapping_section(text)
        if line.startswith("#") and AC_TEST_MAP_HEADER_RE.match(line)
    )


def _apply_edit(text, old, new, replace_all):
    """Apply one Edit-shaped substitution with the tool's own semantics: fail
    on a missing target; without replace_all, fail on a non-unique target. Any
    failure makes the guard fall back to deny (conservative — the edit itself
    would not have landed)."""
    if not isinstance(old, str) or not isinstance(new, str) or old not in text:
        raise ValueError("edit target missing or malformed")
    if not replace_all and text.count(old) > 1:
        raise ValueError("non-unique edit target")
    return text.replace(old, new) if replace_all else text.replace(old, new, 1)


def mapping_append_ok(path, tool, tool_input):
    """ADR #58 carve-out: True iff the proposed edit touches ONLY the frozen
    blueprint's mapping region (header + AC-test bullets) AND the (ac_id,
    test_name) pair set only grows. Everything else — intent, NFRs, seams, even
    the mapping section's own prose — stays byte-frozen."""
    try:
        with open(path, "r", encoding="utf-8") as fh:
            old_text = fh.read()
    except OSError:
        return False
    try:
        if tool == "Write":
            new_text = tool_input["content"]
            if not isinstance(new_text, str):
                return False
        elif tool == "Edit":
            new_text = _apply_edit(
                old_text,
                tool_input["old_string"],
                tool_input["new_string"],
                bool(tool_input.get("replace_all", False)),
            )
        elif tool == "MultiEdit":
            new_text = old_text
            for edit in tool_input["edits"]:
                new_text = _apply_edit(
                    new_text,
                    edit["old_string"],
                    edit["new_string"],
                    bool(edit.get("replace_all", False)),
                )
        else:
            return False
    except (KeyError, TypeError, ValueError):
        return False
    return (
        _strip_mapping_region(old_text) == _strip_mapping_region(new_text)
        and _mapping_pairs(old_text) <= _mapping_pairs(new_text)
        and _mapping_header_count(old_text) <= _mapping_header_count(new_text)
    )


def deny(reason):
    print(
        json.dumps(
            {
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "permissionDecision": "deny",
                    "permissionDecisionReason": reason,
                }
            }
        )
    )
    sys.exit(0)


DENY_MESSAGES = {
    "blueprint": (
        "Blueprint {path} is FROZEN and read-only (Intent Blueprint anchor). "
        "The Coder cannot edit it. The ONLY post-freeze edit that passes is an APPEND to the "
        "`## Acceptance-Criteria -> Test Mapping` section (add `- AC-x -> <test-name>` bullets; "
        "no removals, no renames, nothing outside the section — ADR #58). "
        "To change intent (or correct a mapping bullet), open the Blueprint Revision Channel: "
        "set frontmatter status to 'revising', escalate to Planner (requirements-manager/Plan) + human, revise, bump blueprint_version, then set status back to 'frozen'. "
        "See references/intent-blueprint.md."
    ),
    "plan-queue": (
        "Plan Queue {path} is FROZEN and read-only (plan-driven-mode anchor). "
        "The Coder cannot edit the plan interpretation mid-chain. To revise it, open the Revision Channel: set frontmatter status to 'revising', edit, bump queue_version, set status back to 'frozen', then run `plan_queue.py sync`. "
        "See references/plan-driven-mode.md."
    ),
    "design": (
        "DESIGN.md {path} is FROZEN (external-skill convergence anchor; freeze set via the side-car sentinel .claude/parallel-dev/design.frozen). The Coder cannot edit it mid-loop. To revise, open the Blueprint Revision Channel: the orchestrator clears the design freeze, revises DESIGN.md via /impeccable (document/extract), then re-freezes. See references/external-skills.md."
    ),
    "openapi": (
        "OpenAPI spec {path} is FROZEN (external-skill convergence anchor, Spectral Depth 2; freeze set via the side-car sentinel .claude/parallel-dev/openapi.frozen). The Coder cannot edit it mid-loop. To revise, open the Blueprint Revision Channel: the orchestrator clears the openapi freeze, revises the spec, then re-freezes. See references/external-skills.md, ADR 23."
    ),
}


def main():
    payload = dt.read_payload()
    tool = payload.get("tool_name", "")
    if tool not in ("Edit", "Write", "MultiEdit"):
        sys.exit(0)

    file_path = (payload.get("tool_input") or {}).get("file_path")
    kind = anchor_kind(file_path)
    if not kind:
        sys.exit(0)

    # The design anchor (DESIGN.md) is external-owned: its freeze is a side-car sentinel, not frontmatter `status` (DESIGN.md's frontmatter is an Impeccable token-export with no status).
    if kind == "design":
        if design_is_frozen():
            deny(DENY_MESSAGES["design"].format(path=file_path))
        sys.exit(0)

    # The openapi anchor (Spectral, Depth 2) is external-authored: same side-car sentinel model as design.
    if kind == "openapi":
        if openapi_is_frozen():
            deny(DENY_MESSAGES["openapi"].format(path=file_path))
        sys.exit(0)

    if frozen_status(file_path) == "frozen":
        # ADR #58 mapping carve-out — blueprint kind only: an append-only edit
        # to the AC->test mapping region passes; everything else denies below.
        if kind == "blueprint" and mapping_append_ok(
            file_path, tool, payload.get("tool_input") or {}
        ):
            sys.exit(0)
        deny(DENY_MESSAGES[kind].format(path=file_path))
    sys.exit(0)


if __name__ == "__main__":
    main()
