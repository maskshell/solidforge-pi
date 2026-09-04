#!/usr/bin/env python3
"""pi_loader_smoke.py — pi real-loader smoke gate (BLOCKER for releases).

Asserts the PACKAGE-FORM loadability of this repo with pi's OWN resource
loaders — the class of defect per-skill structural gates cannot see. Born from
a live incident (2026-08-29): the primary-source-verification and
prior-art-search SKILL.md frontmatter descriptions contained ': ' inside plain
YAML scalars — CC's lenient parser accepted them, pi's strict parser SILENTLY
DROPPED both skills (3/5 loaded, "Nested mappings are not allowed"
diagnostics). Found only by exercising the real install path (`pi -e git:...`).

Checks:
  1. skills — pi's loadSkillsFromDir over <repo>/skills: the loaded name set
     equals the expected 5 EXACTLY, and diagnostics == 0 (a warning diagnostic
     is a silent drop in the making — fail it now, not in a user's install).
  2. prompts — prompts/arm-tools.md exists (plain filename; pi composes the
     invocation /solidforge:arm-tools from pi.namespace on namespace-capable
     builds — the literal-colon filename was retired 2026-08-29).
  3. manifest — package.json parses; every pi.extensions / pi.skills /
     pi.prompts path exists on disk.
  4. prompts/arm-tools.md references $ARGUMENTS (prompt-arguments-wired) —
     a template that never wires the invocation arguments silently drops
     every user flag (2026-09-04 live incident).
  5. agents — every agents/*.agent.md frontmatter name is BARE lowercase-hyphen
     and pi.namespace is valid (sf-subagents prefixes the namespace at load
     time per the pi packages spec); a hardcoded "solidforge:" prefix in a
     name is the double-source-of-truth regression.
  6. extensions — bidirectional manifest consistency: every pi.extensions
     entry exists (direction A, manifest-paths-exist) AND every discoverable
     unit under extensions/ (direct *.ts/*.js, or a dir with index.ts /
     index.js / pi-package.json) is listed or explicitly excluded (direction
     B). pi enumerates manifest entries only — an unlisted extension dir is
     structurally invisible (silent no-load, invisible even to settings
     force-includes: the filter universe is manifest-derived).

pi resolution: $PI_LOADER_ROOT override, else walk up from the realpath of
$(command -v pi) to the @earendil-works/pi-coding-agent package root, else
common global locations. Requires `node` (pi ships node-runnable dist).
Graceful skip (exit 0, SKIP note) when pi or node is absent — a dev tool, not
an infra runtime (the lint_self precedent); release CI MUST run it for real.

Usage:
    python3 tools/pi_loader_smoke.py
"""

import fnmatch
import json
import os
import re
import shutil
import subprocess
import sys

GATE = "pi-loader-smoke"
HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)

EXPECTED_SKILLS = {
    "blueprint-crafting",
    "cross-source-review",
    "parallel-development",
    "primary-source-verification",
    "prior-art-search",
}
EXPECTED_PROMPT = os.path.join("prompts", "arm-tools.md")
PI_PKG_NAME = "@earendil-works/pi-coding-agent"

# The node harness: loads skills with pi's real loader, prints one JSON line.
# Kept as a single -e script (no temp files, no repo-state assumptions).
_NODE_HARNESS = """
import { loadSkillsFromDir } from %r;
const r = loadSkillsFromDir({ dir: %r, source: "path" });
console.log(JSON.stringify({
  names: r.skills.map((s) => s.name),
  diagnostics: r.diagnostics.map((d) => ({ type: d.type, message: String(d.message).slice(0, 200), path: d.path })),
}));
"""


def _finding(detail, suggestion):
    return {
        "severity": "blocker",
        "rule": "pi-loader-smoke",
        "file": "package.json",
        "line": 0,
        "detail": detail,
        "suggestion": suggestion,
    }


def _check(name, ok, detail, suggestion, findings, coverage):
    coverage.append(f"{name}: {'PASS' if ok else 'FAIL'}")
    if not ok:
        findings.append(_finding(f"{name}: {detail}", suggestion))


def _has_pi_manifest(pkg_path):
    """True when package.json carries a `pi` object (an extension entry point)."""
    try:
        with open(pkg_path, encoding="utf-8") as fh:
            return isinstance(json.load(fh).get("pi"), dict)
    except (OSError, json.JSONDecodeError, AttributeError):
        return False


def resolve_pi_root():
    """Locate the installed @earendil-works/pi-coding-agent package root."""
    env_root = os.environ.get("PI_LOADER_ROOT")
    if env_root and os.path.isfile(os.path.join(env_root, "dist", "core", "skills.js")):
        return env_root

    candidates = []
    pi_bin = shutil.which("pi")
    if pi_bin:
        # realpath (homebrew bin symlinks into the package), then walk up to
        # the package root carrying package.json with PI_PKG_NAME.
        p = os.path.realpath(pi_bin)
        for _ in range(12):
            p = os.path.dirname(p)
            if os.path.isfile(os.path.join(p, "package.json")):
                try:
                    with open(os.path.join(p, "package.json"), encoding="utf-8") as fh:
                        if json.load(fh).get("name") == PI_PKG_NAME:
                            candidates.append(p)
                            break
                except (OSError, json.JSONDecodeError):
                    continue
    candidates += [
        "/opt/homebrew/lib/node_modules/@earendil-works/pi-coding-agent",
        "/usr/local/lib/node_modules/@earendil-works/pi-coding-agent",
        os.path.expanduser(
            "~/.npm-global/lib/node_modules/@earendil-works/pi-coding-agent"
        ),
    ]
    for c in candidates:
        if os.path.isfile(os.path.join(c, "dist", "core", "skills.js")):
            return c
    return None


