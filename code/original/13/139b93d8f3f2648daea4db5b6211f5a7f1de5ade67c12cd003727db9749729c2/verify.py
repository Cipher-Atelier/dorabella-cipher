"""Second implementation of key inverse and cardinalities; same chat, no agent."""
from pathlib import Path
import json,csv
R=Path(__file__).resolve().parents[1]
rows=list(csv.DictReader((R/'results/positions87.tsv').open(),delimiter='\t'))
# Independently hand-collated letter rows from both rendered PDF tables.
letters=['L','A','D','P','E','N','N','Y','W','R','I','T','I','G','I','C','O','S','W','Y','K','P','B','U']
expected={a:[f'R{k//8+1}C{k%8+1}' for k,b in enumerate(letters) if b==a] for a in set(letters)}
raw=['PSNOWDROCPBEIGEWEEDSSETINITBU','REIDIOCYONEENDTIREBEDLUIGICCIBU','NUDLVNGLYTUNEDLIUTOSTUDOTWO']
assert [len(s) for s in raw]==[29,31,27] and len(rows)==87
for p,(a,row) in enumerate(zip(''.join(raw),rows),1):
    assert row['position']==str(p) and row['published_literal']==a
    ids=[]
    for r in range(3):
        for c in range(8):
            if letters[8*r+c]==a:ids.append(f'R{r+1}C{c+1}')
    assert row['published_inverse_key_cells']==';'.join(ids)
    assert int(row['inverse_cardinality'])==len(ids)
assert [int(x['position']) for x in rows if int(x['inverse_cardinality'])==0]==[65]
assert expected['I']==['R2C3','R2C5','R2C7'] and expected['P']==['R1C4','R3C6']
result={'status':'passed','scope':'87literalpositions and all24published key cells; inverse sets independently checked. Not independent manual facsimile reading.',
        'position65':'Vhas zero preimage; strict full inverse relation empty',
        'unique':sum(int(x['inverse_cardinality'])==1 for x in rows),
        'multi':sum(int(x['inverse_cardinality'])>1 for x in rows),'empty':1}
(R/'results/separate_verification.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
