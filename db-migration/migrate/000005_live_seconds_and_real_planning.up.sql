-- Two changes the demonstration screens depend on.
--
-- 1. Live telemetry moves from a five-second grid to a one-second grid, so the
--    factory overview and the SCADA faceplates advance every second. One second
--    over 48 hours is half a million rows for no benefit, so the fine window is
--    six hours; anything longer already falls back to the minute history.
--
-- 2. The production plan stops being three identical rows of back-to-back
--    six-hour blocks. Each line now runs its own repeating pattern of batch
--    lengths separated by changeover and CIP windows, the patterns have
--    different cycle lengths so the lines drift apart instead of marching in
--    step, and the unplanned stops already present in the telemetry are
--    published as their own timeline entries.

-- ---------------------------------------------------------------- live, at 1 Hz
CREATE OR REPLACE FUNCTION oat_demo.measure_live(p_at timestamptz,p_line integer)
RETURNS TABLE(state text,total_kg numeric,good_kg numeric,energy_kwh numeric,
 temperature numeric,moisture numeric,pressure numeric)
LANGUAGE sql IMMUTABLE PARALLEL SAFE AS $$
 -- A minute of modelled production split into 60 one-second slices. The wave
 -- keeps a full turn per minute, so consecutive seconds visibly differ.
 WITH base AS (SELECT * FROM oat_demo.measure(date_trunc('minute',p_at),p_line)),
 wave AS (SELECT sin(2*pi()*extract(second FROM p_at)/60+p_line) AS x)
 SELECT state,round((total_kg*(1+0.07*x)/60)::numeric,6),
 round((good_kg*(1+0.07*x)/60)::numeric,6),
 round((energy_kwh/60+total_kg*0.07*x*0.024/60)::numeric,6),
 round((temperature+0.8*x)::numeric,2),round((moisture+0.08*x)::numeric,2),
 round((pressure+0.03*x)::numeric,3) FROM base CROSS JOIN wave;
$$;

CREATE OR REPLACE FUNCTION oat_demo.tick_live(p_now timestamptz DEFAULT clock_timestamp())
RETURNS jsonb LANGUAGE plpgsql AS $$
DECLARE stop_at timestamptz:=date_bin(interval '1 second',p_now,timestamptz '2000-01-01')-interval '1 second';
 start_at timestamptz; prior timestamptz; inserted integer;
BEGIN
 IF NOT pg_try_advisory_xact_lock(70831902) THEN RETURN jsonb_build_object('busy',true); END IF;
 SELECT watermark,last_tick INTO start_at,prior FROM oat_demo.live_runtime WHERE id;
 IF prior IS NOT NULL AND p_now<prior THEN RAISE EXCEPTION 'Demo clock moved backwards'; END IF;
 IF (SELECT last_tick IS NULL OR last_tick<=p_now-interval '60 seconds' FROM oat_demo.runtime WHERE id) THEN
  PERFORM oat_demo.tick(p_now);
 END IF;
 -- Never backfill more than the retained window, however long the gateway was down.
 start_at:=greatest(coalesce(start_at+interval '1 second',stop_at-interval '6 hours'+interval '1 second'),
 date_bin(interval '1 second',p_now-interval '6 hours',timestamptz '2000-01-01')+interval '1 second');
 INSERT INTO oat_demo.live_sample
 SELECT t,l.id,m.* FROM generate_series(start_at,stop_at,interval '1 second') t
 CROSS JOIN oat_demo.line l CROSS JOIN LATERAL oat_demo.measure_live(t,l.id) m
 ON CONFLICT DO NOTHING;
 GET DIAGNOSTICS inserted=ROW_COUNT;
 DELETE FROM oat_demo.live_sample WHERE at<p_now-interval '6 hours';
 UPDATE oat_demo.live_runtime SET watermark=greatest(watermark,stop_at),last_tick=p_now,last_prune=p_now WHERE id;
 RETURN jsonb_build_object('inserted',inserted,'lastSample',stop_at);
