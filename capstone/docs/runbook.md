# Runbook — cicd-capstone gateway

Every operational procedure for cloud.mustrysolutions.com. If you find
yourself doing something on the server that is not in here, either stop or
add it here afterwards.

## 1. Bootstrap (first bring-up, or rebuild after server loss)

The only manual sequence; everything afterwards flows through git.

```bash
# on the server (root) — the repo is public, no credentials needed to clone
git clone https://github.com/Mustry-Academy/cicd-lab-07-multi-gateway-deploy /opt/cicd-lab-07
cd /opt/cicd-lab-07/capstone
cp .env.example .env        # fill in RUNNER_GITHUB_PAT (or a fresh RUNNER_TOKEN)
scripts/setup.sh            # generates the admin secret, validates, compose up
```

Then: watch `docker compose logs -f caddy` until the certificate is issued,
check the runner appears under the repo's Settings -> Actions -> Runners, and
open https://cloud.mustrysolutions.com.

One credential lives in two homes: the postgres username/password that
`setup.sh` generated must also be set as GitHub Actions secrets
(`POSTGRES_USERNAME` / `POSTGRES_PASSWORD`) — the lab's Deploy workflow
materializes them for the gateway's file secret provider and runs migrations
with them. Commands in `secrets/README.md`.

Rebuild-after-loss is the same, plus a gwbk restore (§7) and license
re-activation (§8).

## 2. Deploy a change

PR -> merge to `main` -> the `deploy-capstone` workflow runs on the on-server runner:
fast-forwards `/opt/cicd-lab-07/capstone`, `docker compose config -q`,
`pull` + `up -d --remove-orphans`, then smoke-checks
`https://cloud.mustrysolutions.com/StatusPing`.

Caveat: a change to the **runner's own service** kills the runner mid-job
(after applying). The job shows "lost communication" — re-run it for a green
check. The runner survives this: its registration persists in the
`runner-state` volume and automatic deregistration is disabled.

Version rule: the runner deploys with the **host's** docker CLI + compose
plugin (bind-mounted read-only into the runner). Compose versions hash
service configs differently, so a mismatched compose sees every service as
"changed" and recreates the entire stack. Never point the deploy at a
different compose binary.

## 3. Roll back

```bash
git revert <bad-sha>   # or a range
git push origin main
```

Same workflow applies the revert. Because versions are pinned tags, an image
rollback is exactly this.

## 4. Upgrade Ignition (or Caddy)

1. PR bumping the pinned tag in `docker-compose.yaml` (check the Ignition
   release notes for data-format migrations first — gateway data migrates
   forward automatically, **never** backward; take a manual backup before a
   minor-version jump: `scripts/backup.sh`).
2. Merge. The deploy recreates the container from the new image; the
   `gateway-data` volume carries everything across.

## 4b. Changing the gateway admin password

`gwcmd.sh -p` only CLEARS the password — the gateway then boots into the
**commissioning form, served publicly**, and stays there until someone
completes it (StatusPing still says RUNNING, so health checks won't tell
you). The container's env/file-based auto-commissioning applies to fresh
installs only, not to a reset. So, in one sitting:

```bash
cd /opt/cicd-lab-07/capstone
printf '%s' 'NewPassword' > secrets/gateway_admin_password.txt   # future rebuilds
chmod 400 secrets/gateway_admin_password.txt && chown 2003:2003 secrets/gateway_admin_password.txt
docker exec cicd-capstone-gateway ./gwcmd.sh -p
docker restart cicd-capstone-gateway
# NOW: open https://cloud.mustrysolutions.com and complete the commissioning
# form with the new credentials. Do not walk away before this step.
```

TODO(infra): automate the post-reset commissioning (entrypoint-style POST to
the commissioning servlet, or a small script on the server) so a reset can
never leave the public form up.

## 5. Emergency access (runner or GitHub down)

SSH in and drive the same clone by hand — never edit files outside git:

```bash
cd /opt/cicd-lab-07
git fetch origin main && git merge --ff-only origin/main
cd capstone && docker compose up -d --remove-orphans
```

If you must hot-fix without GitHub, commit locally, and reconcile with a push
from the same clone when GitHub returns.

## 6. Backups

Nightly cron (root):

```
10 3 * * * /opt/cicd-lab-07/capstone/scripts/backup.sh >> /var/log/cicd-capstone-backup.log 2>&1
```

