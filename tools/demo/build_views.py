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

metric=flex('root',[bound_label('Title','view.params.title','Demo/Eyebrow'),flex('Reading',[bound_label('Value','view.params.value','Demo/MetricValue'),bound_label('Unit','view.params.unit','Demo/MetricUnit')],'row',classes='Demo/MetricReading'),bound_label('Hint','view.params.hint','Demo/Muted')],classes='Demo/Metric')
view('Demo/Components/Metric',metric,params={'title':'METRIC','value':'0','unit':'','hint':'','accent':'green'},height=140)
line=flex('root',[flex('LineHeading',[bound_label('Name','view.params.name','Demo/SectionTitle'),bound_label('State','view.params.state','Demo/Badge')],'row',classes='Demo/Spread'),bound_label('Product','view.params.product','Demo/Muted'),bound_label('Throughput','view.params.throughput','Demo/LineValue'),flex('Facts',[bound_label('Temperature','view.params.temperature','Demo/Body'),bound_label('Moisture','view.params.moisture','Demo/Body'),bound_label('Power','view.params.power','Demo/Body')],'row',classes='Demo/Facts'),button('OpenLine','Explore line',script='\tself.session.custom.demo.line = self.view.params.id\n\tsystem.perspective.navigate("/process")',classes='Demo/QuietButton')],classes='Demo/Panel')
line['children'][0]['children'][1]['propConfig']['props.style.color']=prop('view.params.colour')
view('Demo/Components/LineCard',line,params={k:'' for k in ['name','state','product','throughput','temperature','moisture','power','colour','batch']}|{'id':0},height=230)

event_card=flex('root',[flex('Top',[bound_label('State','view.params.state','Demo/Badge'),bound_label('Time','view.params.time','Demo/Muted')],'row',classes='Demo/Spread'),bound_label('Line','view.params.line','Demo/Body'),bound_label('Description','view.params.description','Demo/Muted')],classes='Demo/EventCard')
view('Demo/Components/Event',event_card,params={'state':'','time':'','line':'','description':''},height=82)
def event_list():
    n=repeater('Attention','Demo/Components/Event','view.custom.data.events','290px')
    n['props'].update({'direction':'column','wrap':'nowrap','elementPosition':{'basis':'82px','grow':0,'shrink':0}})
    n['propConfig']['props.instances']['binding']['transforms']=[{'type':'script','code':'\treturn list(value)[:3]'}]
    return n

# Persistent per-session choices keep replay independent for each presenter.
write(P/'session-props/props.json',{'custom':{'demo':{'scene':'live','period':'day','line':0,'batch':''}},'props':{'theme':'light'}})
resource(P/'session-props',['props.json'])
nav=[label('Wordmark','OATMAKERS','Demo/Brand'),label('BrandDetail','CONNECTED FACTORY','Demo/NavEyebrow'),label('DemoBadge','SIMULATED CUSTOMER DEMO','Demo/NavBadge')]
routes=[('/','Factory overview','Demo/Overview'),('/production','Production planning','Demo/Production'),('/process','Process detail','Demo/Process'),('/performance','Performance','Demo/Performance'),('/quality','Quality & traceability','Demo/Quality'),('/operator','Operator workflow','Demo/Operator'),('/components','Component library','Demo/ComponentsGallery'),('/demo/health','Demo health','Demo/Health')]
for i,(route,title,_) in enumerate(routes):
    b=button('Nav'+str(i),title,page=route,classes='Demo/NavButton');b['position']['basis']='45px'
    b['propConfig']={'props.style.backgroundColor':expr('if({page.props.path} = '+json.dumps(route)+', "#315844", "transparent")')}
    nav.append(b)
nav += [flex('Spacer',[],grow=1),label('Retention','ROLLING 90-DAY HISTORY','Demo/NavEyebrow'),label('Footer','A Mustry Solutions demonstration','Demo/NavFooter')]
view('Sidenav',flex('root',nav,classes='Demo/Navigation'),height=900)

