"""Integration checks against a disposable PostgreSQL database, never the live demo."""
import json
import os
import pathlib
import subprocess
import time

ROOT = pathlib.Path(__file__).resolve().parents[2]
CONTAINER = os.environ.get('DEMO_TEST_CONTAINER', 'oatmakers-showroom-local-database-1')
DB = 'oatmakers_demo_test'
PREFIX = ['docker','exec','-i',CONTAINER,'psql','-U','ignition'] if CONTAINER else ['psql','-U',os.environ.get('PGUSER','ignition')]

def sql(text, db=DB, expected=True):
    p = subprocess.run(PREFIX+['-d',db,'-X','-tA','-v','ON_ERROR_STOP=1'],input=text,text=True,capture_output=True)
    if expected and p.returncode:
        raise AssertionError(p.stderr)
    return p.stdout.strip() if expected else p.returncode

def value(text):
    return json.loads(sql(text))

def check(ok, message):
    assert ok, message
    print('PASS',message,flush=True)

# The name guard keeps time-travel fixtures away from the production database.
assert DB.endswith('_test')
sql('DROP DATABASE IF EXISTS '+DB, 'postgres')
sql('CREATE DATABASE '+DB, 'postgres')
started=time.monotonic()
try:
    for p in sorted((ROOT/'db-migration/migrate').glob('*.up.sql')):
        sql('BEGIN;\n'+p.read_text()+'\nCOMMIT;')
    health=value('SELECT oat_demo.health()')
    check(health['ok'] and health['lineCount']==3,'initial history is fresh and covers all lines')
    check(380000 <= health['sampleCount'] <= 388803,'history volume is bounded to three months')
    check(value("SELECT oat_demo.tick((SELECT last_tick FROM oat_demo.runtime))")['inserted']==0,'same-timestamp tick is idempotent')
    check(sql('SELECT count(*) FROM oat_demo.sample WHERE good_kg>total_kg OR good_kg<0 OR total_kg<0')=='0','production and quality quantities remain consistent')
    for scene,line,state in [('stoppage',1,'Stopped'),('quality',2,'Quality hold'),('recovery',1,'Recovering')]:
        d=value("SELECT oat_demo.snapshot('%s','day',%d)"%(scene,line))
        check(d['lines'][0]['state']==state,'replay '+scene+' selects recorded '+state+' state')
        check(bool(d['trend']) and bool(d['orders']) and bool(d['quality']),'replay '+scene+' has trends, batches and quality records')
    for period,count in [('shift',30),('day',20),('week',40),('month',25)]:
        d=value("SELECT oat_demo.snapshot('live','%s',0)"%period)
        check(len(d['trend'])>=count,period+' has populated historical buckets')
        oee=float(d['metrics'][1]['value']); calc=d['availability']*d['performance']*d['yield']/10000
        check(abs(oee-calc)<0.2,period+' OEE reconciles with its factors')
    d=value("SELECT oat_demo.snapshot('live','day',0)")
    selected=d['orders'][3]['reference']
    b=value("SELECT oat_demo.snapshot('live','day',0,'%s')->'selectedBatch'"%selected)
    check(b['reference']==selected,'batch drill-down preserves the selected record')
    check(sql("SELECT oat_demo.snapshot('invalid','day',0)",expected=False)!=0,'invalid scenario is rejected')
    check(sql("SELECT oat_demo.tick(now()-interval '1 day')",expected=False)!=0,'clock regression cannot rewind or delete current history')
    check(not value("SELECT oat_demo.health(now()-interval '1 hour')")['ok'],'health detects a regressed clock instead of reporting future data as fresh')
    # Keep one minute absent to test a real outage catch-up from a committed watermark.
    count=int(sql('SELECT count(*) FROM oat_demo.sample'))
    future="(SELECT last_tick+interval '21 days' FROM oat_demo.runtime)"
    sql('SELECT oat_demo.tick('+future+')')
    h=value('SELECT oat_demo.health((SELECT last_tick FROM oat_demo.runtime))')
    check(h['ok'] and h['sampleCount']<=388803,'three-week unattended jump catches up and retains a bounded window')
    check(sql("SELECT count(*) FROM oat_demo.sample WHERE at<(SELECT greatest(last_tick-interval '90 days',last_tick-interval '3 months') FROM oat_demo.runtime)")=='0','no samples exceed either retention limit')
    sql("INSERT INTO oat_demo.operator_order VALUES('00000000-0000-0000-0000-000000000001',now()-interval '100 days','OLD','Rolled oats',100,4,'Trial','Operator demo')")
    sql("INSERT INTO oat_demo.inspection VALUES('OLD',now()-interval '100 days','Released',11.5,82.0)")
    sql("SELECT oat_demo.tick((SELECT last_tick+interval '121 days' FROM oat_demo.runtime))")
    check(sql("SELECT count(*) FROM oat_demo.operator_order WHERE reference='OLD'")=='0','retention also prunes old operator demo requests')
    check(sql("SELECT count(*) FROM oat_demo.inspection WHERE batch_reference='OLD'")=='0','retention prunes old inspections')
    h=value('SELECT oat_demo.health((SELECT last_tick FROM oat_demo.runtime))')
    check(h['ok'] and h['sampleCount']<=388803,'four-month outage regenerates only the retained history')
    # Test the shortest calendar quarter across February.
    sql('TRUNCATE oat_demo.sample; UPDATE oat_demo.runtime SET last_tick=NULL,watermark=NULL;')
    sql("SELECT oat_demo.tick('2027-05-01T12:00:00Z')")
    check(sql("SELECT count(*) FROM oat_demo.sample WHERE at<'2027-02-01T12:00:00Z'")=='0','three-calendar-month retention also holds across February')
    before=sql('SELECT count(*) FROM oat_demo.sample')
    # A second worker must skip rather than generate concurrently.
    process=subprocess.Popen(PREFIX+['-d',DB,'-X','-tA'],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
    process.stdin.write('BEGIN; SELECT pg_advisory_xact_lock(70831901); SELECT 1; SELECT pg_sleep(2); COMMIT;\n');process.stdin.close()
    process.stdout.readline();process.stdout.readline();process.stdout.readline()
    check(value("SELECT oat_demo.tick('2027-05-01T12:01:00Z')").get('busy') is True,'overlapping continuity workers are excluded by the database lock')
    process.wait(timeout=10)
    check(sql('SELECT count(*) FROM oat_demo.sample')==before,'a skipped worker does not alter history')
    print('Integration checks completed in %.1fs'%(time.monotonic()-started),flush=True)
finally:
    sql('DROP DATABASE IF EXISTS '+DB, 'postgres')
