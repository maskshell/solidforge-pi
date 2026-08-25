# cross-source-review — install / provisioning

> How to arm `cross-source-review` (csr) — inside the solidforge workspace OR externally
> (e.g. fedaot wiki). csr's gating is SELF-contained: its self-gates run on csr's own
> infra, NOT the target project's code, so an external project installs nothing (unlike
> parallel-development, whose gates run in the target and need `arm-tools`). csr's only
> runtime dependency is the different-family leg's provider token.

## Provisioning model — env-based, NO arm command

csr is armed by ONE environment variable (the provider token). There is no `arm` command.
csr's self-gates are csr's own (they check csr's scripts/schemas in the solidforge dev
workspace), so the INVOKING project never runs them and installs nothing. The only thing
the invoking project provides at runtime is the different-family leg's token.

## The one required var + where to set it

Set the default provider's token:

- shell (wins): `export DEEPSEEK_ANTHROPIC_AUTH_TOKEN=sk-...`
- OR the invoking project's `.env` (a `KEY=VALUE` line)
- OR, in the solidforge workspace, `.env.solidforge` (arm-tools-provisioned)

**Sole source (namespace isolation)**: the wrapper reads ONLY `<UPPERCASE-FILENAME>_ANTHROPIC_AUTH_TOKEN` for a provider's token. The provider's native `<FILENAME>_API_KEY` (e.g. `DEEPSEEK_API_KEY`) is NEVER read — the `_ANTHROPIC_AUTH_TOKEN` suffix namespaces the credential to this substrate's Anthropic gateway, so it cannot collide with the native var (which may be set in the same env for a different tool/SDK, possibly a different key/quota). A project carrying both `DEEPSEEK_API_KEY` (its own native-SDK use) and `DEEPSEEK_ANTHROPIC_AUTH_TOKEN` (this substrate) is the intended state, not a smell. See the namespace-isolation ADR.

## `.env` resolution (CWD-based — why csr is portable)

csr's substrate (`infra/scripts/hetero_doc_review.py`) reads the INVOKING project's env
(the current `cwd`), in order:

1. `<cwd>/.env.solidforge` — the host workspace's arm-env IF present (the solidforge arm
   convention; absent + silently skipped in external projects).
2. `<cwd>/.env` — the generic project env.

Then the shell env (always wins; between the two files, the first-loaded wins for a shared
key). So: in solidforge → reads the armed `.env.solidforge`; in an external project →
reads that project's `.env`. CWD-based = portable.

## Optional — the profile selector (`HETERO_DOC_PROFILE`)

`HETERO_DOC_PROFILE` selects the provider NAME(S), resolved against csr's OWN
`infra/scripts/profiles/`. Default `deepseek`. Comma-list = dual-/multi-different-family (each backend
runs independently; findings merged + tagged with `provider`):

- `HETERO_DOC_PROFILE=deepseek` (default)
- `HETERO_DOC_PROFILE=deepseek,qwen3` (dual-different-family)

csr's profile selector is SEPARATE from pd's `HETERO_PROFILE` (the two skills do not share
it). The TOKEN vars ARE shared (same provider → same credential).

## Optional — the timeout (`HETERO_DOC_TIMEOUT`)

`HETERO_DOC_TIMEOUT` sets the per-subprocess wall-clock cap (seconds) for
`hetero_doc_review.py`. Default `600`. A cold large doc can exceed 600s
and return a `hetero-subprocess-timeout` malformation. For a known-cold large review: raise
it (e.g. `1200`). Do NOT remap a profile alias to dodge a timeout — cold-start is transient
(DeepSeek auto-caches ~99% after the first call), and a global alias remap permanently
sacrifices review depth on warm calls (ADR #43; the one MEASURED exception: the deepseek
profile's pro→flash demotion, ADR #53 — persistent pathology, not transient cold-start;
all deepseek tiers now map to `deepseek-v4-flash[1m]`). `HETERO_DOC_TIMEOUT` is SEPARATE from pd's
`HETERO_TIMEOUT` (mirrors the `HETERO_DOC_PROFILE` / `HETERO_PROFILE` split).

- `HETERO_DOC_TIMEOUT=1200` (example — raise for cold large docs)

## Optional — the run guards (`HETERO_DOC_MAX_TURNS` / `HETERO_DOC_MAX_STREAM_BYTES`)

