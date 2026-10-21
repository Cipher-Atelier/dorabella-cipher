"""AST/hash/literal review only. Never imports or executes reviewed code/data rules."""
import ast
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
checks = []


def check(name, passed, **detail):
    checks.append({'check': name, 'passed': bool(passed), **detail})
    if not passed:
        raise ValueError(name)


def tree(name):
    return ast.parse((ROOT / name).read_text())


def function(t, name):
    return next(n for n in t.body if isinstance(n, ast.FunctionDef) and n.name == name)


def dump(node):
    return ast.dump(node, include_attributes=False)


pins = {
    'data/positive_source_prefixes.json': 'a142aca9d82d2b6c616a4cd4fbf990f143de667879d4a08360fd0368dd0b294e',
    'data/regression_inputs_original.json': '0d91979dc0aa9834598e9a97f481f9f7595fae022d7a8b33f004b314492eaf7a',
    'sources/review-v1.md': 'fc562ee916908f9f1aa9f60f8fe1e6415a8b9e3d4505697954a5e46b03a11464',
    'sources/driver_review1.py': '9ba2ccfeab4a57b5524ab0b1e0e0ca271b5d42d1f61d9c110988738bad243fb5',
    'sources/fraction_v6.py': 'c6b81f911509373b80979142ef87d61fe3a5b03cb89843a90b7b3866f3debbe4',
    'code/source_port.py': '593a382b892cac74cd062f72f484986d890ced7311e151a422f7d9e11048620e',
    'code/reference_frozen.py': '43979abe589452f87146ce1a20fbd979ac048433fb466d3d40bb842e7006ee52',
    'code/block_oracle.py': '8e70d384388d5f1bf882b62c827ef5d0119c86c8453b8ba4c8fd9a54f805b2d7',
    'sources/run_a2_frozen.py': 'ee2125c4572c74f1b14f0c1572c98c811cb865b5a65db90108c379de7183ddfc',
    'evidence/a2_manifest.json': '9564da52e4e2b776920b36eeb686bd95a37f717d1b47d50c2e124a8cd7047863',
}
for name, pin in pins.items():
    check('byte_pin:' + name, hashlib.sha256((ROOT / name).read_bytes()).hexdigest() == pin)
old = tree('sources/driver_review1.py')
assignment = tree('code/assignment_frozen.py')
runner = tree('code/run_a3.py')
a2 = tree('sources/run_a2_frozen.py')
check('control_assignment_exact_AST', dump(function(old, 'control_assignment')) ==
      dump(function(assignment, 'control_assignment')))
old_candidates, new_candidates = function(old, 'candidates'), function(runner, 'candidates')
def assigned(t, name):
    return next(n for n in ast.walk(t) if isinstance(n, ast.Assign) and
                any(isinstance(x, ast.Name) and x.id == name for x in n.targets))
check('fresh_route_product_exact_AST', dump(assigned(old_candidates, 'params')) == dump(assigned(new_candidates, 'params')))
def regression_for(t):
    return next(n for n in ast.walk(t) if isinstance(n, ast.For) and isinstance(n.target, ast.Tuple) and
                [x.id for x in n.target.elts] == ['index', 'case_id', 'values'])
check('regression_indices_ids_routes_exact_AST', dump(regression_for(old_candidates).iter) == dump(regression_for(new_candidates).iter))
for name in ('limited_read', 'digest', 'interpreter_digest', 'write_new', 'check'):
    check('A2_operational_body_unchanged:' + name, dump(function(a2, name)) == dump(function(runner, name)))
allowed_imports = {'argparse', 'hashlib', 'importlib.util', 'itertools', 'json', 'os', 'pathlib', 'sys', 'time'}
forbidden_calls = {'eval', 'exec', 'compile', '__import__', 'subprocess', 'Popen', 'run', 'system', 'fork',
                   'spawn', 'Thread', 'Process', 'Pool', 'ThreadPoolExecutor', 'ProcessPoolExecutor',
                   'build_model', 'evaluate', 'tables', 'digit_routes', 'run_g0', 'run_g1', 'sleep'}
