-- Fine live telemetry is short-lived; minute history remains capped at 90 days.
CREATE TABLE oat_demo.live_sample (LIKE oat_demo.sample INCLUDING ALL);
CREATE TABLE oat_demo.live_runtime (
 id boolean PRIMARY KEY DEFAULT true CHECK(id), watermark timestamptz,
 last_tick timestamptz, last_prune timestamptz
);
INSERT INTO oat_demo.live_runtime(id) VALUES(true);

CREATE FUNCTION oat_demo.measure_live(p_at timestamptz,p_line integer)
RETURNS TABLE(state text,total_kg numeric,good_kg numeric,energy_kwh numeric,
 temperature numeric,moisture numeric,pressure numeric)
LANGUAGE sql IMMUTABLE PARALLEL SAFE AS $$
 WITH base AS (SELECT * FROM oat_demo.measure(date_trunc('minute',p_at),p_line)),
 wave AS (SELECT sin(2*pi()*extract(second FROM p_at)/60+p_line) AS x)
 SELECT state,round((total_kg*(1+0.07*x)/12)::numeric,6),
 round((good_kg*(1+0.07*x)/12)::numeric,6),
 round((energy_kwh/12+total_kg*0.07*x*0.024/12)::numeric,6),
 round((temperature+0.8*x)::numeric,2),round((moisture+0.08*x)::numeric,2),
 round((pressure+0.03*x)::numeric,3) FROM base CROSS JOIN wave;
$$;

CREATE FUNCTION oat_demo.tick_live(p_now timestamptz DEFAULT clock_timestamp())
RETURNS jsonb LANGUAGE plpgsql AS $$
DECLARE stop_at timestamptz:=date_bin(interval '5 seconds',p_now,timestamptz '2000-01-01')-interval '5 seconds';
 start_at timestamptz; prior timestamptz; inserted integer;
BEGIN
 IF NOT pg_try_advisory_xact_lock(70831902) THEN RETURN jsonb_build_object('busy',true); END IF;
 SELECT watermark,last_tick INTO start_at,prior FROM oat_demo.live_runtime WHERE id;
 IF prior IS NOT NULL AND p_now<prior THEN RAISE EXCEPTION 'Demo clock moved backwards'; END IF;
 IF (SELECT last_tick IS NULL OR last_tick<=p_now-interval '60 seconds' FROM oat_demo.runtime WHERE id) THEN
  PERFORM oat_demo.tick(p_now);
 END IF;
 start_at:=greatest(coalesce(start_at+interval '5 seconds',stop_at-interval '48 hours'+interval '5 seconds'),
 date_bin(interval '5 seconds',p_now-interval '48 hours',timestamptz '2000-01-01')+interval '5 seconds');
 INSERT INTO oat_demo.live_sample
 SELECT t,l.id,m.* FROM generate_series(start_at,stop_at,interval '5 seconds') t
 CROSS JOIN oat_demo.line l CROSS JOIN LATERAL oat_demo.measure_live(t,l.id) m
 ON CONFLICT DO NOTHING;
 GET DIAGNOSTICS inserted=ROW_COUNT;
 DELETE FROM oat_demo.live_sample WHERE at<p_now-interval '48 hours';
 UPDATE oat_demo.live_runtime SET watermark=greatest(watermark,stop_at),last_tick=p_now,last_prune=p_now WHERE id;
 RETURN jsonb_build_object('inserted',inserted,'lastSample',stop_at);
END;
$$;

CREATE FUNCTION oat_demo.health_live(p_now timestamptz DEFAULT clock_timestamp())
RETURNS jsonb LANGUAGE sql STABLE AS $$
 WITH live AS (SELECT max(at) last_at,count(*) n FROM oat_demo.live_sample),
 runtime AS (SELECT * FROM oat_demo.live_runtime WHERE id)
 SELECT oat_demo.health(p_now) || jsonb_build_object(
  'ok',coalesce((oat_demo.health(p_now)->>'ok')::boolean AND live.last_at>=p_now-interval '30 seconds'
   AND live.last_at<=p_now AND runtime.last_tick<=p_now+interval '10 seconds',false),
  'lastTick',runtime.last_tick,'lastLiveSample',live.last_at,
  'liveAgeSeconds',round(extract(epoch FROM p_now-live.last_at)),
  'liveSampleCount',live.n,'liveRetentionHours',48,'liveIntervalSeconds',5)
 FROM live CROSS JOIN runtime;
