-- Isolated, deterministic demonstration data. No customer or plant records.
CREATE SCHEMA IF NOT EXISTS oat_demo;
CREATE TABLE oat_demo.line (
 id integer PRIMARY KEY, name text NOT NULL, product text NOT NULL,
 nominal_kg_min numeric NOT NULL CHECK(nominal_kg_min > 0)
);
INSERT INTO oat_demo.line VALUES (1,'Rolling line 01','Rolled oats',32),
 (2,'Cutting line 02','Steel-cut oats',25),(3,'Milling line 03','Oat flour',21);
CREATE TABLE oat_demo.sample (
 at timestamptz NOT NULL, line_id integer NOT NULL REFERENCES oat_demo.line,
 state text NOT NULL, total_kg numeric NOT NULL, good_kg numeric NOT NULL,
 energy_kwh numeric NOT NULL, temperature numeric NOT NULL,
 moisture numeric NOT NULL, pressure numeric NOT NULL,
 PRIMARY KEY(at,line_id), CHECK(good_kg >= 0 AND good_kg <= total_kg),
 CHECK(total_kg >= 0 AND energy_kwh >= 0)
);
CREATE INDEX ON oat_demo.sample(line_id,at);
CREATE TABLE oat_demo.runtime (
 id boolean PRIMARY KEY DEFAULT true CHECK(id), last_tick timestamptz,
 watermark timestamptz, last_prune timestamptz, revision integer NOT NULL DEFAULT 1
);
INSERT INTO oat_demo.runtime(id) VALUES(true);
CREATE TABLE oat_demo.operator_order (
 request_id uuid PRIMARY KEY, created_at timestamptz NOT NULL DEFAULT now(),
 reference text NOT NULL CHECK(length(reference) BETWEEN 1 AND 40),
 product text NOT NULL CHECK(product IN ('Rolled oats','Steel-cut oats','Oat flour')),
 quantity_kg numeric NOT NULL CHECK(quantity_kg > 0 AND quantity_kg <= 100000),
 bags integer NOT NULL CHECK(bags > 0 AND bags <= 10000),
 mode text NOT NULL CHECK(mode IN ('Trial','Production','Hold')),
 source text NOT NULL DEFAULT 'Operator demo'
);
CREATE INDEX ON oat_demo.operator_order(created_at);
CREATE TABLE oat_demo.inspection (
 batch_reference text PRIMARY KEY, checked_at timestamptz NOT NULL DEFAULT clock_timestamp(),
 decision text NOT NULL, peak_moisture numeric NOT NULL, temperature numeric NOT NULL
);
CREATE INDEX ON oat_demo.inspection(checked_at);


CREATE FUNCTION oat_demo.measure(p_at timestamptz, p_line integer)
RETURNS TABLE(state text,total_kg numeric,good_kg numeric,energy_kwh numeric,
 temperature numeric,moisture numeric,pressure numeric)
LANGUAGE sql IMMUTABLE PARALLEL SAFE AS $$
 WITH clock AS (
  SELECT floor(extract(epoch FROM p_at)/60)::bigint AS m,
   (ARRAY[32,25,21])[p_line]::numeric AS nominal
 ), stage AS (
  SELECT *, ((m % 120)+120)%120 AS phase FROM clock
 ), process AS (
  SELECT *, CASE
   WHEN p_line=1 AND phase BETWEEN 15 AND 29 THEN 'Stopped'
   WHEN p_line=2 AND phase BETWEEN 35 AND 49 THEN 'Quality hold'
   WHEN p_line=1 AND phase BETWEEN 50 AND 64 THEN 'Recovering'
   WHEN p_line=3 AND phase BETWEEN 95 AND 99 THEN 'Changeover'
   ELSE 'Running' END AS state,
   (0.88+0.05*sin(m/19.0+p_line)+0.025*cos(m/173.0))::numeric AS speed
  FROM stage
 ), production AS (
  SELECT *, round(nominal * CASE WHEN state IN ('Stopped','Changeover') THEN 0
   WHEN state='Recovering' THEN 0.55+0.025*(phase-50) ELSE speed END,3) AS kg
  FROM process
 )
 SELECT state, kg,
  round((kg * CASE WHEN state='Quality hold' THEN 0.86 ELSE 0.984+0.009*sin(m/29.0+p_line) END)::numeric,3),
  round((0.17+kg*0.024)::numeric,3),
  round((CASE WHEN state='Stopped' THEN 58 ELSE 82 END + 2.3*sin(m/13.0+p_line))::numeric,2),
  round((CASE WHEN state='Quality hold' THEN 14.1 ELSE 11.4 END+0.35*sin(m/17.0+p_line))::numeric,2),
  round((CASE WHEN state='Stopped' THEN 0.2 ELSE 2.4 END+0.1*cos(m/11.0))::numeric,2)
 FROM production;
$$;

