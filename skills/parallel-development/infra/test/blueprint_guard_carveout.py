#!/usr/bin/env python3
"""blueprint_guard mapping carve-out (ADR #58) — the ONE post-freeze edit that
passes is an APPEND to a frozen blueprint's `## Acceptance-Criteria -> Test
Mapping` section. Verifies via the REAL hook invocation path (stdin payload +
subprocess, per hooks-reference.md "How to test a hook"), not by importing
main(): the deny path, the append-open path, the weakening paths (bullet
delete / rename / heading delete / section-prose edit), Write + MultiEdit
shapes, and the no-carve-out regressions (plan-queue wholesale deny, revising
status, non-anchor files).

Run: python3 infra/test/blueprint_guard_carveout.py
"""

import json
import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
HOOK = os.path.normpath(os.path.join(HERE, "..", "hooks", "blueprint_guard.py"))

BLUEPRINT_BODY = """---
blueprint_version: v1
frozen_at: 2026-08-25
task: carve-out probe
status: frozen
---

# Intent Blueprint — carve-out probe

## Core Use Cases

- UC-1: must implement the widget

## Acceptance Criteria (BDD)

- AC-1: Given a user When the form submits Then the widget renders — seam: `renderWidget` (catches: render path; misses: validation)

## Non-Functional Requirements

- NFR-1: response under 500ms

## Acceptance-Criteria -> Test Mapping

Declared at RED phase. Maps each AC to the executable test(s) that verify it.

- AC-1 -> test_renders_widget
"""


def _fail(msg):
    raise AssertionError(msg)


def _run_hook(tool, tool_input):
    """Invoke the hook exactly as Claude Code would: JSON payload on stdin."""
    payload = json.dumps({"tool_name": tool, "tool_input": tool_input})
    proc = subprocess.run(
        [sys.executable, HOOK],
        input=payload,
        capture_output=True,
        text=True,
        env={**os.environ, "CLAUDE_PROJECT_DIR": os.getcwd()},
    )
    return proc.returncode, proc.stdout


def _blueprint(root, name="task-v1", status="frozen", with_mapping=True):
    body = BLUEPRINT_BODY
    if status != "frozen":
        body = body.replace("status: frozen", f"status: {status}")
    if not with_mapping:
        body = body.replace(
            "\n\n## Acceptance-Criteria -> Test Mapping\n\nDeclared at RED phase. "
            "Maps each AC to the executable test(s) that verify it.\n\n- AC-1 -> test_renders_widget\n",
            "\n",
        )
    path = os.path.join(root, "docs", "intent-blueprints", f"{name}.blueprint.md")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(body)
    return path


def _expect_allow(path, tool, tool_input, label):
    code, out = _run_hook(tool, {**tool_input, "file_path": path})
    if code != 0 or out.strip():
        _fail(f"{label}: expected silent allow, got exit={code} stdout={out!r}")


def _expect_deny(path, tool, tool_input, label):
    code, out = _run_hook(tool, {**tool_input, "file_path": path})
    if code != 0 or "FROZEN" not in out:
        _fail(f"{label}: expected deny, got exit={code} stdout={out!r}")


def _read(path):
    with open(path, "r", encoding="utf-8") as fh:
        return fh.read()