EMPTY={'ready':False,'stale':False,'message':'Loading demonstration data...','metrics':[],'lines':[],'trend':[],'orders':[],'planning':[],'losses':[],'events':[],'quality':[],'batchOptions':[],'selectedBatch':{'reference':'Loading batch','product':'','quality':'Awaiting data'},'inspection':{},'submissions':[],'window':'','clock':'','health':{'ok':False,'ageSeconds':'n/a','coverageDays':'n/a','lineCount':'n/a','sampleCount':'n/a'},'availability':'n/a','performance':'n/a','yield':'n/a'}
OPTIONS={
'scene':[('live','Live production'),('stoppage','Replay: line stoppage'),('quality','Replay: quality deviation'),('recovery','Replay: recovery')],
'period':[('shift','Last 8 hours'),('day','Last 24 hours'),('week','Last 7 days'),('month','Last 30 days')],
'line':[(0,'All production lines'),(1,'Rolling line 01'),(2,'Cutting line 02'),(3,'Milling line 03')]}
def dropdown(name,options,path,width='190px'):
    d=node('ia.input.dropdown',name,{'options':[{'value':k,'label':v} for k,v in options],'value':options[0][0],'search':{'enabled':False}},basis=width,classes='Demo/Select')
    d['propConfig']={'props.value':prop(path,True)};return d

def page(name,title,subtitle,content,custom=None,configs=None):
    heading=flex('Heading',[flex('Identity',[label('Eyebrow','OATMAKERS / CUSTOMER DEMO','Demo/Eyebrow'),label('Title',title,'Demo/PageTitle'),label('Subtitle',subtitle,'Demo/Subtitle')],grow=1),button('ResetScenario','Reset demo filters',script='\tself.session.custom.demo.scene = "live"\n\tself.session.custom.demo.period = "day"\n\tself.session.custom.demo.line = 0\n\tself.session.custom.demo.batch = ""',classes='Demo/QuietButton')],'row',classes='Demo/PageHeader')
    filters=flex('Filters',[dropdown(k,OPTIONS[k],'session.custom.demo.'+k) for k in ['scene','period','line']],'row',classes='Demo/Filters')
    filters['children'].append(bound_label('Clock','view.custom.data.clock','Demo/Clock'))
    status=bound_label('Status','view.custom.data.message','Demo/Status')
    status['propConfig']['props.style.backgroundColor']=expr('if({view.custom.data.stale}, "#fff1d9", "#e8f1ea")')
    cfg={'custom.data':{'binding':{'type':'expr-struct','config':{'waitOnAll':True,'struct':{'tick':'now(10000)','scene':'{session.custom.demo.scene}','period':'{session.custom.demo.period}','line':'{session.custom.demo.line}','batch':'{session.custom.demo.batch}'}},'transforms':[{'type':'script','code':'\treturn application.demo.snapshot(value["scene"], value["period"], value["line"], value["batch"])'}]}}}
    cfg.update(configs or {})
    heading['children'][0]['position'].update({'basis':'260px','shrink':1})
    heading['children'][0]['props']['style']={'minWidth':'0'}
    heading['children'][1]['position']['basis']='150px'
    heading['children'][1]['props']['style']['height']='40px'
    for item in content:
        if item.get('props',{}).get('style',{}).get('classes') == 'Demo/Panel':
            item['position']['grow']=0
    root=flex('root',[heading,filters,status,bound_label('Window','view.custom.data.window','Demo/Muted')]+[bound_label('SelectionNotice','view.custom.selectionNotice','Demo/Muted')]+content,classes='Demo/Page')
    return view(name,root,custom={'data':EMPTY,'selectionNotice':''}|(custom or {}),config=cfg)

