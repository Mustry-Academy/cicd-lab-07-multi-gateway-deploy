#!/bin/bash
# validate.sh — local mirror of .github/workflows/ci.yml.
#
# Run this before opening a PR to catch the cheap stuff the CI workflow checks,
# without waiting for a runner:
#   1. Every *.json under projects/ and services/ parses (+ project.json exists).
#   2. Module manifest ↔ third-party-modules/ agree (trust pair included).
#   3. Gateway identity resources are clean (no commissioning churn staged).
#   4. Migration pairs: every .up.sql has a .down.sql and vice versa.
#   5. release.yaml: schema + every pin points at an existing tag
#      (needs pyyaml; skipped with a warning otherwise).
#   6. capstone/secrets/ hygiene: only *.example and README tracked.
#   7. actionlint on .github/workflows/ (only if actionlint is installed).
#
# Exits non-zero if any check fails. No Ignition or Docker needed.

set -uo pipefail

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; NC='\033[0m'
[ -n "${NO_COLOR:-}" ] && RED='' && GREEN='' && YELLOW='' && NC=''

cd "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/.." || exit 1

rc=0

# 1. JSON validity sweep -------------------------------------------------------
echo "→ JSON validity sweep (projects/, services/)"
json_fail=0
while IFS= read -r f; do
  if ! python3 -m json.tool "$f" > /dev/null 2>&1; then
    echo -e "  ${RED}invalid JSON:${NC} $f"
    json_fail=1
  fi
