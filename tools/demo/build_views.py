"""Build the operational demo with Mustry UI controls and live SCADA."""
import base64,copy,json,shutil
from view_primitives import *
M='mustrysolutions.perspective.'
COLORS=['#2d8962','#428ac3','#c59139']
LINES=[(0,'All lines'),(1,'Rolling line 01'),(2,'Cutting line 02'),(3,'Milling line 03')]
METRICS={'rate':('Throughput','Throughput','kg/h'),'temperature':('Temperature','Temperature','°C'),'moisture':('Moisture','Moisture','%'),'pressure':('Pressure','Pressure','bar'),'power':('Power','Power','kW')}

def bind_script(path,code):
    return {'binding':{'type':'property','config':{'path':path},'transforms':[{'type':'script','code':code}]}}
def struct_binding(values,code):
    return {'binding':{'type':'expr-struct','config':{'waitOnAll':True,'struct':values},'transforms':[{'type':'script','code':code}]}}
def action(script):return {'component':{'onActionPerformed':{'type':'script','scope':'G','config':{'script':script}}}}
def select(name,options,path,width='200px'):
    n=node('ia.input.dropdown',name,{'options':[{'value':v,'label':l} for v,l in options],'value':options[0][0],'search':{'enabled':False},'style':{'classes':'Demo/Select','overflow':'visible'}},basis=width)
    n['propConfig']={'props.value':prop(path,True)};return n

def grid(name,source,columns,key='reference',height='350px',selectable=False):
    cols=[]
    for field,title,width in columns:
        col={'field':field,'header':title,'width':width}
        if field in ('produced_kg','target_kg','good_kg','quantity_kg','bags','minutes','lost_kg'):
            col.update({'type':'number','align':'right','decimals':1 if field.endswith('_kg') else 0})
        if field in ('status','quality','result'):
            col['cellStyles']=[{'equals':v,'color':c,'background':bg} for v,c,bg in [('Scheduled','#6c7b84','#f1f4f6'),('In production','#267653','#e8f5ec'),('Completed','#52685b','#eff5ef'),('Quality review','#a5640c','#fff4db'),('Review required','#a5640c','#fff4db'),('Released','#267653','#e8f5ec'),('Within limits','#267653','#e8f5ec')]]
        cols.append(col)
    n=node(M+'input.datagrid',name,{'config':{'columns':cols,'idField':key,'rowHeight':44,'locale':'en-GB','rowSelect':'single' if selectable else 'none','showToolbar':True,'showExport':True,'editable':False,'emptyMessage':'No records for the selected range.'},'data':{'rows':[]},'state':{'selection':[]},'style':{'classes':'Demo/DataGrid'}},basis=height)
    n['propConfig']={'props.data.rows':prop(source)};return n

def picker(name='DateRange'):
    presets=[{'label':title,'type':'rolling','rolling':{'amount':amount,'unit':unit}} for title,amount,unit in [('Last 15 min',0.25,'hours'),('Last hour',1,'hours'),('Last 8 hours',8,'hours'),('Last 24 hours',24,'hours'),('Last 7 days',7,'days'),('Last 30 days',30,'days')]]
    n=node(M+'input.datetimerangepicker',name,{'config':{'display':'popover','layout':'twoMonths','granularity':'second','timezone':'Europe/Brussels','locale':'en-GB','disableDates':'future','spanDays':{'max':90},'showPresets':True,'showClear':False,'popover':{'placeholder':'Choose history range','closeOnSelect':True,'dateFormat':'DD/MM/YYYY'},'presets':presets,'realtime':{'enabled':True,'refreshSeconds':5}},'selection':{'rollingAmount':1,'rollingUnit':'hours'},'style':{'overflow':'visible','classes':'Demo/DateRange'}},basis='390px')
    n['propConfig']={'props.config.dateBounds.earliest':{'binding':{'type':'expr','config':{'expression':'dateFormat(addDays(now(60000), -90), "yyyy-MM-dd")'}}}}
    return n

# Common visual components.
metric=flex('root',[bound_label('Title','view.params.title','Demo/Eyebrow'),flex('Reading',[bound_label('Value','view.params.value','Demo/MetricValue'),bound_label('Unit','view.params.unit','Demo/MetricUnit')],'row','Demo/MetricReading'),bound_label('Hint','view.params.hint','Demo/Muted')],classes='Demo/Metric')
view('Demo/Components/Metric',metric,params={'title':'','value':'','unit':'','hint':''},height=135)

