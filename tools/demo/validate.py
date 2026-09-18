"""Validate deployable demo resources without an Ignition runtime."""
import ast
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
project=ROOT/'projects/oatmakers'
views=project/'com.inductiveautomation.perspective/views'
errors=[]
for file in project.rglob('*.json'):
    try: json.loads(file.read_text())
    except Exception as exc: errors.append(str(file)+': '+str(exc))
for file in project.rglob('resource.json'):
    data=json.loads(file.read_text())
    for name in data.get('files',[]):
        if not (file.parent/name).is_file():errors.append(str(file)+': missing '+name)

def walk(value,file):
    if isinstance(value,dict):
        if value.get('type') in ('ia.display.view','ia.display.flex-repeater'):
            path=value.get('props',{}).get('path')
            if path and not (views/path/'view.json').is_file():errors.append(str(file)+': missing embedded view '+path)
        if value.get('type') == 'mustrysolutions.perspective.display.panzoomview':
            path=value.get('props',{}).get('config',{}).get('viewPath')
            if path and not (views/path/'view.json').is_file():errors.append(str(file)+': missing SCADA view '+path)
        if value.get('type') == 'mustrysolutions.perspective.input.datetimerangepicker':
            for preset in value['props']['config']['presets']:
                if preset['type']=='rolling' and not (preset.get('rolling',{}).get('amount',0)>0 and preset.get('rolling',{}).get('unit') in ('hours','days','weeks','months')):
                    errors.append(str(file)+': invalid rolling preset')
        for key,item in value.items():
            if key in ('code','script') and isinstance(item,str) and item.strip():
                try:ast.parse('def script(self, value, quality, timestamp, event, currentValue, previousValue, origin, missedEvents):\n'+ '\n'.join('\t'+line for line in item.splitlines()))
                except SyntaxError as exc:errors.append(str(file)+': embedded script '+str(exc))
            else:walk(item,file)
    elif isinstance(value,list):
        for item in value:walk(item,file)
for folder in ['Demo','Templates/InputFields']:
    for file in (views/folder).rglob('view.json'):
        walk(json.loads(file.read_text()),file)
        for parent in file.parent.parents:
            if parent==views:break
            if (parent/'view.json').exists():errors.append(str(file)+': view nested inside another view resource')
for file in (project/'ignition/script-python/application/demo').glob('*.py'):ast.parse(file.read_text())
config=json.loads((project/'com.inductiveautomation.perspective/page-config/config.json').read_text())
for path,definition in config['pages'].items():
    if not (views/definition['viewPath']/'view.json').exists():errors.append('Missing route view: '+path)
if errors:raise SystemExit('\n'.join(errors))
print('JSON, resource files, route mappings, embedded views and script syntax passed.')
