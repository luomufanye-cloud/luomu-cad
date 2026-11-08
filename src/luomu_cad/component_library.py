"""Luomu CAD parametric plan symbols. Copyright (c) 2026 luomufanye-cloud."""
from __future__ import annotations

import json
import math
from pathlib import Path

from shapely.geometry import LineString, Point, Polygon
from shapely.ops import unary_union

from .storage import ROOT

TAU = math.tau


class Symbol:
    """Analytic primitives in local mm, transformed once into drawing coordinates."""
    def __init__(self, x=0, y=0, angle=0):
        self.entities = []
        self.x, self.y = x, y
        self.c, self.s = math.cos(angle), math.sin(angle)

    def point(self, x, y):
        return [self.x+self.c*x-self.s*y, self.y+self.s*x+self.c*y]

    def line(self, a, b, dashed=False):
        if math.dist(a,b) > 1e-9:
            self.entities.append({'type':'line','start':self.point(*a),'end':self.point(*b),'dashed':dashed})

    def poly(self, points, closed=True, dashed=False):
        points = list(points)
        for a,b in zip(points,points[1:]+points[:1] if closed else points[1:]):
            self.line(a,b,dashed)

    def rect(self, x, y, w, d, dashed=False):
        self.poly([(x,y),(x+w,y),(x+w,y+d),(x,y+d)],dashed=dashed)

    def box(self, w, d, inset=0, dashed=False):
        self.rect(-w/2+inset,-d/2+inset,w-2*inset,d-2*inset,dashed)

    def arc(self, x, y, rx, ry=None, start=0, sweep=TAU, rotation=0, dashed=False):
        ry = rx if ry is None else ry
        if min(rx,ry) <= 0:
            raise ValueError('Positive symbol curve radii required')
        self.entities.append({'type':'ellipse_arc','center':self.point(x,y),'rx':rx,'ry':ry,
            'rotation':math.atan2(self.s,self.c)+rotation,'start':start,'sweep':sweep,'dashed':dashed})

    def curve(self, controls):
        self.entities.append({'type':'bezier','controls':[self.point(*p) for p in controls]})

    def smooth(self, points):
        if len(points)<3:
            self.poly(points,False);return
        middle=lambda a,b:((a[0]+b[0])/2,(a[1]+b[1])/2)
        previous=middle(points[0],points[1]);self.line(points[0],previous)
        for i in range(1,len(points)-1):
            following=middle(points[i],points[i+1])
            self.curve([previous,points[i],following]);previous=following
        self.line(previous,points[-1])

    def round_rect(self, x, y, w, d, radius):
        r = min(radius,w/2,d/2)
        for a,b in [((x+r,y),(x+w-r,y)),((x+w,y+r),(x+w,y+d-r)),
                    ((x+w-r,y+d),(x+r,y+d)),((x,y+d-r),(x,y+r))]:
            self.line(a,b)
        for cx,cy,start in [(x+w-r,y+r,-math.pi/2),(x+w-r,y+d-r,0),
                            (x+r,y+d-r,math.pi/2),(x+r,y+r,math.pi)]:
            self.arc(cx,cy,r,start=start,sweep=math.pi/2)

    def ribs(self, w, d, count=6, vertical=True, inset=.08):
        for i in range(1,count):
            f=inset+(1-2*inset)*i/count
            a,b=((-w/2+w*f,-d/2+d*inset),(-w/2+w*f,d/2-d*inset)) if vertical else \
                ((-w/2+w*inset,-d/2+d*f),(w/2-w*inset,-d/2+d*f))
            self.line(a,b)


FAMILIES = {
 'sleep': 'bed roundBed bunkBed crib tatami nightstand bedBench bayCushion petBed',
 'seat': 'sofa lSofa uSofa curvedSofa bendSofa chaise beanbag ottoman rockingChair hangingChair armchair booth entryBench lounge modularSofa theaterSofa outdoorSofa sunLounger stool chair officeChair barStool',
 'table': 'desk lDesk coffeeTable roundTable ovalTable diningTable consoleTable kitchenIsland counter lCounter uCounter sideTable island barCounter trainingTable curveTrainingTable lectern stage teaTable workbench outdoorSet',
 'storage': 'wardrobe chest dresser bookshelf tvCabinet sideboard wineCabinet displayCabinet shoeCabinet cabinet mirrorCabinet shelfRack garageShelf cornerShelf plantShelf wallPanel screenDivider',
 'sanitary': 'toilet squat vanity pedestalSink freeTub shower showerScreen bathtub showerSet laundrySink urinal serviceSink towelWarmer ledMirror',
 'kitchen': 'fridge freezer dishwasher tallOven hood microwave integratedStove coffeeMachine purifier bin waterDispenser',
 'machine': 'acWall acFloor acOutdoor ductAC linearVent cassetteAC vrfOutdoor freshAirUnit thermostat waterHeater gasHeater airPurifier robotVac radiator boiler manifold waterSoftener tank preFilter floorHeat washer dryer washerTower bathHeater airVent',
 'light': 'floorLamp deskLamp chandelier linearPendant ceilLamp ceilingFan bubblePendant gardenLamp inGround wallWasher lawnLamp fan ceilingSpeaker wifiAP projector speaker',
 'garden': 'plant hangingPlant vase tableVase tree shrub hedge flowerBed planterBox palm bamboo rock lawn pool stepStones gazebo parasol swing bbq waterFeature fence gate pergola hammock kidsSlide dogHouse firePit carport',
 'circulation': 'stairU stairRun stairDogleg elevator riser',
 'vehicle': 'car bicycle evCharger',
 'leisure': 'piano grandPiano billiards mahjong sauna treadmill bike yogaMat catTree',
 'accessory': 'coatRack mirror fireplace fishTank projScreen wallTV curtain wallArt clock rug rugRound bayDeck plushToy bookSet slidingBoard mobileDisplay printer clothesRack',
 'free': 'free',
}
TYPE_FAMILY = {kind:family for family,types in FAMILIES.items() for kind in types.split()}
TYPE_FAMILY.update({'louver':'machine','meterBox':'machine'})
NAMES = {'sleep':'卧室','seat':'座椅与沙发','table':'桌台','storage':'储物与隔断','sanitary':'卫浴',
         'kitchen':'厨房','machine':'机电设备','light':'灯具与弱电','garden':'室外景观',
         'circulation':'楼梯与竖向交通','vehicle':'车辆设施','leisure':'休闲设施','accessory':'室内配件','free':'自由几何'}
