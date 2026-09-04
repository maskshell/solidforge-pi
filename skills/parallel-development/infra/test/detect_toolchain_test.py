#!/usr/bin/env python3
"""detect_toolchain_test.py — resolve_tool trust-boundary gates (BLOCKER; rule 4).

Covers the project-local tool resolution contract on the pi substrate:

  1. PATH-only by default — a repo-committed node_modules/.bin/<tool> (or
     .venv/bin/<tool>) is NEVER executed without an explicit opt-in (the
     2026-09-04 venv-exec blocker class; SF_PROJECT_VENV_TOOLS landed in
     0.2.4, SF_PROJECT_NODE_BIN in 0.2.7).
  2. SF_PROJECT_NODE_BIN=1 resolves node_modules/.bin/<tool> — in-tree
     symlinks (the dominant npm shape) resolve; a .bin entry whose realpath
     ESCAPES node_modules/ is refused EVEN under the opt-in.
  3. PATH always wins over project-local candidates (both opt-ins).
  4. SF_PROJECT_VENV_TOOLS regression (0.2.4 behavior unchanged).
  5. arm.py tool_present follows the same trust model (opt-in-gated,
     root-threaded — no silent-green, no cwd≠target drift).

Run: python3 infra/test/detect_toolchain_test.py   (from the skill dir)
"""

import os
import sys
import tempfile
from pathlib import Path

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.normpath(os.path.join(HERE, "..", "hooks", "lib")))

import detect_toolchain as dt  # noqa: E402

RESULTS = []


def check(name, ok, detail=""):
    RESULTS.append(ok)
    suffix = f" — {detail}" if detail and not ok else ""
    print(f"{'PASS' if ok else 'FAIL'}  {name}{suffix}")


class Env:
    """Scoped env-var + project-root sandbox."""

    def __init__(self, root):
        self.root = root
        self._saved = {}

    def __enter__(self):
        for var in (
            "SF_PROJECT_VENV_TOOLS",
            "SF_PROJECT_NODE_BIN",
            "CLAUDE_PROJECT_DIR",
        ):
            self._saved[var] = os.environ.pop(var, None)
        os.environ["CLAUDE_PROJECT_DIR"] = self.root
        return self

    def __exit__(self, *exc):
        for var, val in self._saved.items():
            if val is None:
                os.environ.pop(var, None)
            else:
                os.environ[var] = val


def plant_node_bin(root, name, escape_to=None):
    bindir = Path(root, "node_modules", ".bin")
    bindir.mkdir(parents=True, exist_ok=True)
    target = bindir / name
    if escape_to is not None:
        target.symlink_to(escape_to)
    else:
        target.write_text("#!/bin/sh\nexit 0\n")
        target.chmod(0o755)
    return str(target)


def arm_tool_present_truth():
    """arm.py tool_present must follow resolve_tool's opt-in trust model —
    the pre-0.2.7 bug reported venv tools 'present' unconditionally (a
    silent-green: gates would refuse to run them)."""
    sys.path.insert(0, os.path.normpath(os.path.join(HERE, "..", "install")))
    import arm  # noqa: E402

    with tempfile.TemporaryDirectory() as root:
        venvbin = Path(root, ".venv", "bin")
        venvbin.mkdir(parents=True, exist_ok=True)
        vtool = venvbin / "sf-arm-absent-tool-xyz"
        vtool.write_text("#!/bin/sh\nexit 0\n")
        vtool.chmod(0o755)
        with Env(root):
            check(
                "arm.tool_present: venv tool absent without opt-in",
                not arm.tool_present(root, "sf-arm-absent-tool-xyz"),
            )
            os.environ["SF_PROJECT_VENV_TOOLS"] = "1"
            check(
                "arm.tool_present: venv tool present under opt-in",
                arm.tool_present(root, "sf-arm-absent-tool-xyz"),
            )
            # I1 regression: the positional path (cwd != target) must still
            # resolve against the TARGET project, not cwd/CLAUDE_PROJECT_DIR
            os.environ["CLAUDE_PROJECT_DIR"] = tempfile.gettempdir()
            check(
                "arm.tool_present: root threading (cwd != target)",
                arm.tool_present(root, "sf-arm-absent-tool-xyz"),
            )
    return all(RESULTS[-3:])


