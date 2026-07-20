#!/usr/bin/env bash
# Host preflight — WSL/permission sanity checks shared by every lab.
#
# Sourced by setup.sh BEFORE anything touches Docker or the working tree.
# Its whole job is to make sure that, by the time the gateway containers start
# writing into the bind-mounted repo, the student's own user can still read,
# edit, commit and delete every one of those files WITHOUT sudo.
#
# The four things that break this on Windows, in the order they bite:
#
#   1. The clone lives on /mnt/c (a DrvFs mount of the Windows filesystem).
#      There, the files are governed by Windows ACLs mapped through WSL's uid
#      translation. chown/chmod inside WSL do not stick, Docker bind mounts are
#      slow and lose permission bits, and running WSL as a Windows admin
#      "fixes" it only by sidestepping the ACL — which is exactly the
#      workaround two students landed on. This is FATAL: we refuse to run and
#      tell them to move the clone into the WSL filesystem (~).
#
#   2. /etc/wsl.conf has no `metadata` automount option, so DrvFs cannot store
#      a uid/gid/mode at all. Only relevant once (1) is satisfied, but we still
#      write it so a stray /mnt/c checkout of some OTHER repo behaves.
#
#   3. The containers run as root and write root-owned files into the bind
#      mount. Fixed at the source: compose now runs the gateway as the image's
#      own user with the student's group added (`user: "2003:0"` +
#      `group_add: ${LAB_GID}` — see the export below and section 3), so
#      nothing root-owned is ever created.
#
#   4. Damage already done by earlier runs (root-owned files from before this
#      fix, or from a sudo'd setup.sh) still sits in the tree. We detect it and
#      reclaim it — using sudo ONLY for that one repair, and only with consent.
#
# Env knobs:
#   LAB_SKIP_PREFLIGHT=1     skip every check (escape hatch, CI)
#   LAB_ALLOW_DRVFS=1        downgrade the /mnt/c check from fatal to a warning
#   LAB_ASSUME_YES=1         answer every prompt with "yes" (CI, automation)
#   CI=1                     non-interactive: never prompt, never sudo

# Guard against direct execution.
if [ "${BASH_SOURCE[0]}" = "${0}" ]; then
  echo "scripts/preflight.sh is meant to be sourced, not executed." >&2
  exit 1
fi

[ "${_LAB_PREFLIGHT_LOADED:-0}" = "1" ] && return 0
_LAB_PREFLIGHT_LOADED=1

# Colors — only define if the caller (lib.sh) has not already.
if [ -z "${GREEN+x}" ]; then
  if [ -t 1 ] && [ -z "${NO_COLOR:-}" ]; then
    RED=$'\033[0;31m'; GREEN=$'\033[0;32m'; YELLOW=$'\033[1;33m'; NC=$'\033[0m'
  else
    RED=''; GREEN=''; YELLOW=''; NC=''
  fi
fi

pf_is_wsl() { grep -qi microsoft /proc/version 2>/dev/null; }

pf_interactive() {
  [ "${CI:-}" != "1" ] && [ -t 0 ]
}

# Ask a yes/no question. Yes by default. Non-interactive -> use LAB_ASSUME_YES.
pf_confirm() {
  local prompt="$1"
  if [ "${LAB_ASSUME_YES:-}" = "1" ]; then return 0; fi
  if ! pf_interactive; then return 1; fi
  local reply
  read -r -p "$prompt (Y/n): " reply
  [[ ! "$reply" =~ ^[Nn] ]]
}

# ---------------------------------------------------------------------------
# 0. Refuse to run under sudo.
# ---------------------------------------------------------------------------
# If the student runs `sudo scripts/setup.sh`, every file the script creates
# (.env, gateways/, git hooks, the git config it writes) lands root-owned and
# we have manufactured tomorrow's permission problem. The scripts never need
# root: the only privileged action is the optional wsl.conf write / ownership
# repair, and those call sudo themselves, for that one command.
pf_refuse_sudo() {
  [ "${LAB_SKIP_PREFLIGHT:-}" = "1" ] && return 0
  if [ -n "${SUDO_USER:-}" ] && [ "$(id -u)" = "0" ]; then
    echo "" >&2
    echo "${RED}Do not run this script with sudo.${NC}" >&2
    echo "" >&2
    echo "Running as root makes every file it creates root-owned, which is the" >&2
    echo "cause of the permission problems sudo appears to solve. Run it as" >&2
    echo "yourself:" >&2
    echo "" >&2
    echo "    scripts/setup.sh" >&2
    echo "" >&2
    echo "If a previous sudo run already left root-owned files behind, reclaim" >&2
    echo "them first:" >&2
    echo "" >&2
    echo "    sudo chown -R ${SUDO_USER}:${SUDO_USER} ." >&2
    echo "" >&2
    exit 1
  fi
}

