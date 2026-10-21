"""Audit a MANUAL transcription of published Sams Ex8. Not a solver.
No language scoring, key inference, or plaintext optimization.
Crosswalk uses first occurrences only to compare two numbering systems;
it is not an authenticated geometry convention or missing Sams key.
"""
from pathlib import Path
import json,csv,hashlib
R=Path(__file__).resolve().parents[1]
D=json.loads((R/'source/transcription.json').read_text())
G=json.loads((R/'source/archived_real_inputs.json').read_text())
expanded=[]
for ri,row in enumerate(D['message_number_rows']):
    for ci,token in enumerate(row):
        for number in D['compound_expansions'].get(str(token),[token]):
            expanded.append(dict(message_row=ri+1,cell=ci+1,key_no=number,compound_no=token if token in (25,26) else ''))
assert len(expanded)==87
physical=[(60+i)%87+1 for i in range(87)]
assert physical==list(range(61,88))+list(range(1,61))
bypos={p:dict(x,reading_position=i+1,original_position=p) for i,(p,x) in enumerate(zip(physical,expanded))}
assert bypos[8]['key_no']=='20_or_21'
assert bypos[60]['key_no']==6
rows=[]
for p in range(1,88):
    x=bypos[p];n=x['key_no'];options=D['published_key_options'].get(str(n),['unresolved_printed_number_20_or_21'])
    rows.append(dict(**x,original_row=1 if p<=29 else 2 if p<=60 else 3,
       original_column=p if p<=29 else p-29 if p<=60 else p-60,
       key_options=json.dumps(options,ensure_ascii=False),hauer_glyph=G['hauer_real'][p-1],hartmeier_glyph=G['hart_real'][p-1],
       notes='explicit Sams correction to17; printed cell unresolved' if p==8 else 'presumed null, normally key6=T' if p==60 else 'compound key segment' if x['compound_no'] else ''))
with (R/'results/positions87.tsv').open('w') as f:
    w=csv.DictWriter(f,fieldnames=list(rows[0]),delimiter='\t');w.writeheader();w.writerows(rows)
out={'scope':'Number-pattern and annotated-key audit, not deterministic phonetic reproduction or authenticated autograph comparison',
     'positions':87,'expanded_row_lengths':[sum(len(D['compound_expansions'].get(str(x),[x])) for x in row) for row in D['message_number_rows']],
     'null_original_position':60,'printed_ambiguous_position':8,'versions':{}}
for version,g in G.items():
    variants={}
    for choice in (20,21,17):
        seq=[choice if bypos[p]['key_no']=='20_or_21' else bypos[p]['key_no'] for p in range(1,88)]
        # Freeze crosswalk from first physical occurrence, never choose majority/optimize.
        cross={};anchor={}
        for p,n in enumerate(seq,1):
            if n not in cross:cross[n]=g[p-1];anchor[n]=p
        mism=[{'position':p,'Sams_number':n,'anchor_position':anchor[n],'anchor_glyph':cross[n],'observed_glyph':g[p-1]} for p,n in enumerate(seq,1) if cross[n]!=g[p-1]]
        # Invariant equivalence test does not depend on any geometric crosswalk.
        conflicts=[{'i':i+1,'j':j+1,'same_sams_number':seq[i]==seq[j],'same_archived_glyph':g[i]==g[j]} for i in range(87) for j in range(i+1,87) if (seq[i]==seq[j])!=(g[i]==g[j])]
        variants[str(choice)]={'description':'Sams note6 corrected17' if choice==17 else 'unresolved printed digit possibility',
             'anchor_crosswalk':cross,'anchor_positions':anchor,'nonmatching_positions':mism,'exact_roundtrip':not mism and not conflicts,
             'pair_pattern_conflicts':conflicts}
    out['versions'][version]=variants
out['source_hashes']={str(p.relative_to(R)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted((R/'source').glob('*')) if p.is_file()}
(R/'results/audit.json').write_text(json.dumps(out,indent=2)+'\n')
for version,variants in out['versions'].items():
    for ch,v in variants.items():print(version,ch,'mismatch positions',[x['position'] for x in v['nonmatching_positions']],'pair conflicts',len(v['pair_pattern_conflicts']))
print('87 positions checked; no exact reverse reproduction asserted.')
