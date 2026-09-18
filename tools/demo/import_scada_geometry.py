"""Export the existing Oatmakers vector drawings without PLC bindings or scripts."""
import argparse,base64,copy,json,re
from pathlib import Path
from xml.etree.ElementTree import Element,SubElement,tostring
parser=argparse.ArgumentParser();parser.add_argument('views');args=parser.parse_args()
source=Path(args.views);output=Path(__file__).parent/'scada-assets'
NS='http://www.w3.org/2000/svg'
def number(v,relative=1):
    if isinstance(v,str) and v.endswith('%'):return float(v[:-1])*relative/100
    try:return float(str(v).replace('px','').replace('deg',''))
    except (ValueError,TypeError):return 0

def clean(value):
    if isinstance(value,str):
        if value.startswith('var('):return '#748779'
        if value.lower() in ('#ff0000','#f00','red'):return '#748779'
        if value=='undefined':return ''
    return str(value)
def svg_element(data):
    kind=data.get('type','group');kind={'group':'g','polyline':'polyline'}.get(kind,kind)
    e=Element(kind)
    for k,v in data.items():
        if k in ('type','elements','name','id'):continue
        if k=='text':e.text=str(v);continue
        if k in ('stroke','fill') and isinstance(v,dict):
            for a,b in v.items():
                if b is None or b=='undefined':continue
                name=k if a=='paint' else k+'-'+a
                e.set(name,clean(b))
        elif k=='style' and isinstance(v,dict):
            pairs=[]
            for a,b in v.items():
                if a=='classes' or b is None:continue
                a=re.sub(r'([A-Z])',lambda m:'-'+m[1].lower(),a)
                pairs.append(a+':'+clean(b))
            if pairs:e.set('style',';'.join(pairs))
        elif isinstance(v,(str,int,float)) and v!='undefined':e.set(k,clean(v))
    for c in data.get('elements',[]):e.append(svg_element(c))
    return e

def convert_view(path,params,stack=()):
    if path in stack or len(stack)>12:return Element('g')
    file=source/path/'view.json'
    if not file.exists():return Element('g')
    d=json.loads(file.read_text());cfg=dict(d.get('params',{}));cfg.update(params)
    size=d.get('props',{}).get('defaultSize',{});w=size.get('width') or 300;h=size.get('height') or 200
    root=Element('svg',{'viewBox':f'0 0 {w} {h}','width':'100%','height':'100%','preserveAspectRatio':'none','overflow':'visible'})
    if path.endswith('Connecter'):
        vertical=cfg.get('Vertical',False)
        SubElement(root,'line',{'x1':str(w/2 if vertical else 0),'y1':str(0 if vertical else h/2),'x2':str(w/2 if vertical else w),'y2':str(h if vertical else h/2),'stroke':'#92a79a','stroke-width':'2','stroke-dasharray':'6 5'})
        return root
    children=d['root'].get('children',[])
    flex=d['root']['type']=='ia.container.flex'; cursor=0
    visible=[c for c in children if c.get('meta',{}).get('visible',True) and c['type']!='ia.display.icon']
    fixed=sum(number(c.get('position',{}).get('basis',0)) for c in visible if not c.get('position',{}).get('grow'))
    grow=sum(c.get('position',{}).get('grow',0) for c in visible) or 1
    for c in visible:
        typ=c['type'];p=c.get('props',{});pos=c.get('position',{})
        if typ not in ('ia.shapes.svg','ia.display.view','ia.container.coord','ia.container.flex'):continue
        if typ=='ia.display.view' and any(x in p.get('path','') for x in ('Graphs/','/AIO/','TemperatureShower','Clutter')):continue
        if flex:
            cw=max(12,(w-fixed)*pos.get('grow',0)/grow) if pos.get('grow') else number(pos.get('basis',40));ch=h;x=cursor;y=0;cursor+=cw
        else:
            cw=number(pos.get('width',w),w) or w;ch=number(pos.get('height',h),h) or h;x=number(pos.get('x',0),w);y=number(pos.get('y',0),h)
        angle=number(pos.get('rotate',{}).get('angle',0));anchor=str(pos.get('rotate',{}).get('anchor','50% 50%')).split()
        ax=number(anchor[0],cw) if anchor else cw/2;ay=number(anchor[1],ch) if len(anchor)>1 else ch/2
        group=SubElement(root,'g',{'transform':f'translate({x},{y}) rotate({angle},{ax},{ay})'})
        canvas=SubElement(group,'svg',{'width':str(cw),'height':str(ch),'overflow':'visible'})
        if typ=='ia.shapes.svg':
            canvas.set('viewBox',p.get('viewBox',f'0 0 {cw} {ch}'));canvas.set('preserveAspectRatio',p.get('preserveAspectRatio','none'))
            for shape in p.get('elements',[]):canvas.append(svg_element(shape))
        elif typ=='ia.display.view' and p.get('path'):canvas.append(convert_view(p['path'],p.get('params',{}),stack+(path,)))
    return root

layout={}
for key,path in [('peeling','Templates/PE/L01-PE'),('heating','Templates/HT/L01-HT')]:
    d=json.loads((source/path/'view.json').read_text());size=d['props']['defaultSize']
    root=convert_view(path,{})
    root.set('xmlns',NS)
    root.set('style','fill:none;stroke:#7b9082;stroke-width:1.5')
    output.mkdir(exist_ok=True);(output/(key+'.svg')).write_bytes(tostring(root))
    instruments=[]
    for c in d['root'].get('children',[]):
        p=c.get('props',{});ref=p.get('path','')
        if not any(x in ref for x in ('Graphs/','/AIO/','TemperatureShower')):continue
        text=json.dumps(c).lower();metric='temperature' if 'temp' in text else ('pressure' if 'pressure' in text else ('moisture' if 'moisture' in text else 'rate'))
        pos=c.get('position',{}); instruments.append({'x':number(pos.get('x',0)),'y':number(pos.get('y',0)),'width':max(150,number(pos.get('width',200))),'height':60,'metric':metric})
    layout[key]={'width':size['width'],'height':size['height'],'instruments':instruments}
(output/'layout.json').write_text(json.dumps(layout,indent=2)+'\n')
print('Exported original Oatmakers vector geometry and instrument positions.')
