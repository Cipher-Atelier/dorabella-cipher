"""Freeze source excerpts and synthetic inputs before any cipher scoring.
Only Elgar's letters are copied, not the modern editors' prose. Printed
transcriptions were checked against web screenshots, not original manuscripts.
"""
from pathlib import Path
import json,re,hashlib,itertools
import numpy as np
HERE=Path(__file__).resolve().parent; ROOT=HERE.parent
A='ABCDEFGHIKLMNOPQRSTUWXYZ'
def norm(s): return re.sub('[^a-z]','',s.lower()).replace('j','i').replace('v','u')
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
S1='https://elgarsociety.org/wp-content/uploads/2022/03/ESJ-Dec-2015-final.pdf'
S2='https://elgarsociety.org/wp-content/uploads/2022/03/JOURNAL_1984.01.pdf'
# (id, date as printed, recipient, PDF page ONE-based, printed page, body opening)
raw=[
('bailey_01','1892-04-19','Mrs Bailey',16,'28',"As to your son : I think he has great talent & is just at that ‘receptive’ age when his musical education requires great care & his taste may now be developed for good or evil."),
('bailey_02','1893-01-23','Reginald Bailey',16,'29',"I was extremely glad to receive your letter tell me how you are getting on. I should have replied at once but Mrs Elgar has been really very ill & it has taken all my attention: she is better now."),
('bailey_03','1893-01-23','Mrs Bailey',17,'30',"I was so delighted to receive your dear boy’s letter & to hear from you how well he is going on: I could not write before as we have had a most trying time during Mrs Elgar’s most serious illness:"),
('bailey_04','1893-07-21','Reginald Bailey',17,'30',"I was so very glad to receive your letter & to hear how well you are getting on with your Violin: it is an excellent list of Music which you sent me & I should much like to hear you play some of them:"),
('bailey_05','1895-04-25','Reginald Bailey',17,'31',"I was do delighted to receive your letter & to hear all about you: we were away from home visiting when it reached me & we were going about a great deal so I did not answer at once:"),
('bailey_06','1896-12-08','Mrs Bailey',18,'32',"I was very glad to receive your letter giving such a good account of your son & to hear how well he is getting on in everything: it is so good to hear of a musical boy having a sound education"),
('bailey_07','1897-10-19','Mrs Bailey',18,'33',"I have been waiting to write until I had something to tell you & as we have been abroad I have had no opportunity of speaking to either Dr Parry or Dr Stanford until the Hereford Festival:"),
('bailey_08','undated; editorial placement June 1899, not independently verified','Mrs Bailey',18,'33',"I was must grieved about the scholarship, chiefly because I knew how much your dear son wd be affected by the disappointment: I hope now he is getting quite strong again."),
('bailey_09','1902-06-08','Mrs Bailey',19,'34',"Many thanks for your letter; I am sorry Reginald is laid up & hope he will soon be better. I should be delighted to give any recommendation to your son anytime but I do not like my name to be in print"),
('brewer_01','1901-06-14','Alfred Herbert Brewer',29,'28',"Good! If I can I’ll conduct Cockaigne for you but you would do it all right if I cannot come. I’ll look out for you in town next week."),
('brewer_02','1901-06-30','Alfred Herbert Brewer',29,'28',"I have scored Nos. 1, 4, 5, 6, 9 and 10. If that’s not enough you must let me know. I send on my MS. I hope it will please you but I feel much at sea as to your wishes and I am sadly afraid you will not like my interpretation"),
('brewer_03','1901-07-07','Alfred Herbert Brewer',30,'29',"I shall hope to despatch by an early post to-morrow the remainder of your score - it’s all ready now but Sunday’s a dies non with us as far as business posts are concerned.")]
ex=[]
for name,date,to,page,printed,body in raw:
    p=norm(body)[:87];assert len(p)==87
    ex.append(dict(id=name,date=date,recipient=to,pdf_page_one_based=page,printed_page=printed,
      source_url=S1 if name.startswith('bailey') else S2,body_opening=body,plaintext=p,
      body_sha256=hashlib.sha256(body.encode()).hexdigest(),normalised_sha256=hashlib.sha256(p.encode()).hexdigest()))
(HERE/'data/elgar_letters.json').write_text(json.dumps(dict(
 selection='All nine letters by Edward Elgar in the Bailey article (exclude Arnold, incoming Bailey, and C.A. Elgar); three letters by Edward Elgar quoted in the Brewer article, in publication order; first 87 normalized body letters after salutation.',
 source_status='Printed scholarly transcriptions checked visually against six PDF screenshots; not original manuscript verification. No raw PDF downloaded (container DNS failed).',
 spelling='Keep printed tell me, I was do delighted, I was must grieved, wd, MS, etc. Do not attribute possible editorial typos to Elgar as established autograph spellings.',
 normalisation='ASCII letters only, j->i, v->u; digits and ampersand removed, not expanded; spelling not modernized; 87 letters.',
 test_status='New to this laboratory and not used to fit models or choose parameters; convenient correlated selections, not a representative random corpus; letters from same correspondences.',
 cases=ex),ensure_ascii=False,indent=2))
rng=np.random.default_rng(202610011001);cases=[]
# Known answers stay in metadata. Search receives glyph sequence only.
for e in ex:
    p8=rng.permutation(8);p3=rng.permutation(3)
    key=np.array([3*p8[o]+p3[c] for o in range(8) for c in range(3)])
    inv=np.argsort(key);g=inv[np.array([A.lower().index(c) for c in e['plaintext']])]
    assert ''.join(A[key[z]].lower() for z in g)==e['plaintext']
    cases.append(dict(id=e['id'],kind='positive',glyph=g.tolist(),plaintext=e['plaintext'],
      true_perm8=p8.tolist(),true_perm3=p3.tolist(),source=e['id']))
# Reuse two old regression texts, with fresh structured keys; explicitly not held-out.
old=json.loads((ROOT/'round8/sources/elgar_excerpts.json').read_text())
(HERE/'data/old_excerpt_structure.json').write_text(json.dumps(old,ensure_ascii=False,indent=2))
for i,e in enumerate(old):
    plaintext=norm(e['excerpt'])[:87];assert len(plaintext)==87
    p8=rng.permutation(8);p3=rng.permutation(3)
    key=np.array([3*p8[o]+p3[c] for o in range(8) for c in range(3)])
    inv=np.argsort(key);g=inv[np.array([A.lower().index(c) for c in plaintext])]
    cases.append(dict(id=e['id'],kind='regression',glyph=g.tolist(),plaintext=plaintext,
      true_perm8=p8.tolist(),true_perm3=p3.tolist(),source=e['id']))
# Dorabella unchanged. Alternatives imported from an existing input file.
oldcases=json.loads((ROOT/'results/v6/routes/inputs.json').read_text())['cases']
for e in oldcases:
    if e['kind']=='real': cases.append(dict(id=e['id'],kind='real',glyph=e['glyph']))
assert len([x for x in cases if x['kind']=='real'])==2
(HERE/'data/inputs_base.json').write_text(json.dumps(cases,indent=2))
print('Prepared',len(ex),'new source excerpts and',len(cases),'base inputs.')