line_children=[flex('Heading',[bound_label('Name','view.params.name','Demo/SectionTitle'),bound_label('State','view.params.state','Demo/Badge')],'row','Demo/Spread'),bound_label('Product','view.params.product','Demo/Muted'),label('SpeedCaption','LIVE THROUGHPUT','Demo/Eyebrow')]
rate=bound_label('Rate','view.params.rate','Demo/LineValue');rate['propConfig']['props.text']=bind_script('view.params.rate','\treturn "{0:,.0f} kg/h".format(value or 0)');line_children.append(rate)
readings=[]
for key in ['temperature','moisture','pressure']:
    b=button(key.title(),'',script='\tapplication.demo.showHistory(self.view.params.lineNumber, '+json.dumps(key)+')',classes='Demo/ReadingButton')
    b['position']={'basis':'90px','grow':1,'shrink':1}
    b['propConfig']={'props.text':bind_script('view.params.'+key,'\treturn "{0:.1f} {1}".format(value or 0, '+'u'+json.dumps(METRICS[key][2])+')')};readings.append(b)
line_children += [flex('Readings',readings,'row','Demo/Wrap'),button('Scada','Open SCADA',script='\tself.session.custom.demo.scadaLine = self.view.params.lineNumber\n\tsystem.perspective.navigate("/scada")',classes='Demo/QuietButton')]
line_root=flex('root',line_children,classes='Demo/Panel');line_root['children'][0]['children'][1]['propConfig']['props.style.color']=prop('view.params.colour')
view('Demo/Components/LineCard',line_root,params={'lineNumber':1,'name':'','state':'','product':'','rate':0,'temperature':0,'moisture':0,'pressure':0,'colour':'#2d8962'},height=270)

# Shared history view: the Mustry picker output is the source of the query.
control=flex('Controls',[picker(),select('Line',LINES,'view.params.lineNumber'),select('Measurement',[(k,v[1]) for k,v in METRICS.items()],'view.params.metric')],'row','Demo/Filters')
control['children'][1]['propConfig']['position.display']=prop('view.params.showSelectors');control['children'][2]['propConfig']['position.display']=prop('view.params.showSelectors')
hchart=chart('HistoryPlot',[(f'line{i}',name,COLORS[i-1]) for i,name in LINES if i],source='view.custom.history.points',height='320px')
hchart['position']={'basis':'0px','grow':1,'shrink':1};hchart['props']['style'].update({'minHeight':'240px'})
for s in hchart['props']['series']:
    s['line']['appearance']['fill']['opacity']=0;s['line']['appearance']['stroke']['width']=2
hchart['props']['xAxes'][0]['date']['format']='dd MMM HH:mm';hchart['props']['xAxes'][0]['appearance']['grid']['minDistance']=110
hchart['props']['yAxes'][0]['value']['range']['min']=''
for i in range(3):
    hchart['propConfig'][f'props.series[{i}].visible']=expr('{view.params.lineNumber} = 0 || {view.params.lineNumber} = '+str(i+1))
    hchart['propConfig'][f'props.series[{i}].hiddenInLegend']=expr('{view.params.lineNumber} != 0 && {view.params.lineNumber} != '+str(i+1))
hchart['propConfig']['props.yAxes[0].label.enabled']={'persistent':True};hchart['props']['yAxes'][0]['label']['enabled']=True
hchart['propConfig']['props.yAxes[0].label.text']=bind_script('view.params.metric','\treturn application.demo.METRICS[value][2]')
history_root=flex('root',[control,hchart,bound_label('HistoryMessage','view.custom.history.message','Demo/Muted')],classes='Demo/HistoryRoot')
range_cfg={'binding':{'type':'expr-struct','config':{'waitOnAll':True,'struct':{'start':'{/root/Controls/DateRange.props.output.startEpochMs}','end':'{/root/Controls/DateRange.props.output.endEpochMs}','valid':'{/root/Controls/DateRange.props.output.isValid}','realtime':'{/root/Controls/DateRange.props.output.isRealtime}'}}}}
view('Demo/HistoryChart',history_root,params={'lineNumber':0,'metric':'rate','showSelectors':True,'range':{}},custom={'range':{'start':0,'end':0,'valid':False,'realtime':True},'history':{'points':[],'message':'Select a recorded range.'}},config={'custom.range':range_cfg,'params.lineNumber':{'paramDirection':'inout','persistent':True},'params.metric':{'paramDirection':'inout','persistent':True},'params.range':dict(prop('view.custom.range'),paramDirection='output'),'custom.history':struct_binding({'range':'{view.custom.range}','line':'{view.params.lineNumber}','metric':'{view.params.metric}','refresh':'now(5000)'},'\treturn application.demo.history(value["range"]["start"], value["range"]["end"], value["line"], value["metric"])')},height=430)

