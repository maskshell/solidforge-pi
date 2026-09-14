#!/usr/bin/env python3
"""detect_toolchain_test.py — resolve_tool trust-boundary gates (BLOCKER; rule 4).

Covers the project-local tool resolution contract (pi substrate; 2026-09-04
SF_PROJECT_VENV_TOOLS in 0.2.4, SF_PROJECT_NODE_BIN in 0.2.7; 2026-09-07 the
#63-#66 security mirror of CC 8a19c2e collapsed the seven ad-hoc sites — this
suite adopted verbatim from CC's post-adoption version, which had absorbed
our earlier 10-case file; provenance: docs/upstream-watch.md rows #63-#66):

  1. PATH-only by default — a repo-committed node_modules/.bin/<tool> (or
     .venv/bin/<tool>) is NEVER resolved without an explicit opt-in (the
     execute-repo-committed-binaries class; SF_PROJECT_VENV_TOOLS landed in
     0.2.4, SF_PROJECT_NODE_BIN in 0.2.7).
  2. SF_PROJECT_NODE_BIN=1 resolves node_modules/.bin/<tool> — in-tree
     symlinks (the dominant npm shape) resolve; a .bin entry whose realpath
     ESCAPES node_modules/ is refused EVEN under the opt-in.
  3. PATH always wins over project-local candidates (both opt-ins).
  4. SF_PROJECT_VENV_TOOLS regression (0.2.4 behavior unchanged).
  5. arm.py tool_present follows the same trust model (opt-in-gated,
     root-threaded — no silent-green, no cwd≠target drift).
  6. Gate sites: the SEVEN formerly ad-hoc resolution sites (fast_gate eslint;
     arch_contract_web depcruise/eslint/tsc; arch_contract_tests vitest;
     spectral_adapter; arch_contract_python's delegating wrapper) refuse a
     planted project-local binary without the matching opt-in and resolve it
     under one — and the npx --no-install delegation arm is gated behind
     SF_PROJECT_NODE_BIN (a PATH tool is not PATH resolution (upstream-watch #63-#66)).
  7. site-8 family — the consistency-completion legs (tests gate pytest/coverage;
     deps gate pip-audit/govulncheck) refuse without the venv opt-in and resolve
     under it (report/gate agreement for every arm-report tool row).

Coverage note (rule 3): the site probes exercise the post-collapse RESOLVER
functions, not the calling check_* bodies — a future re-inline of local-first
inside a check_ body would pass this suite (outer-ring residual, accepted).

Run: python3 infra/test/detect_toolchain_test.py   (from the skill dir)
"""

import importlib.util
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


class ScrubbedPath:
    """Scoped PATH scrub: replace PATH with `replacement` (a dir, possibly
    holding fake shims) so `which` is deterministic — machine globals can
    otherwise shadow every site probe (PATH-wins is exercised by the main()
    cases instead)."""

    def __init__(self, replacement):
        self.replacement = replacement
        self._saved = None

    def __enter__(self):
        self._saved = os.environ["PATH"]
        os.environ["PATH"] = self.replacement
        return self

    def __exit__(self, *exc):
        os.environ["PATH"] = self._saved


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


