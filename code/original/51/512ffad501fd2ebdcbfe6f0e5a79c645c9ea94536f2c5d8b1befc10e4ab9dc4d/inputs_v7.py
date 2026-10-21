"""New text excerpts copied from the visible public-domain primary source.
No training on these strings. First 87 ASCII letters, no spelling corrections.
Contamination of the external word-frequency list cannot be excluded.
"""
from pathlib import Path
import hashlib,json,re
import numpy as np
from automata import canonical
ROOT=Path(__file__).resolve().parent
SOURCE='https://www.gutenberg.org/files/25852/25852-h/25852-h.htm'
# Source line coordinates refer to the web tool's retrieved text representation,
# not HTML lines. These are consecutive displayed letter openings, no selection
# based on decoding results.
EXCERPTS=[
(187,'Harley',"I have considered the terms on which I could afford just now to sell Mr. Braham the acting copyright in London of an entirely new piece for the St. James's Theatre; and I could not sit down to write one in a single act of about one hour long, under a hundred pounds."),
(198,'Macready',"There is a semi-business, semi-pleasure little dinner which I intend to give at The Prince of Wales, in Leicester Place, Leicester Square, on Saturday, at five for half-past precisely, at which only Talfourd, Forster, Ainsworth, Jerdan, and the publishers will be present."),
(219,'wife',"I am afraid you will receive this later than I could wish, as the mail does not come through this place until two o'clock to-morrow morning. However, I have availed myself of the very first opportunity of writing, so the fault is that mail's, and not this."),
(244,'Mitton',"I sat down this morning and put on paper my testamentary meaning. Whether it is sufficiently legal or not is another question, but I hope it is. The rough draft of the clauses which I enclose will be preceded by as much of the fair copy as I send you, and followed by the usual clause about the receipts of the trustees being a sufficient discharge."),
(256,'Talfourd',"I cannot tell you how much pleasure I have derived from the receipt of your letter. I have heard little of you, and seen less, for so long a time, that your handwriting came like the renewal of some old friendship, and gladdened my eyes like the face of some old friend."),
(276,'wife',"I received your welcome letter on arriving here last night, and am rejoiced to hear that the dear children are so much better. I hope that in your next, or your next but one, I shall learn that they are quite well. A thousand kisses to them. I wish I could convey them myself."),
(296,'Hughes',"I have given Squeers one cut on the neck and two on the head, at which he appeared much surprised and began to cry, which, being a cowardly thing, is just what I should have expected from him—wouldn't you?"),
(313,'Macready',"I have not seen you for the past week, because I hoped when we next met to bring The Lamplighter in my hand. It would have been finished by this time, but I found myself compelled to set to work first at the Nickleby on which I am at present engaged, and which I regret to say—after my close and arduous application last month—I find I cannot write as quickly as usual."),
(327,'Macready',"I can have but one opinion on the subject—withdraw the farce at once, by all means. I perfectly concur in all you say, and thank you most heartily and cordially for your kind and manly conduct, which is only what I should have expected from you; though, under such circumstances, I sincerely believe there are few but you—if any—who would have adopted it."),
(355,'Macready',"I will have, if you please, three dozen of the extraordinary champagne; and I am much obliged to you for recollecting me. I ought not to be sorry to hear of your abdication, but I am, notwithstanding, most heartily and sincerely sorry, for my own sake and the sake of thousands, who may now go and whistle for a theatre—at least, such a theatre as you gave them."),
(369,'Mitton',"Perhaps you have heard from Kate that I succeeded yesterday in the very first walk, and took a cottage at a place called Alphington, one mile from Exeter, which contains, on the ground-floor, a good parlour and kitchen, and above, a full-sized country drawing-room and three bedrooms;"),
(391,'Cattermole',"Why is Peveril lingering on my dusty shelves in town, while my fair cousin and your fair bride remains in blissful ignorance of his merits? There he is, I grieve to say, but there he shall not be long, for I shall be visiting my other home on Saturday morning, and will bring him bodily down and forward him the moment he arrives.")]

def make():
    dest=ROOT/'results/v7/noisy/inputs.json'
    if dest.exists():raise FileExistsError('Do not silently replace frozen test inputs')
    rng=np.random.default_rng(20260926712);cases=[];texts=[]
    from gensim.test.utils import datapath
    training=re.sub('[^a-z]','',Path(datapath('lee_background.cor')).read_text(encoding='latin1').lower())
    for i,(line,to,raw) in enumerate(EXCERPTS):
        text=re.sub('[^a-z]','',raw.lower())[:87]
        assert len(text)==87 and len(set(text))<=24 and text not in training
        seq=canonical(np.array([ord(c)-97 for c in text]));clean=rng.permutation(24)[seq]
        loc=rng.choice(87,4,replace=False);delta=rng.choice([-1,1],4)
        texts.append(dict(id=f'dickens_{i:02d}',url=SOURCE,source_line=line,recipient=to,excerpt=raw,plaintext=text,sha256=hashlib.sha256(text.encode()).hexdigest()))
        for n in (0,2,4):
            obs=clean.copy()
            for j in range(n):
                p=loc[j];obs[p]=3*((obs[p]//3+delta[j])%8)+obs[p]%3
            cases.append(dict(id=f'dickens_{i:02d}_e{n}',kind='positive',text_id=f'dickens_{i:02d}',n_errors=n,plaintext=text,true_glyph=clean.tolist(),glyph=obs.tolist(),corrupted_positions_1based=(loc[:n]+1).tolist()))
    reals=[dict(c) for c in json.loads((ROOT/'results/v6/routes/inputs.json').read_text())['cases'] if c['kind']=='real']
    cases.extend(reals)
    for j in range(19):
        perm=rng.permutation(87)
        for c in reals:
            cases.append(dict(id=c['id']+f'_null_{j:02d}',kind='null',source=c['id'],replicate=j,glyph=np.array(c['glyph'])[perm].tolist()))
    payload=dict(source=SOURCE,seed=20260926712,letters=texts,statement='12 new-for-development openings, each with matched 0/2/4 errors; 36 records are NOT 36 independent texts. Same substitution within a triplet. No author-disjoint dictionary claim.',negative_pairs=19,cases=cases)
    dest.parent.mkdir(parents=True,exist_ok=True);dest.write_text(json.dumps(payload,indent=2));print('inputs',len(cases))
if __name__=='__main__':make()
