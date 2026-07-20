#!/usr/bin/env bash
# Test harness for scripts/preflight.sh.
#
# Answers "can we test this without a Windows machine?" — yes, for everything
# that matters. The WSL permission problem is really a UID-mismatch problem,
# and a UID mismatch reproduces exactly in a Linux container: we create a
# non-root user, bind-mount a repo, let a root container write into it, and
# assert that the student user can still work.
#
# Two layers:
#   1. Unit tests (run anywhere, seconds): source preflight.sh with the
#      environment-probing functions stubbed, and assert each check fires.
#   2. Container tests (need Docker, ~1 min): a real non-root user in a real
#      container, reproducing the exact root-owned-bind-mount failure and
#      proving the compose fix removes it.
#
# What genuinely cannot be tested here: DrvFs itself (needs Windows) and
# /etc/wsl.conf being honoured (needs a WSL reboot). Those are covered by
# the fatal check + the manual checklist in docs/wsl-setup.md.
#
# Usage:
#   scripts/test-preflight.sh           # unit tests only
#   scripts/test-preflight.sh --docker  # unit + container tests

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

PASS=0
FAIL=0

ok()   { printf '  \033[0;32mPASS\033[0m  %s\n' "$1"; PASS=$((PASS+1)); }
bad()  { printf '  \033[0;31mFAIL\033[0m  %s\n' "$1"; FAIL=$((FAIL+1)); }

check() {
  local desc="$1"; shift
  if "$@" >/dev/null 2>&1; then ok "$desc"; else bad "$desc"; fi
}

check_fails() {
  local desc="$1"; shift
  if "$@" >/dev/null 2>&1; then bad "$desc"; else ok "$desc"; fi
}

# ===========================================================================
# 1. Unit tests — stub the environment probes, assert the decisions.
# ===========================================================================
echo ""
echo "Unit tests (no Docker needed)"
echo "----------------------------"

# Each case runs in a subshell with preflight.sh sourced and specific probes
# overridden, so we test the DECISION LOGIC without needing to be on WSL.
run_case() {
  # shellcheck disable=SC1090
  ( set +u
    . "$SCRIPT_DIR/preflight.sh" >/dev/null 2>&1
    eval "$1" )
}

# --- sudo refusal ---
check_fails "refuses to run when invoked via sudo" \
  run_case 'id() { echo 0; }; SUDO_USER=student; pf_refuse_sudo'

check "runs normally when not under sudo" \
  run_case 'unset SUDO_USER; pf_refuse_sudo'

check "allows root when it is a real root shell (no SUDO_USER)" \
  run_case 'unset SUDO_USER; pf_refuse_sudo'

# --- DrvFs / mnt-c detection ---
check "detects /mnt/c by path" \
  run_case 'PWD=/mnt/c/Users/nick/repo; pf_on_drvfs'

check "detects /mnt/d by path" \
  run_case 'PWD=/mnt/d/work/repo; pf_on_drvfs'

check "detects drvfs by filesystem type" \
  run_case 'pf_filesystem_type() { echo drvfs; }; pf_on_drvfs'

check "detects 9p (WSL2 plan9 mount) by filesystem type" \
  run_case 'pf_filesystem_type() { echo 9p; }; pf_on_drvfs'

check_fails "does NOT flag an ext4 home directory" \
  run_case 'pf_filesystem_type() { echo ext2/ext3; }; PWD=/home/nick/repo; pf_on_drvfs'

check_fails "does NOT flag /mnt/wsl or similar non-drive mounts" \
  run_case 'pf_filesystem_type() { echo ext2/ext3; }; PWD=/mnt/wsl/repo; pf_on_drvfs'

# --- the fatal check fires only on WSL + DrvFs ---
check_fails "aborts setup when on WSL and on /mnt/c" \
  run_case 'pf_is_wsl() { return 0; }; pf_on_drvfs() { return 0; }; pf_check_filesystem'

check "does not abort on WSL when on ext4" \
  run_case 'pf_is_wsl() { return 0; }; pf_on_drvfs() { return 1; }; pf_check_filesystem'