def check_carveout_append_allow():
    with tempfile.TemporaryDirectory() as root:
        path = _blueprint(root)
        # Append a new bullet (Edit): the canonical RED-phase record act.
        _expect_allow(
            path,
            "Edit",
            {
                "old_string": "- AC-1 -> test_renders_widget",
                "new_string": "- AC-1 -> test_renders_widget\n- AC-1 -> tests/test_widget.py::test_renders_widget_default",
            },
            "append mapping bullet (Edit)",
        )
        # Add a bullet for a NEW AC id.
        _expect_allow(
            path,
            "Edit",
            {
                "old_string": "- AC-1 -> test_renders_widget",
                "new_string": "- AC-1 -> test_renders_widget\n- AC-2 -> test_validates_input",
            },
            "append new-AC mapping bullet (Edit)",
        )
        # Write (full content): identical outside the mapping region, one bullet added.
        new_text = _read(path).replace(
            "- AC-1 -> test_renders_widget",
            "- AC-1 -> test_renders_widget\n- AC-3 -> test_extra",
        )
        _expect_allow(
            path, "Write", {"content": new_text}, "append mapping bullet (Write)"
        )
        # MultiEdit: two appends, sequential on the evolving text.
        _expect_allow(
            path,
            "MultiEdit",
            {
                "edits": [
                    {
                        "old_string": "- AC-1 -> test_renders_widget",
                        "new_string": "- AC-1 -> test_renders_widget\n- AC-4 -> test_four",
                    },
                    {
                        "old_string": "- AC-1 -> test_renders_widget\n- AC-4 -> test_four",
                        "new_string": "- AC-1 -> test_renders_widget\n- AC-4 -> test_four\n- AC-5 -> test_five",
                    },
                ]
            },
            "append mapping bullets (MultiEdit)",
        )
    print("  append-only mapping edits (Edit/Write/MultiEdit) allow: PASS")


def check_carveout_weakening_deny():
    with tempfile.TemporaryDirectory() as root:
        path = _blueprint(root)
        # Delete a bullet -> gate would lose its tripwire list.
        _expect_deny(
            path,
            "Edit",
            {
                "old_string": "- AC-1 -> test_renders_widget\n",
                "new_string": "",
            },
            "delete mapping bullet",
        )
        # Rename a bullet's test value: remove+add of the same ac_id.
        _expect_deny(
            path,
            "Edit",
            {
                "old_string": "- AC-1 -> test_renders_widget",
                "new_string": "- AC-1 -> test_renders_widget_v2",
            },
            "rename mapping bullet value",
        )
        # Delete the section heading: parse_ac_test_map goes dormant.
        _expect_deny(
            path,
            "Edit",
            {
                "old_string": "## Acceptance-Criteria -> Test Mapping\n",
                "new_string": "",
            },
            "delete mapping heading (unmapping)",
        )
        # Edit prose INSIDE the mapping section (not header/bullet): frozen.
        _expect_deny(
            path,
            "Edit",
            {
                "old_string": "Declared at RED phase.",
                "new_string": "Declared at GREEN phase.",
            },
            "edit mapping-section prose",
        )
    print("  weakening edits (delete/rename/unmap/prose) deny: PASS")


def check_intent_still_frozen():
    with tempfile.TemporaryDirectory() as root:
        path = _blueprint(root)
        _expect_deny(
            path,
            "Edit",
            {
                "old_string": "- UC-1: must implement the widget",
                "new_string": "- UC-1: changed",
            },
            "edit Core Use Case",
        )
        _expect_deny(
            path,
            "Edit",
            {
                "old_string": "- NFR-1: response under 500ms",
                "new_string": "- NFR-1: 5s",
            },
            "edit NFR",
        )
        _expect_deny(
            path,
            "Edit",
            {
                "old_string": "seam: `renderWidget`",
                "new_string": "seam: `_renderInternal`",
            },
            "edit AC seam",
        )
        # Gutting attempt: relocate UC content under the mapping heading. The UC
        # lines do not strip (outside section) and the heading is duplicated —
        # stripped remainders differ -> deny.
        new_text = (
            _read(path)
            .replace(
                "- UC-1: must implement the widget\n",
                "",
            )
            .replace(
                "## Acceptance-Criteria -> Test Mapping\n",
                "## Acceptance-Criteria -> Test Mapping\n\n- UC-1: must implement the widget\n",
            )
        )
        _expect_deny(
            path, "Write", {"content": new_text}, "relocate UC under mapping heading"
        )
        # MultiEdit mixing an intent edit with a legit mapping append.
        _expect_deny(
            path,
            "MultiEdit",
            {
                "edits": [
                    {
                        "old_string": "- NFR-1: response under 500ms",
                        "new_string": "- NFR-1: 5s",
                    },
                    {
                        "old_string": "- AC-1 -> test_renders_widget",
                        "new_string": "- AC-1 -> test_renders_widget\n- AC-9 -> test_nine",
                    },
                ]
            },
            "MultiEdit intent edit + mapping append",
        )
    print("  intent regions (UC/NFR/seam/gutting/mixed MultiEdit) deny: PASS")


