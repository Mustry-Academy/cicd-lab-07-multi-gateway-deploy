# capstone/ — the shared gateway, as code

Infrastructure as code for **cloud.mustrysolutions.com**: the shared, licensed
Ignition 8.3 gateway that participants of the [CI/CD for Ignition
Masterclass](https://github.com/Mustry-Academy/cicd-masterclass) deploy to in
the capstone. Operator audience (instructors run this); students, start with
[`../docs/capstone-gateway.md`](../docs/capstone-gateway.md). This directory
lives in a PUBLIC repo on purpose — the infrastructure under the capstone is
itself course material — with the security consequences handled explicitly in
[`docs/security-model.md`](docs/security-model.md).

## How it works in one paragraph

This repo is the single source of truth for the server's Docker stack. A
self-hosted GitHub Actions runner runs **inside** the stack it manages: push
to `main` and [`deploy-capstone.yml`](../.github/workflows/deploy-capstone.yml) fast-forwards the
server's clone (`/opt/cicd-lab-07`), validates the compose file, and lets
`docker compose up -d` reconcile reality with git. Rollback is `git revert` +
push. Nothing is ever edited by hand on the server except `.env` and
`secrets/` — the two things that must not be in git.

## The stack

| Service | Image | Exposure | Job |
|---|---|---|---|
| `caddy` | `caddy:2.11.4` | **80 + 443 (the only published ports)** | TLS termination with auto Let's Encrypt, reverse proxy to the gateway |
| `ignition` | `inductiveautomation/ignition:8.3.7` | none (internal network only) | The gateway. Data in the `gateway-data` named volume |
| `github-runner` | `myoung34/github-runner` | none | Applies this repo to the server; repo-scoped to this repo only |

Why only caddy publishes ports: **published Docker ports bypass UFW**, so the
firewall model is "UFW protects the host (22/80/443 allowed), and the compose
file's iron rule keeps the container attack surface at exactly caddy". See
[`docs/security-model.md`](docs/security-model.md) for the full model, and
[`docs/runbook.md`](docs/runbook.md) for every operational procedure
(bootstrap, deploy, rollback, upgrade, backup/restore, licensing, runner
re-registration, student capstone hookup).

## Quick orientation

- Deploy a change: PR -> merge to `main` -> watch the `deploy` workflow -> done.
- Roll back: `git revert <sha>` -> push. Same pipeline applies it.
- Upgrade Ignition/Caddy: bump the pinned tag in `docker-compose.yaml` via PR.
- Emergency (runner dead, can't deploy via git): SSH in, `cd /opt/cicd-lab-07/capstone`,
  fix forward with git commands + `docker compose up -d` — never by editing
  files outside git.
