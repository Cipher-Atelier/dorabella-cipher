#!/usr/bin/env python3
"""Only four fixed synthetic87 scan_block benchmarks; no full search."""
import argparse, datetime, hashlib, importlib, json, os, pathlib, statistics, sys, time

RANGES = ((0, 4), (10000, 10004), (20000, 20004), (30000, 30004))
EXPECTED_INPUT_SHA = "10abe79f71717da2c8e1fa71e5b82b82fd72a17a721aaff37f909c37ab8c227a"

def sha_file(p):
    with pathlib.Path(p).open("rb") as f:
        return hashlib.file_digest(f, "sha256").hexdigest()

def utc():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()

def atomic_json(p, obj):
    tmp = p.with_suffix(p.suffix + ".tmp")
    tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=2, allow_nan=False) + "\n")
    os.replace(tmp, p)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--lab", required=True, type=pathlib.Path)
    ap.add_argument("--out", required=True, type=pathlib.Path)
    a = ap.parse_args()
    lab, out = a.lab.resolve(), a.out.resolve()
    out.mkdir(parents=True, exist_ok=True)
    report_path = out / "benchmark_report.json"
    if report_path.exists():
        raise FileExistsError("Use a new output directory; previous results are preserved.")
    sys.dont_write_bytecode = True
    # Fresh, external cache; no writes into archived code or old checkpoints.
    cache = out / ("jit_cache_" + str(time.time_ns()))
    os.environ["NUMBA_CACHE_DIR"] = str(cache)
    import numpy as np
    import numba
    frozen_path = lab / "round11/frozen_protocol.json"
    frozen = json.loads(frozen_path.read_text())
    dependency_checks = []
    for name, expected in frozen["hashes"].items():
        actual = sha_file(lab / name)
        dependency_checks.append(dict(path=str(lab / name), expected=expected, actual=actual))
        if actual != expected:
            raise RuntimeError("Frozen dependency mismatch: " + name)
    t = time.perf_counter()
    sys.path[:0] = [str(lab / "round11"), str(lab)]
    engine = importlib.import_module("engine")
    model = importlib.import_module("model_v5")
    word = importlib.import_module("wordpolish_v3")
    for mod, rel in ((engine, "round11/engine.py"), (model, "model_v5.py"),
                     (word, "wordpolish_v3.py")):
        if pathlib.Path(mod.__file__).resolve() != (lab / rel).resolve():
            raise RuntimeError("Unexpected imported module: " + str(mod.__file__))
    with np.load(lab / "round11/data/scoring.npz", allow_pickle=False) as d:
        lp, children, vals, letter = (d[k] for k in ("lp", "children", "vals", "letter"))
    setup_seconds = time.perf_counter() - t
    t = time.perf_counter()
    g = np.random.default_rng(1301).integers(0, 24, size=87, dtype=np.int64)
    generation_seconds = time.perf_counter() - t
    def arrsha(x):
        return hashlib.sha256(np.ascontiguousarray(x).tobytes()).hexdigest()
    if arrsha(g) != EXPECTED_INPUT_SHA:
        raise RuntimeError("The synthetic input differs from the agreed seed1301 vector.")
    inputs = dict(g=g, lp=lp, children=children, vals=vals,
                  p8=engine.P8, q=engine.Q, letter=letter)
    before_hashes = {k: arrsha(v) for k, v in inputs.items()}
    common = (g, lp, children, vals, engine.P8, engine.Q, letter)
    report = dict(
        status="running", started_utc=utc(), python=sys.version,
        numpy=np.__version__, numba=numba.__version__, lab=str(lab),
        script_sha256=sha_file(__file__), frozen_protocol_sha256=sha_file(frozen_path),
        frozen_dependencies=dependency_checks,
        imported_modules={m.__name__: dict(path=m.__file__, sha256=sha_file(m.__file__))
                          for m in (engine, model, word)},
        scoring_npz_sha256=sha_file(lab / "round11/data/scoring.npz"),
        input=dict(seed=1301, length=87, dtype=str(g.dtype),
                   sha256=arrsha(g), values=g.tolist(), generation_seconds=generation_seconds),
        arrays={k: dict(shape=list(v.shape), dtype=str(v.dtype), sha256=before_hashes[k])
                for k, v in inputs.items()},
        protocol=dict(
            ranges=[list(x) for x in RANGES], fresh_repetitions=3, conditional_repetitions=3,
            fresh_incumbent=-1e100, fresh_incumbent_id=-1,
            conditional_incumbent="same block's first fresh maximum; reset identically each repeat",
            per_block_warmups=1, kernel="unchanged round11.engine.scan_block",
            score="unchanged C + 0.5 W on all 87 synthetic symbols",
            timer="perf_counter_ns; only synchronous scan_block call, not I/O/checks/import/JIT",
            ties="engine: exact float64 equality, minimum canonical ID",
            compiled_once_explicitly=True, full_search=False, planned_inputs_for_scaling=94),
        counter_semantics=dict(
            source="round11/engine.py",
            W_full="stats[:,4] sums evaluated, incremented exactly after fast_word; also len(sparse_ids)",
            pruned_W="stats[:,5] sums 256-evaluated; C is still computed for every key",
            key_count="768 * (pstop-pstart)",
            W_upper_calls="3 * (pstop-pstart), derived from loop structure, not a returned counter",
            local_pm_max="not used: maxima over evaluated W values can be incomplete under pruning"),
        setup_seconds=setup_seconds, warmups=[], calls=[], summaries=[])
    atomic_json(out / "benchmark_protocol.json", report)
    atomic_json(report_path, report)
    signatures_before = [str(s) for s in engine.scan_block.signatures]
    signature = tuple(numba.typeof(x) for x in common + (0, 4, -1e100, -1))
    t = time.perf_counter()
    engine.scan_block.compile(signature)
    report["jit_compilation_seconds"] = time.perf_counter() - t
    report["signatures_before_compilation"] = signatures_before
    report["compiled_signature"] = str(signature)
    atomic_json(report_path, report)

    def call(start, stop, inc, inc_id, phase, repetition):
        # No output/work arrays or incumbents are reused; the kernel allocates its own work arrays.
        t = time.perf_counter_ns()
        result = engine.scan_block(*common, start, stop, float(inc), int(inc_id))
        elapsed_ns = time.perf_counter_ns() - t
        best, best_id, ties, stats, ids, cs, ws = result
        keys = (stop - start) * 768
        evaluated = int(stats[:, 4].sum())
        skipped = int(stats[:, 5].sum())
        assert evaluated == len(ids) == len(cs) == len(ws)
        assert evaluated + skipped == keys
        assert stats.shape == ((stop - start) * 3, 9)
        assert np.all(stats[:, 4] + stats[:, 5] == 256)
        assert np.all((ids >= start * 768) & (ids < stop * 768))
        stem = f"p{start:05d}_{stop:05d}_{phase}_{repetition}"
        output_arrays = dict(stats=stats, ids=ids, C=cs, W=ws, ties=ties)
        np.savez_compressed(out / (stem + ".npz"), **output_arrays)
        rec = dict(
            phase=phase, repetition=repetition, p8_start=start, p8_stop=stop,
            seconds=elapsed_ns / 1e9, elapsed_ns=elapsed_ns, keys=keys,
            keys_per_second=keys / (elapsed_ns / 1e9), C_evaluations=keys,
            W_full=evaluated, pruned_W=skipped,
            W_upper_calls_derived=(stop-start)*3,
            incoming_incumbent=float(inc), incoming_id=int(inc_id),
            maximum=float(best), maximum_id=int(best_id), exact_tie_ids=ties.tolist(),
            array_file=stem + ".npz", array_file_sha256=sha_file(out / (stem + ".npz")),
            array_sha256={k: arrsha(v) for k, v in output_arrays.items()})
        report["warmups" if phase == "warmup" else "calls"].append(rec)
        atomic_json(report_path, report)
        return rec

    for start, stop in RANGES:
        warm = call(start, stop, -1e100, -1, "warmup", 0)
        fresh = [call(start, stop, -1e100, -1, "fresh", i) for i in range(1, 4)]
        score, key_id = fresh[0]["maximum"], fresh[0]["maximum_id"]
        conditional = [call(start, stop, score, key_id, "conditional", i) for i in range(1, 4)]
        for rec in [warm] + fresh + conditional:
            assert rec["maximum"] == score and rec["maximum_id"] == key_id
        for group in (fresh, conditional):
            assert all(r["array_sha256"] == group[0]["array_sha256"] for r in group)
        row = dict(p8_start=start, p8_stop=stop, keys=3072, maximum=score, maximum_id=key_id)
        for label, group in (("fresh", fresh), ("conditional", conditional)):
            times = [r["seconds"] for r in group]
            row[label] = dict(times_seconds=times, median_seconds=statistics.median(times),
                              W_full=group[0]["W_full"], pruned_W=group[0]["pruned_W"])
        report["summaries"].append(row)
        atomic_json(report_path, report)
        print(json.dumps(row), flush=True)

    after_hashes = {k: arrsha(v) for k, v in inputs.items()}
    assert before_hashes == after_hashes
    for name, expected in frozen["hashes"].items():
        assert sha_file(lab / name) == expected, "Dependency changed: " + name
    ratios = [r["fresh"]["median_seconds"] * engine.NK / r["keys"]
              for r in report["summaries"]]
    report["naive_scaling_not_forecast"] = dict(
        family_keys=int(engine.NK), keys_per_call=3072, multiplier=engine.NK/3072,
        fresh_block_median_scaled_one_input_seconds=ratios,
        fresh_block_median_scaled_94_inputs_seconds=[t*94 for t in ratios],
        limitations=[
            "Only four predetermined blocks (12288 distinct keys) of one synthetic input.",
            "Fresh reset differs from an actual sequential full scan with evolving incumbent.",
            "Conditional repeats start with a known local optimum: not fresh-search timing.",
            "W counts and bound cost depend on key region, input, and incumbent.",
            "No full-search or 94-input timings measured; no preparation/checkpoint/JIT in scaling.",
            "Counts are measured; durations cannot be split into separate C/W/bound timings here."])
    report.update(status="complete", completed_utc=utc(),
                  arrays_unchanged=True, frozen_dependencies_unchanged=True,
                  measured_calls=len(report["calls"]), warmup_calls=len(report["warmups"]),
                  distinct_keys_in_sample=4*3072,
                  total_keys_in_measured_calls=sum(r["keys"] for r in report["calls"]),
                  full_search_started=False)
    atomic_json(report_path, report)
    print("COMPLETE:", report_path, flush=True)

if __name__ == "__main__":
    main()
