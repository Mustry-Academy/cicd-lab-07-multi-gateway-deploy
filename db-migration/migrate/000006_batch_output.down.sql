DROP TRIGGER prune_batch_output ON oat_demo.runtime;
DROP FUNCTION oat_demo.prune_batch_output();
DROP FUNCTION oat_demo.record_batch_output(uuid,text,numeric,integer);
DROP TABLE oat_demo.batch_output;