ORDER_COLS=[('reference','Batch',190),('line','Production line',170),('product','Product',150),('started','Started',140),('produced_kg','Output kg',115),('target_kg','Target kg',115),('status','Status',150)]
EVENT_COLS=[('time','Time',130),('line','Production line',180),('state','State',140),('description','Event',310)]
METRICS=lambda:repeater('Metrics','Demo/Components/Metric','view.custom.data.metrics','150px')
LINES=lambda:repeater('Lines','Demo/Components/LineCard','view.custom.data.lines','240px')
productionChart=lambda:chart('OutputTrend',[('total','Total rate (t/h)','#9baf9b'),('good','Good rate (t/h)','#327656')])
page('Demo/Overview','The factory at a glance','Production, quality and energy. One connected view of the shift.',[
 METRICS(),flex('OverviewCharts',[panel('Output','Production rate through the period','Tonnes per hour, calculated from recorded minute samples.',[productionChart()],basis='600px'),panel('Focus','What needs attention','Select a replay above to follow a stoppage, quality event or recovery.',[event_list()],basis='410px')],'row','Demo/Wrap'),
 label('LineTitle','Explore the production lines','Demo/SectionTitle'),LINES(),
 panel('Recent','Latest production batches','Select a batch to inspect its quality and traceability.',[table('RecentOrders','view.custom.data.orders',ORDER_COLS,'300px',True)])])
page('Demo/Production','Production planning','Follow every batch from its production run to quality release.',[
 METRICS(),panel('Plan','Batch plan and actual production','Select a row to open the matching quality record. All quantities are calculated from stored minute samples.',[table('Orders','view.custom.data.planning',ORDER_COLS,'530px',True)]),
 panel('Submitted','Demo production requests','Generated examples and operator requests are retained for at most 90 days.',[table('SubmittedOrders','view.custom.data.submissions',[('reference','Reference',170),('product','Product',180),('quantity_kg','Requested kg',120),('bags','Bags',90),('mode','Mode',110),('source','Source',150),('submitted','Created',150)],'260px')])])
# A legible process sequence complements live line cards and trends.
stages=[]
for i,(title,detail) in enumerate([('01 / Intake','Incoming oats and batch identity'),('02 / Conditioning','Moisture preparation and inspection'),('03 / Heat treatment','Temperature control and hold time'),('04 / Processing','Rolling, cutting or milling'),('05 / Packing','Good output, rejects and dispatch')]):
    stages.append(panel('Stage'+str(i),title,detail,[],basis='180px'))
page('Demo/Process','Inside the process','Choose a line to follow its state, process conditions and recent events.',[
 LINES(),flex('ProcessFlow',stages,'row','Demo/Wrap'),
 flex('ProcessCharts',[panel('Temperature','Process temperature','Degrees Celsius. The line stoppage replay shows the cooling response.',[chart('TemperatureChart',[('temperature','Temperature (C)','#b4773b')])],basis='450px'),panel('Moisture','Product moisture','Percent moisture. Above 13% requires a quality review.',[chart('MoistureChart',[('moisture','Moisture (%)','#327656')])],basis='450px')],'row','Demo/Wrap'),
 panel('EventLog','Process events','Transitions are derived from recorded equipment states.',[table('ProcessEvents','view.custom.data.events',EVENT_COLS,'330px')])])
factors=[]
for k,title in [('availability','Availability'),('performance','Performance'),('yield','Quality')]:
    e=embed('Factor'+k,'Demo/Components/Metric',{'title':title.upper(),'unit':'%','hint':'Capacity weighted across selected lines' if k=='availability' else 'Calculated for the selected period'},basis='200px',grow=1)
    e['propConfig']={'props.params.value':prop('view.custom.data.'+k)};factors.append(e)
page('Demo/Performance','Understand production losses','Compare output, downtime and energy using the same time window.',[
 METRICS(),flex('Factors',factors,'row','Demo/Wrap'),
 flex('PerformanceCharts',[panel('Production','Output and first-pass quality','Drag across a chart to zoom. Use the period selector for longer history.',[productionChart()],basis='460px'),panel('Energy','Power demand','Mean kW per interval, including the base load during stoppages.',[chart('EnergyChart',[('energy','Power (kW)','#487fa5')])],basis='460px')],'row','Demo/Wrap'),
 panel('LossReasons','Where output was lost','Minutes are accumulated per line. Lost kg compares good output with nominal capacity.',[table('Losses','view.custom.data.losses',[('reason','Loss reason',240),('minutes','Line minutes',160),('lost_kg','Lost output kg',180)],'280px')])])
