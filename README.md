# Lab 07 — Deployments in a multi-gateway architecture

Day 4 (afternoon) of the [CI/CD for Ignition Masterclass](https://github.com/mustry-academy/cicd-masterclass).

> The capstone. For once you do **not** fork: everyone works as a **contributor on this one shared, locked-down repo**. Every push to `main` auto-deploys to your **own test gateway**; only a change to `release.yaml` reaches the **real production gateway on the internet**. Feature branch → PR → review → tag → release pin → live, again and again, with four other people in the same version stream.

Two deploy channels, one rule: `release.yaml` is the **only** production trigger. Each pin is a git tag `<project>@vX.Y.Z` that must exist before the file may point at it — CI enforces that on the PR. Rollback is `git revert` of the release PR.

## Prerequisites

- Accept the **contributor invite** (check your GitHub notifications) — no fork
- Docker with the Compose V2 plugin, `git`, `curl`, `python3`
- **≥ 4 GB free RAM for Docker** — one Ignition gateway (1 GB cap) plus TimescaleDB
- _Background:_ labs 03–06 — the runner, tags, secrets ladder, migrations and module moves all return here, wired into one pipeline

## Quick start

```bash
git clone git@github.com:Mustry-Academy/cicd-lab-07-multi-gateway-deploy.git
cd cicd-lab-07-multi-gateway-deploy
scripts/setup.sh       # compose up + one-time first-boot fix, idempotent
scripts/validate.sh    # local mirror of CI — green before you PR
```

| Service | URL | Login |
|---|---|---|
| local gateway | http://localhost:8088 | `admin` / `password` — bind-mounted from `./projects/` + `./services/config/` |
| local database | localhost:5432 | `ignition` / `lab07-postgres-pw`, database `ignition` |
| **production** | https://cloud.mustrysolutions.com | shared team gateway — deploys land here via `release.yaml` only |

The local gateway bind-mounts the repo: a save in the Designer lands in your
working tree, so `git status` is your export step. Tear down with
`scripts/teardown.sh` (add `--volumes` for a factory reset, then re-run
`scripts/setup.sh`).

> **Trial mode:** the local gateway runs in 2-hour trial mode. Reset via *Gateway → Config → Licensing → Reset Trial* — unlimited and entirely legal for development.

## Lab structure

[`exercises/lab.md`](./exercises/lab.md) is the source of truth; [`slides/assignment.html`](./slides/assignment.html) mirrors it:

| Part | Topic | Gate |
|---|---|---|
| 0 (±15 min) | Stand up your personal test gateway: second clone, provided runner + gateway pair, your own `test-<yourname>.yml` on your runner label | a dashboard change lands on your test gateway on its own after a merge to `main` |
| 1 (±20 min) | Your own project through the full loop: PR → review → `<yourname>@v1.0.0` tag → `release.yaml` pin | your view live on production |
| 2 (±35 min) | Five challenges on the shared oatmakers project — module, JAR, migration + referenced secret, simulator tags, history | your challenge live via an `oatmakers@v2.0.X` tag you cut |
| 3 (extra) | Build on each other's work; small PRs, rebases, real merge conflicts | a merged PR that uses someone else's Part 2 work |

Reference reading: [`docs/multi-gateway-deployments.md`](./docs/multi-gateway-deployments.md) — the full teaching content (architectures, release files, promotion as a PR, repo layouts).

## Repo layout

```
cicd-lab-07-multi-gateway-deploy/
├── release.yaml               ← what runs on production, right now (the ONLY deploy trigger)
├── projects/                  ← oatmakers (shared) + one project per contributor
├── services/                  ← gateway config export + modules.json manifest
├── third-party-modules/       ← .modl files the pipeline installs
├── jar-files/jar/             ← library JARs → lib/core/gateway at deploy time
├── db-migration/migrate/      ← golang-migrate up/down pairs, run before anything ships
├── dev/                       ← local-only stand-ins (secrets) for the dev stack
├── capstone/                  ← the production server stack (Caddy, gateway, runner) — GitOps'd
├── scripts/                   ← setup / teardown / validate / migrate / mint-api-key
├── exercises/ · slides/ · docs/ · architectures/
└── .github/workflows/         ← ci.yml (PR checks) · deploy.yml (release.yaml → production)
```

## License

[Apache 2.0](./LICENSE) — © 2026 Mustry Solutions BV.
