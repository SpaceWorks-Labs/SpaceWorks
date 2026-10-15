import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from png import load
from collections import Counter
def lum(c):
    f=lambda v:(v/255)/12.92 if v/255<=0.04045 else ((v/255+0.055)/1.055)**2.4
    return sum(f(v)*w for v,w in zip(c,(.2126,.7152,.0722)))
def cr(a,b):
    x,y=sorted((lum(a),lum(b)),reverse=True); return (x+.05)/(y+.05)
w,h,px = load(os.path.join(os.path.dirname(os.path.abspath(__file__)),'crops/org5-settings.png')); print(w,h)
def region(x0,y0,x1,y1): return Counter(px(x,y) for y in range(y0,y1) for x in range(x0,x1))
for name,(x0,y0,x1,y1) in {'heading':(430,718,585,738),'button text':(1050,728,1205,750)}.items():
    c=region(x0,y0,x1,y1); reds=[(k,n) for k,n in c.items() if k[0]>k[1]+40]
    reds.sort(key=lambda kn: lum(kn[0])); print(name,'darkest', reds[:4], 'n', len(reds))
print('button top border', [px(1120,y) for y in range(712,722)])
print('card left border', [px(x,740) for x in range(410,420)])
print('card top border', [px(800,y) for y in range(692,700)])
print('card bg', px(700,765), 'page bg', px(700,450))
