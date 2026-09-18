"""Keep the bundled lint policy and declare real Ignition project namespaces."""
import json
from pathlib import Path
import sys
import ignition_lint
root=Path(__file__).resolve().parents[2]
project=sys.argv[1] if len(sys.argv)>1 else 'oatmakers'
modules=set()
seen=set()
while project:
    if project in seen:raise SystemExit('Project inheritance cycle')
    seen.add(project)
    directory=root/'projects'/project
    scripts=directory/'ignition/script-python'
    if scripts.exists():modules.update(p.name for p in scripts.iterdir() if p.is_dir())
    project=json.loads((directory/'project.json').read_text()).get('parent','')
base=Path(ignition_lint.__file__).parent/'.config/.ignition-pylintrc'
lines=base.read_text().splitlines()
for index,line in enumerate(lines):
    if line.startswith('additional-builtins='):
        lines[index]=line+','+','.join(sorted(modules))
    if line.startswith('function-rgx='):
        lines[index]=line.replace('onShutdown', 'onShutdown|onRowClick|valueChanged')
    if line.startswith('argument-rgx='):
        lines[index]='argument-rgx=^(?:[a-z_][a-z0-9_]*|previousValue|currentValue|missedEvents)$'
out=root/'build/lint';out.mkdir(parents=True,exist_ok=True)
(out/'ignition-pylintrc').write_text('\n'.join(lines)+'\n')
rules=json.loads((root/'rule_config.json').read_text())
rules['PylintScriptRule']['kwargs']['pylintrc']=str(out/'ignition-pylintrc')
(out/'rules.json').write_text(json.dumps(rules,indent=2)+'\n')
print('Declared Ignition namespaces:', ', '.join(sorted(modules)))
