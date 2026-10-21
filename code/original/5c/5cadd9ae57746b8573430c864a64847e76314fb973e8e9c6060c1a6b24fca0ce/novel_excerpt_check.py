"""Check exact normalized 87-letter occurrences, not author-level contamination."""
import os,sys,json,hashlib
from pathlib import Path
HERE=Path(__file__).resolve().parent;ROOT=HERE.parent
sys.dont_write_bytecode=True;os.environ.setdefault('NUMBA_CACHE_DIR',str(HERE/'cache'));sys.path.insert(0,str(ROOT))
from model_v5 import normalise
from language import corpus_path,documents
src=corpus_path('lee_background.cor');docs=[normalise(x) for x in documents(src)]
old=json.loads((HERE/'data/old_round9_hashes.json').read_text())
positives=json.loads((HERE/'data/elgar_letters.json').read_text())['cases']
training=[];oldhits=[]
for p in positives:
 for i,s in enumerate(docs):
  if p['plaintext'] in s:training.append([p['id'],i])
for rel in old:
 path=ROOT.parent/rel
 if path.suffix in ('.json','.jsonl','.py','.md','.txt'):
  try:s=normalise(path.read_text())
  except UnicodeError:continue
  for p in positives:
   if p['plaintext'] in s:oldhits.append([p['id'],rel])
r={'training_corpus_sha256':hashlib.sha256(src.read_bytes()).hexdigest(),'training_documents':len(docs),'full_87letter_matches_in_training':training,'full_87letter_matches_in_old_text_artifacts':oldhits,'limitation':'Does not prove author exclusion from all sources used to make the external TextBlob word-frequency dictionary.'}
(HERE/'results/novel_excerpt_check.json').write_text(json.dumps(r,indent=2));print(json.dumps(r,indent=2))
assert not training and not oldhits
