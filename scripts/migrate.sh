#!/bin/bash
# migrate.sh — run golang-migrate in Docker against the LOCAL dev database
# (the lab07-postgres container from the repo-root docker-compose.yaml), the
# same way the Deploy workflow migrates the capstone's database. No local
# install needed; the tool runs from the migrate/migrate image on the stack's
# own Docker network.
#
# Usage:
#   scripts/migrate.sh up [N]        # apply all (or N) pending
#   scripts/migrate.sh down N        # roll back N steps
#   scripts/migrate.sh version       # current position + dirty flag
#   scripts/migrate.sh force V       # reset a dirty ledger to version V
#
# The applied position is tracked in the database's schema_migrations table:
#   docker exec lab07-postgres psql -U ignition -d ignition \
#     -c 'SELECT * FROM schema_migrations;'
set -euo pipefail
cd "$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

MIGRATE_IMAGE="migrate/migrate:v4.17.1"
DB_CONTAINER="${DB_CONTAINER:-lab07-postgres}"
MIGRATIONS_DIR="db-migration/migrate"
PG_USER="${POSTGRES_USER:-ignition}"
PG_PASS="${POSTGRES_PASSWORD:-lab07-postgres-pw}"
DATABASE="${POSTGRES_DB:-ignition}"

[ $# -gt 0 ] || { sed -n '2,15p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'; exit 1; }

if ! find "$MIGRATIONS_DIR" -name '*.sql' -print -quit 2>/dev/null | grep -q .; then
  echo "No migrations in $MIGRATIONS_DIR — nothing to do."
  exit 0
fi

if ! docker inspect "$DB_CONTAINER" > /dev/null 2>&1; then
  echo "Error: container '$DB_CONTAINER' not found — is the stack up? (docker compose up -d)" >&2
  exit 1
fi
NETWORK="$(docker inspect "$DB_CONTAINER" \
  --format '{{range $k, $_ := .NetworkSettings.Networks}}{{$k}}{{end}}')"

# Credentials go INTO a URL, so they must be percent-encoded — same move as
# the Deploy workflow (a ':' '@' '/' or '%' in the password breaks the URL).
urlenc() {
  local s="$1" out='' c i
  for ((i = 0; i < ${#s}; i++)); do
    c="${s:i:1}"
    case "$c" in
      [a-zA-Z0-9.~_-]) out+="$c" ;;
      *) printf -v c '%%%02X' "'$c"; out+="$c" ;;
    esac
  done
  printf '%s' "$out"
}

# create + docker cp + start instead of a bind mount: works identically on
# the host and inside a containerized runner.
DB_URL="postgres://$(urlenc "$PG_USER"):$(urlenc "$PG_PASS")@${DB_CONTAINER}:5432/${DATABASE}?sslmode=disable"
echo "migrate $* -> ${DATABASE} (network: ${NETWORK})"

cid="$(docker create --network "$NETWORK" "$MIGRATE_IMAGE" \
  -path=/migrations -database "$DB_URL" "$@")"
# shellcheck disable=SC2317,SC2329  # invoked via the EXIT trap
cleanup() { docker rm -f "$cid" > /dev/null 2>&1 || true; }
trap cleanup EXIT

docker cp "$MIGRATIONS_DIR/." "$cid:/migrations/" > /dev/null
rc=0
docker start -a "$cid" || rc=$?
if [ "$rc" -ne 0 ]; then
  echo "migrate exited with status $rc" >&2
  echo "  If the ledger is 'dirty', fix the failed migration and run:" >&2
  echo "    scripts/migrate.sh force <version>" >&2
fi
exit "$rc"
