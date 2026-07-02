# Lab 07 — Secrets management & deploying the database with your code

Day 4 (afternoon session) of the [CI/CD for Ignition Masterclass](https://github.com/mustry-academy/cicd-masterclass), with Day 3 spillover on database deployment.

> Two gaps are left in the pipeline you built in labs 04–06: the values that must **never** be committed (passwords, API keys, tokens) and the state that isn't files at all (the **database schema** your project depends on). This lab closes both — a secrets ladder from `.env` files through Docker secrets to Ignition 8.3's native secret references, and schema migrations as versioned SQL files that ship through the same pipeline as your project. The lab closes with the **capstone brief** that ties all seven labs together.

This lab reuses the local → dev → prod gateway stack and the `db-init/` + `.env.example` conventions from [Lab 04](https://github.com/mustry-academy/cicd-lab-04-ignition-file-based-deploy) and [Lab 05](https://github.com/mustry-academy/cicd-lab-05-ignition-image-based-deploy).

## Prerequisites

- Completed (or at least run) Lab 04 — this lab assumes the file-based deploy pipeline and the three-gateway mental model
- A fork of this repo (the self-hosted runner registers against your fork, not the upstream)
- A GitHub Personal Access Token with `repo` scope — lives only in `.env`, never committed
- **≥ 8 GB free RAM for Docker** — same footprint as Lab 04 <!-- TODO: confirm final stack size; may be 2 gateways instead of 3 -->
- _Optional but recommended:_ pass [`cicd-preflight`](https://github.com/mustry-academy/cicd-preflight)

## Quick start

<!-- TODO(infra): scripts/setup.sh does not exist yet — copy + adapt from lab 04/05 once the compose stack is built. -->

```bash
gh repo clone mustry-academy/cicd-lab-07-secrets-and-db
cd cicd-lab-07-secrets-and-db
cp .env.example .env
scripts/setup.sh    # brings up the stack, waits for the gateways, prints credentials
```

> **Trial mode:** each gateway runs in 2-hour trial mode. Reset via *Gateway → Config → Licensing → Reset Trial* — unlimited and entirely legal for development.

## Lab structure

| Part | Topic | Where |
|---|---|---|
| Teaching | Secrets ladder · Ignition 8.3 secret providers · schema migrations · capstone brief | [`slides/teaching.html`](./slides/teaching.html) |
| Assignment | Warm-ups + Phase 1 (secrets) + Phase 2 (database) | [`slides/assignment.html`](./slides/assignment.html) · [`exercises/lab.md`](./exercises/lab.md) |
| Reference | The secrets approach, end to end | [`docs/secrets-management.md`](./docs/secrets-management.md) |

## Repo layout (target)

Items marked *(planned)* still have to be built — see the TODO section below.

```
cicd-lab-07-secrets-and-db/
├── README.md
├── docker-compose.yaml                 ← (planned) gateways + TimescaleDB + Flyway + runner, with Docker secrets
├── .env.example                        ← (planned) copy to .env; same convention as labs 04/05
├── secrets/                            ← (planned) gitignored dir for file-based Docker secrets (ships a .example per secret)
├── db-init/                            ← (planned) first-boot database creation (carried over from labs 04/05)
├── migrations/                         ← (planned) versioned SQL migrations (V1__…, V2__…) + repeatable seeds (R__…)
├── exercises/
│   └── lab.md                          ← the assignment, step by step
├── docs/
│   └── secrets-management.md           ← reference reading: the secrets ladder end to end
├── instructor-notes/                   ← (planned) answer keys
├── scripts/                            ← (planned) setup.sh / teardown.sh / validate.sh / migrate.sh / lib.sh
├── slides/
│   ├── teaching.html
│   └── assignment.html
└── .github/workflows/                  ← (planned) ci.yml + deploy.yml with a migration step before the gateway scan
```

## The two ideas in one paragraph each

**Secrets.** Configuration that is secret does not belong in Git — not in `docker-compose.yaml`, not in an Ignition `config.json` export, not "temporarily". The lab climbs a ladder: `.env` files interpolated by Compose (fine locally, already the labs' convention) → Docker secrets mounted as files under `/run/secrets/` (no secrets in `docker inspect` or process env) → Ignition 8.3 **secret providers**, where gateway config *references* a secret by name instead of embedding an encrypted blob that only that one gateway can decrypt. Referenced secrets are what make gateway config portable across local/dev/prod — which is the whole point of a pipeline.

**Database.** Labs 04/05 used `db-init/` — SQL that Postgres runs **once, on first volume init**. That's bootstrap, not deployment: it never runs again on an existing database. Real schema change ships as **migrations**: numbered, immutable SQL files in the repo, applied in order by a migration tool that records what already ran in a history table. The deploy workflow runs migrations against the target environment's database *in the same pipeline run* that ships the project files, so screens and schema can't drift apart.

## TODO — infra still to build

- [ ] `docker-compose.yaml` — start from lab 05's stack; add a `flyway` (or equivalent) migration service and a `secrets/` file-based Docker secrets block. <!-- TODO: decide 2 vs 3 gateways for the Day 4 timebox -->
- [ ] `.env.example` — lab-07 variant of lab 04's file (gateway creds, API keys, `RUNNER_*`, `POSTGRES_*`)
- [ ] `secrets/*.example` files + `.gitignore` rules for the real ones
- [ ] `migrations/` — `V1__baseline.sql` matching what `db-init/` creates, `V2__…` left for participants, `R__seed_reference_data.sql`
- [ ] `scripts/` — `setup.sh`, `teardown.sh`, `validate.sh` (should include a secret-scan step, e.g. gitleaks), `migrate.sh` wrapper
- [ ] `.github/workflows/deploy.yml` — lab 04's deploy plus a `migrate` job/step **before** the gateway scan
- [ ] `instructor-notes/` — answer keys for both phases
- [ ] Decide + verify the exact Ignition 8.3 secret-provider flow used in Phase 1 (provider type, UI path, how a DB connection consumes the reference) — slides currently carry `[VERIFY]` markers
- [ ] Seed a fake leaked secret in the repo history for Warm-up 2 (leak & rotate drill)
- [ ] Capstone brief: finalize scope, deliverables and rubric (teaching deck has a placeholder section)

## Licence

Apache 2.0 — see `LICENSE`. <!-- TODO: copy LICENSE file from a sibling lab -->