END;
$$;

-- Each fine row now covers one second, which is what the rate arithmetic divides by.
CREATE OR REPLACE FUNCTION oat_demo.range_points(p_start timestamptz,p_end timestamptz,p_line integer DEFAULT 0)
RETURNS TABLE(at timestamptz,line_id integer,state text,total_kg numeric,good_kg numeric,
 energy_kwh numeric,temperature numeric,moisture numeric,pressure numeric,seconds integer)
LANGUAGE sql STABLE AS $$
 WITH use_fine AS (SELECT coalesce(p_start>=min(at),false) yes FROM oat_demo.live_sample)
 SELECT s.*,1 FROM oat_demo.live_sample s CROSS JOIN use_fine
 WHERE yes AND at>=p_start AND at+interval '1 second'<=p_end AND (p_line=0 OR line_id=p_line)
 UNION ALL
 SELECT s.*,60 FROM oat_demo.sample s CROSS JOIN use_fine
 WHERE NOT yes AND at>=p_start AND at+interval '1 minute'<=p_end AND (p_line=0 OR line_id=p_line);
$$;

CREATE OR REPLACE FUNCTION oat_demo.health_live(p_now timestamptz DEFAULT clock_timestamp())
RETURNS jsonb LANGUAGE sql STABLE AS $$
 WITH live AS (SELECT max(at) last_at,count(*) n FROM oat_demo.live_sample),
 runtime AS (SELECT * FROM oat_demo.live_runtime WHERE id)
 SELECT oat_demo.health(p_now) || jsonb_build_object(
  'ok',coalesce((oat_demo.health(p_now)->>'ok')::boolean AND live.last_at>=p_now-interval '15 seconds'
   AND live.last_at<=p_now AND runtime.last_tick<=p_now+interval '10 seconds',false),
  'lastTick',runtime.last_tick,'lastLiveSample',live.last_at,
  'liveAgeSeconds',round(extract(epoch FROM p_now-live.last_at)),
  'liveSampleCount',live.n,'liveRetentionHours',6,'liveIntervalSeconds',1)
 FROM live CROSS JOIN runtime;
$$;

-- The five-second rows already banked would be weighted as one-second rows and
-- inflate every rate until they aged out. The next tick refills the window.
TRUNCATE oat_demo.live_sample;
UPDATE oat_demo.live_runtime SET watermark=NULL,last_tick=NULL WHERE id;

-- Live faceplate colours: greyscale while a line is healthy, colour only when an
-- operator needs to look. Green-for-running is the opposite of what a
-- high-performance HMI asks for.
CREATE OR REPLACE FUNCTION oat_demo.state_colour(p_state text)
RETURNS text LANGUAGE sql IMMUTABLE AS $$
 SELECT CASE p_state
  WHEN 'Stopped' THEN '#b23b34' WHEN 'Quality hold' THEN '#b57a17'
  WHEN 'Recovering' THEN '#4a6f96' WHEN 'Changeover' THEN '#7d8891'
  ELSE '#4d5862' END;
$$;

