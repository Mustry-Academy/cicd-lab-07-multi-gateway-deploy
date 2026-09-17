#!/usr/bin/env bash
# Verify the demo through its database and native Perspective page routes.
# No optional Web Dev module license is required for this readiness check.
set -euo pipefail
container="${POSTGRES_CONTAINER:-cicd-capstone-postgres}"
gateway="${IGNITION_CONTAINER:-cicd-capstone-gateway}"
url="${PUBLIC_URL:-https://cloud.mustrysolutions.com}"
mode="${1:-check}"
tmp="$(mktemp)"
trap 'rm -f "$tmp"' EXIT
read_health() {
  docker exec "$container" sh -c '
    user="${POSTGRES_USER:-}"
    if [ -z "$user" ]; then user="$(cat /run/secrets/postgres_username)"; fi
    psql -U "$user" -d ignition -X -tA -v ON_ERROR_STOP=1 -c "SELECT oat_demo.health()"
  ' > "$tmp"
}
read_health
first="$(python3 -c 'import json,sys;print(json.load(open(sys.argv[1])).get("lastTick",""))' "$tmp")"
if [ "$mode" = progress ]; then
  advanced=false
  for _ in $(seq 1 18); do
    sleep 5
    read_health
    latest="$(python3 -c 'import json,sys;print(json.load(open(sys.argv[1])).get("lastTick",""))' "$tmp")"
    if [ "$latest" != "$first" ]; then advanced=true; break; fi
  done
  test "$advanced" = true || { echo 'The gateway continuity timer did not advance.' >&2; exit 1; }
fi
docker exec "$gateway" grep -q "REVISION = 'showroom-1'" /usr/local/bin/ignition/data/projects/oatmakers/ignition/script-python/application/demo/code.py
python3 tools/demo/check-live.py "$url" --health-file "$tmp"
