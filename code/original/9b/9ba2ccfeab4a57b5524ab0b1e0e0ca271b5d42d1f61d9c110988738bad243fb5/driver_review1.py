"""Only G0/G1 procedures for review. NO standalone worker/CLI or scoring path.

Requires a future admitted supervisor context (not available in this package).
ctx must own: manifest, root, guard(stage), save(name, value), event(value),
begin_case(id), end_case(id, commit). begin/end persist and enforce the same
original T0, 180s case and 5400s positive deadline through verified commit.
This is explicitly an integration blocker, not an implemented containment claim.
"""
import hashlib
import importlib
import itertools
import json
from pathlib import Path
import sys

from guard import pinned_bytes, require_stage
from reference import A25, decode, encode, route, table, undo_route, verify, require


def admission(ctx, stage):
    require_stage(ctx.manifest, stage)
    ctx.guard(stage)


def load_archived_structural(ctx):
    """Normal import, only after admission; never original main/run/evaluate.

    No build_model, WordSearch, WordScorer or merged-model construction. All
    transitive local source bytes must be pinned. No trusted-by-name reuse.
    """
    admission(ctx, "G0")
    modules = ("language", "wordscore_v3", "wordpolish_v3", "automata",
               "wordsearch_v4", "model_v5", "fraction_v6")
    for name in modules:
        pinned_bytes(ctx.root, ctx.manifest, "original/" + name + ".py")
        require(name not in sys.modules, "PRELOADED_MODULE:" + name)
    pinned_bytes(ctx.root, ctx.manifest, "original/data/english_model.npz")
    pinned_bytes(ctx.root, ctx.manifest, "original/dictionary/en-spelling.txt")
    directory = (Path(ctx.root) / "original").resolve()
    sys.dont_write_bytecode = True
    sys.path.insert(0, str(directory))
    try:
        original = importlib.import_module("fraction_v6")
        for name in modules:
            require(Path(sys.modules[name].__file__).resolve() == directory / (name + ".py"),
                    "UNEXPECTED_MODULE_ORIGIN:" + name)
        import numpy as np
        require(np.dtype("float64").itemsize == 8, "FLOAT64")
    finally:
        sys.path.remove(str(directory))
    return original, np


def archived_decode(original, np, glyphs, key, q):
    result = original.output_numeric(np.array(glyphs, dtype=np.int64),
                                     np.array(table(key), dtype=np.int64),
                                     np.array(q, dtype=np.int64), 5)
    return "".join(A25[int(x)] for x in result)


def reference_table_bank():
    bank = {}
    count = 0
    for sign, rot, arcs in itertools.product((1, -1), range(8), itertools.permutations(range(3))):
        for layout, missing in itertools.product(range(2), range(25)):
            key = dict(sign=sign, rot=rot, arcs=arcs, layout=layout, missing=missing)
            coords = table(key)
            count += 1
            code = tuple(tuple(pair) for pair in coords)
            if code not in bank:
                bank[code] = (coords, key)
    return list(bank.values()), count


def reference_route_bank():
    bank = {}
    count = 0
    for period, reset, inverse, reverse in itertools.product(range(1, 88), range(2), range(2), range(2)):
        key = dict(period=period, reset=reset, inverse=inverse, reverse=reverse)
        q = route(**key)
        count += 1
        if tuple(q) not in bank:
            bank[tuple(q)] = (q, key)
    return list(bank.values()), count