done < <(find projects services -type f -name '*.json' 2>/dev/null)
for dir in projects/*/; do
  [ -d "$dir" ] || continue
  if [ ! -f "${dir}project.json" ]; then
    echo -e "  ${RED}missing project.json:${NC} $dir — is this a real Ignition project?"
    json_fail=1
  fi
done
if [ "$json_fail" -eq 0 ]; then
  echo -e "  ${GREEN}ok${NC} — all JSON parses"
else
  rc=1
fi

# 2. Module manifest ↔ third-party-modules/ ------------------------------------
echo "→ module manifest ↔ third-party-modules/"
if [ -f services/modules.json ]; then
  if python3 - <<'EOF'
import json, os, sys

with open("services/modules.json") as f:
    manifest = json.load(f)

errors = []
referenced = set()
for module_id, entry in manifest.items():
    filename = entry.get("filename", "")
    if not filename.startswith("/third-party-modules/"):
        continue  # gateway-bundled module, nothing to ship
    basename = os.path.basename(filename)
    referenced.add(basename)
    if not os.path.isfile(f"third-party-modules/{basename}"):
        errors.append(f"{module_id}: manifest points at {filename} but "
                      f"third-party-modules/{basename} is not in the repo")
    if entry.get("onStartup") == "enabled":
        for key in ("certFingerprint", "licenseAgreementHash"):
            if key not in entry:
                errors.append(f"{module_id}: enabled third-party module is missing "
                              f"'{key}' — the gateway will refuse to trust it")

if os.path.isdir("third-party-modules"):
    for f in os.listdir("third-party-modules"):
        if f.endswith(".modl") and f not in referenced:
            errors.append(f"third-party-modules/{f} is not registered in "
                          "services/modules.json — it would never be installed")

for e in errors:
    print(f"  {e}")
sys.exit(1 if errors else 0)
EOF
  then
    echo -e "  ${GREEN}ok${NC} — manifest and folder agree"
  else
    rc=1
  fi
else
  echo "  (no services/modules.json — skipped)"
fi

# 3. Gateway identity resources ------------------------------------------------
echo "→ gateway identity resources (commissioning churn)"
sp="services/config/resources/core/ignition/security-properties/config.json"
syp="services/config/resources/core/ignition/system-properties/config.json"
id_fail=0
if [ -f "$sp" ]; then
  grep -q '"APIKEY"' "$sp" || {
    echo -e "  ${RED}$sp:${NC} APIKEY security level is gone — run scripts/setup.sh (or git checkout the file)"; id_fail=1; }
  grep -q '"systemAuthProfile": "default"' "$sp" || {
    echo -e "  ${RED}$sp:${NC} systemAuthProfile is not default — commissioning churn"; id_fail=1; }
fi
if [ -f "$syp" ]; then
  grep -q '"systemName": "lab07-local"' "$syp" || {
    echo -e "  ${RED}$syp:${NC} systemName is not lab07-local — don't commit another gateway's rewrite"; id_fail=1; }
fi
if [ "$id_fail" -eq 0 ]; then
  echo -e "  ${GREEN}ok${NC} — identity resources are clean"
else
  rc=1
fi

# 4. Migration pairs -----------------------------------------------------------
echo "→ migration pairs (.up.sql ↔ .down.sql)"
mig_fail=0
dir="db-migration/migrate"
if [ -d "$dir" ]; then
  shopt -s nullglob
  for up in "$dir"/*.up.sql; do
    [ -f "${up%.up.sql}.down.sql" ] || {
      echo -e "  ${RED}missing pair:${NC} ${up%.up.sql}.down.sql"; mig_fail=1; }
  done
  for down in "$dir"/*.down.sql; do
    [ -f "${down%.down.sql}.up.sql" ] || {
      echo -e "  ${RED}missing pair:${NC} ${down%.down.sql}.up.sql"; mig_fail=1; }
  done
  shopt -u nullglob
  if [ "$mig_fail" -eq 0 ]; then
    echo -e "  ${GREEN}ok${NC} — every up has a down"
  else
    rc=1
  fi
else
  echo "  (no $dir — skipped)"
fi

# 5. release.yaml --------------------------------------------------------------
echo "→ release.yaml (schema + pins point at existing tags)"
if python3 -c "import yaml" > /dev/null 2>&1; then
  if python3 - <<'EOF'
import re, subprocess, sys, yaml

errors = []
try:
    with open("release.yaml") as f:
        data = yaml.safe_load(f)
except FileNotFoundError:
    print("  release.yaml is gone — it is the production state, it must exist")
    sys.exit(1)
except yaml.YAMLError as e:
    print(f"  release.yaml is not valid YAML: {e}")
    sys.exit(1)

if not isinstance(data, dict):
    print("  expected a mapping with 'gateway' and 'projects'")
    sys.exit(1)

if data.get("gateway") != "oatmakers-site-7":
    errors.append(f"gateway must be 'oatmakers-site-7', got {data.get('gateway')!r}")

projects = data.get("projects")
if not isinstance(projects, dict) or not projects:
    errors.append("'projects' must be a non-empty mapping of <project>: vX.Y.Z")
    projects = {}

tags = set(subprocess.run(["git", "tag", "--list"],
                          capture_output=True, text=True, check=True).stdout.split())

for name, version in projects.items():
    if not re.fullmatch(r"v\d+\.\d+\.\d+", str(version)):
        errors.append(f"{name}: version {version!r} must look like v1.2.3")
        continue
    if f"{name}@{version}" not in tags:
        errors.append(f"{name}: pinned {version} but tag '{name}@{version}' does not exist "
                      "(push the tag first — or fetch tags: git fetch --tags)")

for e in errors:
    print(f"  {e}")
sys.exit(1 if errors else 0)
EOF
  then
    echo -e "  ${GREEN}ok${NC} — every pin points at an existing tag"
  else
    rc=1
  fi
else
  echo -e "  ${YELLOW}skipped${NC} — pyyaml not installed (pip install pyyaml)"
fi

# 6. capstone secrets hygiene ----------------------------------------------------
echo "→ capstone/secrets/ hygiene"
bad="$(git ls-files 'capstone/secrets/' 2>/dev/null | grep -vE '\.example$|/README\.md$' || true)"
if [ -n "$bad" ]; then
  while IFS= read -r f; do
    echo -e "  ${RED}secret file committed:${NC} $f — rotate this credential NOW, then remove the file"
  done <<< "$bad"
  rc=1
else
  echo -e "  ${GREEN}ok${NC} — only example files tracked"
fi

# 7. actionlint (optional) -------------------------------------------------------
echo "→ actionlint (.github/workflows/)"
if command -v actionlint > /dev/null 2>&1; then
  if actionlint -color; then
    echo -e "  ${GREEN}ok${NC}"
  else
    rc=1
  fi
else
  echo -e "  ${YELLOW}skipped${NC} — actionlint not installed (CI runs it; install from https://github.com/rhysd/actionlint)"
fi

echo ""
if [ "$rc" -eq 0 ]; then
  echo -e "${GREEN}validate.sh: all checks passed${NC}"
else
  echo -e "${RED}validate.sh: one or more checks failed${NC}"
fi
exit "$rc"
