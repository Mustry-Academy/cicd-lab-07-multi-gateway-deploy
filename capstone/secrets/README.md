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