$$;

CREATE FUNCTION oat_demo.shift_start(p_now timestamptz)
RETURNS timestamptz LANGUAGE sql IMMUTABLE AS $$
 SELECT (date_trunc('day',p_now AT TIME ZONE 'Europe/Brussels')+
 CASE WHEN extract(hour FROM p_now AT TIME ZONE 'Europe/Brussels')>=22 THEN interval '22 hours'
 WHEN extract(hour FROM p_now AT TIME ZONE 'Europe/Brussels')>=14 THEN interval '14 hours'
 WHEN extract(hour FROM p_now AT TIME ZONE 'Europe/Brussels')>=6 THEN interval '6 hours'
 ELSE interval '-2 hours' END) AT TIME ZONE 'Europe/Brussels';
$$;

CREATE FUNCTION oat_demo.live_overview(p_line integer DEFAULT 0,p_now timestamptz DEFAULT clock_timestamp())
RETURNS jsonb LANGUAGE plpgsql STABLE AS $$
DECLARE latest timestamptz; lines jsonb; trend jsonb; good numeric; rate numeric; operating integer; alerts integer; result jsonb;
BEGIN
 IF p_line NOT BETWEEN 0 AND 3 THEN RAISE EXCEPTION 'Invalid line'; END IF;
 SELECT max(at) INTO latest FROM oat_demo.live_sample;
 SELECT jsonb_agg(to_jsonb(x) ORDER BY x."lineNumber"),sum(x.rate),count(*) FILTER(WHERE x.rate>0),
 count(*) FILTER(WHERE x.state IN ('Stopped','Quality hold')) INTO lines,rate,operating,alerts FROM (
  SELECT l.id AS "lineNumber",l.name,l.product,s.state,
   round(s.total_kg*720,0) rate,round(s.temperature,1) temperature,round(s.moisture,2) moisture,
   round(s.pressure,2) pressure,round(s.energy_kwh*720,1) power,
   (extract(epoch FROM s.at)*1000)::bigint AS "updatedEpochMs",
   CASE s.state WHEN 'Stopped' THEN '#bf4945' WHEN 'Quality hold' THEN '#be8b29'
    WHEN 'Changeover' THEN '#76837b' WHEN 'Recovering' THEN '#4484b4' ELSE '#2e8862' END colour
  FROM oat_demo.line l JOIN oat_demo.live_sample s ON s.line_id=l.id AND s.at=latest
  WHERE p_line=0 OR l.id=p_line
 ) x;
 SELECT coalesce(sum(good_kg),0) INTO good FROM (
  SELECT good_kg FROM oat_demo.sample WHERE at>=oat_demo.shift_start(p_now) AND at<date_trunc('minute',p_now)
   AND (p_line=0 OR line_id=p_line)
  UNION ALL
  SELECT good_kg FROM oat_demo.live_sample WHERE at>=date_trunc('minute',p_now)
   AND at+interval '5 seconds'<=p_now AND (p_line=0 OR line_id=p_line)
 ) x;
 SELECT jsonb_agg(to_jsonb(x) ORDER BY x.ts) INTO trend FROM (
  SELECT (extract(epoch FROM at)*1000)::bigint ts,round(sum(total_kg)*720/1000,3) rate,
   round(sum(energy_kwh)*720,1) power FROM oat_demo.live_sample
  WHERE at>=p_now-interval '10 minutes' AND (p_line=0 OR line_id=p_line) GROUP BY at
 ) x;
 RETURN jsonb_build_object('ready',latest IS NOT NULL AND latest>=p_now-interval '30 seconds',
  'updatedEpochMs',coalesce((extract(epoch FROM latest)*1000)::bigint,0),
  'updatedAt',to_char(latest AT TIME ZONE 'Europe/Brussels','HH24:MI:SS'),
  'shiftStart',to_char(oat_demo.shift_start(p_now) AT TIME ZONE 'Europe/Brussels','HH24:MI'),
  'lines',coalesce(lines,'[]'),'trend',coalesce(trend,'[]'),
  'metrics',jsonb_build_array(
   jsonb_build_object('title','CURRENT THROUGHPUT','value',to_char(rate,'FM999,990'),'unit','kg/h','hint','Actual live production rate','accent','green'),
   jsonb_build_object('title','GOOD OUTPUT THIS SHIFT','value',to_char(good,'FM999,990.0'),'unit','kg','hint','Shift started at '||to_char(oat_demo.shift_start(p_now) AT TIME ZONE 'Europe/Brussels','HH24:MI'),'accent','green'),
   jsonb_build_object('title','PRODUCING LINES','value',operating::text,'unit','/ '||(CASE WHEN p_line=0 THEN 3 ELSE 1 END),'hint','Lines currently producing material','accent','blue'),
   jsonb_build_object('title','ACTIVE ALERTS','value',alerts::text,'unit','','hint','Current stops and quality alerts','accent','amber')));
