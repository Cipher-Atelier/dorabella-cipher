"""Precisely bounded family of 672 invertible, two-state transformations.
Output glyph keeps axis and arc count. Only polarity is XORed with state.
F has two states and one input: current cipher polarity, arc count, or axis.
"""
import numpy as np
from itertools import product

def canonical(seq):
    mapping={};out=[]
    for v in seq:
        if int(v) not in mapping:mapping[int(v)]=len(mapping)
        out.append(mapping[int(v)])
    return np.array(out,dtype=np.int64)

def definitions():
    for kind,R in [('polarity',2),('arcs',3),('axis',4)]:
        for bits in product(range(2),repeat=2*R):
            for init in (0,1):
                yield {'input':kind,'R':R,'table':list(bits),'initial_state':init}

def transform(o,c,rule):
    state=rule['initial_state'];out=[];R=rule['R'];table=rule['table']
    for oi,ci in zip(o,c):
        oi,ci=int(oi),int(ci);axis=oi%4;p=oi//4
        q=p^state;out.append(3*(axis+4*q)+ci)
        x={'polarity':p,'arcs':ci,'axis':axis}[rule['input']]
        state=table[state*R+x]
    return np.array(out,dtype=np.int64)

def inverse(z,rule):
    state=rule['initial_state'];o=[];c=[];R=rule['R'];table=rule['table']
    for zi in z:
        ori,ci=divmod(int(zi),3);axis=ori%4;q=ori//4;p=q^state
        o.append(axis+4*p);c.append(ci)
        x={'polarity':p,'arcs':ci,'axis':axis}[rule['input']]
        state=table[state*R+x]
    return np.array(o,dtype=np.int64),np.array(c,dtype=np.int64)

def variants(o,c):
    out={}
    for rule in definitions():
        seq=canonical(transform(o,c,rule));tag=seq.tobytes()
        if tag not in out:out[tag]=(seq,rule)
    return list(out.values())

if __name__=='__main__':
    from audit import load_cipher
    _,_,o,c=load_cipher();rules=list(definitions())
    for rule in rules:
        z=transform(o,c,rule);oo,cc=inverse(z,rule)
        assert np.array_equal(o,oo) and np.array_equal(c,cc)
        assert np.array_equal((z//3)%4,o%4)
    print('Definitions:',len(rules),'distinct equality patterns:',len(variants(o,c)))
    print('Round-trip checks: all passed')
