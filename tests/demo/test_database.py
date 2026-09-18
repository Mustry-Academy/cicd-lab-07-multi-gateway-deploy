"""Integration checks against a disposable PostgreSQL database, never the live demo."""
import json
import os
import pathlib
import subprocess
import time

ROOT = pathlib.Path(__file__).resolve().parents[2]
CONTAINER = os.environ.get('DEMO_TEST_CONTAINER', 'oatmakers-ui-local-database-1')
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
    live=value('SELECT oat_demo.health_live()')
    check(live['ok'] and 64000<live['liveSampleCount']<=64800,'one-second telemetry is fresh and bounded to 6 hours')
    check(live['liveIntervalSeconds']==1 and live['liveRetentionHours']==6,'health reports the one-second grid the screens poll at')
    check(value('SELECT oat_demo.tick_live((SELECT last_tick FROM oat_demo.live_runtime))')['inserted']==0,'fine telemetry ticks are idempotent')
    check(sql("WITH minute AS (SELECT date_trunc('minute',at) t FROM oat_demo.live_sample WHERE line_id=1 AND state='Running' AND at<now()-interval '1 minute' ORDER BY at DESC LIMIT 1) SELECT count(DISTINCT total_kg)>1 FROM oat_demo.live_sample,minute WHERE line_id=1 AND at>=t AND at<t+interval '1 minute'")=='t','production rates visibly change within a minute')
    check(sql("WITH fine AS (SELECT sum(total_kg) kg FROM generate_series(date_trunc('minute',now()),date_trunc('minute',now())+interval '59 seconds',interval '1 second') t CROSS JOIN LATERAL oat_demo.measure_live(t,1)) SELECT abs(fine.kg-m.total_kg)<0.00001 FROM fine CROSS JOIN oat_demo.measure(date_trunc('minute',now()),1) m")=='t','fine production quantities reconcile with minute history')
    check(sql("SELECT count(*) FROM oat_demo.live_sample WHERE good_kg>total_kg OR good_kg<0 OR total_kg<0 OR energy_kwh<0")=='0','fine production and energy remain physically consistent')
    check(sql("SELECT oat_demo.tick_live(now()-interval '1 day')",expected=False)!=0,'fine clock regression cannot overwrite current samples')
    for days,metric in [(1,'rate'),(7,'temperature'),(30,'power'),(89,'moisture')]:
        query="SELECT oat_demo.history_range((extract(epoch FROM now()-interval '%s days')*1000)::bigint,(extract(epoch FROM now())*1000)::bigint,2,'%s')"%(days,metric)
        history=value(query)
        check(0<len(history['points'])<=901,str(days)+'-day '+metric+' history is populated and downsampled')
        check(all(p['line1'] is None and p['line3'] is None and p['line2'] is not None for p in history['points']),'history line filter is exact for '+metric)
    bounds="(extract(epoch FROM now()-interval '10 days')*1000)::bigint,(extract(epoch FROM now()-interval '9 days')*1000)::bigint"
    history=value('SELECT oat_demo.history_range('+bounds+",1,'pressure')")
    check(history['points'] and history['points'][0]['ts']>=history['startEpochMs'],'a manually selected historical window returns recorded points from that window')
    batches=value('SELECT oat_demo.batches_range('+bounds+',1)')
    check(len(batches)>0 and all(b['lineNumber']==1 for b in batches),'planning and quality can inspect an older arbitrary date range')
    detail=value("SELECT oat_demo.batch_detail('%s')"%batches[0]['reference'])
    check(detail['available'] and detail['reference']==batches[0]['reference'],'batch popup resolves historical references outside the old three-day window')
    check(sql("SELECT oat_demo.history_range(1,9999999999999,0,'invalid')",expected=False)!=0,'invalid history measurements are rejected')

    # The board has to look like a factory, not a ruled sheet: the lines must not
    # share start times, batches must not all be the same length, there must be
    # real gaps between them, and the stops in the telemetry must reach the board.
    window="(extract(epoch FROM now()-interval '24 hours')*1000)::bigint,(extract(epoch FROM now()+interval '12 hours')*1000)::bigint"
    plan=value('SELECT oat_demo.batches_range('+window+',0)')
    starts={}
    for b in plan:
        starts.setdefault(b['lineNumber'],[]).append((b['startEpochMs'],b['endEpochMs'],b['plannedMinutes']))
    check(len(starts)==3,'every line appears on the board')
    check(len({tuple(sorted(s for s,_,_ in v)) for v in starts.values()})==3,'no two lines run the same start times')
    check(len({m for v in starts.values() for _,_,m in v})>1,'batches are not all the same length')
    gaps=[]
    for runs in starts.values():
        runs.sort()
        gaps += [runs[i+1][0]-runs[i][1] for i in range(len(runs)-1)]
    check(gaps and all(g>0 for g in gaps),'every line has a real gap between consecutive batches')
    check(any(g>=30*60*1000 for g in gaps),'at least one gap is a full changeover or CIP window')
    board=value('SELECT oat_demo.timeline_range('+window+',0)')
    stops=[e for e in board if e.get('isDowntime')]
    check(len(board)>len(plan) and stops,'the board carries downtime alongside the planned batches')
    check({e['category'] for e in stops} & {'stop','quality','changeover'},'downtime is categorised for the timeline legend')
    check(all(e['endEpochMs']>e['startEpochMs'] for e in board),'no board entry ends before it starts')
    check(sql('SELECT oat_demo.timeline_range(1,9999999999999,0)',expected=False)!=0,'an unbounded planning window is rejected')
    detail=value("SELECT oat_demo.batch_detail('%s')"%plan[0]['reference'])
    check(detail['available'],'a batch from the varied plan still resolves to a popup record')
    # Keep one minute absent to test a real outage catch-up from a committed watermark.
    count=int(sql('SELECT count(*) FROM oat_demo.sample'))
    future="(SELECT last_tick+interval '21 days' FROM oat_demo.runtime)"
    sql('SELECT oat_demo.tick('+future+')')
    h=value('SELECT oat_demo.health((SELECT last_tick FROM oat_demo.runtime))')
    check(h['ok'] and h['sampleCount']<=388803,'three-week unattended jump catches up and retains a bounded window')
    sql('SELECT oat_demo.tick_live((SELECT last_tick FROM oat_demo.runtime))')
    fine=value('SELECT oat_demo.health_live((SELECT last_tick FROM oat_demo.live_runtime))')
    check(fine['ok'] and fine['liveSampleCount']<=64800,'fine telemetry catches up after three weeks and retains only 6 hours')
    check(sql("SELECT count(*) FROM oat_demo.sample WHERE at<(SELECT greatest(last_tick-interval '90 days',last_tick-interval '3 months') FROM oat_demo.runtime)")=='0','no samples exceed either retention limit')
    sql("INSERT INTO oat_demo.operator_order VALUES('00000000-0000-0000-0000-000000000001',now()-interval '100 days','OLD','Rolled oats',100,4,'Trial','Operator demo')")
    sql("INSERT INTO oat_demo.inspection VALUES('OLD',now()-interval '100 days','Released',11.5,82.0)")
    sql("SELECT oat_demo.tick((SELECT last_tick+interval '121 days' FROM oat_demo.runtime))")
    check(sql("SELECT count(*) FROM oat_demo.operator_order WHERE reference='OLD'")=='0','retention also prunes old operator demo requests')
    check(sql("SELECT count(*) FROM oat_demo.inspection WHERE batch_reference='OLD'")=='0','retention prunes old inspections')
    h=value('SELECT oat_demo.health((SELECT last_tick FROM oat_demo.runtime))')
    check(h['ok'] and h['sampleCount']<=388803,'four-month outage regenerates only the retained history')
    sql('SELECT oat_demo.tick_live((SELECT last_tick FROM oat_demo.runtime))')
    check(value('SELECT oat_demo.health_live((SELECT last_tick FROM oat_demo.live_runtime))')['ok'],'both history resolutions recover after a four-month outage')
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
