from pathlib import Path
import json,math,html,hashlib,shutil
from playwright.sync_api import sync_playwright
from PIL import Image
ROOT=Path(__file__).resolve().parent
DEST=ROOT/'browser_preview';DEST.mkdir(exist_ok=True)
# After manual edits, the current PPTX is authoritative. Preview the native
# exports instead of regenerating an HTML layout from an obsolete source deck.
if (ROOT/'deck_order.json').exists():
 order=json.loads((ROOT/'deck_order.json').read_text())
 native=json.loads((ROOT/'powerpoint_validation.json').read_text(encoding='utf-8-sig'))
 sha=hashlib.sha256((ROOT.parent/'StoryBridge_智理杯_5分钟展示.pptx').read_bytes()).hexdigest()
 assert sha==order['pptx_sha256']==native['pptxSha256']
 body=['<!doctype html><meta charset="utf-8"><title>StoryBridge 当前 PPT 原生预览</title><style>body{margin:0;background:#d4d4d4;font-family:sans-serif}section{width:1280px;margin:0 auto 24px}img{display:block;width:1280px;height:720px}p{margin:0;padding:6px}</style>']
 sheet=Image.new('RGB',(1280,math.ceil(order['total_slides']/2)*384),'#D0D0D0')
 for row in order['slides']:
  n=row['page'];src=ROOT/'powerpoint_preview'/f'{n:02d}.png'
  shutil.copyfile(src,DEST/f'{n:02d}.png')
  label=f'{n:02d} · {row["title"]}'+(' · 隐藏备答' if row['hidden'] else '')
  body.append(f'<section><img src="{src.as_uri()}" alt="{html.escape(label)}"><p>{html.escape(label)}</p></section>')
  sheet.paste(Image.open(src).resize((640,360)),(((n-1)%2)*640,((n-1)//2)*384))
 (ROOT/'preview.html').write_text('\n'.join(body))
 sheet.save(DEST/'contact_sheet.jpg')
 (ROOT/'browser_validation.json').write_text(json.dumps({'pptx_sha256':sha,'slides':order['total_slides'],'method':'Preview of current PowerPoint-native exports; text overflow checked by native PowerPoint.','overflow':native['textOverflow']},ensure_ascii=False,indent=2))
 print(json.dumps({'native_preview_pages':order['total_slides'],'overflow':native['textOverflow']},ensure_ascii=False))
 raise SystemExit(0)
with sync_playwright() as p:
 browser=p.chromium.launch(headless=True,args=['--no-sandbox'])
 page=browser.new_page(viewport={'width':1280,'height':760},device_scale_factor=1)
 page.goto((ROOT/'preview.html').as_uri());page.evaluate('document.fonts.ready')
 over=page.locator('.text').evaluate_all('(xs)=>xs.filter(e=>e.scrollHeight>e.clientHeight+2 || e.scrollWidth>e.clientWidth+2).map(e=>({text:e.textContent,h:e.clientHeight,actual:e.scrollHeight}))')
 print(json.dumps({'overflow':over},ensure_ascii=False,indent=2))
 (ROOT/'browser_validation.json').write_text(json.dumps({'slides':page.locator('.slide').count(),'overflow':over},ensure_ascii=False,indent=2))
 for i,s in enumerate(page.locator('.slide').all(),1):s.screenshot(path=str(DEST/f'{i:02d}.png'))
 browser.close()
n=len(list(DEST.glob('*.png')))
sheet=Image.new('RGB',(1280,math.ceil(n/2)*384),'#D0D0D0')
for i in range(n):sheet.paste(Image.open(DEST/f'{i+1:02d}.png').resize((640,360)),((i%2)*640,(i//2)*384))
sheet.save(DEST/'contact_sheet.jpg')
