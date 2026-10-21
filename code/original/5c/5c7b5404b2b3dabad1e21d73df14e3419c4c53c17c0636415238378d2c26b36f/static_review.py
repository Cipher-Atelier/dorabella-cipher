"""Source-only audit. Parses AST and hashes bytes; never imports target modules.

No bank construction, text encoding, inverse, score, JIT or worker creation.
"""
import ast
import hashlib
import json
from pathlib import Path
import re


def sha(data):
    return hashlib.sha256(data).hexdigest()


def review(root):
    root = Path(root)
    result = {"kind": "STATIC_ONLY", "checks": [], "functions": {}, "calls": {}}

    def record(name, passed, **detail):
        result["checks"].append({"check": name, "passed": bool(passed), **detail})

    trees = {}
    for path in sorted((root / "code").glob("*.py")):
        tree = ast.parse(path.read_text(), filename=str(path))
        trees[path.name] = tree
        result["functions"][path.name] = {n.name: [n.lineno, n.end_lineno]
                                          for n in tree.body if isinstance(n, (ast.FunctionDef, ast.ClassDef))}
        result["calls"][path.name] = sorted({ast.unparse(n.func) for n in ast.walk(tree) if isinstance(n, ast.Call)})
    record("new_code_ast_parse", True, files=sorted(trees))
    original = (root / "original/fraction_v6.py").read_text()
    ast.parse(original)
    block = "".join(original.splitlines(keepends=True)[99:109])
    new = (root / "code/winner_original.py").read_text()
    start = new.index("    flat=scores.ravel();")
    finish = new.index("    return record\n", start)
    record("winner_literal_lines_100_109", new[start:finish] == block,
           sha256=sha(block.encode()), original_lines=[100, 109],
           new_lines=[new[:start].count("\n") + 1, new[:finish].count("\n")])
    old_tree = ast.parse(original)
    old_run = next(n for n in old_tree.body if isinstance(n, ast.FunctionDef) and n.name == "run")
    old_nodes = [n for n in old_run.body if 100 <= n.lineno <= 109]
    new_fn = next(n for n in trees["winner_original.py"].body if isinstance(n, ast.FunctionDef))
    new_nodes = [n for n in new_fn.body if n.lineno >= new[:start].count("\n") + 1 and not isinstance(n, ast.Return)]
    record("winner_AST_identical", [ast.dump(n, include_attributes=False) for n in old_nodes] ==
           [ast.dump(n, include_attributes=False) for n in new_nodes])
    frozen = json.loads((root / "original/results/v6/fraction/frozen.json").read_text())
    for relative, expected in frozen["hashes"].items():
        actual = sha((root / "original" / relative).read_bytes())
        record("original_freeze:" + relative, actual == expected, sha256=actual)
    record("dictionary_original_freeze",
           sha((root / "original/dictionary/en-spelling.txt").read_bytes()) == frozen["dictionary"]["sha256"])
    protocol = (root / "protocol/review-v1.md").read_bytes()
    record("protocol_byte_identity", sha(protocol) == "fc562ee916908f9f1aa9f60f8fe1e6415a8b9e3d4505697954a5e46b03a11464")
    record("positive_json_byte_identity", sha((root / "inputs/positive_source_prefixes.json").read_bytes()) ==
           "a142aca9d82d2b6c616a4cd4fbf990f143de667879d4a08360fd0368dd0b294e")
    record("regression_source_byte_identity", sha((root / "original/round8/results/elgar/inputs.json").read_bytes()) ==
           "0d91979dc0aa9834598e9a97f481f9f7595fae022d7a8b33f004b314492eaf7a")
    # All hash rows in the protocol for files supplied in this packet, not just 4 original pins.
    text = protocol.decode()
    checked = []
    for relative, expected in re.findall(r"\| `([^`]+)` \| `([0-9a-f]{64})` \|", text):
        path = root / "original" / relative
        if path.is_file():
            checked.append(relative)
            record("protocol_source_pin:" + relative, sha(path.read_bytes()) == expected)
    record("supplementary_source_pins_present", len(checked) >= 16, files=checked)
    forbidden = {"main", "run", "evaluate", "build_model", "WordSearch", "WordScorer", "make_model", "load_model", "score"}
    calls = result["calls"]["driver.py"]
    bad = [s for s in calls if s.rsplit(".", 1)[-1] in forbidden]
    record("driver_no_solver_or_scorer_calls", not bad, forbidden_found=bad)
    spawning = []
    for name, calls in result["calls"].items():
        spawning += [name + ":" + c for c in calls if c.rsplit(".", 1)[-1] in
                     {"Popen", "fork", "execv", "execve", "kill", "killpg", "system"}]
    record("no_spawn_or_signal_backend_in_this_revision", not spawning,
           meaning="Intentional fail-closed blocker, NOT proof of a functioning resource supervisor")
    result["static_machine_checks_pass"] = all(z["passed"] for z in result["checks"])
    result["not_established"] = ["Runtime execution", "G0/G1 success", "Function return correctness by tests",
                                  "Operational context/launcher/watchdog integration", "Host-crash durability"]
    return result


if __name__ == "__main__":
    root = Path(__file__).resolve().parents[1]
    result = review(root)
    destination = root / "evidence/static_machine_review.json"
    if destination.exists():
        raise SystemExit("REFUSE_OVERWRITE_REVIEW")
    destination.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"static_machine_checks_pass": result["static_machine_checks_pass"],
                      "checks": len(result["checks"]), "output": str(destination)}))
    raise SystemExit(0 if result["static_machine_checks_pass"] else 1)