# ---------------------------------------------------------------------------
# 1. The clone must not live on a Windows drive mount (/mnt/c, DrvFs).
# ---------------------------------------------------------------------------
# This is the root cause behind "my Windows user conflicts with my WSL user".
# On DrvFs the Windows ACL wins, WSL's uid mapping is a translation layer over
# it, and the container's uid is a third identity that matches neither. No
# amount of chown inside WSL makes that stable — the only real fix is to keep
# the repo on the ext4 side.
pf_filesystem_type() {
  # Prefer the real filesystem type from stat; fall back to parsing mounts.
  stat -f -c %T . 2>/dev/null || {
    df -P . 2>/dev/null | awk 'NR==2 {print $1}'
  }
}

pf_on_drvfs() {
  local fstype
  fstype="$(pf_filesystem_type)"
  case "$fstype" in
    drvfs|9p|v9fs|cifs|smb*) return 0 ;;
  esac
  # Belt and braces: path-based check for the standard automount root.
  case "$PWD" in
    /mnt/[a-z]/*|/mnt/[a-z]) return 0 ;;
  esac
  return 1
}

pf_check_filesystem() {
  [ "${LAB_SKIP_PREFLIGHT:-}" = "1" ] && return 0
  pf_is_wsl || return 0
  pf_on_drvfs || return 0

  local suggested="$HOME/${PWD##*/}"
  echo "" >&2
  echo "${RED}This repo is on the Windows filesystem ($PWD).${NC}" >&2
  echo "" >&2
  echo "Under WSL that path is a DrvFs mount: file ownership is decided by" >&2
  echo "Windows ACLs, not by your WSL user. Your Windows user, your WSL user" >&2
  echo "and the container's user are three different identities there, so" >&2
  echo "chown/chmod do not stick, Docker bind mounts lose permission bits, and" >&2
  echo "the only thing that appears to work is running WSL as a Windows admin." >&2
  echo "That is a symptom, not a fix, and it makes the next lab worse." >&2
  echo "" >&2
  echo "${GREEN}Move the clone into the WSL filesystem and re-run:${NC}" >&2
  echo "" >&2
  echo "    mv \"$PWD\" \"$suggested\"" >&2
  echo "    cd \"$suggested\"" >&2
  echo "    scripts/setup.sh" >&2
  echo "" >&2
  echo "Then reopen it in VS Code with:  code \"$suggested\"" >&2
  echo "(Docker Desktop must have WSL2 integration enabled for this distro.)" >&2
  echo "" >&2

  if [ "${LAB_ALLOW_DRVFS:-}" = "1" ]; then
    echo "${YELLOW}LAB_ALLOW_DRVFS=1 set — continuing anyway. Expect permission pain.${NC}" >&2
    echo "" >&2
    return 0
  fi
  exit 1
}

# ---------------------------------------------------------------------------
# 2. /etc/wsl.conf metadata automount options.
# ---------------------------------------------------------------------------
# Only meaningful for DrvFs paths, but a student may well have another repo on
# /mnt/c. Written idempotently and without clobbering unrelated settings.
pf_check_wsl_conf() {
  [ "${LAB_SKIP_PREFLIGHT:-}" = "1" ] && return 0
  pf_is_wsl || return 0
  grep -qs metadata /etc/wsl.conf && return 0

  echo ""
  echo "${YELLOW}/etc/wsl.conf has no 'metadata' automount option.${NC}"
  echo "Without it, Windows-drive paths (/mnt/c/...) cannot store Linux file"
  echo "ownership or permissions at all."
  echo ""

  if ! pf_interactive && [ "${LAB_ASSUME_YES:-}" != "1" ]; then
    echo "Non-interactive — add this to /etc/wsl.conf yourself, then run"
    echo "'wsl --shutdown' from PowerShell:"
    echo ""
    echo "  [automount]"
    echo "  enabled = true"
    echo '  options = "metadata,umask=022,fmask=011"'
    echo ""
    return 0
  fi

  if ! pf_confirm "Write it now (needs sudo, one command)?"; then
    echo "Skipped."
    return 0
  fi

  # Append an [automount] section rather than overwriting the file: a student
  # may have [boot]/[interop]/[network] settings we must not destroy.
  if grep -qs '^\[automount\]' /etc/wsl.conf; then
    sudo sed -i 's|^\[automount\]|[automount]\nenabled = true\noptions = "metadata,umask=022,fmask=011"|' /etc/wsl.conf
  else
    printf '\n[automount]\nenabled = true\noptions = "metadata,umask=022,fmask=011"\n' \
      | sudo tee -a /etc/wsl.conf >/dev/null
  fi
  echo "${GREEN}Written.${NC} Run 'wsl --shutdown' in PowerShell, reopen your terminal,"
  echo "then run this script again."
}

