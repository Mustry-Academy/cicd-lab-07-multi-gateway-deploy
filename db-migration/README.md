# db-migration/migrate/

golang-migrate pairs, run against the course database (`ignition` on the
capstone's postgres) by the Deploy workflow BEFORE anything ships — a failed
migration stops the deploy.

Rules (lab 06):

- **Always pairs.** `NNNN_name.up.sql` creates, `NNNN_name.down.sql` undoes
  it. CI fails the PR if one of the two is missing.
- Numbers are the ledger order — take the next free `NNNN`, exactly like the
  release tags.
- The applied position lives in the database's `schema_migrations` table.

The database Part 2 challenge writes the first pair here (tables + seed).
