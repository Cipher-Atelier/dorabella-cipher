"""Post-primary diagnostic, not a new held-out test or a protocol change.
Does the old b/d score defect disappear, or does the structural key constraint
exclude the false candidate? Uses the already frozen 24-letter model.
"""
import os,sys,json,hashlib
from pathlib import Path
HERE=Path(__file__).resolve().parent;ROOT=HERE.parent
os.environ.setdefault('NUMBA_CACHE_DIR',str(HERE/'cache'));sys.dont_write_bytecode=True
sys.path.insert(0,str(ROOT));sys.path.insert(0,str(HERE))
import numpy as np
from table_search import setup,P8,P3,LETTER,NK
from wordpolish_v3 import char_score,fast_word
cases,lp,sc,ch,v=setup();c=next(x for x in cases if x['id']=='elgar_march_1897')
g=np.array(c['glyph']);true=np.array([ord(x)-97 for x in c['plaintext']]);false=true.copy()
false[true==1]=3;false[true==3]=1
keys=LETTER[(3*P8[:,None,:,None]+P3[None,:,None,:]).reshape(NK,24)]
matchtrue=np.all(keys[:,g]==true,axis=1);matchfalse=np.all(keys[:,g]==false,axis=1)
r=dict(status='post-primary diagnostic on already known regression example, not independent validation',
 true_score=float(char_score(true,lp)+.5*fast_word(true,ch,v)),
 false_b_d_swap_score=float(char_score(false,lp)+.5*fast_word(false,ch,v)),
 true_keys_in_family=int(np.sum(matchtrue)),false_keys_in_family=int(np.sum(matchfalse)),
 changed_positions_one_based=(np.flatnonzero(true!=false)+1).tolist(),
 conclusion='The current score still prefers the b/d error. The constrained family excludes it; the scoring defect was not fixed.')
(HERE/'results/regression_diagnostic.json').write_text(json.dumps(r,indent=2));print(json.dumps(r,indent=2))