# Minimal fixed-height headers leave the operational content its space.
EMPTY_LIVE={'ready':False,'metrics':[],'lines':[],'trend':[],'updatedEpochMs':0,'updatedAt':'','shiftStart':''}
def page(name,title,subtitle,body,custom=None,config=None,live_header=True):
    header=flex('Header',[flex('Identity',[label('Eyebrow','OATMAKERS / LIVE OPERATIONS','Demo/Eyebrow'),label('Title',title,'Demo/PageTitle'),label('Subtitle',subtitle,'Demo/Subtitle')],grow=1),label('Mode','SIMULATED FACTORY','Demo/DemoBadge')],'row','Demo/PageHeader')
    children=[header]
    if live_header:
        live_label=label('LiveStatus','','Demo/LiveStatus')
        live_label['propConfig']={'props.text':expr('if({view.custom.live.ready}, "Live · recorded at " + {view.custom.live.updatedAt} + " · updates every 5 seconds", "Live telemetry is unavailable")'),'props.style.color':expr('if({view.custom.live.ready}, "#277b57", "#b66622")')}
        children.append(live_label)
    cfg={'custom.live':struct_binding({'tick':'now(5000)'},'\treturn application.demo.live()')} if live_header else {}
    cfg.update(config or {})
    return view(name,flex('root',children+body,classes='Demo/Page'),custom=({'live':EMPTY_LIVE} if live_header else {})|(custom or {}),config=cfg)

def line_cards():
    return repeater('Lines','Demo/Components/LineCard','view.custom.live.lines','auto')
def live_metrics():
    n=repeater('LiveMetrics','Demo/Components/Metric','view.custom.live.metrics','auto');return n

live_plot=chart('LiveTrend',[('rate','Throughput (t/h)','#2d8962')],source='view.custom.live.trend',height='235px');live_plot['props']['legend']['enabled']=False
page('Demo/Overview','What is happening now','Live production rates, shift output and process alerts.',[
 live_metrics(),line_cards(),panel('LiveTrendPanel','Factory throughput','The latest ten minutes of recorded five-second telemetry.',[live_plot,button('History','Choose a history range',page='/performance',classes='Demo/QuietButton')],grow=0)])

# The resource timeline owns its window; only visible batches are fetched.
resources=[{'id':str(i),'label':name,'group':'Oat processing','color':COLORS[i-1]} for i,name in LINES if i]
timeline=node(M+'display.resourcetimeline','Timeline',{'config':{'resources':resources,'rowHeight':76,'timezone':'Europe/Brussels','locale':'en-GB','showToolbar':True,'showMiniNav':True,'showLegend':True,'refreshSeconds':5,'editable':False,'selectable':False,'builtInEditor':False,'showExport':True,'categories':[{'id':k,'label':t,'color':c} for k,t,c in [('planned','Scheduled','#7790a7'),('running','In production','#2d8962'),('quality','Quality review','#c89128'),('complete','Completed','#b0bdb4')]],'shifts':[{'label':'Early','start':'06:00'},{'label':'Late','start':'14:00'},{'label':'Night','start':'22:00'}]},'data':{'events':[]},'state':{'zoom':'shift','followNow':True},'style':{'classes':'Demo/PlanningTimeline'}},basis='480px')
timeline['propConfig']={'props.data.events':prop('view.custom.events')}
timeline['events']={'component':{'onEventClick':{'type':'script','scope':'G','config':{'script':'\tapplication.demo.showBatch(event.id)'}}}}
page('Demo/Production','Production planning','Browse shifts, pan through the schedule and open a batch for details.',[
 timeline,label('PlanningHelp','Use Hour, Day, Shift or Week to change the scale. Click a batch to inspect its production and quality record.','Demo/Muted')],custom={'events':[]},config={'custom.events':struct_binding({'start':'{/root/Timeline.props.output.visibleStartMs}','end':'{/root/Timeline.props.output.visibleEndMs}','refresh':'now(5000)'},'\treturn application.demo.timeline(value["start"], value["end"])')})

history=embed('History','Demo/HistoryChart',{'lineNumber':0,'metric':'rate','showSelectors':True},basis='460px')
page('Demo/Performance','Performance & history','Pick exact dates or a live preset. Every chart uses that recorded range.',[
 history,repeater('Metrics','Demo/Components/Metric','view.custom.summary.metrics','auto'),
 grid('Losses','view.custom.summary.losses',[('reason','Loss reason',250),('minutes','Line minutes',140),('lost_kg','Lost output kg',160)],key='reason',height='250px')],custom={'summary':{'metrics':[],'losses':[]}},config={'custom.summary':struct_binding({'start':'{/root/History.props.params.range.start}','end':'{/root/History.props.params.range.end}','line':'{/root/History.props.params.lineNumber}','refresh':'now(10000)'},'\treturn application.demo.rangeSnapshot(value["start"], value["end"], value["line"])')},live_header=False)