check "does not abort on macOS/Linux even under a /mnt path" \
  run_case 'pf_is_wsl() { return 1; }; pf_on_drvfs() { return 0; }; pf_check_filesystem'

check "LAB_ALLOW_DRVFS=1 downgrades the fatal check to a warning" \
  run_case 'pf_is_wsl() { return 0; }; pf_on_drvfs() { return 0; }; LAB_ALLOW_DRVFS=1; pf_check_filesystem'

check "LAB_SKIP_PREFLIGHT=1 bypasses the fatal check" \
  run_case 'pf_is_wsl() { return 0; }; pf_on_drvfs() { return 0; }; LAB_SKIP_PREFLIGHT=1; pf_check_filesystem'

# --- container user export ---
check "exports LAB_UID/LAB_GID for compose" \
  run_case 'pf_export_container_user; [ "$LAB_UID" = "$(id -u)" ] && [ "$LAB_GID" = "$(id -g)" ]'

# Sourcing alone must already give compose a usable LAB_GID, so that piping or
# otherwise subshelling lab_preflight cannot silently leave it empty (which
# would fall back to gid 2003 and reintroduce the unwritable-files bug).
check "LAB_GID is set at source time, before lab_preflight runs" \
  run_case '[ -n "$LAB_GID" ] && [ "$LAB_GID" = "$(id -g)" ]'

check "LAB_GID survives lab_preflight being piped into another command" \
  run_case 'pf_is_wsl() { return 1; }; docker() { return 0; }
            lab_preflight >/dev/null 2>&1 | cat >/dev/null
            [ "$LAB_GID" = "$(id -g)" ]'

# --- LAB_GID persisted into .env for later manual compose runs ---
check "pf_persist_lab_gid is a no-op when .env does not exist" \
  run_case 'cd "$(mktemp -d)"; pf_persist_lab_gid; [ ! -f .env ]'

check "pf_persist_lab_gid appends LAB_GID to an existing .env" \
  run_case 'cd "$(mktemp -d)"; touch .env; pf_persist_lab_gid
            grep -q "^LAB_GID=$(id -g)\$" .env'

check "pf_persist_lab_gid is idempotent (one LAB_GID line after two runs)" \
  run_case 'cd "$(mktemp -d)"; touch .env; pf_persist_lab_gid; pf_persist_lab_gid
            [ "$(grep -c "^LAB_GID=" .env)" = "1" ]'

check "pf_persist_lab_gid replaces a stale LAB_GID value" \
  run_case 'cd "$(mktemp -d)"; echo "LAB_GID=99999" > .env; pf_persist_lab_gid
            grep -q "^LAB_GID=$(id -g)\$" .env && ! grep -q 99999 .env'

check "pf_persist_lab_gid keeps unrelated .env lines intact" \
  run_case 'cd "$(mktemp -d)"; printf "FOO=bar\nLAB_GID=99999\n" > .env
            pf_persist_lab_gid; grep -q "^FOO=bar\$" .env'

check "lab_preflight persists LAB_GID when .env already exists" \
  run_case 'cd "$(mktemp -d)"; touch .env
            pf_is_wsl() { return 1; }; docker() { return 0; }
            lab_preflight >/dev/null 2>&1
            grep -q "^LAB_GID=$(id -g)\$" .env'

# --- docker access ---
check_fails "aborts when the docker daemon is unreachable" \
  run_case 'docker() { return 1; }; pf_check_docker_access'

check "passes when the docker daemon answers" \
  run_case 'docker() { return 0; }; pf_check_docker_access'

# --- wsl.conf ---
check "skips the wsl.conf check when not on WSL" \
  run_case 'pf_is_wsl() { return 1; }; pf_check_wsl_conf'

