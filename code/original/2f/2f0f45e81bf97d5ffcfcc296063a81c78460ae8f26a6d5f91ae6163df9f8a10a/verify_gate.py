"""Separate implementation: compare complete endpoint adjacency matrices to stored masks.
Does not import gate.py or run a cipher solver.
"""
from pathlib import Path
import json,hashlib,itertools,csv
import numpy as np
R=Path(__file__).resolve().parent
P=json.loads((R/'protocol.json').read_text())
F=json.loads((R/'freeze.json').read_text())
for name,sha in F['hashes'].items():assert hashlib.sha256((R/name).read_bytes()).hexdigest()==sha
truth=json.loads((R/'known_plaintexts.json').read_text())
settings=json.loads((R/'settings.json').read_text())
reported=json.loads((R/'results.json').read_text())
stored=np.load(R/'all_position_failures.npz')['blocked']
alphabet=''.join(ch for ch in 'abcdefghijklmnopqrstuvwxyz' if ch not in 'jv')
assert len(alphabet)==24
tables={};direction_checks=0
for H,W in P['board_shapes_height_width']:
    for layout in P['board_layouts']:
        cells=[(x,y) for y in range(H) for x in range(W)] if layout=='row_major' else [(x,y) for x in range(W) for y in range(H)]
        matrix=np.zeros((24,24),bool)
        for i,(x,y) in enumerate(cells):
            for j,(u,v) in enumerate(cells):
                # Direct endpoint test, not displacement set used by gate.py.
                answers=set()
                for step in (1,2,3):
                    for dx,dy in itertools.product((-1,0,1),repeat=2):
                        if (dx,dy)!=(0,0) and (x+step*dx)%W==u and (y+step*dy)%H==v:
                            answers.add((step,dx,dy))
                matrix[i,j]=bool(answers)
        tables[(H,W,layout)]=matrix
        # Explicitly check each of the16 orientation relabellings is a permutation.
        for s,h in itertools.product((-1,1),range(8)):
            assert sorted((s*o+h)%8 for o in range(8))==list(range(8))
            direction_checks+=1
check_count=0; recovered=[]
for i,z in enumerate(truth):
    counts=[]
    for j,((H,W),layout,reading,reset,start) in enumerate(settings):
        chars=z['plaintext'][::1 if reading=='forward' else -1]
        cuts=(0,29,60) if reading=='forward' else (0,27,58)
        matrix=tables[(H,W,layout)];prev=start;errors=[]
        for t,ch in enumerate(chars):
            if reset!='continuous' and t in cuts:prev=start
            nxt=alphabet.index(ch); errors.append(not matrix[prev,nxt]);prev=nxt
        assert np.array_equal(errors,stored[i,j])
        check_count+=87;counts.append(sum(errors))
    best=min(counts);item=reported['texts'][i]
    assert item['id']==z['id'] and best==item['min_blocked']
    assert (best==0)==item['encodable']
    recovered.append(best==0)
assert sum(recovered)==reported['representable']
assert reported['gate_passed']==(sum(recovered)>=12)
# Verify every displayed inverse set independently against adjacency endpoints.
num=0
with (R/'best_patterns_all87.csv').open() as f:
    for z in csv.DictReader(f):
        H,W=settings[int(z['setting_index'])][0]
        x,y,u,v=map(int,[z['previous_x'],z['previous_y'],z['next_x'],z['next_y']])
        vec=((1,0),(1,1),(0,1),(-1,1),(-1,0),(-1,-1),(0,-1),(1,-1))
        allowed=[]
        for g in range(24):
            d=g//3;step=g%3+1;dx,dy=vec[d]
            if (x+step*dx)%W==u and (y+step*dy)%H==v:allowed.append(g)
        assert allowed==json.loads(z['allowed_glyph_ids_s1_h0']);num+=1
out=dict(status='PASS',freeze_hashes_unchanged=True,independently_checked_positions=check_count,
         direction_permutations_checked=direction_checks,inverse_set_rows_checked=num,
         representable=sum(recovered),real_cipher_search_performed=False,
         limitations='Code verification and known-text representability only; not cryptanalytic sensitivity or statistical calibration.')
(R/'verification.json').write_text(json.dumps(out,indent=2)+'\n')
print(json.dumps(out))
