#!/usr/bin/env bash
# Nightly gateway backup (gwbk) + rotation. Installed on the server as a root
# cron job (see docs/runbook.md, "Backups"):
#   10 3 * * * /opt/cicd-lab-07/capstone/scripts/backup.sh >> /var/log/cicd-capstone-backup.log 2>&1
#
# The gwbk contains projects, config, and the internal database — everything
# needed to rebuild the gateway on a fresh volume. It deliberately lands in
# ./backups (gitignored) and NOT in git: backups are state, not source.
set -euo pipefail

STACK_DIR=/opt/cicd-lab-07/capstone
KEEP=14
STAMP=$(date +%Y%m%d-%H%M)
DEST="/backups/cicd-capstone-${STAMP}.gwbk"   # path INSIDE the container (= ./backups on host)

docker exec cicd-capstone-gateway ./gwcmd.sh -b "$DEST"

# Rotate: keep the newest $KEEP
cd "$STACK_DIR/backups"
ls -1t cicd-capstone-*.gwbk 2>/dev/null | tail -n +$((KEEP + 1)) | xargs -r rm --

echo "$(date -Is) backup OK -> $(ls -1t cicd-capstone-*.gwbk | head -1)"