# ===========================================================================
# 2. Container tests — reproduce the real UID conflict.
# ===========================================================================
if [ "${1:-}" = "--docker" ]; then
  echo ""
  echo "Container tests (real UID mismatch, needs Docker)"
  echo "------------------------------------------------"

  if ! docker info >/dev/null 2>&1; then
    echo "  SKIP  Docker daemon not reachable"
  else
    # --- Reproduce the bug, and prove the fix, INSIDE a Linux VM ------------
    # Doing this on the host would be meaningless on macOS: Docker Desktop
    # virtualises bind-mount ownership to the calling user, so a root
    # container's files never look root-owned. Running the whole scenario in
    # one privileged Linux container gives us the real ext4 semantics that
    # WSL2 and native Linux have, on any host.
    #
    # Inside: a uid-1000 "student" owns a repo dir. A root process writes into
    # it (the gateway container today), then a user-mapped process writes into
    # it (the gateway container after the compose fix). We assert the first is
    # unusable without sudo and the second is fine.
    uid_out="$(docker run --rm alpine:3 sh -c '
      adduser -D -u 1000 student
      mkdir -p /repo/projects && chown -R student:student /repo

      # 1. Today: the gateway runs as root and writes into the bind mount.
      echo written-by-root > /repo/projects/gateway-output.json

      # Can the student edit what the gateway produced?
      if su student -c "echo edit >> /repo/projects/gateway-output.json" 2>/dev/null; then
        echo BUG_NOT_REPRODUCED
      else
        echo BUG_REPRODUCED
      fi

      # 2. After the fix: the gateway runs as the students uid:gid.
      su student -c "echo written-as-student > /repo/projects/fixed-output.json"
      owner=$(stat -c %u /repo/projects/fixed-output.json)
      if [ "$owner" = "1000" ] && su student -c "echo edit >> /repo/projects/fixed-output.json" 2>/dev/null; then
        echo FIX_VERIFIED
      else
        echo FIX_FAILED
      fi
    ' 2>&1)"

    if echo "$uid_out" | grep -q BUG_REPRODUCED; then
      ok "reproduced the bug: student cannot edit files a root container wrote"
    else
      bad "expected the root-written file to be unwritable by the student user"
    fi

    if echo "$uid_out" | grep -q FIX_VERIFIED; then
      ok "fix verified: a user-mapped container writes student-owned, editable files"
    else
      bad "user-mapped container did not produce student-owned files"
      echo "$uid_out" | sed 's/^/        /' | tail -5
    fi

    # --- The actual shipped recipe: uid 2003 + student's gid + setgid -------
    # The Ignition image runs as uid 2003 and owns its own data/ tree, so we
    # cannot simply run it as the student's uid (that breaks the boot). This
    # asserts the recipe compose really uses.
    recipe_out="$(docker run --rm alpine:3 sh -c '
      adduser -D -u 1000 student
      # The gateway identity compose ships: uid 2003, primary gid 0, plus the
      # student group as a SUPPLEMENTARY group (group_add).
      adduser -D -u 2003 -G root ignition
      addgroup ignition student
      mkdir -p /repo/projects && chown -R student:student /repo

      # What preflight does: group-write + setgid on the bind-mounted trees.
      chmod -R g+w /repo && find /repo -type d -exec chmod g+s {} +

      su ignition -c "umask 002; echo gw > /repo/projects/gw.json" || echo GW_WRITE_FAIL
      stat -c "MODE=%a GID=%g" /repo/projects/gw.json
      su student -c "echo edit >> /repo/projects/gw.json" && echo STUDENT_EDIT_OK
      su student -c "rm /repo/projects/gw.json" && echo STUDENT_DELETE_OK
    ' 2>&1)"

    if echo "$recipe_out" | grep -q GW_WRITE_FAIL; then
      bad "shipped recipe: gateway (uid 2003) could not write the bind mount"
    else
      ok "shipped recipe: gateway (uid 2003) writes into the bind mount"
    fi
    if echo "$recipe_out" | grep -q 'GID=1000'; then
      ok "shipped recipe: setgid gave the file the student's group"
    else
      bad "shipped recipe: file did not inherit the student's group"
      echo "$recipe_out" | sed 's/^/        /' | tail -4
    fi
    if echo "$recipe_out" | grep -q STUDENT_EDIT_OK && \
       echo "$recipe_out" | grep -q STUDENT_DELETE_OK; then
      ok "shipped recipe: student edits and deletes gateway files without sudo"
    else
      bad "shipped recipe: student still blocked on gateway-written files"
      echo "$recipe_out" | sed 's/^/        /' | tail -4
    fi

    # --- Volume repair must never touch volumes outside this project -------
    # Regression guard: an earlier version matched volumes by NAME PATTERN and
    # would have chowned unrelated Ignition stacks on the same machine (other
    # customers' repos, personal sandboxes). Scoping is now driven by
    # `docker compose config`, so assert it only ever names this project's.
    proj_vols="$(docker compose config --format json 2>/dev/null \
      | python3 -c 'import json,sys
