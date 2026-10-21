"""Reproduce source metadata and document numbering. No enhancement or OCR."""
from pathlib import Path
from PIL import Image,ImageDraw
import numpy as np,json,hashlib
R=Path(__file__).resolve().parents[1]
for z in json.loads((R/'source_comparison.json').read_text()):
    p=R/z['file'];im=Image.open(p);a=np.asarray(im.convert('L'))
    assert list(im.size)==z['size']
    assert hashlib.sha256(p.read_bytes()).hexdigest()==z['sha256']
    assert len(np.unique(a))==z['decoded_gray_levels']
    print(z['id'],im.size,z['decoded_gray_levels'])
im=Image.open(R/'source/dorabella-hires.jpg')
for z in json.loads((R/'numbering_regions.json').read_text())['regions']:
    crop=im.crop(z['box']);out=Image.new('RGB',(crop.width,crop.height+30),'white');out.paste(crop,(0,30));draw=ImageDraw.Draw(out)
    for n,x in enumerate(z['centers'],z['first']):draw.text((x-5,5),str(n),fill='black')
    dest=R/f"numbering_row{z['row']}.png"
    assert Image.open(dest).tobytes()==out.tobytes()
records=json.loads((R/'all_crop_boxes.json').read_text());ps=[7,8,13,32,34,70,78]
sheet=Image.new('RGB',(1160,520),'white');dr=ImageDraw.Draw(sheet)
for j,p in enumerate(ps):
    x=90+j*150;dr.text((x,5),str(p),fill='black')
    for k,name in enumerate(['benzedrine','s36b','wikimedia']):
        c=Image.open(R/'crops'/f'{name}_p{p}.png');y=30+k*180
        sheet.paste(c.convert('RGB'),(x,y));dr.text((5,y),name,fill='black')
assert Image.open(R/'native_comparison.png').tobytes()==sheet.tobytes()
print('PASS: source properties, native comparison, and three numbered row prefixes')