batchSelector=dropdown('BatchSelector',[('','Latest available batch')],'session.custom.demo.batch','360px');batchSelector['propConfig']['props.options']=prop('view.custom.data.batchOptions')
batchHeader=bound_label('BatchIdentity','view.custom.data.selectedBatch.reference','Demo/SectionTitle')
inspectionLabel=label('InspectionHistory','','Demo/Muted')
inspectionLabel['propConfig']={'props.text':{'binding':{'type':'property','config':{'path':'view.custom.data.inspection'},'transforms':[{'type':'script','code':'\tif not value or not value.get("checkedAt"):\n\t\treturn "No demo inspection recorded for this batch yet."\n\treturn "Recorded inspection: {0}, {1}.".format(value["checkedAt"], value["decision"])'}]}}}
inspectionButton=button('RecordInspection','Record demo inspection',script='\ttry:\n\t\tself.view.custom.inspectionResult = application.demo.recordInspection(self.view.custom.data.selectedBatch.reference)\n\t\tself.view.refreshBinding("custom.data")\n\texcept:\n\t\tself.view.custom.inspectionResult = "Could not record the inspection. Select a recent batch and try again."')
inspectionButton['propConfig']={'props.enabled':prop('view.custom.data.ready')}
page('Demo/Quality','Quality & batch traceability','Follow a production batch into its process measurements and release decision.',[
 flex('BatchChoice',[label('ChooseBatch','Inspect batch','Demo/SectionTitle'),batchSelector],'row','Demo/Filters'),
 panel('Batch','Batch record','The review decision includes moisture excursions during the run.',[batchHeader,inspectionLabel,inspectionButton,bound_label('InspectionResult','view.custom.inspectionResult','Demo/Muted'),bound_label('BatchProduct','view.custom.data.selectedBatch.product','Demo/Subtitle'),bound_label('QualityDecision','view.custom.data.selectedBatch.quality','Demo/Badge'),table('Checks','view.custom.data.quality',[('measurement','Measurement',240),('value','Result',100),('unit','Unit',80),('specification','Specification',160),('result','Assessment',170)],'300px')]),
 panel('BatchHistory','Production and quality history','Select a batch to inspect the record above.',[table('BatchTable','view.custom.data.orders',ORDER_COLS,'360px',True)]),
 panel('QualityTrend','Moisture history','Use the quality-deviation replay and select Cutting line 02 for the clearest example.',[chart('QualityChart',[('moisture','Moisture (%)','#327656')])])],custom={'inspectionResult':''})

# The form uses the copied reusable fields; state and submit validation live on the view.
fields=[]
spec=[('Reference','TextInputField','Batch reference','DEMO-001',{}),('Product','DropdownInputField','Product','Rolled oats',{'options':[{'label':v,'value':v} for v in ['Rolled oats','Steel-cut oats','Oat flour']]}),('Quantity','NumericInputField','Requested weight (kg)','1250.5',{'decimalAllowed':True,'negativeAllowed':False}),('Bags','NumericInputField','Number of bags','50',{'decimalAllowed':False,'negativeAllowed':False}),('Mode','MultiStateInputField','Run mode','Trial',{'states':[{'value':v,'text':v,'selectedStyle':{'classes':''},'unselectedStyle':{'classes':''}} for v in ['Trial','Production','Hold']]})]
for name,kind,title,initial,extra in spec:
    params={'label':title,'labelFieldWidth':'180px','inputFieldWidth':'280px','required':True,'enabled':True,'input':initial,'value':initial,'validatedInput':initial,'placeholder':'Enter a value...'}|extra
    field=embed(name,'Templates/InputFields/'+kind,params,basis='76px')
    field['props']['style']={'classes':'Demo/FormInput'}
    fields.append(field)
