# Lab 07 — Secrets management & deploying the database with your code

**Day 4 · afternoon session.** One **I do / we do / you do** covering the two things
your pipeline still can't handle: values that must never be committed, and state
that isn't files. Then the **capstone brief** closes the course.

**Duration:** ~3 hours
* 60 min teaching ([`slides/teaching.html`](../slides/teaching.html))
* 45–60 min I do / we do (demos below, woven into the teaching)
* 60 min you do ([`slides/assignment.html`](../slides/assignment.html) mirrors this file)
* Debrief + capstone Q&A

## Goal

You should leave this lab able to:

- Sort configuration into **public / per-environment / secret**, and say where each kind lives
- Explain why a secret that has ever been pushed is **burned** — and that the fix is *rotate*, not *delete*
- Climb the secrets ladder: `.env` + Compose interpolation → Docker secrets (`/run/secrets/`) → Ignition 8.3 secret providers (embedded vs **referenced**)
- Explain why *referenced* secrets make Ignition gateway config portable across environments <!-- [VERIFY] exact 8.3 behaviour of embedded ciphertext across gateways -->
- Explain why `db-init/` (labs 04/05) is bootstrap, not deployment
- Write a schema **migration** as a versioned SQL file, apply it with the migration runner, and read the history table
- Wire a migration step into `deploy.yml` so the database ships in the same pipeline run as the project files

Read-ahead: [`docs/secrets-management.md`](../docs/secrets-management.md).

## Pre-flight

<!-- TODO(infra): setup.sh / compose stack not built yet — see README TODO section. -->

```bash
cp .env.example .env
scripts/setup.sh          # idempotent — safe if the stack is already up
scripts/validate.sh       # green before you start
```

You'll need the same fork + PAT + API-key setup as Lab 04 (see its README) — the
deploy workflow in Phase 2 runs on the bundled self-hosted runner.

---

## I do (instructor demos)

### Demo 1 — a leak is forever

1. Commit a fake API key on a branch, push, then "remove" it in a follow-up commit.
2. `git log -p` / GitHub UI: the key is still perfectly readable in history.
3. Talk through the real-world response: **rotate the credential**, then (optionally) scrub history (`git filter-repo` / BFG) — and why scrubbing alone is never enough on a shared remote.

### Demo 2 — the secrets ladder on the lab stack

1. Show the `.env` → Compose interpolation the labs have used since Lab 02 (`${POSTGRES_PASSWORD:-ignition}`), and where it leaks: `docker inspect`, `docker compose config`, process env.
2. Convert one credential (the Postgres password) to a **Docker secret**: top-level `secrets:` block, file under `secrets/`, mounted at `/run/secrets/postgres_password` in the container. <!-- [VERIFY] official Ignition image `_FILE`-suffix env var support for reading secrets from files -->
3. In the Ignition gateway UI: create a **secret provider**, store the DB password there, and point the database connection at the *reference* instead of a pasted plaintext value. Export config; diff `config.json` — the secret value is not in the export. <!-- [VERIFY] exact 8.3 UI path + provider type (environment-variable vs file vs embedded) and how the reference appears in config.json -->

### Demo 3 — migrations, live

1. `db-init/` recap: rename the volume → SQL runs; existing volume → it doesn't. Bootstrap, not deployment.
2. Add `V2__add_downtime_log.sql` to `migrations/`, run `scripts/migrate.sh` against the local DB, inspect the `flyway_schema_history` table. <!-- TODO(infra): decide Flyway vs Liquibase vs hand-rolled; slides assume Flyway -->
3. Edit an already-applied migration → checksum mismatch error → the "migrations are immutable" rule, discovered live.

## We do (together)

- Walk the repo's config together and sort every value into public / per-environment / secret. <!-- TODO: worksheet or shared doc -->
- Sketch the deploy pipeline on the whiteboard and place the `migrate` step: before the file ship? after? what happens on migration failure? (Answer: migrate first, fail the run — never ship screens that need a table that isn't there.)

## You do (breakout rooms)

Follows [`slides/assignment.html`](../slides/assignment.html) 1:1.

### Warm-up 1 — secret triage
Grep your clone for candidate secrets; check `.gitignore` covers `.env` and `secrets/`; run the secret scanner in `scripts/validate.sh`. <!-- TODO(infra): gitleaks (or similar) step in validate.sh -->

### Warm-up 2 — leak & rotate drill
Repeat Demo 1 yourself on a scratch branch; convince yourself the "deleted" secret is still in history; write the two-line incident response in `NOTES.local.md` (rotate → scrub).

### Phase 1 — climb the secrets ladder (solo)
- **A.** Move the Postgres password from Compose `environment:` to a Docker secret.
- **B.** Create an Ignition secret provider and re-point the gateway DB connection at a referenced secret. Export + diff config to prove no plaintext/ciphertext left the gateway. <!-- [VERIFY] -->
- **Gate:** `scripts/validate.sh` green — includes the secret scan finding **zero** plaintext secrets in tracked files.

### Phase 2 — ship a schema change through the pipeline (solo)
- **C.** Write `V2__…` (new table for the example project), migrate locally, verify in `flyway_schema_history` and in the gateway (Perspective screen reads the new table). <!-- TODO(infra): example-project screen that consumes the table -->
- **D.** Add/enable the `migrate` step in `deploy.yml`, push to `develop` via PR, watch the run: migrate dev DB → ship files → scan → verify.

### Stretch (optional)
- **S1.** Expand–contract: rename a column with two migrations and no broken screens in between.
- **S2.** Seed data as a repeatable migration (`R__seed_reference_data.sql`) — when do repeatables re-run?
- **S3.** Add a secret-scanning job to `ci.yml` so a leaked key fails the PR.

## Debrief + capstone brief

- One surprise, one question, per room.
- **Capstone brief** (final teaching slides): the course-closing assignment that ties labs 01–07 together. <!-- TODO: finalize capstone scope, deliverables, rubric, and how/when it's reviewed -->
