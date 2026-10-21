"""Exhaustive bounded affine orientation decoder, fixed alphabetic glyph key.
Mode 0: r_t = a*d_t + b*d_(t-1) + k*t + h mod 8.
Mode 1: r_t = a*d_t + b*r_(t-1) + k*t + h mod 8.
Arcs unchanged. a odd -> invertible. Both modes have an initial predecessor.
32768 parameter definitions (including functionally duplicate definitions).
No learned 24-letter permutation; no position-specific corrections/cribs.
"""
import itertools
import numpy as np
from numba import njit
from model_v5 import LETTER
from wordpolish_v3 import char_score,fast_word

def rules():
    return np.array(list(itertools.product(range(2),(1,3,5,7),range(8),range(8),range(8),range(8))),dtype=np.int64)

@njit(cache=True)
def decode(o,c,rule):
    mode,a,b,k,h,previous=rule;out=np.empty(len(o),np.int64)
    for t in range(len(o)):
        r=(a*o[t]+b*previous+k*t+h)%8
        out[t]=3*r+c[t]
        previous=o[t] if mode==0 else r
    return out

@njit(cache=True)
def encode(z,rule):
    mode,a,b,k,h,previous=rule;out=np.empty(len(z),np.int64)
    # Every odd residue in Z/8Z is its own multiplicative inverse.
    for t in range(len(z)):
        r,c=divmod(z[t],3)
        d=(a*(r-b*previous-k*t-h))%8
        out[t]=3*d+c
        previous=d if mode==0 else r
    return out

@njit(cache=True,nogil=True)
def evaluate(o,c,rs,lp,children,vals):
    scores=np.empty(len(rs),np.float64)
    for i in range(len(rs)):
        z=decode(o,c,rs[i]);text=LETTER[z]
        scores[i]=char_score(text,lp)+.5*fast_word(text,children,vals)
    return scores

def rule_dict(r):
    return dict(zip(('mode','a','b','k','h','initial'),map(int,r)))
