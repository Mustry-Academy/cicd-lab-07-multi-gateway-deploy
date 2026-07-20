#!/usr/bin/env bash
# mint-api-key.sh — (re)generate the PRODUCTION deploy pipeline's Ignition
# API key. Instructors only; run it on the host that runs the production
# gateway container (the capstone box).
#
# One command, both homes, no gateway UI, no commit:
#   1. generates a fresh secret (base64url, gateway-decodable)
#   2. builds the CICD-APIKEY api-token resource (hash only, scheme:
#      base64url(sha256(base64url_decode(secret))), verified against
#      Ignition 8.3.7; secureChannelRequired stays false — the deploy scans
#      over in-network HTTP) and docker-cp's it INTO the gateway container,
#      then restarts the gateway so it loads the new token
#   3. sets the repo's IGNITION_API_KEY Actions secret to the full header
#      value "CICD-APIKEY:<secret>" (the gateway looks tokens up by the name
#      before the colon)
#
# The token resource lives ONLY on the gateway's disk and in the Actions
# secret — never in git. The deploy workflow's wipe spares api-token/, so
# the installed token survives every deploy. Rotation = re-running this
# script; no commit, no tag, no release pin involved.
#
# (Students never run this: scripts/generate-api-key.sh gives each clone its
# own key for the local + personal test gateways.)
#
# Usage:
#   scripts/mint-api-key.sh                        # container cicd-capstone-gateway
#   scripts/mint-api-key.sh <container-name>       # another gateway container
set -euo pipefail
cd "$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

REPO="${REPO:-Mustry-Academy/cicd-lab-07-multi-gateway-deploy}"
TOKEN_NAME="CICD-APIKEY"
CONTAINER="${1:-cicd-capstone-gateway}"
TOKEN_DIR=/usr/local/bin/ignition/data/config/resources/core/ignition/api-token

command -v gh > /dev/null || { echo "gh CLI required." >&2; exit 1; }
command -v python3 > /dev/null || { echo "python3 required." >&2; exit 1; }
docker inspect -f '{{.State.Status}}' "$CONTAINER" 2>/dev/null | grep -q running || {
  echo "Container $CONTAINER is not running on this host." >&2
  echo "Run this on the box that hosts the production gateway." >&2
  exit 1
}

secret="$(openssl rand -base64 33 | tr -- '+/' '-_' | tr -d '=\n')"

TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
python3 - "$secret" "$TMP/$TOKEN_NAME" <<'EOF'
import base64, hashlib, json, os, sys, time, uuid
secret, out = sys.argv[1], sys.argv[2]
raw = base64.urlsafe_b64decode(secret + "=" * (-len(secret) % 4))
h = base64.urlsafe_b64encode(hashlib.sha256(raw).digest()).decode().rstrip("=")
os.makedirs(out)
with open(os.path.join(out, "config.json"), "w") as f:
    json.dump({
        "profile": {
            # The deploy's scan calls arrive over plain in-network HTTP; a
            # secure-channel-only token can never authenticate them.
            "secureChannelRequired": False,
            # This lab's committed security-properties grants the flat
            # Authenticated/APIKEY level (not labs 04-06's APIToken/*).
            "securityLevels": [{
                "children": [{"children": [], "name": "APIKEY"}],
                "description": "Represents a user who has been authenticated by the system.",
                "name": "Authenticated",
            }],
            "timestamp": int(time.time() * 1000),
            "type": "basic-token",
        },
        "settings": {"tokenHash": h},
    }, f, indent=2)
    f.write("\n")
with open(os.path.join(out, "resource.json"), "w") as f:
    json.dump({
        "scope": "A", "description": "", "version": 1,
        "restricted": False, "overridable": True,
        "files": ["config.json"],
        "attributes": {"uuid": str(uuid.uuid4()), "enabled": True},
    }, f, indent=2)
    f.write("\n")
EOF

echo "  installing $TOKEN_NAME into $CONTAINER..."
docker exec -u root "$CONTAINER" mkdir -p "$TOKEN_DIR"
docker exec -u root "$CONTAINER" rm -rf "$TOKEN_DIR/$TOKEN_NAME"
docker cp "$TMP/$TOKEN_NAME" "$CONTAINER:$TOKEN_DIR/$TOKEN_NAME"
docker exec -u root "$CONTAINER" chown -R 2003:0 "$TOKEN_DIR"

echo "  restarting $CONTAINER (token resources load at boot)..."
docker restart "$CONTAINER" >/dev/null

printf '%s:%s' "$TOKEN_NAME" "$secret" | gh secret set IGNITION_API_KEY --repo "$REPO"
echo "  IGNITION_API_KEY -> $REPO (format: $TOKEN_NAME:<secret>)"

cat <<EOF

Done. The gateway is restarting with the new token and the secret is live in
GitHub — the next deploy authenticates with the new pair. If the first scan
after a rotation races the restart, the workflow's 401 self-heal retries it.
EOF
