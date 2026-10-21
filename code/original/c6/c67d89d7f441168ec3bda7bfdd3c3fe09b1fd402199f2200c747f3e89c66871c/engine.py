"""Exact cyclic-triplet family, arbitrary independent arc permutations."""
from pathlib import Path
import os,sys,itertools
import numpy as np
H=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(H.parents[0]/'dorabella_round13/deps'))
os.environ.setdefault('NUMBA_CACHE_DIR',str(H/'cache'))
from numba import njit
ALPHABET='abcdefghiklmnopqrstuwxyz'
LETTER=np.array([ord(c)-97 for c in ALPHABET],dtype=np.int64)
Q=np.array(list(itertools.permutations(range(3))),dtype=np.int64)
P=np.array([[(s*o+h)%8 for o in range(8)] for s in (1,-1) for h in range(8)],dtype=np.int64)
NQ=6**8;NK=16*NQ

def key_at(i):
 p,z=divmod(int(i),NQ); key=np.empty(24,np.int64)
 for o in range(8):
  z,q=divmod(z,6)
  for c in range(3):key[3*o+c]=LETTER[3*P[p,o]+Q[q,c]]
 return key

@njit(cache=True)
def word_score(text,children,vals):
 n=len(text);dp=np.full(n+1,-1e100);dp[0]=0.
 for start in range(n):
  v=dp[start]-8.
  if v>dp[start+1]:dp[start+1]=v
  node=0
  for end in range(start,min(n,start+24)):
   node=children[node,text[end]]
   if node<0:break
   v=vals[node,0]
   if start==0 and end+1<n:v=max(v,vals[node,2])
   if end+1==n and start>0:v=max(v,vals[node,1])
   value=dp[start]+v
   if value>dp[end+1]:dp[end+1]=value
 return dp[n]/n

@njit(cache=True)
def char_score(t,lp):
 s=0.
 for j in range(len(t)-3):s+=lp[((t[j]*26+t[j+1])*26+t[j+2])*26+t[j+3]]
 return s/(len(t)-3)

@njit(cache=True)
def word_bound(g,p,letter,children,vals,Q,z=-1):
 n=len(g); dp=np.full(n+1,-1e100); dp[0]=0.
 # A ternary DFS needs <=49 pending states for depth24; use128.
 nodes=np.empty(128,np.int64); ends=np.empty(128,np.int64)
 fixed=np.full(8,-1,np.int64)
 if z>=0:
  zz=z
  for o in range(8):
   if o>=5:fixed[o]=zz%6
   zz//=6
 for start in range(n):
  dp[start+1]=max(dp[start+1],dp[start]-8.)
  sp=1;nodes[0]=0;ends[0]=start
  while sp:
   sp-=1;node=nodes[sp];end=ends[sp]
   for ci in range(1 if fixed[g[end]//3]>=0 else 3):
    c=Q[fixed[g[end]//3],g[end]%3] if fixed[g[end]//3]>=0 else ci
    child=children[node,letter[3*p[g[end]//3]+c]]
    if child<0:continue
    v=vals[child,0]
    if start==0 and end+1<n:v=max(v,vals[child,2])
    if end+1==n and start>0:v=max(v,vals[child,1])
    dp[end+1]=max(dp[end+1],dp[start]+v)
    if end+1<n and end+1<start+24:
     if sp>=128:raise RuntimeError('DFS full')
     nodes[sp]=child;ends[sp]=end+1;sp+=1
 return dp[n]/n

@njit(cache=True,nogil=True)
def scan(g,pidx,qstart,qstop,lp,children,vals,P,Q,letter,incumbent,unpruned=False):
 p=P[pidx];bound=word_bound(g,p,letter,children,vals,Q)
 table=np.empty((8,6,3),np.int64)
 for o in range(8):
  for q in range(6):
   for c in range(3):table[o,q,c]=letter[3*p[o]+Q[q,c]]
 key=np.empty(24,np.int64);t=np.empty(len(g),np.int64)
 best=incumbent;bestid=-1;ties=[np.int64(0) for _ in range(0)];nw=0;bestC=-1e100;bestW=-1e100
 for z in range(qstart,qstop):
  if z==qstart or z%(6**5)==0:bound=word_bound(g,p,letter,children,vals,Q,z)
  v=z
  for o in range(8):
   q=v%6;v//=6
   for c in range(3):key[3*o+c]=table[o,q,c]
  for j in range(len(g)):t[j]=key[g[j]]
  C=char_score(t,lp)
  if unpruned or C+0.5*bound>=best-1e-9:
   W=word_score(t,children,vals);nw+=1;S=C+0.5*W
   if S>best:
    best=S;bestid=pidx*NQ+z;ties=[bestid];bestC=C;bestW=W
   elif S==best:
    ties.append(pidx*NQ+z)
    if bestid<0:bestid=pidx*NQ+z;bestC=C;bestW=W
 return best,bestid,ties,nw,bestC,bestW,bound