DISPLAY = {'bed':'床','roundBed':'圆床','sofa':'沙发','lSofa':'转角沙发','uSofa':'围合沙发',
           'bendSofa':'曲线沙发','toilet':'坐便器','squat':'蹲便器','vanity':'洗面台','ovalTable':'椭圆桌',
           'roundTable':'圆桌','desk':'书桌','chair':'座椅','wardrobe':'衣柜','cabinet':'柜体'}
for vocabulary in (
 'bunkBed=双层床|crib=婴儿床|tatami=榻榻米|nightstand=床头柜|bedBench=床尾凳|bayCushion=飘窗坐垫|petBed=宠物床',
 'curvedSofa=弧形沙发|chaise=贵妃榻|beanbag=懒人沙发|ottoman=脚凳|rockingChair=摇椅|hangingChair=吊椅|armchair=扶手椅|booth=卡座|entryBench=换鞋凳|lounge=躺椅|modularSofa=组合沙发|theaterSofa=影院座椅|outdoorSofa=户外沙发|sunLounger=日光躺椅|stool=圆凳|officeChair=办公椅|barStool=吧椅',
 'lDesk=转角书桌|coffeeTable=茶几|diningTable=餐桌|consoleTable=玄关台|kitchenIsland=厨房中岛|counter=厨房台面|lCounter=转角台面|uCounter=围合台面|sideTable=边桌|island=岛台|barCounter=吧台|trainingTable=培训桌|curveTrainingTable=弧形培训桌|lectern=讲台|stage=舞台|teaTable=茶台|workbench=工作台|outdoorSet=户外桌椅',
 'chest=抽屉柜|dresser=梳妆台|bookshelf=书架|tvCabinet=电视柜|sideboard=餐边柜|wineCabinet=酒柜|displayCabinet=展示柜|shoeCabinet=鞋柜|mirrorCabinet=镜柜|shelfRack=置物架|garageShelf=车库货架|cornerShelf=转角架|plantShelf=植物架|wallPanel=墙面饰板|screenDivider=屏风',
 'pedestalSink=立柱盆|freeTub=独立浴缸|shower=淋浴区|showerScreen=淋浴屏|bathtub=浴缸|showerSet=淋浴花洒|laundrySink=洗衣盆|urinal=小便器|serviceSink=清洁池|towelWarmer=电热毛巾架|ledMirror=照明镜',
 'fridge=冰箱|freezer=冷柜|dishwasher=洗碗机|tallOven=嵌入式烤箱|hood=油烟机|microwave=微波炉|integratedStove=灶具|coffeeMachine=咖啡机|purifier=净水器|bin=垃圾桶|waterDispenser=饮水机',
 'acWall=壁挂机|acFloor=立柜空调|acOutdoor=空调外机|ductAC=风管机|linearVent=条形风口|cassetteAC=嵌入空调|vrfOutdoor=多联机室外机|freshAirUnit=新风机|thermostat=温控器|waterHeater=热水器|gasHeater=燃气热水器|airPurifier=空气净化器|robotVac=扫地机器人|radiator=散热器|boiler=锅炉|manifold=分集水器|waterSoftener=软水设备|tank=储水罐|preFilter=前置过滤器|floorHeat=地暖分区|washer=洗衣机|dryer=烘干机|washerTower=洗烘叠机|bathHeater=浴室暖风机|airVent=通风口|louver=百叶|meterBox=计量箱',
 'floorLamp=落地灯|deskLamp=台灯|chandelier=吊灯|linearPendant=线形吊灯|ceilLamp=吸顶灯|ceilingFan=吊扇|bubblePendant=球形吊灯|gardenLamp=庭院灯|inGround=地埋灯|wallWasher=洗墙灯|lawnLamp=草坪灯|fan=风扇|ceilingSpeaker=吸顶音响|wifiAP=无线接入点|projector=投影机|speaker=音箱',
 'plant=绿植|hangingPlant=吊盆|vase=花瓶|tableVase=桌花|tree=乔木|shrub=灌木|hedge=绿篱|flowerBed=花坛|planterBox=花箱|palm=棕榈|bamboo=竹丛|rock=景石|lawn=草坪|pool=泳池|stepStones=汀步|gazebo=凉亭|parasol=遮阳伞|swing=秋千|bbq=烧烤炉|waterFeature=水景|fence=围栏|gate=庭院门|pergola=廊架|hammock=吊床|kidsSlide=滑梯|dogHouse=犬舍|firePit=火盆|carport=车棚',
 'stairU=折返楼梯|stairRun=直跑楼梯|stairDogleg=双跑楼梯|elevator=电梯|riser=立管|car=汽车|bicycle=自行车|evCharger=充电桩',
 'piano=钢琴|grandPiano=三角钢琴|billiards=台球桌|mahjong=麻将桌|sauna=桑拿房|treadmill=跑步机|bike=健身车|yogaMat=瑜伽垫|catTree=猫爬架',
 'coatRack=衣帽架|mirror=镜面|fireplace=壁炉|fishTank=鱼缸|projScreen=投影幕|wallTV=壁挂电视|curtain=窗帘|wallArt=挂画|clock=时钟|rug=地毯|rugRound=圆地毯|bayDeck=飘窗台|plushToy=玩偶|bookSet=书籍|slidingBoard=移动白板|mobileDisplay=移动显示屏|printer=打印机|clothesRack=晾衣架|free=自由造型',
):
    DISPLAY.update(part.split('=',1) for part in vocabulary.split('|'))


def _catalogue_file():
    for root in (ROOT,Path(__file__).resolve().parents[2],Path(__file__).resolve().parents[1]):
        file=root/'references/component-catalogue.json'
        if file.is_file(): return file
    raise ValueError('Complete component catalogue required')


def catalogue():
    entries=json.loads(_catalogue_file().read_text(encoding='utf8'))['entries']
    result=[]
    for row in entries:
        family=TYPE_FAMILY.get(row['type'])
        if family is None: raise ValueError('Unimplemented component family '+row['type'])
        title=DISPLAY.get(row['type'],row['type'])
        if row['type']=='free':
            title=next((label for word,label in [('ArcWall','弧形墙'),('HalfCyl','半圆柱'),('RoundBox','圆角块'),
                ('RoundStage','圆形地台'),('WallBlock','墙体造型块'),('CeilBlock','吊顶块'),('GlassScreen','玻璃隔断'),
                ('Cyl','圆柱'),('Tube','圆管'),('Sphere','球体'),('Hemi','半球'),('Cone','圆锥'),('Pyramid','棱锥'),
                ('Wedge','坡道'),('Arch','拱形'),('Slats','格栅'),('Steps','台阶'),('Torus','圆环'),('LightBox','灯带'),
                ('Mirror','镜板'),('Vase','花瓶'),('Column','装饰柱'),('Extrude','轮廓拉伸'),('Lawn','草坪'),
                ('Gravel','碎石'),('Paver','铺装'),('Deck','平台'),('Water','水景'),('Bed','花池'),('ZoneRound','圆形吊顶'),
                ('ZoneCove','灯带吊顶'),('Zone','吊顶分区'),('BeamWood','装饰木梁')] if word in row['key']),title)
        result.append({**row,'name':f"{title} {row['w']}×{row['d']}",
                       'group':NAMES[family],'native_geometry':True,'implementation':'luomu-parametric'})
    return {'openings':OPENINGS,'furniture':result}