CREATE OR REPLACE FUNCTION oat_demo.live_overview(p_line integer DEFAULT 0,p_now timestamptz DEFAULT clock_timestamp())
RETURNS jsonb LANGUAGE plpgsql STABLE AS $$
DECLARE latest timestamptz; lines jsonb; trend jsonb; good numeric; rate numeric; operating integer; alerts integer;
BEGIN
 IF p_line NOT BETWEEN 0 AND 3 THEN RAISE EXCEPTION 'Invalid line'; END IF;
 SELECT max(at) INTO latest FROM oat_demo.live_sample;
 SELECT jsonb_agg(to_jsonb(x) ORDER BY x."lineNumber"),sum(x.rate),count(*) FILTER(WHERE x.rate>0),
 count(*) FILTER(WHERE x.state IN ('Stopped','Quality hold')) INTO lines,rate,operating,alerts FROM (
  SELECT l.id AS "lineNumber",l.name,l.product,s.state,
   round(s.total_kg*3600,0) rate,round(s.temperature,1) temperature,round(s.moisture,2) moisture,
   round(s.pressure,2) pressure,round(s.energy_kwh*3600,1) power,
   (extract(epoch FROM s.at)*1000)::bigint AS "updatedEpochMs",
   oat_demo.state_colour(s.state) colour
  FROM oat_demo.line l JOIN oat_demo.live_sample s ON s.line_id=l.id AND s.at=latest
  WHERE p_line=0 OR l.id=p_line
 ) x;
 SELECT coalesce(sum(good_kg),0) INTO good FROM (
  SELECT good_kg FROM oat_demo.sample WHERE at>=oat_demo.shift_start(p_now) AND at<date_trunc('minute',p_now)
   AND (p_line=0 OR line_id=p_line)
  UNION ALL
  SELECT good_kg FROM oat_demo.live_sample WHERE at>=date_trunc('minute',p_now)
   AND at+interval '1 second'<=p_now AND (p_line=0 OR line_id=p_line)
 ) x;
 SELECT jsonb_agg(to_jsonb(x) ORDER BY x.ts) INTO trend FROM (
  SELECT (extract(epoch FROM at)*1000)::bigint ts,round(sum(total_kg)*3600/1000,3) rate,
   round(sum(energy_kwh)*3600,1) power FROM oat_demo.live_sample
  WHERE at>=p_now-interval '10 minutes' AND (p_line=0 OR line_id=p_line) GROUP BY at
 ) x;
 RETURN jsonb_build_object('ready',latest IS NOT NULL AND latest>=p_now-interval '15 seconds',
  'updatedEpochMs',coalesce((extract(epoch FROM latest)*1000)::bigint,0),
  'updatedAt',to_char(latest AT TIME ZONE 'Europe/Brussels','HH24:MI:SS'),
  'shiftStart',to_char(oat_demo.shift_start(p_now) AT TIME ZONE 'Europe/Brussels','HH24:MI'),
  'lines',coalesce(lines,'[]'),'trend',coalesce(trend,'[]'),
  'metrics',jsonb_build_array(
   jsonb_build_object('title','CURRENT THROUGHPUT','value',to_char(rate,'FM999,990'),'unit','kg/h','hint','Actual live production rate'),
   jsonb_build_object('title','GOOD OUTPUT THIS SHIFT','value',to_char(good,'FM999,990.0'),'unit','kg','hint','Shift started at '||to_char(oat_demo.shift_start(p_now) AT TIME ZONE 'Europe/Brussels','HH24:MI')),
   jsonb_build_object('title','PRODUCING LINES','value',operating::text,'unit','/ '||(CASE WHEN p_line=0 THEN 3 ELSE 1 END),'hint','Lines currently producing material'),
   jsonb_build_object('title','ACTIVE ALERTS','value',alerts::text,'unit','','hint','Current stops and quality alerts')));
END;
$$;

-- ------------------------------------------------------------- the actual plan
-- Each line keeps its own repeating rhythm of batches and the windows between
-- them. The cycle lengths are deliberately co-prime-ish, so line 1 and line 3
-- never settle into the same phase and the board stops looking ruled.
ALTER TABLE oat_demo.line ADD COLUMN IF NOT EXISTS plan_offset_minutes integer NOT NULL DEFAULT 0;
UPDATE oat_demo.line SET plan_offset_minutes = CASE id WHEN 1 THEN 0 WHEN 2 THEN 155 ELSE 310 END;

