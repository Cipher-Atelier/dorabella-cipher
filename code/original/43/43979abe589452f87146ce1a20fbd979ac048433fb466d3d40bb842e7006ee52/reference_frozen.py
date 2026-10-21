"""Independent scalar square D/E, review-v1 §3. No calls at module import.

Not a solver. No normalisation, scoring, random generator or source imports.
All position arrays use zero-based indices. Original g=3*orientation+arc_index.
"""

A25 = "abcdefghiklmnopqrstuvwxyz"
N = 87


def require(condition, message):
    if not condition:
        raise ValueError(message)


def validate_key(key):
    require(set(key) == {"sign", "rot", "arcs", "layout", "missing"}, "KEY_FIELDS")
    require(type(key["sign"]) is int and key["sign"] in (1, -1), "SIGN")
    require(type(key["rot"]) is int and 0 <= key["rot"] < 8, "ROT")
    require(all(type(v) is int for v in key["arcs"]) and
            sorted(key["arcs"]) == [0, 1, 2], "ARCS")
    require(type(key["layout"]) is int and key["layout"] in (0, 1), "LAYOUT")
    require(type(key["missing"]) is int and 0 <= key["missing"] < 25, "MISSING")


def validate_q(q):
    require(len(q) == 174 and all(type(v) is int for v in q) and
            sorted(q) == list(range(174)), "NOT_A_PERMUTATION")


def route(period, reset, inverse, reverse):
    """Original 50–65, scalar construction; reverse values AFTER argsort."""
    require(type(period) is int and 1 <= period <= 87, "PERIOD")
    require(all(type(v) is int and v in (0, 1)
                for v in (reset, inverse, reverse)), "ROUTE_FLAGS")
    bounds = (0, 29, 60, 87) if reset else (0, 87)
    p = list(range(174))
    for lo, hi in zip(bounds[:-1], bounds[1:]):
        for first in range(lo, hi, period):
            width = min(period, hi - first)
            for i in range(width):
                for j in (0, 1):
                    p[2 * (first + i) + j] = 2 * first + j * width + i
    q = sorted(range(174), key=p.__getitem__) if inverse else p[:]
    if reverse:
        q = [2 * (86 - v // 2) + v % 2 for v in q]
    validate_q(q)
    return q


def table(key):
    """Formula §3; deliberately no NumPy or original table-bank call."""
    validate_key(key)
    result = []
    for glyph in range(24):
        u = (key["sign"] * (glyph // 3) + key["rot"]) % 8
        v = key["arcs"][glyph % 3]
        x = 3 * u + v if key["layout"] == 0 else 8 * v + u
        z = x + int(x >= key["missing"])
        result.append([z // 5, z % 5])
    return result


def decode(glyphs, key, q):
    validate_key(key)
    validate_q(q)
    require(len(glyphs) == N and all(type(g) is int and 0 <= g < 24
                                    for g in glyphs), "GLYPHS")
    cells = table(key)
    d = [digit for g in glyphs for digit in cells[g]]
    e = [d[j] for j in q]
    return "".join(A25[5 * e[2 * i] + e[2 * i + 1]] for i in range(N))


def undo_route(plaintext, q):
    validate_q(q)
    if not isinstance(plaintext, str) or len(plaintext) != N:
        return {"status": "LENGTH_OUTSIDE", "length": len(plaintext)
                if isinstance(plaintext, str) else None}
    invalid = [{"position": i, "character": ch} for i, ch in enumerate(plaintext)
               if ch not in A25]
    if invalid:
        return {"status": "ALPHABET_OUTSIDE", "invalid": invalid}
    e = []
    for ch in plaintext:
        y = A25.index(ch)
        e.extend((y // 5, y % 5))
    d = [None] * 174
    for j, position in enumerate(q):
        d[position] = e[j]
    z = [5 * d[2 * i] + d[2 * i + 1] for i in range(N)]
    return {"status": "VALID_COORDINATES", "e": e, "d": d, "z": z,
            "available_missing": [m for m in range(25) if m not in z]}


def encode(plaintext, key, q):
    """Partial inverse. Refusal never retries a key, route or input."""
    validate_key(key)
    record = undo_route(plaintext, q)
    if record["status"] != "VALID_COORDINATES":
        return record
    bad = [i for i, z in enumerate(record["z"]) if z == key["missing"]]
    if bad:
        return {**record, "status": "OUTSIDE_DOMAIN", "missing_positions": bad}
    inverse_arcs = {v: c for c, v in enumerate(key["arcs"])}
    glyphs = []
    for z in record["z"]:
        x = z - int(z > key["missing"])
        if key["layout"] == 0:
            u, v = x // 3, x % 3
        else:
            u, v = x % 8, x // 8
        o = (key["sign"] * (u - key["rot"])) % 8
        glyphs.append(3 * o + inverse_arcs[v])
    return {**record, "status": "ENCODED", "glyphs": glyphs}


def verify(plaintext, glyphs, key, q, archived_plaintext):
    """Report every position; original D is supplied separately by the driver."""
    decoded = decode(glyphs, key, q)
    encoded = encode(plaintext, key, q)
    reencoded = encode(decoded, key, q)
    require(encoded["status"] == reencoded["status"] == "ENCODED", "INVERSE_DOMAIN")
    rows = [{"position": i, "plaintext": plaintext[i], "decoded": decoded[i],
             "archived_decoded": archived_plaintext[i], "glyph": glyphs[i],
             "encoded_glyph": encoded["glyphs"][i],
             "reencoded_glyph": reencoded["glyphs"][i],
             "ok": plaintext[i] == decoded[i] == archived_plaintext[i] and
                   glyphs[i] == encoded["glyphs"][i] == reencoded["glyphs"][i]}
            for i in range(N)]
    require(all(row["ok"] for row in rows), "INVERSE_MISMATCH")
    return {"status": "VERIFIED", "verified_positions": 87, "positions": rows,
            "decoded": decoded, "archived_decoded": archived_plaintext,
            "reencoded_glyphs": reencoded["glyphs"]}