# ---------------------------------------------------------------------------
# 3. Export the gid the gateway containers should run as.
# ---------------------------------------------------------------------------
# docker-compose.yaml uses this as a supplementary group:
#   user: "2003:0"  +  group_add: ["${LAB_GID:-0}"]
#
# Why 2003 and not the student's uid: the Ignition image already runs as its
# own non-root user (uid 2003, "ignition") and the image's /usr/local/bin/
# ignition/data tree is owned by it. Forcing an arbitrary host uid makes that
# tree unwritable and the gateway fails to boot — verified: the bind mount
# becomes writable but data/ does not.
#
# So we keep uid 2003 and instead join the container to the STUDENT'S GROUP.
# Combined with the group-write + setgid bits applied below, that means:
#   - the gateway can write data/ (it is still uid 2003), and
#   - everything it writes into the bind mount lands group-owned by the
#     student, mode 664/775, so the student can edit and delete it.
# No root-owned files anywhere, so no sudo, ever.
#
# Docker Desktop on macOS virtualises bind-mount ownership, so this is inert
# there; on WSL2 and native Linux it is what removes the problem.
pf_export_container_user() {
  LAB_UID="$(id -u)"
  LAB_GID="$(id -g)"
  export LAB_UID LAB_GID
}

# Persist LAB_GID into .env so MANUAL compose runs pick it up too.
#
# The export above only reaches the shell that ran setup.sh, but the labs
# legitimately tell students to run `docker compose up -d ...` themselves later
# (the lab 05 image deploy, recreating the runner, the lab 07 test profile) —
# usually from a fresh terminal where LAB_GID is unset. Compose then falls back
# to group_add 0 and, because the config hash changed, RECREATES the gateway
# without the student's group, and its writes into the bind mounts start
# failing again. Compose reads .env from the project dir on every invocation,
# so recording the value once here fixes every later manual run.
# (A real environment variable still takes precedence over .env, so the export
# above stays authoritative inside setup.sh itself.)
#
# On the first ever run .env does not exist yet when lab_preflight fires;
# setup.sh calls this again right after it creates .env.
pf_persist_lab_gid() {
  [ "${LAB_SKIP_PREFLIGHT:-}" = "1" ] && return 0
  [ -f .env ] || return 0
  local gid
  gid="$(id -g)"
  if grep -q '^LAB_GID=' .env 2>/dev/null; then
    grep -q "^LAB_GID=${gid}\$" .env && return 0
    local tmp
    tmp="$(mktemp)" || return 0
    # cat-over instead of mv: keeps .env's inode and permission bits.
    sed "s/^LAB_GID=.*/LAB_GID=${gid}/" .env > "$tmp" && cat "$tmp" > .env
    rm -f "$tmp"
  else
    {
      echo ""
      echo "# Written by scripts/preflight.sh: your group id. docker-compose joins the"
      echo "# gateway container to this group (group_add) so files it writes into the"
      echo "# bind mounts stay editable by you — also when you run 'docker compose"
      echo "# up -d' yourself from a fresh terminal. See docs/wsl-setup.md."
      echo "LAB_GID=${gid}"
    } >> .env
  fi
}

