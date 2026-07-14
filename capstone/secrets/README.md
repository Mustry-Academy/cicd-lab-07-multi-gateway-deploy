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
migrations. Same value, two homes — set both when you (re)generate them:

```bash
gh secret set POSTGRES_USERNAME --repo Mustry-Academy/cicd-lab-07-multi-gateway-deploy < secrets/postgres_username.txt
gh secret set POSTGRES_PASSWORD --repo Mustry-Academy/cicd-lab-07-multi-gateway-deploy < secrets/postgres_password.txt
```
