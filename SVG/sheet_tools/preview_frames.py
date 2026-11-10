import sys, os, re, json, base64
from playwright.sync_api import sync_playwright
d=sys.argv[1]; out=sys.argv[2]; sets=sys.argv[3].split(','); w=int(sys.argv[4]) if len(sys.argv)>4 else 220
cues=json.load(open(os.path.join(d,'cues.json'))); W,H=cues['canvas']
def cell(inner,lab): return f'<div style="display:inline-block;text-align:center;font:12px sans-serif;margin:2px;vertical-align:top">{inner}<br>{lab}</div>'
def svgf(p,i):
    s=open(p).read(); s=s.replace('<svg ',f'<svg width="{w}" height="{w*H/W:.0f}" ',1)
    return s
rows=[]
r=''
for f in cues['frames']:
    png=base64.b64encode(open(os.path.join(d,f['file'].replace('.svg','.png')),'rb').read()).decode()
    marks=''.join(f'<ellipse cx="{e["x"]}" cy="{e["y"]}" rx="{e["w"]/2}" ry="{e["h"]/2}" fill="none" stroke="#08f" stroke-width="4"/>' for e in f['eyes'])
    if f['nose']: marks+=f'<circle cx="{f["nose"]["x"]}" cy="{f["nose"]["y"]}" r="8" fill="#0c0"/>'
    r+=cell(f'<svg viewBox="0 0 {W} {H}" width="{w}" height="{w*H/W:.0f}"><image href="data:image/png;base64,{png}" width="{W}" height="{H}"/>{marks}</svg>', f'frame {f["frame"]}: cues')
rows.append(r)
rows.append(''.join(cell(svgf(os.path.join(d,f['file']),0),f'frame {f["frame"]}: traced, eyes removed') for f in cues['frames']))
for s in sets:
    rows.append(''.join(cell(svgf(os.path.join(d,f['file'].replace('.svg',f'_{s}.svg')),0),f'kit eyes: {s}') for f in cues['frames']))
html='<html><body style="margin:0;background:#fff">'+''.join(f'<div style="white-space:nowrap">{x}</div>' for x in rows)+'</body></html>'
with sync_playwright() as p:
    b=p.chromium.launch(); pg=b.new_page(viewport={'width':(w+8)*len(cues['frames'])+10,'height':400})
    pg.set_content(html); pg.screenshot(path=out,full_page=True); b.close()
