"""Independent read-only audit; writes only checks/ artifacts."""
from pathlib import Path
import os, sys, json, hashlib, itertools, time
from collections import Counter
ROOT=Path(__file__).resolve().parents[1]
os.environ['NUMBA_CACHE_DIR']=str(ROOT/'checks'/'audit_cache')
sys.dont_write_bytecode=True
sys.path.insert(0,str(ROOT/'code'))
import experiment as ex
import numpy as np
ALPHA='abcdefghiklmnopqrstuwxyz'
PERMS=list(itertools.permutations([0,1,2]))

def params(key):
    table, route=divmod(int(key),696)
    layout, remainder=divmod(table,96)
    pi, qi=divmod(remainder,6)
    rev, remainder=divmod(route,348)
    reset, remainder=divmod(remainder,174)
    anchor, ki=divmod(remainder,87)
    return layout,(1 if pi<8 else -1),pi%8,PERMS[qi],rev,reset,anchor,ki-43

def indices(j,rev,reset,anchor,k):
    lengths=([27,31,29] if rev else [29,31,27]) if reset else [87]
    start=0
    for length in lengths:
        if start<=j<start+length:
            shifted=start+(j-start+k)%length
            break
        start+=length
    raw=lambda z:86-z if rev else z
    return (raw(shifted),raw(j)) if anchor else (raw(j),raw(shifted))

