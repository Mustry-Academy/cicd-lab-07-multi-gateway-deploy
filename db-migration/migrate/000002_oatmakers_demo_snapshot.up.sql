CREATE FUNCTION oat_demo.snapshot(p_scene text DEFAULT 'live',p_period text DEFAULT 'day',p_line integer DEFAULT 0,p_batch text DEFAULT '')
RETURNS jsonb LANGUAGE plpgsql STABLE AS $$
DECLARE
 wall timestamptz := statement_timestamp();
 finish timestamptz;
 begin_at timestamptz;
 span interval;
 bucket interval;
 payload jsonb;
 metrics jsonb;
 lines jsonb;
 trend jsonb;
 orders jsonb;
 losses jsonb;
 events jsonb;
 quality jsonb;
 totals record;
 fresh timestamptz;
 batch_options jsonb;
 selected jsonb;
 planning jsonb;
 inspection jsonb;
 health_state jsonb;
BEGIN
 IF p_scene NOT IN ('live','stoppage','quality','recovery') OR p_period NOT IN ('shift','day','week','month') OR p_line NOT BETWEEN 0 AND 3 THEN
  RAISE EXCEPTION 'Invalid demonstration filter';
 END IF;
 finish := oat_demo.replay_clock(wall,p_scene);
 span := CASE p_period WHEN 'shift' THEN interval '8 hours' WHEN 'week' THEN interval '7 days' WHEN 'month' THEN interval '30 days' ELSE interval '24 hours' END;
 bucket := CASE p_period WHEN 'shift' THEN interval '15 minutes' WHEN 'week' THEN interval '4 hours' WHEN 'month' THEN interval '1 day' ELSE interval '1 hour' END;
 begin_at := finish-span;
 SELECT last_tick INTO fresh FROM oat_demo.runtime WHERE id;
 SELECT sum(s.total_kg) total, sum(s.good_kg) good, sum(s.energy_kwh) energy,
  sum(l.nominal_kg_min) planned, count(*) n,
  count(*) FILTER(WHERE s.state NOT IN ('Stopped','Changeover')) running,
  sum(l.nominal_kg_min) FILTER(WHERE s.state NOT IN ('Stopped','Changeover')) running_plan,
  avg(s.moisture) moisture, avg(s.temperature) temperature
 INTO totals FROM oat_demo.sample s JOIN oat_demo.line l ON s.line_id=l.id
 WHERE s.at>begin_at AND s.at<=finish AND (p_line=0 OR s.line_id=p_line);
 IF totals.n=0 THEN
  RETURN jsonb_build_object('ready',false,'message','The simulator is preparing history. Refresh shortly.');
 END IF;
 metrics := jsonb_build_array(
  jsonb_build_object('title','GOOD OUTPUT','value',to_char(totals.good/1000,'FM9999990.0'),'unit','t','hint',to_char(totals.planned/1000,'FM9999990.0')||' t planned','accent','green'),
  jsonb_build_object('title','OVERALL EFFECTIVENESS','value',round(100*totals.good/nullif(totals.planned,0),1)::text,'unit','%','hint','Availability x performance x quality','accent','green'),
  jsonb_build_object('title','QUALITY YIELD','value',round(100*totals.good/nullif(totals.total,0),1)::text,'unit','%','hint',to_char(totals.total-totals.good,'FM9999990')||' kg rejected','accent','amber'),
  jsonb_build_object('title','ENERGY INTENSITY','value',round(totals.energy/nullif(totals.good/1000,0),1)::text,'unit','kWh/t','hint',to_char(totals.energy,'FM9999990')||' kWh consumed','accent','blue')
 );
 SELECT coalesce(jsonb_agg(to_jsonb(x) ORDER BY x.id),'[]') INTO lines FROM (
  SELECT l.id,l.name,l.product,s.state,
   to_char(s.total_kg*60,'FM999990')||' kg/h' throughput,
   to_char(s.temperature,'FM990.0')||' C' temperature,
   to_char(s.moisture,'FM990.0')||' %' moisture,
   to_char(s.pressure,'FM990.0')||' bar' pressure,
   to_char(s.energy_kwh*60,'FM990.0')||' kW' power,
   CASE s.state WHEN 'Stopped' THEN '#b34335' WHEN 'Quality hold' THEN '#b87517' WHEN 'Changeover' THEN '#6f7780' WHEN 'Recovering' THEN '#367ab6' ELSE '#357a5b' END colour,
   'OM-'||to_char(date_bin(interval '6 hours',s.at,timestamptz '2020-01-01'),'YYYYMMDDHH24')||'-'||l.id AS batch
  FROM oat_demo.line l JOIN LATERAL (
   SELECT * FROM oat_demo.sample WHERE line_id=l.id AND at<=finish ORDER BY at DESC LIMIT 1
  ) s ON true WHERE p_line=0 OR l.id=p_line
 ) x;
 SELECT coalesce(jsonb_agg(to_jsonb(x) ORDER BY x.ts),'[]') INTO trend FROM (
  SELECT (extract(epoch FROM date_bin(bucket,at,timestamptz '2020-01-01'))*1000)::bigint ts,
   round(sum(total_kg)*60/nullif(count(DISTINCT at),0)/1000,3) total,round(sum(good_kg)*60/nullif(count(DISTINCT at),0)/1000,3) good,
   round(sum(energy_kwh)*60/nullif(count(DISTINCT at),0),1) energy,round(avg(temperature),2) temperature,
   round(avg(moisture),2) moisture
  FROM oat_demo.sample WHERE at>begin_at AND at<=finish AND (p_line=0 OR line_id=p_line)
  GROUP BY 1
 ) x;
 WITH grouped AS (
  SELECT date_bin(interval '6 hours',s.at,timestamptz '2020-01-01') started,l.id,l.name,l.product,
   round(sum(s.total_kg),0) total,round(sum(s.good_kg),0) good,
   round(avg(s.moisture),2) moisture,max(s.moisture) maximum_moisture,
   round(avg(s.temperature),1) temperature,
   round(100*sum(s.good_kg)/nullif(sum(s.total_kg),0),1) yield,
   l.nominal_kg_min*360 target
  FROM oat_demo.sample s JOIN oat_demo.line l ON l.id=s.line_id
  WHERE s.at>=date_bin(interval '6 hours',finish-interval '3 days',timestamptz '2020-01-01')
   AND s.at<=finish AND (p_line=0 OR s.line_id=p_line)
  GROUP BY 1,l.id,l.name,l.product,l.nominal_kg_min
 ), records AS (
  SELECT 'OM-'||to_char(started,'YYYYMMDDHH24')||'-'||id reference,
   name line,product,to_char(started AT TIME ZONE 'Europe/Brussels','DD Mon HH24:MI') started,
   total AS produced_kg,good AS good_kg,target AS target_kg,
   CASE WHEN grouped.started+interval '6 hours'>finish THEN 'In production'
    WHEN maximum_moisture>13 THEN 'Quality review' ELSE 'Completed' END status,
   moisture,round(maximum_moisture,2) AS peak_moisture,temperature,yield,
   CASE WHEN maximum_moisture>13 THEN 'Review required' ELSE 'Released' END quality,
   grouped.started AS sort_time
  FROM grouped
 ) SELECT jsonb_agg(to_jsonb(x)-'sort_time' ORDER BY sort_time DESC,line) INTO orders
 FROM (SELECT * FROM records ORDER BY sort_time DESC,line LIMIT 24) x;
 SELECT coalesce(jsonb_agg(to_jsonb(x)),'[]') INTO losses FROM (
  SELECT CASE state WHEN 'Running' THEN 'Speed and quality losses' ELSE state END AS reason,count(*) AS minutes,
   round(sum(l.nominal_kg_min-s.good_kg),0) AS lost_kg
  FROM oat_demo.sample s JOIN oat_demo.line l ON l.id=s.line_id
  WHERE at>begin_at AND at<=finish AND (p_line=0 OR line_id=p_line)
  GROUP BY state ORDER BY lost_kg DESC
 ) x;
 WITH edges AS (
  SELECT at,line_id,state,lag(state) OVER(PARTITION BY line_id ORDER BY at) previous
  FROM oat_demo.sample WHERE at>finish-interval '12 hours' AND at<=finish AND (p_line=0 OR line_id=p_line)
 ) SELECT coalesce(jsonb_agg(to_jsonb(x)-'sort_time' ORDER BY sort_time DESC),'[]') INTO events FROM (
  SELECT to_char(e.at AT TIME ZONE 'Europe/Brussels','DD Mon HH24:MI') time,l.name AS line,e.state,
   CASE e.state WHEN 'Stopped' THEN 'Infeed blockage detected' WHEN 'Quality hold' THEN 'Moisture above 13% limit'
    WHEN 'Recovering' THEN 'Controlled ramp-up after maintenance' WHEN 'Changeover' THEN 'Recipe change in progress'
    ELSE 'Production resumed' END description,e.at sort_time
  FROM edges e JOIN oat_demo.line l ON l.id=e.line_id
  WHERE previous IS DISTINCT FROM state AND previous IS NOT NULL
  ORDER BY e.at DESC LIMIT 12
 ) x;
 SELECT jsonb_agg(jsonb_build_object('label',x->>'reference','value',x->>'reference')) INTO batch_options
 FROM jsonb_array_elements(coalesce(orders,'[]')) x;
 SELECT x INTO selected FROM jsonb_array_elements(coalesce(orders,'[]')) x
 WHERE x->>'reference'=p_batch LIMIT 1;
 selected := coalesce(selected,orders->0,'{}');
 SELECT coalesce(jsonb_agg(to_jsonb(x) ORDER BY x.started),'[]') INTO planning FROM (
  SELECT 'OM-'||to_char(t,'YYYYMMDDHH24')||'-'||l.id reference,l.name line,l.product,
   to_char(t AT TIME ZONE 'Europe/Brussels','DD Mon HH24:MI') started,
   0 AS produced_kg,l.nominal_kg_min*360 target_kg,'Scheduled'::text status
  FROM generate_series(date_bin(interval '6 hours',finish,timestamptz '2020-01-01')+interval '6 hours',finish+interval '24 hours',interval '6 hours') t
  CROSS JOIN oat_demo.line l WHERE p_line=0 OR l.id=p_line
 ) x;
 SELECT jsonb_agg(value ORDER BY CASE value->>'status' WHEN 'In production' THEN 0 WHEN 'Scheduled' THEN 1 ELSE 2 END, ordinality)
 INTO planning FROM jsonb_array_elements(planning || coalesce(orders,'[]')) WITH ORDINALITY;
 SELECT jsonb_build_object('checkedAt',to_char(checked_at AT TIME ZONE 'Europe/Brussels','DD Mon HH24:MI'),
  'decision',decision,'peakMoisture',peak_moisture,'temperature',temperature) INTO inspection
 FROM oat_demo.inspection WHERE batch_reference=selected->>'reference';
 quality := jsonb_build_array(
  jsonb_build_object('measurement','Peak moisture during batch','value',selected->>'peak_moisture','unit','%','specification','<= 13.0','result',CASE WHEN (selected->>'peak_moisture')::numeric<=13 THEN 'Within limits' ELSE 'Review required' END),
  jsonb_build_object('measurement','Average moisture','value',selected->>'moisture','unit','%','specification','10.5 - 13.0','result',CASE WHEN (selected->>'moisture')::numeric BETWEEN 10.5 AND 13 THEN 'Within limits' ELSE 'Review required' END),
  jsonb_build_object('measurement','Average process temperature','value',selected->>'temperature','unit','C','specification','55.0 - 86.0','result',CASE WHEN (selected->>'temperature')::numeric BETWEEN 55 AND 86 THEN 'Within limits' ELSE 'Review required' END),
  jsonb_build_object('measurement','First-pass yield','value',selected->>'yield','unit','%','specification','>= 97.0','result',CASE WHEN (selected->>'yield')::numeric>=97 THEN 'Within limits' ELSE 'Review required' END)
 );
 health_state := oat_demo.health(wall);
 RETURN jsonb_build_object('ready',true,'simulated',true,'message',CASE WHEN NOT coalesce((health_state->>'ok')::boolean,false) THEN 'Data is stale or inconsistent. The simulator needs attention.' WHEN p_scene<>'live' THEN 'Replay of stored demo data. Choose Live production to return to current values.' ELSE 'Simulation running. Updates every minute.' END,
  'stale',NOT coalesce((health_state->>'ok')::boolean,false),'scenario',p_scene,
  'clock',to_char(finish AT TIME ZONE 'Europe/Brussels','DD Mon YYYY HH24:MI'),
  'window',to_char(begin_at AT TIME ZONE 'Europe/Brussels','DD Mon HH24:MI')||' to '||to_char(finish AT TIME ZONE 'Europe/Brussels','DD Mon HH24:MI')||' Brussels',
  'metrics',metrics,'lines',lines,'trend',trend,'planning',planning,'orders',coalesce(orders,'[]'),'losses',losses,'events',events,
  'batchOptions',coalesce(batch_options,'[]'),'selectedBatch',selected,'quality',quality,'inspection',coalesce(inspection,'{}'),
  'availability',round(100.0*totals.running_plan/nullif(totals.planned,0),1),
  'performance',round(100.0*totals.total/nullif(totals.running_plan,0),1),
  'yield',round(100.0*totals.good/nullif(totals.total,0),1),
  'health',health_state);
END;
$$;
