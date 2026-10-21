"""Exact cardinality of symbol strings with fixed directed bigrams/endpoints.
Matrix-tree determinant times last-exit edge-order counts, divided by permutations
of indistinguishable equal directed edges. Checked against toy enumeration.
"""
import math,json,itertools
from pathlib import Path
from collections import Counter
import sympy as sp
ROOT=Path(__file__).resolve().parent

def count_strings(s):
 vocab=sorted(set(s));lookup={x:i for i,x in enumerate(vocab)};K=len(vocab);adj=[[0]*K for _ in range(K)]
 for u,v in zip(s,s[1:]):adj[lookup[u]][lookup[v]]+=1
 out=[sum(r) for r in adj];root=lookup[s[-1]]
 lap=sp.Matrix(K,K,lambda i,j:(out[i] if i==j else 0)-adj[i][j]);minor=lap.minor_submatrix(root,root)
 trees=int(minor.det()) if K>1 else 1
 top=trees
 for i,d in enumerate(out):top*=math.factorial(d-1+(i==root))
 bottom=math.prod(math.factorial(v) for row in adj for v in row)
 assert top%bottom==0
 return top//bottom,trees

def main():
 toys=[(0,1,0,2,0,1,2,0),(0,0,1,2,1,0,1,2),(0,1,0,1,2,1,2,0),(0,0,0),(0,1,2)]
 for s in toys:
  edges=Counter(zip(s,s[1:]));exact={p for p in itertools.permutations(s) if p[0]==s[0] and p[-1]==s[-1] and Counter(zip(p,p[1:]))==edges}
  assert count_strings(s)[0]==len(exact)
 cases=json.loads((ROOT/'results/v7/conditional/inputs.json').read_text())['cases'];result={}
 for c in cases:
  if c['kind']=='real':
   total,trees=count_strings(c['glyph']);result[c['id']]={'strings_exact':str(total),'log10_strings':math.log10(total),'arborescences_exact':str(trees)}
 result['toy_checks']=len(toys)
 (ROOT/'results/v7/conditional/cardinality.json').write_text(json.dumps(result,indent=2));print(json.dumps(result,indent=2))
if __name__=='__main__':main()