CREATE TABLE IF NOT EXISTS oat_demo.line_plan (
 line_id integer NOT NULL REFERENCES oat_demo.line,
 slot integer NOT NULL,
 run_minutes integer NOT NULL CHECK(run_minutes BETWEEN 60 AND 1440),
 gap_minutes integer NOT NULL CHECK(gap_minutes BETWEEN 0 AND 720),
 gap_kind text NOT NULL CHECK(gap_kind IN ('changeover','cip','maintenance')),
 PRIMARY KEY(line_id,slot)
);
TRUNCATE oat_demo.line_plan;
INSERT INTO oat_demo.line_plan(line_id,slot,run_minutes,gap_minutes,gap_kind) VALUES
 (1,1,300,45,'changeover'),(1,2,420,30,'cip'),(1,3,360,75,'maintenance'),
 (2,1,240,60,'changeover'),(2,2,480,40,'cip'),(2,3,300,95,'maintenance'),
 (3,1,390,35,'changeover'),(3,2,270,80,'cip'),(3,3,450,50,'changeover');

-- Every planned batch overlapping a window, with its own start, length and the
-- window that follows it.
CREATE OR REPLACE FUNCTION oat_demo.plan_batches(p_from timestamptz,p_to timestamptz,p_line integer DEFAULT 0)
RETURNS TABLE(line_id integer,reference text,starts timestamptz,ends timestamptz,
 gap_minutes integer,gap_kind text)
LANGUAGE sql STABLE AS $$
 WITH cycle AS (
  SELECT p.line_id,p.slot,p.run_minutes,p.gap_minutes,p.gap_kind,
   sum(p.run_minutes+p.gap_minutes) OVER (PARTITION BY p.line_id)::integer AS cycle_minutes,
   coalesce(sum(p.run_minutes+p.gap_minutes) OVER (PARTITION BY p.line_id ORDER BY p.slot
     ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING),0)::integer AS slot_offset
  FROM oat_demo.line_plan p
 ), span AS (
  SELECT c.*,l.plan_offset_minutes,
   floor(extract(epoch FROM p_from-timestamptz '2020-01-05 06:00:00+01')/(c.cycle_minutes*60))::integer-1 AS c_min,
   floor(extract(epoch FROM p_to  -timestamptz '2020-01-05 06:00:00+01')/(c.cycle_minutes*60))::integer+1 AS c_max
  FROM cycle c JOIN oat_demo.line l ON l.id=c.line_id
  WHERE p_line=0 OR c.line_id=p_line
 )
 SELECT s.line_id,'OM-'||to_char(g.st,'YYYYMMDDHH24')||'-'||s.line_id,
  g.st,g.st+make_interval(mins=>s.run_minutes),s.gap_minutes,s.gap_kind
 FROM span s
 CROSS JOIN generate_series(s.c_min,s.c_max) AS k
 CROSS JOIN LATERAL (SELECT timestamptz '2020-01-05 06:00:00+01'
   +make_interval(mins=>s.plan_offset_minutes+s.slot_offset+k*s.cycle_minutes) AS st) g
 WHERE g.st<p_to AND g.st+make_interval(mins=>s.run_minutes)>p_from;
$$;

