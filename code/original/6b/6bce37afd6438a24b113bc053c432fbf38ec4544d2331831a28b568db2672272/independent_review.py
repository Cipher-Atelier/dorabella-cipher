"""Reproduce the independent, bounded Round13 full87 code/data review.

This reconstructs and reruns the checks previously executed read-only. It does
not import the engine, compile Numba functions, modify frozen inputs, or run a
full search. Selected function definitions are loaded through AST extraction
with decorators removed, preventing bytecode/Numba cache writes. Only the JSON
report beside this script is written.

Run: python -B dorabella_round13/checks/independent_review/independent_review.py
"""
from pathlib import Path
from collections import Counter
import ast
import datetime
import hashlib
import itertools
import json
import platform
import sys
import time

import numpy as np


SCRIPT = Path(__file__).resolve()
OUT = SCRIPT.parent
H = OUT.parents[1]
ROOT = H.parent
EXPECTED_PROTOCOL_SHA256 = "43de9f2fc5dec87c13e9ec9a68d58295aed951a4d865f32c9648a0ff86f2a4a3"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def check(condition, description):
    if not condition:
        raise AssertionError(description)


def extract_functions(path, names, env):
    """Execute only named function definitions, with all decorators removed."""
    nodes = []
    for node in ast.parse(path.read_text()).body:
        if isinstance(node, ast.FunctionDef) and node.name in names:
            node.decorator_list = []
            nodes.append(node)
    check({node.name for node in nodes} == set(names), "Missing function in " + str(path))
    module = ast.fix_missing_locations(ast.Module(body=nodes, type_ignores=[]))
    exec(compile(module, str(path), "exec"), env)


