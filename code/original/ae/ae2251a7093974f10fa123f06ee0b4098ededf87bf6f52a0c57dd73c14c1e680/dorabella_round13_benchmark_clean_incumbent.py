#!/usr/bin/env python3
"""Four fixed synthetic87 scan_block microbenchmarks; no full search.
Run with the restored, unchanged round10 + round11 laboratory.
All timings cover exactly one scan_block call, not serialization.
"""
import argparse
import hashlib
import importlib
import inspect
import json
import os
from pathlib import Path
import platform
import statistics
import sys
import time
from datetime import datetime, timezone

RANGES = ((0, 4), (10000, 10004), (20000, 20004), (30000, 30004))
REPEATS = 3
EXPECTED_SYNTHETIC_SHA = "10abe79f71717da2c8e1fa71e5b82b82fd72a17a721aaff37f909c37ab8c227a"

def sha(path):
    with Path(path).open("rb") as f:
        return hashlib.file_digest(f, "sha256").hexdigest()

def write_json(path, value):
    path = Path(path)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    tmp.replace(path)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--lab", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    lab, out = args.lab.resolve(), args.out.resolve()
    out.mkdir(parents=True, exist_ok=True)
    report_path = out / "benchmark_report.json"
    if report_path.exists():
        raise RuntimeError("Existing report is preserved; select a new --out directory.")
    lock = out / "benchmark.running"
    fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    os.write(fd, str(os.getpid()).encode("ascii"))
    os.close(fd)
    try:
        sys.dont_write_bytecode = True
        os.environ["NUMBA_CACHE_DIR"] = str(out / "numba_cache")
        sys.path.insert(0, str(lab / "round11"))
        sys.path.insert(1, str(lab))
        import numpy as np
        import numba
        engine = importlib.import_module("engine")
        model = importlib.import_module("model_v5")
        word = importlib.import_module("wordpolish_v3")
        assert Path(engine.__file__).resolve() == lab / "round11/engine.py"
        assert Path(model.__file__).resolve() == lab / "model_v5.py"
        assert Path(word.__file__).resolve() == lab / "wordpolish_v3.py"
        frozen_path = lab / "round11/frozen_protocol.json"
        frozen = json.loads(frozen_path.read_text())
        checked = {}
        for rel, expected in frozen["hashes"].items():
            actual = sha(lab / rel)
            checked[rel] = {"sha256": actual, "expected": expected, "match": actual == expected}
        assert all(x["match"] for x in checked.values()), "Frozen dependency hash mismatch"
        scoring = lab / "round11/data/scoring.npz"
        with np.load(scoring, allow_pickle=False) as d:
            lp, ch, vals, letter = (d[k].copy() for k in ("lp", "children", "vals", "letter"))
        g = np.random.default_rng(1301).integers(0, 24, size=87, dtype=np.int64)
        assert hashlib.sha256(g.tobytes()).hexdigest() == EXPECTED_SYNTHETIC_SHA
        array_inputs = {"g": g, "lp": lp, "children": ch, "vals": vals,
                        "letter": letter, "P8": engine.P8, "Q": engine.Q}
        def input_hashes():
            return {k: hashlib.sha256(v.tobytes()).hexdigest() for k, v in array_inputs.items()}
        before_arrays = input_hashes()
        np.save(out / "synthetic87.npy", g, allow_pickle=False)
        source = inspect.getsource(engine.scan_block.py_func)
        (out / "scan_block_source.txt").write_text(source, encoding="utf-8")
        assert "w=fast_word(buf,children,vals);s=cs[b]+.5*w;evaluated+=1" in source
        assert "stats[row,4]=evaluated;stats[row,5]=256-evaluated" in source
        protocol = {
            "registered_at_utc": datetime.now(timezone.utc).isoformat(),
            "script_sha256": sha(__file__),
            "seed": 1301, "input_length": 87, "dtype": "int64",
            "input_sha256": EXPECTED_SYNTHETIC_SHA, "synthetic_glyphs": g.tolist(),
            "ranges_P8_half_open": RANGES, "repeats_per_mode": REPEATS,
            "keys_per_P8": 768, "keys_per_block": 3072,
            "fresh": {"incumbent": -1e100, "incumbent_id": -1,
                      "reset": "Scalar arguments reset each call; scan_block allocates scratch/output arrays internally."},
            "conditional": "All three calls start from the exact S and ID of fresh repeat 1 of this SAME block. No carry between blocks.",
            "warmup": "Explicit signature compilation/cache load once, then one unmeasured fresh scan_block warmup on each fixed block.",
            "timing": "time.perf_counter_ns around scan_block only. No generation, hashes, result validation, disk I/O or compilation inside timed region.",
            "counter_semantics": {
                "complete_W": "sum(stats[:,4]); evaluated increments once immediately after each fast_word call",
                "W_pruned": "sum(stats[:,5]); each row is 256 - evaluated",
                "C_evaluated": "All 256 masks per (P8,m); exactly 3072 keys per call",
                "W_upper_evaluations": "One ambiguous_word call per (P8,m); exactly 12 per call",
                "checks": "complete_W equals len(sparse_ids),len(sparse_c),len(sparse_w); complete_W+W_pruned=3072"
            },
            "maximum_semantics": "Returned best S/ID is max(incoming incumbent, evaluated candidates). Fresh yields exact block maximum under unchanged pruning rule. Conditional carries that same known maximum. stats[:,7:9] are only evaluated-subset local maxima and are not treated as true sub-block maxima.",
            "tie_rule": "Unchanged engine: strict greater float64 score; exactly equal score chooses smallest canonical ID.",
            "no_full_search": True, "no_Dorabella_used": True,
        }
        write_json(out / "benchmark_protocol.json", protocol)
        report = {
            "status": "running",
            "started_at_utc": datetime.now(timezone.utc).isoformat(),
            "lab": str(lab), "script": str(Path(__file__).resolve()),
            "script_sha256": sha(__file__),
            "environment": {"python": sys.version, "platform": platform.platform(),
                            "numpy": np.__version__, "numba": numba.__version__,
                            "cpu_count": os.cpu_count(), "pid": os.getpid(),
                            "clock": vars(time.get_clock_info("perf_counter"))},
            "modules": {m.__name__: {"path": m.__file__, "sha256": sha(m.__file__)}
                        for m in (engine, model, word)},
            "scoring": {"path": str(scoring), "sha256": sha(scoring)},
            "frozen_dependencies": checked,
            "protocol": protocol, "input_hashes_before": before_arrays,
            "warmups": [], "calls": [], "summary": [],
            "limitations": [
                "Only four fixed blocks and one uniform-random synthetic87 input.",
                "Timings include both C and bound work plus the W evaluations actually needed, not full W for every key.",
                "Conditional measurements are repeat evaluations with an already known block maximum, not fresh searches.",
                "No decomposition of wall time among C, upper bound and W; only total scan_block time and code-derived operation counts.",
                "No full-family or 94-input run; no correctness audit repeated beyond counter consistency, hashes and repeated outputs.",
                "No claim about unknown true local maxima in pruned per-(P8,m) rows."
            ],
        }
        compile_args = (g, lp, ch, vals, engine.P8, engine.Q, letter, 0, 4, -1e100, -1)
        sig = tuple(numba.typeof(x) for x in compile_args)
        report["signatures_before_compile"] = [str(s) for s in engine.scan_block.signatures]
        t0 = time.perf_counter_ns()
        engine.scan_block.compile(sig)
        report["signature_compile_or_cache_load_seconds"] = (time.perf_counter_ns() - t0) / 1e9
        report["compiled_signature"] = str(sig)
        write_json(report_path, report)

        def do_call(start, stop, incumbent, incumbent_id, mode, repeat):
            t0 = time.perf_counter_ns()
            result = engine.scan_block(g, lp, ch, vals, engine.P8, engine.Q, letter,
                                       start, stop, float(incumbent), int(incumbent_id))
            seconds = (time.perf_counter_ns() - t0) / 1e9
            best, bestid, ties, stats, ids, cc, ww = result
            nkeys = (stop - start) * 768
            neval = int(stats[:, 4].sum())
            nskip = int(stats[:, 5].sum())
            assert np.all(stats[:, 4] >= 0) and np.all(stats[:, 5] >= 0)
            assert np.all(stats[:, 4] + stats[:, 5] == 256)
            assert neval == len(ids) == len(cc) == len(ww)
            assert neval + nskip == nkeys
            stem = f"P8_{start:05d}_{stop:05d}_{mode}_{repeat}"
            raw = out / (stem + ".npz")
            np.savez_compressed(raw, ties=ties, stats=stats,
                                evaluated_key_ids=ids, C=cc, W=ww)
            output_hashes = {name: hashlib.sha256(a.tobytes()).hexdigest()
                             for name, a in zip(("ties", "stats", "ids", "C", "W"),
                                               (ties, stats, ids, cc, ww))}
            return {
                "P8_start": start, "P8_stop": stop, "mode": mode, "repeat": repeat,
                "seconds": seconds, "keys": nkeys, "keys_per_second": nkeys/seconds,
                "incoming_incumbent": float(incumbent), "incoming_incumbent_id": int(incumbent_id),
                "complete_W": neval, "W_pruned": nskip,
                "C_evaluated": nkeys, "W_upper_evaluations": (stop-start)*3,
                "best_S": float(best), "best_ID": int(bestid),
                "exact_tie_ids_returned": ties.tolist(),
                "counter_consistency_passed": True,
                "returned_arrays_sha256": output_hashes,
                "raw_output_file": raw.name, "raw_output_sha256": sha(raw),
                "measured_at_utc": datetime.now(timezone.utc).isoformat(),
            }

        for start, stop in RANGES:
            warm = do_call(start, stop, -1e100, -1, "warmup_excluded", 0)
            report["warmups"].append(warm)
            write_json(report_path, report)
            clean = []
            for rep in range(1, REPEATS + 1):
                rec = do_call(start, stop, -1e100, -1, "fresh", rep)
                clean.append(rec); report["calls"].append(rec)
                write_json(report_path, report)
            incumbent, incumbent_id = clean[0]["best_S"], clean[0]["best_ID"]
            conditional = []
            for rep in range(1, REPEATS + 1):
                rec = do_call(start, stop, incumbent, incumbent_id, "conditional", rep)
                conditional.append(rec); report["calls"].append(rec)
                write_json(report_path, report)
            assert all(r["returned_arrays_sha256"] == clean[0]["returned_arrays_sha256"]
                       for r in clean), "Fresh repetitions differ"
            assert all(r["returned_arrays_sha256"] == conditional[0]["returned_arrays_sha256"]
                       for r in conditional), "Conditional repetitions differ"
            assert all((r["best_S"], r["best_ID"]) == (incumbent, incumbent_id)
                       for r in clean + conditional + [warm])
            summary = {"P8_range": [start, stop], "keys": 3072,
                       "best_S": incumbent, "best_ID": incumbent_id}
            for name, records in (("fresh", clean), ("conditional", conditional)):
                times = [r["seconds"] for r in records]
                summary[name] = {"seconds_all": times, "seconds_median": statistics.median(times),
                                 "seconds_min": min(times), "seconds_max": max(times),
                                 "complete_W": records[0]["complete_W"],
                                 "W_pruned": records[0]["W_pruned"],
                                 "keys_per_second_at_median": 3072/statistics.median(times)}
            report["summary"].append(summary)
            write_json(report_path, report)
            print(json.dumps(summary), flush=True)

        after_arrays = input_hashes()
        report["input_hashes_after"] = after_arrays
        assert before_arrays == after_arrays, "Input array mutated"
        report["input_arrays_unchanged"] = True
        assert all(sha(lab/rel) == rec["sha256"] for rel, rec in checked.items())
        report["frozen_dependencies_unchanged_after"] = True
        block_medians = [r["fresh"]["seconds_median"] for r in report["summary"]]
        multiplier = engine.NK / 3072
        one = statistics.mean(block_medians) * multiplier
        report["arithmetic_scaling_not_runtime_prediction"] = {
            "basis": "Mean of four fresh-block median wall times, each block independently starts at -1e100",
            "total_keys_in_family": engine.NK, "blocks_equivalent": multiplier,
            "planned_inputs": 94,
            "one_input_seconds": one, "94_inputs_seconds": 94*one,
            "one_input_range_from_slowest_fastest_block_seconds":
                [min(block_medians)*multiplier, max(block_medians)*multiplier],
            "94_inputs_range_from_slowest_fastest_block_seconds":
                [94*min(block_medians)*multiplier, 94*max(block_medians)*multiplier],
            "is_confidence_interval": False,
            "exclusions": "Compilation, setup, checkpoint I/O, different inputs, unknown W pruning load, effects of a running incumbent across full search."
        }
        report["measured_calls"] = len(report["calls"])
        report["warmup_calls_excluded"] = len(report["warmups"])
        report["timed_keys_including_repeats"] = sum(r["keys"] for r in report["calls"])
        report["distinct_keys_benchmarked"] = 4*3072
        report["status"] = "completed"
        report["completed_at_utc"] = datetime.now(timezone.utc).isoformat()
        write_json(report_path, report)
        print("REPORT", report_path, flush=True)
    finally:
        lock.unlink(missing_ok=True)

if __name__ == "__main__":
    main()
