#!/usr/bin/env bash
# Mirror the stack's postgres secret files into the repo's GitHub Actions
# secrets (POSTGRES_USERNAME / POSTGRES_PASSWORD) — same value, two homes:
# the compose stack reads the files, the Deploy workflow reads the Actions
# secrets (migrations + the gateway's /run/secrets files).
#
# Called by setup.sh right after generating the files, so a fresh bring-up
# lands the values in both homes in one go. Safe to re-run any time (e.g.
# after a rotation — see secrets/README.md).
#
# Auth, in order of preference:
#   1. an already-authenticated gh (laptop case)
#   2. GH_TOKEN, or RUNNER_GITHUB_PAT from ./.env (server case) — the PAT
#      needs the fine-grained "Secrets: Read and write" repo permission,
#      which is MORE than runner registration needs; grant it on the PAT if
#      you want unattended first-boot sync.
# If neither can write secrets, this prints the exact manual commands and
# exits non-zero (setup.sh treats that as a warning, not a failure).
set -euo pipefail
cd "$(dirname "$0")/.."

REPO="${REPO:-Mustry-Academy/cicd-lab-07-multi-gateway-deploy}"

for f in secrets/postgres_username.txt secrets/postgres_password.txt; do
  [ -s "$f" ] || { echo "Missing $f — generate it first (setup.sh does)." >&2; exit 1; }
done

command -v gh > /dev/null || {
  echo "gh CLI not installed — install it, or run from a machine that has it." >&2
  exit 1
}

# Server case: no interactive gh login, but the runner PAT may be in .env.
if ! gh auth status > /dev/null 2>&1 && [ -z "${GH_TOKEN:-}" ] && [ -f .env ]; then
  pat="$(sed -n 's/^RUNNER_GITHUB_PAT=//p' .env | tail -1)"
  [ -n "$pat" ] && export GH_TOKEN="$pat"
fi

sync_one() {
  gh secret set "$1" --repo "$REPO" < "$2"
  echo "  $1 -> $REPO"
}

if sync_one POSTGRES_USERNAME secrets/postgres_username.txt \
   && sync_one POSTGRES_PASSWORD secrets/postgres_password.txt; then
  echo "GitHub Actions secrets in sync with secrets/*.txt."
else
  cat >&2 <<EOF

Could not write the Actions secrets (no usable token — the runner PAT needs
the "Secrets: Read and write" repo permission for unattended sync). Run this
from a machine where gh is authenticated:

  gh secret set POSTGRES_USERNAME --repo $REPO < secrets/postgres_username.txt
  gh secret set POSTGRES_PASSWORD --repo $REPO < secrets/postgres_password.txt
EOF
  exit 1
fi
