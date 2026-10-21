"""Exact control_assignment body from implementation-readback-1 driver.py:152–168.
Its old G1 docstring is preserved; A3 calls it only during the authorized attempt.
"""
import hashlib
import itertools


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