# One modern record grid, with an explicit inspect action.
quality_picker=picker('QualityRange')
quality_picker['props']['selection']['rollingAmount']=24
qgrid=grid('BatchGrid','view.custom.batches',[('reference','Batch',190),('product','Product',160),('line','Line',170),('good_kg','Good output kg',150),('quality','Quality decision',170)],height='480px',selectable=True)
inspect=button('InspectBatch','Inspect selected batch',script='\tapplication.demo.showBatch(self.view.custom.selected)',classes='Demo/Button');inspect['propConfig']={'props.enabled':expr('len({view.custom.selected}) > 0')}
page('Demo/Quality','Quality & traceability','Find a production batch and inspect its measurements.',[
 flex('QualityFilters',[quality_picker,inspect],'row','Demo/Filters'),qgrid],custom={'batches':[],'selected':''},config={'custom.batches':struct_binding({'start':'{/root/QualityFilters/QualityRange.props.output.startEpochMs}','end':'{/root/QualityFilters/QualityRange.props.output.endEpochMs}','refresh':'now(10000)'},'\treturn application.demo.batches(value["start"], value["end"])'),'custom.selected':bind_script('/root/BatchGrid.props.state.selection','\treturn str(value[0]) if value else ""')},live_header=False)

# Detail popups have their own range-controlled history and compact measurements.
qc=button('Inspect','Record demo inspection',script='\ttry:\n\t\tself.view.custom.result = application.demo.recordInspection(self.view.params.reference)\n\t\tself.view.refreshBinding("custom.batch")\n\texcept (Exception, application.demo.JavaException):\n\t\tself.view.custom.result = "Inspection could not be recorded for this batch."')
qc['propConfig']={'props.enabled':expr('{view.custom.batch.available} && {view.custom.batch.status} != "Scheduled"')}
batch_cards=[]
for name,title,key,unit in [('Output','GOOD OUTPUT','good_kg','kg'),('Moisture','PEAK MOISTURE','peak_moisture','%'),('Temperature','AVERAGE TEMPERATURE','temperature','°C')]:
    card=embed(name,'Demo/Components/Metric',{'title':title,'unit':unit,'hint':''},basis='240px',grow=1)
    card['propConfig']={'props.params.value':bind_script('view.custom.batch','\treturn value.get("'+key+'", "n/a")')};batch_cards.append(card)
batch_root=flex('root',[bound_label('BatchTitle','view.params.reference','Demo/SectionTitle'),bound_label('Product','view.custom.batch.product','Demo/Subtitle'),bound_label('Status','view.custom.batch.status','Demo/Badge'),flex('Measurements',batch_cards,'row','Demo/Wrap'),qc,bound_label('Result','view.custom.result','Demo/Muted')],classes='Demo/PopupRoot')
view('Demo/BatchDetails',batch_root,params={'reference':''},custom={'batch':{'available':False,'product':'','status':'Loading'},'result':''},config={'custom.batch':bind_script('view.params.reference','\treturn application.demo.batchDetails(value)')},height=400)

# The request form never gets its own scroll container. The grid owns its scroll.
fields=[]
spec=[('Reference','TextInputField','Batch reference','DEMO-001',{}),('Product','DropdownInputField','Product','Rolled oats',{'options':[{'label':v,'value':v} for v in ['Rolled oats','Steel-cut oats','Oat flour']]}),('Quantity','NumericInputField','Weight (kg)','1250.5',{'decimalAllowed':True,'negativeAllowed':False}),('Bags','NumericInputField','Bags','50',{'decimalAllowed':False,'negativeAllowed':False}),('Mode','MultiStateInputField','Run mode','Trial',{'states':[{'value':v,'text':v,'selectedStyle':{'classes':''},'unselectedStyle':{'classes':''}} for v in ['Trial','Production','Hold']]})]
for name,kind,title,initial,extra in spec:
    field=embed(name,'Templates/InputFields/'+kind,{'label':title,'labelFieldWidth':'130px','inputFieldWidth':'220px','input':initial,'value':initial,'validatedInput':initial,'required':True,'enabled':True,'placeholder':'Enter a value...'}|extra,basis='66px')
    field['props']['style']={'overflow':'visible'};fields.append(field)