def check_section_addition_wholesale():
    with tempfile.TemporaryDirectory() as root:
        path = _blueprint(root, with_mapping=False)
        # Adding header + bullets with NO prose passes: stripped remainder equals
        # the original text (no section), pairs grow, header count grows.
        _expect_allow(
            path,
            "Edit",
            {
                "old_string": "- NFR-1: response under 500ms",
                "new_string": (
                    "- NFR-1: response under 500ms\n\n"
                    "## Acceptance-Criteria -> Test Mapping\n\n"
                    "- AC-1 -> test_renders_widget"
                ),
            },
            "add bare mapping section",
        )
        # Adding the section WITH prose denies (prose is not strippable).
        path2 = _blueprint(root, "task-v2", with_mapping=False)
        _expect_deny(
            path2,
            "Edit",
            {
                "old_string": "- NFR-1: response under 500ms",
                "new_string": (
                    "- NFR-1: response under 500ms\n\n"
                    "## Acceptance-Criteria -> Test Mapping\n\n"
                    "Declared at RED phase.\n\n"
                    "- AC-1 -> test_renders_widget"
                ),
            },
            "add mapping section with prose",
        )
    print("  bare-section add allows, prose-carrying add denies: PASS")


def check_regressions_no_carveout():
    with tempfile.TemporaryDirectory() as root:
        # Revising status: edits allow (pre-existing behavior).
        path = _blueprint(root, status="revising")
        _expect_allow(
            path,
            "Edit",
            {
                "old_string": "- UC-1: must implement the widget",
                "new_string": "- UC-1: changed",
            },
            "revising blueprint edit",
        )
        # Plan-queue: NO carve-out — a mapping-shaped append still denies.
        queue = os.path.join(root, "docs", "plan-queues", "plan.queue.md")
        os.makedirs(os.path.dirname(queue), exist_ok=True)
        with open(queue, "w", encoding="utf-8") as fh:
            fh.write("---\nstatus: frozen\n---\n\n## Plan\n\n- I0: do it\n")
        _expect_deny(
            queue,
            "Edit",
            {
                "old_string": "- I0: do it",
                "new_string": "- I0: do it\n- AC-1 -> test_x",
            },
            "frozen plan-queue mapping-shaped append",
        )
        # Non-anchor file: silent allow.
        plain = os.path.join(root, "plain.md")
        with open(plain, "w", encoding="utf-8") as fh:
            fh.write("hello\n")
        _expect_allow(
            plain,
            "Edit",
            {"old_string": "hello", "new_string": "world"},
            "non-anchor file edit",
        )
        # Malformed edit (target missing): conservative deny on a frozen blueprint.
        path3 = _blueprint(root, "task-v3")
        _expect_deny(
            path3,
            "Edit",
            {"old_string": "- AC-404 -> nonexistent", "new_string": "- AC-404 -> x"},
            "edit with missing target on frozen blueprint",
        )
    print("  regressions (revising/plan-queue/non-anchor/malformed): PASS")


def main():
    print("blueprint_guard carve-out (ADR #58):")
    check_carveout_append_allow()
    check_carveout_weakening_deny()
    check_intent_still_frozen()
    check_section_addition_wholesale()
    check_regressions_no_carveout()
    print("blueprint_guard carve-out: ALL CHECKS PASS")


if __name__ == "__main__":
    main()
