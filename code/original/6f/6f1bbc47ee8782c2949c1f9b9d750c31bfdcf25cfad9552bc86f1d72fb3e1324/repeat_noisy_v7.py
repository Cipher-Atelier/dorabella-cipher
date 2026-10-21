"""Full deterministic reruns of the two noisy-transcription real inputs.
These are technical repeats, not additional independent trials.
"""
from pathlib import Path
import json
from concurrent.futures import ThreadPoolExecutor
from noisy_v7 import WordSearch,dictionary_by_length,run_case
ROOT=Path(__file__).resolve().parent;OUT=ROOT/'results/v7/noisy'
def main():
 engine=WordSearch();pack=dictionary_by_length(engine.scorer);cases=[c for c in json.loads((OUT/'inputs.json').read_text())['cases'] if c['kind']=='real'];dest=OUT/'repeats';dest.mkdir(exist_ok=True)
 def check(c):
  old=json.loads((OUT/'records'/(c['id']+'.json')).read_text());new=run_case(c,engine,pack)
  for field in ('best','frontier','trace'):assert old[field]==new[field],(c['id'],field)
  (dest/(c['id']+'.json')).write_text(json.dumps(new,indent=2));print('repeat verified',c['id'],flush=True);return c['id']
 with ThreadPoolExecutor(max_workers=2) as pool:done=list(pool.map(check,cases))
 (OUT/'repeat_checks.json').write_text(json.dumps({'full_noisy_deterministic_repeats':done,'matched_fields':['best','frontier','trace']},indent=2))
if __name__=='__main__':main()
