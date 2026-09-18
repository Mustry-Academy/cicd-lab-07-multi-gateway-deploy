"""Build the supplied Separator A reference as a complete, scalable process view."""
import base64,json
from view_primitives import *

W,H=1740,910
BG='#e6e6e6'
INK='#565957'
FLOW_AXIS=48

def image_svg(name,svg):
    return node('ia.display.image',name,{'source':'data:image/svg+xml;base64,'+base64.b64encode(svg.encode()).decode(),'fit':{'mode':'contain'},'style':{'pointerEvents':'none'}})

def svg(body,w,h):
    return '<svg xmlns="http://www.w3.org/2000/svg" width="%s" height="%s" viewBox="0 0 %s %s">%s</svg>'%(w,h,w,h,body)

def xy(n,x,y,w,h):
    n['position']={'x':x/W,'y':y/H,'width':w/W,'height':h/H};return n

def bind(path):return {'binding':{'type':'property','config':{'path':path}}}
def script_expr(expression,code):return {'binding':{'type':'expr','config':{'expression':expression},'transforms':[{'type':'script','code':code}]}}

# Every reusable graphic uses design coordinates, including labels and borders.
# Its ports remain on the same coordinates as the parent piping when scaled.
def symbol(kind,active,tag,w,h,highlight):
    from html import escape
    cx=w/2.0; cy=float(FLOW_AXIS)
    fill='#a7dfa5' if active else '#b3b3b3'
    body=''
    if highlight:
        body+='<rect x="1.25" y="1.25" width="%s" height="%s" fill="none" stroke="#f0a128" stroke-width="2.5"/>'%(w-2.5,h-2.5)
    if kind=='pump':
        body+='<circle cx="%s" cy="%s" r="21" fill="#c0dfb8" stroke="#555" stroke-width="2"/>'%(cx,cy)
        for r in (0,90,180,270):
            body+='<path d="M%s %s q-22 -20 -9 -19 q15 -3 13 14 Z" transform="rotate(%d %s %s)" fill="#548455"/>'%(cx,cy,r,cx,cy)
        body+='<circle cx="%s" cy="%s" r="5" fill="#555"/><text x="%s" y="17" font-size="12">M</text><text x="%s" y="72" font-size="10">R</text>'%(cx,cy,w-15,w-15)
    else:
        body+='<path d="M%s %s L%s %s V%s L%s %s Z" fill="%s" stroke="#555" stroke-width="1.6"/>'%(cx-15,cy-8,cx+15,cy+8,cy-8,cx-15,cy+8,fill)
        body+='<path d="M%s %s V%s" stroke="#555" stroke-width="1.4"/>'%(cx,cy-22,cy)
        if kind=='control':
            body+='<path d="M%s %s a14 12 0 0 1 28 0 Z" fill="%s" stroke="#555" stroke-width="1.4"/><text x="%s" y="%s" font-size="12">%s</text>'%(cx-14,cy-22,fill,cx+20,cy-23,'A' if active else 'M')
        else:
            body+='<rect x="%s" y="%s" width="20" height="12" fill="%s" stroke="#555" stroke-width="1.4"/><path d="M%s %s h20 M%s %s v12" stroke="#555"/>'%(cx-10,cy-34,fill,cx-10,cy-28,cx,cy-34)
    body+='<text x="%s" y="%s" text-anchor="middle" font-size="12" font-weight="600">%s</text>'%(cx,h-5,escape(tag))
    return svg('<g font-family="Arial" fill="#555">'+body+'</g>',w,h)


def stream_svg(text,w):
    from html import escape
    body='<path d="M0 0 H%s a14 14 0 0 1 0 28 H0 Z" fill="#595c5a"/>'%(w-14)
    body+='<circle cx="%s" cy="14" r="9" fill="#cdd0cd"/><path d="M%s 8 l7 6 -7 6 Z" fill="#60645f"/>'%(w-14,w-17)
    lines=text.rsplit(' ',2) if w<120 else [text]
    if len(lines)>1:lines=[' '.join(lines[:-2]),' '.join(lines[-2:])]
    for i,line in enumerate(lines):
        body+='<text x="%s" y="%s" text-anchor="middle" font-family="Arial" font-size="10.5" fill="white">%s</text>'%((w-25)/2,17 if len(lines)==1 else 11+i*11,escape(line))
    return svg(body,w,28)


