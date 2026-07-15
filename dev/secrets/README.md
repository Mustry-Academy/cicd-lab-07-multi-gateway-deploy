# dev/secrets — local stand-ins for the referenced secrets

These are NOT secrets. They are the documented local-dev defaults for the
compose stack in the repo root, committed on purpose so the same
referenced-secret configuration works in both places:

| File | Local value | On production |
|---|---|---|
| `POSTGRES_USERNAME` | `ignition` (the local postgres login) | Materialized by the Deploy workflow from the GitHub secret |
| `POSTGRES_PASSWORD` | `lab07-postgres-pw` | Same |

The compose file mounts this folder at `/run/secrets/` inside the local
gateway — the exact path the gateway's file-type secret provider reads on
cloud.mustrysolutions.com. A database connection that references the secret
`POSTGRES_USERNAME` therefore resolves on your laptop AND on production,
each against its own database.

Real secrets never go in this folder. Production values live as GitHub
Actions secrets and in the server's gitignored `capstone/secrets/`.
