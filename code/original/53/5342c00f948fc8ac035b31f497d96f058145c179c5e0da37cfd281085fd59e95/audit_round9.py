"""Check stored arrays, frozen procedures and exact preservation of round8 inputs.
Use --old-archive to change the input ZIP location. No old file is modified.
"""
from pathlib import Path
import argparse,sys,json,hashlib,zipfile,subprocess,platform,importlib.metadata,time
import numpy as np
HERE=Path(__file__).resolve().parent;ROOT=HERE.parent
sys.path[:0]=[str(HERE),str(ROOT),str(ROOT/'round8')]
import geometry_order as geo
import change_point as cp
from exact_study import le_exact
from conditional_v7 import euler_shuffle

def sha(b):return hashlib.sha256(b).hexdigest()
def dump(p,x):p.write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n')
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--old-archive',type=Path,default=ROOT.parent.parent/'dorabella_lab_round8.zip');args=ap.parse_args()
    t=time.monotonic();result={'old_archive':{},'frozen_protocols':{},'geometry':{},'change_point':{}}
    original_hashes={}
    with zipfile.ZipFile(args.old_archive) as z:
        for info in z.infolist():
            if info.is_dir():continue
            data=z.read(info.filename);path=ROOT.parent/info.filename
            assert path.is_file(),str(path)
            assert sha(path.read_bytes())==sha(data),info.filename
            original_hashes[info.filename]=sha(data)
    result['old_archive']={'file':args.old_archive.name,'sha256':sha(args.old_archive.read_bytes()),'unchanged_files':len(original_hashes),'all_unchanged':True}
    dump(HERE/'results/old_archive_file_hashes.json',original_hashes)
    for name in ['frozen_geometry_protocol.json','frozen_change_point_protocol.json']:
        frozen=json.loads((HERE/name).read_text())
        for rel,h in frozen['sha256'].items():assert sha((ROOT/rel).read_bytes())==h,rel
        result['frozen_protocols'][name]='all hashes match'
    cases=[c for c in json.loads((ROOT/'results/v7/conditional/inputs.json').read_text())['cases'] if c['kind']=='real']
    gs=json.loads((geo.OUT/'summary.json').read_text());cs=json.loads((cp.OUT/'summary.json').read_text())
    for ci,c in enumerate(cases):
        name=c['id'];s=np.array(c['glyph'],np.int64);rows=[]
        for r,(st,en) in enumerate(geo.ROWS):
            z=np.load(geo.OUT/f'{name}_row{r+1}.npz');a=z['sequences'];e=z['energy_pairs']
            assert len(a)==gs['cases'][name]['rows'][r]['n']
            assert len(np.unique(a,axis=0))==len(a)
            assert np.all(np.sort(a,axis=1)==np.sort(s[st:en]))
            b=a.astype(np.int64)
            assert np.all(np.sort(b[:,:-1]*24+b[:,1:],axis=1)==np.sort(s[st:en-1]*24+s[st+1:en]))
            assert np.all(a[:,0]==s[st]) and np.all(a[:,-1]==s[en-1])
            recalculated,endpoints=geo.path_measures(a);assert np.array_equal(recalculated,e)
            obs,obs_ep=geo.path_measures(s[st:en][None,:]);assert np.all(endpoints==obs_ep)
            assert int(le_exact(e,obs[0]).sum())==gs['cases'][name]['rows'][r]['exact_le']
            rows.append((a,e))
        mc={}
        for si,style in enumerate(['unigram','bigram']):
            rng=np.random.default_rng(np.random.SeedSequence([geo.PROTOCOL['seed'],ci,si]))
            summary,a,e=geo.MC(s,rows,style,rng)
            old=np.load(geo.OUT/f'{name}_{style}_mc.npz')
            assert np.array_equal(a,old['sequences'])
            assert np.array_equal(e,old['energy_pairs'])
            assert summary==gs['cases'][name][style]
            mc[style]={'full_replayed_draws':len(a),'all_sequences_energies_and_summary_identical':True}
        result['geometry'][name]={'full_row_ensemble_entries_checked':sum(len(a) for a,e in rows),'MC':mc}
        res={};obs=cp.stats(s[None,:])[0]
        for si,style in enumerate(['unigram','bigram','trigram']):
            z=np.load(cp.OUT/f'{name}_{style}.npz');a=z['sequences'];v=z['statistics']
            assert np.all(np.sort(a,axis=1)==np.sort(s));b=a.astype(np.int64)
            if style!='unigram':
                assert np.all(a[:,0]==s[0]) and np.all(a[:,-1]==s[-1])
                assert np.all(np.sort(b[:,:-1]*24+b[:,1:],axis=1)==np.sort(s[:-1]*24+s[1:]))
            if style=='trigram':
                assert np.array_equal(a,np.load(ROOT/f'round8/results/{name}_trigrams.npz')['sequences'])
                assert np.all(a[:,:2]==s[:2]) and np.all(a[:,-2:]==s[-2:])
                assert np.all(np.sort(b[:,:-2]*576+b[:,1:-1]*24+b[:,2:],axis=1)==np.sort(s[:-2]*576+s[1:-1]*24+s[2:]))
            new=cp.stats(a);assert np.array_equal(new,v)
            assert cp.summary(a,v,obs,s,style!='trigram')==cs['cases'][name]['nulls'][style]
            replay=0
            if style!='trigram':
                rng=np.random.default_rng(np.random.SeedSequence([cp.PROTOCOL['seed'],ci,si]));s8=s.astype(np.uint8)
                for i in range(50):
                    x=rng.permutation(s8) if style=='unigram' else euler_shuffle(s8,rng)
                    assert np.array_equal(x,a[i]);replay+=1
            res[style]={'full_statistic_rows_recomputed':len(a),'cuts_per_row':v.shape[1],
                'sampling_prefix_replayed':replay,'all_constraints_and_summary_match':True}
        result['change_point'][name]=res
    old=(HERE/'results/literal_walk.json').read_bytes()
    p=subprocess.run([sys.executable,str(HERE/'literal_walk.py')],capture_output=True,text=True,check=True)
    assert old==(HERE/'results/literal_walk.json').read_bytes()
    result['literal_walk']={'full_symbolic_replay_identical':True,'four_geometric_cases':4,'direct_symbolic_checks':16}
    result['environment']={'python':sys.version,'platform':platform.platform(),
        'packages':{p:importlib.metadata.version(p) for p in ['numpy','numba','sympy','scipy']},
        'compiler':subprocess.run(['g++','--version'],capture_output=True,text=True,check=True).stdout.splitlines()[0]}
    result['wall_seconds_for_this_audit']=time.monotonic()-t
    dump(HERE/'results/final_audit.json',result);print(json.dumps(result,indent=2),flush=True)
if __name__=='__main__':main()