submit=button('Submit','Create demo request',script='\tif self.view.custom.busy:\n\t\treturn\n\tself.view.custom.busy = True\n\ttry:\n\t\tif not self.view.custom.requestId:\n\t\t\tself.view.custom.requestId = application.demo.newRequestId()\n\t\tself.view.custom.result = application.demo.createOrder(dict(self.view.custom.values),self.view.custom.requestId)\n\t\tself.view.refreshBinding("custom.requests")\n\texcept (Exception, application.demo.JavaException):\n\t\tself.view.custom.result = "Could not create the request. Review the inputs and connection."\n\tfinally:\n\t\tself.view.custom.busy = False')
submit['propConfig']={'props.enabled':expr('{view.custom.validation.valid} && !{view.custom.busy} && {view.custom.live.ready}')}
form=panel('Form','Create a production request','Demonstration records only.',fields+[bound_label('Validation','view.custom.validation.message','Demo/Muted'),submit,bound_label('Result','view.custom.result','Demo/Status')],basis='450px',grow=0);form['props']['style'].update({'overflow':'visible','alignSelf':'flex-start'})
request_grid=grid('Requests','view.custom.requests',[('reference','Reference',190),('product','Product',160),('quantity_kg','Weight kg',120),('bags','Bags',80),('mode','Mode',110),('submitted','Created',140)],height='0px');request_grid['position']={'basis':'0px','grow':1,'shrink':1}
request_panel=panel('RequestList','Production requests','Your saved requests remain available after reloading.',[request_grid],basis='560px',grow=1);request_panel['props']['style'].update({'height':'calc(100vh - 215px)','minHeight':'400px','overflow':'hidden'})
workspace=flex('Workspace',[form,request_panel],'row','Demo/Workspace')
page('Demo/Operator','Operator workflow','Create a request while the production list stays in view.',[workspace],custom={'values':{},'validation':{'valid':False,'message':''},'requestId':'','busy':False,'result':'','requests':[]},config={'custom.values':dict(struct_binding({name.lower():'{/root/Workspace/Form/'+name+'.props.params.value}' for name,*_ in spec},'\treturn value'),onChange={'enabled':True,'script':'\tself.custom.requestId = ""'}),'custom.validation':bind_script('view.custom.values','\treturn application.demo.validateOrder(value)'),'custom.requests':struct_binding({'refresh':'now(5000)'},'\treturn application.demo.recentOrders()')})

# Generic tag faceplate: live tag subscriptions, not per-view random values.
inst_root=flex('root',[bound_label('Name','view.params.label','Demo/TagName'),flex('Reading',[label('Value','','Demo/TagValue'),bound_label('Unit','view.params.unit','Demo/TagUnit')],'row','Demo/MetricReading')],classes='Demo/TagFace')
inst_root['children'][1]['children'][0]['propConfig']={'props.text':expr('if({view.custom.fresh}, numberFormat({view.custom.value}, "#,##0.0"), "n/a")')}
inst_root['events']={'dom':{'onClick':{'type':'script','scope':'G','config':{'script':'\tapplication.demo.showHistory(self.view.params.lineNumber, self.view.params.metric)'}}}}
view('Demo/ScadaViews/Instrument',inst_root,params={'lineNumber':1,'metric':'temperature','tag':'Temperature','label':'Temperature','unit':'°C'},custom={'value':0,'lastUpdate':0,'fresh':False},config={'custom.value':{'binding':{'type':'tag','config':{'mode':'indirect','tagPath':'[default]OatmakersDemo/Line{line}/{tag}','references':{'line':'{view.params.lineNumber}','tag':'{view.params.tag}'}}}},'custom.lastUpdate':{'binding':{'type':'tag','config':{'mode':'indirect','tagPath':'[default]OatmakersDemo/Line{line}/LastUpdate','references':{'line':'{view.params.lineNumber}'}}}},'custom.fresh':expr('dateDiff({view.custom.lastUpdate}, now(1000), "second") < 30')},height=60)
layouts=json.loads((ROOT/'tools/demo/scada-assets/layout.json').read_text())
# One faceplate per recorded line measurement, placed around the original geometry.
for area,positions in {
    'peeling':[('rate',160,20),('pressure',600,300),('temperature',590,430),('moisture',10,610),('power',650,770)],
    'heating':[('pressure',270,70),('temperature',640,335),('power',950,590),('rate',45,850),('moisture',715,1100)]
}.items():
    layouts[area]['instruments']=[{'metric':metric,'x':x,'y':y,'width':280 if area=='heating' else 230,'height':80} for metric,x,y in positions]

