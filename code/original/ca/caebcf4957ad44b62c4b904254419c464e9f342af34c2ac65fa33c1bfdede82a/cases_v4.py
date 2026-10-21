"""Twelve consecutive letter openings (II-XIII), not a random sample.
Manually transcribed from Project Gutenberg HTML after protocol freeze.
Salutations removed; first 87 ASCII letters retained. No source spellings changed.
"""
import json,re,hashlib
import numpy as np
from wordscore_v3 import ROOT
from automata import definitions,canonical,inverse,transform
from historical_check import cases as historical_cases
SOURCE='https://www.gutenberg.org/files/42078/42078-h/42078-h.htm'
EXTRACTS=[
('II',123,'Here I am once more in this scene of dissipation and vice, and I begin already to find my morals corrupted. We reached Staines yesterday,'),
('III',139,'I shall be extremely anxious to hear the event of your ball, and shall hope to receive so long and minute an account of every particular that I shall be tired of reading it.'),
('IV',153,'We have been very gay since I wrote last; dining at Nackington, returning by moonlight, and everything quite in style, not to mention Mr. Claringbould\'s funeral'),
('V',174,'This morning has been spent in doubt and deliberation, in forming plans and removing difficulties, for it ushered in the day with an event which I had not intended'),
('VI',198,'You have already heard from Daniel, I conclude, in what excellent time we reached and quitted Sittingbourne, and how very well my mother bore her journey thither.'),
('VII',216,'Your letter was a most agreeable surprise to me to-day, and I have taken a long sheet of paper to show my gratitude.'),
('VIII',252,'I am so good as to write to you again thus speedily, to let you know that I have just heard from Frank. He was at Cadiz, alive and well, on October 19,'),
('IX',282,'Your letter came quite as soon as I expected, and so your letters will always do, because I have made it a rule not to expect them till they come,'),
('X',302,'I have got some pleasant news for you which I am eager to communicate, and therefore begin my letter sooner, though I shall not send it sooner than usual.'),
('XI',339,'Frank is made. He was yesterday raised to the rank of Commander, and appointed to the "Petterel" sloop, now at Gibraltar. A letter from Daysh has just announced this,'),
('XII',355,'You must read your letters over five times in future before you send them, and then, perhaps, you may find them as entertaining as I do. I laughed at several parts'),
('XIII',402,'I will endeavor to make this letter more worthy your acceptance than my last, which was so shabby a one that I think Mr. Marshall could never charge you with the postage.')]

def make_new_heldout():
    rng=np.random.default_rng(2026092603);rules=list(definitions());out=[]
    for i,(letter,line,raw) in enumerate(EXTRACTS):
        plain=re.sub('[^a-z]','',raw.lower())[:87];assert len(plain)==87,(letter,len(plain))
        truth=np.frombuffer(plain.encode(),np.uint8).astype(np.int64)-97;seq=canonical(truth)
        assert seq.max()<24
        z=rng.permutation(24)[seq]
        for _ in range(1000):
            rule=rules[int(rng.integers(len(rules)))];o,c=inverse(z,rule)
            if not np.array_equal(canonical(3*o+c),seq):break
        else:raise RuntimeError('Could not draw a nontrivial rule')
        assert np.array_equal(transform(o,c,rule),z)
        out.append(dict(id=f'austen_{i:02d}',group='heldout',source=SOURCE,letter=letter,web_line_start=line,
                        source_excerpt=raw,plaintext=plain,plaintext_sha256=hashlib.sha256(plain.encode()).hexdigest(),
                        orientation=o.tolist(),arcs_zero_based=c.tolist(),generating_rule=rule))
    return out

def make_regression():
    rows=[]
    for label,o,c,a,info in historical_cases():
        rows.append(dict(id=label,group='regression',orientation=o.tolist(),arcs_zero_based=c.tolist(),
                         plaintext=''.join(chr(int(t)+97) for t in a),generating_rule=info['generating_rule'],
                         cached_v3=f'results/v3/dev_{label}.json'))
    old=json.loads((ROOT/'results/v3/heldout/inputs.json').read_text())['cases']
    for x in old:
        rows.append(dict(x,group='regression',cached_v3=f"results/v3/heldout/{x['id']}.json"))
    return rows

def make_real_and_null():
    from audit import load_cipher
    _,_,o,c=load_cipher();rng=np.random.default_rng(2026092604)
    rows=[dict(id='dorabella',group='real',orientation=o.tolist(),arcs_zero_based=c.tolist(),
               cached_v3='results/v3/cached/dorabella.json')]
    for i in range(39):
        idx=rng.permutation(87)
        rows.append(dict(id=f'null4_{i:02d}',group='null',orientation=o[idx].tolist(),arcs_zero_based=c[idx].tolist(),permutation=idx.tolist()))
    return rows

if __name__=='__main__':
    rows=make_regression()+make_new_heldout()+make_real_and_null()
    out=ROOT/'results/v4';out.mkdir(exist_ok=True)
    manifest={'source':SOURCE,'n_new_heldout':12,'n_new_null':39,'selection':'consecutive Austen letters II-XIII; remove salutation, truncate to87ASCII; convenient sample, not random','cases':rows}
    p=out/'inputs.json'
    if p.exists():assert json.loads(p.read_text())==manifest
    else:p.write_text(json.dumps(manifest,indent=2))
    print('Cases saved',len(rows),flush=True)