OPENINGS = {
 'door':('单开门',800,0,2100),'double':('双开门',1400,0,2100),'unequal':('子母门',1200,0,2100),
 'sliding':('推拉门',1800,0,2400),'folding':('折叠门',1600,0,2400),'pocket':('暗藏门',850,0,2100),
 'hole':('门洞',900,0,2100),'window':('平开窗',1500,900,2400),'slideWindow':('推拉窗',1500,900,2400),
 'floorWindow':('落地窗',2400,0,2500),'highWindow':('高窗',900,1500,2100),
 'bay':('飘窗',1800,450,2400),'garage':('车库门',3000,0,2400),'glassWall':('玻璃隔断',2400,0,2600)}
OPENINGS={key:dict(zip(('name','width','sill','head'),values)) for key,values in OPENINGS.items()}


def _seat(symbol, w, d, kind, item):
    x,y=-w/2,-d/2
    if kind in ('lSofa','uSofa'):
        t=min(w,d)*.33
        points=[(x,y),(x+w,y),(x+w,y+t),(x+t,y+t),(x+t,y+d),(x,y+d)]
        if kind=='uSofa':points=[(x,y),(x+w,y),(x+w,y+d),(x+w-t,y+d),(x+w-t,y+t),(x+t,y+t),(x+t,y+d),(x,y+d)]
        symbol.poly(points)
        for i in range(max(2,round(w/600))):
            a=x+w*i/max(2,round(w/600));cw=w/max(2,round(w/600))
            symbol.round_rect(a+cw*.08,y+t*.12,cw*.84,t*.7,t*.09)
        for i in range(1,max(2,round(d/600))):
            a=y+d*i/max(2,round(d/600));cd=d/max(2,round(d/600))
            symbol.round_rect(x+t*.12,a,t*.70,cd*.85,t*.08)
            if kind=='uSofa':symbol.round_rect(x+w-t*.82,a,t*.70,cd*.85,t*.08)
        return
    if kind in ('beanbag','ottoman','hangingChair','stool','barStool'):
        symbol.arc(0,0,w/2,d/2);symbol.arc(0,0,w*.37,d*.37)
        if kind=='hangingChair': symbol.arc(0,d*.12,w*.42,d*.35,start=.15,sweep=math.pi-.3)
        else: symbol.line((-w*.2,0),(w*.2,0));symbol.line((0,-d*.2),(0,d*.2))
        return
    if kind in ('curvedSofa','bendSofa'):
        custom=item.get('opt',{}).get('path')
        if not custom and kind=='bendSofa' and '_' in item['key']:
            if 'serpentine' in item['key']:
                points=[((u-.5)*w*.80,math.sin(TAU*u)*d*.20,d*.28) for u in [i/8 for i in range(9)]]
            elif 'crescent' in item['key']:
                points=[((u-.5)*w*.78,d*(.24*(2*u-1)**2-.12),d*(.22+.14*(1-(2*u-1)**2))) for u in [i/8 for i in range(9)]]
            else:
                points=[(-w*.35,d*.23),(0,d*.23),(w*.23,0),(w*.23,-d*.35)]
                points=[(*p,min(w,d)*.25) for p in points]
            custom='|'.join(','.join(str(v) for v in p) for p in points)
        if custom:
            rows=[list(map(float,part.split(','))) for part in custom.split('|')]
            if len(rows)<2 or any(len(p) not in (2,3) or not all(math.isfinite(v) for v in p) for p in rows):
                raise ValueError('Custom curved seat requires finite path points')
            left=[];right=[]
            if item.get('opt',{}).get('flip'):
                rows=[[-p[0],*p[1:]] for p in rows]
            for i,p in enumerate(rows):
                before,after=rows[max(0,i-1)],rows[min(len(rows)-1,i+1)]
                dx,dy=after[0]-before[0],after[1]-before[1];length=math.hypot(dx,dy)
                if not length:raise ValueError('Repeated seat path points')
                depth=p[2] if len(p)==3 else min(w,d)*.4
                if depth<=0:raise ValueError('Positive seat depth required')
                offset=(-dy/length*depth/2,dx/length*depth/2)
                left.append((p[0]+offset[0],p[1]+offset[1]));right.append((p[0]-offset[0],p[1]-offset[1]))
                symbol.line(left[-1],right[-1])
            for points in (left,right):symbol.smooth(points)
            symbol.line(left[0],right[0]);symbol.line(left[-1],right[-1])
            return
        # Own cubic annular seat; user path points provide an optional custom baseline.
        symbol.curve([(-w/2,-d*.15),(-w*.25,d*.55),(w*.25,d*.55),(w/2,-d*.15)])
        symbol.curve([(-w*.42,-d*.4),(-w*.22,d*.15),(w*.22,d*.15),(w*.42,-d*.4)])
        symbol.line((-w/2,-d*.15),(-w*.42,-d*.4));symbol.line((w/2,-d*.15),(w*.42,-d*.4))
        for i in range(1,6):
            u=i/6;xx=(u-.5)*w*.86; yy=d*(.22-.6*(2*u-1)**2)
            symbol.line((xx,yy-d*.12),(xx,yy+d*.12))
        return
    symbol.round_rect(x,y,w,d,min(w,d)*.10)
    symbol.round_rect(x+w*.12,y+d*.12,w*.76,d*.70,min(w,d)*.055)
    symbol.rect(x+w*.12,y+d*.82,w*.76,d*.12)
    symbol.rect(x+w*.025,y+d*.12,w*.075,d*.74);symbol.rect(x+w*.90,y+d*.12,w*.075,d*.74)
    n=max(1,round(w/min(d,650)))
    for i in range(1,n):symbol.line((x+w*.12+w*.76*i/n,y+d*.13),(x+w*.12+w*.76*i/n,y+d*.80))
    if kind in ('lSofa','uSofa','chaise','lounge'):
        symbol.rect(x+w*.12,y+d*.12,w*.26,d*.50)
        if kind=='uSofa':symbol.rect(x+w*.62,y+d*.12,w*.26,d*.50)
    if kind in ('chair','officeChair','rockingChair'):
        for xx,yy in [(-w*.35,-d*.42),(w*.35,-d*.42),(-w*.35,d*.42),(w*.35,d*.42)]:
            symbol.arc(xx,yy,min(w,d)*.025)
        if kind=='officeChair':
            for i in range(5):
                a=TAU*i/5;symbol.line((0,-d*.05),(math.cos(a)*w*.38,math.sin(a)*d*.38))