# Make the bind-mounted trees group-writable and setgid, so files the gateway
# creates inherit the student's group instead of the container's. Cheap and
# idempotent; only touches dirs that exist.
pf_prepare_bind_mounts() {
  [ "${LAB_SKIP_PREFLIGHT:-}" = "1" ] && return 0
  [ "$(uname -s)" = "Linux" ] || return 0   # inert on Docker Desktop/macOS

  local d
  for d in projects services/config gateways third-party-modules; do
    [ -d "$d" ] || continue
    chmod -R g+w "$d" 2>/dev/null || true
    find "$d" -type d -exec chmod g+s {} + 2>/dev/null || true
  done
}

# ---------------------------------------------------------------------------
# 4. Reclaim files a previous root/sudo run left behind.
# ---------------------------------------------------------------------------
# The one place we legitimately need sudo — repairing damage, with consent.
pf_reclaim_root_owned() {
  [ "${LAB_SKIP_PREFLIGHT:-}" = "1" ] && return 0
  # Docker Desktop's virtualised bind mounts on macOS make this check
  # meaningless (everything reports as the calling user anyway).
  [ "$(uname -s)" = "Linux" ] || return 0

  local me count
  me="$(id -u)"
  # -xdev: never wander into a different mount (e.g. a nested volume).
  count="$(find . -xdev ! -user "$me" -print -quit 2>/dev/null | wc -l | tr -d ' ')"
  [ "$count" = "0" ] && return 0

  echo ""
  echo "${YELLOW}Some files in this repo are not owned by you.${NC}"
  echo "They are left over from an earlier run as root (a sudo'd setup.sh, or a"
  echo "container writing as root before this fix). Examples:"
  find . -xdev ! -user "$me" -printf '  %u  %p\n' 2>/dev/null | head -5
  echo ""

  if ! command -v sudo >/dev/null 2>&1; then
    echo "${RED}sudo not available — cannot repair automatically.${NC}"
    echo "Reclaim them as root:  chown -R $(id -un):$(id -gn) $PWD"
    return 0
  fi

  if ! pf_confirm "Reclaim them with 'sudo chown -R $(id -un):$(id -gn) .'?"; then
    echo "${YELLOW}Skipped — you will likely hit permission errors during the lab.${NC}"
    return 0
  fi

  sudo chown -R "$(id -u):$(id -g)" .
  echo "${GREEN}Ownership reclaimed.${NC}"
}

# ---------------------------------------------------------------------------
# 4b. Repair named volumes left root-owned by the old `user: root` compose.
# ---------------------------------------------------------------------------
# Until this fix the gateways ran as root, so everything inside their data
# VOLUMES (gateway.xml, the internal db, var/) is owned 0:0. Now that the
# gateway runs as 2003:0 it can no longer write those files and dies on boot
# with: "Property file 'data/gateway.xml' exists, but isnt readable or
# writable."
#
# Students who ran ANY earlier version of the lab have such volumes on disk, so
# this is not a corner case — it is the upgrade path. Fix it by chowning the
# volume contents to the uid the gateway now runs as. Done in a throwaway
# root container, so it needs no sudo on the host.
pf_repair_gateway_volumes() {
  [ "${LAB_SKIP_PREFLIGHT:-}" = "1" ] && return 0
  command -v docker >/dev/null 2>&1 || return 0

  # Scope STRICTLY to the volumes this compose project declares. Matching on a
  # name pattern instead would sweep up unrelated Ignition stacks on the same
  # machine (other customers' repos, personal sandboxes) and chown their data —
  # destructive and completely outside this lab's business.
  local vols vol
  vols="$(docker compose config --format json 2>/dev/null \
          | python3 -c 'import json,sys
try:
    cfg = json.load(sys.stdin)
except Exception:
    sys.exit(0)
name = cfg.get("name", "")
for key, v in (cfg.get("volumes") or {}).items():
    # Respect an explicit external/custom name; otherwise compose prefixes it.
    print((v or {}).get("name") or f"{name}_{key}")' 2>/dev/null || true)"
  [ -z "$vols" ] && return 0

  local repaired=0
  for vol in $vols; do
    # Only Ignition gateway volumes: a database volume (timescaledb/postgres)
    # has its own uid and must NOT be chowned to the Ignition user.
    case "$vol" in
      *timescale*|*postgres*|*mssql*|*db-data*) continue ;;
    esac
    docker volume inspect "$vol" >/dev/null 2>&1 || continue

    # Does it hold files the gateway (uid 2003) cannot write?
    # NOTE: this runs under BusyBox find (alpine), which has no -uid and no
    # -quit — use -user with a numeric id and cap the output with head.
    if docker run --rm -v "$vol:/d" alpine:3 \
         sh -c '[ -n "$(find /d -maxdepth 2 ! -user 2003 2>/dev/null | head -n1)" ]' \
         >/dev/null 2>&1; then
      if [ "$repaired" = "0" ]; then
        echo ""
        echo "${YELLOW}Repairing gateway data volumes left root-owned by an earlier run.${NC}"
        echo "(The gateway no longer runs as root, so it cannot write those files.)"
      fi
      docker run --rm -v "$vol:/d" alpine:3 chown -R 2003:0 /d >/dev/null 2>&1 \
        && { echo "  repaired: $vol"; repaired=$((repaired+1)); } \
        || echo "  ${RED}could not repair: $vol${NC}"
    fi
  done
  [ "$repaired" -gt 0 ] && echo ""
  return 0
}