observations = {}
for path in sorted((ROOT / 'code').glob('*.py')):
    t = ast.parse(path.read_text())
    imports = []
    for n in ast.walk(t):
        if isinstance(n, ast.Import): imports.extend(a.name for a in n.names)
        if isinstance(n, ast.ImportFrom): imports.append(n.module)
    names = {n.func.id if isinstance(n.func, ast.Name) else n.func.attr
             for n in ast.walk(t) if isinstance(n, ast.Call) and isinstance(n.func, (ast.Name, ast.Attribute))}
    check(path.name + ':stdlib_imports_only', set(imports) <= allowed_imports, imports=imports)
    check(path.name + ':no_process_search_scoring_calls', not names.intersection(forbidden_calls))
    check(path.name + ':no_while_async', not any(isinstance(n, (ast.While, ast.AsyncFunctionDef, ast.AsyncFor)) for n in ast.walk(t)))
    funcs = {n.name: n for n in t.body if isinstance(n, ast.FunctionDef)}
    graph = {name: {n.func.id for n in ast.walk(node) if isinstance(n, ast.Call) and
                   isinstance(n.func, ast.Name) and n.func.id in funcs} for name, node in funcs.items()}
    def cycle(name, seen):
        return name in seen or any(cycle(child, seen | {name}) for child in graph[name])
    check(path.name + ':no_local_recursion', not any(cycle(name, set()) for name in graph))
    if path.name not in ('run_a3.py', 'readback_a3.py'):
        top = ast.Module(body=[n for n in t.body if not isinstance(n, (ast.FunctionDef, ast.ClassDef))], type_ignores=[])
        check(path.name + ':no_top_level_calls', not any(isinstance(n, ast.Call) for n in ast.walk(top)))
    observations[path.name] = {'imports': imports, 'call_names': sorted(names),
                              'functions': {name: [n.lineno, n.end_lineno] for name, n in funcs.items()}}
diagnose = function(runner, 'diagnose')
check('conditional_first_missing_no_scoring',
      ast.unparse(assigned(diagnose, 'chosen').value) == 'eligible[0] if eligible else None')
check('no_runtime_text_replace', not any(isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and
      n.func.attr == 'replace' for n in ast.walk(runner)))
summary = function(runner, 'descriptive_summary')
check('no14_of16_threshold', not any(isinstance(n, ast.Constant) and n.value == 14 for n in ast.walk(summary)))
check('no_attempt_directory', not (ROOT / 'attempt_A3_v1').exists())
result = {'kind': 'STATIC_ONLY_NO_A3_CASE_OR_ASSIGNMENT_EXECUTION', 'checks': checks,
          'all_pass': all(c['passed'] for c in checks), 'check_count': len(checks), 'observations': observations,
          'manual_review': {'scope': 'Source flow reviewed; byte/AST checks do not prove semantic correctness',
                            'normalization': 'Verification of frozen lowercase ASCII prefix; no replacement of plaintext',
                            'domain': 'One assigned q;25 fixed-m predicates, one conditional selected m or domain refusal',
                            'terminal': 'All18 outcomes required; no14/16 threshold or next-stage authorization'},
          'not_executed': ['candidates', 'control_assignment', 'route', 'undo_route', 'encode', 'decode', 'diagnose', 'readback_a3', 'A2 tests']}
with (ROOT / 'evidence/static_review.json').open('x') as f:
    json.dump(result, f, ensure_ascii=False, indent=2)
    f.write('\n')
print(json.dumps({'kind': result['kind'], 'checks': len(checks), 'all_pass': result['all_pass'],
                  'function_lines': {k: v['functions'] for k, v in observations.items()}}, ensure_ascii=False, indent=2))
