#!/usr/bin/env bash
# Bring up the isolated customer-demo runtime without touching other gateways.
set -euo pipefail
cd "$(dirname "$0")/../.."
scripts/generate-api-key.sh
first_boot=false
if ! docker inspect oatmakers-ui-local-gateway-1 >/dev/null 2>&1; then first_boot=true; fi
docker compose -f compose.demo.yml up -d database
for _ in $(seq 1 30); do
  if docker compose -f compose.demo.yml exec -T database pg_isready -U ignition -d ignition >/dev/null 2>&1; then break; fi
  sleep 2
done
docker run --rm --network oatmakers-ui-local_default \
  -v "$PWD/db-migration/migrate:/migrations:ro" migrate/migrate:v4.17.1 \
  -path=/migrations -database 'postgres://ignition:lab07-postgres-pw@postgres:5432/ignition?sslmode=disable&x-migrations-table=oat_demo_schema_migrations' up
if [ "$(docker inspect -f '{{.State.Running}}' oatmakers-ui-local-gateway-1 2>/dev/null || true)" != true ]; then
  docker compose -f compose.demo.yml up -d gateway
fi
for _ in $(seq 1 45); do
  if curl -fsS --max-time 3 http://localhost:18096/StatusPing 2>/dev/null | grep -q RUNNING; then break; fi
  sleep 2
done
if [ "$first_boot" = true ]; then
  # Commissioning replaces the token-aware permissions with Administrator-only
  # defaults. Restore only these two local permission fields, then load them.
  python3 - <<'PYTHON'
import json, subprocess
from pathlib import Path
path=Path('services/config/resources/core/ignition/security-properties/config.json')
original=json.loads(subprocess.check_output(['git','show','HEAD:'+str(path)]))
current=json.loads(path.read_text())
for key in ('readPermissions','writePermissions'):
    current[key]=original[key]
path.write_text(json.dumps(current,indent=2)+'\n')
PYTHON
  docker compose -f compose.demo.yml restart gateway
  for _ in $(seq 1 60); do
    if curl -fsS --max-time 3 http://localhost:18096/StatusPing 2>/dev/null | grep -q RUNNING; then break; fi
    sleep 2
  done
fi
IGNITION_URL=http://localhost:18096 scripts/scan.sh local
IGNITION_URL=http://localhost:18096 scripts/reset-trial.sh local
echo 'Open http://localhost:18096/data/perspective/client/oatmakers/'