END;
$$;

CREATE FUNCTION oat_demo.range_points(p_start timestamptz,p_end timestamptz,p_line integer DEFAULT 0)
RETURNS TABLE(at timestamptz,line_id integer,state text,total_kg numeric,good_kg numeric,
 energy_kwh numeric,temperature numeric,moisture numeric,pressure numeric,seconds integer)
LANGUAGE sql STABLE AS $$
 WITH use_fine AS (SELECT coalesce(p_start>=min(at),false) yes FROM oat_demo.live_sample)
 SELECT s.*,5 FROM oat_demo.live_sample s CROSS JOIN use_fine
 WHERE yes AND at>=p_start AND at+interval '5 seconds'<=p_end AND (p_line=0 OR line_id=p_line)
 UNION ALL
 SELECT s.*,60 FROM oat_demo.sample s CROSS JOIN use_fine
 WHERE NOT yes AND at>=p_start AND at+interval '1 minute'<=p_end AND (p_line=0 OR line_id=p_line);
$$;

CREATE FUNCTION oat_demo.history_range(p_start_ms bigint,p_end_ms bigint,p_line integer,p_metric text)
RETURNS jsonb LANGUAGE plpgsql STABLE AS $$
DECLARE start_at timestamptz:=to_timestamp(p_start_ms/1000.0);
 end_at timestamptz:=least(to_timestamp(p_end_ms/1000.0),statement_timestamp());
 span_s numeric; bucket interval; points jsonb; n integer;
BEGIN
 IF p_line NOT BETWEEN 0 AND 3 OR p_metric NOT IN ('rate','power','temperature','moisture','pressure') THEN RAISE EXCEPTION 'Invalid history source'; END IF;
 span_s:=extract(epoch FROM end_at-start_at);
 IF span_s<=0 OR span_s>90*86400 THEN RAISE EXCEPTION 'Choose a recorded range of at most 90 days'; END IF;
 bucket:=make_interval(secs=>greatest(5,ceil(span_s/900/5)*5)::integer);
 WITH raw AS (
  SELECT * FROM oat_demo.range_points(start_at,end_at,p_line)
 ), grouped AS (
  SELECT min(at) stamp,line_id,
   CASE p_metric WHEN 'rate' THEN sum(total_kg)*3600/nullif(sum(seconds),0)
    WHEN 'power' THEN sum(energy_kwh)*3600/nullif(sum(seconds),0)
    WHEN 'temperature' THEN avg(temperature) WHEN 'moisture' THEN avg(moisture) ELSE avg(pressure) END value
  FROM raw GROUP BY date_bin(bucket,at,timestamptz '2000-01-01'),line_id
 ), wide AS (
  SELECT (extract(epoch FROM stamp)*1000)::bigint ts,
   round(max(value) FILTER(WHERE line_id=1),3) line1,
   round(max(value) FILTER(WHERE line_id=2),3) line2,
   round(max(value) FILTER(WHERE line_id=3),3) line3
  FROM grouped GROUP BY stamp
 ) SELECT coalesce(jsonb_agg(to_jsonb(x) ORDER BY ts),'[]'),count(*) INTO points,n FROM wide x;
 RETURN jsonb_build_object('points',points,'count',n,'startEpochMs',p_start_ms,'endEpochMs',(extract(epoch FROM end_at)*1000)::bigint,
 'message',CASE WHEN n=0 THEN 'No recorded data in this range.' ELSE n||' recorded points' END);
END;
$$;

SELECT oat_demo.tick_live();
