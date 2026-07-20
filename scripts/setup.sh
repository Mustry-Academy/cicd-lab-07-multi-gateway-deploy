#!/bin/bash
# One-shot setup for the lab 07 stack:
#   - sanity-checks the host (docker compose v2, curl, git, python3)
#   - brings up the stack (local Ignition gateway + TimescaleDB)
#   - waits for the gateway to reach RUNNING
#   - fixes the one-time first-boot identity churn: commissioning invents a
#     "temp" idp/user source (password reset semantics, because the repo
#     already carries security-properties) — this promotes it to the
#     gitignored "default" (admin / password), restores the committed
#     security-properties, and restarts the gateway
#
# Re-run safely — every step is idempotent.

set -euo pipefail

RED='\033[0;31m'; GREEN='\033[0;32m'; NC='\033[0m'
[ -n "${NO_COLOR:-}" ] && RED='' && GREEN='' && NC=''

cd "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/.."

# ---- Host preflight (WSL/permissions) --------------------------------------
# Refuses a sudo'd run, verifies the repo is not on the Windows filesystem
# (/mnt/c), reclaims root-owned leftovers, and exports LAB_GID so the
# gateway container writes files this user can still edit. See
# scripts/preflight.sh and docs/wsl-setup.md.
# shellcheck source=preflight.sh disable=SC1091
. "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/preflight.sh"
lab_preflight

# ---- prerequisites --------------------------------------------------------

require_cmd() {
  command -v "$1" >/dev/null 2>&1 || {
    echo -e "${RED}Error: '$1' is required but not installed.${NC}" >&2
    exit 1
  }
}

require_cmd docker
require_cmd curl
require_cmd git
require_cmd python3

if ! docker compose version >/dev/null 2>&1; then
  echo -e "${RED}Error: Docker Compose V2 plugin is required but not installed.${NC}" >&2
  exit 1
fi

echo -e "${GREEN}Mustry Academy — Lab 07 setup${NC}"
echo "================================"

# ---- Part 0 opt-in: is the personal test gateway configured? ---------------
# The test profile (test-gateway + test-runner) only rides along when the
# student has set LAB_USER in .env (see .env.example). Without it, this
# script manages just the dev stack, exactly as before.

PROFILE_ARGS=()
if grep -qs '^LAB_USER=..*' .env && ! grep -qs '^LAB_USER=yourname$' .env; then
  PROFILE_ARGS=(--profile test)
fi

# ---- Part 0: seed the test gateway's API token BEFORE its first boot --------
# The scan API only accepts tokens the gateway has LOADED, and a deploy
# cannot scan its own token in (the scan call already needs it). The test
# gateway has no bind mount, so we write into its named volume with a
# throwaway container — the same trick preflight.sh uses to repair volumes.
#
# The collection manifest MUST come along: on first boot the gateway creates
# the `core` collection and refuses a non-empty dir that has no manifest
# ("Resource collection path ... exists but is not empty" -> FAULTED).
#
# Deliberately NOT seeded: security-properties. A gateway that boots with a
# pre-existing security-properties treats commissioning as a password reset
# and stamps a "temp" identity instead of "default" (see the first-boot fix
# below) — and the deploy's wipe step only preserves the identity named
# "default", so that path ends in an admin lockout. The committed
# security-properties ships with the FIRST DEPLOY instead; the workflow's
# 401/403 self-heal restart loads it.
seed_test_gateway() {
  local vol seed
  vol="$(docker compose config --format json 2>/dev/null \
    | python3 -c 'import json,sys; print(json.load(sys.stdin).get("name",""))')_test-gateway-data"

  # Create the container (and thereby the volume) WITHOUT booting it: if the
  # gateway wins this race, commissioning runs before the token is on disk.
  docker compose "${PROFILE_ARGS[@]}" create test-gateway >/dev/null 2>&1 || true
  docker volume inspect "$vol" >/dev/null 2>&1 || return 0

  # Already seeded (or already deployed to)? Nothing to do.
  if docker run --rm -v "$vol:/d" alpine:3 \
       test -d /d/config/resources/core/ignition/api-token 2>/dev/null; then
    return 0
  fi

  echo "Seeding the test gateway's API token before its first boot..."
  local tmp
  tmp="$(mktemp -d)"
  mkdir -p "$tmp/resources/core/ignition"
  cp services/config/resources/core/config-mode.json "$tmp/resources/core/"
  cp -R services/config/resources/core/ignition/api-token "$tmp/resources/core/ignition/"
  docker run --rm -v "$vol:/d" -v "$tmp:/seed:ro" alpine:3 \
    sh -c 'mkdir -p /d/config && cp -R /seed/. /d/config/ && chown -R 2003:0 /d'
  rm -rf "$tmp"
  echo "  seeded api-token into $vol"
}

