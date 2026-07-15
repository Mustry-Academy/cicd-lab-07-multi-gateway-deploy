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

# ---- bring up the stack ---------------------------------------------------

docker compose up -d

wait_running() {
  echo -n "Waiting for the gateway to reach RUNNING "
  for _ in $(seq 1 60); do
    state="$(curl -fsS -m 3 http://localhost:8088/StatusPing 2>/dev/null || true)"
    if echo "$state" | grep -q '"state":"RUNNING"' && ! echo "$state" | grep -q COMMISSIONING; then
      echo " up."
      return 0
    fi
    echo -n "."
    sleep 5
  done
  echo ""
  echo -e "${RED}Gateway did not reach RUNNING — check: docker logs lab07-gateway${NC}" >&2
  exit 1
}
wait_running

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
echo ""
echo "git status should be clean now — if the identity files ever show up"
echo "dirty again, re-run this script (CI blocks them from merging anyway)."
