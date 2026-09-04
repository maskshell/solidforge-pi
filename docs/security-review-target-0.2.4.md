<!-- markdownlint-disable MD010 --><!-- verbatim diff embeds tab-indented code -->

# Security-review target — sf-hooks pre-lint + hooks lib (0.2.4 surface)

> Prepared for the different-family (hetero) review leg. Same-family coverage: code-reviewer + security-specialist dual round (2026-09-03), findings all fixed — this doc exists so a hetero model can hunt BEYOND that blind spot. Run:
> `HETERO_DOC_PROFILE=deepseek python3 skills/cross-source-review/infra/scripts/hetero_doc_review.py --artifact docs/security-review-target-0.2.4.md` (needs `.env.solidforge` credentials — absent on the authoring machine as of 2026-09-04; the leg is intentionally NOT dry-run theater).

## Scope under review

1. `extensions/sf-hooks/index.ts` — pre-write python lint gate: wouldBeContent (literal splice, caps), resolveRuff (once-cached absolute path), runCmd/runHook (immediate-resolve hard timeouts), preLintPython (mkdtemp probe, mode-copy read-bit guard), ccPayload (CC-shape edit translation).
2. `skills/parallel-development/infra/hooks/lib/detect_toolchain.py` — PATH-only resolve_tool (SF_PROJECT_VENV_TOOLS opt-in), fail-closed loop_state_path.
3. Callers: counters.py, fast_gate.py (None handling).

## Already caught by the same-family round (do not re-litigate; hunt what they missed)

- venv-exec blocker, loop_state project-dir fallback (fixed: PATH-only / fail-closed)
- $-sequence splice divergence (fixed: function-replacement)
- ADR #58 carve-out bridge unreachability (fixed: ccPayload translation)
- mkdtemp, TOCTOU, PATH-strip cache, EPIPE, %20 paths, transient-which caching (fixed)

## Hunt targets

- The carve-out regex-walk edge semantics (blank-adjacency fixpoint, H3 strippability) — upstream-verbatim, flagged by same-family as 'would need the hetero leg'
- Any spawn/env/temp surface the same-family rounds pattern-matched as sound
- Trust-boundary claims that hold only under the authors' shared assumptions

## The code

