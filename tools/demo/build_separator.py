"""Build the supplied Separator A reference as a complete, scalable process view."""
import base64
from view_primitives import *

W,H=1740,910
BG='#e6e6e6'
INK='#565957'

def image_svg(name,svg):
    return node('ia.display.image',name,{'source':'data:image/svg+xml;base64,'+base64.b64encode(svg.encode()).decode(),'fit':{'mode':'contain'},'style':{'pointerEvents':'none'}})

def svg(body,w,h):
    return '<svg xmlns="http://www.w3.org/2000/svg" width="%s" height="%s" viewBox="0 0 %s %s">%s</svg>'%(w,h,w,h,body)

def xy(n,x,y,w,h):
    n['position']={'x':x/W,'y':y/H,'width':w/W,'height':h/H};return n

def bind(path):return {'binding':{'type':'property','config':{'path':path}}}
def script_expr(expression,code):return {'binding':{'type':'expr','config':{'expression':expression},'transforms':[{'type':'script','code':code}]}}

def symbol(kind,active=True):
    fill='#a7dfa5' if active else '#b3b3b3'
    if kind=='pump':
        body='<circle cx="39" cy="36" r="23" fill="#c0dfb8" stroke="#555" stroke-width="2"/>'
        for r in (0,90,180,270):body+='<path d="M39 36 Q16 15 30 17 Q45 14 43 31 Z" transform="rotate(%d 39 36)" fill="#548455"/>'%r
        body+='<circle cx="39" cy="36" r="6" fill="#555"/><text x="60" y="12" font-size="12">M</text><text x="60" y="64" font-size="11">R</text>'
    else:
        body='<path d="M20 43 L56 59 L56 43 L20 59 Z" fill="%s" stroke="#555" stroke-width="1.6"/><path d="M38 29 V51" stroke="#555" stroke-width="1.4"/>'%fill
        if kind=='control':body+='<path d="M24 29 A14 12 0 0 1 52 29 Z" fill="%s" stroke="#555" stroke-width="1.4"/><text x="59" y="30" font-size="12">%s</text>'%(fill,'A' if active else 'M')
        else:body+='<rect x="29" y="17" width="20" height="12" fill="%s" stroke="#555" stroke-width="1.4"/><path d="M29 23 H49 M39 17 V29" stroke="#555"/>'%fill
    return svg('<g font-family="Arial" fill="#555">'+body+'</g>',78,75)


