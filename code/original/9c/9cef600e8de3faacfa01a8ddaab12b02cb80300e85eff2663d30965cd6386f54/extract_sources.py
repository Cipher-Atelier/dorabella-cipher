"""Repeat extraction of full downloaded PDFs. No solver. Rendering is QA."""
from pathlib import Path
import json,hashlib,fitz
R=Path(__file__).resolve().parents[1]
meta=[]
for name,page in [('S36a',0),('S36b',3)]:
 p=R/'source'/f'{name}.pdf';d=fitz.open(p)
 meta.append({'file':p.name,'pages':len(d),'metadata':d.metadata,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()})
 (R/'source'/f'{name}_text.txt').write_text('\n'.join('\nPAGE '+str(i+1)+'\n'+pg.get_text() for i,pg in enumerate(d)))
 spans=[s for b in d[page].get_text('rawdict')['blocks'] for l in b.get('lines',[]) for s in l['spans'] if s['font']=='DoraBellaCipher']
 (R/'source'/f'{name}_key_font_spans.json').write_text(json.dumps(spans,indent=2)+'\n')
 xf=next(x[0] for x in d[page].get_fonts() if 'DoraBella' in x[3]);(R/'source'/f'{name}_DoraBellaCipher.ttf').write_bytes(d.extract_font(xf)[3])
 if name=='S36b':
  for x in d[1].get_images(full=True):
   z=d.extract_image(x[0]);(R/'source'/('S36b_embedded_'+str(x[0])+'.'+z['ext'])).write_bytes(z['image'])
(R/'results/pdf_inventory.json').write_text(json.dumps(meta,indent=2)+'\n')
print('Metadata, full text, font and facsimile extracted. Visual table collation is recorded separately.')
