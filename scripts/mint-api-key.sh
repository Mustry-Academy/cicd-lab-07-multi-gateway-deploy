#!/usr/bin/env bash
# mint-api-key.sh — (re)generate the deploy pipeline's Ignition API key.
#
# One command, both homes, no gateway UI:
#   1. generates a fresh secret (base64url, gateway-decodable)
#   2. writes its hash into the CICD-APIKEY api-token resource in
#      services/config/ (scheme: base64url(sha256(base64url_decode(secret))),
#      verified against Ignition 8.3.7) and keeps secureChannelRequired
#      false — the deploy scans over in-network HTTP
#   3. sets the repo's IGNITION_API_KEY Actions secret to the full header
#      value "CICD-APIKEY:<secret>" (the gateway looks tokens up by the name
#      before the colon)
#
# The hash only reaches the gateway through the normal release flow — after
# committing, cut the next oatmakers tag and pin it in release.yaml (the
# gateway payload rides the oatmakers pin). Until that deploy lands, the old
# key keeps working; the first deploy after it self-heals via a restart.
set -euo pipefail
cd "$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

REPO="${REPO:-Mustry-Academy/cicd-lab-07-multi-gateway-deploy}"
TOKEN_NAME="CICD-APIKEY"
CONFIG="services/config/resources/core/ignition/api-token/$TOKEN_NAME/config.json"

[ -f "$CONFIG" ] || { echo "No $CONFIG in this checkout." >&2; exit 1; }
command -v gh > /dev/null || { echo "gh CLI required." >&2; exit 1; }
command -v python3 > /dev/null || { echo "python3 required." >&2; exit 1; }

secret="$(openssl rand -base64 33 | tr -- '+/' '-_' | tr -d '=\n')"

python3 - "$secret" "$CONFIG" <<'EOF'
import base64, hashlib, json, sys
secret, path = sys.argv[1], sys.argv[2]
raw = base64.urlsafe_b64decode(secret + "=" * (-len(secret) % 4))
h = base64.urlsafe_b64encode(hashlib.sha256(raw).digest()).decode().rstrip("=")
with open(path) as f:
    cfg = json.load(f)
cfg["settings"]["tokenHash"] = h
# The deploy's scan calls arrive over plain in-network HTTP; a
# secure-channel-only token can never authenticate them.
cfg["profile"]["secureChannelRequired"] = False
with open(path, "w") as f:
    json.dump(cfg, f, indent=2)
    f.write("\n")
print(f"  tokenHash -> {path}")
EOF

printf '%s:%s' "$TOKEN_NAME" "$secret" | gh secret set IGNITION_API_KEY --repo "$REPO"
echo "  IGNITION_API_KEY -> $REPO (format: $TOKEN_NAME:<secret>)"

cat <<EOF

Done. The new key is live in GitHub; the gateway still runs the old one.
Ship the hash through the normal flow:

  1. commit $CONFIG (PR, review, merge)
  2. git tag oatmakers@vX.Y.Z && git push origin oatmakers@vX.Y.Z
  3. bump release.yaml to that tag by PR

The first deploy after the pin lands 401s once, restarts the gateway to load
the new token, and retries — by design. Every deploy after that scans hot.
EOF
