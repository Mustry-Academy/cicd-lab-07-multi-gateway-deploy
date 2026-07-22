#!/usr/bin/env bash
# generate-api-key.sh — provision THIS CLONE's Ignition scan-API key, without
# ever putting a secret (or its hash) in git.
#
# Earlier versions of this lab committed the CICD-APIKEY token resource, so
# every clone and every fork carried the hash the shared repo secret matched.
# Now each clone generates its own key:
#
#   1. ensures .env has a real IGNITION_API_KEY — if the line is empty,
#      missing, or a placeholder, it generates `CICD-APIKEY:<base64url(32
#      random bytes)>` and writes it into .env
#   2. writes the matching api-token resource — the gateway stores only the
#      SHA-256 hash of the secret — into
#        services/config/resources/core/ignition/api-token/CICD-APIKEY/
#      (gitignored: it must never enter a commit). The local gateway loads it
#      from the bind mount; setup.sh seeds the same resource into your test
#      gateway's volume before its first boot.
#
# Your test-deploy workflow reads the key from the RUNNER's environment —
# docker-compose.yaml passes IGNITION_API_KEY from .env into your
# test-runner container — so no GitHub secret is involved for your own
# gateway. (Production is different: its key is minted by the instructors
# with scripts/mint-api-key.sh and lives in the repo's IGNITION_API_KEY
# Actions secret.)
#
# Idempotent: an existing key in .env is kept, and the resource is only
# (re)written when its hash does not match the key. .env is the single
# source of truth — a wiped config tree is restored on the next run.
#
# Usage:
#   scripts/generate-api-key.sh          # normally invoked by setup.sh

set -euo pipefail
cd "$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

command -v python3 >/dev/null || { echo "python3 required." >&2; exit 1; }

[ -f .env ] || cp .env.example .env

python3 - "$PWD" <<'PYEOF'
import base64, hashlib, json, os, re, secrets, sys, time, uuid

root = sys.argv[1]
env_path = os.path.join(root, ".env")
with open(env_path) as f:
    env_text = f.read()

TOKEN_NAME = "CICD-APIKEY"
VAR = "IGNITION_API_KEY"

m = re.search(rf"^[ \t]*{VAR}=(.*)$", env_text, re.M)
value = m.group(1).strip().strip("\"'") if m else ""

if not value or "replace-me" in value or ":" not in value:
    secret = base64.urlsafe_b64encode(secrets.token_bytes(32)).rstrip(b"=").decode()
    value = f"{TOKEN_NAME}:{secret}"
    line = f"{VAR}={value}"
    if m:
        env_text = env_text[:m.start()] + line + env_text[m.end():]
    else:
        env_text = env_text + ("" if env_text.endswith("\n") else "\n") + line + "\n"
    with open(env_path, "w") as f:
        f.write(env_text)
    print(f"  generated a new API key into .env ({VAR})")

name, secret_b64 = value.split(":", 1)
raw = base64.urlsafe_b64decode(secret_b64 + "=" * (-len(secret_b64) % 4))
thash = base64.urlsafe_b64encode(hashlib.sha256(raw).digest()).rstrip(b"=").decode()

res_dir = os.path.join(root, "services/config/resources/core/ignition/api-token", name)
config_path = os.path.join(res_dir, "config.json")
current = None
if os.path.isfile(config_path):
    try:
        with open(config_path) as f:
            current = json.load(f)["settings"]["tokenHash"]
    except (ValueError, KeyError):
        pass
if current != thash:
    os.makedirs(res_dir, exist_ok=True)
    with open(config_path, "w") as f:
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
            "settings": {"tokenHash": thash},
        }, f, indent=2)
        f.write("\n")
    with open(os.path.join(res_dir, "resource.json"), "w") as f:
        json.dump({
            "scope": "A", "description": "", "version": 1,
            "restricted": False, "overridable": True,
            "files": ["config.json"],
            "attributes": {"uuid": str(uuid.uuid4()), "enabled": True},
        }, f, indent=2)
        f.write("\n")
    print(f"  wrote api-token resource -> services/config/.../api-token/{name}/")
PYEOF
