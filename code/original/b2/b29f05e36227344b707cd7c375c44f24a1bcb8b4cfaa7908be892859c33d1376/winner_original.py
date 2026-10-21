"""Literal original winner 100–109; dormant review copy, NOT a scoring driver.

A future G2 must save the one complete matrix before calling this block.
No evaluate or scorer-construction entry point is provided in this package.
Argpartition candidate subset, exact ties, text deduplication unchanged.
"""
import hashlib
import time
from guard import require_stage


def original_winner(ctx, *, np, scores, glyph, tarray, rarray, base, astr,
                    engine, tt, td, rr, rd, kind, z, start, output_numeric):
    require_stage(ctx.manifest, "G2")
    ctx.guard("G2")
    flat=scores.ravel();ids=np.argpartition(flat,-32)[-32:];ids=sorted(ids,key=lambda j:(-float(flat[j]),int(j)));top=[];seen=set()
    for idx in ids:
        i,j=np.unravel_index(idx,scores.shape);out=output_numeric(glyph,tarray[i],rarray[j],base)
        text=''.join(astr[v] for v in out)
        if text in seen:continue
        seen.add(text);stripped=text.replace(' ','');ws,seg=engine.scorer.score(stripped,True)
        top.append(dict(score=float(scores[i,j]),text=text,table_index=int(i),route_index=int(j),table=tt[i][1],route=rr[j][1],segmentation=seg,scored_length=len(stripped)))
    record=dict(kind=kind,id=z['id'],best_score=top[0]['score'],best_text=top[0]['text'],top=top,
        n_table_definitions=td,n_unique_tables=len(tt),n_route_definitions=rd,n_unique_routes=len(rr),
        n_evaluations=int(scores.size),score_sha256=hashlib.sha256(scores.tobytes()).hexdigest(),seconds=time.monotonic()-start)
    return record
