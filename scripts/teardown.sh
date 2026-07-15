#!/bin/bash
# Stop and remove the lab stack.
#
# Usage:
#   scripts/teardown.sh              # docker compose down (keeps volumes)
#   scripts/teardown.sh --volumes    # also wipes named volumes AND the local
#                                    # gateway's gitignored identity files —
#                                    # DATA LOSS; next boot re-commissions
#                                    # (run scripts/setup.sh to come back up)
#   scripts/teardown.sh --help

set -euo pipefail

GREEN='\033[0;32m'; YELLOW='\033[1;33m'; NC='\033[0m'
[ -n "${NO_COLOR:-}" ] && GREEN='' && YELLOW='' && NC=''

cd "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/.."

REMOVE_VOLUMES=false
for arg in "$@"; do
  case "$arg" in
    -v|--volumes) REMOVE_VOLUMES=true ;;
    -h|--help)
      sed -n '2,10p' "$0" | sed 's/^# \{0,1\}//'
      exit 0
      ;;
    *)
      echo "Unknown argument: $arg" >&2
      echo "Try: scripts/teardown.sh --help" >&2
      exit 2
      ;;
  esac
done

if [ "$REMOVE_VOLUMES" = "true" ]; then
  echo -e "${YELLOW}This will wipe named volumes (gateway internal DB, TimescaleDB data)${NC}"
  echo -e "${YELLOW}and the local gateway's gitignored identity files.${NC}"
  if [ -t 0 ] && [ "${CI:-}" != "1" ]; then
    read -p "Continue? (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
      echo "Aborted."
      exit 0
    fi
  fi
  echo -e "${GREEN}Stopping stack and removing volumes...${NC}"
  docker compose down -v
  # Wiping the gateway volume means commissioning runs again on the next
  # boot, and leftover identity files would make it create a temp_N profile
  # instead of temp. Remove them so setup.sh's first-boot flow starts clean.
  IG=services/config/resources/core/ignition
  rm -rf "$IG/user-source" "$IG/identity-provider" \
         services/config/resources/.resources
else
  echo -e "${GREEN}Stopping stack (volumes retained)...${NC}"
  docker compose down
fi

echo -e "${GREEN}Done.${NC}"