def _sleep(s,w,d,kind,item):
    if kind in ('roundBed','petBed'):
        s.arc(0,0,w/2,d/2);s.arc(0,0,w*.44,d*.44);s.round_rect(-w*.2,d*.14,w*.4,d*.20,min(w,d)*.05);return
    s.box(w,d);s.box(w,d,min(w,d)*.035)
    if kind in ('nightstand','bedBench','bayCushion'):
        s.line((-w*.4,0),(w*.4,0));s.arc(0,-d*.14,min(w,d)*.025);return
    s.rect(-w/2,d*.35,w,d*.15)
    count=2 if w>=1400 else 1
    for i in range(count):
        pw=w*.82/count;s.round_rect(-w*.41+i*pw,d*.12,pw*.92,d*.20,min(w,d)*.035)
    s.line((-w*.45,d*.04),(w*.45,d*.04))
    s.curve([(-w*.42,-d*.22),(-w*.10,-d*.10),(w*.15,-d*.35),(w*.42,-d*.20)])
    if kind in ('bunkBed','crib'):
        s.ribs(w,d,12,True)
        if kind=='bunkBed':
            for i in range(5):s.line((w*.30,-d*.3+i*d*.12),(w*.48,-d*.3+i*d*.12))


def _table(s,w,d,kind,item):
    if kind in ('roundTable','ovalTable'):
        s.arc(0,0,w/2,d/2);s.arc(0,0,w*.45,d*.45)
    elif kind in ('lDesk','lCounter','uCounter'):
        t=min(w,d)*.30
        points=[(-w/2,-d/2),(w/2,-d/2),(w/2,-d/2+t),(-w/2+t,-d/2+t),(-w/2+t,d/2),(-w/2,d/2)]
        if kind=='uCounter':points=[(-w/2,-d/2),(w/2,-d/2),(w/2,d/2),(w/2-t,d/2),(w/2-t,-d/2+t),(-w/2+t,-d/2+t),(-w/2+t,d/2),(-w/2,d/2)]
        s.poly(points);s.line((-w*.45,-d*.35),(w*.40,-d*.35))
    else:
        s.round_rect(-w/2,-d/2,w,d,min(w,d)*.055)
        s.round_rect(-w*.46,-d*.43,w*.92,d*.86,min(w,d)*.03)
    if kind in ('desk','trainingTable','workbench','lectern'):
        s.rect(-w*.30,d*.05,w*.60,d*.27);s.line((-w*.20,d*.05),(-w*.20,d*.32))
        s.rect(-w*.15,-d*.32,w*.30,d*.17)
    elif kind in ('diningTable','teaTable','outdoorSet'):
        n=max(2,round(w/600))
        for i in range(n):
            x=-w*.38+w*.76*(i+.5)/n
            s.round_rect(x-w*.06,-d*.47,w*.12,d*.13,min(w,d)*.025)
            s.round_rect(x-w*.06,d*.34,w*.12,d*.13,min(w,d)*.025)
    else:
        for x,y in [(-w*.34,-d*.27),(w*.34,d*.27)]:s.arc(x,y,min(w,d)*.035)


