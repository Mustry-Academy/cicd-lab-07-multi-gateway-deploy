#!/usr/bin/env bash
# Restore only this deployment's project/config backup; keep demo data intact.
set -euo pipefail
container="${IGNITION_CONTAINER:?gateway container required}"
backup="${DEMO_BACKUP:?deployment backup required}"
case "$backup" in /backups/oatmakers-demo/*) ;; *) echo 'Invalid backup path' >&2; exit 1;; esac
docker exec -u root "$container" sh -c '
  set -eu
  backup="$1"; data=/usr/local/bin/ignition/data
  test -d "$backup/project"
  rm -rf "$data/projects/oatmakers"
  cp -a "$backup/project" "$data/projects/oatmakers"
  chown -R 2003:0 "$data/projects/oatmakers"
  for item in database-connection/OatmakersDemo secret-provider/DemoRuntime; do
    rm -rf "$data/config/resources/core/ignition/$item"
    if [ -d "$backup/config/$item" ]; then
      mkdir -p "$data/config/resources/core/ignition/$(dirname "$item")"
      cp -a "$backup/config/$item" "$data/config/resources/core/ignition/$item"
    fi
  done
' sh "$backup"
for resource in config projects; do
  curl -fsS --max-time 30 -X POST -H "X-Ignition-API-Token: $IGNITION_API_KEY" \
    "$IGNITION_URL/data/api/v1/scan/$resource" >/dev/null
done
echo 'Previous Oatmakers resources restored. Demo database records preserved.'
