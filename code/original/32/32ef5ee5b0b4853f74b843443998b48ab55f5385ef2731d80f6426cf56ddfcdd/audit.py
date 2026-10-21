"""Exact audit of two downloaded publications. No solver or key generation.
The normalized geometry crosswalk is an audit convention, NOT certification
of ambiguous autograph orientations. All comparisons to archived arrays are conditional.
"""
from pathlib import Path
import json,csv,hashlib,collections,fitz
R=Path(__file__).resolve().parents[1]
def save(n,x): (R/n).write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n')
D=json.loads((R/'source/transcribed_publication.json').read_text())
G=json.loads((R/'source/archived_real_inputs.json').read_text())
key=D['key_rows'];raw=''.join(D['S36b_raw_rows']);assert len(raw)==87
cells=[]
for ri,row in enumerate(key,1):
    assert len(row['font_codes'])==len(row['letters'])==8
    for ci,(code,letter) in enumerate(zip(row['font_codes'],row['letters']),1):
        cells.append(dict(id=f'R{ri}C{ci}',font_code=code,letter=letter))
bycode={x['font_code']:x for x in cells};assert len(bycode)==24
inverse={a:[x['id'] for x in cells if x['letter']==a] for a in sorted(set(raw)|set(x['letter'] for x in cells))}
cross=D['normalized_glyph_to_font_code'];assert len(cross)==24 and set(cross)==set(bycode)
def getfontcodes(pdf,page):
    doc=fitz.open(R/'source'/pdf);chars=[]
    for b in doc[page].get_text('dict')['blocks']:
        for l in b.get('lines',[]):
            for sp in l['spans']:
                if sp['font']=='DoraBellaCipher':chars += [c for c in sp['text'] if not c.isspace()]
    return ''.join(chars)
codes=''.join(x['font_codes'] for x in key)
assert getfontcodes('S36a.pdf',0)==getfontcodes('S36b.pdf',3)==codes
assert hashlib.sha256((R/'source/S36a_DoraBellaCipher.ttf').read_bytes()).hexdigest()==hashlib.sha256((R/'source/S36b_DoraBellaCipher.ttf').read_bytes()).hexdigest()
assert all(x in fitz.open(R/'source/S36b.pdf')[2].get_text() for x in D['S36b_raw_rows'])
rows=[];mism={v:[] for v in G}
for i,a in enumerate(raw):
    p=i+1;rr=1 if p<=29 else 2 if p<=60 else 3;cc=p if rr==1 else p-29 if rr==2 else p-60
    rec=dict(position=p,source_glyph_locator=f'S36b.pdf page2 facsimile row{rr} column{cc}',
       source_glyph_status='Exact45degree geometry not certified; no new transcription forced',
       published_literal=a,published_inverse_key_cells=';'.join(inverse.get(a,[])),
       inverse_cardinality=len(inverse.get(a,[])),author_exception=';'.join(x['id'] for x in D['exceptions'] if p in x['positions']),
       facsimile_limit='Same low-quality-source limit; larger pixel dimensions alone do not certify new detail')
    for v,g in G.items():
        code=cross[g[i]];cell=bycode[code];rec[v+'_glyph_id']=g[i];rec[v+'_font_code_conditional']=code;rec[v+'_key_cell_conditional']=cell['id'];rec[v+'_decode_conditional']=cell['letter']
        if cell['letter']!=a:mism[v].append(p)
    rows.append(rec)
with (R/'results/positions87.tsv').open('w') as f:
    w=csv.DictWriter(f,fieldnames=list(rows[0]),delimiter='\t');w.writeheader();w.writerows(rows)
save('results/key24.json',cells)
unique=[i+1 for i,a in enumerate(raw) if len(inverse[a])==1]
multi=[i+1 for i,a in enumerate(raw) if len(inverse[a])>1]
empty=[i+1 for i,a in enumerate(raw) if not inverse[a]]
summary=dict(status='deterministic87glyph_reproduction_not_established',
  versions='S36a3pages explicitly revised2014; S36b5pages internally undated, PDFmetadata2014; not separate verified2013edition',
  key_font_codes_equal=True,key_letter_rows_equal='visually collated24/24; no mnemonic derivation used',
  homophones={a:v for a,v in inverse.items() if len(v)>1},
  published_raw_length=len(raw),unique_inverse_positions=unique,multiple_inverse_positions=multi,empty_inverse_positions=empty,
  literal_V_position=65,no_V_rule_in_publications=True,
  conditional_archive_mismatch_positions=mism,
  roundtrip='Strict literal inverse has no87glyph sequence because position65has empty inverse. Even with an unapproved VtoU repair it would remain multivalued. No repair performed.',
  scope='No proof of autograph error; conditional archived-glyph mismatches not grounds for attributing error to author. No nulls explicitly prescribed for the87glyphs; dot is discussed as omitted character(s), not a glyph null.')
save('results/summary.json',summary)
print(json.dumps(summary,ensure_ascii=False,indent=2))
