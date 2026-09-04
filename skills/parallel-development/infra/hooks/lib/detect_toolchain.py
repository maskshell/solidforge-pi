#!/usr/bin/env python3
"""Shared toolchain classification for parallel-development hooks.

Pure stdlib. Imported by fast_gate.py and counters.py to classify a single
edited file by extension into a platform bucket (python / swift / web /
rust / java / go), and to locate the project root / state directory regardless of CWD.

Run from inside the hooks dir; callers add this file's parent to sys.path.
"""

import json
import os
import sys

PY_EXTS = {".py"}
SWIFT_EXTS = {".swift"}
WEB_EXTS = {".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs", ".vue", ".svelte"}
RUST_EXTS = {".rs"}
JAVA_EXTS = {".java"}
GO_EXTS = {".go"}


def classify(file_path):
    """Return 'python' | 'swift' | 'web' | 'rust' | 'java' | 'go' | None for a file path by extension."""
    if not file_path:
        return None
    _, ext = os.path.splitext(file_path)
    ext = ext.lower()
    if ext in PY_EXTS:
        return "python"
    if ext in SWIFT_EXTS:
        return "swift"
    if ext in RUST_EXTS:
        return "rust"
    if ext in JAVA_EXTS:
        return "java"
    if ext in GO_EXTS:
        return "go"
    if ext in WEB_EXTS:
        return "web"
    return None


def project_root():
    """Project root: CLAUDE_PROJECT_DIR env (set in hook context) else CWD."""
    return os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd()


def state_dir():
    return os.path.join(project_root(), ".claude", "parallel-dev")


def state_file():
    return os.path.join(state_dir(), "loop-state.json")


def relpath(file_path):
    """Project-relative path for fingerprint stability across runs."""
    try:
        return os.path.relpath(file_path, project_root())
    except ValueError:
        return file_path


def which_any(*candidates):
    """Return the first candidate command found on PATH, else None."""
    for c in candidates:
        if _shutil_which(c):
            return c
    return None


def resolve_tool(name, root=None):
    """Return an argv prefix to run a tool: [<resolved-path>] or None.

    PATH only, by default (pi port, 2026-09-03 security divergence from CC):
    the project-venv fallback executed whatever binary a repo had committed
    under .venv/venv/env — a hostile repo could plant an executable and have
    the gate run it with the user's full privileges, with no prior code exec
    (the fallback armed exactly in the state where the tool is absent from
    PATH). Opt back in explicitly per-project when you actually rely on
    project-local tooling and trust the repo:

      SF_PROJECT_VENV_TOOLS=1  -> .venv/venv/env python bins (0.2.4)
      SF_PROJECT_NODE_BIN=1    -> node_modules/.bin (0.2.7)

    The node branch carries a containment hard stop: a .bin entry whose
    realpath ESCAPES node_modules/ (symlink to code outside the declared
    trust boundary) is refused even under the opt-in. PATH always wins.
    `root` (optional, for callers that know the target project — arm.py's
    positional path) defaults to project_root(). POSIX layout only
    (bin/, .bin/ — Windows Scripts//.cmd shims are out of scope, as in 0.2.4).
    """
    p = _shutil_which(name)
    if p:
        return [p]
    root = root or project_root()
    if os.environ.get("SF_PROJECT_NODE_BIN") == "1":
        cand = os.path.join(root, "node_modules", ".bin", name)
        if os.path.exists(cand):
            node_modules = os.path.realpath(os.path.join(root, "node_modules"))
            real = os.path.realpath(cand)
            if real == node_modules or real.startswith(node_modules + os.sep):
                return [cand]
            # escaping symlink — outside the declared trust boundary; fall
            # through to None (refuse) even though the opt-in is set
    if os.environ.get("SF_PROJECT_VENV_TOOLS") != "1":
        return None
    for venv in (".venv", "venv", "env"):
        cand = os.path.join(root, venv, "bin", name)
        if os.path.exists(cand):
            return [cand]
    return None


def _shutil_which(cmd):
    # Inlined to keep import surface minimal / predictable.
    from shutil import which

    return which(cmd)


# --- shared hook I/O helpers -------------------------------------------------


def read_payload():
    """Read the Claude Code hook JSON payload from stdin. Returns {} on failure."""
    try:
        raw = sys.stdin.read()
    except Exception:
        return {}
    if not raw or not raw.strip():
        return {}
    try:
        return json.loads(raw)
    except Exception:
        return {}


def emit_block(reason):
    """PostToolUse feedback: structured decision:block, conversation continues.
    The edit already happened; this feeds the failure back so Claude self-corrects
    next turn and the orchestrator treats it as 'inner red, short-circuit'."""
    print(json.dumps({"decision": "block", "reason": reason}))
    sys.exit(0)


def deny_block(reason):
    """PreToolUse: true pre-call deny. The tool call does not execute."""
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


def loop_state_path():
    """Locate loop_state.py: dev/package location only (sibling scripts/ dir).

    The old fallback executed loop_state.py from the PROJECT's
    .claude/parallel-dev/scripts/ — executing project-committed code with user
    privileges, dormant only because the package layout happened to satisfy the
    primary path. Fail closed (None) instead: accounting is best-effort, code
    execution from the project dir is not an acceptable fallback.
    """
    here = os.path.dirname(os.path.abspath(__file__))  # .../hooks/lib
    dev = os.path.normpath(os.path.join(here, "..", "..", "scripts", "loop_state.py"))
    if os.path.exists(dev):
        return dev
    return None
