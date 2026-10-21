"""Documentation only. No enhancement, glyph classification, or solver."""
from pathlib import Path
import json,hashlib
from PIL import Image,ImageDraw
R=Path(__file__).resolve().parents[1]
p=R/'source/Dorabella-cipher-image.png'
assert hashlib.sha1(p.read_bytes()).hexdigest()=='ccbc8de6d7bba5170fb247eebffeb3bd98119d11'
im=Image.open(p).convert('RGB');assert im.size==(433,161)
obs=json.loads((R/'observations.json').read_text())
contact=Image.new('RGB',(910,300),'white');d=ImageDraw.Draw(contact)
for i,o in enumerate(obs):
 p=o['position'];assert p==(o['column']+[0,29,60][o['row']-1])
 cr=im.crop(o['bbox_xyxy_exclusive']);cr.save(R/'crops'/f'p{p}.png');x=i*130
 d.text((x+2,4),f'p{p} r{o["row"]}c{o["column"]}',fill='black');contact.paste(cr,(x+10,27))
 contact.paste(cr.resize((cr.width*6,cr.height*6),Image.Resampling.NEAREST),(x+10,75));d.text((x+2,270),'native + 6x pixels',fill='black')
contact.save(R/'target_contact_sheet.png')
centers=[[8,22,34,49,62,81,97,108,122,136,152,168,183],[8,21,33,46,60],[12,30,41,58,80,99,113,128,147,166,182,201,216,234,257,272,289,300]]
regions=[(0,0,202,34),(0,35,85,75),(0,75,313,114)];starts=[1,30,61]
canvas=Image.new('RGB',(1270,660),'white');d=ImageDraw.Draw(canvas)
for j,(pts,b,start) in enumerate(zip(centers,regions,starts)):
 y=j*205;d.text((5,y),f'Row {j+1}; left-to-right; original pixel x labels; p = {start} + column - 1',fill='black')
 canvas.paste(im.crop(b).resize(((b[2]-b[0])*4,(b[3]-b[1])*4),Image.Resampling.NEAREST),(5,y+25))
 for k,x in enumerate(pts):d.text((x*4,y+185),str(start+k),fill='blue')
canvas.save(R/'numbered_prefixes.png')
print('Verified433x161source SHA1;7coordinates and row/column numbers; crops copied, nearest-neighbour only.')
