"""Layered square-pixel worlds, composed once and animated without dependencies."""
import math
import random
from functools import lru_cache

SCENE_NAMES = {
    'bike': 'Alpine Daydream', 'walk': 'Fernwood Trail',
    'coding': 'Rainy Window', 'bounce': 'Afterhours Rooftop',
    'wave': 'Blossom Courtyard', 'coffee': 'The Corner Cafe',
    'napping': 'Moonlit Stillwater', 'idle': 'The Quiet Garden',
    'guitar': 'Golden Hour Coast',
}


def blend(a, b, t):
    return tuple(round(x+(y-x)*max(0,min(1,t))) for x,y in zip(a,b))


class Canvas:
    def __init__(self, w, h, top=(0,0,0), bottom=None, pixels=None):
        self.w,self.h=w,h
        if pixels is not None:
            self.pixels=[list(row) for row in pixels]
        else:
            self.pixels=[[blend(top,bottom or top,y/max(1,h-1))]*w for y in range(h)]

    def rect(self,x,y,w,h,color):
        x,y,w,h=round(x),round(y),round(w),round(h)
        for yy in range(max(0,y),min(self.h,y+h)):
            self.pixels[yy][max(0,x):min(self.w,max(0,x+w))]=[color]*max(0,min(self.w,x+w)-max(0,x))

    def line(self,x,y,x2,y2,color):
        n=max(1,round(max(abs(x2-x),abs(y2-y))))
        for i in range(n+1):self.rect(x+(x2-x)*i/n,y+(y2-y)*i/n,1,1,color)

    def ellipse(self,x,y,rx,ry,color):
        for yy in range(max(0,round(y-ry)),min(self.h,round(y+ry)+1)):
            span=rx*math.sqrt(max(0,1-((yy-y)/max(.1,ry))**2))
            self.rect(x-span,yy,span*2+1,1,color)

    def poly(self,points,color):
        for yy in range(max(0,math.floor(min(p[1] for p in points))),min(self.h,math.ceil(max(p[1] for p in points))+1)):
            hits=[]
            for (x1,y1),(x2,y2) in zip(points,points[1:]+points[:1]):
                if (y1<=yy<y2) or (y2<=yy<y1):hits.append(x1+(x2-x1)*(yy-y1)/(y2-y1))
            hits.sort()
            for a,b in zip(hits[::2],hits[1::2]):self.rect(math.ceil(a),yy,math.floor(b)-math.ceil(a)+1,1,color)


def _mountains(c,base,color,phase=0,high=.18):
    pts=[(0,c.h),(0,base)]
    for i in range(9):
        x=c.w*i/8
        y=base-c.h*(high*(.4+.6*math.sin(i*2.3+phase)**2))
        pts.append((x,y))
    pts.extend([(c.w,base),(c.w,c.h)])
    c.poly(pts,color)


def _pine(c,x,y,height,color,trunk):
    c.rect(x,y-height,1,height,trunk)
    for k in (1,.75,.48):
        hh=height*k
        c.poly([(x,y-height),(x-hh*.33,y-height+hh),(x+hh*.33,y-height+hh)],color)


def _pagoda(c,x,y,size,roof,wall):
    for level in range(3):
        ww=size*(.5+.25*level); yy=y+level*size*.26
        c.rect(x-ww*.32,yy,ww*.64,size*.24,wall)
        c.poly([(x-ww*.65,yy+1),(x-ww*.45,yy-1),(x,yy-size*.22),
                (x+ww*.45,yy-1),(x+ww*.65,yy+1)],roof)
    c.rect(x-size*.45,y+size*.78,size*.9,1,roof)


def _flowers(c,seed,lo,hi,colors,count=18):
    rng=random.Random(seed)
    for _ in range(count):
        x=rng.randrange(c.w); y=rng.randrange(max(0,lo),max(lo+1,hi))
        c.rect(x,y,1,1,rng.choice(colors))