Two wrapper-side caps with sane defaults — set them only for an unusual doc regime
(ADR #52):

- `HETERO_DOC_MAX_TURNS` — hard cap on the review subprocess's agentic turns.
  Default `60`. Print-mode Claude Code has NO default turn limit; tripping the cap
  DEGRADES honestly (`error_max_turns`, ADR #41) — the same-family leg stands.
- `HETERO_DOC_MAX_STREAM_BYTES` — runaway breaker on the accumulated stream
  (bytes, including token-delta partial events). Default `67108864` (64MiB).
  Tripping it MALFORMS loudly (`hetero-stream-bytes-cap`) — the 2026-08-21
  incident class (a provider-side endless stream otherwise burns the full
  wall-clock cap invisibly).

While a review runs, the wrapper emits a progress heartbeat line to stderr every
30s (`{"type":"hetero-heartbeat",...}` — elapsed / stream bytes / assistant events / the
RESOLVED model name / idle seconds). stdout stays the single result JSON. The
result also carries a `provider_runs[]` array (resolved model / assistant events /
bytes / elapsed per provider), so a post-hoc reader answers "which model actually ran,
and was the stream alive?" from the record alone. The `--no-stream` CLI flag
restores the legacy single-envelope json spawn — the documented fallback if a
Claude Code upgrade breaks the stream-json surface.

## Adding a custom third-party provider (zero code change)

csr ships `infra/scripts/profiles/deepseek.json`. Add another provider by dropping a
`profiles/<name>.json` (ROUTING ONLY — no secret) + setting its token var. csr resolves
the profile against its OWN `profiles/` dir, INDEPENDENT from pd's (adding a csr profile
does NOT affect pd).

### Profile template (routing only)

`profiles/<name>.json` carries `ANTHROPIC_BASE_URL` (the provider's Anthropic-compatible
endpoint) + model aliases (tier → the provider's model id) + an optional `model` default.
NO `ANTHROPIC_AUTH_TOKEN` field, NO `${...}` ceremony. Example — a custom OpenAI-compatible
gateway:

```json
{
  "_provider": "my-gateway",
  "env": {
    "ANTHROPIC_BASE_URL": "https://my-gateway.example.com/anthropic",
    "ANTHROPIC_DEFAULT_OPUS_MODEL": "my-strong-model",
    "ANTHROPIC_DEFAULT_SONNET_MODEL": "my-fast-model",
    "ANTHROPIC_DEFAULT_HAIKU_MODEL": "my-cheap-model"
  },
  "model": "my-strong-model"
}
```

### Token-var naming rule

The token var is derived BY CONVENTION from the profile filename:
`<UPPERCASE-FILENAME>_ANTHROPIC_AUTH_TOKEN`. Non-alphanumeric chars in the filename
collapse to `_` before uppercasing.

| profile filename (ROUTE) | `_family` (FAMILY) | token env var |
| --- | --- | --- |
| `zai-coding-cn.json` | glm | (auth.json route — `_token_env` empty; fallback `ZAI_CODING_CN_API_KEY`) |
| `deepseek.json` | deepseek | `DEEPSEEK_ANTHROPIC_AUTH_TOKEN` (bridged to `DEEPSEEK_API_KEY`) |
| `minimax-cn.json` | minimax | `MINIMAX_ANTHROPIC_AUTH_TOKEN` (via `_token_env`; bridged to `MINIMAX_CN_API_KEY`) |
| `qwen-token-plan-cn.json` | qwen | `QWEN_TOKEN_PLAN_CN_API_KEY` (subscription key) |
| `qwen-bailian.json` | qwen | `QWEN3_ANTHROPIC_AUTH_TOKEN` (the Bailian pay-per-use key; route registered by sf-providers) |

**Naming — the three-level doctrine** (the profile FILENAME names the credential+endpoint ROUTE; the `_family` field names the MODEL LINEAGE — the same/different-family judgment unit; the `model` field is the pinned per-generation id, never part of the filename). One family rides many routes (qwen: token-plan subscription + bailian pay-per-use; glm: pi's zai-coding-cn coding route); a multi-family route's `_family` names the PINNED model's lineage. Pick review routes across FAMILIES, not across routes of one family. Full doctrine: parallel-development's model-routing.md. CC-era profile names (`bigmodel`, `minimax`, `qwen3`) resolve via the wrappers' alias map.

Override the var name via the profile's optional `_token_env` field (rarely needed — e.g.
a profile that must read a non-conventional var).

csr reads the token from shell / `.env` / `.env.solidforge`, INJECTS it as
`ANTHROPIC_AUTH_TOKEN` into a throwaway chmod-600 temp settings file passed to
the spawned `pi` child's environment (the wrapper loads it into `os.environ`; the bundled sf-providers extension reads the same convention var). The real token NEVER touches the committed profile.

### Use the new provider

`HETERO_DOC_PROFILE=<name>` (or `--profile <name>` on the substrate CLI), with
`<UPPERCASE_NAME>_ANTHROPIC_AUTH_TOKEN` set. Done — no code change.

## What needs no arming

- The same-family leg (`solidforge:doc-reviewer`) — a local fresh-context agent; needs nothing
  beyond the Claude Code runtime.
- The convergence engine (`converge.py`) — pure stdlib; jsonschema OPTIONAL (the engine
  graceful-skips schema validation if absent, with an honest coverage note). The solidforge
  dev workspace ships jsonschema via `uv sync` (dev deps, fix C) — the SKIP note appears
  only in environments without it.
- **Record schema version note (fix A / ADR #3)**: records produced before the retention
  fix (round `findings` + `dispositions` required) no longer validate against the current
  `convergence-record.schema.json`. Historical counts-only records (e.g. any emitted before
  2026-08) are accepted as-is — no migration (ADR #3); treat them as version-0 records.
- csr's self-gates — run on csr's own infra (the solidforge dev workspace). An external
  project invoking csr NEVER runs them.
