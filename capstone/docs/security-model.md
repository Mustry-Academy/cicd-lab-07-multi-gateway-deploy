# Security model — cloud.mustrysolutions.com

Reference for operators. The box has a public IP; every decision below starts
from that fact.

## 1. Attack surface

Exactly three ports answer from the internet:

| Port | Service | Protection |
|---|---|---|
| 22 | OpenSSH | Key-only auth (passwords disabled), fail2ban, root is `prohibit-password` |
| 80 | Caddy | Redirects to 443, serves ACME challenges |
| 443 | Caddy | TLS (auto Let's Encrypt), reverse proxy to the gateway |

Everything else is dropped by UFW. **UFW does not protect published Docker
ports** (Docker inserts its own iptables rules ahead of ufw-user chains), so
the compose file carries the iron rule: no service other than caddy may
publish a port. Anything that needs host-local exposure binds to 127.0.0.1
(the pre-existing `mustry-cockpit` Postgres on 127.0.0.1:5434 is the example
already on the box). Treat any `ports:` entry in a PR to this repo as a
security review trigger.

## 2. SSH

- `PasswordAuthentication no`, `PermitRootLogin prohibit-password` via
  `/etc/ssh/sshd_config.d/00-hardening.conf`. Named `00-` deliberately: sshd
  uses the FIRST value it reads per keyword, and Ubuntu's cloud-init ships a
  `PasswordAuthentication yes` in `50-cloud-init.conf` that would otherwise
  win over a later-sorted drop-in.
- fail2ban with the default sshd jail bans brute-force sources.
- Access = your public key in the relevant `authorized_keys`. No shared
  passwords exist.

## 3. Secrets

The Lab 07 ladder, applied to ourselves:

- Nothing secret in git — mandatory now that the repo is public. The compose
  file, Caddyfile and scripts must stay shareable with the whole internet.
- Server-specific non-secrets and the runner credential live in `/opt/cicd-lab-07/capstone/.env`.
- Real secrets are file-based Docker secrets under `secrets/` (mode 600),
  surfacing only at `/run/secrets/…` inside the consuming container. Not in
  `docker inspect`, not in the environment.
- Pipeline-side secrets (gateway API token for capstone deploys) live as
  GitHub **environment** secrets in the consuming repo, course convention
  since Lab 04.

## 4. The runner is root-equivalent — and this repo is PUBLIC

The runner mounts `/var/run/docker.sock`; whoever can run a workflow on it
can do anything on the host. GitHub's own guidance is to avoid self-hosted
runners on public repos. Keeping this stack in the public course repo anyway
is a **deliberate, accepted tradeoff** (the infrastructure is course
material). That decision only stays acceptable while ALL of the following
hold:

- **Trigger discipline.** `deploy-capstone.yml` runs only on `push` to
  `main` and `workflow_dispatch` — events reserved for people with write
  access. Iron rule: **no workflow in this repo may ever combine a
  `pull_request`/`pull_request_target` trigger with the `cicd-capstone`
  runner labels.** Treat any PR that touches `.github/workflows/` as a
  security review, exactly like a `ports:` change.
- **Fork-PR approval gate.** Repo Actions settings require approval for ALL
  outside contributors before any workflow runs. Never click "Approve and
  run" on a PR you have not read — a fork PR can add or modify workflow
  files, and approval is what would let one reach the runner.
- **Read-only default token.** The default `GITHUB_TOKEN` for workflows is
  read-only; `deploy-capstone.yml` asks for nothing more.
- **Protected main.** No force pushes or branch deletion; pushing to main is
  what deploys, so main's integrity is the deployment's integrity.
- **Separate runners for students.** Student capstone repos get their own
  runner (see runbook §9) registered against the cohort repo; that runner
  gets no docker socket unless the deploy mechanism needs it. Students never
  get anything that talks to this one.
- Runner auth is a fine-grained PAT (Administration read/write on this
  single repo), stored only in the server's `.env`. Rotate it like any
  credential; revoking it does not kill an already-registered runner
  (registration persists), it only prevents self-re-registration.

## 5. The gateway

- Reachable only through Caddy over TLS; the 8088 listener never touches the
  internet.
- Licensed (no trial-reset churn), commissioned with a generated admin
  password held by instructors; students do not get gateway admin.
- Student deploys authenticate with an Ignition 8.3 **API token** scoped to
  the scan endpoints, not with the admin account.
- `GATEWAY_PUBLIC_ADDRESS` pins redirects and Designer links to the public
  hostname, so the internal address never leaks into client flows.

## 6. Patching

- Host: `unattended-upgrades` is active (Ubuntu security patches apply
  themselves).
- Containers: versions are pinned in git; patching is a PR that bumps the tag
  (visible, reviewable, revertable). The runner image is the one exception
  (`:latest` + `DISABLE_AUTO_UPDATE`, the course-wide convention).

## 7. What is deliberately NOT here

- No VPN/bastion: single box, small operator group, key-only SSH is the
  accepted bar.
- No WAF/rate limiting in front of the gateway: capstone traffic is a handful
  of students; revisit if the gateway ever holds real data.
- No secrets manager (Vault etc.): file-based secrets + GitHub environments
  match the course's own ladder and the operational scale.