for area,cfg in layouts.items():
    width=cfg['width']+120;height=cfg['height']+120
    encoded=base64.b64encode((ROOT/('tools/demo/scada-assets/'+area+'.svg')).read_bytes()).decode()
    background=node('ia.display.image','OriginalDrawing',{'source':'data:image/svg+xml;base64,'+encoded,'fit':{'mode':'fill'},'style':{'pointerEvents':'none'}});background['position']={'x':60,'y':60,'width':cfg['width'],'height':cfg['height']}
    nodes=[background]
    for index,instrument in enumerate(cfg['instruments']):
        metric=instrument['metric'];tag,title,unit=METRICS[metric]
        e=embed('Measurement'+str(index),'Demo/ScadaViews/Instrument',{'metric':metric,'tag':tag,'label':title,'unit':unit})
        e['position']={'x':instrument['x']+60,'y':instrument['y']+60,'width':instrument['width'],'height':80}
        e['propConfig']={'props.params.lineNumber':prop('view.params.lineNumber')};nodes.append(e)
    root=node('ia.container.coord','root',{'mode':'fixed','style':{'backgroundColor':'#f7faf7','overflow':'visible'}},nodes)
    d=view('Demo/ScadaViews/'+area.title(),root,params={'lineNumber':1},height=height);d['props']['defaultSize']['width']=width;write(V/('Demo/ScadaViews/'+area.title())/'view.json',d)
scada_controls=flex('Controls',[select('Line',LINES[1:],'session.custom.demo.scadaLine'),select('Area',[('peeling','Peeling & conveying'),('heating','Heat treatment')],'session.custom.demo.scadaArea'),label('Hint','Drag to pan, wheel to zoom. Click a measurement for its history.','Demo/Muted')],'row','Demo/Filters')
pan=node(M+'display.panzoomview','ScadaMap',{'config':{'viewPath':'Demo/ScadaViews/Peeling','viewParams':[{'name':'lineNumber','value':1}],'contentWidth':0,'contentHeight':0,'minZoom':0.25,'maxZoom':4,'showControls':True,'showMinimap':True,'showPoiList':True,'wheelZoom':True,'doubleClickZoom':True,'flyToMs':350,'home':{'x':-1,'y':-1,'zoom':0}},'data':{'pois':[]},'style':{'classes':'Demo/ScadaMap'}},basis='0px',grow=1)
pan['position']['shrink']=1;pan['props']['style']['minHeight']='480px'
pan['propConfig']={'props.config.viewPath':expr('if({session.custom.demo.scadaArea} = "heating", "Demo/ScadaViews/Heating", "Demo/ScadaViews/Peeling")'),'props.config.viewParams[0].value':prop('session.custom.demo.scadaLine'),'props.data.pois':bind_script('session.custom.demo.scadaArea','\tif value == "heating":\n\t\treturn [{"name":"Heater", "x":500,"y":600,"zoom":1.1},{"name":"Heat exchanger","x":850,"y":900,"zoom":1.4}]\n\treturn [{"name":"Infeed", "x":300,"y":150,"zoom":1.5},{"name":"Peeling", "x":580,"y":490,"zoom":1.3},\n\t\t{"name":"Discharge", "x":850,"y":710,"zoom":1.4}]')}
page('Demo/SCADA','SCADA','Live process drawings with smooth navigation and tag history.',[scada_controls,pan])
# This page uses the canvas height, not an outer page scrollbar.
p=V/'Demo/SCADA/view.json';d=json.loads(p.read_text());d['root']['props']['style']['classes']='Demo/Page Demo/ScadaPage';write(p,d)

popup_history=embed('History','Demo/HistoryChart',{'showSelectors':False},basis='0px',grow=1);popup_history['position']['shrink']=1;popup_history['propConfig']={'props.params.lineNumber':prop('view.params.lineNumber'),'props.params.metric':prop('view.params.metric')}
view('Demo/TagHistory',flex('root',[bound_label('Title','view.params.title','Demo/SectionTitle'),bound_label('Tag','view.params.tagPath','Demo/Muted'),popup_history],classes='Demo/PopupRoot'),params={'lineNumber':1,'metric':'temperature','title':'Temperature','tagPath':''},height=560)

health_cards=[]
for name,title,key,unit,hint in [('Age','LIVE DATA AGE','liveAgeSeconds','sec','Five-second recorded telemetry'),('History','HISTORY','coverageDays','days','Minute history, capped at three months'),('Lines','LINES','lineCount','','Three simulated production lines')]:
    card=embed(name,'Demo/Components/Metric',{'title':title,'unit':unit,'hint':hint},basis='240px',grow=1);card['propConfig']={'props.params.value':prop('view.custom.health.'+key)};health_cards.append(card)
page('Demo/Health','Demo health','Data freshness and automatic retention.',[flex('Metrics',health_cards,'row','Demo/Wrap'),label('Policy','Five-second telemetry is retained for 48 hours. Minute history, demo requests and inspections are retained for at most 90 days or three calendar months.','Demo/Body')],custom={'health':{'liveAgeSeconds':'n/a','coverageDays':'n/a','lineCount':'n/a'}},config={'custom.health':struct_binding({'refresh':'now(5000)'},'\treturn application.demo.health()')})