# ---------------------------------------------------------------------------
# 5. Docker must be reachable without sudo.
# ---------------------------------------------------------------------------
# On a native/WSL Linux install where the user is not in the docker group, the
# obvious "fix" is again sudo — which then runs compose as root and root-owns
# every generated file. Catch it here and point at the real fix.
pf_check_docker_access() {
  [ "${LAB_SKIP_PREFLIGHT:-}" = "1" ] && return 0
  docker info >/dev/null 2>&1 && return 0

  echo "" >&2
  echo "${RED}Cannot talk to the Docker daemon as $(id -un).${NC}" >&2
  echo "" >&2
  if pf_is_wsl; then
    echo "On Windows this usually means Docker Desktop is not running, or WSL" >&2
    echo "integration is off for this distro:" >&2
    echo "  Docker Desktop -> Settings -> Resources -> WSL integration" >&2
    echo "  -> enable your distro -> Apply & restart." >&2
  else
    echo "Add yourself to the docker group (then log out and back in):" >&2
    echo "" >&2
    echo "    sudo usermod -aG docker $(id -un)" >&2
    echo "    newgrp docker" >&2
  fi
  echo "" >&2
  echo "${YELLOW}Do not work around this with 'sudo docker' or 'sudo scripts/setup.sh'${NC}" >&2
  echo "${YELLOW}— that root-owns your repo files and breaks the rest of the lab.${NC}" >&2
  echo "" >&2
  exit 1
}

# ---------------------------------------------------------------------------
# Git hygiene on WSL: ignore the executable-bit noise DrvFs invents.
# ---------------------------------------------------------------------------
pf_configure_git() {
  [ "${LAB_SKIP_PREFLIGHT:-}" = "1" ] && return 0
  git rev-parse --git-dir >/dev/null 2>&1 || return 0
  if pf_is_wsl; then
    git config core.fileMode false
  fi
  # Git 2.35.2+ refuses to operate on a repo owned by another user. After the
  # reclaim above this is normally moot, but a repo cloned from Windows can
  # still trip it.
  git status >/dev/null 2>&1 || {
    git config --global --add safe.directory "$PWD" 2>/dev/null || true
  }
}

# ---------------------------------------------------------------------------
# Fallback: make LAB_GID valid the moment this file is sourced.
# ---------------------------------------------------------------------------
# lab_preflight exports LAB_GID for docker-compose.yaml, but an export only
# reaches the caller if the function runs in THIS shell. Piping it
# (`lab_preflight | tee`) or backgrounding it silently drops the export, and
# compose would then fall back to gid 2003 and write files the student cannot
# edit — the exact bug we are fixing, reintroduced invisibly.
# Setting it at source time means the value is always correct even if someone
# later wraps the call.
LAB_UID="$(id -u)"; LAB_GID="$(id -g)"; export LAB_UID LAB_GID

# ---------------------------------------------------------------------------
# Entry point — run every check in dependency order.
# ---------------------------------------------------------------------------
# Call it plainly: `lab_preflight`. Do NOT pipe it — see the note above.
lab_preflight() {
  pf_refuse_sudo
  pf_check_filesystem      # fatal on /mnt/c — nothing below can fix that
  pf_check_wsl_conf
  pf_check_docker_access
  pf_export_container_user
  pf_persist_lab_gid         # no-op on the first run (.env not created yet)
  pf_reclaim_root_owned
  pf_repair_gateway_volumes  # upgrade path from the old `user: root` compose
  pf_prepare_bind_mounts     # after the reclaim: needs to own the files first
  pf_configure_git
}