submit=button('Submit','Create demo batch',script='\tif self.view.custom.busy:\n\t\treturn\n\tself.view.custom.busy = True\n\ttry:\n\t\tfrom java.util import UUID\n\t\tif not self.view.custom.requestId:\n\t\t\tself.view.custom.requestId = str(UUID.randomUUID())\n\t\tself.view.custom.result = application.demo.createOrder(dict(self.view.custom.values), self.view.custom.requestId)\n\t\tself.view.refreshBinding("custom.data")\n\texcept:\n\t\tself.view.custom.result = "Could not create the demo batch. Check your values or open Demo health."\n\tfinally:\n\t\tself.view.custom.busy = False')
submit['propConfig']={'props.enabled':expr('{view.custom.validation.valid} && !{view.custom.busy} && {view.custom.data.ready}')}
new=button('NewRequest','Start another demo request',script='\tself.view.custom.requestId = ""\n\tself.view.custom.result = "Edit the fields and create another demo batch."',classes='Demo/QuietButton')
form=panel('Form','Create a production request','Demonstration data only. This action never controls equipment.',fields+[bound_label('FormValidation','view.custom.validation.message','Demo/Muted'),submit,new,bound_label('SubmitResult','view.custom.result','Demo/Status')],basis='560px')
form['props']['style'].update({'maxWidth':'820px'})
values={'onChange':{'enabled':True,'script':'\tself.custom.requestId = ""'},'binding':{'type':'expr-struct','config':{'waitOnAll':True,'struct':{name.lower():'{/root/Form/'+name+'.props.params.value}' for name,*_ in spec}}}}
page('Demo/Operator','An operator workflow','Enter a batch, see validation, and create a persistent demonstration request.',[
 form,panel('RecentRequests','Recent demo requests','Reload the page or open Production planning to see the same submissions.',[table('Requests','view.custom.data.submissions',[('reference','Reference',180),('product','Product',160),('quantity_kg','Weight kg',120),('bags','Bags',100),('mode','Mode',120),('source','Source',150),('submitted','Submitted',160)],'300px')])],
 custom={'values':{},'validation':{'valid':False,'message':'Loading form...'},'busy':False,'requestId':'','result':'No request submitted in this session.'},configs={'custom.values':values,'custom.validation':{'binding':{'type':'property','config':{'path':'view.custom.values'},'transforms':[{'type':'script','code':'\treturn application.demo.validateOrder(value)'}]}}})
health_cards=[]
for name,title,path,unit,hint in [
 ('Freshness','DATA AGE','ageSeconds','sec','Fresh points should be less than 180 seconds old'),
 ('Coverage','HISTORY AVAILABLE','coverageDays','days','Rolling window, automatically maintained'),
 ('LineCount','PRODUCTION LINES','lineCount','','Each line has a coherent process simulation'),
 ('Samples','STORED MEASUREMENTS','sampleCount','','Minute samples across the retained history')]:
    card=embed(name,'Demo/Components/Metric',{'title':title,'unit':unit,'hint':hint},basis='230px',grow=1)
    card['propConfig']={'props.params.value':prop('view.custom.data.health.'+path)}
    health_cards.append(card)
page('Demo/Health','Demo readiness','Check data freshness, history coverage and the automatic retention policy.',[
 flex('HealthCards',health_cards,'row','Demo/Wrap'),
 panel('Readiness','Ready without an open browser','The gateway timer runs every 30 seconds. The demo keeps recording when everyone closes their session.',[
  bound_label('ReadyState','view.custom.data.message','Demo/Status'),
  label('RetentionPolicy','Data is retained for at most 90 days or three calendar months, whichever is shorter. The same policy covers demo requests and inspections.','Demo/Body')]),
 panel('Operations','What happens automatically','The data lifecycle is bounded and repeatable.',[
  label('Policy','Each tick fills missing minute samples after an outage and prunes expired data. Database locking prevents overlapping workers.','Demo/Body'),
  label('ReplayPolicy','Replays select a complete recent cycle from stored data. Each browser session has its own scenario, line and period settings.','Demo/Body'),
  label('StatusPolicy','An unavailable database produces an explicit error state. The screens recover automatically when the connection returns.','Demo/Body'),
  label('MonitoringPolicy','The cloud readiness check runs every six hours and verifies both page availability and the freshness of the underlying data.','Demo/Body')])])
