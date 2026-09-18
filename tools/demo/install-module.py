"""Stage the pinned signed UI module, preserving every other module registration."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
import time
import zipfile
import xml.etree.ElementTree as ET

parser = argparse.ArgumentParser()
parser.add_argument('payload', type=Path)
args = parser.parse_args()
root = Path(__file__).resolve().parents[2]
metadata = args.payload / 'tools/demo/mustry-ui-version.json'
if not metadata.is_file():
    print('This project release does not carry a Mustry UI module. Keeping installed modules.')
    raise SystemExit(0)
meta = json.loads(metadata.read_text())
binary = args.payload / meta['file']
assert hashlib.sha256(binary.read_bytes()).hexdigest() == meta['sha256'], 'Module checksum mismatch'
with zipfile.ZipFile(binary) as archive:
    manifest = ET.fromstring(archive.read('module.xml')).find('module')
    assert manifest.findtext('id') == meta['moduleId']
    assert manifest.findtext('version') == meta['version']
    assert manifest.findtext('freeModule') == 'true'
container = os.environ['IGNITION_CONTAINER']
data = os.environ.get('GATEWAY_DATA_PATH', '/usr/local/bin/ignition/data')
target = data + '/custom-modules/Mustry_UI.modl'
def docker(*command, **kwargs):
    return subprocess.check_output(['docker', *command], **kwargs)
registry = json.loads(docker('exec', container, 'cat', data + '/modules.json'))
entry = {'filename': target, 'onStartup': 'enabled',
         'certFingerprint': meta['certFingerprint'], 'licenseAgreementHash': meta['licenseAgreementHash']}
current = subprocess.run(['docker', 'exec', container, 'sha256sum', target], capture_output=True, text=True)
unchanged = current.returncode == 0 and current.stdout.split()[0] == meta['sha256'] and registry.get(meta['moduleId']) == entry
env = Path(os.environ['GITHUB_ENV']) if os.environ.get('GITHUB_ENV') else None
if unchanged:
    if env:
        with env.open('a') as output: output.write('DEMO_MODULE_CHANGED=false\n')
    print('Mustry UI binary and registration are unchanged.')
else:
    backup = '/backups/mustry-ui/' + str(time.time_ns())
    docker('exec', '-u', 'root', container, 'sh', '-c',
           'set -eu; mkdir -p "$1" "$2/custom-modules"; cp "$2/modules.json" "$1/modules.json"; '
           'if [ -f "$3" ]; then cp "$3" "$1/Mustry_UI.modl"; fi', 'sh', backup, data, target)
    registry[meta['moduleId']] = entry
    with tempfile.TemporaryDirectory() as temporary:
        path = Path(temporary) / 'modules.json'
        path.write_text(json.dumps(registry, indent=2) + '\n')
        docker('cp', str(binary), container + ':' + target + '.new')
        docker('cp', str(path), container + ':' + data + '/modules.json.new')
    docker('exec', '-u', 'root', container, 'sh', '-c',
           'set -eu; chown 2003:0 "$1.new" "$2/modules.json.new"; mv "$1.new" "$1"; '
           'mv "$2/modules.json.new" "$2/modules.json"', 'sh', target, data)
    if env:
        with env.open('a') as output:
            output.write('DEMO_MODULE_CHANGED=true\nDEMO_MODULE_BACKUP=' + backup + '\n')
    print('Pinned Mustry UI staged. All other registrations preserved. Backup: ' + backup)