def literal_decode(g,key):
    layout,s,h,q,rev,reset,anchor,k=params(key)
    out=[]
    for j in range(87):
        oi,ci=indices(j,rev,reset,anchor,k)
        o=(s*(int(g[oi])//3)+h)%8
        c=q[int(g[ci])%3]
        letter=ALPHA[3*o+c if layout==0 else 8*c+o]
        out.append(ord(letter)-97)
    return np.array(out,np.int64)

def literal_encrypt(text,key):
    layout,s,h,q,rev,reset,anchor,k=params(key)
    orientations=[None]*87;arcs=[None]*87
    for j,letter in enumerate(text):
        z=ALPHA.index(chr(int(letter)+97))
        o,c=(z//3,z%3) if layout==0 else (z%8,z//8)
        oi,ci=indices(j,rev,reset,anchor,k)
        assert orientations[oi] is None and arcs[ci] is None
        orientations[oi]=(s*(o-h))%8;arcs[ci]=q.index(c)
    return np.array([3*o+c for o,c in zip(orientations,arcs)],np.int64)

def backward_word(text,ch,va):
    n=len(text);best=[float('-inf')]*(n+1);best[n]=0.
    for start in range(n-1,-1,-1):
        best[start]=-8.+best[start+1];node=0
        for end in range(start,min(n,start+24)):
            node=int(ch[node,int(text[end])])
            if node<0:break
            values=[float(va[node,0])]
            if start==0 and end<n-1:values.append(float(va[node,2]))
            if end==n-1 and start>0:values.append(float(va[node,1]))
            best[start]=max(best[start],max(values)+best[end+1])
    return best[0]/n

def literal_score(text,lp,ch,va):
    vals=[]
    for i in range(84):
        ix=0
        for letter in text[i:i+4]:ix=26*ix+int(letter)
        vals.append(float(lp[ix]))
    c=sum(vals)/84;w=backward_word(text,ch,va)
    return c+.5*w,c,w

def main():
    started=time.monotonic()
    before=hashlib.sha256((ROOT/'code/experiment.py').read_bytes()).hexdigest()
    maps,oi,ci,tables,routes=ex.banks();lp,ch,va=ex.model()
    assert maps.shape==(192,8,3) and oi.shape==ci.shape==(696,87)
    assert len(maps)*len(oi)==133632
    rng=np.random.default_rng(202610091119)
    # Entire index bank checked from canonical IDs without using stored route metadata.
    for ri in range(696):
        layout,s,h,q,rev,reset,anchor,k=params(ri)
        for j in range(87):assert indices(j,rev,reset,anchor,k)==(int(oi[ri,j]),int(ci[ri,j]))
    # Entire mapping bank checked directly from mixed-radix arithmetic.
    for mi in range(192):
        layout,s,h,q,*_=params(mi*696)
        for o in range(8):
            for c in range(3):
                z=3*((s*o+h)%8)+q[c] if layout==0 else 8*q[c]+((s*o+h)%8)
                assert maps[mi,o,c]==ord(ALPHA[z])-97
    max_score_error=0.;tests=0
    for key in [0,43,86,347,348,695,133631]+rng.integers(133632,size=125).tolist():
        glyph=rng.integers(24,size=87,dtype=np.int64)
        literal=literal_decode(glyph,key)
        assert np.array_equal(literal,ex.decode(glyph,maps,oi,ci,key))
        assert np.array_equal(literal_encrypt(literal,key),glyph)
        assert np.array_equal(ex.encrypt(literal,maps,oi,ci,key),glyph)
        truth=ex.LETTER[rng.integers(24,size=87)]
        encrypted=literal_encrypt(truth,key)
        assert np.array_equal(encrypted,ex.encrypt(truth,maps,oi,ci,key))
        assert np.array_equal(truth,literal_decode(encrypted,key))
        a=literal_score(literal,lp,ch,va);b=ex.score_py(literal,lp,ch,va)
        max_score_error=max(max_score_error,max(abs(x-y) for x,y in zip(a,b)),abs(a[2]-float(ex.word(literal,ch,va))))
        tests+=1
    assert max_score_error<1e-11
    # Slice all 696 routes, so every branch and eight k=0 definitions are covered.
    # Independent backward-DP scores also check actual maxima and tie handling.
    small=[]
    for sample,mi in enumerate([0,95,96,0]):
        if sample==3:
            text=json.loads((ROOT/'data/positive_truth.json').read_text())[0]['plaintext']
            glyph=literal_encrypt([ord(x)-97 for x in text],0)
        else:
            glyph=rng.integers(24,size=87,dtype=np.int64)
        submaps=maps[mi:mi+1]
        pruned=ex.scan(glyph,submaps,oi,ci,lp,ch,va,False)
        full=ex.scan(glyph,submaps,oi,ci,lp,ch,va,True)
        for i in [0,1,2,4,5]:assert pruned[i]==full[i]
        if sample==3:assert pruned[3]<full[3]
        independently=[literal_score(literal_decode(glyph,mi*696+ri),lp,ch,va)[0] for ri in range(696)]
        best=max(independently);bestids=[i for i,x in enumerate(independently) if abs(x-best)<1e-11]
        baseids=[i for i in range(696) if i%87==43]
        baseline=max(independently[i] for i in baseids)
        assert abs(pruned[0]-best)<1e-11 and pruned[1] in bestids
        assert abs(pruned[4]-baseline)<1e-11
        assert pruned[1]==min(pruned[2])
        for key in pruned[2]:assert key in bestids
        small.append({'table_id':mi,'keys':696,'favorable_text_fixture':sample==3,'word_calls_pruned':int(pruned[3]),'word_calls_full':int(full[3]),'pruned_unpruned_maxima_ties_baseline_equal':True,'independent_score_maximum_equal':True})
    cases=json.loads((ROOT/'data/search_inputs.json').read_text())
    truths={x['id']:x for x in json.loads((ROOT/'data/positive_truth.json').read_text())}
    assert len(cases)==414 and len(truths)==14
    positives=[x for x in cases if x['kind']=='positive']
    reals={x['id']:x for x in cases if x['kind']=='real'}
    assert len(positives)==14 and len(reals)==2
    for case in positives:
        truth=truths[case['id']];decoded=literal_decode(case['glyph'],truth['key_id'])
        assert ''.join(chr(int(x)+97) for x in decoded)==truth['plaintext']
    counts={name:0 for name in reals}
    for case in cases:
        if case['kind']!='null':continue
        original=reals[case['source']]['glyph'];shuffled=case['glyph']
        assert len(shuffled)==87 and original[0]==shuffled[0] and original[-1]==shuffled[-1]
        assert Counter(original)==Counter(shuffled)
        assert Counter(zip(original,original[1:]))==Counter(zip(shuffled,shuffled[1:]))
        counts[case['source']]+=1
    assert all(n==199 for n in counts.values())
    assert hashlib.sha256((ROOT/'code/experiment.py').read_bytes()).hexdigest()==before
    report={'status':'passed','experiment_sha256':before,'all_696_route_indices_independently_checked':True,'all_192_tables_independently_checked':True,'literal_roundtrip_and_score_trials':tests,'max_score_error':max_score_error,'small_pruned_unpruned':small,'positive_truths_independently_reconstructed':14,'nulls_independently_checked':counts,'word_upper_bound_nonpositive':bool(np.max(va)<=0),'gate_review':'run() searches only positives before testing exact>=12 and letters>=1194, then returns on failure. No outcome-based retuning found.','notes':['Small independent maxima use a 1e-11 comparison tolerance; production exact ties independently match unpruned execution.','Uniformity of Euler shuffle supported by directed-Wilson last-exit construction; finite small-support histograms are diagnostics, not a general proof.','No real/null language searches performed by this audit.'],'seconds':time.monotonic()-started}
    (ROOT/'checks/independent_audit.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))

def final_results():
    started=time.monotonic()
    proto=json.loads((ROOT/'protocol.json').read_text())
    assert hashlib.sha256((ROOT/'protocol.json').read_bytes()).hexdigest()==(ROOT/'protocol.sha256').read_text().strip()
    for name,expected in proto['hashes'].items():assert hashlib.sha256((ROOT/name).read_bytes()).hexdigest()==expected
    cases=json.loads((ROOT/'data/search_inputs.json').read_text())
    truth={x['id']:x for x in json.loads((ROOT/'data/positive_truth.json').read_text())}
    summary=json.loads((ROOT/'results/summary.json').read_text())
    assert len(cases)==summary['cases']==414
    lp,ch,va=ex.model();maps,oi,ci,tables,routes=ex.banks()
    records=[];maxerr=0.;tiechecks=0;max_distinct_tied_texts=0
    for case in cases:
        rec=json.loads((ROOT/'results'/f"{case['id']}.json").read_text())
        assert rec['id']==case['id'] and rec['kind']==case['kind']
        assert rec['all_ties']==sorted(set(rec['all_ties']))
        assert rec['key_id']==min(rec['all_ties']) and len(rec['all_ties'])==rec['tie_count']
        assert rec['char_evaluations']==133632 and 1<=rec['word_evaluations']<=133632
        glyph=np.array(case['glyph'],np.int64);decoded=literal_decode(glyph,rec['key_id'])
        assert rec['plaintext']==''.join(chr(int(x)+97) for x in decoded)
        mi,ri=divmod(rec['key_id'],696)
        assert rec['table']==tables[mi] and rec['route']==routes[ri]
        independent=literal_score(decoded,lp,ch,va)
        maxerr=max(maxerr,max(abs(x-rec[name]) for x,name in zip(independent,['S','C','W'])))
        tied_texts=set()
        for key in rec['all_ties']:
            assert 0<=key<133632
            text=literal_decode(glyph,key)
            assert np.array_equal(literal_encrypt(text,key),glyph)
            score=literal_score(text,lp,ch,va)[0];maxerr=max(maxerr,abs(score-rec['S']))
            tied_texts.add(tuple(map(int,text)));tiechecks+=1
        max_distinct_tied_texts=max(max_distinct_tied_texts,len(tied_texts))
        bkey=rec['baseline_key_id'];assert bkey%696%87==43
        btext=literal_decode(glyph,bkey);bs=literal_score(btext,lp,ch,va)[0]
        assert np.array_equal(literal_encrypt(btext,bkey),glyph)
        maxerr=max(maxerr,abs(bs-rec['baseline_S']))
        assert abs(rec['gain']-(rec['S']-rec['baseline_S']))<1e-12 and rec['gain']>=-1e-12
        if case['kind']=='positive':
            correct=sum(a==b for a,b in zip(rec['plaintext'],truth[case['id']]['plaintext']))
            assert rec['correct_letters']==correct
            assert rec['true_key_among_ties']==(truth[case['id']]['key_id'] in rec['all_ties'])
        records.append(rec)
    assert maxerr<1e-11
    pos=[r for r in records if r['kind']=='positive']
    gate={'exact':sum(r['correct_letters']==87 for r in pos),'correct_letters':sum(r['correct_letters'] for r in pos)}
    gate['passed']=gate['exact']>=12 and gate['correct_letters']>=1194
    assert gate==summary['sensitivity']==json.loads((ROOT/'checks/sensitivity.json').read_text()) and gate['passed']
    tails={}
    for real in [r for r in records if r['kind']=='real']:
        null=[r for r in records if r['kind']=='null' and r['source']==real['id']]
        assert len(null)==199
        ks=sum(r['S']>=real['S']-1e-11 for r in null)
        kg=sum(r['gain']>=real['gain']-1e-11 for r in null)
        v=summary['versions'][real['id']]
        assert v['null_ge_S']==ks and v['null_ge_gain']==kg
        assert v['plus_one_tail_S']==(ks+1)/200 and v['plus_one_tail_gain']==(kg+1)/200
        assert v['null_score_min']==min(r['S'] for r in null) and v['null_score_max']==max(r['S'] for r in null)
        tails[real['id']]={'null_ge_S':ks,'plus_one_tail_S':(ks+1)/200,'null_ge_gain':kg,'plus_one_tail_gain':(kg+1)/200}
    unpruned=json.loads((ROOT/'checks/full_unpruned.json').read_text())
    assert len(unpruned)==3 and all(x['all_maxima_and_baseline_equal'] and x['unpruned_word_evaluations']==133632 for x in unpruned)
    out={'status':'passed','cases':414,'reported_maximum_ties_independently_scored_and_inverted':tiechecks,'all_baseline_keys_independently_scored_and_inverted':414,'max_independent_score_error':maxerr,'max_distinct_plaintexts_among_any_cases_exact_ties':max_distinct_tied_texts,'positive_gate':gate,'tails':tails,'full_unpruned_rerun_records_verified':3,'frozen_file_hashes_unchanged':True,'limits':'All reported ties verified. This audit does not independently enumerate every key of every full input; completeness relies on reviewed exhaustive scan and safe pruning, plus the three recorded full unpruned repeats.','seconds':time.monotonic()-started}
    (ROOT/'checks/independent_final_results.json').write_text(json.dumps(out,indent=2)+'\n')
    print(json.dumps(out,indent=2))

if __name__=='__main__':
    final_results() if '--final' in sys.argv else main()