def build_separator():
    # Reusable instruments remain separate native Perspective views.
    tag=bound_label('Tag','view.params.tag','Separator/InstrumentTag')
    circle=bound_label('Type','view.params.kind','Separator/InstrumentType')
    val=bound_label('Value','view.params.value','Separator/InstrumentValue')
    val['propConfig']['props.style.backgroundColor']=bind('view.params.colour')
    instrument=flex('root',[tag,flex('Reading',[circle,val],'row','Separator/InstrumentReading')],classes='Separator/Instrument')
    instrument['events']={'dom':{'onClick':{'type':'script','scope':'G','config':{'script':'\tapplication.demo.showSeparatorDetail(self.view.params.tag, self.view.params.signal)'}}}}
    view('Demo/Separator/Instrument',instrument,params={'tag':'PI152A','kind':'PI','value':'--','colour':'#f7f7f7','signal':'pressure'},height=50)
    device_root=flex('root',[image_svg('Symbol',symbol('control')),bound_label('Tag','view.params.tag','Separator/DeviceTag')],classes='Separator/Device')
    device_root['children'][0]['position']={'basis':'0px','grow':1,'shrink':1}
    device_root['children'][0]['propConfig']={'props.source':bind('view.params.source')}
    device_root['propConfig']={'props.style.borderColor':expr('if({view.params.highlight}, "#f0a128", "transparent")')}
    device_root['events']={'dom':{'onClick':{'type':'script','scope':'G','config':{'script':'\tapplication.demo.showSeparatorDetail(self.view.params.tag, self.view.params.signal)'}}}}
    view('Demo/Separator/Device',device_root,params={'tag':'PCV151A2','source':'','highlight':False,'signal':'pressure'},height=95)
    trend=image_svg('Plot',svg('',280,70));trend['props']['style']={'pointerEvents':'none'}
    trend['props']['fit']['mode']='fill'
    trend['propConfig']={'props.source':{'binding':{'type':'expr-struct','config':{'waitOnAll':True,'struct':{'tick':'now(1000)','signal':'{view.params.signal}','colour':'{view.params.colour}','sp':'{view.params.sp}'}},'transforms':[{'type':'script','code':'\treturn application.demo.separatorTrendSvg(value["signal"], value["colour"], value["sp"])'}]}}}
    trend['position']={'x':0,'y':0,'width':1,'height':1}
    view('Demo/Separator/Trend',node('ia.container.coord','root',{'mode':'percent'},[trend]),params={'signal':'level','colour':'#81888d','sp':47.3},height=70)

    stream=flex('root',[bound_label('Text','view.params.text','Separator/StreamText'),label('Arrow','▶','Separator/StreamArrow')],'row','Separator/Stream')
    stream['children'][0]['position']={'basis':'0px','grow':1,'shrink':1}
    stream['children'][1]['position']={'basis':'18px','grow':0,'shrink':0}
    stream['events']={'dom':{'onClick':{'type':'script','scope':'G','config':{'script':'\tapplication.demo.showSeparatorDetail(self.view.params.text, "pressure")'}}}}
    view('Demo/Separator/Stream',stream,params={'text':'From Header A'},height=28)

    # Connections are drawn as vector geometry, never cropped screenshots.
    pipes=[]
    def path(d,colour=INK,width=1.8,dash=None):
        pipes.append('<path d="%s" fill="none" stroke="%s" stroke-width="%s" stroke-linejoin="round" %s/>'%(d,colour,width,('stroke-dasharray="'+dash+'"') if dash else ''))
    for d in ['M166 122 H189 Q194 122 194 128 V200 H518 Q524 200 524 206 V242',
              'M166 200 H277 V818 Q277 822 282 822 H1420 V626 H1520',
              'M166 358 H277','M166 448 H277','M166 538 H270','M286 538 H540',
              'M555 538 H839 V494','M839 494 V710 Q839 716 845 716 H1520',
              'M839 641 H913','M950 613 H1040','M1080 613 H1520',
              'M1280 470 H1330 Q1336 470 1336 476 V613',
              'M1058 368 V482 Q1058 488 1052 488 H970',
              'M369 421 V576 Q369 581 375 581 H700 V742',
              'M1058 361 H1469 V585','M1265 735 V683 Q1265 677 1271 677 H1390 V611']:
        path(d,INK,1.8 if 'M369' not in d and 'M1058 361' not in d and 'M1265' not in d else 1,'4 3' if d.startswith(('M369','M1058 361','M1265')) else None)
    path('M898 242 V197 Q898 193 904 193 H1520','#d1c389',1.7)
    path('M1190 193 V122 Q1190 117 1196 117 H1520','#d1c389',1.7)
    path('M549 496 V763 Q549 768 555 768 H1530','#93bcd1',1.7)
    path('M1420 718 V763',INK,1.7)
    # Instrument impulse lines and pneumatic control loop.
    for d in ['M559 242 V193','M641 242 V157','M766 242 V196','M865 242 V160',
              'M998 244 V260 Q998 265 989 265 H970',
              'M320 420 V374 Q320 366 330 366 H410','M320 426 V470 Q320 477 330 477 H438',
              'M983 613 V583','M1133 613 V555','M1224 613 V527','M1392 613 V550',
              'M1114 192 V158','M623 768 V736']:
        path(d,INK,1)
    path('M918 68 V21 Q918 17 924 17 H1388 V176',INK,1,'3 3')
    path('M1075 51 H1275 V110',INK,1.4)
    pipes.append('<g fill="none" stroke="#777"><rect x="1060" y="40" width="31" height="21"/><rect x="1260" y="40" width="31" height="21"/><path d="M1145 46 L1170 57 V46 L1145 57 Z"/><rect x="1150" y="27" width="16" height="14"/></g><g font-family="Arial" fill="#555" text-anchor="middle" font-size="12"><text x="1075" y="55">AS</text><text x="1275" y="55">I/P</text><text x="1158" y="38">S</text><text x="1158" y="71">SOV151A2</text></g>')
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
        ('PI162A','PI','suction','bar',1,938,565,None),('PI165A','PI','discharge','bar',1,1090,538,None),
        ('PI164A','PI','exportPressure','bar',1,1180,510,None),('FIC161A','FI','flow','M3/h',1,1347,537,None),
        ('FIC152A','FI','iop','',0,578,689,None)]
    for tag,kind,signal,unit,dec,x,y,colour in instruments:
        n=embed(tag,'Demo/Separator/Instrument',{'tag':tag,'kind':kind,'signal':signal,'colour':colour or '#f7f7f7','value':'--'})
        n['propConfig']={'props.params.value':script_expr('try({view.custom.data.'+signal+'}, 0)','\treturn "IOP"' if signal=='iop' else '\treturn u"{0:.'+str(dec)+'f} '+unit+'".format(value or 0)')}
        canvas.append(xy(n,x,y,130,51))
    for tag,kind,x,y,w,h,highlight,active,signal in [
        ('SDV151A','block',200,159,65,81,True,True,'pressure'),('PCV151A2','control',1232,73,78,84,True,True,'gas'),
        ('PCV151A1','control',1350,165,77,82,False,True,'gas'),('SDV161A','block',875,594,76,79,True,True,'suction'),
        ('P01A','pump',1025,590,76,81,True,True,'flow'),('SDV162A','block',1241,575,77,80,True,True,'exportPressure'),
        ('LCV152A','control',1433,581,77,80,False,True,'flow'),('LCV151A','control',657,735,80,75,False,False,'interface'),
        ('SDV152A','block',755,735,67,75,False,False,'interface'),('FCV161A','control',1227,788,79,79,True,True,'flow')]:
        n=embed(tag,'Demo/Separator/Device',{'tag':tag,'source':'data:image/svg+xml;base64,'+base64.b64encode(symbol(kind,active).encode()).decode(),'highlight':highlight,'signal':signal})
        canvas.append(xy(n,x,y,w,h))
    # Pipe entry and exit links retain the reference's placement and wording.
    for text,x,y,w in [('AntiFoam',38,109,132),('From Header A',38,187,132),('From Closed Drain',38,345,132),('From Open Drain',38,435,132),('Corrosion Inhibitor',38,525,132),('To Flare',1520,105,132),('To Gas Scrubber',1520,183,132),('From Booster Pump C',1172,457,112),('To Crude Export',1520,600,132),('To Booster Pump C',1520,703,132)]:
        n=embed(text.replace(' ','')+'Link','Demo/Separator/Stream',{'text':text})
        canvas.append(xy(n,x,y,w,28))
    for name,text,x,y,w,h,cls in [('VesselTag','PP-V-01A',647,265,155,25,'Separator/VesselTag'),('HistoryCaption','-1 hr  ↶',493,474,100,25,'Separator/Small'),('Sea','Dump To Sea',1538,758,130,25,'Separator/Small'),('Title','Separator A',750,869,250,38,'Separator/Title'),('Simulation','SIMULATION',1560,879,132,20,'Separator/Simulation')]:
        canvas.append(xy(label(name,text,cls),x,y,w,h))
    scene=node('ia.container.coord','Process',{'mode':'percent','aspectRatio':'1740:910','style':{'backgroundColor':BG,'overflow':'hidden','containerType':'inline-size'}},canvas,basis='0px',grow=1)
    scene['position']['shrink']=1
    tabs=[]
    names=['Overview','Crude Inlet A B C','Crude Inlet D EF','Crude Inlet GH NT','Separator A','Separator B','Booster Pump C','Crude Export','Gas Scrubber','Knockout Drum','Drain System','Water Injection']
    for i,name in enumerate(names):
        n=button('Tab'+str(i),name,page='/' if i==0 else None,script=None if i in (0,4) else '\tapplication.demo.showSeparatorDetail('+repr(name)+', "pressure")',classes='Separator/Tab'+(' Separator/SelectedTab' if i==4 else ''))
        n['position']={'basis':'0px','grow':1,'shrink':1};tabs.append(n)
    nav=flex('ProcessNavigation',tabs,'row','Separator/Tabs',basis='29px')
    data={key:0 for key in ['pressure','temperature','level','interface','gas','suction','discharge','exportPressure','flow','drain','iop']}
    root=flex('root',[nav,scene],classes='Separator/Page')
    view('Demo/SCADA',root,custom={'data':data},config={'custom.data':dict(script_expr('now(1000)','\treturn application.demo.separatorData()'),persistent=True)},height=939)
    # A reusable read-only detail view for instruments and connected streams.
    detail_value=label('Value','','Separator/DetailValue')
    detail_value['propConfig']={'props.text':{'binding':{'type':'expr-struct','config':{'waitOnAll':True,'struct':{'tick':'now(1000)','signal':'{view.params.signal}'}},'transforms':[{'type':'script','code':'\treturn application.demo.separatorDetailValue(value["signal"])'}]}}}
    detail=flex('root',[bound_label('Title','view.params.tag','Demo/SectionTitle'),label('Mode','Read-only process simulation','Demo/Muted'),detail_value,embed('Trend','Demo/Separator/Trend',{'colour':'#626b75','sp':0},basis='160px'),label('Caption','Last hour of simulated process history','Demo/Muted')],classes='Demo/PopupRoot')
    detail['children'][3]['propConfig']={'props.params.signal':bind('view.params.signal')}
    view('Demo/Separator/Detail',detail,params={'tag':'PI152A','signal':'pressure'},height=300)