def run_g0(ctx):
    admission(ctx, "G0")
    # Future context refuses an existing completed or partial G0. No replay.
    ctx.event({"event": "G0_STARTED", "implementation_only": True})
    original, np = load_archived_structural(ctx)
    tt, td = original.tables("square")
    rr, rd = original.digit_routes(2)
    reference_tt, reference_td = reference_table_bank()
    reference_rr, reference_rd = reference_route_bank()
    require((len(tt), td, len(rr), rd) == (4800, 4800, 462, 696), "BANK_COUNTS")
    require((td, rd) == (reference_td, reference_rd), "DEFINITION_COUNTS")
    require(len(reference_tt) == len(tt) and len(reference_rr) == len(rr), "REFERENCE_COUNTS")
    for (a, ak), (b, bk) in zip(tt, reference_tt):
        require(a.dtype == np.dtype("int64") and a.tolist() == b and ak == bk, "TABLE_ORDER_OR_VALUES")
        occupied = [5 * pair[0] + pair[1] for pair in b]
        require(sorted(occupied) == [m for m in range(25) if m != bk["missing"]], "TABLE_INJECTION")
    for (a, ak), (b, bk) in zip(rr, reference_rr):
        require(a.dtype == np.dtype("int64") and a.tolist() == b and ak == bk, "ROUTE_ORDER_OR_VALUES")
    ctx.save("g0_banks.json", {"tables": reference_tt, "routes": reference_rr,
                              "table_definitions": td, "route_definitions": rd})
    glyphs = [i % 24 for i in range(87)]
    fixed = dict(sign=1, rot=0, arcs=(0, 1, 2), layout=0, missing=24)
    identity = route(1, 0, 0, 0)
    completed = 0
    for family, entries in (("tables", [(key, identity) for _, key in reference_tt]),
                            ("routes", [(fixed, q) for q, _ in reference_rr])):
        for index, (key, q) in enumerate(entries):
            ctx.guard("G0")
            plaintext = decode(glyphs, key, q)
            native = archived_decode(original, np, glyphs, key, q)
            inverse = verify(plaintext, glyphs, key, q, native)
            ctx.save("g0_" + family + "_" + str(index) + ".json",
                     {"implementation_only": True, "key": key, "q": q,
                      "glyphs": glyphs, "plaintext": plaintext, "inverse": inverse})
            completed += 1
    require(completed == 5262, "ROUNDTRIP_COUNT")
    q = route(5, 0, 0, 0)
    for missing in range(25):
        ctx.guard("G0")
        d = [0] * 174
        d[0], d[1] = divmod(missing, 5)
        e = [d[j] for j in q]
        plaintext = "".join(A25[5 * e[2 * i] + e[2 * i + 1]] for i in range(87))
        key = {**fixed, "missing": missing}
        refusal = encode(plaintext, key, q)
        expected = [i for i in range(87) if 5 * d[2 * i] + d[2 * i + 1] == missing]
        require(refusal["status"] == "OUTSIDE_DOMAIN" and
                refusal["missing_positions"] == expected, "INVALID_MISSING_ACCEPTED")
        ctx.save("g0_invalid_missing_" + str(missing) + ".json",
                 {"implementation_only": True, "key": key, "q": q,
                  "plaintext": plaintext, "refusal": refusal})
    # Fixture contents added by implementation review; only the 3 specified categories.
    for label, text, status in (("length86", "a" * 86, "LENGTH_OUTSIDE"),
                                ("length88", "a" * 88, "LENGTH_OUTSIDE"),
                                ("J87", "j" + "a" * 86, "ALPHABET_OUTSIDE")):
        refusal = encode(text, fixed, q)
        require(refusal["status"] == status, "INVALID_INPUT_ACCEPTED")
        ctx.save("g0_invalid_" + label + ".json",
                 {"implementation_only": True, "plaintext": text, "refusal": refusal})
    ctx.guard("G0")
    ctx.save("G0_verified_complete.json", {"status": "PASS", "roundtrips": 5262,
             "invalid_missing": 25, "invalid_input": 3, "score_calls": 0})
    return original, np


def control_assignment(case_id):
    """Compute only in a future G1. No assignments precomputed in this package."""
    def h(field, value):
        return hashlib.sha256(("202610160607|" + case_id + "|" + field + "|" + value).encode("utf-8")).hexdigest()
    fields = (("sign", (1, -1)), ("rot", tuple(range(8))),
              ("arcs", tuple(itertools.permutations(range(3)))), ("layout", (0, 1)))
    key, audit = {}, {}
    for field, choices in fields:
        def label(value):
            return ",".join(map(str, value)) if field == "arcs" else str(value)
        rows = [{"value": value, "sha256": h(field, label(value)), "original_order": i}
                for i, value in enumerate(choices)]
        key[field] = min(rows, key=lambda row: (row["sha256"], row["original_order"]))["value"]
        audit[field] = rows
    rows = [{"missing": m, "sha256": h("missing", str(m))} for m in range(25)]
    rows.sort(key=lambda row: (row["sha256"], row["missing"]))
    return key, [row["missing"] for row in rows], {**audit, "missing_order": rows}


