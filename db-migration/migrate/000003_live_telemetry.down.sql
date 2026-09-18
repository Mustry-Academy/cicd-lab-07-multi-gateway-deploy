DROP FUNCTION IF EXISTS oat_demo.history_range(bigint,bigint,integer,text);
DROP FUNCTION IF EXISTS oat_demo.range_points(timestamptz,timestamptz,integer);
DROP FUNCTION IF EXISTS oat_demo.live_overview(integer,timestamptz);
DROP FUNCTION IF EXISTS oat_demo.shift_start(timestamptz);
DROP FUNCTION IF EXISTS oat_demo.health_live(timestamptz);
DROP FUNCTION IF EXISTS oat_demo.tick_live(timestamptz);
DROP FUNCTION IF EXISTS oat_demo.measure_live(timestamptz,integer);
DROP TABLE IF EXISTS oat_demo.live_runtime,oat_demo.live_sample;
