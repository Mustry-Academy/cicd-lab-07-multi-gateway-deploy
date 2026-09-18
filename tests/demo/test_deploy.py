"""Exercise scoped deployment and rollback against a disposable filesystem container."""
import http.server
import json
import os
import pathlib
import subprocess
import tempfile
import threading
ROOT=pathlib.Path(__file__).resolve().parents[2]
NAME='oatmakers-deploy-isolation-test'
DATA='/usr/local/bin/ignition/data'
class Scan(http.server.BaseHTTPRequestHandler):
    def do_POST(self):
        assert self.path in ('/data/api/v1/scan/config','/data/api/v1/scan/projects')
        self.send_response(200);self.end_headers();self.wfile.write(b'{}')
    def log_message(self,*args):pass
server=http.server.HTTPServer(('127.0.0.1',0),Scan)
threading.Thread(target=server.serve_forever,daemon=True).start()
def run(args,**kwargs):return subprocess.check_output(args,text=True,**kwargs).strip()
def read(path):return run(['docker','exec',NAME,'cat',path])
subprocess.run(['docker','run','-d','--name',NAME,'alpine:3.22','sleep','300'],check=True,stdout=subprocess.DEVNULL)
try:
    run(['docker','exec',NAME,'sh','-c',f'mkdir -p {DATA}/projects/oatmakers {DATA}/projects/unrelated {DATA}/config/resources/core/ignition/database-connection/OtherDb; echo old > {DATA}/projects/oatmakers/project.json; echo keep > {DATA}/projects/unrelated/marker; echo keep > {DATA}/config/resources/core/ignition/database-connection/OtherDb/marker'])
    with tempfile.TemporaryDirectory() as temporary:
        payload=pathlib.Path(temporary)/'payload'
        p=payload/'projects/oatmakers';p.mkdir(parents=True);(p/'project.json').write_text('{"title":"new"}')
        for name in ['database-connection/OatmakersDemo','secret-provider/DemoRuntime']:
            p=payload/'services/config/resources/core/ignition'/name;p.mkdir(parents=True);(p/'config.json').write_text('{}')
        env=dict(os.environ,IGNITION_CONTAINER=NAME,GATEWAY_DATA_PATH=DATA,
                 GITHUB_ENV=str(pathlib.Path(temporary)/'env'),IGNITION_API_KEY='test-only',
                 IGNITION_URL='http://127.0.0.1:'+str(server.server_port))
        run(['bash',str(ROOT/'tools/demo/deploy-scoped.sh'),str(payload)],env=env)
        assert json.loads(read(DATA+'/projects/oatmakers/project.json'))['title']=='new'
        assert read(DATA+'/projects/unrelated/marker')=='keep'
        assert read(DATA+'/config/resources/core/ignition/database-connection/OtherDb/marker')=='keep'
        env['DEMO_BACKUP']=pathlib.Path(env['GITHUB_ENV']).read_text().split('=',1)[1].strip()
        run(['bash',str(ROOT/'tools/demo/rollback-scoped.sh')],env=env)
        assert read(DATA+'/projects/oatmakers/project.json')=='old'
        assert read(DATA+'/projects/unrelated/marker')=='keep'
        assert read(DATA+'/config/resources/core/ignition/database-connection/OtherDb/marker')=='keep'
        assert run(['docker','exec',NAME,'sh','-c',f'test ! -d {DATA}/config/resources/core/ignition/database-connection/OatmakersDemo && echo removed'])=='removed'
    print('PASS scoped ship, backup and rollback preserve unrelated projects and connections')
finally:
    server.shutdown()
    subprocess.run(['docker','rm','-f',NAME],check=True,stdout=subprocess.DEVNULL)