def candidates(ctx):
    raw = pinned_bytes(ctx.root, ctx.manifest, "inputs/positive_source_prefixes.json")
    fresh = json.loads(raw)["new_candidates"]
    require([z["id"] for z in fresh] == ["fresh_" + str(i).zfill(2) for i in range(16)], "FRESH_IDS")
    params = list(itertools.product((5, 17), (0, 1), (0, 1), (0, 1)))
    answer = []
    for z, values in zip(fresh, params):
        text = z["plaintext"]
        require(hashlib.sha256(text.encode()).hexdigest() == z["plaintext_sha256"], "TEXT_SHA")
        answer.append({"id": z["id"], "plaintext": text, "regression": False,
                       "route": dict(zip(("period", "reset", "inverse", "reverse"), values))})
    old = json.loads(pinned_bytes(ctx.root, ctx.manifest, "original/round8/results/elgar/inputs.json"))["sources"]
    for index, case_id, values in ((0, "reg_march", (5, 0, 0, 0)),
                                   (1, "reg_caractacus", (17, 1, 1, 1))):
        answer.append({"id": case_id, "plaintext": old[index]["plaintext"], "regression": True,
                       "route": dict(zip(("period", "reset", "inverse", "reverse"), values))})
    return answer


def run_g1(ctx, original, np):
    admission(ctx, "G1")
    # Context must verify G0 commit/hash before authorizing this stage.
    records = []
    for candidate in candidates(ctx):
        case_id = candidate["id"]
        ctx.begin_case(case_id)
        ctx.guard("G1")
        key, missing_order, assignment_audit = control_assignment(case_id)
        q = route(**candidate["route"])
        text = candidate["plaintext"]
        domain = undo_route(text, q)
        record = {**candidate, "protocol_sha256": ctx.manifest["protocol_sha256"],
                  "plaintext_sha256": hashlib.sha256(text.encode()).hexdigest(),
                  "key_without_missing": key, "assignment_hashes": assignment_audit,
                  "missing_order": missing_order, "q": q, "domain": domain,
                  "stratum": [candidate["route"][f] for f in ("reset", "inverse", "reverse")]}
        if domain["status"] != "VALID_COORDINATES":
            record.update(status=domain["status"], selected_missing=None,
                          missing_dispositions=[{"missing": m, "reason": "not_evaluated_invalid_text"}
                                                for m in missing_order])
        else:
            available = domain["available_missing"]
            eligible = [m for m in missing_order if m in available]
            chosen = eligible[0] if eligible else None
            record["selected_missing"] = chosen
            record["missing_dispositions"] = [
                {"missing": m, "reason": "occupied" if m not in available else
                 ("selected" if m == chosen else "available_not_selected"),
                 "positions": [i for i, z in enumerate(domain["z"]) if z == m]}
                for m in missing_order]
            if chosen is None:
                record["status"] = "ROUTE_DOMAIN_OUTSIDE"
            else:
                full_key = {**key, "missing": chosen}
                encoded = encode(text, full_key, q)
                require(encoded["status"] == "ENCODED", "ENCODER_INCONSISTENT")
                glyphs = encoded["glyphs"]
                native = archived_decode(original, np, glyphs, full_key, q)
                record.update(key=full_key, encoded=encoded, glyphs=glyphs,
                              glyph_sha256=hashlib.sha256(bytes(glyphs)).hexdigest(),
                              inverse=verify(text, glyphs, full_key, q, native),
                              status="REPRESENTABLE")
        ctx.guard("G1")
        commit = ctx.save(case_id + ".json", record)
        ctx.end_case(case_id, commit)
        records.append(record)
    fresh = [z for z in records if not z["regression"]]
    good = [z for z in fresh if z["status"] == "REPRESENTABLE"]
    strata = [{"stratum": list(s), "success_ids": [z["id"] for z in good if z["stratum"] == list(s)]}
              for s in itertools.product((0, 1), repeat=3)]
    passed = len(good) >= 14 and all(row["success_ids"] for row in strata)
    ctx.guard("G1")
    return ctx.save("G1_checkpoint.json", {"status": "PASS" if passed else "G1_FAILED_STOP_VERSION",
                    "fresh_denominator": 16, "representable_fresh": len(good),
                    "strata": strata, "score_calls": 0, "next_stage": "STOP_FOR_READBACK",
                    "regressions": [{"id": z["id"], "status": z["status"]}
                                    for z in records if z["regression"]]})