routes=[('/','Factory overview','Demo/Overview'),('/scada','SCADA','Demo/SCADA'),('/production','Production planning','Demo/Production'),('/performance','Performance','Demo/Performance'),('/quality','Quality & traceability','Demo/Quality'),('/operator','Operator workflow','Demo/Operator')]
nav=[label('Brand','OATMAKERS','Demo/Brand'),label('BrandDetail','CONNECTED OPERATIONS','Demo/NavEyebrow'),label('DemoLabel','LIVE SIMULATION','Demo/NavBadge')]
for i,(path,title,_) in enumerate(routes):
    b=button('Nav'+str(i),title,page=path,classes='Demo/NavButton');b['position']['basis']='45px';b['propConfig']={'props.style.backgroundColor':expr('if({page.props.path} = '+json.dumps(path)+', "#315844", "transparent")')};nav.append(b)
nav += [flex('Spacer',[],grow=1),button('Health','Demo health',page='/demo/health',classes='Demo/NavButton'),label('Footer','Mustry Solutions','Demo/NavFooter')]
view('Sidenav',flex('root',nav,classes='Demo/Navigation'),height=900)
config=json.loads((P/'page-config/config.json').read_text());config['pages'].pop('/components',None)
for route,title,path in routes:config['pages'][route]={'title':title,'viewPath':path}
config['pages']['/process']={'title':'SCADA','viewPath':'Demo/SCADA'};config['pages']['/demo/health']={'title':'Demo health','viewPath':'Demo/Health'}
config['pages']['/oee']={'title':'Performance','viewPath':'Demo/Performance'};config['pages']['/demo/input-fields']={'title':'Operator workflow','viewPath':'Demo/Operator'}
write(P/'page-config/config.json',config)
write(P/'session-props/props.json',{'custom':{'demo':{'scadaLine':1,'scadaArea':'peeling'}},'props':{'theme':'light'}});resource(P/'session-props',['props.json'])
for old in ['Demo/ComponentsGallery','Demo/Process']:
    if (V/old).exists():shutil.rmtree(V/old)

