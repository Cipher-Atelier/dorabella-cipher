"""Public author URLs only. Preserve audited versions; stop on changed bytes."""
from pathlib import Path
import urllib.request,hashlib
R=Path(__file__).resolve().parents[1]
checks={'S36a.pdf':'0b8963f441a400a9b8745b9b269db3d2a771360ceb3dac9f157d759539852be3','S36b.pdf':'7a54445b1ef5a98b046e544b3423c98c4ab518ec9dcc57ce6093aaad37dc34b9'}
for name,h in checks.items():
 p=R/'source'/name
 if p.exists():assert hashlib.sha256(p.read_bytes()).hexdigest()==h;continue
 with urllib.request.urlopen('https://unsolvedproblems.org/'+name,timeout=20) as response:b=response.read()
 assert b.startswith(b'%PDF') and hashlib.sha256(b).hexdigest()==h,'Different publication bytes: do not replace audited source'
 p.write_bytes(b)
print('Two exact audited PDFs present.')