Drops a `.gwbk` **and** a gzipped `pg_dump` of the course database in
`/opt/cicd-lab-07/capstone/backups/`, keeps the newest 14 of each
(`gwcmd.sh -b`, verified working on the 8.3.7 image).
Off-server copies: pull one down whenever you touch the box —
`scp root@cloud.mustrysolutions.com:/opt/cicd-lab-07/capstone/backups/<latest>.gwbk ~/backups/`.

## 7. Restore from gwbk

```bash
cd /opt/cicd-lab-07/capstone
docker compose stop ignition
docker compose run --rm -v ./backups:/backups ignition -r /backups/<file>.gwbk
docker compose up -d ignition
```

(The image's `-r` flag restores on start. Verify the gateway comes up, then
check licensing — a restore onto a fresh volume needs re-activation, §8.)

Course database, from the nightly dump (fresh volumes re-run initdb from the
secret files, so credentials come back by themselves; migrations' ledger is
in the dump):

```bash
gunzip -c backups/cicd-capstone-db-<stamp>.sql.gz | docker exec -i cicd-capstone-postgres \
  sh -c 'psql -U "$(cat /run/secrets/postgres_username)" ignition'
```

## 8. Licensing

The gateway runs licensed (no trial churn for students).

- Traditional 8-digit key: activate in the gateway UI (Config -> Licensing).
  The activation lives **inside the `gateway-data` volume**. Iron rule:
  **unactivate before ever deleting that volume**, or the activation is
  burned and you're on the phone with IA support.
- Leased activation (8.3): license key + activation token as file-based
  secrets consumed by the ignition service; survives volume loss by design.

Which one this gateway uses, plus the key location: see the instructor
password manager entry "cicd-capstone gateway".

## 9. Hooking up a cohort's capstone repo (per cohort)

Students deploy with the Lab 04/06 mechanism (`docker cp` + scan API) from
their own repo, via their own runner:

1. Mint an **API token** for the scan endpoints with
   `scripts/mint-api-key.sh <gateway-container>` (installs the token on the
   gateway and prints nothing secret to disk); store the key it sets as an
   environment secret (`IGNITION_API_KEY`, environment `capstone-gateway`)
   in the cohort repo.
2. Register a **separate** runner container against the cohort repo (same
   `myoung34/github-runner` pattern; labels `self-hosted,capstone`). Add it
   as a service in this repo's compose file via PR, so it is reproducible.
3. After the cohort: delete the runner service (PR) and revoke the API token.

Students never receive: SSH access, gateway admin credentials, or anything
from this repo.

## 10. Locked out of SSH (lost key, broken sshd config)

Losing the SSH key locks you out of **sshd only**, never out of the machine.
All the hardening (`PermitRootLogin prohibit-password`,
`PasswordAuthentication no`) is enforced by the SSH daemon for connections on
port 22; local console logins don't go through sshd at all.

Recovery, in order:

1. **Contabo VNC console** — my.contabo.com -> this VPS -> VNC/emergency
   console. That is a virtual keyboard+screen on the machine itself: log in
   as `root` with the root password (stored in the instructor password
   manager, entry "cicd-capstone server root"), then fix access:
   ```bash
   # add a replacement public key
   echo "ssh-ed25519 AAAA... you@laptop" >> /root/.ssh/authorized_keys
   # or, if you broke sshd config: validate and restart
   sshd -t && systemctl restart ssh
   ```
2. **Contabo rescue system / root password reset** — also in the control
   panel. Use when the root password is lost too: reset it, or boot the
   rescue image and mount the disk.

Keep this scenario boring:

- The root password MUST exist in the password manager — the console is
  useless without it. After any password reset, update the entry.
- Prefer two independent public keys in `/root/.ssh/authorized_keys`
  (e.g. two instructors, or laptop + offline backup key), so one lost laptop
  never even needs the console.
- When changing sshd config: always `sshd -t` before restarting, and keep
  your current session open while you verify a fresh login from a second
  terminal.

## 11. Runner re-registration

With `RUNNER_GITHUB_PAT` set (normal state) the runner self-registers on
every container start — nothing to do. If the PAT was revoked/expired and the
container was recreated, either set a new fine-grained PAT in `.env`, or mint
a one-hour token from a laptop:

```bash
gh api -X POST repos/Mustry-Academy/cicd-lab-07-multi-gateway-deploy/actions/runners/registration-token --jq .token
# paste into RUNNER_TOKEN in /opt/cicd-lab-07/capstone/.env, then:
docker compose up -d github-runner
```
