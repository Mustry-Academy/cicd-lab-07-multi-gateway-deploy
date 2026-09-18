"""Read-only readiness check for the public demonstration."""
import argparse
import json
import time
import urllib.error
import urllib.request

parser=argparse.ArgumentParser()
parser.add_argument('url')
parser.add_argument('--attempts',type=int,default=1)
parser.add_argument('--health-file')
args=parser.parse_args()
base=args.url.rstrip('/')
for attempt in range(args.attempts):
    try:
        if args.health_file:
            with open(args.health_file) as response:
                health=json.load(response)
        else:
            with urllib.request.urlopen(base+'/system/webdev/oatmakers/api/demo-health',timeout=20) as response:
                health=json.load(response)
        assert health.get('ok'), 'Demo data is not ready: '+json.dumps(health)
        if not args.health_file:
            assert health.get('appRevision')=='showroom-4.1.0', 'Unexpected demo application revision'
        assert health['liveAgeSeconds']<=15, 'Fine telemetry stopped advancing'
        assert health['liveRetentionHours']==6, 'Wrong fine telemetry retention'
        assert health['ageSeconds']<=180, 'History stopped advancing'
        assert health['coverageDays']>=88, 'Insufficient rolling history'
        assert health['retentionDays']==90, 'Wrong retention policy'
        for route in ['/','/production','/scada','/performance','/quality','/operator','/demo/health']:
            with urllib.request.urlopen(base+'/data/perspective/client/oatmakers'+route,timeout=20) as response:
                assert response.status==200, 'Page unavailable: '+route
        print(json.dumps(health,indent=2))
        print('Seven page routes and live data readiness passed.')
        break
    except (AssertionError, OSError, ValueError) as exc:
        if attempt+1==args.attempts:raise SystemExit(str(exc))
        print('Waiting for data readiness (%d/%d)'%(attempt+1,args.attempts),flush=True)
        time.sleep(5)