```text
diff --git a/extensions/sf-hooks/index.ts b/extensions/sf-hooks/index.ts
index 52c9bb0..c80b5ef 100644
--- a/extensions/sf-hooks/index.ts
+++ b/extensions/sf-hooks/index.ts
@@ -29,9 +29,10 @@ import { spawn } from "node:child_process";
 import * as fs from "node:fs";
 import * as os from "node:os";
 import * as path from "node:path";
+import { fileURLToPath } from "node:url";
 import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";
 
-const HERE = path.dirname(new URL(import.meta.url).pathname);
+const HERE = path.dirname(fileURLToPath(import.meta.url)); // decode-safe (raw .pathname breaks on %20 paths)
 const HOOKS_DIR = path.normalize(path.join(HERE, "..", "..", "skills", "parallel-development", "infra", "hooks"));
 
 const PRE_HOOKS = ["blueprint_guard.py", "counters.py"];
@@ -64,20 +65,32 @@ function runHook(
 		});
 		child.stdin.write(JSON.stringify(payload));
 		child.stdin.end();
+		child.stdin.on("error", () => {
+			/* EPIPE when the child exits before reading — not a gate signal */
+		});
 		let stdout = "";
-		let timedOut = false;
+		let settled = false;
+		const settle = (r: HookOutput | null) => {
+			if (settled) return;
+			settled = true;
+			resolve(r);
+		};
 		const timer = setTimeout(() => {
-			timedOut = true;
-			child.kill("SIGKILL");
+			try {
+				child.kill("SIGKILL");
+			} catch {
+				/* already gone */
+			}
+			settle({ stdout, code: null, timedOut: true }); // hard bound — do not wait for close (fd-inheriting grandchildren)
 		}, timeoutMs);
 		child.stdout.on("data", (d) => (stdout += d.toString()));
 		child.on("close", (code) => {
 			clearTimeout(timer);
-			resolve({ stdout, code, timedOut });
+			settle({ stdout, code, timedOut: false });
 		});
 		child.on("error", () => {
 			clearTimeout(timer);
-			resolve(null);
+			settle(null);
 		});
 	});
 }
@@ -105,13 +118,38 @@ function parseDeny(stdout: string): { reason: string } | null {
 	return null;
 }
 
-function ccPayload(toolName: string, input: Record<string, unknown>): Record<string, unknown> {
-	// pi edit/write input {path,...} → CC {tool_name, tool_input:{file_path}}
+export function ccPayload(toolName: string, input: Record<string, unknown>): Record<string, unknown> {
+	// pi edit/write input {path,...} → CC {tool_name, tool_input:{file_path}}.
+	// Edit translation (2026-09-03, I-1): CC hook contract has Edit
+	// {old_string,new_string} and MultiEdit {edits:[{old_string,new_string}]};
+	// emitting pi's raw {edits:[{oldText,newText}]} under tool_name "Edit" left
+	// blueprint_guard's ADR #58 mapping carve-out UNREACHABLE through this
+	// bridge (the carve-out arms read the CC keys — missing keys ⇒ conservative
+	// deny, so the documented append-open path never passed). counters.py and
+	// fast_gate.py read only file_path — inert to the translation.
 	const filePath = (input.path as string) ?? (input.file_path as string) ?? "";
 	const toolInput: Record<string, unknown> = { file_path: filePath };
 	if (input.content !== undefined) toolInput.content = input.content;
-	if (input.edits !== undefined) toolInput.edits = input.edits;
-	return { tool_name: toolName, tool_input: toolInput };
+	let effectiveName = toolName;
+	const edits = input.edits;
+	if (Array.isArray(edits)) {
+		const ccEdits = edits.map((e) =>
+			e && typeof (e as Record<string, unknown>).oldText === "string"
+				? {
+						old_string: (e as Record<string, unknown>).oldText,
+						new_string: (e as Record<string, unknown>).newText,
+				}
+				: e
+		);
+		if (ccEdits.length === 1) {
+			toolInput.old_string = (ccEdits[0] as Record<string, unknown>).old_string;
+			toolInput.new_string = (ccEdits[0] as Record<string, unknown>).new_string;
+		} else {
+			toolInput.edits = ccEdits;
+			if (toolName === "Edit") effectiveName = "MultiEdit";
+		}
+	}
+	return { tool_name: effectiveName, tool_input: toolInput };
 }
 
 const CC_NAMES: Record<string, string> = { edit: "Edit", write: "Write" };
@@ -126,9 +164,14 @@ interface CmdResult {
  * Run a CLI command, capture combined output. null when the binary is absent
  * (ENOENT). The timeout resolves IMMEDIATELY (hard bound) — not waiting for
  * `close`, which can be held hostage by fd-inheriting grandchildren of the
- * killed child.
+ * killed child. Exported for the seam selftest (timeout/ENOENT paths).
  */
-function runCmd(cmd: string, args: string[], cwd: string, timeoutMs: number): Promise<CmdResult | null> {
+export async function runCmd(
+	cmd: string,
+	args: string[],
+	cwd: string,
+	timeoutMs: number,
+): Promise<CmdResult | null> {
 	return new Promise((resolve) => {
 		const child = spawn(cmd, args, { cwd, stdio: ["ignore", "pipe", "pipe"] });
 		let out = "";
@@ -190,22 +233,32 @@ function findRuffConfig(filePath: string): string | null {
 /**
  * The would-be file content after a pi edit/write tool call, or null when it
  * cannot be determined (write without content; edit against a missing file or
- * a stale oldText — the tool itself will error in those cases).
+ * a stale oldText — the tool itself will error in those cases; also pi-side
+ * CRLF/BOM/fuzzy-whitespace tolerance diverges from this exact match — those
+ * paths return null and the post-write gate stays authoritative).
+ * Caps: >200 edits or >5MB content bail to null (unbounded model-fabricated
+ * arrays would otherwise freeze the event loop synchronously).
  */
 function wouldBeContent(input: Record<string, unknown>): string | null {
 	if (typeof input.content === "string") return input.content; // write
 	const edits = input.edits;
-	if (!Array.isArray(edits)) return null;
+	if (!Array.isArray(edits) || edits.length > 200) return null;
 	let content: string;
 	try {
 		content = fs.readFileSync(String(input.path ?? ""), "utf-8");
 	} catch {
 		return null;
 	}
+	if (content.length > 5 * 1024 * 1024) return null;
 	for (const e of edits) {
 		if (!e || typeof e.oldText !== "string" || typeof e.newText !== "string") return null;
 		if (!content.includes(e.oldText)) return null;
-		content = content.replace(e.oldText, e.newText); // first occurrence = the tool's unique-region contract
+		// LITERAL splice via function replacement: String.replace with a string
+		// replacement INTERPRETS $& $` $' $$ — a crafted newText could make the
+		// probe clean while the landed (literal) edit is red. The function form
+		// skips $ interpretation; first occurrence = the tool's unique-region
+		// contract.
+		content = content.replace(e.oldText, () => e.newText);
 	}
 	return content;
 }