def load_script(module_name, filename):
    """Load an infra script as a module by path (the scripts dir is not a
    package; each gate stays a self-contained deployable script — rule 7)."""
    path = os.path.join(HERE, "..", "scripts", filename)
    spec = importlib.util.spec_from_file_location(module_name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def cc_site_probes():
    """Section 6: the seven collapsed sites + the gated npx arm. All probes
    run under a scrubbed PATH (only our fake shims visible) so assertions do
    not depend on the machine's global installs."""
    web = load_script("cc_acw", "arch_contract_web.py")
    tests = load_script("cc_act", "arch_contract_tests.py")
    pygate = load_script("cc_acp", "arch_contract_python.py")
    spectral = load_script("cc_spc", "spectral_adapter.py")

    with tempfile.TemporaryDirectory() as shims, tempfile.TemporaryDirectory() as root:
        shimdir = Path(shims)
        npx = shimdir / "npx"
        npx.write_text("#!/bin/sh\nexit 0\n")
        npx.chmod(0o755)
        # the gates' have() probes via `sh -c` — sh itself must resolve on the
        # scrubbed PATH (the conventional location on macOS/Linux, the suite's
        # supported platforms — the trust model is POSIX-only by scope; on a
        # system without /bin/sh this fails loud, never false-pass)
        os.symlink("/bin/sh", shimdir / "sh")
        for name in ("eslint", "depcruise", "tsc", "vitest", "spectral"):
            plant_node_bin(root, name)
        with Env(root), ScrubbedPath(shims):
            # sites 1-4: fast_gate's exact call + the web gate's resolvers
            check(
                "site1 fast_gate resolution (dt.resolve_tool('eslint')): planted refused",
                dt.resolve_tool("eslint") is None,
            )
            check(
                "site2 depcruise_cmd: planted + npx shim refused (no opt-in)",
                web.depcruise_cmd(root) is None,
            )
            check(
                "site3 web eslint resolver: planted refused",
                web._resolve("eslint", root) is None,
            )
            check(
                "site4 _resolve_tsc: planted refused",
                web._resolve_tsc(root) is None,
            )
            check(
                "site5 _resolve_vitest: planted refused",
                tests._resolve_vitest(root) is None,
            )
            check(
                "site6 resolve_spectral: planted refused (npx never armed)",
                spectral.resolve_spectral(root) is None,
            )
            # site 7 regression probe: the python gate's former PRIVATE
            # unconditional venv resolver must refuse without the venv opt-in
            venvbin = Path(root, ".venv", "bin")
            venvbin.mkdir(parents=True, exist_ok=True)
            vtool = venvbin / "lint-imports"
            vtool.write_text("#!/bin/sh\nexit 0\n")
            vtool.chmod(0o755)
            check(
                "site7 arch_contract_python: venv lint-imports refused (no opt-in)",
                pygate.resolve_tool("lint-imports", root=root) is None,
            )
            os.environ["SF_PROJECT_VENV_TOOLS"] = "1"
            check(
                "site7 arch_contract_python: venv lint-imports resolves under opt-in",
                pygate.resolve_tool("lint-imports", root=root) is not None,
            )
            os.environ.pop("SF_PROJECT_VENV_TOOLS", None)
            # under the node opt-in everything resolves project-locally …
            os.environ["SF_PROJECT_NODE_BIN"] = "1"
            check(
                "site2 depcruise_cmd: planted resolves under opt-in",
                web.depcruise_cmd(root)
                == [os.path.join(root, "node_modules", ".bin", "depcruise")],
            )
            check(
                "site5 _resolve_vitest: planted resolves under opt-in",
                tests._resolve_vitest(root)
                == [os.path.join(root, "node_modules", ".bin", "vitest")],
            )
            # … and the npx arm stays reachable ONLY under the opt-in:
            # remove the planted depcruise so resolution falls through to npx
            os.remove(os.path.join(root, "node_modules", ".bin", "depcruise"))
            os.environ.pop("SF_PROJECT_NODE_BIN", None)
            check(
                "npx arm gated: no delegation without the opt-in (npx shim visible)",
                web.depcruise_cmd(root) is None,
            )
            os.environ["SF_PROJECT_NODE_BIN"] = "1"
            check(
                "npx arm: delegates under the opt-in (ADR #65)",
                web.depcruise_cmd(root) == ["npx", "--no-install", "depcruise"],
            )
            os.environ.pop("SF_PROJECT_NODE_BIN", None)
            # site-8 family: the consistency-completion legs migrated during
            # execution (pytest/coverage in the test gate; pip-audit/govulncheck
            # in the deps gate) — the arm report rows for these resolve via the
            # canonical resolver, so the gates must too (report/gate agreement).
            deps = load_script("cc_acd", "arch_contract_deps.py")
            for tname in ("pytest", "coverage", "pip-audit", "govulncheck"):
                vtool = venvbin / tname
                vtool.write_text("#!/bin/sh\nexit 0\n")
                vtool.chmod(0o755)
            check(
                "site8 pytest leg: venv pytest refused (no opt-in)",
                tests._resolve("pytest", root) is None,
            )
            check(
                "site8 pip-audit leg: venv pip-audit refused (no opt-in)",
                deps._resolve("pip-audit", root) is None,
            )
            check(
                "site8 govulncheck leg: venv copy refused (no opt-in)",
                deps._resolve("govulncheck", root) is None,
            )
            os.environ["SF_PROJECT_VENV_TOOLS"] = "1"
            check(
                "site8: all four legs resolve under the venv opt-in",
                all(
                    x is not None
                    for x in (
                        tests._resolve("pytest", root),
                        tests._resolve("coverage", root),
                        deps._resolve("pip-audit", root),
                        deps._resolve("govulncheck", root),
                    )
                ),
            )
    return all(RESULTS[-16:])


def arm_tool_present_truth():
    """arm.py tool_present must follow resolve_tool's opt-in trust model —
    the pre-adoption bug reported venv tools 'present' unconditionally (a
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

            # 4. venv opt-in regression (489b217 behavior)
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
        cc_sites_ok = cc_site_probes()
        if all(RESULTS) and cc_sites_ok:
            arm_ok = arm_tool_present_truth()
            if all(RESULTS) and arm_ok:
                if len(RESULTS) != 26:  # fail loud on section re-slicing
                    print(
                        f"detect_toolchain opt-in gates: section count drift — "
                        f"{len(RESULTS)} checks (expected 26)"
                    )
                    return 1
                print(f"detect_toolchain opt-in gates: ALL {len(RESULTS)} PASS")
                return 0
    print(
        f"detect_toolchain opt-in gates: {RESULTS.count(False)} FAILED / {len(RESULTS)}"
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())