@lru_cache(maxsize=18)
def _base(w,h,key,dark):
    floor=h-2
    if key=='bike':
        sky=((35,59,78),(104,147,153)) if dark else ((177,215,222),(235,234,204))
        c=Canvas(w,h,*sky)
        c.ellipse(w*.77,h*.24,4,4,(236,209,147) if dark else (248,221,155))
        far=(66,91,115) if dark else (137,168,180)
        _mountains(c,h*.62,far,.8,.31)
        c.poly([(w*.48,h*.29),(w*.40,h*.43),(w*.45,h*.40),(w*.48,h*.43),(w*.51,h*.39),(w*.55,h*.43)],(187,207,204) if dark else (230,237,220))
        _mountains(c,h*.72,(49,78,87) if dark else (96,143,142),2.8,.14)
        c.rect(0,h*.69,w,h*.31,(56,99,112) if dark else (132,185,188))
        for y in range(round(h*.72),floor,3):
            c.rect(w*.55,y,w*.26,1,(100,139,145) if dark else (187,213,202))
        for x in (-1,w*.95):_pine(c,x,floor,round(h*.42),(32,62,65) if dark else (65,110,98),(66,90,79))
        c.rect(0,floor-1,w,1,(103,125,104) if dark else (179,183,142))
        c.rect(0,floor,w,2,(65,73,70) if dark else (164,153,129))
    elif key=='walk':
        c=Canvas(w,h,*(((30,63,60),(83,114,87)) if dark else ((192,222,196),(231,225,169))))
        c.ellipse(w*.67,h*.22,4,4,(199,202,142) if dark else (248,235,169))
        _mountains(c,h*.71,(49,91,76) if dark else (141,180,128),1,.16)
        for i in range(16):
            x=i*w/15
            _pine(c,x,h*.81,h*(.23+.1*math.sin(i*4)**2),(44,83,68) if dark else (100,149,105),(70,96,67))
        c.rect(0,h*.82,w,h*.18,(47,73,56) if dark else (123,158,99))
        # A winding trail recedes toward the right-hand clearing.
        c.poly([(w*.81,h*.65),(w*.84,h*.65),(w*.69,floor),(w*.34,floor)],(102,101,74) if dark else (201,183,131))
        for x in (w*.05,w*.95):
            c.rect(x-1,h*.20,3,h*.72,(54,66,48) if dark else (100,111,69))
            c.ellipse(x,h*.17,w*.15,h*.24,(37,72,54) if dark else (83,132,83))
        _flowers(c,12,round(h*.86),floor,[(181,163,112),(197,139,130),(150,183,132)])
        c.rect(0,floor,w,2,(75,82,58) if dark else (183,172,124))
    elif key=='coding':
        c=Canvas(w,h,*(((38,42,61),(62,66,81)) if dark else ((192,203,207),(222,216,196))))
        wx,wy,ww,wh=round(w*.55),round(h*.10),round(w*.40),round(h*.67)
        c.rect(wx-1,wy-1,ww+2,wh+2,(117,108,101) if not dark else (93,88,94))
        c.rect(wx,wy,ww,wh,(38,60,83) if dark else (139,165,177))
        for i in range(7):
            bx=wx+i*ww/7;bh=wh*(.24+.36*((i*7)%5)/5)
            c.rect(bx,wy+wh-bh,ww/8,bh,(48,65,82) if dark else (104,133,147))
            for yy in range(round(wy+wh-bh)+2,wy+wh-1,3):
                c.rect(bx+1,yy,1,1,(211,180,126))
        c.rect(wx+ww/2,wy,1,wh,(92,88,91) if dark else (224,214,190))
        c.rect(wx,wy+wh*.55,ww,1,(92,88,91) if dark else (224,214,190))
        c.rect(w*.06,h*.34,w*.25,1,(106,83,69))
        for i,col in enumerate([(116,139,124),(171,123,108),(192,173,130),(117,137,157)]):
            c.rect(w*.08+i*3,h*.34-4,2,4,col)
        c.rect(w*.14,0,1,h*.16,(100,89,72))
        c.poly([(w*.10,h*.22),(w*.14,h*.14),(w*.18,h*.22)],(211,171,100))
        c.rect(w*.82,floor-3,6,3,(138,109,83))
        for dx,dy in [(-3,-5),(0,-7),(3,-4)]:
            c.line(w*.85,floor-3,w*.85+dx,floor+dy,(90,135,107))
            c.ellipse(w*.85+dx,floor+dy,2,1,(99,143,108))
        c.rect(0,floor,w,2,(73,65,64) if dark else (163,137,110))
    elif key=='bounce':
        c=Canvas(w,h,*(((30,27,60),(112,70,111)) if dark else ((108,112,164),(208,158,175))))
        c.ellipse(w*.75,h*.27,5,5,(206,139,179))
        for layer,base,color in [(0,h*.83,(73,72,108)),(1,h*.94,(46,48,79))]:
            for i in range(12):
                x=i*w/11-2;bh=h*(.13+((i*13+layer*3)%9)/40)
                c.rect(x,base-bh,w/12,bh,color)
                for yy in range(round(base-bh)+2,round(base)-1,3):
                    c.rect(x+2,yy,1,1,(157,126,183) if i%2 else (100,172,177))
                if i in (2,8):c.rect(x,base-bh-1,w/12,1,(214,128,166))
        c.rect(0,floor-2,w,1,(160,124,149));c.rect(0,floor-1,w,1,(54,49,78))
        c.rect(0,floor,w,2,(43,42,64) if dark else (78,72,103))
    elif key=='wave':
        c=Canvas(w,h,*(((64,58,83),(129,103,122)) if dark else ((232,207,202),(248,230,201))))
        _mountains(c,h*.79,(91,99,112) if dark else (178,182,166),.4,.18)
        _pagoda(c,w*.77,h*.48,min(w*.22,h*.52),(88,72,83) if dark else (142,102,95),(180,143,123) if dark else (224,195,153))
        for x,side in [(w*.05,1),(w*.94,-1)]:
            c.line(x,floor,x+side*2,h*.32,(110,77,75))
            for dx,dy in [(0,0),(4,.07),(-4,.08),(2,-.08)]:
                c.ellipse(x+dx,h*(.32+dy),5,3,(165,116,139) if dark else (223,155,170))
                c.ellipse(x+dx-1,h*(.32+dy)-1,3,1,(190,139,159) if dark else (243,187,192))
        c.rect(0,floor-2,w,2,(98,110,83) if dark else (166,185,123))
        c.rect(0,floor,w,2,(116,105,101) if dark else (206,189,162))
        for x in range(0,w,9):c.rect(x,floor,1,2,(101,93,91) if dark else (181,168,145))
    elif key=='coffee':
        c=Canvas(w,h,*(((69,48,46),(116,78,58)) if dark else ((224,186,143),(244,218,176))))
        # Arched cafe window, warm mullions and a quiet garden outside.
        x,y,rx,ry=w*.77,h*.40,w*.17,h*.30
        c.ellipse(x,y,rx+1,ry+1,(95,68,58));c.rect(x-rx-1,y,rx*2+3,h*.39,(95,68,58))
        c.ellipse(x,y,rx,ry,(71,97,96) if dark else (166,191,174))
        c.rect(x-rx,y,rx*2+1,h*.36,(71,97,96) if dark else (166,191,174))
        c.rect(x-rx,y+h*.21,rx*2+1,h*.15,(53,80,64) if dark else (112,153,115))
        c.rect(x,y-ry,1,h*.66,(112,79,60));c.rect(x-rx,y+h*.07,rx*2+1,1,(112,79,60))
        c.rect(w*.05,h*.38,w*.30,1,(142,96,64))
        for i in range(4):
            xx=w*.08+i*5;c.rect(xx,h*.38-3,3,3,(208,191,157));c.rect(xx+3,h*.38-2,1,1,(208,191,157))
        for xx in (w*.17,w*.51,w*.88):
            c.rect(xx,0,1,h*.13,(118,83,60))
            c.poly([(xx-3,h*.18),(xx,h*.10),(xx+3,h*.18)],(218,172,98))
        c.rect(w*.72,floor-5,w*.23,1,(151,101,63));c.rect(w*.82,floor-4,1,4,(111,80,57))
        c.rect(w*.81,floor-8,2,3,(204,163,117));c.rect(w*.81,floor-10,1,2,(130,151,94));c.rect(w*.80,floor-10,3,1,(210,144,126))
        c.rect(0,floor,w,2,(108,76,57) if dark else (173,128,85))
    elif key=='napping':
        c=Canvas(w,h,*(((19,30,56),(61,78,114)) if dark else ((74,91,133),(142,159,182))))
        moon=(222,225,197) if dark else (241,236,208)
        c.ellipse(w*.77,h*.25,4,4,moon)
        c.ellipse(w*.77+2,h*.25-1,3.7,3.7,blend(c.pixels[round(h*.25)][0],c.pixels[0][0],.15))
        _mountains(c,h*.71,(32,52,77) if dark else (90,118,140),2,.18)
        c.rect(0,h*.70,w,h*.30,(37,62,89) if dark else (100,134,160))
        for yy in range(round(h*.73),floor,3):
            span=(yy-h*.7)*.7+2;c.rect(w*.77-span,yy,span*2,1,(107,132,149) if dark else (179,192,190))
        _flowers(c,30,1,round(h*.48),[(181,192,204),(151,171,193)],count=23)
        c.rect(0,floor-1,w,3,(29,48,53) if dark else (71,101,103))
        for x in range(0,w,4):c.line(x,floor,x+1,floor-2,(40,64,63) if dark else (85,119,110))
    elif key=='idle':
        c=Canvas(w,h,*(((39,68,74),(105,138,128)) if dark else ((187,215,208),(235,231,197))))
        _mountains(c,h*.73,(71,103,107) if dark else (139,169,163),2.3,.29)
        _mountains(c,h*.85,(54,89,89) if dark else (113,151,133),.3,.14)
        _pagoda(c,w*.77,h*.46,min(w*.23,h*.52),(51,70,73) if dark else (95,117,105),(140,156,135) if dark else (212,211,170))
        c.ellipse(w*.8,h*.94,w*.26,h*.15,(57,95,100) if dark else (138,177,167))
        for i in range(4):c.rect(w*(.65+i*.08),h*(.91+(i%2)*.04),3,1,(99,136,108) if dark else (170,194,142))
        for x in (1,4,w-3):
            c.rect(x,h*.12,1,h*.82,(66,105,90) if dark else (113,152,106))
            for yy in range(round(h*.2),floor-3,5):
                c.line(x,yy,x+3,yy-2,(66,105,90) if dark else (113,152,106))
        c.rect(0,floor,w,2,(66,88,72) if dark else (176,183,141))
    else: # guitar: broad, quiet sunset sea and a timber pier
        c=Canvas(w,h,*(((105,73,105),(209,138,115)) if dark else ((221,174,159),(252,217,159))))
        c.ellipse(w*.74,h*.42,6,6,(234,174,112) if dark else (250,227,163))
        c.rect(0,h*.55,w,h*.45,(67,104,120) if dark else (128,170,177))
        c.poly([(0,h*.56),(w*.10,h*.48),(w*.22,h*.56),(w*.29,h*.58),(0,h*.60)],(64,81,98) if dark else (105,141,149))
        for i in range(6):
            yy=round(h*.59+i*h*.055); span=3+i*2
            c.rect(w*.74-span,yy,span*2,1,(169,151,135) if dark else (225,205,166))
        c.rect(0,floor-1,w,1,(111,88,75) if dark else (180,142,100))
        c.rect(0,floor,w,2,(83,70,65) if dark else (158,121,86))
        for x in range(0,w,10):c.rect(x,floor,1,2,(69,60,59) if dark else (133,104,79))
    return tuple(tuple(row) for row in c.pixels)