css='''
:root { --demo-ink:#1c382c; --demo-muted:#738579; --demo-bg:#f3f6f2; --demo-line:#e0e9df; }
.psc-Demo\\/Page { container-type:inline-size; container-name:demo; background:var(--demo-bg); color:var(--demo-ink); padding:24px 30px; gap:18px; overflow:auto; font-family:Arial,sans-serif; }
.psc-Demo\\/PageHeader { align-items:center; justify-content:space-between; gap:20px; overflow:visible; }
.psc-Demo\\/PageTitle { font-size:28px; font-weight:700; line-height:1.3; padding:4px 0; white-space:normal; }
.psc-Demo\\/Eyebrow { font-size:10px; font-weight:700; letter-spacing:1.3px; color:#718573; }
.psc-Demo\\/Subtitle { font-size:13px; color:#6a7e70; line-height:1.5; white-space:normal; }
.psc-Demo\\/SectionTitle { font-size:17px; font-weight:700; white-space:normal; }
.psc-Demo\\/Body { font-size:14px; line-height:1.5; white-space:normal; }
.psc-Demo\\/Muted { font-size:12px; color:#748175; line-height:1.5; white-space:normal; }
.psc-Demo\\/Panel { background:#fff; border:1px solid var(--demo-line); border-radius:10px; padding:20px; gap:12px; min-width:0; overflow:visible; }
.psc-Demo\\/Metric { background:white; border:1px solid var(--demo-line); border-radius:10px; padding:18px 20px; gap:10px; height:100%; box-sizing:border-box; }
.psc-Demo\\/MetricReading { align-items:baseline; gap:8px; }
.psc-Demo\\/MetricValue { font-size:32px; font-weight:700; font-variant-numeric:tabular-nums; color:#234e3b; }
.psc-Demo\\/MetricUnit { font-size:14px; color:#748175; }
.psc-Demo\\/Repeater { gap:14px; overflow:visible; }
.psc-Demo\\/Wrap,.psc-Demo\\/Workspace { gap:18px; align-items:stretch; overflow:visible; }
.psc-Demo\\/Filters { gap:10px; align-items:center; min-height:44px; overflow:visible !important; position:relative; z-index:4; }
.psc-Demo\\/Select { height:40px; min-height:40px; border-radius:6px; border-color:#dce5da; background:white; font-size:13px; overflow:visible; }
.psc-Demo\\/DateRange { min-height:40px; overflow:visible !important; --dtrp-accent:#327d58; --dtrp-bg:#fff; }
.psc-Demo\\/HistoryRoot { overflow:visible; gap:10px; min-height:0; }
.psc-Demo\\/PopupRoot { overflow:visible !important; background:white; padding:20px; gap:14px; min-height:0; }
.psc-Demo\\/DemoBadge { padding:7px 12px; border-radius:6px; background:#e5efe4; color:#55764b; font-size:10px; letter-spacing:1px; }
.psc-Demo\\/LiveStatus { font-size:12px; color:#277b57; }
.psc-Demo\\/Status { padding:10px; border-radius:6px; font-size:12px; color:#315e43; white-space:normal; }
.psc-Demo\\/Button { background:#327d58; color:white; border:1px solid #327d58; border-radius:6px; padding:8px 16px; font-weight:600; }
.psc-Demo\\/Button:disabled { background:#dce5db; border-color:#dce5db; color:#748475; }
.psc-Demo\\/QuietButton,.psc-Demo\\/ReadingButton { background:#f8faf7; color:#35674e; border:1px solid #e1e8dc; border-radius:6px; padding:8px 12px; font-size:12px; }
.psc-Demo\\/ReadingButton { font-variant-numeric:tabular-nums; background:#f2f7f0; }
.psc-Demo\\/Badge { padding:5px 8px; border-radius:5px; background:#eef5ec; font-size:11px; font-weight:700; }
.psc-Demo\\/Spread { justify-content:space-between; align-items:center; gap:8px; }
.psc-Demo\\/LineValue { font-size:28px; font-weight:700; font-variant-numeric:tabular-nums; color:#2d7150; }
.psc-Demo\\/Chart { font-size:11px; min-width:0; }
.psc-Demo\\/DataGrid { --dg-accent:#347857; --dg-bg:#fff; --dg-header-bg:#f2f6ef; --dg-border:#e5ece0; --dg-text:#284532; --dg-muted:#77897c; border:1px solid #e1e9dd; border-radius:8px; min-height:180px; }
.psc-Demo\\/PlanningTimeline { --tml-accent:#347857; --tml-bg:#fff; --tml-group-bg:#f1f6ef; --tml-border:#e0e9da; --tml-line:#edf1e9; --tml-text:#294231; border:1px solid #dfe8da; border-radius:10px; background:white; }
.psc-Demo\\/ScadaPage { overflow:hidden; }
.psc-Demo\\/ScadaMap { border:1px solid #dce6d8; border-radius:10px; --pz-canvas:#f7faf7; --pz-accent:#347857; }
.psc-Demo\\/TagFace { background:#ffffffec; border:1px solid #d5e3d1; border-radius:6px; padding:6px 10px; gap:3px; cursor:pointer; box-sizing:border-box; overflow:visible; }
.psc-Demo\\/TagFace:hover { border-color:#418666; box-shadow:0 2px 8px #315c3920; }
.psc-Demo\\/TagName { font-size:15px; font-weight:600; color:#55735c; }
.psc-Demo\\/TagValue { font-size:26px; font-weight:700; font-variant-numeric:tabular-nums; color:#2e6d4c; }
.psc-Demo\\/TagUnit { font-size:15px; color:#758677; }
.psc-Demo\\/Navigation { background:#1d382c; padding:28px 16px 20px; gap:9px; color:#e7eee2; height:100%; box-sizing:border-box; font-family:Arial,sans-serif; }
.psc-Demo\\/Brand { font-size:24px; font-weight:800; letter-spacing:1.2px; color:#f4eedb; padding:0 9px; }
.psc-Demo\\/NavEyebrow { font-size:9px; letter-spacing:1.3px; color:#abc0a9; padding:0 9px; }
.psc-Demo\\/NavBadge { font-size:9px; color:#cbdba6; background:#2e4b39; padding:9px; border-radius:5px; margin:15px 0; }
.psc-Demo\\/NavButton { background:transparent; color:#d9e4d6; border:0; border-radius:6px; padding:10px 12px; font-size:12px; }
.psc-Demo\\/NavButton:hover { background:#36543f; }
.psc-Demo\\/NavFooter { font-size:10px; color:#9db69e; padding:4px 9px; }
@container demo (max-width:900px) { .psc-Demo\\/Workspace { flex-wrap:wrap !important; } .psc-Demo\\/Workspace > * { flex-basis:100% !important; } .psc-Demo\\/PageHeader { flex-wrap:wrap !important; } }
@media(max-width:650px) { .psc-Demo\\/Page { padding:14px; } .psc-Demo\\/PageTitle { font-size:24px; } .psc-Demo\\/Filters { flex-wrap:wrap !important; } }
'''
p=P/'stylesheet';(p/'stylesheet.css').write_text(css);resource(p,['stylesheet.css'])
print('Built operational screens with Mustry UI, SCADA and range-controlled history.')