-- A planned batch joined to what the line actually recorded while it ran.
CREATE OR REPLACE FUNCTION oat_demo.batch_rows(p_from timestamptz,p_to timestamptz,p_line integer DEFAULT 0)
RETURNS jsonb LANGUAGE sql STABLE AS $$
 SELECT coalesce(jsonb_agg(to_jsonb(x) ORDER BY x."startEpochMs",x."lineNumber"),'[]') FROM (
  SELECT b.reference,l.id AS "lineNumber",l.id::text AS "resourceId",l.name line,l.product,
   l.product||' · '||b.reference title,
   to_char(b.starts,'YYYY-MM-DD"T"HH24:MI:SSOF') AS start,
   to_char(b.ends,'YYYY-MM-DD"T"HH24:MI:SSOF') AS "end",
   (extract(epoch FROM b.starts)*1000)::bigint AS "startEpochMs",
   (extract(epoch FROM b.ends)*1000)::bigint AS "endEpochMs",
   round(extract(epoch FROM b.ends-b.starts)/60)::integer AS "plannedMinutes",
   b.gap_minutes AS "followedByMinutes",b.gap_kind AS "followedByKind",
   coalesce(a.produced,0) AS produced_kg,coalesce(a.good,0) AS good_kg,
   round(l.nominal_kg_min*extract(epoch FROM b.ends-b.starts)/60) AS target_kg,
   a.temperature,a.moisture,a.peak AS peak_moisture,a.yield,
   coalesce(a.stopped_minutes,0) AS stopped_minutes,
   CASE WHEN b.starts>now() THEN 'Scheduled' WHEN b.ends>now() THEN 'In production'
    WHEN a.peak>13 THEN 'Quality review' ELSE 'Completed' END AS status,
   CASE WHEN b.starts>now() THEN 'planned' WHEN b.ends>now() THEN 'running'
    WHEN a.peak>13 THEN 'quality' ELSE 'complete' END AS category,
   CASE WHEN b.starts>now() THEN 'Awaiting production' WHEN a.peak>13 THEN 'Review required'
    ELSE 'Released' END quality
  FROM oat_demo.plan_batches(p_from,p_to,p_line) b
  JOIN oat_demo.line l ON l.id=b.line_id
  LEFT JOIN LATERAL (
   SELECT round(sum(s.total_kg),1) produced,round(sum(s.good_kg),1) good,
    round(avg(s.temperature),1) temperature,round(avg(s.moisture),2) moisture,
    round(max(s.moisture),2) peak,round(100*sum(s.good_kg)/nullif(sum(s.total_kg),0),1) yield,
    count(*) FILTER(WHERE s.state='Stopped') stopped_minutes
   FROM oat_demo.sample s
   WHERE s.line_id=b.line_id AND s.at>=b.starts AND s.at<least(b.ends,now())
  ) a ON true
 ) x;
$$;

-- Unplanned stops, quality holds and changeovers, read back out of the same
-- telemetry the rest of the screens use rather than invented for the board.
CREATE OR REPLACE FUNCTION oat_demo.downtime_events(p_from timestamptz,p_to timestamptz,p_line integer DEFAULT 0)
RETURNS jsonb LANGUAGE sql STABLE AS $$
 WITH marked AS (
  SELECT at,line_id,state,
   at-make_interval(mins=>(row_number() OVER (PARTITION BY line_id,state ORDER BY at))::integer) AS grp
  FROM oat_demo.sample
  WHERE at>=p_from-interval '3 hours' AND at<least(p_to,now()) AND state<>'Running'
    AND (p_line=0 OR line_id=p_line)
 ), runs AS (
  SELECT line_id,state,min(at) starts,max(at)+interval '1 minute' ends
  FROM marked GROUP BY line_id,state,grp
  HAVING max(at)-min(at)>=interval '3 minutes' AND max(at)+interval '1 minute'>p_from
 )
 SELECT coalesce(jsonb_agg(to_jsonb(x) ORDER BY x."startEpochMs"),'[]') FROM (
  SELECT 'DT-'||(extract(epoch FROM r.starts)*1000)::bigint||'-'||r.line_id AS reference,
   r.line_id AS "lineNumber",r.line_id::text AS "resourceId",l.name line,r.state,
   CASE r.state WHEN 'Stopped' THEN 'Unplanned stop · infeed blockage'
    WHEN 'Quality hold' THEN 'Quality hold · moisture above 13%'
    WHEN 'Recovering' THEN 'Controlled ramp-up after stop'
    ELSE 'Changeover in progress' END AS title,
   CASE r.state WHEN 'Stopped' THEN 'stop' WHEN 'Quality hold' THEN 'quality'
    ELSE 'changeover' END AS category,
   to_char(r.starts,'YYYY-MM-DD"T"HH24:MI:SSOF') AS start,
   to_char(r.ends,'YYYY-MM-DD"T"HH24:MI:SSOF') AS "end",
   (extract(epoch FROM r.starts)*1000)::bigint AS "startEpochMs",
   (extract(epoch FROM r.ends)*1000)::bigint AS "endEpochMs",
   round(extract(epoch FROM r.ends-r.starts)/60)::integer AS minutes,
   true AS "isDowntime"
  FROM runs r JOIN oat_demo.line l ON l.id=r.line_id
 ) x;
