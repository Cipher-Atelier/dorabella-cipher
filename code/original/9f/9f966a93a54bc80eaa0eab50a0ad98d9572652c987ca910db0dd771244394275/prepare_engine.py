from pathlib import Path
import ast,json,hashlib,shutil
H=Path(__file__).resolve().parents[1]; BASE=H.parent/'dorabella_audit'; LAB=BASE/'test_lab'; R11=BASE/'round11/dorabella_lab/round11'
selected={LAB/'wordpolish_v3.py':['fast_word','char_score'],R11/'engine.py':['key_at','ambiguous_word','scan_block','brute_block']}
parts=['''"""Round13: identical archived numerical function bodies, task-local imports.
The original scan docstring's per-P local Smax is only over unpruned evaluated
keys and need not be the actual local maximum. Global optimum stays exact.
"""
from pathlib import Path
import os,sys,itertools
H=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(H/'deps'))
os.environ.setdefault('NUMBA_CACHE_DIR',str(H/'cache'))
import numpy as np
from numba import njit
P8=np.array(list(itertools.permutations(range(8))),dtype=np.int64)
Q=np.array([[1,0,2],[0,1,2],[0,2,1]],dtype=np.int64)
LETTER=np.array([ord(x)-97 for x in 'abcdefghiklmnopqrstuwxyz'],np.int64)
NK=40320*3*256
''']; rows=[]
for path,names in selected.items():
 src=path.read_text();tree=ast.parse(src)
 for name in names:
  f=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name==name)
  start=min([f.lineno]+[d.lineno for d in f.decorator_list]);frag='\n'.join(src.splitlines()[start-1:f.end_lineno])
  parts.append(frag);rows.append({'function':name,'source':str(path.relative_to(H.parent)),'source_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'body_ast_sha256':hashlib.sha256(ast.dump(ast.Module(body=f.body,type_ignores=[])).encode()).hexdigest()})
(H/'code/engine.py').write_text('\n\n'.join(parts)+'\n')
for source,dest in [(LAB/'round11/data/scoring.npz',H/'data/scoring.npz'),(R11/'data/cases.json',H/'data/cases.json'),(R11/'frozen_protocol.json',H/'data/round11_frozen_protocol.json'),(BASE/'frozen_hash_verification.json',H/'checks/original_frozen_hash_verification.json')]:shutil.copyfile(source,dest)
cases=json.loads((H/'data/cases.json').read_text());assert len(cases)==94 and all(len(c['glyph'])==87 for c in cases)
(H/'data/search_inputs.json').write_text(json.dumps([{'id':c['id'],'kind':c['kind'],'glyph':c['glyph']} for c in cases],indent=2)+'\n')
(H/'checks/engine_body_provenance.json').write_text(json.dumps(rows,indent=2)+'\n')