def _kitchen(s,w,d,kind,item):
    """Plan-view kitchen legs with independently positioned basin/hob modules."""
    options=item.get('kit',{})
    if not isinstance(options,dict):raise ValueError('Kitchen configuration must be an object')
    shape=options.get('shape',{'lCounter':'L','uCounter':'U'}.get(kind,'I'))
    if shape not in ('I','L','U'):raise ValueError('Kitchen shape requires I/L/U')
    depth=options.get('depth',min(d,600))
    if isinstance(depth,bool) or not isinstance(depth,(int,float)) or not math.isfinite(depth) or depth<=0:
        raise ValueError('Positive kitchen depth required')
    if depth>d or (shape in ('L','U') and depth>=w) or (shape=='U' and 2*depth>=w):
        raise ValueError('Kitchen depth does not fit the supplied footprint')
    legs=[((-w/2,-d/2),(1,0),(0,1),w)]
    if shape in ('L','U'):
        corner=options.get('corner','left')
        if corner not in ('left','right'):raise ValueError('Kitchen corner requires left/right')
        direction=-1 if corner=='right' else 1
        x=w/2 if direction==-1 else -w/2
        legs.append(((x,-d/2+depth),(0,1),(direction,0),d-depth))
        if shape=='U':legs.append(((-x,-d/2+depth),(0,1),(-direction,0),d-depth))
    footprints=[]
    for origin,u,n,length in legs:
        point=lambda at,across:(origin[0]+u[0]*at+n[0]*across,origin[1]+u[1]*at+n[1]*across)
        footprints.append(Polygon([point(0,0),point(length,0),point(length,depth),point(0,depth)]))
        for i in range(1,max(2,math.ceil(length/600))):
            at=length*i/max(2,math.ceil(length/600));s.line(point(at,0),point(at,depth))
        if options.get('wall',True):
            wall_depth=options.get('wallD',depth*.45)
            if not isinstance(wall_depth,(float,int)) or not math.isfinite(wall_depth) or wall_depth<=0:
                raise ValueError('Positive upper cabinet depth required')
            wall_depth=min(wall_depth,depth)
            selected=options.get('wallLegs')
            if selected is None or legs.index((origin,u,n,length)) in selected:
                s.poly([point(0,depth-wall_depth),point(length,depth-wall_depth),
                        point(length,depth),point(0,depth)],dashed=True)
    region=unary_union(footprints)
    for poly in list(region.geoms) if hasattr(region,'geoms') else [region]:
        s.poly(list(poly.exterior.coords)[:-1])
    for feature,default_position in [('sink',.27),('hob',.73)]:
        definition=options.get(feature,{})
        if definition is False:continue
        if not isinstance(definition,dict):raise ValueError('Kitchen feature configuration must be an object')
        if definition.get('off'):continue
        leg=definition.get('leg',0)
        if type(leg) is not int or not 0<=leg<len(legs):raise ValueError('Kitchen feature leg does not exist')
        origin,u,n,length=legs[leg]
        feature_width=definition.get('w',min(750,length*.3))
        at=definition.get('at',length*default_position)
        if any(isinstance(v,bool) or not isinstance(v,(float,int)) or not math.isfinite(v) for v in (feature_width,at)):
            raise ValueError('Finite kitchen feature position and width required')
        if feature_width<=0 or feature_width>length or at-feature_width/2<0 or at+feature_width/2>length:
            raise ValueError('Kitchen feature does not fit the selected leg')
        center=(origin[0]+u[0]*at+n[0]*depth*.5,origin[1]+u[1]*at+n[1]*depth*.5)
        feature_symbol=Symbol(*s.point(*center),math.atan2(s.s,s.c)+math.atan2(u[1],u[0]))
        if feature=='sink':
            bowls=definition.get('bowls',1)
            if type(bowls) is not int or not 1<=bowls<=4:raise ValueError('Sink bowls requires 1..4')
            feature_symbol.round_rect(-feature_width/2,-depth*.34,feature_width,depth*.68,depth*.05)
            for i in range(bowls):
                span=feature_width*.88/bowls;xx=-feature_width*.44+span*i
                feature_symbol.round_rect(xx,-depth*.25,span*.92,depth*.48,depth*.06)
                feature_symbol.arc(xx+span*.46,0,depth*.025)
            feature_symbol.line((0,depth*.32),(0,depth*.43))
        else:
            burners=definition.get('burners',2)
            if type(burners) is not int or not 1<=burners<=6:raise ValueError('Burners requires 1..6')
            feature_symbol.rect(-feature_width/2,-depth*.34,feature_width,depth*.68)
            columns=min(3,burners);rows=math.ceil(burners/columns)
            for i in range(burners):
                xx=-feature_width/2+feature_width*(i%columns+.5)/columns
                yy=-depth*.25+depth*.5*(i//columns+.5)/rows
                radius=min(feature_width/columns,depth*.5/rows)*.28
                feature_symbol.arc(xx,yy,radius);feature_symbol.arc(xx,yy,radius*.65)
            if options.get('hood',True):feature_symbol.box(feature_width*.90,depth*.80,dashed=True)
        s.entities.extend(feature_symbol.entities)


def _storage(s,w,d,kind,item):
    cab=item.get('cab',{})
    if cab.get('shape')=='L':
        depth=min(cab.get('depth',min(w,d)*.3),min(w,d)*.8)
        angle=math.atan2(s.s,s.c)
        bottom=Symbol(*s.point(0,-d/2+depth/2),angle)
        upright=Symbol(*s.point(-w/2+depth/2,depth/2),angle+math.pi/2)
        plain={**item,'cab':{k:v for k,v in cab.items() if k not in ('shape','depth')}}
        _storage(bottom,w,depth,kind,plain);_storage(upright,d-depth,depth,kind,plain)
        s.entities.extend(bottom.entities+upright.entities)
        return
    else:s.box(w,d);s.box(w,d,min(w,d)*.04)
    cols=cab.get('cols') or ['door']*max(2,min(12,round(w/450)))
    if not isinstance(cols,list) or not cols:raise ValueError('Cabinet cols requires a list')
    widths=cab.get('ws') or [1]*len(cols)
    if len(widths)!=len(cols) or any(isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(v) or v<=0 for v in widths):
        raise ValueError('Cabinet widths must match cols and be positive')
    cursor=-w/2;total=sum(widths);count=len(cols)
    for mode,weight in zip(cols,widths):
        span=w*weight/total;x=cursor+span/2;cursor+=span
        s.line((cursor,-d*.45),(cursor,d*.45))
        if mode in ('open','hang','niche'):
            s.line((x-span*.4,d*.2),(x+span*.4,d*.2))
            if mode=='hang':
                for i in range(4):s.poly([(x-span*.3+i*span*.18,d*.18),(x-span*.36+i*span*.18,-d*.1),(x-span*.24+i*span*.18,-d*.1)],False)
        elif mode=='drawer':
            for y in (-d*.25,0,d*.25):s.line((x-span*.4,y),(x+span*.4,y))
        elif cab.get('door')=='sliding':
            s.line((x-span*.44,-d*.25),(x+span*.44,-d*.25));s.line((x-span*.35,-d*.15),(x+span*.35,-d*.15))
        elif mode=='glass':
            s.rect(x-span*.35,-d*.3,span*.7,d*.6);s.line((x-span*.3,-d*.25),(x+span*.3,d*.25))
    for i in range(count):
        x=-w/2+w*(i+.5)/count
        if kind in ('bookshelf','shelfRack','garageShelf','plantShelf'):
            for j in range(3):s.rect(x-w/count*.35+j*w/count*.22,-d*.22,w/count*.14,d*.42)
        else:
            s.line((x-w/count*.12,-d*.32),(x+w/count*.12,-d*.32))
            if kind in ('wardrobe','shoeCabinet'):s.line((x-w/count*.40,d*.35),(x+w/count*.40,-d*.35))
    if kind=='wineCabinet':
        for i in range(count):s.arc(-w/2+w*(i+.5)/count,0,min(w/count,d)*.17)


def _sanitary(s,w,d,kind,item):
    if kind in ('toilet','squat','urinal'):
        if kind=='toilet':
            s.round_rect(-w*.45,d*.24,w*.90,d*.26,w*.07)
            s.curve([(-w*.42,d*.24),(-w*.55,-d*.46),(w*.55,-d*.46),(w*.42,d*.24)])
            s.line((-w*.42,d*.24),(w*.42,d*.24))
            s.arc(0,-d*.02,w*.28,d*.27);s.arc(0,d*.38,w*.035)
        else:
            s.round_rect(-w*.48,-d*.48,w*.96,d*.96,min(w,d)*.12)
            s.arc(0,0,w*.26,d*.35)
            for side in (-1,1):
                s.rect(side*w*.36-w*.07,-d*.28,w*.14,d*.56)
                for j in range(5):s.line((side*w*.36-w*.06,-d*.22+j*d*.10),(side*w*.36+w*.06,-d*.22+j*d*.10))
        return
    if kind in ('freeTub','bathtub'):
        s.round_rect(-w/2,-d/2,w,d,min(w,d)*.30)
        s.round_rect(-w*.43,-d*.38,w*.86,d*.76,min(w,d)*.25)
        s.arc(w*.28,0,min(w,d)*.025);s.line((-w*.32,-d*.30),(-w*.32,d*.30));return
    if kind in ('shower','showerScreen','showerSet'):
        s.box(w,d);s.arc(0,0,min(w,d)*.045)
        s.line((-w*.45,-d*.45),(w*.45,d*.45),True);s.line((-w*.45,d*.45),(w*.45,-d*.45),True)
        s.arc(-w*.4,-d*.4,min(w,d)*.60,start=0,sweep=math.pi/2)
        for i in range(4):s.line((-w*.1+i*w*.06,d*.35),(-w*.1+i*w*.06,d*.20))
        return
    if kind=='towelWarmer':
        s.box(w,d);s.ribs(w,d,10,False);return
    s.round_rect(-w/2,-d/2,w,d,min(w,d)*.07)
    count=max(1,round(w/1000))
    for i in range(count):
        x=-w/2+w*(i+.5)/count;s.arc(x,-d*.04,w/count*.32,d*.32)
        s.arc(x,-d*.04,min(w/count,d)*.035);s.rect(x-w/count*.04,d*.30,w/count*.08,d*.14)


def _equipment(s,w,d,kind,item):
    circular={'robotVac','tank','ceilLamp','inGround','wifiAP','ceilingSpeaker','bubblePendant','floorLamp','deskLamp','ceilingFan','fan'}
    if kind in circular:
        s.arc(0,0,w/2,d/2);s.arc(0,0,w*.35,d*.35)
        n=3 if kind in ('fan','ceilingFan') else 4
        for i in range(n):
            a=TAU*i/n;s.line((0,0),(w*.4*math.cos(a),d*.4*math.sin(a)))
        s.arc(0,0,min(w,d)*.07);return
    s.round_rect(-w/2,-d/2,w,d,min(w,d)*.06);s.box(w,d,min(w,d)*.09)
    if kind in ('washer','dryer','washerTower'):
        s.arc(0,0,w*.34,d*.34);s.arc(0,0,w*.28,d*.28)
        for i in range(3):s.arc(w*(-.25+.15*i),d*.38,min(w,d)*.02)
    elif kind in ('airVent','linearVent','acWall','acOutdoor','vrfOutdoor','ductAC','radiator','manifold','floorHeat','freshAirUnit'):
        s.ribs(w,d,min(18,max(5,round(w/150))))
        s.line((-w*.35,-d*.35),(w*.35,d*.35))
    elif kind in ('fridge','freezer','dishwasher','microwave','tallOven','integratedStove'):
        s.line((-w*.45,d*.22),(w*.45,d*.22));s.line((-w*.30,d*.32),(w*.30,d*.32))
        if kind=='integratedStove':
            for x in (-w*.25,w*.25):s.arc(x,-d*.06,min(w,d)*.17);s.arc(x,-d*.06,min(w,d)*.11)
        else:s.rect(-w*.30,-d*.30,w*.60,d*.40)
    else:
        s.ribs(w,d,5,False)
        for x in (-w*.25,0,w*.25):s.arc(x,d*.31,min(w,d)*.025)


def _garden(s,w,d,kind,item):
    if kind in ('tree','plant','shrub','hedge','palm','bamboo','hangingPlant','planterBox','flowerBed','vase','tableVase'):
        if kind in ('planterBox','flowerBed','hedge'):s.box(w,d)
        count=9 if kind in ('tree','palm') else 6
        for i in range(count):
            a=TAU*i/count
            s.curve([(0,0),(math.cos(a-.3)*w*.35,math.sin(a-.3)*d*.35),
                     (math.cos(a+.3)*w*.48,math.sin(a+.3)*d*.48),(math.cos(a)*w*.30,math.sin(a)*d*.30)])
        s.arc(0,0,min(w,d)*.08);return
    if kind in ('pool','waterFeature','firePit'):
        s.round_rect(-w/2,-d/2,w,d,min(w,d)*.18);s.round_rect(-w*.43,-d*.40,w*.86,d*.8,min(w,d)*.16)
        for i in range(4):
            yy=d*(-.25+i*.15);s.curve([(-w*.35,yy),(-w*.1,yy+d*.08),(w*.1,yy-d*.08),(w*.35,yy)])
        return
    if kind in ('parasol','gazebo','pergola','carport'):
        s.box(w,d)
        for x in (-w*.43,w*.43):
            for y in (-d*.43,d*.43):s.rect(x-w*.025,y-d*.025,w*.05,d*.05)
        s.line((-w/2,-d/2),(w/2,d/2));s.line((-w/2,d/2),(w/2,-d/2));s.ribs(w,d,7);return
    s.box(w,d);s.box(w,d,min(w,d)*.08)
    s.ribs(w,d,8,kind not in ('fence','gate','lawn'))
    if kind in ('stepStones','rock'):
        for i in range(4):s.arc(-w*.32+i*w*.21,0,w*.08,d*.30)


def _free(s,w,d,key,item):
    shape=item.get('opt',{}).get('shape','')
    if not shape:
        options={'Cyl':'cyl','Tube':'tube','Sphere':'sphere','Hemi':'hemi','Cone':'cone',
          'Pyramid':'pyramid','Wedge':'wedge','Arch':'arch','ArcWall':'arcWall','Slats':'slats','Steps':'steps',
          'Torus':'torus','Vase':'lathe','Column':'lathe','RoundBox':'roundBox','RoundStage':'cyl',
          'HalfCyl':'halfCyl','Round':'cyl'}
        shape=next((options[k] for k in sorted(options,key=len,reverse=True) if k.lower() in key.lower()),'box')
    outline=item.get('opt',{}).get('outline')
    if outline:
        pts=[tuple(map(float,p.split(','))) for p in outline.split('|')]
        if len(pts)<3 or any(len(p)!=2 or not all(math.isfinite(v) for v in p) for p in pts):raise ValueError('Invalid explicit outline')
        poly=Polygon(pts)
        if not poly.is_valid or poly.area<=0:raise ValueError('Invalid outline polygon')
        s.poly(pts)
        return
    if shape in ('cyl','sphere','hemi','cone','tube','torus','lathe'):
        s.arc(0,0,w/2,d/2)
        if shape in ('tube','torus','lathe'):s.arc(0,0,w*.36,d*.36)
        elif shape=='cone':
            for a in (0,math.pi/2,math.pi,math.pi*1.5):s.line((0,0),(math.cos(a)*w/2,math.sin(a)*d/2))
        return
    if shape=='halfCyl':
        s.arc(0,-d/2,w/2,d,start=0,sweep=math.pi);s.line((-w/2,-d/2),(w/2,-d/2));return
    if shape=='arcWall':
        s.arc(0,-d/2,w/2,d,start=0,sweep=math.pi)
        s.arc(0,-d/2,w*.44,d*.7,start=0,sweep=math.pi)
        s.line((-w/2,-d/2),(-w*.44,-d/2));s.line((w/2,-d/2),(w*.44,-d/2));return
    if shape=='roundBox':s.round_rect(-w/2,-d/2,w,d,min(w,d)*.14)
    else:s.box(w,d)
    if shape in ('pyramid','wedge','arch'):
        s.line((-w/2,-d/2),(w/2,d/2));s.line((-w/2,d/2),(w/2,-d/2))
    if shape in ('slats','steps') or key in ('ceilSlats','ceilBeamWood'):
        n=item.get('opt',{}).get('n',8)
        if type(n) is not int or not 1<=n<=200:raise ValueError('Finite slat/step count required')
        s.ribs(w,d,n,shape!='steps')
    if key.startswith('land') or key.startswith('ceilZone'):
        s.box(w,d,min(w,d)*.055);s.ribs(w,d,9,False)


def furniture_geometry(item):
    template=next((r for r in catalogue()['furniture'] if r['key']==item.get('key')),None)
    if template is None:raise ValueError('Unknown furniture component key')
    obj={**template,**item};w,d=obj['w'],obj['d'];kind=obj['type']
    if kind=='cabinet' and not obj.get('cab'):
        obj['cab']={'cols':['door','drawer','door']}
        if 'Corner' in obj['key']:obj['cab'].update(shape='L',depth=min(w,d)*.30)
        if 'Slide' in obj['key']:obj['cab'].update(door='sliding')
        if 'Wardrobe' in obj['key']:obj['cab'].update(cols=['hang','drawer','hang'])
    if not all(isinstance(v,(int,float)) and math.isfinite(v) and v>0 for v in (w,d)):raise ValueError('Positive furniture dimensions required')
    symbol=Symbol(obj.get('x',0),obj.get('y',0),math.radians(obj.get('rot',0)))
    family=TYPE_FAMILY[kind]
    if kind=='clock':
        symbol.arc(0,0,w/2,d/2);symbol.arc(0,0,w*.43,d*.43)
        for i in range(12):
            a=TAU*i/12;symbol.line((w*.37*math.cos(a),d*.37*math.sin(a)),(w*.42*math.cos(a),d*.42*math.sin(a)))
        symbol.line((0,0),(w*.1,d*.26));symbol.line((0,0),(-w*.24,d*.07))
    elif kind=='curtain':
        symbol.line((-w/2,d*.4),(w/2,d*.4))
        for i in range(12):
            x=-w/2+w*i/12
            symbol.curve([(x,d*.30),(x+w*.025,-d*.5),(x+w*.05,-d*.5),(x+w/12,d*.30)])
    elif kind in ('rug','rugRound'):
        if kind=='rugRound':symbol.arc(0,0,w/2,d/2);symbol.arc(0,0,w*.44,d*.44)
        else:symbol.box(w,d);symbol.box(w,d,min(w,d)*.06)
        symbol.ribs(w,d,10)
    elif kind in ('wallTV','projScreen','mobileDisplay','slidingBoard'):
        symbol.box(w,d);symbol.box(w,d,min(w,d)*.12)
        for xx in (-w*.32,w*.32):symbol.line((xx,-d*.48),(xx,-d*.60))
    elif kind=='bookSet':
        for i in range(5):symbol.rect(-w/2+i*w*.2,-d/2,w*.18,d*(.8+.04*i))
    elif kind in ('mirror','wallArt'):
        symbol.round_rect(-w/2,-d/2,w,d,min(w,d)*.12);symbol.box(w,d,min(w,d)*.09)
        if kind=='mirror':symbol.line((-w*.30,-d*.30),(w*.30,d*.30))
    elif kind=='coatRack':
        symbol.arc(0,0,min(w,d)*.12)
        for i in range(6):
            a=TAU*i/6;symbol.line((0,0),(w*.4*math.cos(a),d*.4*math.sin(a)));symbol.arc(w*.4*math.cos(a),d*.4*math.sin(a),min(w,d)*.03)
    elif family=='sleep':_sleep(symbol,w,d,kind,obj)
    elif family=='seat':_seat(symbol,w,d,kind,obj)
    elif kind in ('counter','lCounter','uCounter'):_kitchen(symbol,w,d,kind,obj)
    elif family=='table':_table(symbol,w,d,kind,obj)
    elif family=='storage':_storage(symbol,w,d,kind,obj)
    elif family=='sanitary':_sanitary(symbol,w,d,kind,obj)
    elif family in ('machine','kitchen','light'):_equipment(symbol,w,d,kind,obj)
    elif family=='garden':_garden(symbol,w,d,kind,obj)
    elif family=='free':_free(symbol,w,d,obj['key'],obj)
    elif family=='circulation':
        if kind=='riser':
            symbol.arc(0,0,w/2,d/2);symbol.arc(0,0,w*.35,d*.35)
            symbol.line((-w*.25,0),(w*.25,0));symbol.line((0,-d*.25),(0,d*.25))
        else:
            symbol.box(w,d)
            if kind in ('stairU','stairDogleg'):
                landing=d*.22;top=d/2-landing;gap=w*.16
                symbol.line((-w/2,top),(w/2,top))
                for i in range(1,13):
                    yy=-d/2+(d-landing)*i/13
                    symbol.line((-w/2,yy),(-gap/2,yy));symbol.line((gap/2,yy),(w/2,yy))
                for xx,direction in [(-w*.28,1),(w*.28,-1)]:
                    symbol.line((xx,-d*.35),(xx,top-d*.08))
                    end=top-d*.08 if direction==1 else -d*.35
                    symbol.poly([(xx-w*.06,end-direction*d*.08),(xx,end),(xx+w*.06,end-direction*d*.08)],False)
                symbol.line((-gap/2,-d/2),(-gap/2,top));symbol.line((gap/2,-d/2),(gap/2,top))
            elif kind=='elevator':
                symbol.box(w,d,min(w,d)*.10);symbol.line((-w*.4,-d*.4),(w*.4,d*.4));symbol.line((-w*.4,d*.4),(w*.4,-d*.4))
            else:
                symbol.ribs(w,d,14,False);symbol.line((0,-d*.4),(0,d*.4))
                symbol.poly([(-w*.09,d*.24),(0,d*.4),(w*.09,d*.24)],False)
    elif family=='vehicle':
        symbol.round_rect(-w/2,-d/2,w,d,min(w,d)*.18)
        symbol.round_rect(-w*.38,-d*.25,w*.76,d*.50,min(w,d)*.08)
        for xx in (-w*.47,w*.37):
            for yy in (-d*.30,d*.20):symbol.rect(xx,yy,w*.10,d*.10)
        if kind=='bicycle':
            for xx in (-w*.29,w*.29):symbol.arc(xx,0,w*.20,d*.40)
    elif family=='leisure':
        symbol.round_rect(-w/2,-d/2,w,d,min(w,d)*.12);symbol.box(w,d,min(w,d)*.10)
        if kind in ('piano','grandPiano'):
            for i in range(14):symbol.rect(-w*.42+i*w*.06,-d*.4,w*.055,d*.18)
        elif kind in ('billiards','mahjong'):
            for x in (-w*.4,0,w*.4):
                for y in (-d*.4,d*.4):symbol.arc(x,y,min(w,d)*.025)
            symbol.arc(0,0,min(w,d)*.05)
        else:symbol.ribs(w,d,9);symbol.arc(0,0,w*.20,d*.20)
    else:
        symbol.box(w,d);symbol.box(w,d,min(w,d)*.07)
        if kind in ('rug','rugRound'):symbol.ribs(w,d,10)
        elif kind in ('clock','mirror','fishTank'):symbol.arc(0,0,w*.38,d*.38)
        else:
            symbol.line((-w*.4,-d*.3),(w*.4,d*.3));symbol.line((-w*.4,d*.3),(w*.4,-d*.3))
            symbol.ribs(w,d,4)
    if not symbol.entities:raise ValueError('No native geometry created')
    return {'id':item.get('id'),'key':obj['key'],'name':obj['name'],'entities':symbol.entities,'family':family}


def _opening(wall, opening):
    a,b=wall['a_point'],wall['b_point'];angle=math.atan2(b[1]-a[1],b[0]-a[0])
    width=opening['width'];start=opening['pos']-width/2;side=opening['side'];half=wall['t']/2
    s=Symbol(*a,angle);kind=opening['type']
    for xx in (start,start+width):s.line((xx,-half),(xx,half))
    jambs=[s.point(start,side*half),s.point(start+width,side*half)]
    def leaf(hinge,closed,radius,thickness=40):
        target=(hinge,side*half+side*radius)
        for offset in (-thickness/2,thickness/2):s.line((hinge+offset,side*half),(target[0]+offset,target[1]))
        s.line((target[0]-thickness/2,target[1]),(target[0]+thickness/2,target[1]))
        direction=1 if closed>hinge else -1
        initial=0 if direction==1 else math.pi
        sweep=side*direction*math.pi/2
        s.arc(hinge,side*half,radius,start=initial,sweep=sweep)
    if kind=='door':leaf(start+width if opening['hinge'] else start,start if opening['hinge'] else start+width,width)
    elif kind in ('double','unequal'):
        split=.5 if kind=='double' else .65
        leaf(start,start+width*split,width*split);leaf(start+width,start+width*split,width*(1-split))
    elif kind in ('sliding','pocket'):
        for i in range(2):
            xx=start+width*.5*i;yy=(-.2 if i==0 else .2)*half
            s.rect(xx,yy-half*.12,width*.60,half*.24)
        s.line((start+width*.2,0),(start+width*.8,0));s.poly([(start+width*.7,-half*.20),(start+width*.8,0),(start+width*.7,half*.20)],False)
    elif kind=='folding':
        pts=[(start+width*i/6,side*(half+(.18*width if i%2 else 0))) for i in range(7)]
        s.poly(pts,False)
    elif kind=='garage':
        for i in range(1,8):s.line((start+width*i/8,-half),(start+width*i/8,half))
        s.line((start,-half),(start+width,-half));s.line((start,half),(start+width,half))
    elif kind!='hole':
        for yy in (-half*.45,0,half*.45):s.line((start,yy),(start+width,yy),kind=='highWindow')
        if kind in ('window','slideWindow','glassWall'):
            n=max(2,round(width/600))
            for i in range(1,n):s.line((start+width*i/n,-half*.45),(start+width*i/n,half*.45))
        if kind=='bay':
            exterior=wall['exterior_side'];offset=exterior*(half+min(width*.25,600))
            s.poly([(start,exterior*half),(start,offset),(start+width,offset),(start+width,exterior*half)],False)
    return {'id':opening['id'],'wall':wall['id'],'type':kind,'jambs':jambs,'entities':s.entities}


def assemble(plan):
    nodes={r['id']:(r['x'],r['y']) for r in plan.get('nodes',[])}
    walls=[];by_id={};at_node={}
    for row in plan.get('walls',[]):
        wall={**row,'a_point':nodes[row['a']],'b_point':nodes[row['b']]}
        wall['region']=LineString([wall['a_point'],wall['b_point']]).buffer(row['t']/2,cap_style='flat')
        by_id[row['id']]=wall
        for end in ('a','b'):at_node.setdefault(row[end],[]).append(wall)
    junctions=[]
    for node,incident in at_node.items():
        if len(incident)<2:continue
        center=nodes[node]
        for index,first in enumerate(incident):
            for second in incident[index+1:]:
                p=first['b_point'] if first['a']==node else first['a_point']
                q=second['b_point'] if second['a']==node else second['a_point']
                radius=max(first['t'],second['t'])*4
                joint=LineString([p,center,q]).buffer(min(first['t'],second['t'])/2,cap_style='flat',join_style='mitre',mitre_limit=4)
                junctions.append((first['id']+'+'+second['id'],joint.intersection(Point(center).buffer(radius))))
    openings=[]
    for opening in plan.get('openings',[]):
        wall=by_id[opening['wall']]
        start=opening['pos']-opening['width']/2
        a,b=wall['a_point'],wall['b_point'];length=math.dist(a,b);ux,uy=(b[0]-a[0])/length,(b[1]-a[1])/length
        ends=[(a[0]+ux*s,a[1]+uy*s) for s in (start,start+opening['width'])]
        wall['region']=wall['region'].difference(LineString(ends).buffer(wall['t']/2+1,cap_style='flat'))
        openings.append(_opening(wall,opening))
    for identity,region in [(w['id'],w['region']) for w in by_id.values()]+junctions:
        for poly in list(region.geoms) if hasattr(region,'geoms') else [region]:
            if isinstance(poly,Polygon) and not poly.is_empty:
                walls.append({'wall':identity,'polygon':[list(p) for p in list(poly.exterior.coords)[:-1]]})
    return {'walls':walls,'openings':openings,'furniture':[furniture_geometry(row) for row in plan.get('furniture',[])]}
