"""Fresh complete run in a required, previously nonexistent directory."""
from pathlib import Path
import argparse, json, os, shutil, subprocess, sys
import numpy as np
R=Path(__file__).resolve().parent
ap=argparse.ArgumentParser();ap.add_argument('directory');a=ap.parse_args();dest=Path(a.directory).resolve()
assert not dest.exists(),'Destination must not exist: refusing to reuse a cache or overwrite data.'
dest.mkdir(parents=True)
protocol=json.loads((R/'frozen_protocol.json').read_text())
for relative in protocol['hashes']:
    src=R.parent/relative;out=dest/relative;out.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(src,out)
D=dest/R.name
for name in ['frozen_protocol.json','audit.py','reproduce.py','requirements.txt']:
    shutil.copy2(R/name,D/name)
(D/'results').mkdir();(D/'logs').mkdir()
env=os.environ.copy();env.update(PYTHONDONTWRITEBYTECODE='1',OPENBLAS_NUM_THREADS='1')
for command in [['experiment.py','check'],['experiment.py','run'],['audit.py']]:
    with (D/'logs'/f"fresh_{command[0]}_{command[-1]}.log").open('w') as f:
        subprocess.run([sys.executable,str(D/command[0]),*command[1:]],check=True,env=env,stdout=f,stderr=subprocess.STDOUT)
compared=0
for path in (R/'results').glob('*.npz'):
    x=np.load(path);y=np.load(D/'results'/path.name);assert set(x.files)==set(y.files)
    for key in x.files:assert np.array_equal(x[key],y[key]),(path.name,key)
    compared+=1
for c in json.loads((R/'data/cases.json').read_text()):
    x=json.loads((R/'results'/f"{c['id']}.json").read_text());y=json.loads((D/'results'/f"{c['id']}.json").read_text());x.pop('seconds');y.pop('seconds');assert x==y,c['id']
result=dict(fresh_directory=str(D),all_npz_arrays_equal=True,npz_files_compared=compared,case_records_equal_except_runtime=216)
(D/'fresh_comparison.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
