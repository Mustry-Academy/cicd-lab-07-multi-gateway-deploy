#!/usr/bin/env bash
# Nightly gateway backup (gwbk) + rotation. Installed on the server as a root
# cron job (see docs/runbook.md, "Backups"):
#   10 3 * * * /opt/cicd-lab-07/capstone/scripts/backup.sh >> /var/log/cicd-capstone-backup.log 2>&1
#
# The gwbk contains projects, config, and the internal database — everything
# needed to rebuild the gateway on a fresh volume. It deliberately lands in
# ./backups (gitignored) and NOT in git: backups are state, not source.
# shellcheck disable=SC2012  # ls-by-mtime is fine: filenames are our own fixed-format stamps
set -euo pipefail

STACK_DIR=/opt/cicd-lab-07/capstone
KEEP=14
STAMP=$(date +%Y%m%d-%H%M)
DEST="/backups/cicd-capstone-${STAMP}.gwbk"   # path INSIDE the container (= ./backups on host)

docker exec cicd-capstone-gateway ./gwcmd.sh -b "$DEST"

# Course database: the gwbk knows nothing about postgres, so dump it too.
# The image's pg_hba trusts local-socket connections, so no password is
# needed inside the container.
docker exec cicd-capstone-postgres sh -c \
  'pg_dump -U "$(cat /run/secrets/postgres_username)" ignition' \
  | gzip > "$STACK_DIR/backups/cicd-capstone-db-${STAMP}.sql.gz"

# Rotate: keep the newest $KEEP of each
cd "$STACK_DIR/backups"
ls -1t cicd-capstone-*.gwbk 2>/dev/null | tail -n +$((KEEP + 1)) | xargs -r rm --
ls -1t cicd-capstone-db-*.sql.gz 2>/dev/null | tail -n +$((KEEP + 1)) | xargs -r rm --

echo "$(date -Is) backup OK -> $(ls -1t cicd-capstone-*.gwbk | head -1) + $(ls -1t cicd-capstone-db-*.sql.gz | head -1)"
