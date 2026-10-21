"""Independent, read-only integrity validation; no key search or frozen-code imports.

Run after extraction, after the positive gate, and after the full experiment:
    python code/audit_integrity.py
    python code/audit_integrity.py --require-complete
An optional --output PATH writes this helper's JSON report. With no --output,
the validator only reads files and prints a summary. It supports a fresh replay
tree without the historical source archive. Frozen positive truth is sufficient
there; source plaintext/scorer equality is additionally checked when available.
"""
from pathlib import Path
from collections import Counter
import argparse
import datetime
import hashlib
import itertools
import json
import math
import numpy as np

H = Path(__file__).resolve().parents[1]
EXPECTED_PROTOCOL = "ae5d77723a64e36ecef03edf596339b6da027173af0bc601df7fece0bb756996"
ALPHABET = "abcdefghiklmnopqrstuwxyz"
PERMS = list(itertools.permutations(range(3)))
NQ = 6 ** 8
NK = 16 * NQ


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text())


def independent_key(key_id):
    require(isinstance(key_id, int) and 0 <= key_id < NK, "Invalid key ID")
    pi, z = divmod(key_id, NQ)
    sign, shift = (1 if pi < 8 else -1), pi % 8
    return [ord(ALPHABET[3 * ((sign * o + shift) % 8)
                        + PERMS[(z // 6 ** o) % 6][c]]) - 97
            for o in range(8) for c in range(3)]


def independent_score(text, lp, children, vals):
    """Original-window-order C and independent endpoint-first word DP."""
    require(len(text) == 87, "Expected 87 decoded letters")
    char = 0.0
    for a, b, c, d in zip(text, text[1:], text[2:], text[3:]):
        char += float(lp[((a * 26 + b) * 26 + c) * 26 + d])
    char /= 84
    dp = [-1e100] * 88
    dp[0] = 0.0
    for end in range(1, 88):
        dp[end] = dp[end - 1] - 8.0
        for start in range(max(0, end - 24), end):
            node = 0
            for letter in text[start:end]:
                node = int(children[node, letter])
                if node < 0:
                    break
            if node < 0:
                continue
            word = float(vals[node, 0])
            if start == 0 and end < 87:
                word = max(word, float(vals[node, 2]))
            if end == 87 and start > 0:
                word = max(word, float(vals[node, 1]))
            dp[end] = max(dp[end], dp[start] + word)
    word = dp[87] / 87
    return char + 0.5 * word, char, word


def audit(require_complete=False):
    ph = sha(H / "protocol.json")
    require(ph == EXPECTED_PROTOCOL, "Protocol differs from independently reviewed freeze")
    require((H / "protocol.sha256").read_text().split()[0] == ph,
            "protocol.sha256 does not match protocol.json")
    protocol = read(H / "protocol.json")
    hashes = []
    for rel, expected in protocol["sha256"].items():
        actual = sha(H / rel)
        require(actual == expected, f"Frozen file changed: {rel}")
        hashes.append({"path": rel, "sha256": actual})
    cases = read(H / "data/search_inputs.json")
    by_id = {c["id"]: c for c in cases}
    require(len(cases) == len(by_id) == 94, "Expected 94 unique inputs")
    require(Counter(c["kind"] for c in cases) ==
            {"positive": 12, "regression": 2, "real": 2, "null": 78}, "Unexpected input kinds")
    truths = {c["id"]: c for c in read(H / "data/positive_truth.json")}
    positives = [c for c in cases if c["kind"] in ("positive", "regression")]
    require(set(truths) == {c["id"] for c in positives}, "Positive truth IDs mismatch")
    source_path = H / "source/dorabella_round13/data/cases.json"
    source = {c["id"]: c for c in read(source_path)} if source_path.exists() else None
    rng = np.random.default_rng(202610051340)
    for case in cases:
        cid, glyphs = case["id"], case["glyph"]
        require(len(glyphs) == 87 and all(isinstance(g, int) and 0 <= g < 24 for g in glyphs),
                f"Invalid glyph input: {cid}")
        if cid in truths:
            truth = truths[cid]
            require(len(truth["plaintext"]) == 87 and set(truth["plaintext"]) <= set(ALPHABET),
                    f"Invalid truth: {cid}")
            require(truth["true_key_id"] == int(rng.integers(NK)), f"Seeded key mismatch: {cid}")
            inverse = {letter: g for g, letter in enumerate(independent_key(truth["true_key_id"]))}
            require([inverse[ord(letter) - 97] for letter in truth["plaintext"]] == glyphs,
                    f"Seeded encryption mismatch: {cid}")
            if source is not None:
                require(truth["plaintext"] == source[cid]["plaintext"], f"Source plaintext changed: {cid}")
        if case["kind"] == "null":
            real = by_id[case["source"]]["glyph"]
            require(Counter(glyphs) == Counter(real)
                    and Counter(zip(glyphs, glyphs[1:])) == Counter(zip(real, real[1:]))
                    and glyphs[0] == real[0] and glyphs[-1] == real[-1], f"Invalid null: {cid}")
    with np.load(H / "data/scoring.npz", allow_pickle=False) as model:
        lp, children, vals = (model[k] for k in ("lp", "children", "vals"))
    require(np.isfinite(vals).all() and float(vals.max()) <= 0, "Invalid word-score values")
    old_model = H / "source/dorabella_round13/data/scoring.npz"
    if old_model.exists():
        require(sha(old_model) == sha(H / "data/scoring.npz"), "Archived scorer mismatch")
    for path in (H / "results").glob("*.json"):
        require(path.stem in by_id or path.name == "summary.json", f"Unrecognized result: {path.name}")
    if (H / "checkpoints").exists():
        for path in (H / "checkpoints").iterdir():
            require(path.is_dir() and path.name in by_id, f"Unrecognized checkpoint item: {path.name}")
    records, partial, total_blocks, max_error = [], [], 0, 0.0
    for case in cases:
        cid, glyphs = case["id"], case["glyph"]
        files = sorted((H / "checkpoints" / cid).glob("*.json"))
        result_path = H / "results" / (cid + ".json")
        if not files and not result_path.exists():
            continue
        require(len(files) <= 16, f"Too many checkpoint blocks: {cid}")
        cache = {}

        def check_score(key_id, expected_score):
            nonlocal max_error
            if key_id not in cache:
                key = independent_key(key_id)
                require(len(set(key)) == 24, f"Non-bijective key: {cid}")
                text = [key[g] for g in glyphs]
                cache[key_id] = independent_score(text, lp, children, vals), text
            got = cache[key_id][0][0]
            max_error = max(max_error, abs(got - expected_score))
            require(got == expected_score, f"Independent score mismatch: {cid}, key {key_id}")
            return cache[key_id]

        incumbent, ties, word_evaluations, blocks, block_hashes = -1e100, [], 0, [], []
        for pi, path in enumerate(files):
            block = read(path)
            require(path.stem == f"{pi:02d}" and block["pidx"] == pi,
                    f"Missing or reordered checkpoint: {cid}")
            require(block["protocol_sha256"] == ph and block["incoming"] == incumbent,
                    f"Checkpoint provenance/chain mismatch: {cid}/{pi}")
            require(block["keys"] == NQ and 0 <= block["word_evaluations"] <= NQ,
                    f"Invalid evaluation count: {cid}/{pi}")
            require(math.isfinite(block["score"]) and block["score"] >= incumbent,
                    f"Invalid block maximum: {cid}/{pi}")
            block_ties = block["exact_ties"]
            require(block_ties == sorted(set(block_ties))
                    and all(pi * NQ <= k < (pi + 1) * NQ for k in block_ties),
                    f"Invalid block tie IDs: {cid}/{pi}")
            if block_ties:
                require(block["key_id"] == min(block_ties), f"Noncanonical block key: {cid}/{pi}")
                for key_id in block_ties:
                    check_score(key_id, block["score"])
                computed = check_score(block["key_id"], block["score"])[0]
                require(computed[1] == block["C"] and computed[2] == block["W"],
                        f"Checkpoint components mismatch: {cid}/{pi}")
            else:
                require(block["key_id"] == -1 and block["score"] == incumbent,
                        f"Missing incumbent improvement ties: {cid}/{pi}")
            if block["score"] > incumbent:
                require(bool(block_ties), f"Improvement without key: {cid}/{pi}")
                incumbent, ties = block["score"], block_ties.copy()
            else:
                ties += block_ties
            word_evaluations += block["word_evaluations"]
            blocks.append(block)
            block_hashes.append({"path": str(path.relative_to(H)), "sha256": sha(path)})
        total_blocks += len(files)
        if not result_path.exists():
            partial.append({"id": cid, "checkpoint_count": len(files)})
            continue
        result = read(result_path)
        require(len(files) == 16, f"Final result lacks complete checkpoints: {cid}")
        require(result["id"] == cid and result["kind"] == case["kind"]
                and result["source"] == case.get("source") and result["protocol_sha256"] == ph,
                f"Result provenance mismatch: {cid}")
        require(result["score"] == incumbent and result["exact_ties"] == sorted(set(ties))
                and result["key_id"] == min(ties), f"Final maximum/tie union mismatch: {cid}")
        require(result["char_evaluations"] == NK and result["word_evaluations"] == word_evaluations
                and result["blocks"] == blocks, f"Final counters/embedded checkpoints mismatch: {cid}")
        key = independent_key(result["key_id"])
        components, decoded = check_score(result["key_id"], result["score"])
        require(result["key_ascii_0based"] == key
                and result["decoded"] == "".join(chr(a + 97) for a in decoded), f"Decoding mismatch: {cid}")
        inverse = {letter: g for g, letter in enumerate(key)}
        require([inverse[a] for a in decoded] == glyphs, f"Re-encryption mismatch: {cid}")
        if case["kind"] in ("real", "null"):
            require(len(ties) >= 2 and len(ties) % 2 == 0, f"Tie multiplicity invariant failed: {cid}")
        record = {"id": cid, "kind": case["kind"], "status": "passed", "result_sha256": sha(result_path),
                  "checkpoint_hashes": block_hashes, "checkpoint_count": 16,
                  "protocol_sha256": ph, "char_evaluations": NK, "word_evaluations": word_evaluations,
                  "S": components[0], "C": components[1], "W": components[2],
                  "key_id": result["key_id"], "final_tie_count": len(result["exact_ties"]),
                  "independent_scored_keys": len(cache), "decoded": result["decoded"],
                  "exact_tie_union_verified": True, "reencryption_verified": True}
        if cid in truths:
            truth = truths[cid]
            record.update(correct=sum(a == b for a, b in zip(result["decoded"], truth["plaintext"])),
                          true_key_among_ties=truth["true_key_id"] in result["exact_ties"])
        records.append(record)
    completed = {r["id"]: r for r in records}
    pos = [r for r in records if r["kind"] in ("positive", "regression")]
    exact = sum(r["correct"] == 87 for r in pos)
    letters = sum(r["correct"] for r in pos)
    gate = len(pos) == 14 and exact >= 12 and letters >= 1194
    require(not any(r["kind"] in ("real", "null") for r in records) or gate,
            "Real/control results exist without an independently passing positive gate")
    snapshot_path = H / "checks/results_verified.json"
    snapshot_hash, snapshot_count = None, 0
    if snapshot_path.exists():
        raw = snapshot_path.read_bytes()
        snapshot, snapshot_hash = json.loads(raw), hashlib.sha256(raw).hexdigest()
        seen = set()
        for row in snapshot["records"]:
            cid = row["id"]
            require(cid not in seen and cid in completed, "Invalid verified-results snapshot IDs")
            seen.add(cid)
            actual = completed[cid]
            for field in ("kind", "key_id", "decoded"):
                require(row[field] == actual[field], f"Verified snapshot differs: {cid}/{field}")
            require(row["ties"] == actual["final_tie_count"] and row["re_encryption"] is True,
                    f"Verified snapshot tie/roundtrip mismatch: {cid}")
            for field in ("S", "C", "W"):
                require(abs(row[field] - actual[field]) < 1e-11, f"Verified snapshot score mismatch: {cid}/{field}")
            if cid in truths:
                require(row["correct"] == actual["correct"]
                        and row["true_key_among_ties"] == actual["true_key_among_ties"],
                        f"Verified positive snapshot mismatch: {cid}")
        snapshot_count = len(seen)
        require(snapshot["verified_cases"] == snapshot_count, "Verified snapshot count mismatch")
    if require_complete:
        require(len(records) == 94 and not partial, "All 94 complete results are required")
        require(gate and snapshot_count == 94, "Complete current verification snapshot is required")
    return {"status": "passed", "reviewed_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "scope": "Frozen hash/input/checkpoint/result validation and independent scoring of saved keys; no key search",
            "protocol_sha256": ph, "frozen_hashes": hashes, "source_plaintexts_checked": source is not None,
            "source_scorer_checked": old_model.exists(), "completed_cases": len(records),
            "checkpoint_blocks_verified": total_blocks, "partial_cases": partial,
            "positive_cases_verified": len(pos), "positive_exact87": exact, "positive_correct_letters": letters,
            "sensitivity_gate_passed": gate, "max_independent_score_error": max_error,
            "verified_snapshot_sha256": snapshot_hash, "verified_snapshot_cases": snapshot_count,
            "required_complete": require_complete, "records": records,
            "limitations": ["Completeness of search and admissibility of pruning are separate from checkpoint integrity.",
                            "This validator does not execute the separate complete unpruned audits.",
                            "Run with numerical writers stopped for a final immutable audit; partial live snapshots can race."]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--require-complete", action="store_true", help="Require all 94 results and their verification snapshot")
    parser.add_argument("--output", type=Path, help="Optional explicit JSON report destination; otherwise read-only")
    args = parser.parse_args()
    result = audit(args.require_complete)
    if args.output is not None:
        args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({k: v for k, v in result.items() if k not in ("records", "frozen_hashes")}, indent=2))


if __name__ == "__main__":
    main()