def main():
    absent = "sf-dt-absent-tool-xyz"
    with tempfile.TemporaryDirectory() as root:
        node_bin = plant_node_bin(root, absent)

        with Env(root):
            # 1. default PATH-only: repo-committed node bin ignored
            check(
                "default: node_modules/.bin ignored (PATH-only)",
                dt.resolve_tool(absent) is None,
                f"resolved {node_bin}",
            )

            # 2a. opt-in resolves the planted bin
            os.environ["SF_PROJECT_NODE_BIN"] = "1"
            got = dt.resolve_tool(absent)
            check(
                "SF_PROJECT_NODE_BIN=1 resolves project node bin",
                got is not None and os.path.exists(got[0]),
                f"got {got}",
            )

            # 2b. in-tree symlink (the DOMINANT npm shape: .bin/<name> ->
            # ../<pkg>/bin/...) must RESOLVE — a containment regression to
            # real==cand would pass every other case while breaking every
            # actual npm repo under the opt-in
            pkg_bin = Path(root, "node_modules", "some-pkg", "bin")
            pkg_bin.mkdir(parents=True, exist_ok=True)
            real_entry = pkg_bin / "cli.js"
            real_entry.write_text("#!/bin/sh\nexit 0\n")
            real_entry.chmod(0o755)
            plant_node_bin(root, "sf-dt-intree-tool", escape_to=str(real_entry))
            got = dt.resolve_tool("sf-dt-intree-tool")
            check(
                "in-tree .bin symlink (npm shape) resolves under opt-in",
                got is not None
                and got[0].endswith("node_modules/.bin/sf-dt-intree-tool"),
                f"got {got}",
            )

            # 2c. containment: symlink escaping node_modules refused even with opt-in
            with tempfile.TemporaryDirectory() as outside:
                payload = Path(outside, "payload.sh")
                payload.write_text("#!/bin/sh\nexit 0\n")
                payload.chmod(0o755)
                plant_node_bin(root, "sf-dt-escaping-tool", escape_to=str(payload))
                check(
                    "escaping symlink refused even under the opt-in",
                    dt.resolve_tool("sf-dt-escaping-tool") is None,
                )

            # 3. PATH wins over project bin (same tool name)
            planted_builtin = plant_node_bin(root, "python3")
            got = dt.resolve_tool("python3")
            check(
                "PATH wins over project-local bin",
                got is not None
                and os.path.realpath(got[0]) != os.path.realpath(planted_builtin),
                f"got {got}",
            )

            # 4. venv opt-in regression (0.2.4 behavior)
            os.environ.pop("SF_PROJECT_NODE_BIN", None)
            os.environ["SF_PROJECT_VENV_TOOLS"] = "1"
            venvbin = Path(root, ".venv", "bin")
            venvbin.mkdir(parents=True, exist_ok=True)
            vtool = venvbin / absent
            vtool.write_text("#!/bin/sh\nexit 0\n")
            vtool.chmod(0o755)
            got = dt.resolve_tool(absent)
            check(
                "SF_PROJECT_VENV_TOOLS regression: venv bin resolves",
                got is not None and got[0].endswith(f".venv/bin/{absent}"),
                f"got {got}",
            )
            os.environ.pop("SF_PROJECT_VENV_TOOLS", None)
            check(
                "venv bin ignored again without its opt-in",
                dt.resolve_tool(absent) is None,
            )

    print()
    if all(RESULTS):
        arm_tool_present_truth()
        if all(RESULTS):
            print(f"detect_toolchain opt-in gates: ALL {len(RESULTS)} PASS")
            return 0
    print(
        f"detect_toolchain opt-in gates: {RESULTS.count(False)} FAILED / {len(RESULTS)}"
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())
