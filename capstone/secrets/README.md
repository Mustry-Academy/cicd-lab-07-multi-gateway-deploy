# File-based Docker secrets

Same pattern as Lab 07's secrets ladder, rung 2: each secret is one file, the
compose file mounts it under `/run/secrets/`, and nothing shows up in
`docker inspect` or the process environment.

On the server, for each `*.example` here, create the real file next to it
(drop the `.example`) and fill it with the real value:

```bash
openssl rand -base64 24 > secrets/gateway_admin_password.txt
chmod 600 secrets/*.txt
```

The real files are gitignored. Losing the server means regenerating them —
that is intended; secrets are not backed up through git.

| Secret file | Consumed by | Purpose |
|---|---|---|
| `gateway_admin_password.txt` | `ignition` service | Gateway admin password at first-boot commissioning. Changing it later happens in the gateway UI, not here. |
| `postgres_username.txt` | `postgres` service | The course database's superuser name — the "referenced secret" of Lab 07's Part 2. Read at first boot (initdb); changing it later means SQL, not this file. |
| `postgres_password.txt` | `postgres` service | Its password. Same first-boot rule. |

The two postgres values must ALSO exist as GitHub Actions secrets
(`POSTGRES_USERNAME` / `POSTGRES_PASSWORD`) in this repo: the Deploy workflow
materializes them for the gateway's file secret provider and uses them to run
migrations. Same value, two homes — `setup.sh` generates the files AND pushes
both secrets on first bring-up (via `scripts/sync-github-secrets.sh`). For the
push to work unattended on the server, the `RUNNER_GITHUB_PAT` in `.env` needs
the fine-grained **"Secrets: Read and write"** repo permission; without it the
script prints the two `gh secret set` commands to run from a laptop.

Re-sync any time (idempotent):

```bash
capstone/scripts/sync-github-secrets.sh
```

## Rotating

**Postgres password** (the username survives rotation; it is baked into the
data volume by initdb):

```bash
# on the server, in /opt/cicd-lab-07/capstone — write IN PLACE (>): the
# compose file-secret is bind-mounted by inode, mv would detach it
openssl rand -hex 24 | tr -d '\n' > secrets/postgres_password.txt
docker exec cicd-capstone-postgres sh -c \
  'u="$(cat /run/secrets/postgres_username)"; p="$(cat /run/secrets/postgres_password)"; \
   psql -U "$u" -d ignition -c "ALTER USER \"$u\" WITH PASSWORD '\''$p'\'';"'
scripts/sync-github-secrets.sh
```

Then re-run the Deploy workflow (workflow_dispatch) so the gateway's
`/run/secrets/POSTGRES_*` files pick up the new value.

**Ignition API key:** `scripts/mint-api-key.sh` at the repo root — updates the
api-token resource and the `IGNITION_API_KEY` secret in one go, then walk the
tag + pin flow it prints.
