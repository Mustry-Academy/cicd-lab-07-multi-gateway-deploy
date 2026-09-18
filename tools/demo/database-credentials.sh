#!/usr/bin/env bash
# Use the running PostgreSQL service's managed credentials for the demo.
set -euo pipefail
container="${POSTGRES_CONTAINER:-cicd-capstone-postgres}"
username="$(docker exec "$container" sh -c 'if [ -n "${POSTGRES_USER_FILE:-}" ]; then cat "$POSTGRES_USER_FILE"; else printf "%s" "${POSTGRES_USER:-}"; fi')"
password="$(docker exec "$container" sh -c 'if [ -n "${POSTGRES_PASSWORD_FILE:-}" ]; then cat "$POSTGRES_PASSWORD_FILE"; else printf "%s" "${POSTGRES_PASSWORD:-}"; fi')"
test -n "$username" && test -n "$password" || { echo 'Managed database credentials are missing.' >&2; exit 1; }
mask() {
  local value="$1"
  value="${value//%/%25}"
  value="${value//$'\r'/%0D}"
  value="${value//$'\n'/%0A}"
  printf '::add-mask::%s\n' "$value"
}
if [ "${GITHUB_ACTIONS:-false}" = true ]; then mask "$username"; mask "$password"; fi
case "$username$password" in *$'\n'*|*$'\r'*) echo 'Multiline database credentials are not supported.' >&2; exit 1;; esac
# TCP authentication verifies the password, unlike a local trusted socket.
docker exec -e PGPASSWORD="$password" "$container" \
  psql -h 127.0.0.1 -U "$username" -d "${POSTGRES_DB:-ignition}" -X -tA -v ON_ERROR_STOP=1 -c 'SELECT 1' >/dev/null
umask 077
printf 'DEMO_POSTGRES_USERNAME=%s\nDEMO_POSTGRES_PASSWORD=%s\n' "$username" "$password" >> "${GITHUB_ENV:?environment output path required}"
echo 'Verified managed credentials against the running PostgreSQL service.'