def main():
    started = datetime.datetime.now(datetime.timezone.utc).isoformat()
    begin = time.monotonic()
    protocol_path = H / "frozen_protocol.json"
    protocol_sha = sha(protocol_path)
    check(protocol_sha == EXPECTED_PROTOCOL_SHA256, "Unexpected frozen protocol")
    frozen = json.loads(protocol_path.read_text())
    frozen_dependencies = []
    for name, expected in frozen["hashes"].items():
        actual = sha(H / name)
        check(actual == expected, "Frozen dependency changed: " + name)
        frozen_dependencies.append({"path": name, "sha256": actual, "passed": True})

    cases = json.loads((H / "data/cases.json").read_text())
    search_inputs = json.loads((H / "data/search_inputs.json").read_text())
    check(len(cases) == len(search_inputs) == 94, "Case count")
    check(len({c["id"] for c in cases}) == 94, "Unique case IDs")
    check(Counter(c["kind"] for c in cases) == {"positive": 12, "regression": 2, "real": 2, "null": 78}, "Case kinds")
    for c, solver in zip(cases, search_inputs):
        check(set(solver) == {"id", "kind", "glyph"}, "Solver input fields")
        check((c["id"], c["kind"], c["glyph"]) == (solver["id"], solver["kind"], solver["glyph"]), "Solver input equality")
        check(len(c["glyph"]) == 87 and all(isinstance(x, int) and 0 <= x < 24 for x in c["glyph"]), "Full87 glyph length/range")
        if "plaintext" in c:
            check(len(c["plaintext"]) == 87, "Full87 plaintext length")

    old = json.loads((H / "data/round11_frozen_protocol.json").read_text())
    archive_matches = []
    for old_name, name in [("round11/data/cases.json", "data/cases.json"), ("round11/data/scoring.npz", "data/scoring.npz")]:
        actual = sha(H / name)
        check(actual == old["hashes"][old_name], "Round11 archive mismatch: " + name)
        archive_matches.append({"path": name, "sha256": actual, "round11_frozen_sha256": old["hashes"][old_name], "passed": True})

    engine_path = H / "code/engine.py"
    verifier_path = H / "code/verify.py"
    shuffle_path = ROOT / "dorabella_audit/test_lab/conditional_v7.py"
    nodes = {n.name: n for n in ast.parse(engine_path.read_text()).body if isinstance(n, ast.FunctionDef)}
    provenance = json.loads((H / "checks/engine_body_provenance.json").read_text())
    ast_checks = []
    for entry in provenance:
        source_path = ROOT / entry["source"]
        source_nodes = {n.name: n for n in ast.parse(source_path.read_text()).body if isinstance(n, ast.FunctionDef)}
        current_body = ast.dump(ast.Module(body=nodes[entry["function"]].body, type_ignores=[]))
        source_body = ast.dump(ast.Module(body=source_nodes[entry["function"]].body, type_ignores=[]))
        actual_body_sha = hashlib.sha256(current_body.encode()).hexdigest()
        check(current_body == source_body, "Archived AST body mismatch: " + entry["function"])
        check(actual_body_sha == entry["body_ast_sha256"], "Provenance AST hash mismatch")
        check(sha(source_path) == entry["source_sha256"], "Archived source hash mismatch")
        ast_checks.append({"function": entry["function"], "source": entry["source"], "source_sha256": sha(source_path), "body_ast_sha256": actual_body_sha, "passed": True})
    check(len(ast_checks) == 6, "Expected six preserved functions")
    check(sha(shuffle_path) == old["hashes"]["conditional_v7.py"], "Shuffle source hash mismatch")

    letter = np.array([ord(x) - 97 for x in "abcdefghiklmnopqrstuwxyz"], np.int64)
    p8 = np.array(list(itertools.permutations(range(8))), np.int64)
    q = np.array([[1, 0, 2], [0, 1, 2], [0, 2, 1]], np.int64)
    env = {"np": np, "Counter": Counter, "P8": p8, "Q": q, "LETTER": letter}
    extract_functions(engine_path, {"key_at", "fast_word", "char_score", "ambiguous_word", "scan_block"}, env)
    extract_functions(verifier_path, {"independent_key", "ref_word", "ref_score"}, env)
    extract_functions(shuffle_path, {"euler_shuffle", "bigrams"}, env)

    with np.load(H / "data/scoring.npz", allow_pickle=False) as stored:
        arrays = {name: stored[name] for name in stored.files}
    lp, children, values = (arrays[name] for name in ("lp", "children", "vals"))
    check(np.array_equal(arrays["letter"], letter), "Alphabet mismatch")
    check(lp.shape == (26 ** 4,) and children.shape == (len(values), 26) and values.shape[1] == 3, "Scoring array shape")
    check(np.isfinite(lp).all() and np.isfinite(values).all(), "Non-finite scoring array")
    check(children.min() >= -1 and children.max() < len(children), "Trie index range")

    positive_checks = []
    null_checks = []
    rng = np.random.default_rng(202610011101)
    reals = {c["id"]: c for c in cases if c["kind"] == "real"}
    by_id = {c["id"]: c for c in cases}
    for c in cases:
        if c["kind"] in ("positive", "regression"):
            p = rng.permutation(8)
            m = int(rng.integers(3))
            mask = int(rng.integers(1, 255))
            pi = int(np.flatnonzero(np.all(p8 == p, axis=1))[0])
            key_id = pi * 768 + m * 256 + mask
            check(c["true_perm8"] == p.tolist() and c["true_middle"] == m and c["true_mask"] == mask and c["true_key"] == key_id, "Positive seed regeneration: " + c["id"])
            key = env["independent_key"](key_id)
            decoded = "".join(chr(int(x) + 97) for x in key[c["glyph"]])
            check(decoded == c["plaintext"], "Positive decryption: " + c["id"])
            inverse = {int(x): i for i, x in enumerate(key)}
            reglyph = [inverse[ord(x) - 97] for x in c["plaintext"]]
            check(reglyph == c["glyph"], "Positive encryption: " + c["id"])
            positive_checks.append({"case": c["id"], "key_id": key_id, "length": len(decoded), "passed": True})
        if c["kind"] == "null":
            seed = int(np.random.SeedSequence([202610011102, c["replicate"]]).generate_state(1, dtype=np.uint64)[0])
            check(c["seed"] == seed, "Null seed regeneration: " + c["id"])
            base = np.array(reals[c["source"]]["glyph"], np.int64)
            shuffled = env["euler_shuffle"](base, np.random.default_rng(seed))
            check(shuffled.tolist() == c["glyph"], "Null shuffle regeneration: " + c["id"])
            check(Counter(shuffled) == Counter(base), "Null unigram counts")
            check(Counter(zip(shuffled, shuffled[1:])) == Counter(zip(base, base[1:])), "Null directed bigram counts")
            check(shuffled[0] == base[0] and shuffled[-1] == base[-1], "Null endpoints")
            null_checks.append({"case": c["id"], "seed": seed, "length": len(shuffled), "regenerated_exactly": True, "glyph_counts_equal": True, "directed_bigram_counts_equal": True, "endpoints_equal": True})
    check(len(positive_checks) == 14 and len(null_checks) == 78, "Regeneration counts")
    check(all(by_id[f"hauer_real_pair_{i:02d}"]["seed"] == by_id[f"hart_real_pair_{i:02d}"]["seed"] for i in range(39)), "Paired seeds differ")

    word_checks = []
    for c in cases[:14] + cases[14:18]:
        for key_id in [0, c.get("true_key", 30965759)]:
            key = env["key_at"](key_id)
            check(np.array_equal(key, env["independent_key"](key_id)), "Independent decoder equality")
            text = key[c["glyph"]]
            forward = float(env["fast_word"](text, children, values))
            reference = float(env["ref_word"](text, children, values))
            check(forward == reference, "Word DP mismatch")
            ordered_c = float(env["char_score"](text, lp))
            _, vector_c, _ = env["ref_score"](text, (lp, children, values, letter))
            c_error = abs(ordered_c - vector_c)
            check(c_error < 1e-11, "Direct C mismatch")
            word_checks.append({"case": c["id"], "key_id": key_id, "length": len(text), "forward_word_score": forward, "independent_word_score": reference, "word_error": abs(forward - reference), "character_error": c_error, "passed": True})
    check(len(word_checks) == 36, "Word test count")

    # Bounded synthetic tie stress, not a full experiment. Empty dictionary
    # makes W=-8 and zero character model makes S=-4 for every key.
    glyph = np.zeros(87, np.int64)
    toy_lp = np.zeros(26 ** 4)
    toy_children = np.full((1, 26), -1, np.int64)
    toy_values = np.full((1, 3), -1e100)
    first = env["scan_block"](glyph, toy_lp, toy_children, toy_values, p8, q, letter, 0, 1, -1e100, -1)
    second = env["scan_block"](glyph, toy_lp, toy_children, toy_values, p8, q, letter, 1, 2, first[0], first[1])
    combined_ties = sorted(set(first[2].tolist() + second[2].tolist()))
    check(first[0] == second[0] == -4.0, "All-tie score")
    check(first[1] == second[1] == 0, "All-tie global minimum ID")
    check(combined_ties == list(range(1536)), "All ties preserved across blocks")
    check(len(first[4]) == len(second[4]) == 768, "Every tied key evaluated")

    report = {
        "status": "passed",
        "review_type": "independent bounded code/data review; reconstructed and rerun checks",
        "started_utc": started,
        "completed_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "elapsed_seconds": time.monotonic() - begin,
        "script_path": str(SCRIPT.relative_to(H)),
        "script_sha256": sha(SCRIPT),
        "protocol_sha256": protocol_sha,
        "python": sys.version,
        "numpy": np.__version__,
        "platform": platform.platform(),
        "frozen_dependencies": frozen_dependencies,
        "archive_matches": archive_matches,
        "engine_ast_checks": ast_checks,
        "shuffle_source_sha256": sha(shuffle_path),
        "input_checks": {"cases": len(cases), "unique_ids": len(by_id), "kinds": dict(Counter(c["kind"] for c in cases)), "all_glyph_lengths": 87, "all_plaintext_lengths": 87, "solver_fields": ["glyph", "id", "kind"], "solver_inputs_equal": True, "paired_seeds_equal": True},
        "scoring_arrays": {name: {"shape": list(arr.shape), "dtype": str(arr.dtype)} for name, arr in arrays.items()},
        "positive_regeneration": positive_checks,
        "null_regeneration": null_checks,
        "word_and_decoder_checks": word_checks,
        "word_checks_count": len(word_checks),
        "max_word_error": max(c["word_error"] for c in word_checks),
        "max_character_error": max(c["character_error"] for c in word_checks),
        "tie_stress": {"length": 87, "blocks": [[0, 1], [1, 2]], "keys_evaluated": len(first[4]) + len(second[4]), "score": float(first[0]), "winning_id": int(second[1]), "ties": len(combined_ties), "all_ids_0_through_1535_present": True, "passed": True},
        "blocking_correctness_bugs_found": [],
        "scope_limits": [
            "No full searches or full unpruned audits were performed by this script.",
            "Main verifier independently checks all saved C scores, but only sampled, winning and tied W scores; skipped-key verification relies on planned supplemental audits.",
            "Execution-stage ordering beyond the positive gate relies on orchestration.",
            "Per-group local maxima in stats columns 7 and 8 concern evaluated keys only, not all keys.",
            "Tie stress executes exact source bodies in Python and combines cross-block ties by the runner's union rule; it does not exercise checkpoint disk I/O.",
            "The review found no change to its earlier correctness findings."
        ],
    }
    # Recheck freeze and script identity before publishing the measured report.
    check(sha(protocol_path) == protocol_sha, "Protocol changed during review")
    check(all(sha(H / entry["path"]) == entry["sha256"] for entry in frozen_dependencies), "Frozen dependency changed during review")
    report_path = OUT / "report.json"
    report_path.write_text(json.dumps(report, sort_keys=True, indent=2) + "\n")
    print(json.dumps({"status": report["status"], "script": str(SCRIPT), "script_sha256": report["script_sha256"], "report": str(report_path), "report_sha256": sha(report_path), "elapsed_seconds": report["elapsed_seconds"], "positive_encryptions": len(positive_checks), "null_shuffles": len(null_checks), "word_checks": len(word_checks), "max_word_error": report["max_word_error"], "max_character_error": report["max_character_error"], "tie_stress_keys": len(combined_ties)}, sort_keys=True))


if __name__ == "__main__":
    main()
