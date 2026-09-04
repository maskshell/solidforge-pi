#!/bin/sh
# e2e_probe.sh — the AUTHENTICATED install-path probe (the one leg CI cannot
# run: it needs model credentials). Loads the repo as a temporary package via
# pi's real `-e` path (package resolution + extension load/activate + skill
# load) and round-trips one LLM turn, asserting a unique marker survives.
#
# Complements the CI set: ci.yml proves resource loading + extension init
# headless (pi_loader_smoke / pi_extensions_load_smoke / namespace smoke);
# this proves the authenticated end-to-end session. Run before releases from
# a credentialed machine. Usage: tools/e2e_probe.sh [repo-path]
set -eu
REPO="${1:-$(cd "$(dirname "$0")/.." && pwd)}"
MARKER="SF-E2E-OK-$$"
out=$(pi -e "$REPO" -p "Reply with exactly: $MARKER" 2>&1) || {
	printf '%s\n' "$out" >&2
	echo "e2e probe FAIL: pi -e exited nonzero" >&2
	exit 1
}
case "$out" in
*"$MARKER"*)
	echo "e2e probe PASS — marker round-tripped through package load + extension init + LLM turn"
	exit 0
	;;
*)
	printf '%s\n' "$out" >&2
	echo "e2e probe FAIL: marker absent from reply" >&2
	exit 1
	;;
esac
