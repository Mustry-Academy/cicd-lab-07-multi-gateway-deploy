#!/usr/bin/env bash
# Bring up the isolated customer-demo runtime without touching other gateways.
set -euo pipefail
cd "$(dirname "$0")/../.."
scripts/generate-api-key.sh
# First-boot commissioning creates Administrator-only gateway permissions.
# This local-only token already owns gateway configuration through APIKEY.
python3 - <<'PY'
import json
from pathlib import Path
path=Path('services/config/resources/core/ignition/api-token/CICD-APIKEY/config.json')
value=json.loads(path.read_text())
children=value['profile']['securityLevels'][0]['children']
if not any(x.get('name')=='Roles' for x in children):
    children.append({'name':'Roles','children':[{'name':'Administrator','children':[]}]})
path.write_text(json.dumps(value,indent=2)+'\n')
PY
docker compose -f compose.demo.yml up -d database
for _ in $(seq 1 30); do
  if docker compose -f compose.demo.yml exec -T database pg_isready -U ignition -d ignition >/dev/null 2>&1; then break; fi
  sleep 2
done
docker run --rm --network oatmakers-showroom-local_default \
  -v "$PWD/db-migration/migrate:/migrations:ro" migrate/migrate:v4.17.1 \
  -path=/migrations -database 'postgres://ignition:lab07-postgres-pw@postgres:5432/ignition?sslmode=disable&x-migrations-table=oat_demo_schema_migrations' up
if [ "$(docker inspect -f '{{.State.Running}}' oatmakers-showroom-local-gateway-1 2>/dev/null || true)" != true ]; then
  docker compose -f compose.demo.yml up -d gateway
fi
for _ in $(seq 1 45); do
  if curl -fsS --max-time 3 http://localhost:18094/StatusPing 2>/dev/null | grep -q RUNNING; then break; fi
  sleep 2
done
IGNITION_URL=http://localhost:18094 scripts/scan.sh local
IGNITION_URL=http://localhost:18094 scripts/reset-trial.sh local
echo 'Open http://localhost:18094/data/perspective/client/oatmakers/'
