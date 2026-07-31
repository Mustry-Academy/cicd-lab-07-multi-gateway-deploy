#!/usr/bin/env bash
# Trigger both gateway scan endpoints — /data/api/v1/scan/projects and
# /data/api/v1/scan/config. Hitting these tells the gateway to pick up new
# content on disk under data/projects/ and data/config/ without a restart.
# Both scans always run (fired in parallel): after changing files you want
# the gateway to see the full tree, projects and config alike.
#
# The script waits SCAN_WAIT_SECONDS (see below) to give the gateway time to
# complete the scans, and finally reports each response: HTTP code +
# pretty-printed body. Numeric *timestamp fields (e.g. lastScanTimestamp) are
# rewritten to local human-readable time when jq is available.
#
# Usage:
#   scripts/scan.sh               # local gateway (default)
#   scripts/scan.sh test          # test gateway
#   scripts/scan.sh production    # production gateway
#
# Gateways:
#   local        http://localhost:8088   (default — student's bind-mounted gateway)
#   test         http://localhost:8089   (deploy.yml target)
#   production   http://localhost:8090   (deploy.yml target=production)
#
# Env (override the gateway defaults when needed):
#   IGNITION_URL          full URL; if set, wins over the gateway preset
#   IGNITION_API_KEY      API key. If unset, looked up from .env as
#                         IGNITION_API_KEY_<GATEWAY> first, then plain
#                         IGNITION_API_KEY.
#   SCAN_WAIT_SECONDS     seconds to wait between firing the scan(s) and
#                         reading the response (default: 2).

set -euo pipefail

# shellcheck source=lib.sh
. "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/lib.sh"

# ---- tunables -------------------------------------------------------------

SCAN_WAIT_SECONDS="${SCAN_WAIT_SECONDS:-2}"
CURL_MAX_TIME=30   # seconds; protects against a hung gateway

# ---- arg parsing ---------------------------------------------------------

gateway="local"

while [ $# -gt 0 ]; do
  case "$1" in
    -h|--help)
      sed -n '2,29p' "$0" | sed 's/^# \{0,1\}//'
      exit 0
      ;;
    local|test|production)
      gateway="$1"
      shift
      ;;
    *)
      echo "ERROR: unknown environment: $1 (expected: local | test | production)" >&2
      exit 2
      ;;
  esac
done

TARGETS=("projects" "config")

# ---- resolve gateway URL --------------------------------------------------

# IGNITION_URL env var (if set) wins. Otherwise use the preset for the
# selected gateway.
IGNITION_URL="${IGNITION_URL:-$(gateway_url "$gateway")}"

# ---- API key --------------------------------------------------------------

load_api_key_from_env "$gateway"
if [ -z "${IGNITION_API_KEY:-}" ]; then
  echo "ERROR: IGNITION_API_KEY is not set (env or .env)." >&2
  echo "Looked for IGNITION_API_KEY_${gateway^^} and IGNITION_API_KEY in .env." >&2
  echo "Generate one in the gateway UI at $IGNITION_URL — Config → Security → API Keys → New" >&2
  exit 2
fi

# ---- tempfile cleanup -----------------------------------------------------

TMP_FILES=()
cleanup_tempfiles() {
  [ ${#TMP_FILES[@]} -gt 0 ] && rm -f "${TMP_FILES[@]}"
}
trap cleanup_tempfiles EXIT

# ---- helpers --------------------------------------------------------------

# Human-readable timestamp prefix for log lines.
ts() {
  date '+%Y-%m-%d %H:%M:%S'
}

# jq filter: rewrite any numeric field whose key matches /^timestamp$|Timestamp$/
# (e.g. lastScanTimestamp, lastModificationTimestamp) into a local human-readable
# string. Treats values >= 1e12 as epoch milliseconds, otherwise epoch seconds.
JQ_HUMAN_TS='
def fmt_ts:
  (if . >= 1000000000000 then . / 1000 else . end)
  | strflocaltime("%Y-%m-%d %H:%M:%S");
walk(
  if type == "object" then
    with_entries(
      if (.key | test("^timestamp$|Timestamp$"))
         and (.value | type) == "number"
      then .value |= fmt_ts
      else .
      end
    )
  else . end
)
'

# Pretty-print a response body. JSON via jq when available; otherwise raw.
# Output is indented 4 spaces so it nests cleanly under the endpoint header.
pretty_print() {
  local body="$1"
  [ -z "$body" ] && return
  if command -v jq >/dev/null 2>&1 && printf '%s' "$body" | jq -e . >/dev/null 2>&1; then
    printf '%s\n' "$body" | jq "$JQ_HUMAN_TS" | sed 's/^/    /'
  else
    printf '%s\n' "$body" | sed 's/^/    /'
  fi
}

# Fire one scan POST. Writes the response body to $2 and the HTTP code to $3.
# Designed to be safe to run in the background ( & ) — silent, all output goes
# to files, the wrapper handles printing.
fire_scan() {
  local what="$1" body_file="$2" code_file="$3"
  local url="$IGNITION_URL/data/api/v1/scan/$what"
  curl -sS -X POST \
    --max-time "$CURL_MAX_TIME" \
    -H "X-Ignition-API-Token: $IGNITION_API_KEY" \
    -H "Accept: application/json" \
    -o "$body_file" -w "%{http_code}" "$url" >"$code_file" 2>/dev/null \
    || echo "000" >"$code_file"
}

# Print the verdict + pretty-printed body for one already-fired scan.
report_scan() {
  local what="$1" body_file="$2" code_file="$3"
  local code body
  code=$(<"$code_file")
  [ -z "$code" ] && code="000"
  body=$(<"$body_file")
  if [ "$code" -ge 200 ] && [ "$code" -lt 300 ]; then
    echo "[$(ts)]   ✓ $what  HTTP $code"
    pretty_print "$body"
    return 0
  else
    echo "[$(ts)]   ✗ $what  HTTP $code" >&2
    pretty_print "$body" >&2
    return 1
  fi
}

# Fire 1..N scans in parallel, wait SCAN_WAIT_SECONDS, then report each.
# Works uniformly for a single target or multiple — `wait` (no args) blocks
# until all background curls return; for a single target it just waits on
# that one job.
run_scans() {
  local targets=("$@")
  local body_files=() code_files=()
  local what i

  # allocate tempfiles (also pushed onto TMP_FILES for the EXIT trap)
  for what in "${targets[@]}"; do
    local b c
    b=$(mktemp); c=$(mktemp)
    body_files+=("$b"); code_files+=("$c")
    TMP_FILES+=("$b" "$c")
    echo "[$(ts)] → $what scan on $gateway gateway ($IGNITION_URL/data/api/v1/scan/$what)"
  done

  # fire all POSTs in the background — true parallel when there are 2
  for i in "${!targets[@]}"; do
    fire_scan "${targets[$i]}" "${body_files[$i]}" "${code_files[$i]}" &
  done
  wait

  echo "[$(ts)]   waiting ${SCAN_WAIT_SECONDS}s for gateway to settle..."
  sleep "$SCAN_WAIT_SECONDS"

  # report each — cleanup is handled by the EXIT trap
  local exit_code=0
  for i in "${!targets[@]}"; do
    report_scan "${targets[$i]}" "${body_files[$i]}" "${code_files[$i]}" || exit_code=1
  done
  return $exit_code
}

# ---- go -------------------------------------------------------------------

run_scans "${TARGETS[@]}"
