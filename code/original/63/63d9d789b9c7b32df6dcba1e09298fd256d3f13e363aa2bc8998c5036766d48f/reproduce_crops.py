"""Native crops only. No resizing, sharpening, thresholding, OCR or retouching."""
from pathlib import Path
from PIL import Image
import json,hashlib
R=Path(__file__).resolve().parents[1]
paths={'benzedrine':R/'source/dorabella-hires.jpg',
       'wikimedia':R/'source/Dorabella-cipher-image.png',
       's36b':R/'source/S36b_embedded_21.png'}
records=json.loads((R/'all_crop_boxes.json').read_text())
for z in records:
    im=Image.open(paths[z['source']]);assert list(im.size)==z['source_size']
    out=R/'crops'/f"{z['source']}_p{z['position']}.png"
    crop=im.crop(z['bbox_xyxy_exclusive']);assert list(crop.size)==z['crop_size']
    if out.exists():assert crop.tobytes()==Image.open(out).tobytes()
    crop.save(out)
print('PASS:21 native crops match source pixels exactly')
