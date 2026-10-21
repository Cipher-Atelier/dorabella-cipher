"""Summarize completed round6 results without extrapolating unfinished cases."""
import argparse,csv,json,hashlib,platform,sys
from pathlib import Path
import numpy as np
from model_v5 import ROOT
OUT=ROOT/'results/v6'
FAMILIES=['whole24','routes','localrules','relax','homophonic','homophonic_emission','periodic','fraction','header','merged_masc','keyword_tables','routes_wordall']

def cases_for(family):
    obj=json.loads((OUT/family/'inputs.json').read_text())
    return obj['cases'] if isinstance(obj,dict) else obj

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--partial',action='store_true');args=ap.parse_args()
    summary={'date':'2026-09-26','status':'No verified decipherment. Candidate strings are optimization outputs, not proposed plaintexts.',
     'selection_warning':'Families were explored adaptively. Within-family paired shuffle tests do not correct the entire research history. No pooled p-values or cross-family score comparisons.',
     'sensitivity_warning':'All plaintext fixtures reused from prior rounds; newly encrypted examples are not new independent historical texts.',
     'families':{}}
    rows=[]
    for fam in FAMILIES:
        directory=OUT/fam;cs=cases_for(fam);pairs=[];missing=[]
        if fam=='fraction':
            for kind in ('square','cube'):
                for c in cs:
                    name=kind+'_'+c['id'];path=directory/(name+'.json')
                    if path.exists():
                        r=json.loads(path.read_text());pairs.append((dict(c,id=name,kind='real'),r))
                    else:missing.append(name)
        else:
            for c in cs:
                path=directory/(c['id']+'.json')
                if path.exists():pairs.append((c,json.loads(path.read_text())))
                elif fam=='relax' and c['kind']=='null':pass # Inputs constructed, deliberately NOT executed.
                else:missing.append(c['id'])
        if not args.partial:assert not missing,(fam,missing)
        item={'completed_records':len(pairs),'missing_records':missing,'real':{},'null_calibrated':False}
        positive=[];nulls={};real={}
        for c,r in pairs:
            score=r.get('best_score',r.get('score'));text=r.get('best_text',r.get('text'))
            if fam=='header':score=r['mono']['score'];text=r['mono_text']
            row=dict(family=fam,id=c['id'],kind=c['kind'],best_score=score,accuracy=r.get('accuracy'),n_evaluations=r.get('n_rule_evaluations',r.get('n_evaluations',r.get('definitions_char_scored'))),text=text)
            rows.append(row)
            if c['kind']=='real':
                rr=dict(best_score=score,text=text)
                for k in ('identity_score','static_score','gain','n_plain_letters','n_glyphs','emission_penalty','definitions_char_scored','definitions_fully_scored','n_evaluations','n_rule_evaluations','n_routes','n_definitions','distinct_patterns','first_count'):
                    if k in r:rr[k]=r[k]
                if fam=='header':rr['homophone_score']=r['homophone']['score'];rr['homophone_text']=r['homophone']['text']
                item['real'][c['id']]=rr;real[c['id']]=r
            elif c['kind']=='null':
                prefix=c['id'].split('_')[0];nulls.setdefault(prefix,[]).append((c['pair'],r))
            elif c['kind']=='positive':positive.append(r)
        if positive:
            acc=np.array([r['accuracy'] for r in positive]);item['sensitivity']={
                'n':len(acc),'mean_accuracy':float(acc.mean()),'min_accuracy':float(acc.min()),'exact':int((acc==1).sum()),
                'at_least_90pct':int((acc>=.9).sum()),'cases':[{'id':r['id'],'accuracy':r['accuracy']} for r in positive],
                'not_independent_holdout':True}
        if nulls:
            item['null_calibrated']=True;item['nulls']={}
            for pre,rr in nulls.items():
                r=real[pre+'_real'];values=np.array([z['best_score'] for _,z in rr]);k=int((values>=r['best_score']).sum());n=len(values)
                q=dict(n=n,exceedances=k,plus_one_tail=(k+1)/(n+1),mean_maximum=float(values.mean()))
                if 'gain' in r:
                    gains=np.array([z['gain'] for _,z in rr]);q.update(gain_exceedances=int((gains>=r['gain']).sum()),mean_gain=float(gains.mean()))
                item['nulls'][pre]=q
            hn=dict(nulls['hauer']);tn=dict(nulls['hart']);assert set(hn)==set(tn)
            threshold=max(real['hauer_real']['best_score'],real['hart_real']['best_score'])
            exceed=sum(max(hn[i]['best_score'],tn[i]['best_score'])>=threshold for i in hn)
            item['paired_choice_between_transcriptions']={'n':len(hn),'exceedances':exceed,'plus_one_tail':(exceed+1)/(len(hn)+1)}
        if fam=='relax':item['unused_manifest_nulls']=sum(c['kind']=='null' for c in cs)
        if fam=='routes':
            failure=json.loads((directory/'positive_00.json').read_text());item['known_screen_failure']={k:failure[k] for k in ['accuracy','true_pattern_finalist','true_pattern_ranks']}
        if fam=='routes_wordall':
            p=directory/'positive_00.json'
            if p.exists():
                r=json.loads(p.read_text());item['targeted_regression']={k:r[k] for k in ['accuracy','true_route_first_rank','best_text']}
            item['old_null_calibration_does_not_apply']=True
        summary['families'][fam]=item
    summary['total_completed_records']=sum(v['completed_records'] for v in summary['families'].values())
    summary['checks']=json.loads((OUT/'implementation_checks.json').read_text()) if (OUT/'implementation_checks.json').exists() else None
    target=OUT/('summary_partial.json' if args.partial else 'summary.json');target.write_text(json.dumps(summary,ensure_ascii=False,indent=2))
    with (OUT/('results_partial.csv' if args.partial else 'results.csv')).open('w',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
    print('completed:',summary['total_completed_records']);print(json.dumps({f:{'records':v['completed_records'],'sensitivity':v.get('sensitivity'),'paired':v.get('paired_choice_between_transcriptions')} for f,v in summary['families'].items()},ensure_ascii=False,indent=2))

if __name__=='__main__':main()
