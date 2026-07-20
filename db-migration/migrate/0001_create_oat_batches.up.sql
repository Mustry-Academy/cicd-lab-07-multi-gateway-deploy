-- Oat production batches: the table Tom's view reads and Gregory's
-- dashboard joins against. Seeded so the view shows rows on first deploy.
CREATE TABLE IF NOT EXISTS oat_batches (
    id          SERIAL PRIMARY KEY,
    batch_code  TEXT        NOT NULL UNIQUE,
    recipe      TEXT        NOT NULL,
    kg_in       NUMERIC(10, 2) NOT NULL,
    kg_out      NUMERIC(10, 2) NOT NULL,
    started_at  TIMESTAMPTZ NOT NULL,
    finished_at TIMESTAMPTZ
);

INSERT INTO oat_batches (batch_code, recipe, kg_in, kg_out, started_at, finished_at) VALUES
    ('OAT-2607-001', 'Rolled Classic',   1200.00, 1146.50, '2026-07-16 06:00:00+02', '2026-07-16 14:20:00+02'),
    ('OAT-2607-002', 'Instant Fine',     1000.00,  962.75, '2026-07-17 06:00:00+02', '2026-07-17 13:55:00+02'),
    ('OAT-2607-003', 'Steel Cut Coarse',  800.00,  771.20, '2026-07-18 06:00:00+02', '2026-07-18 15:05:00+02'),
    ('OAT-2607-004', 'Rolled Classic',   1200.00, 1150.10, '2026-07-19 06:00:00+02', NULL)
ON CONFLICT (batch_code) DO NOTHING;