def main():
    coverage = [
        (
            "pi-loader-smoke (release BLOCKER; dev-skip when pi/node absent): the "
            "package loads under pi's REAL resource loaders — the harness-gap "
            "incident class (frontmatter that one harness parses and another "
            "silently drops)."
        )
    ]
    findings = []

    pi_root = resolve_pi_root()
    node_bin = shutil.which("node")
    if not pi_root or not node_bin:
        missing = "pi package root" if not pi_root else "node"
        print(
            json.dumps(
                {
                    "gate": GATE,
                    "passed": True,
                    "skipped": True,
                    "coverage": coverage
                    + [
                        f"SKIP: {missing} not found — dev machine without pi; release CI must run this for real"
                    ],
                    "findings": [],
                },
                indent=2,
                ensure_ascii=False,
            )
        )
        return 0

    loader = os.path.join(pi_root, "dist", "core", "skills.js")
    proc = subprocess.run(
        [
            node_bin,
            "--input-type=module",
            "-e",
            _NODE_HARNESS % (loader, os.path.join(REPO, "skills")),
        ],
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    loaded = None
    if proc.returncode == 0:
        m = re.search(r"^\{.*\}$", proc.stdout, re.MULTILINE | re.DOTALL)
        if m:
            try:
                loaded = json.loads(m.group(0))
            except json.JSONDecodeError:
                loaded = None
    _check(
        "pi-loader-runs",
        loaded is not None,
        f"node harness rc={proc.returncode} stderr={proc.stderr[:200]!r}",
        "pi's dist/core/skills.js must be importable by node — check the pi "
        "install (or set PI_LOADER_ROOT to the package root)",
        findings,
        coverage,
    )

    if loaded is not None:
        names = set(loaded["names"])
        _check(
            "skills-exact-set",
            names == EXPECTED_SKILLS,
            f"loaded={sorted(names)} expected={sorted(EXPECTED_SKILLS)}",
            "every skill must load under pi's strict YAML parser AND no extra "
            "skill may appear; a skill dropped by the loader ships as a "
            "silent no-op to users",
            findings,
            coverage,
        )
        diags = loaded.get("diagnostics", [])
        _check(
            "skills-zero-diagnostics",
            len(diags) == 0,
            f"diagnostics={[d.get('message', '?') for d in diags]}",
            "any loader diagnostic (e.g. a YAML frontmatter warning) is a "
            "pending silent drop — fix the frontmatter (folded block scalar "
            "`>-` for descriptions containing ': ' or quotes), not the gate",
            findings,
            coverage,
        )

    _check(
        "prompt-namespace-file",
        os.path.isfile(os.path.join(REPO, EXPECTED_PROMPT)),
        f"missing {EXPECTED_PROMPT}",
        "the prompt is namespace-composed (/solidforge:arm-tools) on "
        "pi.namespace-capable builds (pi-manifest.js) — the literal-colon "
        "filename retired with the 2026-08-29 re-adoption; the package now "
        "requires a namespace-capable pi",
        findings,
        coverage,
    )

    # arm-tools must WIRE the invocation arguments into the prompt body — a
    # template that never references $ARGUMENTS silently drops every flag the
    # user typed (2026-09-04 incident: `--with-tools --scaffold-configs`
    # vanished; the model armed without tools). Verified against the fork's
    # substituteArgs renderer: multi-arg preservation + clean no-arg fallback.
    try:
        with open(os.path.join(REPO, EXPECTED_PROMPT), encoding="utf-8") as fh:
            prompt_body = fh.read()
    except OSError:
        prompt_body = ""
    _check(
        "prompt-arguments-wired",
        "$ARGUMENTS" in prompt_body or "${ARGUMENTS" in prompt_body,
        f"{EXPECTED_PROMPT} never references $ARGUMENTS — invocation flags "
        "are silently dropped",
        "reference the invocation arguments (e.g. `${ARGUMENTS:-<none "
        "passed>}`) near the top so the model parses the user's actual flags; "
        "pi substitutes them at render time",
        findings,
        coverage,
    )

    try:
        with open(os.path.join(REPO, "package.json"), encoding="utf-8") as fh:
            manifest = json.load(fh)
        pi_manifest = manifest.get("pi") or {}
    except (OSError, json.JSONDecodeError) as exc:
        pi_manifest = None
        _check(
            "manifest-parses",
            False,
            str(exc),
            "package.json must be valid JSON",
            findings,
            coverage,
        )
    if pi_manifest is not None:
        missing_paths = []
        for key in ("extensions", "skills", "prompts"):
            for rel in pi_manifest.get(key, []) or []:
                if rel.startswith(("!", "+", "-")):
                    continue  # override patterns (!exclude / +include / -exclude)
                if not os.path.exists(os.path.join(REPO, rel)):
                    missing_paths.append(f"{key}: {rel}")
        _check(
            "manifest-paths-exist",
            not missing_paths,
            f"missing={missing_paths}",
            "every pi.* manifest path must resolve — a dangling entry is an "
            "install-time load error",
            findings,
            coverage,
        )

    # agents — bare frontmatter names; sf-subagents applies pi.namespace at
    # load time (pi packages spec: single source of truth). A hardcoded
    # "solidforge:" prefix in a name is the double-truth regression (runtime
    # agent names would silently drift on a namespace change).
    ns = pi_manifest.get("namespace") if pi_manifest is not None else None
    ns_ok = isinstance(ns, str) and bool(
        re.fullmatch(r"[a-z0-9](?:[a-z0-9-]{0,62}[a-z0-9])?", ns)
    )
    agents_dir = os.path.join(REPO, "agents")
    bad_agents = []
    agent_count = 0
    if os.path.isdir(agents_dir):
        for fn in sorted(os.listdir(agents_dir)):
            if not fn.endswith(".agent.md"):
                continue
            agent_count += 1
            try:
                with open(os.path.join(agents_dir, fn), encoding="utf-8") as fh:
                    head = fh.read(4096)
            except OSError:
                bad_agents.append(f"{fn}: unreadable")
                continue
            m = re.search(r'^name:\s*"?(.+?)"?\s*$', head, re.MULTILINE)
            if not m:
                bad_agents.append(f"{fn}: no name: field in frontmatter")
            elif ":" in m.group(1) or not re.fullmatch(
                r"[a-z0-9][a-z0-9-]*", m.group(1)
            ):
                bad_agents.append(
                    f'{fn}: name="{m.group(1)}" must be bare lowercase-hyphen'
                )
    _check(
        "agents-bare-names",
        ns_ok and agent_count > 0 and not bad_agents,
        f"ns={ns!r} agents={agent_count} bad={bad_agents}",
        "agents/*.agent.md frontmatter names must be BARE (lowercase-hyphen); "
        "sf-subagents composes <pi.namespace>:<name> at load — a hardcoded "
        "prefix duplicates the namespace truth and drifts on rename",
        findings,
        coverage,
    )

    # extensions — direction B of manifest consistency (direction A — entry
    # exists — is manifest-paths-exist above): every discoverable unit under
    # extensions/ must be registered in pi.extensions or explicitly excluded.
    # pi expands manifest entries only for packages, so an unregistered
    # extension dir is structurally invisible: silent no-load AND invisible
    # even to a user's `+path` force-include (the settings filter universe is
    # derived from manifest entries — verified against pi 0.84.x
    # package-manager.js collectManifestFiles/collectFilesFromManifestEntries).
    def _norm_entry(entry):
        """Strip ./ and any leading override marker (!, +, -) for matching."""
        entry = entry.removeprefix("./")
        for marker in ("!", "+", "-"):
            if entry.startswith(marker):
                return entry.removeprefix(marker)
        return entry

    ext_entries = (pi_manifest or {}).get("extensions") or []
    listed = [_norm_entry(e) for e in ext_entries if not e.startswith(("!", "-"))]
    excluded = [_norm_entry(e) for e in ext_entries if e.startswith(("!", "-"))]

    def _registered(posix_rel):
        if any(fnmatch.fnmatch(posix_rel, pat) for pat in excluded if pat):
            return True  # deliberately excluded
        return any(
            posix_rel == pat or fnmatch.fnmatch(posix_rel, pat) for pat in listed
        )

    unregistered = []
    ext_dir = os.path.join(REPO, "extensions")
    if os.path.isdir(ext_dir):
        for name in sorted(os.listdir(ext_dir)):
            if name.startswith(".") or name == "node_modules":
                continue
            full = os.path.join(ext_dir, name)
            discoverable = (os.path.isfile(full) and name.endswith((".ts", ".js"))) or (
                os.path.isdir(full)
                and (
                    os.path.isfile(os.path.join(full, "index.ts"))
                    or os.path.isfile(os.path.join(full, "index.js"))
                    or _has_pi_manifest(os.path.join(full, "package.json"))
                )
            )
            if discoverable and not _registered(f"extensions/{name}"):
                unregistered.append(f"extensions/{name}")
    _check(
        "extensions-registered",
        not unregistered,
        f"unregistered={unregistered}",
        "every discoverable unit under extensions/ must be listed in "
        "pi.extensions (or explicitly excluded with '!'): pi expands manifest "
        "entries only — an unlisted extension silently no-loads and is "
        "invisible even to settings force-includes",
        findings,
        coverage,
    )

    passed = not any(f.get("severity") == "blocker" for f in findings)
    print(
        json.dumps(
            {
                "gate": GATE,
                "passed": passed,
                "coverage": coverage,
                "findings": findings,
            },
            indent=2,
            ensure_ascii=False,
        )
    )
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
