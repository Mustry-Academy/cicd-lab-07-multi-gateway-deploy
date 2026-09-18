"""Build the native Perspective customer demo and reusable view library."""
import copy
import json
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
P = ROOT / 'projects/oatmakers/com.inductiveautomation.perspective'
V = P / 'views'

def write(p, value):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(value, indent=2) + '\n')

def resource(p, files):
    write(p/'resource.json', dict(scope='G',version=1,restricted=False,overridable=True,files=files,attributes={}))

def prop(path, both=False):
    return {'binding': {'type':'property','config':dict(path=path, **({'bidirectional':True} if both else {}))}}

def expr(value):
    return {'binding': {'type':'expr','config':{'expression':value}}}

def node(kind,name,props=None,children=None,basis=None,grow=None,classes=None):
    n={'type':kind,'meta':{'name':name},'props':props or {}}
    if children is not None:n['children']=children
    if classes:n['props'].setdefault('style',{})['classes']=classes
    n['position']={'shrink':0}
    if basis is not None:n['position']['basis']=basis
    if grow is not None:n['position']['grow']=grow
    return n

def label(name,text='',classes='Demo/Body',basis='auto'):
    return node('ia.display.label',name,{'text':text},basis=basis,classes=classes)

def bound_label(name,path,classes='Demo/Body',basis='auto'):
    n=label(name,'',classes,basis);n['propConfig']={'props.text':prop(path)};return n

def flex(name,children,direction='column',classes=None,basis=None,grow=None):
    props={'direction':direction}
    if classes in ('Demo/Wrap','Demo/PageHeader','Demo/Filters','Demo/Facts','Demo/Spread'):props['wrap']='wrap'
    return node('ia.container.flex',name,props,children,basis,grow,classes)

def button(name,text,script=None,page=None,classes='Demo/Button'):
    n=node('ia.input.button',name,{'text':text},basis='40px',classes=classes)
    if script:n['events']={'component':{'onActionPerformed':{'type':'script','scope':'G','config':{'script':script}}}}
    if page:n['events']={'dom':{'onClick':{'type':'nav','scope':'C','config':{'page':page}}}}
    return n

def embed(name,path,params=None,basis=None,grow=None):
    return node('ia.display.view',name,{'path':path,'params':params or {},'useDefaultViewWidth':False,'useDefaultViewHeight':False},basis=basis,grow=grow)

def repeater(name,path,source,basis='150px'):
    n=node('ia.display.flex-repeater',name,{'path':path,'direction':'row','wrap':'wrap','useDefaultViewWidth':False,'useDefaultViewHeight':True,'elementPosition':{'basis':'230px','grow':1,'shrink':0},'instances':[]},basis='auto',classes='Demo/Repeater')
    n['propConfig']={'props.instances':prop(source)};return n

def table(name,source,columns,height='320px',drill=False):
    cols=[{'field':k,'visible':True,'editable':False,'render':'auto','header':{'title':title},'width':w,'strictWidth':False} for k,title,w in columns]
    n=node('ia.display.table',name,{'data':[],'columns':cols,'pager':{'top':False,'bottom':True,'initialOption':10,'options':[10,20,50]},'selection':{'enabled':True,'mode':'row'},'filter':{'enabled':True},'headerStyle':{'backgroundColor':'#edf2e8','color':'#355541','fontWeight':'600','fontSize':12},'rows':{'height':36,'striped':{'enabled':True,'color':'#f7f9f4'}}},basis=height,classes='Demo/Table')
    n['propConfig']={'props.data':prop(source)}
    if drill:n['events']={'component':{'onRowClick':{'type':'script','scope':'G','config':{'script':'\trow = self.props.data[event.row]\n\tif row.get("status") == "Scheduled":\n\t\tself.view.custom.selectionNotice = "This batch is scheduled. Quality measurements become available after production starts."\n\t\treturn\n\tself.session.custom.demo.batch = row["reference"]\n\tsystem.perspective.navigate("/quality")'}}}}
    return n

BASE_CHART=json.loads((ROOT/'tools/demo/xy-template.json').read_text())
def chart(name,series,source='view.custom.data.trend',height='300px'):
    props=copy.deepcopy(BASE_CHART)
    props['dataSources']={'history':[]}
    props['legend']={'enabled':True,'position':'bottom'}
    props['title']={'text':''}
    props['cursor']={'enabled':True,'behavior':'zoomX'}
    x=props['xAxes'][0];x['name']='time';x['render']='date';x['label']['enabled']=False;x['date']['format']='dd MMM HH:mm';x['date']['inputFormat']='x'
    x['appearance']['grid']['minDistance']=120;x['appearance']['grid']['opacity']=0.08;x['appearance']['labels']['color']='#63766d'
    y=props['yAxes'][0];y['name']='value';y['render']='value';y['label']['enabled']=False;y['value']['range']['min']=0;y['appearance']['grid']['opacity']=0.08;y['appearance']['labels']['color']='#63766d'
    props['xAxes']=[x];props['yAxes']=[y]
    proto=props['series'][0];props['series']=[]
    for key,title,colour in series:
        s=copy.deepcopy(proto);s['name']=title;s['data']={'source':'history','x':'ts','y':key};s['xAxis']='time';s['yAxis']='value';s['line']['appearance']['stroke']['color']=colour;s['line']['appearance']['stroke']['width']=3;s['line']['appearance']['fill']={'color':colour,'opacity':0.07};s['tooltip']['text']='{name}: [bold]{valueY}[/]';s['label']={};props['series'].append(s)
    n=node('ia.chart.xy',name,props,basis=height,classes='Demo/Chart');n['propConfig']={'props.dataSources.history':prop(source)};return n

def panel(name,title,subtitle,children,basis=None,grow=1):
    return flex(name,[label(name+'Title',title,'Demo/SectionTitle'),label(name+'Subtitle',subtitle,'Demo/Muted')]+children,classes='Demo/Panel',basis=basis,grow=grow)

def view(name,root,params=None,custom=None,config=None,height=1000):
    d={'custom':custom or {},'params':params or {},'propConfig':config or {},'props':{'defaultSize':{'width':1280,'height':height}},'root':root}
    for key in d['params']:d['propConfig'].setdefault('params.'+key,{'paramDirection':'input','persistent':True})
    for key in d['custom']:
        if 'custom.'+key not in d['propConfig']:d['propConfig']['custom.'+key]={'persistent':True}
    write(V/name/'view.json',d);resource(V/name,['view.json']);return d