@@ -214,6 +267,34 @@ function tail(s: string, n = LINT_OUT_MAX): string {
 	return s.length > n ? `${s.slice(0, n)}…` : s;
 }
 
+/**
+ * Absolute ruff path, resolved ONCE via `which` and cached forever: the two
+ * ruff calls per edit (check + format) then hit the same binary (no TOCTOU),
+ * and no later PATH state can swap it mid-session. Trust boundary: `which`
+ * runs against the pi process's startup PATH — the same trust level as the
+ * python hooks and the post-gate (a binary found there is environment-trusted
+ * by definition). null when ruff is absent (degrade to post-gate).
+ */
+let ruffBinCache: string | null | undefined;
+
+async function resolveRuff(): Promise<string | null> {
+	if (ruffBinCache !== undefined) return ruffBinCache;
+	const out = await runCmd("which", ["ruff"], process.cwd(), 2_000);
+	if (out === null) {
+		// `which` itself absent/failed to spawn — definitive enough for this session
+		ruffBinCache = null;
+		return null;
+	}
+	if (out.timedOut) {
+		// transient: do NOT cache — retry on the next edit (a hung moment must not
+		// degrade the pre-gate for the whole session)
+		return null;
+	}
+	const first = out.ok ? out.out.split("\n").map((l) => l.trim()).find(Boolean) : undefined;
+	ruffBinCache = first || null;
+	return ruffBinCache;
+}
+
 /**
  * Pre-write ruff gate for .py targets: lint/format the WOULD-BE content on a
  * temp copy (mode preserved from the original so EXE001 verdicts match), using
@@ -226,7 +307,12 @@ async function preLintPython(input: Record<string, unknown>, cwd: string): Promi
 	if (!filePath.endsWith(".py")) return null;
 	const content = wouldBeContent(input);
 	if (content === null) return null;
-	const tmp = path.join(os.tmpdir(), `sf-pre-lint-${process.pid}-${Date.now()}.py`);
+	const bin = await resolveRuff();
+	if (bin === null) return null;
+	// Private unpredictable dir per invocation — a predictable top-level
+	// /tmp filename is a symlink/raid surface on shared machines.
+	const dir = fs.mkdtempSync(path.join(os.tmpdir(), "sf-pre-lint-"));
+	const tmp = path.join(dir, "probe.py");
 	try {
 		try {
 			fs.writeFileSync(tmp, content);
@@ -234,18 +320,19 @@ async function preLintPython(input: Record<string, unknown>, cwd: string): Promi
 			return null; // tmpdir unwritable — degrade to post-gate
 		}
 		try {
-			fs.chmodSync(tmp, fs.statSync(filePath).mode & 0o777);
+			const mode = fs.statSync(filePath).mode & 0o777;
+			if (mode & 0o400) fs.chmodSync(tmp, mode); // preserve exec bit (EXE001 parity); skip unreadable modes
 		} catch {
 			/* new file — keep default mode */
 		}
 		const cfg = findRuffConfig(filePath);
 		const common = cfg ? ["--config", cfg] : [];
