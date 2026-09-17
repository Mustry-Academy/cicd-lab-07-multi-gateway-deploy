#!/usr/bin/env bash
# Replace only the Oatmakers project and the two resources owned by this demo.
set -euo pipefail
payload="${1:?payload directory required}"
container="${IGNITION_CONTAINER:?gateway container required}"
data="${GATEWAY_DATA_PATH:-/usr/local/bin/ignition/data}"
backup="/backups/oatmakers-demo/$(date -u +%Y%m%dT%H%M%SZ)"
test -f "$payload/projects/oatmakers/project.json"
for item in database-connection/OatmakersDemo secret-provider/DemoRuntime; do
  test -f "$payload/services/config/resources/core/ignition/$item/config.json"
done
# A prior version remains available even if a resource scan subsequently fails.
docker exec -u root "$container" sh -c '
  set -eu
  data="$1"; backup="$2"
  mkdir -p "$backup/config"
  if [ -d "$data/projects/oatmakers" ]; then cp -a "$data/projects/oatmakers" "$backup/project"; fi
  for item in database-connection/OatmakersDemo secret-provider/DemoRuntime; do
    if [ -d "$data/config/resources/core/ignition/$item" ]; then
      mkdir -p "$backup/config/$(dirname "$item")"
      cp -a "$data/config/resources/core/ignition/$item" "$backup/config/$item"
    fi
  done
  printf "%s\n" "$backup" > /backups/oatmakers-demo/latest
  find /backups/oatmakers-demo -mindepth 1 -maxdepth 1 -type d -mtime +89 -exec rm -rf {} +
' sh "$data" "$backup"
if [ -n "${GITHUB_ENV:-}" ]; then printf 'DEMO_BACKUP=%s\n' "$backup" >> "$GITHUB_ENV"; fi
# Stage first, then swap just this project's directory. No gateway restart.
docker cp "$payload/projects/oatmakers" "$container:$backup/new-project"
docker exec -u root "$container" sh -c '
  set -eu
  data="$1"; backup="$2"
  chown -R 2003:0 "$backup/new-project"
  if [ -d "$data/projects/oatmakers" ]; then mv "$data/projects/oatmakers" "$backup/replaced-project"; fi
  cp -a "$backup/new-project" "$data/projects/oatmakers"
' sh "$data" "$backup"
for item in database-connection/OatmakersDemo secret-provider/DemoRuntime; do
  docker exec -u root "$container" mkdir -p "$data/config/resources/core/ignition/$item"
  docker cp "$payload/services/config/resources/core/ignition/$item/." "$container:$data/config/resources/core/ignition/$item/"
  docker exec -u root "$container" chown -R 2003:0 "$data/config/resources/core/ignition/$item"
done
printf 'Scoped Oatmakers deployment staged. Backup: %s\n' "$backup"