SEPARATOR_CSS='''
.psc-Separator\\/Page { background:#e6e6e6; color:#565957; overflow:hidden; width:100%; height:100%; font-family:Arial,sans-serif; }
.psc-Separator\\/Tabs { gap:0; background:#f2f2f2; border-top:3px solid #657074; align-items:stretch; }
.psc-Separator\\/Tab { border:0; border-right:1px solid #d6d6d6; border-bottom:1px solid #d4d4d4; border-radius:0; padding:2px 4px; color:#666; background:#f4f4f4; font-size:12px; font-weight:400; white-space:nowrap; }
.psc-Separator\\/SelectedTab { background:#e6e6e6; border-bottom-color:#e6e6e6; font-weight:700; }
.psc-Separator\\/Instrument { gap:3px; cursor:pointer; overflow:visible; }
.psc-Separator\\/InstrumentTag { font-size:0.75cqw; height:17px; font-weight:500; color:#565957; }
.psc-Separator\\/InstrumentReading { gap:5px; align-items:center; overflow:visible; }
.psc-Separator\\/InstrumentType { border:1px solid #7d817f; border-radius:50%; width:1.18cqw; height:1.18cqw; flex-shrink:0; font-size:0.52cqw; text-align:center; color:#666; }
.psc-Separator\\/InstrumentValue { border-radius:16px; padding:2px 7px; font-size:0.74cqw; color:#6c706f; white-space:nowrap; font-variant-numeric:tabular-nums; }
.psc-Separator\\/Device { border:3px solid transparent; gap:0; cursor:pointer; overflow:visible; }
.psc-Separator\\/DeviceTag { font-size:0.73cqw; text-align:center; color:#555; font-weight:600; }
.psc-Separator\\/Stream { border:0; background:#595c5a; color:white; border-radius:0 18px 18px 0; align-items:center; gap:4px; padding:2px 3px; cursor:pointer; }
.psc-Separator\\/StreamText { font-size:0.63cqw; text-align:center; line-height:1.1; white-space:normal; }
.psc-Separator\\/StreamArrow { background:#cdd0cd; color:#60645f; border-radius:50%; height:18px; text-align:center; font-size:11px; }
.psc-Separator\\/VesselTag { text-align:center; font-size:0.76cqw; font-weight:600; color:#666; }
.psc-Separator\\/Small { font-size:0.74cqw; color:#727777; }
.psc-Separator\\/Title { text-align:center; font-size:1.4cqw; font-family:'Arial Narrow',Arial,sans-serif; font-weight:600; color:#5a5e5c; }
.psc-Separator\\/Simulation { text-align:right; font-size:0.55cqw; letter-spacing:1px; color:#777; }
.psc-Separator\\/DetailValue { font-size:28px; color:#444; }
'''