def render_background(w,h,key,dark=False,elapsed=0):
    """Return a fresh full-width canvas; deterministic for a scene/time/size."""
    c=Canvas(w,h,pixels=_base(w,h,key,dark))
    t=math.floor(elapsed*6)/6
    floor=h-2
    if key=='coding':
        for i in range(16):
            x=round(w*.57+(i*7)%max(1,round(w*.35)))
            y=round(h*.13+(i*11+t*4)%max(1,round(h*.58)))
            c.line(x,y,x-1,min(y+2,round(h*.73)),(125,151,171) if dark else (190,210,211))
    elif key in ('wave','walk'):
        for i in range(4):
            x=round((i*w*.29+t*.8)%w)
            y=round(h*.19+(i*7+t*1.2)%max(1,round(h*.60)))
            c.rect(x,y,1,1,(213,158,173) if key=='wave' else (190,192,132))
    elif key in ('napping','guitar'):
        for i in range(5):
            x=round((i*.193+.12)*w)%w
            y=round(h*(.17+(i%3)*.12)) if key=='napping' else floor-3-(i*3)%max(1,round(h*.23))
            a=(math.sin(t*.8+i*2)+1)/2
            if a>.55:c.rect(x,y,1,1,blend((125,149,158),(234,219,151),a))
    elif key=='bike':
        offset=round(t*3)%12
        for x in range(-12,w+12,12):c.rect(x-offset,floor,4,1,(177,166,139) if not dark else (105,111,94))
    elif key=='bounce':
        for i in range(3):
            x=round(w*(.13+i*.33))
            c.rect(x,round(h*.53),1,1,(146,165,186) if int(t+i)%4<2 else (112,95,144))
    return c.pixels