-		const chk = await runCmd("ruff", [...common, "check", "--no-cache", "--output-format=concise", tmp], cwd, PRE_LINT_TIMEOUT_MS);
+		const chk = await runCmd(bin, [...common, "check", "--no-cache", "--output-format=concise", tmp], cwd, PRE_LINT_TIMEOUT_MS);
 		if (chk === null || chk.timedOut) return null; // absent or hung ruff — degrade to post-gate
 		if (!chk.ok) {
 			return { reason: `pre-write lint: ruff check fails on the proposed edit — fix the edit itself and retry (the file has NOT been modified):\n${tail(chk.out)}` };
 		}
-		const fmt = await runCmd("ruff", [...common, "format", "--check", tmp], cwd, PRE_LINT_TIMEOUT_MS);
+		const fmt = await runCmd(bin, [...common, "format", "--check", tmp], cwd, PRE_LINT_TIMEOUT_MS);
 		if (fmt === null || fmt.timedOut) return null; // absent or hung ruff — degrade to post-gate
 		if (!fmt.ok) {
 			return { reason: `pre-write lint: ruff format would reformat the proposed edit — wrap the lines inside the edit and retry (the file has NOT been modified):\n${tail(fmt.out)}` };
@@ -253,7 +340,7 @@ async function preLintPython(input: Record<string, unknown>, cwd: string): Promi
 		return null;
 	} finally {
 		try {
-			fs.rmSync(tmp, { force: true });
+			fs.rmSync(dir, { recursive: true, force: true });
 		} catch {
 			/* best effort */
 		}
diff --git a/skills/parallel-development/infra/hooks/blueprint_guard.py b/skills/parallel-development/infra/hooks/blueprint_guard.py
index b831422..f1d8d8a 100644
--- a/skills/parallel-development/infra/hooks/blueprint_guard.py
+++ b/skills/parallel-development/infra/hooks/blueprint_guard.py
@@ -11,10 +11,13 @@ Guards FOUR anchor kinds (distinct freeze signals, one deny path):
   - OpenAPI spec (external skill, Depth 2): any `openapi.{json,yaml,yml}` / `swagger.{json,yaml,yml}` (Spectral; see references/external-skills.md, ADR 23).
     Freeze = side-car sentinel `.claude/parallel-dev/openapi.frozen` (the spec is external-authored; frozen at Phase 0 so the implementer codes against a stable contract).
 
-Each is FROZEN after its freeze step and must be read-only for the Coder mid-loop. The only legitimate change path is the Revision Channel.
+Each is FROZEN after its freeze step and must be read-only for the Coder mid-loop. The only legitimate change path is the Revision Channel — with ONE carve-out (ADR #58): a frozen Intent Blueprint's `## Acceptance-Criteria -> Test Mapping` section is APPEND-OPEN. The mapping records RED-phase observations (real test names exist only after RED writes the tests), so a wholesale deny left the mapping section unreachable as documented and the test-name set gate dormant. An Edit/Write/MultiEdit to a frozen blueprint is allowed iff BOTH hold:
+  (1) old and new content are byte-identical after stripping the mapping region — the section's H2 header line, its `- AC-x -> test` bullet lines, and blank runs adjacent to them, with symmetric EOF trailing-blank normalization (section-aware, mirroring parse_ac_test_map's H1/H2 toggle; prose inside the section and everything outside it stay frozen);
+  (2) the (ac_id, test_name) pair set only grows — no removal, no value rename — and the mapping-header count does not decrease (deleting the heading would silently re-dormant the gate).
+A mapping bullet correction therefore goes through the Revision Channel like any intent change. Plan-queues / DESIGN.md / openapi specs keep the wholesale deny (no mapping semantics).
 
 Deterministic guard (freeze signal differs per kind):
-  - blueprint / plan-queue: DENY if the target's YAML frontmatter has `status: frozen` (`status: revising` / missing / other, or a brand-new Write -> allow).
+  - blueprint / plan-queue: DENY if the target's YAML frontmatter has `status: frozen` (`status: revising` / missing / other, or a brand-new Write -> allow) — except the blueprint mapping carve-out above.
   - design (DESIGN.md): DENY if the side-car sentinel `.claude/parallel-dev/design.frozen` exists (DESIGN.md's frontmatter is an external token-export with no `status`).
   - openapi (spec): DENY if the side-car sentinel `.claude/parallel-dev/openapi.frozen` exists (same side-car model as design; the spec is external-authored).
 """
@@ -34,6 +37,17 @@ OPENAPI_RE = re.compile(r"(^|/)(openapi|swagger)\.(json|ya?ml)$")
 FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*(?:\n|$)", re.DOTALL)
 STATUS_RE = re.compile(r"^\s*status\s*:\s*['\"]?(\w+)['\"]?\s*$", re.MULTILINE)
 
+# Mapping-carve-out shapes (ADR #58) — duplicated from arch_contract_tests.py's
+# parse_ac_test_map on purpose (self-contained-script convention, rule 7): the
+# guard's open region must match the parser's read region EXACTLY, byte-shape
+# included, or the carve-out drifts from the gate it feeds.
+AC_TEST_MAP_HEADER_RE = re.compile(
+    r"^##\s+Acceptance[\s-]+Criteria\s*(?:->|→)\s*Test\s+Mapping", re.IGNORECASE
+)
+AC_TEST_LINE_RE = re.compile(
+    r"^\s*[-*]\s+([A-Za-z][\w-]*)\s*(?:->|→)\s*(\S(?:.*\S)?)\s*$"
+)
+
 
 def anchor_kind(path):
     """Return 'blueprint' | 'plan-queue' | 'design' | 'openapi' | None for a path."""
@@ -75,6 +89,136 @@ def openapi_is_frozen():
     return os.path.exists(os.path.join(dt.state_dir(), "openapi.frozen"))
 
 
+def _walk_mapping_section(text):
+    """Yield (line, in_section) per line, toggling section state exactly like
+    parse_ac_test_map: an H1/H2 heading closes (or re-opens, if it is the
+    mapping header) the section; deeper headings are content. The carve-out's
+    open region mirrors the parser's read region — same walk, same shapes."""
+    in_section = False
+    for line in (text or "").splitlines():
+        if line.startswith("#"):
+            level = len(line) - len(line.lstrip("#"))
+            if level <= 2:
+                in_section = level == 2 and bool(AC_TEST_MAP_HEADER_RE.match(line))
+            yield line, in_section
+            continue
+        yield line, in_section
+
+
+def _strip_mapping_region(text):
+    """Remove the section's H2 header line, its AC-test bullet lines, and blank
+    runs ADJACENT to them (insertion-point formatting noise — a section added
+    mid-file carries its own surrounding blanks). Prose inside the section and
+    every line outside it STAY — they are compared byte-for-byte, so only
+    header+bullets(+their adjacent blanks) are malleable (ADR #58)."""
+    lines = text.splitlines()
+    strippable = [False] * len(lines)
+    for i, (line, in_section) in enumerate(_walk_mapping_section(text)):
+        if in_section and (line.startswith("#") or AC_TEST_LINE_RE.match(line)):
+            strippable[i] = True
+    # A blank line strips iff its nearest non-blank neighbor above OR below is
+    # strippable — that makes it boundary formatting, not content. A blank
+    # between two frozen lines (kept neighbors on both sides) stays frozen.
+    changed = True
+    while changed:
+        changed = False
+        for i, line in enumerate(lines):
+            if strippable[i] or line.strip():
+                continue
+            up = next((j for j in range(i - 1, -1, -1) if lines[j].strip()), None)
+            down = next((j for j in range(i + 1, len(lines)) if lines[j].strip()), None)
+            if (up is not None and strippable[up]) or (
+                down is not None and strippable[down]
+            ):
+                strippable[i] = True
+                changed = True
+    kept = [line for i, line in enumerate(lines) if not strippable[i]]
+    # Symmetric EOF normalization: drop the trailing blank run from BOTH
+    # residuals. A file frozen with trailing blanks would otherwise deny every
+    # section append (old keeps its EOF blank, new absorbs it as boundary
+    # formatting) — and blanks-at-EOF carry no content, so nothing is hidden.
+    while kept and not kept[-1].strip():
+        kept.pop()
+    return "\n".join(kept)
+
+
+def _mapping_pairs(text):
+    """Set of (ac_id, test_name) from AC-test bullets INSIDE the section — the
+    same pairs parse_ac_test_map would collect (order-free compare is enough
+    for the no-removal invariant)."""
+    pairs = set()
+    for line, in_section in _walk_mapping_section(text):
+        if in_section and not line.startswith("#"):
+            m = AC_TEST_LINE_RE.match(line)
+            if m:
+                pairs.add((m.group(1), m.group(2).strip()))
+    return pairs
+
+
+def _mapping_header_count(text):
+    """Number of H2 mapping headers — deleting the heading unmapped the section
+    (the gate would go dormant), so the count must not decrease."""
+    return sum(
+        1
+        for line, _ in _walk_mapping_section(text)
+        if line.startswith("#") and AC_TEST_MAP_HEADER_RE.match(line)
+    )
+
+
+def _apply_edit(text, old, new, replace_all):
+    """Apply one Edit-shaped substitution with the tool's own semantics: fail
+    on a missing target; without replace_all, fail on a non-unique target. Any
+    failure makes the guard fall back to deny (conservative — the edit itself
+    would not have landed)."""
+    if not isinstance(old, str) or not isinstance(new, str) or old not in text:
+        raise ValueError("edit target missing or malformed")
+    if not replace_all and text.count(old) > 1:
+        raise ValueError("non-unique edit target")
+    return text.replace(old, new) if replace_all else text.replace(old, new, 1)
+
+
+def mapping_append_ok(path, tool, tool_input):
+    """ADR #58 carve-out: True iff the proposed edit touches ONLY the frozen
+    blueprint's mapping region (header + AC-test bullets) AND the (ac_id,
+    test_name) pair set only grows. Everything else — intent, NFRs, seams, even
+    the mapping section's own prose — stays byte-frozen."""
+    try:
+        with open(path, "r", encoding="utf-8") as fh:
+            old_text = fh.read()
+    except OSError:
+        return False
+    try:
+        if tool == "Write":
+            new_text = tool_input["content"]
+            if not isinstance(new_text, str):
+                return False
+        elif tool == "Edit":
+            new_text = _apply_edit(
+                old_text,
+                tool_input["old_string"],
+                tool_input["new_string"],
+                bool(tool_input.get("replace_all", False)),
+            )
+        elif tool == "MultiEdit":
+            new_text = old_text
+            for edit in tool_input["edits"]:
+                new_text = _apply_edit(
+                    new_text,
+                    edit["old_string"],
+                    edit["new_string"],
+                    bool(edit.get("replace_all", False)),
+                )
+        else:
+            return False
+    except (KeyError, TypeError, ValueError):
+        return False
+    return (
+        _strip_mapping_region(old_text) == _strip_mapping_region(new_text)
+        and _mapping_pairs(old_text) <= _mapping_pairs(new_text)
+        and _mapping_header_count(old_text) <= _mapping_header_count(new_text)
+    )
+
+
 def deny(reason):
     print(
         json.dumps(
@@ -93,7 +237,10 @@ def deny(reason):
 DENY_MESSAGES = {
     "blueprint": (
         "Blueprint {path} is FROZEN and read-only (Intent Blueprint anchor). "
-        "The Coder cannot edit it. To change intent, open the Blueprint Revision Channel: "
+        "The Coder cannot edit it. The ONLY post-freeze edit that passes is an APPEND to the "
+        "`## Acceptance-Criteria -> Test Mapping` section (add `- AC-x -> <test-name>` bullets; "
+        "no removals, no renames, nothing outside the section — ADR #58). "
+        "To change intent (or correct a mapping bullet), open the Blueprint Revision Channel: "
         "set frontmatter status to 'revising', escalate to Planner (requirements-manager/Plan) + human, revise, bump blueprint_version, then set status back to 'frozen'. "
         "See references/intent-blueprint.md."
     ),
@@ -135,6 +282,12 @@ def main():
         sys.exit(0)
 
     if frozen_status(file_path) == "frozen":
+        # ADR #58 mapping carve-out — blueprint kind only: an append-only edit
+        # to the AC->test mapping region passes; everything else denies below.
+        if kind == "blueprint" and mapping_append_ok(
+            file_path, tool, payload.get("tool_input") or {}
+        ):
+            sys.exit(0)
         deny(DENY_MESSAGES[kind].format(path=file_path))
     sys.exit(0)
 
diff --git a/skills/parallel-development/infra/hooks/counters.py b/skills/parallel-development/infra/hooks/counters.py
index 9b5fb25..d721544 100644
--- a/skills/parallel-development/infra/hooks/counters.py
+++ b/skills/parallel-development/infra/hooks/counters.py
@@ -36,7 +36,7 @@ def deny(reason):
 
 def loop_status():
     ls = dt.loop_state_path()
-    if not os.path.exists(ls):
+    if not ls or not os.path.exists(ls):
         return None
     try:
         proc = subprocess.run(
diff --git a/skills/parallel-development/infra/hooks/fast_gate.py b/skills/parallel-development/infra/hooks/fast_gate.py
index abfe9c4..514a58c 100644
--- a/skills/parallel-development/infra/hooks/fast_gate.py
+++ b/skills/parallel-development/infra/hooks/fast_gate.py
@@ -260,6 +260,10 @@ def main():
     action = "ok"
     breaker_reason = ""
     try:
+        if not ls:
+            raise FileNotFoundError(
+                "loop_state not resolvable (fail-closed, no project-dir fallback)"
+            )
         proc = subprocess.run(
             ["python3", ls, "gate-fail", fingerprint],
             capture_output=True,
diff --git a/skills/parallel-development/infra/hooks/lib/detect_toolchain.py b/skills/parallel-development/infra/hooks/lib/detect_toolchain.py
index 0c63a2e..6bee834 100644
--- a/skills/parallel-development/infra/hooks/lib/detect_toolchain.py
+++ b/skills/parallel-development/infra/hooks/lib/detect_toolchain.py
@@ -72,12 +72,20 @@ def which_any(*candidates):
 
 def resolve_tool(name):
     """Return an argv prefix to run a tool: [<resolved-path>] or None.
-    Checks PATH first, then the project's local virtualenv bins (.venv/venv/env).
-    Lets gates find tools installed as project dev deps even when the venv is not
-    'active' on PATH."""
+
+    PATH only, by default (pi port, 2026-09-03 security divergence from CC):
+    the project-venv fallback executed whatever binary a repo had committed
+    under .venv/venv/env — a hostile repo could plant an executable and have
+    the gate run it with the user's full privileges, with no prior code exec
+    (the fallback armed exactly in the state where the tool is absent from
+    PATH). Opt back in explicitly per-project with SF_PROJECT_VENV_TOOLS=1
+    when you actually rely on venv dev-dep tooling and trust the repo.
+    """
     p = _shutil_which(name)
     if p:
         return [p]
+    if os.environ.get("SF_PROJECT_VENV_TOOLS") != "1":
+        return None
     root = project_root()
     for venv in (".venv", "venv", "env"):
         cand = os.path.join(root, venv, "bin", name)
@@ -135,11 +143,16 @@ def deny_block(reason):
 
 
 def loop_state_path():
-    """Locate loop_state.py: dev location first (sibling scripts/ dir), then the
-    installed project location."""
+    """Locate loop_state.py: dev/package location only (sibling scripts/ dir).
+
+    The old fallback executed loop_state.py from the PROJECT's
+    .claude/parallel-dev/scripts/ — executing project-committed code with user
+    privileges, dormant only because the package layout happened to satisfy the
+    primary path. Fail closed (None) instead: accounting is best-effort, code
+    execution from the project dir is not an acceptable fallback.
+    """
     here = os.path.dirname(os.path.abspath(__file__))  # .../hooks/lib
     dev = os.path.normpath(os.path.join(here, "..", "..", "scripts", "loop_state.py"))
     if os.path.exists(dev):
         return dev
-    root = os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd()
-    return os.path.join(root, ".claude", "parallel-dev", "scripts", "loop_state.py")
+    return None
```