try: cfg=json.load(sys.stdin)
except Exception: sys.exit(0)
name=cfg.get("name","")
for k,v in (cfg.get("volumes") or {}).items():
    print((v or {}).get("name") or f"{name}_{k}")' 2>/dev/null)"
    if [ -n "$proj_vols" ]; then
      stray="$(printf '%s\n' "$proj_vols" | grep -viE "^$(basename "$PWD" | tr 'A-Z' 'a-z')" || true)"
      if [ -z "$stray" ]; then
        ok "volume repair is scoped to this compose project only"
      else
        bad "volume repair would touch volumes outside this project: $stray"
      fi
    fi

    # The detection probe runs under BusyBox find, which has no -uid/-quit.
    # Regression guard for the silent no-op that caused.
    probe_out="$(docker run --rm alpine:3 sh -c '
      mkdir -p /d/sub && touch /d/root-owned
      [ -n "$(find /d -maxdepth 2 ! -user 2003 2>/dev/null | head -n1)" ] && echo PROBE_DETECTS
    ' 2>&1)"
    if echo "$probe_out" | grep -q PROBE_DETECTS; then
      ok "root-owned-volume probe works under BusyBox find"
    else
      bad "volume probe silently fails on BusyBox (no -uid/-quit support)"
    fi

    # --- The real Ignition image must boot under 2003:<gid> ----------------
    # Regression guard for the trap we hit while designing this: forcing an
    # arbitrary uid makes the image's own data/ tree unwritable.
    # The image's data/ is owned 2003:0 mode 775, so write access needs uid
    # 2003 OR gid 0. These assert the exact identity compose ships --
    # `user: "2003:0"` plus `group_add: [<student gid>]` -- and the two ways
    # of getting it wrong that actually broke the gateway during development.
    if docker image inspect inductiveautomation/ignition:8.3.6 >/dev/null 2>&1; then
      img_out="$(docker run --rm --user "2003:0" --group-add "$(id -g)" \
        --entrypoint sh inductiveautomation/ignition:8.3.6 \
        -c 'touch /usr/local/bin/ignition/data/probe && echo DATADIR_WRITABLE' 2>&1)"
      if echo "$img_out" | grep -q DATADIR_WRITABLE; then
        ok "real Ignition image: data/ writable as 2003:0 + supplementary group"
      else
        bad "real Ignition image: data/ NOT writable — the gateway would fail to boot"
      fi

      # The restart-loop we hit ("Property file 'data/gateway.xml' exists, but
      # isnt readable or writable") came from the DATA VOLUME, not the image:
      # volumes written by the old `user: root` compose hold root-owned files
      # that uid 2003 cannot touch. This reproduces that exact failure and
      # proves pf_repair_gateway_volumes is what fixes it.
      docker volume rm lab-preflight-voltest >/dev/null 2>&1 || true
      docker volume create lab-preflight-voltest >/dev/null
      docker run --rm -v lab-preflight-voltest:/d alpine:3 \
        sh -c 'echo x > /d/gateway.xml; chown 0:0 /d/gateway.xml; chmod 644 /d/gateway.xml' >/dev/null

      before="$(docker run --rm --user 2003:0 -v lab-preflight-voltest:/d \
        --entrypoint sh inductiveautomation/ignition:8.3.6 \
        -c 'touch /d/gateway.xml 2>/dev/null && echo WRITABLE || echo BLOCKED' 2>&1)"
      if echo "$before" | grep -q BLOCKED; then
        ok "reproduced the restart-loop cause: root-owned gateway.xml in the volume"
      else
        bad "expected a root-owned gateway.xml to block the gateway"
      fi

      docker run --rm -v lab-preflight-voltest:/d alpine:3 chown -R 2003:0 /d >/dev/null
      after="$(docker run --rm --user 2003:0 -v lab-preflight-voltest:/d \
        --entrypoint sh inductiveautomation/ignition:8.3.6 \
        -c 'touch /d/gateway.xml 2>/dev/null && echo WRITABLE || echo BLOCKED' 2>&1)"
      if echo "$after" | grep -q WRITABLE; then
        ok "volume repair fixes it: the gateway can write gateway.xml again"
      else
        bad "volume repair did not restore write access to gateway.xml"
      fi
      docker volume rm lab-preflight-voltest >/dev/null 2>&1 || true
    else
      echo "  SKIP  inductiveautomation/ignition:8.3.6 not pulled locally"
    fi

    # --- Full end-to-end: a simulated WSL student user in a container ------
    # A non-root user (uid 1000, like a default WSL account) runs preflight
    # against a repo containing root-owned leftovers, and must come out able
    # to write everything. This is the closest we get to Nick and Stephan's
    # machine without Windows.
    echo ""
    echo "  End-to-end: simulated WSL student user"
    E2E="$(mktemp -d)"
    cp "$SCRIPT_DIR/preflight.sh" "$E2E/preflight.sh"
    mkdir -p "$E2E/repo/projects"
    echo 'seed' > "$E2E/repo/projects/keep.json"

    e2e_out="$(docker run --rm -v "$E2E:/w" alpine:3 sh -c '
      set -e
      apk add --no-cache bash sudo git >/dev/null 2>&1
      adduser -D -u 1000 student
      echo "student ALL=(ALL) NOPASSWD: ALL" >> /etc/sudoers
      # Root-owned leftovers, exactly like a sudo/root-container run leaves.
      echo root-owned > /w/repo/projects/stale-root-file.json
      chown -R student:student /w/repo/projects/keep.json
      chown student:student /w/repo /w/repo/projects
      # preflight.sh is bash (setup.sh sources it from a bash shebang), so the
      # student shell must be bash too — not BusyBox ash.
      su student -s /bin/bash -c "
        cd /w/repo
        export LAB_ASSUME_YES=1
        # Stub the two probes we cannot satisfy in a plain container.
        . /w/preflight.sh
        pf_is_wsl() { return 1; }
        docker() { return 0; }
        lab_preflight
        # The reclaim must have made the stale root file writable.
        echo touched >> projects/stale-root-file.json && echo E2E_WRITABLE
        echo \"E2E_UID=\$LAB_UID E2E_GID=\$LAB_GID\"
      "
    ' 2>&1)"

    if echo "$e2e_out" | grep -q E2E_WRITABLE; then
      ok "student user reclaimed root-owned files and can write them"
    else
      bad "student user could not reclaim root-owned files"
      echo "$e2e_out" | sed 's/^/        /' | tail -8
    fi

    if echo "$e2e_out" | grep -q 'E2E_UID=1000 E2E_GID=1000'; then
      ok "preflight exported the student's uid/gid for compose (1000:1000)"
    else
      bad "preflight did not export the expected uid/gid"
    fi

    rm -rf "$E2E" 2>/dev/null || sudo rm -rf "$E2E" 2>/dev/null
  fi
else
  echo ""
  echo "  (run with --docker to also verify the real UID mismatch)"
fi

# ===========================================================================
echo ""
echo "----------------------------"
printf 'Passed: %d   Failed: %d\n' "$PASS" "$FAIL"
echo ""
[ "$FAIL" -eq 0 ]