class Particle:
    def __init__(self,x,y,char,color,vy=-1.5,vx=0,max_life=2.5):
        self.x,self.y=float(x),float(y);self.char,self.color=char,color
        self.vy,self.vx=vy,vx;self.life,self.max_life=0.0,max_life
    def update(self,dt):
        self.x+=self.vx*dt;self.y+=self.vy*dt;self.life+=dt
        return self.life<self.max_life


class Scene:
    def __init__(self):
        self.cloud_x,self.small_cloud_x=20.0,75.0
        self.road_offset=0.0;self.particles=[];self.spawn_elapsed=0.0
        self.activity=None;self.elapsed=0.0;self._rng=random.Random(17)
    def reset(self,activity):
        self.activity=activity;self.particles.clear();self.spawn_elapsed=0.0;self.elapsed=0.0
    def update(self,dt=1/24,is_biking=True,activity='bike',mascot_x=30,mascot_y=20,particle_origin=None,cols=80):
        if activity!=self.activity:self.reset(activity)
        if dt<=0:return
        self.elapsed+=dt
        self.particles=[p for p in self.particles if p.update(dt)]
        self.spawn_elapsed+=dt
        if particle_origin and self.spawn_elapsed>=1.1:
            self.spawn_elapsed%=1.1;ox,oy=particle_origin
            self.particles.append(Particle(mascot_x+ox,mascot_y+oy/2,
                self._rng.choice(['z','Z'] if activity=='napping' else ['♪','♫']),
                (167,174,177),vx=.45,max_life=2.8))
