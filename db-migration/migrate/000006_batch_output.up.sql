-- Operator-entered output is separate from planned orders and simulated telemetry.
CREATE TABLE oat_demo.batch_output (
 request_id uuid PRIMARY KEY,
 batch_reference text NOT NULL UNIQUE,
 line_id integer NOT NULL REFERENCES oat_demo.line(id),
 product text NOT NULL,
 completed_at timestamptz NOT NULL,
 quantity_kg numeric NOT NULL CHECK(quantity_kg >= 0 AND quantity_kg <= 100000),
 bags integer NOT NULL CHECK(bags >= 0 AND bags <= 10000),
 recorded_at timestamptz NOT NULL DEFAULT clock_timestamp()
);
CREATE INDEX ON oat_demo.batch_output(recorded_at);

CREATE FUNCTION oat_demo.record_batch_output(p_request uuid,p_reference text,p_quantity numeric,p_bags integer)
RETURNS jsonb LANGUAGE plpgsql AS $$
DECLARE batch record; saved oat_demo.batch_output%ROWTYPE; inserted boolean;
BEGIN
 IF p_request IS NULL OR p_quantity IS NULL OR NOT (p_quantity BETWEEN 0 AND 100000)
    OR p_bags IS NULL OR p_bags NOT BETWEEN 0 AND 10000 THEN
  RAISE EXCEPTION 'Enter a valid output quantity and bag count';
 END IF;
 SELECT b.*,l.product INTO batch
 FROM oat_demo.plan_batches(now()-interval '90 days',now(),0) b
 JOIN oat_demo.line l ON l.id=b.line_id
 WHERE b.reference=p_reference AND b.ends<=now()
 AND EXISTS(SELECT 1 FROM oat_demo.sample s WHERE s.line_id=b.line_id AND s.at>=b.starts AND s.at<b.ends)
 LIMIT 1;
 IF NOT FOUND THEN RAISE EXCEPTION 'Select a completed batch with recorded production'; END IF;
 INSERT INTO oat_demo.batch_output(request_id,batch_reference,line_id,product,completed_at,quantity_kg,bags)
 VALUES(p_request,batch.reference,batch.line_id,batch.product,batch.ends,p_quantity,p_bags)
 ON CONFLICT DO NOTHING RETURNING * INTO saved;
 inserted:=FOUND;
 IF NOT inserted THEN
  SELECT * INTO saved FROM oat_demo.batch_output
  WHERE request_id=p_request OR batch_reference=p_reference ORDER BY recorded_at LIMIT 1;
  IF saved.batch_reference IS DISTINCT FROM p_reference OR saved.quantity_kg IS DISTINCT FROM p_quantity
     OR saved.bags IS DISTINCT FROM p_bags THEN
   RAISE EXCEPTION 'Output has already been recorded for this batch';
  END IF;
 END IF;
 RETURN jsonb_build_object('created',inserted,'reference',saved.batch_reference,
  'product',saved.product,'quantity_kg',saved.quantity_kg,'bags',saved.bags);
END;
$$;

CREATE FUNCTION oat_demo.prune_batch_output()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
 IF NEW.last_tick IS NOT NULL THEN
  DELETE FROM oat_demo.batch_output WHERE recorded_at<greatest(NEW.last_tick-interval '90 days',NEW.last_tick-interval '3 months');
 END IF;
 RETURN NEW;
END;
$$;
CREATE TRIGGER prune_batch_output AFTER UPDATE OF last_tick ON oat_demo.runtime
FOR EACH ROW EXECUTE FUNCTION oat_demo.prune_batch_output();
