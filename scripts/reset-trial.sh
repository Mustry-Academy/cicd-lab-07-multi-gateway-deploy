#!/usr/bin/env bash
# Reset the gateways' two-hour trial, so licensed functionality starts serving
# again.
#
# Ignition's trial runs for two hours at a time. When it lapses, licensed
# functionality stops serving: Perspective pages stop rendering, the Designer
# drops its connection, and deploy workflows start failing on things that
# worked an hour ago. The failures look like application bugs, but they are a
# licensing state.
#
# This is the same reset the "Reset Trial" button in the gateway UI performs —
# a single authenticated POST to /data/api/v1/trial. Unlimited and entirely
# legal for development.
#
# Do NOT reach for `docker compose down -v` or `scripts/teardown.sh --volumes`
# here. The trial clock lives in the gateway volume, so wiping it looks like the
# right move and is not: you throw away your gateway state (and your test
# gateway's seeded API token) to solve a problem one HTTP call solves.
# Restarting the container does not help either — the clock survives it.
#
# Safe to run unconditionally: it reads the trial state first and only POSTs
# when the trial has actually expired.
#
# Usage:
#   scripts/reset-trial.sh          # both gateways (default)
#   scripts/reset-trial.sh local    # just the local gateway
#   scripts/reset-trial.sh test     # just your personal test gateway
#
# Gateways (ports come from docker-compose.yaml):
#   local   http://localhost:8088   your bind-mounted development gateway
#   test    http://localhost:8090   the `test` profile gateway (Part 0, opt-in)
#
# With no argument, a gateway that is not running is skipped rather than
# reported as a failure — the test profile only rides along once LAB_USER is
# set in .env. Name it explicitly and a non-responding gateway is an error.
#
# Env:
#   IGNITION_URL      full URL; if set, wins over the gateway preset
#   IGNITION_API_KEY  API key. If unset, read from .env (written there by
#                     scripts/generate-api-key.sh during setup).

set -uo pipefail

# shellcheck source=lib.sh
. "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/lib.sh"

CURL_MAX_TIME=15

# ---- arg parsing ----------------------------------------------------------

requested=()
explicit=0

while [ $# -gt 0 ]; do
  case "$1" in
    -h|--help)
      sed -n '2,40p' "$0" | sed 's/^# \{0,1\}//'
      exit 0
      ;;
    local|test)
      requested+=("$1")
      explicit=1
      shift
      ;;
    *)
      echo "ERROR: unknown gateway: $1 (expected: local | test)" >&2
      exit 2
      ;;
  esac
done

[ ${#requested[@]} -eq 0 ] && requested=(local test)

# ---- gateway URLs ---------------------------------------------------------

# Deliberately not lib.sh's gateway_url(): that map still carries lab 06's
# three-gateway layout. This lab ships two gateways, both from the repo-root
# docker-compose.yaml.
trial_url() {
  case "$1" in
    local) printf 'http://localhost:8088' ;;
    test)  printf 'http://localhost:8090' ;;
    *)     return 1 ;;
  esac
}

# ---- API key --------------------------------------------------------------

# Both gateways accept the same key in this lab: setup.sh seeds the generated
# CICD-APIKEY token resource into the test gateway's volume before its first
# boot, so one lookup covers both.
load_api_key_from_env
if is_placeholder_api_key; then
  echo "ERROR: IGNITION_API_KEY is not set (env or .env)." >&2
  echo "Run scripts/setup.sh — it generates the key into .env." >&2
  exit 2
fi

# ---- helpers --------------------------------------------------------------

# Reads `expired` / `trialSecondsLeft` / `licenseMode` off stdin as three fields.
parse_trial() {
  python3 -c 'import sys, json; d = json.load(sys.stdin); print(d["expired"], d["trialSecondsLeft"], d["licenseMode"])'
}

fmt() { printf '%d:%02d:%02d' $(( $1 / 3600 )) $(( $1 % 3600 / 60 )) $(( $1 % 60 )); }

read_trial() {
  curl -sf -m "$CURL_MAX_TIME" -H "X-Ignition-API-Token: $IGNITION_API_KEY" "$1/data/api/v1/trial"
}

# Reset one gateway. Returns 0 on success or "nothing to do", 1 on failure,
# 2 when the gateway is not responding (the caller decides whether that is a
# failure or a skip).
reset_gateway() {
  local name="$1" url="$2"

  # Local dev only. Resetting a trial is a licensing action, and production is
  # a shared, remote gateway — nobody should reset its clock from a laptop.
  local host="${url#*://}"; host="${host%%[:/]*}"
  case "$host" in
    localhost|127.0.0.1|::1|0.0.0.0) ;;
    *)
      echo -e "  ${RED}✗${NC} refusing to reset the trial on '$host': this is a local-dev tool" >&2
      return 1
      ;;
  esac

  local before
  before="$(read_trial "$url")" || return 2

  local expired seconds_left mode
  read -r expired seconds_left mode <<<"$(printf '%s' "$before" | parse_trial || true)"
  if ! [[ "$seconds_left" =~ ^[0-9]+$ ]]; then
    echo -e "  ${RED}✗${NC} $name returned an unexpected trial response" >&2
    return 1
  fi

  if [ "$mode" != "Trial" ]; then
    echo -e "  ${GREEN}✓${NC} $name is licensed ($mode); nothing to reset"
    return 0
  fi
  if [ "$expired" != "True" ]; then
    echo -e "  ${GREEN}✓${NC} $name trial is still running ($(fmt "$seconds_left") left); nothing to reset"
    return 0
  fi

  # The gateway rejects a reset with 403 until the trial has genuinely expired,
  # which is why this only fires in the expired branch. No request body — the
  # Reset Trial button in the gateway UI issues exactly this bare POST.
  local status
  status="$(curl -s -m "$CURL_MAX_TIME" -o /dev/null -w '%{http_code}' \
    -X POST -H "X-Ignition-API-Token: $IGNITION_API_KEY" "$url/data/api/v1/trial")"
  if [ "$status" != "200" ]; then
    echo -e "  ${RED}✗${NC} $name reset rejected (HTTP $status)" >&2
    [ "$status" = "401" ] && echo "    the API token was not accepted — check IGNITION_API_KEY in .env" >&2
    [ "$status" = "403" ] && echo "    the gateway does not consider the trial expired yet" >&2
    return 1
  fi

  # Verify rather than trust the response: a reported success that did not move
  # the server-side clock would be worse than no script at all.
  local after
  read -r _ after _ <<<"$(read_trial "$url" | parse_trial || true)"
  if ! [[ "$after" =~ ^[0-9]+$ ]]; then
    echo -e "  ${RED}✗${NC} $name returned 200 but the trial state could not be re-read to confirm it" >&2
    return 1
  fi
  if [ "$after" -le "$seconds_left" ]; then
    echo -e "  ${RED}✗${NC} $name returned 200 but the clock did not move ($(fmt "$after") left)" >&2
    return 1
  fi
  echo -e "  ${GREEN}✓${NC} $name trial reset — $(fmt "$after") remaining"
}

# ---- go -------------------------------------------------------------------

failed=0
for name in "${requested[@]}"; do
  url="${IGNITION_URL:-$(trial_url "$name")}"
  reset_gateway "$name" "$url"
  case "$?" in
    0) ;;
    2)
      if [ "$explicit" = "1" ]; then
        echo -e "  ${RED}✗${NC} $name is not responding at $url" >&2
        failed=1
      else
        echo -e "  ${YELLOW}-${NC} $name is not running at $url; skipped"
      fi
      ;;
    *) failed=1 ;;
  esac
done

exit $failed