$$;

-- The batch list keeps returning batches only; the board gets its own function so
-- stops and changeovers never leak into the quality grid.
CREATE OR REPLACE FUNCTION oat_demo.batches_range(p_start_ms bigint,p_end_ms bigint,p_line integer DEFAULT 0)
RETURNS jsonb LANGUAGE plpgsql STABLE AS $$
DECLARE start_at timestamptz:=to_timestamp(p_start_ms/1000.0);end_at timestamptz:=to_timestamp(p_end_ms/1000.0);
BEGIN
 IF end_at<=start_at OR end_at-start_at>interval '91 days' OR p_line NOT BETWEEN 0 AND 3 THEN
  RAISE EXCEPTION 'Invalid planning window'; END IF;
 RETURN oat_demo.batch_rows(greatest(start_at,now()-interval '90 days'),least(end_at,now()+interval '7 days'),p_line);
END;
$$;

CREATE OR REPLACE FUNCTION oat_demo.timeline_range(p_start_ms bigint,p_end_ms bigint,p_line integer DEFAULT 0)
RETURNS jsonb LANGUAGE plpgsql STABLE AS $$
DECLARE start_at timestamptz:=to_timestamp(p_start_ms/1000.0);end_at timestamptz:=to_timestamp(p_end_ms/1000.0);
 lo timestamptz; hi timestamptz;
BEGIN
 IF end_at<=start_at OR end_at-start_at>interval '91 days' OR p_line NOT BETWEEN 0 AND 3 THEN
  RAISE EXCEPTION 'Invalid planning window'; END IF;
 lo:=greatest(start_at,now()-interval '90 days');hi:=least(end_at,now()+interval '7 days');
 RETURN oat_demo.batch_rows(lo,hi,p_line)||oat_demo.downtime_events(lo,hi,p_line);
END;
$$;

CREATE OR REPLACE FUNCTION oat_demo.batch_detail(p_reference text)
RETURNS jsonb LANGUAGE plpgsql STABLE AS $$
DECLARE stamp timestamptz; line_no integer; result jsonb;
BEGIN
 IF p_reference !~ '^OM-[0-9]{10}-[123]$' THEN RAISE EXCEPTION 'Invalid demo batch reference'; END IF;
 stamp:=to_timestamp(substring(p_reference,4,10),'YYYYMMDDHH24');line_no:=right(p_reference,1)::integer;
 IF stamp<now()-interval '90 days' OR stamp>now()+interval '7 days' THEN
  RETURN jsonb_build_object('reference',p_reference,'available',false,'message','This batch is outside the retained demonstration window.');
 END IF;
 -- A batch starts anywhere inside the hour its reference names, so look across
 -- that hour rather than assuming a fixed six-hour block.
 SELECT value INTO result FROM jsonb_array_elements(
  oat_demo.batch_rows(stamp,stamp+interval '1 hour',line_no)) WHERE value->>'reference'=p_reference;
 RETURN coalesce(result,'{}')||jsonb_build_object('available',result IS NOT NULL,
  'inspection',(SELECT jsonb_build_object('checkedAt',to_char(checked_at AT TIME ZONE 'Europe/Brussels','DD Mon HH24:MI'),'decision',decision) FROM oat_demo.inspection WHERE batch_reference=p_reference));
END;
$$;

-- Fill the one-second window now, so the screens have data the moment the
-- deploy lands rather than waiting on the gateway's first timer tick.
SELECT oat_demo.tick_live();
