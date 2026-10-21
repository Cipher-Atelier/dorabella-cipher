"""Frozen-compatible extension: same v2 finalist selection and v3 seeds,
then direct word-aware search for every finalist. No truth enters selection.
This does NOT rerun early finalist selection with the new objective.
"""
import json,time
import numpy as np
from wordsearch_v4 import WordSearch,CONFIG,ROOT
from scan_v3 import Pipeline as PipelineV3
from automata import variants

class Pipeline:
    def __init__(self): self.engine=WordSearch()
    def run(self,o,c,v3bank,config=None,tag='v4'):
        t=time.monotonic();all_variants=variants(o,c);rows=[]
        # Stable index order means the output does not depend on v3 sort order.
        for entry in sorted(v3bank['candidates'],key=lambda e:e['index']):
            seq,rule=all_variants[entry['index']]
            r=self.engine.run(seq,entry['decoded'],config,tag=tag)
            r.update(index=entry['index'],rule=rule,seed_combined_score=entry['combined_score'])
            assert r['score']>=entry['combined_score']-1e-9
            rows.append(r)
        rows.sort(key=lambda r:(-r['score'],r['decoded']))
        best=rows[0];ii=v3bank['identity_index'];identity=next(r for r in rows if r['index']==ii)
        return dict(id=v3bank.get('id'),best_score=best['score'],identity_score=identity['score'],
                    improvement=best['score']-identity['score'],best_index=best['index'],identity_index=ii,
                    decoded=best['decoded'],candidates=rows,seconds=time.monotonic()-t,
                    finalist_count=len(rows),distinct_full_family=len(all_variants))
