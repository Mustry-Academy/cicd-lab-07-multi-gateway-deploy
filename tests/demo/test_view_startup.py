"""Regression checks for history bindings before the date picker publishes a range."""
import json
from pathlib import Path
from types import SimpleNamespace

ROOT=Path(__file__).resolve().parents[2]
V=ROOT/'projects/oatmakers/com.inductiveautomation.perspective/views'
history=json.loads((V/'Demo/HistoryChart/view.json').read_text())
performance=json.loads((V/'Demo/Performance/view.json').read_text())
code=history['propConfig']['custom.history']['binding']['transforms'][0]['code']
calls=[]
def query(start,end,line,metric):
    calls.append((start,end,line,metric))
    return {'points':[{'ts':start,'line1':12.3}],'count':1,'message':'1 recorded point'}
namespace={'application':SimpleNamespace(demo=SimpleNamespace(history=query))}
exec('def transform(value):\n'+code,namespace)
for value in (None,{}, {'range':None}, {'range':{}}, {'range':{'start':0,'end':0,'valid':False}}):
    result=namespace['transform'](value)
    assert result['points']==[] and not calls, 'Startup must not query or produce an invalid chart value'
result=namespace['transform']({'range':{'start':1000,'end':2000,'valid':True},'line':1,'metric':'rate'})
assert calls==[(1000,2000,1,'rate')] and result['points'][0]['line1']==12.3
assert set(history['params']['range'])=={'start','end','valid','realtime'}
embedded=next(c for c in performance['root']['children'] if c['meta']['name']=='History')
assert embedded['props']['params']['range']==history['params']['range']
assert history['propConfig']['custom.history']['persistent']
print('PASS empty, null and pending ranges render safely; valid selections still load history')