def build_separator():
    # Instrument circle center is (10,32), with pipe ports at y=22 and y=42.
    graphic=image_svg('Graphic',svg('',130,51));graphic['props']['fit']['mode']='fill'
    graphic['propConfig']={'props.source':{'binding':{'type':'expr-struct','config':{'waitOnAll':True,'struct':{'tag':'{view.params.tag}','kind':'{view.params.kind}','value':'{view.params.value}','colour':'{view.params.colour}'}},'transforms':[{'type':'script','code':'\treturn application.demo.separatorInstrumentSvg(value["tag"], value["kind"], value["value"], value["colour"])'}]}}}
    graphic['position']={'x':0,'y':0,'width':1,'height':1}
    instrument=node('ia.container.coord','root',{'mode':'percent','style':{'cursor':'pointer'}},[graphic])
    instrument['events']={'dom':{'onClick':{'type':'script','scope':'G','config':{'script':'\tapplication.demo.showSeparatorDetail(self.view.params.tag, self.view.params.signal)'}}}}
    view('Demo/Separator/Instrument',instrument,params={'tag':'PI152A','kind':'PI','value':'n/a','colour':'#f7f7f7','signal':'pressure'},height=51)
    device_graphic=image_svg('Graphic',svg('',78,88));device_graphic['props']['fit']['mode']='fill'
    device_graphic['propConfig']={'props.source':bind('view.params.source')}
    device_graphic['position']={'x':0,'y':0,'width':1,'height':1}
    device_root=node('ia.container.coord','root',{'mode':'percent','style':{'cursor':'pointer'}},[device_graphic])
    device_root['events']={'dom':{'onClick':{'type':'script','scope':'G','config':{'script':'\tapplication.demo.showSeparatorDetail(self.view.params.tag, self.view.params.signal)'}}}}
    view('Demo/Separator/Device',device_root,params={'tag':'PCV151A2','source':'','signal':'pressure'},height=88)
    trend=image_svg('Plot',svg('',280,70));trend['props']['style']={'pointerEvents':'none'}
    trend['props']['fit']['mode']='fill'
    trend['propConfig']={'props.source':{'binding':{'type':'expr-struct','config':{'waitOnAll':True,'struct':{'tick':'now(1000)','signal':'{view.params.signal}','colour':'{view.params.colour}','sp':'{view.params.sp}'}},'transforms':[{'type':'script','code':'\treturn application.demo.separatorTrendSvg(value["signal"], value["colour"], value["sp"])'}]}}}
    trend['position']={'x':0,'y':0,'width':1,'height':1}
    view('Demo/Separator/Trend',node('ia.container.coord','root',{'mode':'percent'},[trend]),params={'signal':'level','colour':'#81888d','sp':47.3},height=70)

    stream_graphic=image_svg('Graphic',svg('',132,28));stream_graphic['props']['fit']['mode']='fill'
    stream_graphic['propConfig']={'props.source':bind('view.params.source')}
    stream_graphic['position']={'x':0,'y':0,'width':1,'height':1}
    stream=node('ia.container.coord','root',{'mode':'percent','style':{'cursor':'pointer'}},[stream_graphic])
    stream['events']={'dom':{'onClick':{'type':'script','scope':'G','config':{'script':'\tapplication.demo.showSeparatorDetail(self.view.params.text, "pressure")'}}}}
    view('Demo/Separator/Stream',stream,params={'text':'From Header A','source':''},height=28)

    # Connections are drawn as vector geometry, never cropped screenshots.
    pipes=[]
    def path(d,colour=INK,width=1.8,dash=None):
        pipes.append('<path d="%s" fill="none" stroke="%s" stroke-width="%s" stroke-linejoin="round" %s/>'%(d,colour,width,('stroke-dasharray="'+dash+'"') if dash else ''))
    for d in ['M170 123 H189 Q194 123 194 129 V201 H518 Q524 201 524 207 V242',
              'M170 201 H277 V818 Q277 822 282 822 H1420 V613 H1520',
              'M170 359 H277','M170 449 H277','M170 539 H270','M286 538 H540',
              'M555 538 H839 V494','M839 494 V710 Q839 716 845 716 H1520',
              'M839 613 H1520',
              'M1284 471 H1330 Q1336 471 1336 477 V613',
              'M1051 365 H1000',
              'M368 432 V576 Q368 581 374 581 H697 V734',
              'M1071 365 H1471.5 V579','M1367 569 H1390 V677 H1266.5 V788']:
        path(d,INK,1.8 if 'M368 432' not in d and 'M1071 365' not in d and 'M1367' not in d else 1,'4 3' if d.startswith(('M368 432','M1071 365','M1367')) else None)
    path('M898 242 V201 Q898 197 904 197 H1520','#d1c389',1.7)
    path('M1190 197 V125 Q1190 119 1196 119 H1520','#d1c389',1.7)
    path('M549 496 V763 Q549 768 555 768 H1530','#93bcd1',1.7)
    path('M1420 718 V763',INK,1.7)
    # Impulse lines terminate at the instrument circle boundary, not its text.
    for cx,bottom,pipe_y in [(550,206,242),(645,169,242),(855,171,242),(762,207,242),
                            (979,560,613),(1122,580,613),(1190,552,613),(1357,579,613),
                            (1080,163,197),(588,731,768)]:
        path('M%s %s V%s'%(cx,pipe_y,bottom),INK,1)
    for d in ['M1000 258 V260 Q1000 265 994 265 H940',
              'M310 422 H298 V374 Q298 366 308 366 H430',
              'M320 432 V470 Q320 477 330 477 H490',
              'M402 528 V539','M1008 498 V494 H900']:
        path(d,INK,1)
    path('M1158 27 V17 H1388.5 V163',INK,1,'3 3')
    # Pneumatic supply stops at the AS and I/P enclosure edges.
    path('M1091 50.5 H1145 M1170 50.5 H1255.5 M1271 61 V85',INK,1.4)
    pipes.append('<g fill="#e6e6e6" stroke="#777"><rect x="1060" y="40" width="31" height="21"/><rect x="1255.5" y="40" width="31" height="21"/><path d="M1145 45 L1170 56 V45 L1145 56 Z"/><rect x="1150" y="27" width="16" height="14"/></g><g font-family="Arial" fill="#555" text-anchor="middle" font-size="12"><text x="1075.5" y="55">AS</text><text x="1271" y="55">I/P</text><text x="1158" y="38">S</text><text x="1158" y="71">SOV151A2</text></g>')
    # Main vessel is a separate live view, over the pipe network.
    canvas=[xy(image_svg('Piping',svg(''.join(pipes),W,H)),0,0,W,H)]
    vessel=image_svg('Vessel',svg('',610,260))
    vessel['propConfig']={'props.source':script_expr('now(1000)','\treturn application.demo.separatorVesselSvg()')}
    canvas.append(xy(vessel,410,240,610,260))
    for name,signal,colour,sp,x,y,w,h in [('PressureTrend','pressure','#d2ab53',3.88,424,284,570,62),('LevelTrend','level','#7c8185',47.33,720,340,271,62),('InterfaceTrend','interface','#789cad',21.51,444,429,268,65)]:
        canvas.append(xy(embed(name,'Demo/Separator/Trend',{'signal':signal,'colour':colour,'sp':sp}),x,y,w,h))
    instruments=[
        ('PI153A','PI','pressure','bar',2,540,164,None),('PI152A','PI','pressure','bar',2,635,127,None),
        ('PIC151A','PI','pressure','bar',2,845,129,None),('TI151A','TI','temperature','°C',2,752,165,None),
        ('LI156A','LI','iop','',0,990,216,None),('LIC152A','LI','level','%',2,1051,333,'#a7eef0'),
        ('LIC151A','LI','interface','%',2,310,390,'#ffe044'),('LI157A','LI','drain','%',0,392,486,None),
        ('LI153A','LI','level','%',2,998,476,None),('FIC151A','FI','gas','MMSCF/D',1,1070,121,None),
        ('PI162A','PI','suction','bar',1,969,518,None),('PI165A','PI','discharge','bar',1,1112,538,None),
        ('PI164A','PI','exportPressure','bar',1,1180,510,None),('FIC161A','FI','flow','M3/h',1,1347,537,None),
        ('FIC152A','FI','iop','',0,578,689,None)]
    for tag,kind,signal,unit,dec,x,y,colour in instruments:
        n=embed(tag,'Demo/Separator/Instrument',{'tag':tag,'kind':kind,'signal':signal,'colour':colour or '#f7f7f7','value':'--'})
        n['propConfig']={'props.params.value':script_expr('try({view.custom.data.'+signal+'}, 0)','\treturn "IOP"' if signal=='iop' else '\treturn u"{0:.'+str(dec)+'f} '+unit+'".format(value or 0)')}
        canvas.append(xy(n,x,y,130,51))
    # Device y coordinates are derived from the common flow-axis anchor (48).
    for tag,kind,x,flow_y,w,highlight,active,signal in [
        ('SDV151A','block',200,201,65,True,True,'pressure'),('PCV151A2','control',1232,119,78,True,True,'gas'),
        ('PCV151A1','control',1350,197,77,False,True,'gas'),('SDV161A','block',875,613,76,True,True,'suction'),
        ('P01A','pump',1025,613,76,True,True,'flow'),('SDV162A','block',1241,613,77,True,True,'exportPressure'),
        ('LCV152A','control',1433,613,77,False,True,'flow'),('LCV151A','control',657,768,80,False,False,'interface'),
        ('SDV152A','block',755,768,67,False,False,'interface'),('FCV161A','control',1227,822,79,True,True,'flow')]:
        n=embed(tag,'Demo/Separator/Device',{'tag':tag,'source':'data:image/svg+xml;base64,'+base64.b64encode(symbol(kind,active,tag,w,88,highlight).encode()).decode(),'signal':signal})
        canvas.append(xy(n,x,flow_y-FLOW_AXIS,w,88))
    # Pipe entry and exit links retain the reference's placement and wording.
    for text,x,y,w in [('AntiFoam',38,109,132),('From Header A',38,187,132),('From Closed Drain',38,345,132),('From Open Drain',38,435,132),('Corrosion Inhibitor',38,525,132),('To Flare',1520,105,132),('To Gas Scrubber',1520,183,132),('From Booster Pump C',1172,457,112),('To Crude Export',1520,600,132),('To Booster Pump C',1520,703,132)]:
        n=embed(text.replace(' ','')+'Link','Demo/Separator/Stream',{'text':text,'source':'data:image/svg+xml;base64,'+base64.b64encode(stream_svg(text,w).encode()).decode()})
        canvas.append(xy(n,x,y,w,28))
    for name,text,x,y,w,h,cls in [('VesselTag','PP-V-01A',647,265,155,25,'Separator/VesselTag'),('HistoryCaption','-1 hr  ↶',493,474,100,25,'Separator/Small'),('Sea','Dump To Sea',1538,758,130,25,'Separator/Small'),('Title','Separator A',750,869,250,38,'Separator/Title'),('Simulation','SIMULATION',1560,879,132,20,'Separator/Simulation')]:
        canvas.append(xy(label(name,text,cls),x,y,w,h))
    scene=node('ia.container.coord','Process',{'mode':'percent','aspectRatio':'1740:910','style':{'backgroundColor':BG,'overflow':'hidden','containerType':'inline-size'}},canvas,basis='0px',grow=1)
    scene['position']['shrink']=1
    header=flex('Header',[flex('Identity',[label('Eyebrow','OATMAKERS / LIVE OPERATIONS','Demo/Eyebrow'),label('Title','SCADA','Demo/PageTitle'),label('Subtitle','Separator A','Demo/Subtitle')],grow=1),label('Mode','SIMULATED FACTORY','Demo/DemoBadge')],'row','Demo/PageHeader')
    data={key:0 for key in ['pressure','temperature','level','interface','gas','suction','discharge','exportPressure','flow','drain','iop']}
    root=flex('root',[header,scene],classes='Demo/Page Separator/Page')
    view('Demo/SCADA',root,custom={'data':data},config={'custom.data':dict(script_expr('now(1000)','\treturn application.demo.separatorData()'),persistent=True)},height=939)
    # A reusable read-only detail view for instruments and connected streams.
    detail_value=label('Value','','Separator/DetailValue')
    detail_value['propConfig']={'props.text':{'binding':{'type':'expr-struct','config':{'waitOnAll':True,'struct':{'tick':'now(1000)','signal':'{view.params.signal}'}},'transforms':[{'type':'script','code':'\treturn application.demo.separatorDetailValue(value["signal"])'}]}}}
    detail=flex('root',[bound_label('Title','view.params.tag','Demo/SectionTitle'),label('Mode','Read-only process simulation','Demo/Muted'),detail_value,embed('Trend','Demo/Separator/Trend',{'colour':'#626b75','sp':0},basis='160px'),label('Caption','Last hour of simulated process history','Demo/Muted')],classes='Demo/PopupRoot')
    detail['children'][3]['propConfig']={'props.params.signal':bind('view.params.signal')}
    view('Demo/Separator/Detail',detail,params={'tag':'PI152A','signal':'pressure'},height=300)


SEPARATOR_CSS='''
.psc-Separator\\/Page { background:#e6e6e6; color:#565957; overflow:hidden; width:100%; height:100%; font-family:Arial,sans-serif; }
.psc-Separator\\/VesselTag { text-align:center; font-size:0.76cqw; font-weight:600; color:#666; }
.psc-Separator\\/Small { font-size:0.74cqw; color:#727777; }
.psc-Separator\\/Title { text-align:center; font-size:1.4cqw; font-family:'Arial Narrow',Arial,sans-serif; font-weight:600; color:#5a5e5c; }
.psc-Separator\\/Simulation { text-align:right; font-size:0.55cqw; letter-spacing:1px; color:#777; }
.psc-Separator\\/DetailValue { font-size:28px; color:#444; }
'''
