#!/usr/bin/env bash
# One-time fix after the FIRST `docker compose up` of a fresh clone.
#
# First-boot commissioning cannot be avoided: because the repo already
# carries a security-properties resource, the gateway treats the admin
# credentials from the compose env as a PASSWORD RESET — it invents a
# "temp" identity provider + user source (admin / password) and rewrites
# security-properties to point at them.
#
# This script makes the result look like every other lab:
#   1. promote the temp pair to "default" (gitignored, stays local)
#   2. restore the committed security-properties (points at "default")
#   3. restart the gateway so it picks both up
#
# Safe to re-run any time: it exits early when there is nothing to fix.
set -euo pipefail
cd "$(dirname "$0")/.."

IG=services/config/resources/core/ignition

if [ ! -d "$IG/user-source/temp" ] && [ ! -d "$IG/identity-provider/temp" ]; then
  git checkout -- "$IG/security-properties" 2>/dev/null || true
  echo "Nothing to fix — no temp identity present."
  exit 0
fi

# 1. temp user source → default (files unchanged, so its signature stays valid)
rm -rf "$IG/user-source/default"
mv "$IG/user-source/temp" "$IG/user-source/default"

# 2. temp identity provider → default, repointed at the "default" user source.
#    Editing config.json invalidates the recorded signature, so drop it —
#    the gateway accepts unsigned resources.
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

# 3. put the committed permission policy back and restart onto it
git checkout -- "$IG/security-properties"
docker compose restart gateway

echo "Done. Local gateway now uses the default identity (admin / password)."
echo "Wait for it to come back up: curl -s http://localhost:8088/StatusPing"
