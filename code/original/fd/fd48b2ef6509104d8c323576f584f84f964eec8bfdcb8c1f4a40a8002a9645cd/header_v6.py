"""Conditional published header hypothesis: first12 glyphs are a non-cipher heading.
This does NOT validate the alleged heading. Only tries to read remaining75 signs;
no alleged plaintext letters are provided to search. No p-values or exclusion claim.
"""
import json,time,hashlib
import numpy as np
from concurrent.futures import ThreadPoolExecutor
from model_v5 import ROOT
from automata import canonical
from wordsearch_v4 import WordSearch
from fastsolve import solve_fast
from language import stable_seed
import homophonic_v6 as h
import homophonic_emission_v6 as e
OUT=ROOT/'results/v6/header';OUT.mkdir(parents=True,exist_ok=True)
PROTOCOL={'hypothesis':'first12 are an independent visual heading, tail is75 coded glyphs','prefix_status':'not established',
 'external_source':'https://ciphermysteries.com/2013/02/24/dorabella-cipher-first-two-words-decrypted',
 'searches':['injective substitution','many-to-one with emission penalty'],
 'crib_letters':False,'mono_budget':[128,16000],'homophone_budget':[128,16000],'null_calibration':False}

def run(case,eng):
    dest=OUT/(case['id']+'.json')
    if dest.exists():return
    t=time.monotonic();g=(3*np.array(case['orientation'])+case['arcs'])[12:];seq=canonical(g)
    _,key=solve_fast(seq,eng.lp,eng.p1,128,20000,stable_seed(seq,'header_v6_initial'))
    mono=eng.run(seq,key[seq],dict(restarts=128,iterations=16000),tag='header_v6_word')
    ss,k,trace=e.solve(seq,key,eng.lp,eng.children,eng.vals,eng.p1,*h.prepare(seq,eng.scorer),128,16000,stable_seed(seq,'header_v6_homo'))
    txt=''.join(chr(v+97) for v in k[seq]);_,seg=eng.scorer.score(txt,True)
    rec=dict(id=case['id'],n_symbols=75,mono=mono,mono_text=''.join(chr(v+97) for v in mono['decoded']),homophone=dict(score=float(ss),key=k.tolist(),text=txt,segmentation=seg,trace=trace.tolist()),seconds=time.monotonic()-t)
    dest.write_text(json.dumps(rec,indent=2));print(case['id'],mono['score'],rec['mono_text'],'; homo',ss,txt,rec['seconds'],flush=True)

def main():
    eng=WordSearch();cs=[z for z in json.loads((ROOT/'results/v5/inputs.json').read_text())['cases'] if z['kind']=='real']
    f=dict(protocol=PROTOCOL,hashes={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in ['header_v6.py','homophonic_emission_v6.py','homophonic_v6.py','wordsearch_v4.py','data/english_model.npz']},dictionary=eng.scorer.metadata)
    p=OUT/'frozen.json'
    if p.exists():assert json.loads(p.read_text())==f
    else:p.write_text(json.dumps(f,indent=2))
    (OUT/'inputs.json').write_text(json.dumps(cs,indent=2))
    with ThreadPoolExecutor(max_workers=2) as pool:list(pool.map(lambda c:run(c,eng),cs))
if __name__=='__main__':main()
