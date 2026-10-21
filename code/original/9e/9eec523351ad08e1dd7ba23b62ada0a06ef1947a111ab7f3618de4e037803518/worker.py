"""Single-case launcher: archived solver byte-identical; metadata/paths only overridden."""
import os,sys,json,copy
from pathlib import Path
R=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(R/'dependencies'),str(R/'lab')]
# Archived TextBlob code is not required; only its pinned spelling data file is used.
import types
stub=types.ModuleType('textblob');stub.__file__=str(R/'dictionary/textblob/__init__.py');sys.modules['textblob']=stub
import routes_wordall_v6 as solver
if __name__=='__main__':
    case=sys.argv[1]
    assert case in [x['id'] for x in json.loads((R/'inputs/cases.json').read_text())]
    solver.OUT=R/'runs'/case;solver.OUT.mkdir(parents=True,exist_ok=True)
    solver.PROTOCOL=copy.deepcopy(solver.PROTOCOL)
    # These fields describe inputs/status only and are not read by the search.
    solver.PROTOCOL['cases']=[case]
    solver.PROTOCOL['null_calibration']=True
    solver.PROTOCOL['regression_status']='archived regression or reused conditional null; see master protocol'
    sys.argv=['routes_wordall_v6.py','--workers','4']
    solver.main()