preview=embed('CompactPreview','Demo/Overview',basis='900px')
preview['props']['style']={'width':'390px','maxWidth':'100%','border':'1px solid #dce3d8','borderRadius':'8px','overflow':'hidden'}
page('Demo/ComponentsGallery','Reusable screen components','A small design system with working data and reusable parameter interfaces.',[
 METRICS(),LINES(),panel('GalleryForms','Validated inputs','Text, numeric, dropdown and multistate controls are demonstrated together in the operator workflow.',[button('OpenForm','Try the operator form',page='/operator')]),
 panel('GalleryTrends','A consistent trend pattern','The same time filters, colours and series definitions are reused across screens.',[productionChart()]),
 panel('CompactGallery','Compact screen preview','The real factory overview in a 390 px panel. Scroll inside it to inspect how the shared components adapt.',[preview])])
# Preserve the course observatory. The previous OEE URL now opens the maintained view.
config=json.loads((P/'page-config/config.json').read_text())
for route,title,path in routes:config['pages'][route]={'title':title,'viewPath':path}
config['pages']['/oee']={'title':'Performance','viewPath':'Demo/Performance'}
config['pages']['/demo/input-fields']={'title':'Operator workflow','viewPath':'Demo/Operator'}
for dock in config['sharedDocks']['left']:dock.update({'size':225,'autoBreakpoint':1000,'viewPath':'Sidenav'})
write(P/'page-config/config.json',config)
# Project title appears in the cloud session launcher.
p=ROOT/'projects/oatmakers/project.json';d=json.loads(p.read_text());d['title']='Oatmakers | Connected factory demo';d['description']='A populated factory demonstration with production, performance, quality, operator workflows and rolling history.';write(p,d)
css='''
:root { --demo-ink:#18352a; --demo-muted:#718177; --demo-green:#357a5b; --demo-bg:#f4f5f0; --demo-line:#e0e7dc; }
.psc-Demo\\/Page { container-type:inline-size; container-name:demo; background:var(--demo-bg); color:var(--demo-ink); padding:28px 32px 40px; gap:18px; overflow:auto; font-family:Arial,sans-serif; }
.psc-Demo\\/PageHeader { align-items:center; gap:24px; flex-wrap:wrap; }
.psc-Demo\\/PageTitle { font-size:30px; font-weight:700; line-height:1.3; padding:4px 0 8px; }
.psc-Demo\\/Eyebrow { font-size:10px; font-weight:700; letter-spacing:1.4px; color:#748274; }
.psc-Demo\\/Subtitle { font-size:14px; color:#63766a; white-space:normal; line-height:1.5; }
.psc-Demo\\/SectionTitle { font-size:17px; font-weight:700; white-space:normal; }
.psc-Demo\\/Body { font-size:14px; line-height:1.5; white-space:normal; }
.psc-Demo\\/Muted { font-size:12px; color:#748175; line-height:1.5; white-space:normal; }
.psc-Demo\\/Panel { background:#fff; border:1px solid var(--demo-line); border-radius:12px; padding:20px; gap:12px; min-width:0; box-shadow:0 2px 6px #19372905; }
.psc-Demo\\/Metric { background:#fff; border:1px solid var(--demo-line); border-radius:12px; padding:20px 22px; gap:12px; height:100%; box-sizing:border-box; }
.psc-Demo\\/MetricReading { align-items:baseline; gap:8px; }
.psc-Demo\\/MetricValue { font-size:35px; font-weight:700; color:#234e3b; }
.psc-Demo\\/MetricUnit { font-size:15px; color:#748175; }
.psc-Demo\\/Repeater { gap:14px; overflow:visible; }
.psc-Demo\\/Wrap { flex-wrap:wrap; gap:18px; align-items:stretch; }
.psc-Demo\\/Filters { gap:10px; align-items:center; flex-wrap:wrap; min-height:42px; }
.psc-Demo\\/Select { height:40px; min-height:40px; border-radius:7px; border-color:#dce3d8; background:#fff; font-size:13px; }
.psc-Demo\\/Clock { margin-left:auto; font-size:12px; color:#687b6f; }
.psc-Demo\\/Status { padding:10px 14px; border-radius:7px; font-size:12px; color:#315e43; white-space:normal; }
.psc-Demo\\/Button { background:#357a5b; color:white; border:1px solid #357a5b; border-radius:7px; font-weight:600; padding:8px 16px; }
.psc-Demo\\/Button:disabled { background:#d8e2d8; border-color:#d8e2d8; color:#718175; }
.psc-Demo\\/QuietButton { background:#fff; color:#356b51; border:1px solid #dce3d8; border-radius:7px; padding:8px 14px; font-size:12px; }
.psc-Demo\\/Badge { padding:6px 9px; border-radius:6px; background:#f0f5ee; font-size:11px; font-weight:700; }
.psc-Demo\\/Spread { justify-content:space-between; align-items:center; gap:8px; }
.psc-Demo\\/Facts { gap:15px; color:#6d7d70; font-size:12px; flex-wrap:wrap; }
.psc-Demo\\/LineValue { font-size:27px; font-weight:700; color:#315f45; }
.psc-Demo\\/EventCard { padding:10px 0; gap:6px; border-bottom:1px solid #e5ebe0; }
.psc-Demo\\/Table { font-size:12px; border:1px solid #e9eee5; border-radius:6px; }
.psc-Demo\\/Chart { font-size:11px; min-width:0; }
.psc-Demo\\/Code { font-family:monospace; font-size:12px; white-space:pre-wrap; align-items:flex-start; }
.psc-Demo\\/Navigation { background:#18372c; padding:30px 16px 24px; gap:9px; color:#e8f1e6; height:100%; box-sizing:border-box; font-family:Arial,sans-serif; }
.psc-Demo\\/Brand { font-weight:800; letter-spacing:1.2px; font-size:24px; color:#f3edd9; padding:0 9px; }
.psc-Demo\\/NavEyebrow { font-size:9px; letter-spacing:1.5px; color:#abc2ac; padding:0 9px; }
.psc-Demo\\/NavBadge { font-size:9px; letter-spacing:.6px; color:#d3d6a2; background:#294639; padding:9px; border-radius:5px; margin:18px 0; }
.psc-Demo\\/NavButton { justify-content:flex-start; text-align:left; background:transparent; color:#d5e3d5; border:0; border-radius:7px; padding:11px 13px; font-size:12px; }
.psc-Demo\\/NavButton:hover,.psc-Demo\\/NavButton:focus { background:#315844; color:#fff; }
.psc-Demo\\/NavFooter { font-size:10px; color:#99b59f; padding:4px 9px; white-space:normal; }
@container demo (max-width:650px) { .psc-Demo\\/PageTitle { font-size:25px; white-space:normal; } .psc-Demo\\/Wrap > * { flex-basis:100% !important; } .psc-Demo\\/FormInput { flex-basis:110px !important; } .psc-Demo\\/Clock { margin-left:0; } .psc-Demo\\/Filters { align-items:stretch; } }
@media(max-width:1100px) { .psc-Demo\\/Page { padding:20px; } .psc-Demo\\/MetricValue { font-size:28px; } }
@media(max-width:650px) { .psc-Demo\\/Page { padding:16px; gap:14px; } .psc-Demo\\/PageTitle { font-size:25px; } .psc-Demo\\/Clock { margin-left:0; } .psc-Demo\\/Panel { padding:15px; } .psc-Demo\\/Wrap > * { flex-basis:100% !important; } .psc-Demo\\/Repeater { height:auto; min-height:150px; } }
'''
p=P/'stylesheet';p.mkdir(exist_ok=True);existing=(p/'stylesheet.css').read_text() if (p/'stylesheet.css').exists() else '';marker='/* Oatmakers customer demo */';existing=existing.split(marker)[0];(p/'stylesheet.css').write_text(existing+'\n'+marker+'\n'+css);resource(p,['stylesheet.css'])
print('Built',len(routes),'demo pages and shared components.')
