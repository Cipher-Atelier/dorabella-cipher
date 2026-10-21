"""Separate scalar verification. Does not import audit.py or fit any key."""
import csv,json
from pathlib import Path
R=Path(__file__).resolve().parents[1]
d=json.loads((R/'source/transcription.json').read_text());g=json.loads((R/'source/archived_real_inputs.json').read_text())
rows=list(csv.DictReader((R/'results/positions87.tsv').open(),delimiter='\t'))
# Independent explicit expansion in reading order from manually inspected Ex8.
seq=[17,6,14,2,6,17,16,2,3,13,6,17,5,14,2,4,6,13,21,9,13,6,14,21,16,22,21,
20,9,17,21,19,14,1,'20_or_21',10,23,18,5,4,16,5,15,5,5,14,9,9,5,16,22,
23,22,13,18,6,1,5,4,14,1,21,10,11,21,17,5,5,17,14,13,
4,1,5,18,5,14,2,6,4,16,22,10,10,22,18,6]
assert len(seq)==87
for row in rows:
    p=int(row['original_position']);i=int(row['reading_position'])
    assert int(row['hauer_glyph'])==g['hauer_real'][p-1]
    assert int(row['hartmeier_glyph'])==g['hart_real'][p-1]
    assert str(seq[i-1])==row['key_no']
    assert (p if p>60 else p+87)-60==i
assert seq[-1]==6 and int(rows[59]['reading_position'])==87
assert rows[12]['key_no']==rows[31]['key_no']=='4'
for version,gl in g.items():assert gl[12]!=gl[31]
assert g['hauer_real'][6]!=g['hauer_real'][33] # Sams1 repeated
assert g['hart_real'][69]!=g['hart_real'][77] # Sams13 repeated
groups={str(n):[int(row['original_position']) for row in rows if row['key_no']==str(n)] for n in range(1,25)}
out={'status':'passed','checks':'Separate explicit87number expansion, TSV position/order/input equality, compound expansion, null position, repeated-symbol contradictions. This is a second implementation in the same ChatGPT, not an independent researcher. Manual image reading is NOT independently certified.',
     'positions_by_Sams_number':groups,
     'nonunique_key_categories':{n:ps for n,ps in groups.items() if len(d['published_key_options'].get(n,[]))>1},
     'source_digit_at8':'unresolved20/21; note6 corrected17 separately',
     'exact_original_glyph_roundtrip':'not established; contradictions to both archived readings regardless of uncertain digit'}
(R/'results/separate_verification.json').write_text(json.dumps(out,indent=2)+'\n');print(json.dumps(out,ensure_ascii=False))