-- A single transaction and advisory lock make overlapping timers/reloads safe.
-- Generation is bounded to the retained window, even after a long outage.
CREATE FUNCTION oat_demo.tick(p_now timestamptz DEFAULT clock_timestamp())
RETURNS jsonb LANGUAGE plpgsql AS $$
DECLARE
 stop_at timestamptz := date_trunc('minute',p_now);
 cutoff timestamptz := greatest(p_now-interval '90 days',p_now-interval '3 months');
 start_at timestamptz;
 n integer := 0;
 removed integer := 0;
 old_tick timestamptz;
BEGIN
 IF NOT pg_try_advisory_xact_lock(70831901) THEN
  RETURN jsonb_build_object('busy',true);
 END IF;
 SELECT watermark,last_tick INTO start_at,old_tick FROM oat_demo.runtime WHERE id;
 -- Never delete future data or move the watermark back if the clock regresses.
 IF old_tick IS NOT NULL AND p_now < old_tick THEN
  RAISE EXCEPTION 'Demo clock moved backwards';
 END IF;
 start_at := greatest(coalesce(start_at+interval '1 minute',date_trunc('minute',cutoff)+interval '1 minute'),
                      date_trunc('minute',cutoff)+interval '1 minute');
 INSERT INTO oat_demo.sample
 SELECT t,l.id,m.* FROM generate_series(start_at,stop_at,interval '1 minute') t
 CROSS JOIN oat_demo.line l CROSS JOIN LATERAL oat_demo.measure(t,l.id) m
 ON CONFLICT DO NOTHING;
 GET DIAGNOSTICS n = ROW_COUNT;
 DELETE FROM oat_demo.sample WHERE at < cutoff;
 GET DIAGNOSTICS removed = ROW_COUNT;
 INSERT INTO oat_demo.operator_order(request_id,created_at,reference,product,quantity_kg,bags,mode,source)
 SELECT md5('scheduled:'||extract(epoch FROM t)::bigint||':'||l.id)::uuid,t,
  'DEMO-'||to_char(t AT TIME ZONE 'Europe/Brussels','YYYYMMDDHH24')||'-'||l.id,
  l.product,l.nominal_kg_min*240,ceil(l.nominal_kg_min*240/25)::integer,'Production','Scheduled demo'
 FROM generate_series(date_trunc('day',p_now)-interval '7 days',stop_at,interval '6 hours') t
 CROSS JOIN oat_demo.line l ON CONFLICT(request_id) DO NOTHING;
 DELETE FROM oat_demo.operator_order WHERE created_at < cutoff;
 DELETE FROM oat_demo.inspection WHERE checked_at < cutoff;
 UPDATE oat_demo.runtime SET last_tick=p_now,watermark=stop_at,last_prune=p_now WHERE id;
 RETURN jsonb_build_object('inserted',n,'pruned',removed,'watermark',stop_at);
END;
$$;

CREATE FUNCTION oat_demo.health(p_now timestamptz DEFAULT clock_timestamp())
RETURNS jsonb LANGUAGE sql STABLE AS $$
 WITH bounds AS (SELECT min(at) AS first_at,max(at) AS last_at,count(*) AS samples,
 count(DISTINCT line_id) AS lines FROM oat_demo.sample),
 r AS (SELECT * FROM oat_demo.runtime WHERE id)
 SELECT jsonb_build_object('ok',coalesce(r.last_tick >= p_now-interval '3 minutes'
 AND r.last_tick <= p_now+interval '10 seconds'
 AND b.last_at <= date_trunc('minute',p_now)
 AND b.last_at >= date_trunc('minute',p_now)-interval '2 minutes'
 AND b.first_at >= greatest(p_now-interval '90 days',p_now-interval '3 months')-interval '1 minute'
 AND b.samples > 100000 AND b.lines=3,false),
 'simulation',true,'retentionDays',90,'retentionPolicy','At most 90 days or three calendar months',
 'sampleCount',b.samples,'lineCount',b.lines,'firstSample',b.first_at,'lastSample',b.last_at,
 'lastTick',r.last_tick,'lastPrune',r.last_prune,'revision',r.revision,
 'ageSeconds',round(extract(epoch FROM p_now-b.last_at)),
 'coverageDays',round(extract(epoch FROM b.last_at-b.first_at)/86400,1))
 FROM bounds b CROSS JOIN r;
$$;

-- Replay times always refer to a complete historical cycle, relative to now.
CREATE FUNCTION oat_demo.replay_clock(p_now timestamptz,p_scene text)
RETURNS timestamptz LANGUAGE sql IMMUTABLE AS $$
 SELECT CASE WHEN p_scene='live' THEN date_trunc('minute',p_now)
 ELSE to_timestamp(floor(extract(epoch FROM p_now)/7200)*7200-7200+
  CASE p_scene WHEN 'stoppage' THEN 20*60 WHEN 'quality' THEN 40*60
   WHEN 'recovery' THEN 60*60 ELSE 0 END) END;
$$;

-- Initial history is available before the new screens are deployed.
SELECT oat_demo.tick();
