"""AST/hash checks ONLY. Never imports or executes the A2 target modules."""
import ast
import copy
import hashlib
import json
from pathlib import Path


def expression(text):
    return ast.parse(text, mode='eval').body


def canonical(node):
    return ast.dump(node, include_attributes=False)


class ExplicitListPort(ast.NodeTransformer):
    def visit_FunctionDef(self, node):
        node.decorator_list = []
        return self.generic_visit(node)

    def visit_Subscript(self, node):
        if canonical(node) == canonical(expression('table.shape[1]')):
            return expression('len(table[0])')
        if canonical(node) == canonical(expression('table[glyph[i],j]')):
            return expression('table[glyph[i]][j]')
        return self.generic_visit(node)

    def visit_Call(self, node):
        if canonical(node) == canonical(expression('np.empty(87*dim,np.int64)')):
            return expression('[0]*(87*dim)')
        if canonical(node) == canonical(expression('np.empty(87,np.int64)')):
            return expression('[0]*87')
        return self.generic_visit(node)


def main():
    root = Path(__file__).resolve().parent
    checks = []
    def record(name, ok, **extra):
        checks.append({'check': name, 'passed': bool(ok), **extra})
    files = sorted((root / 'code').glob('*.py'))
    trees = {p.name: ast.parse(p.read_text(), filename=str(p)) for p in files}
    original_bytes = (root / 'sources/fraction_v6.py').read_bytes()
    record('original_fraction_pin', hashlib.sha256(original_bytes).hexdigest() ==
           'c6b81f911509373b80979142ef87d61fe3a5b03cb89843a90b7b3866f3debbe4')
    original = ast.parse(original_bytes)
    old = next(n for n in original.body if isinstance(n, ast.FunctionDef) and n.name == 'output_numeric')
    new = next(n for n in trees['source_port.py'].body if isinstance(n, ast.FunctionDef) and n.name == 'output_numeric')
    changed = ExplicitListPort().visit(copy.deepcopy(old))
    record('output_numeric_AST_after_only_declared_changes', canonical(changed) == canonical(new),
           changes=['remove njit decorator','shape[1] -> len(table[0])','two np.empty -> zero lists',
                    'table[glyph[i],j] -> table[glyph[i]][j]'])
    assignment = ast.parse('p[(first+i)*dim+j]=first*dim+j*m+i').body[0]
    route_fn = next(n for n in trees['source_port.py'].body if isinstance(n, ast.FunctionDef) and n.name == 'route_one')
    record('route_core_index_assignment_unchanged', any(canonical(n) == canonical(assignment) for n in ast.walk(route_fn)))
    forbidden_imports = {'subprocess','multiprocessing','threading','concurrent','numpy','numba','scipy',
                         'gensim','textblob','random','socket','requests','urllib','asyncio'}
    banned_calls = {'fork','forkpty','posix_spawn','Popen','system','execv','execve','kill','killpg',
                    'Thread','Process','evaluate','score','build_model','WordSearch','argpartition',
                    'sleep','eval','exec','compile','__import__'}
    imports, calls, loops, lines = {}, {}, {}, {}
    for name, tree in trees.items():
        imports[name] = [a.name for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names]
        imports[name] += [n.module or '' for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)]
        calls[name] = sorted({ast.unparse(n.func) for n in ast.walk(tree) if isinstance(n, ast.Call)})
        loops[name] = {'for': sum(isinstance(n, ast.For) for n in ast.walk(tree)),
                       'while': sum(isinstance(n, ast.While) for n in ast.walk(tree)),
                       'async': sum(isinstance(n, (ast.AsyncFor, ast.AsyncFunctionDef, ast.Await)) for n in ast.walk(tree))}
        lines[name] = {n.name: [n.lineno, n.end_lineno] for n in tree.body if isinstance(n, ast.FunctionDef)}
        record(name+':allowed_imports', not any(i.split('.')[0] in forbidden_imports for i in imports[name]))
        record(name+':no_process_score_dynamic_code_calls', not any(c.rsplit('.',1)[-1] in banned_calls for c in calls[name]))
        record(name+':no_while_async', loops[name]['while'] == loops[name]['async'] == 0)
        functions = {n.name: n for n in tree.body if isinstance(n, ast.FunctionDef)}
        adjacency = {k:{n.func.id for n in ast.walk(v) if isinstance(n, ast.Call) and
                        isinstance(n.func, ast.Name) and n.func.id in functions} for k,v in functions.items()}
        def cycle(node, visiting):
            return node in visiting or any(cycle(child, visiting | {node}) for child in adjacency[node])
        record(name+':no_direct_local_recursion', not any(cycle(node,set()) for node in adjacency))
    for name in ('source_port.py','reference_frozen.py','block_oracle.py'):
        record(name+':no_imports_at_all', imports[name] == [])
        allowed_top = (ast.FunctionDef, ast.Assign, ast.Expr)
        top = trees[name].body
        ok = all(isinstance(n, allowed_top) and not any(isinstance(x,ast.Call) for x in ast.walk(n))
                 for n in top if not isinstance(n,ast.FunctionDef))
        record(name+':no_top_level_execution_calls',ok)
    vector = json.loads((root / 'vectors.json').read_text())
    record('declared_counts_11_3_8', (len(vector['positive']),len(vector['missing']),len(vector['invalid'])) == (11,3,8))
    record('eight_fixed_flag_combinations', {tuple(z['route'][f] for f in ('reset','inverse','reverse'))
          for z in vector['positive'][3:]} == {(a,b,c) for a in (0,1) for b in (0,1) for c in (0,1)})
    record('three_literal_golden_definitions', sum(z['golden'] is not None for z in vector['positive']) == 3)
    record('fixture_max_lengths', all(1<=z['route']['period']<=87 and len(z['key']['arcs'])==3
           for z in vector['positive']))
    result = {'kind':'STATIC_ONLY_NOT_A2_EXECUTION','checks':checks,'all_pass':all(c['passed'] for c in checks),
              'imports':imports,'calls':calls,'loops':loops,'function_lines':lines,
              'limits':'No target module was imported. Test vectors were not evaluated. AST checks are not a semantic proof.'}
    destination=root/'evidence/static_review.json'
    if destination.exists():raise SystemExit('REFUSE_OVERWRITE_STATIC_REVIEW')
    destination.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({'static_pass':result['all_pass'],'checks':len(checks),'A2_executed':False}))
    return 0 if result['all_pass'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
