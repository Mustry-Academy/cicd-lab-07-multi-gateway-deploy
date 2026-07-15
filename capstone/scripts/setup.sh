#!/usr/bin/env bash
# First bring-up of the cicd-capstone stack ON THE SERVER. Run once; after
# this, all changes flow through git (push to main -> deploy.yml).
#
# The one thing GitOps cannot do is deploy the deployer — this script is that
# bootstrap. Preconditions it checks rather than assumes:
#   - running from /opt/cicd-lab-07/capstone (a clone of this repo)
#   - .env exists (copy .env.example, set RUNNER_GITHUB_PAT or RUNNER_TOKEN)
#   - real secret files exist under secrets/
set -euo pipefail
cd "$(dirname "$0")/.."

STACK_DIR_EXPECTED=/opt/cicd-lab-07/capstone
[ "$(pwd)" = "$STACK_DIR_EXPECTED" ] || {
  echo "Run from $STACK_DIR_EXPECTED (the runner bind-mounts that exact path); you are in $(pwd)" >&2
  exit 1
}

[ -f .env ] || { echo "No .env — cp .env.example .env and fill it in." >&2; exit 1; }

if [ ! -s secrets/gateway_admin_password.txt ]; then
  echo "Generating secrets/gateway_admin_password.txt"
  openssl rand -base64 24 > secrets/gateway_admin_password.txt
fi
# Postgres credentials are first-boot values (initdb); generated once, then
# they live in the postgres-data volume. Hex on purpose: these values end up
# inside connection URLs and student hand-tests — a charset that can never
# need escaping beats one that sometimes does.
generated_pg=0
if [ ! -s secrets/postgres_username.txt ]; then
  echo "Generating secrets/postgres_username.txt"
  printf 'oat_%s' "$(openssl rand -hex 4)" > secrets/postgres_username.txt
  generated_pg=1
fi
if [ ! -s secrets/postgres_password.txt ]; then
  echo "Generating secrets/postgres_password.txt"
  openssl rand -hex 24 | tr -d '\n' > secrets/postgres_password.txt
  generated_pg=1
fi
# Same values must exist as the repo's Actions secrets — push them now so a
# fresh bring-up is done in one go (non-fatal: the script prints the manual
# commands if no usable GitHub token is around).
if [ "$generated_pg" -eq 1 ]; then
  scripts/sync-github-secrets.sh \
    || echo "WARNING: GitHub secret sync failed — see instructions above." >&2
fi
# Owned by the in-container ignition user (uid 2003), mode 400: compose
# bind-mounts secret files as-is, and the gateway must be able to read it
# (root-owned 600 = AccessDeniedException at commissioning).
chmod 400 secrets/*.txt
chown 2003:2003 secrets/*.txt

# Runner needs one of the two auth paths (see .env.example).
if ! grep -qE '^(RUNNER_GITHUB_PAT|RUNNER_TOKEN)=.+' .env; then
  echo "Set RUNNER_GITHUB_PAT (preferred) or a fresh RUNNER_TOKEN in .env." >&2
  echo "Mint a token from a laptop with:" >&2
  echo "  gh api -X POST repos/Mustry-Academy/cicd-lab-07-multi-gateway-deploy/actions/runners/registration-token --jq .token" >&2
  exit 1
fi

# The gateway container runs as the ignition user (uid 2003) and must be able
# to write nightly backups into ./backups.
mkdir -p backups
chown 2003:2003 backups

# Nightly gwbk + db-dump backup (scripts/backup.sh) — installed here so a
# from-scratch rebuild needs no manual cron step. cron.d format (with user
# field); idempotent overwrite.
cat > /etc/cron.d/cicd-capstone-backup <<'CRON'
10 3 * * * root /opt/cicd-lab-07/capstone/scripts/backup.sh >> /var/log/cicd-capstone-backup.log 2>&1
CRON
chmod 644 /etc/cron.d/cicd-capstone-backup
echo "Backup cron installed at /etc/cron.d/cicd-capstone-backup"

docker compose config -q
docker compose up -d

echo
echo "Stack starting. Watch it with: docker compose ps ; docker compose logs -f"
echo "Gateway (via caddy, once the cert is issued): https://cloud.mustrysolutions.com"
echo "Runner registration: check https://github.com/Mustry-Academy/cicd-lab-07-multi-gateway-deploy/settings/actions/runners"
