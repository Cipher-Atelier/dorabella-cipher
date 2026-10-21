"""Finite, explicit walk models: exact state counts and algebraic closure tests.
These are deterministic conditional deductions, not preregistered hypothesis tests.
The two arc/geometry conventions and results were inspected during development.
No search for plaintext, no adopted key and no claim to cover all geometric ciphers.
"""
from pathlib import Path
import sys, json, itertools, hashlib
import numpy as np
import sympy as sp
HERE=Path(__file__).resolve().parent; ROOT=HERE.parent
sys.path.insert(0,str(ROOT/'round8'))
from exact_study import COEFF
ROWS=((0,29),(29,60),(60,87))
KING=np.array([[1,0],[1,1],[0,1],[-1,1],[-1,0],[-1,-1],[0,-1],[1,-1]],np.int64)

def main():
    out={'status':'exploratory exact diagnostic, no statistical p-values or prospective selection claim',
      'finite_table_assumptions':['glyph encodes an absolute compass-direction step',
      'distance is the number of arcs 1,2,3', 'every glyph emits the letter at its endpoint',
      'one fixed table, each letter has exactly one location, at most 26 letters',
      'no wrapping, no folding, no ignored steps, no glyph corrections',
      'two tested reset modes: continuous, or same origin at each printed row'],
      'closure_assumptions':['fixed directions, independent of position',
      'one shared real length w1,w2,w3 per arc count',
      'both first printed rows return exactly to their own initial point'],
      'caveats':['state counts do not reject tables with several cells for one letter',
      'state counts for unit compass directions use an exact irrational basis',
      'Cartesian diagonal step has length sqrt(2), unlike the unit compass model',
      'arbitrary initial translation and rigid rotation/reflection do not change state counts',
      'arbitrary separate row translations and alternative traversal orders are not tested',
      'nonzero closure minor rejects only exact simultaneous closure, not approximate closure'],
      'cases':{}}
    cases=[c for c in json.loads((ROOT/'results/v7/conditional/inputs.json').read_text())['cases'] if c['kind']=='real']
    for c in cases:
        s=np.array(c['glyph'],np.int64); o=s//3; a=s%3+1
        res={}
        for name,V in [('unit_compass',COEFF),('cartesian_eight_directions',KING)]:
            v=V[o]*a[:,None]; cont=np.cumsum(v,axis=0)
            pieces=[np.cumsum(v[st:en],axis=0) for st,en in ROWS]
            reset=np.vstack(pieces)
            def count(p):return len(set(map(tuple,p.tolist())))
            state_counts={'continuous':count(cont),'same_origin_row_resets':count(reset),
                 'separate_rows':[count(p) for p in pieces]}
            blocks=[]
            for st,en in ROWS[:2]:
                M=sp.Matrix(np.stack([V[o[st:en][a[st:en]==j]].sum(axis=0) for j in range(1,4)],axis=1).tolist())
                if name=='unit_compass':
                    # w_j may be arbitrary REAL values: convert into physical x/y
                    # before rank calculation. Treating the four irrational-basis
                    # coefficient rows as independent equations would be invalid
                    # for arbitrary real weights (although valid for rational ones).
                    M=sp.Matrix.vstack(M[0,:]+M[2,:]/sp.sqrt(2),M[1,:]+M[3,:]/sp.sqrt(2))
                blocks.append(M)
            M=sp.Matrix.vstack(*blocks)
            minors=[]
            for idx in itertools.combinations(range(4),3):
                d=sp.simplify(M[list(idx),:].det())
                minors.append({'row_indices_zero_based':list(idx),'determinant':str(d),'nonzero':bool(d!=0)})
            assert any(m['nonzero'] for m in minors) and M.rank()==3
            assert not M.nullspace()
            # Independent direct sums at four fixed real weight triples.
            for weights in [(1,2,3),(2,3,5),(1,sp.sqrt(2),sp.pi),(sp.Rational(1,3),2,sp.sqrt(3))]:
                expected=M*sp.Matrix(weights); direct=[]
                for st,en in ROWS[:2]:
                    x=sp.S(0);y=sp.S(0)
                    for pos in range(st,en):
                        if name=='unit_compass':
                            vx=sp.cos(sp.pi*int(o[pos])/4);vy=sp.sin(sp.pi*int(o[pos])/4)
                        else:vx,vy=map(int,V[o[pos]])
                        x+=weights[int(a[pos])-1]*vx;y+=weights[int(a[pos])-1]*vy
                    direct.extend([x,y])
                assert all(sp.simplify(x-y)==0 for x,y in zip(direct,expected))
            res[name]={'state_counts':state_counts,
                'continuous_endpoint_states':cont.tolist(),'row_reset_endpoint_states':reset.tolist(),
                'first_two_rows_closure_matrix':[[str(M[i,j]) for j in range(3)] for i in range(4)],
                'closure_matrix_rank':int(M.rank()),'three_by_three_minors':minors,
                'only_solution_for_shared_weights':'w1=w2=w3=0',
                'independent_direct_symbolic_sum_checks':4}
        out['cases'][c['id']]=res
    dest=HERE/'results/literal_walk.json';dest.write_text(json.dumps(out,indent=2)+'\n')
    print(json.dumps({name:{k:{'counts':v['state_counts'],'rank':v['closure_matrix_rank'],'minor':v['three_by_three_minors'][0]} for k,v in c.items()} for name,c in out['cases'].items()},indent=2))
if __name__=='__main__':main()
