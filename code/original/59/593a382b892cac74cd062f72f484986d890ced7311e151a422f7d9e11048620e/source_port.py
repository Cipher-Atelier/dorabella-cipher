"""Selected square table/route and output_numeric: list port of original.

Source bodies at fraction_v6.py30–35,53–63,68–77. No source import,
bank enumeration, cube branch, scorer, JIT or target input. Valid fixtures only.
"""


def table_one(key):
    sign, rot, arcs = key['sign'], key['rot'], key['arcs']
    layout, missing = key['layout'], key['missing']
    oo=[(sign*(i//3)+rot)%8 for i in range(24)];cc=[arcs[i%3] for i in range(24)]
    x=[3*oo[i]+cc[i] if layout==0 else 8*cc[i]+oo[i] for i in range(24)]
    x=[v+(v>=missing) for v in x]
    coords=[[v//5,v%5] for v in x]
    return coords


def route_one(period, reset, inverse, reverse):
    dim=2
    bounds=[0,29,60,87] if reset else [0,87]
    p=list(range(87*dim))
    for lo,hi in zip(bounds[:-1],bounds[1:]):
        for first in range(lo,hi,period):
            m=min(period,hi-first)
            for i in range(m):
                for j in range(dim):p[(first+i)*dim+j]=first*dim+j*m+i
    q=sorted(range(len(p)),key=p.__getitem__) if inverse else p.copy()
    if reverse:q=[(86-v//dim)*dim+v%dim for v in q]
    return q


def output_numeric(glyph,table,route,base):
    dim=len(table[0]);digit=[0]*(87*dim)
    for i in range(87):
        for j in range(dim):digit[i*dim+j]=table[glyph[i]][j]
    out=[0]*87
    for i in range(87):
        v=0
        for j in range(dim):v=v*base+digit[route[i*dim+j]]
        out[i]=v
    return out
