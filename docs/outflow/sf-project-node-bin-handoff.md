# OUTFLOW handoff — SF_PROJECT_NODE_BIN + argument-wired arm-tools (pi 0.2.7 → CC)

> Direction: solidforge-pi → solidforge (CC reference). pi-side implementation is
> FINAL and shipped; this document is the adoption handoff. Per the 2026-09-04
> session decision: the pi repo manages its own end only — CC adoption is the CC
> maintainers' call, at their cadence. Ledger row: `docs/upstream-watch.md`
> (inflow table, outflow rows).

## 1. Problem this solves (observed live on pi, likely latent on CC)

The 2026-09-04 security fix (PATH-only `resolve_tool`, backported to CC as
solidforge `489b217`) closed the execute-repo-committed-binaries class — and in
doing so broke the `arm.py --with-tools` contract on the pi substrate: tools
installed into project-local `node_modules/.bin` (or `.venv/bin`) became
INVISIBLE to the gates, because the only project-local resolution path was the
removed fallback. Observed live: `npm add -D eslint dependency-cruiser vitest`
succeeded, arm.py still reported `absent (gate degrades)`.

The trust tension is real and irreducible: project-local tooling IS
repo-committable code. The resolution on pi is **explicit per-project opt-in**
(consistent with `SF_PROJECT_VENV_TOOLS`, 0.2.4):

## 2. What landed on pi (commit trail, 0.2.7)

1. `detect_toolchain.resolve_tool`: `SF_PROJECT_NODE_BIN=1` → resolve
   `node_modules/.bin/<name>`, **with a containment hard stop**: the entry's
   `realpath` must stay under the project's `node_modules/` — a `.bin` symlink
   escaping that boundary (to code outside the declared trust zone) is refused
   even under the opt-in. PATH always wins.
2. `arm.py tool_present`: replaced its own unconditional venv scan with a call
   to `resolve_tool` (single source of truth). Bug it fixed: the status report
   claimed tools "present" that the 0.2.4+ gates would refuse to execute — a
   silent-green of its own.
3. `prompts/arm-tools.md`: the template never referenced `$ARGUMENTS`, so pi
   substituted the invocation flags NOWHERE — `--with-tools --scaffold-configs`
   vanished silently (live incident). Fixed by wiring
   `` `${ARGUMENTS:-<none passed>}` `` near the top + an instruction to parse
   flags from that line. Verified against pi's `substituteArgs` renderer
   (multi-arg preserved; clean fallback when empty). A smoke-gate assertion
   (`prompt-arguments-wired`) guards the wiring against regression.
4. Tests: `infra/test/detect_toolchain_test.py` — 6 cases: PATH-only default,
   node opt-in, escaping-symlink refusal, PATH-wins, venv opt-in regression ×2.

## 3. CC-side adoption sketch (apply at your cadence)

- `skills/parallel-development/infra/hooks/lib/detect_toolchain.py`:
  add the node branch to `resolve_tool` mirroring the above (opt-in env +
  realpath containment). The pi file (post-0.2.7) can be diffed directly.
- `infra/install/arm.py`: route `tool_present` through `resolve_tool`.
- Arguments: CC slash commands support `$ARGUMENTS` natively — audit
  `commands/arm-tools.md` for the same silent-drop shape (a command body that
  never references `$ARGUMENTS` discards the user's flags; CC's native
  substitution may make the fix a one-liner there).
- Port the test file; it is substrate-neutral.

## 4. Trust model (for the CC decision)

Opt-in envs are a per-project, per-user trust statement ("I run gates in this
repo and accept that its devDependencies define gate tooling"). Default stays
PATH-only everywhere. Containment (node branch) narrows the blast radius to
`node_modules/` itself; the venv branch has no equivalent check today (venv
entries are conventionally real files, not symlinks — noted asymmetry, kept
deliberately to match 0.2.4 semantics). Residual TOCTOU: exists→realpath→spawn leaves a swap window — accepted,
informational (threat model is repo-committed content, not a concurrent local
process; same residual the 0.2.4 fix accepted). POSIX layout only: Windows
Scripts//.cmd shims are out of scope, as in 0.2.4 — the test file is
substrate-neutral but not Windows-tested.
