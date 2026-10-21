"""Structurally different block implementation; shares the specified mechanism.

No q-index formula or algebraic glyph inverse is used. This is independent
code organisation, not an independent historical source or common-error proof.
"""
A25 = 'abcdefghiklmnopqrstuvwxyz'


def coordinate_rows(key):
    occupied = list(range(25))
    occupied.remove(key['missing'])
    rows = []
    for orientation in range(8):
        transformed = (key['sign'] * orientation + key['rot']) % 8
        for arc_index in range(3):
            arc = key['arcs'][arc_index]
            rank = 3 * transformed + arc if key['layout'] == 0 else 8 * arc + transformed
            rows.append(list(divmod(occupied[rank], 5)))
    return rows


def reverse_pairs(values):
    answer = []
    for i in range(86, -1, -1):
        answer.extend(values[2 * i:2 * i + 2])
    return answer


def rearrange_blocks(values, period, reset, split_to_columns):
    """All blocks are partitioned at original0/29/60/87, even after reversal."""
    answer = []
    bounds = [0, 29, 60, 87] if reset else [0, 87]
    for lo, hi in zip(bounds[:-1], bounds[1:]):
        for start in range(lo, hi, period):
            block = values[2 * start:2 * min(start + period, hi)]
            if split_to_columns:
                answer.extend(block[0::2] + block[1::2])
            else:
                width = len(block) // 2
                for left, right in zip(block[:width], block[width:]):
                    answer.extend((left, right))
    return answer


def forward_digits(values, route):
    working = reverse_pairs(values) if route['reverse'] else values[:]
    return rearrange_blocks(working, route['period'], route['reset'], route['inverse'] == 1)


def backward_digits(values, route):
    working = rearrange_blocks(values, route['period'], route['reset'], route['inverse'] == 0)
    return reverse_pairs(working) if route['reverse'] else working


def decode(glyphs, key, route):
    rows = coordinate_rows(key)
    digits = [digit for glyph in glyphs for digit in rows[glyph]]
    output = forward_digits(digits, route)
    return ''.join(A25[5 * output[2 * i] + output[2 * i + 1]] for i in range(87))


def encode(plaintext, key, route):
    if len(plaintext) != 87:
        return {'status': 'LENGTH_OUTSIDE'}
    if any(ch not in A25 for ch in plaintext):
        return {'status': 'ALPHABET_OUTSIDE'}
    output = [digit for ch in plaintext for digit in divmod(A25.index(ch), 5)]
    original = backward_digits(output, route)
    inverse_table = {tuple(pair): glyph for glyph, pair in enumerate(coordinate_rows(key))}
    bad = [i for i in range(87) if tuple(original[2 * i:2 * i + 2]) not in inverse_table]
    if bad:
        return {'status': 'OUTSIDE_DOMAIN', 'missing_positions': bad}
    return {'status': 'ENCODED',
            'glyphs': [inverse_table[tuple(original[2 * i:2 * i + 2])] for i in range(87)]}
