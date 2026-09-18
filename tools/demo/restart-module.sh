#!/usr/bin/env bash
# One controlled restart is needed when a new gateway module is installed.
set -euo pipefail
test "${DEMO_MODULE_CHANGED:-false}" = true || exit 0
wait_ready() {
  for _ in $(seq 1 60); do
    if curl -fsS --max-time 5 "$IGNITION_URL/StatusPing" 2>/dev/null | grep -q RUNNING; then return 0; fi
    sleep 5
  done
  return 1
}
docker restart "$IGNITION_CONTAINER"
if wait_ready; then
  echo 'Gateway is running with the staged Mustry UI module.'
  exit 0
fi
echo 'Module startup failed; restoring the prior module registry and binary.' >&2
docker exec -u root "$IGNITION_CONTAINER" sh -c '
  set -eu
  cp "$1/modules.json" "$2/modules.json"
  if [ -f "$1/Mustry_UI.modl" ]; then cp "$1/Mustry_UI.modl" "$2/custom-modules/Mustry_UI.modl";
  else rm -f "$2/custom-modules/Mustry_UI.modl"; fi
  chown 2003:0 "$2/modules.json"
' sh "$DEMO_MODULE_BACKUP" "${GATEWAY_DATA_PATH:-/usr/local/bin/ignition/data}"
docker restart "$IGNITION_CONTAINER"
wait_ready || echo 'Gateway requires operator attention after restoring the previous module state.' >&2
exit 1