if [ ${#PROFILE_ARGS[@]} -gt 0 ]; then
  seed_test_gateway
fi

# ---- bring up the stack ---------------------------------------------------

docker compose "${PROFILE_ARGS[@]}" up -d

wait_running() {
  local port="${1:-8088}" container="${2:-lab07-gateway}"
  echo -n "Waiting for the gateway on :$port to reach RUNNING "
  for _ in $(seq 1 60); do
    state="$(curl -fsS -m 3 "http://localhost:$port/StatusPing" 2>/dev/null || true)"
    if echo "$state" | grep -q '"state":"RUNNING"' && ! echo "$state" | grep -q COMMISSIONING; then
      echo " up."
      return 0
    fi
    echo -n "."
    sleep 5
  done
  echo ""
  echo -e "${RED}Gateway did not reach RUNNING — check: docker logs $container${NC}" >&2
  exit 1
}
wait_running 8088 lab07-gateway
if [ ${#PROFILE_ARGS[@]} -gt 0 ]; then
  wait_running 8090 lab07-test-gateway
fi

# ---- one-time first-boot identity fix --------------------------------------

IG=services/config/resources/core/ignition

if [ -d "$IG/user-source/temp" ] || [ -d "$IG/identity-provider/temp" ]; then
  echo "First boot detected — replacing the commissioning's temp identity..."

  # temp user source → default (files unchanged, so its signature stays valid)
  rm -rf "$IG/user-source/default"
  mv "$IG/user-source/temp" "$IG/user-source/default"

  # temp identity provider → default, repointed at the "default" user source.
  # Editing config.json invalidates the recorded signature, so drop it —
  # the gateway accepts unsigned resources.
  rm -rf "$IG/identity-provider/default"
  mv "$IG/identity-provider/temp" "$IG/identity-provider/default"
  python3 - "$IG/identity-provider/default" <<'EOF'
import json, sys, os
d = sys.argv[1]
cfg_path = os.path.join(d, 'config.json')
cfg = json.load(open(cfg_path))
cfg['settings']['userSource'] = 'default'
json.dump(cfg, open(cfg_path, 'w'), indent=2, sort_keys=True)
res_path = os.path.join(d, 'resource.json')
res = json.load(open(res_path))
res['description'] = 'Local identity provider backed by the "default" user source.'
res['attributes'].pop('lastModificationSignature', None)
json.dump(res, open(res_path, 'w'), indent=2)
EOF

  # put the committed permission policy back and restart onto it
  git checkout -- "$IG/security-properties"
  docker compose restart gateway
  wait_running
else
  # nothing to promote; still make sure commissioning churn isn't lingering
  git checkout -- "$IG/security-properties" 2>/dev/null || true
fi

# ---- summary ----------------------------------------------------------------

echo ""
echo -e "${GREEN}Ready.${NC}"
echo "  gateway    http://localhost:8088   admin / password"
echo "  postgres   localhost:5432          ignition / lab07-postgres-pw"
if [ ${#PROFILE_ARGS[@]} -gt 0 ]; then
  echo "  test gw    http://localhost:8090   admin / password   (your deploy target)"
  echo "  runner     check Settings -> Actions -> Runners for your '<yourname>-local' label"
fi
echo ""
echo "git status should be clean now — if the identity files ever show up"
echo "dirty again, re-run this script (CI blocks them from merging anyway)."
