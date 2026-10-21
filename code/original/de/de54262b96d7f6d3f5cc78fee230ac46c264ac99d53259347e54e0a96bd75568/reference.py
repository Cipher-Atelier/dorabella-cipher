"""Own finite reference: raw sequential fields and membership-driven segmentation.
No external modules. FindWords is a literal control-flow reference, NOT an
independent theorem or proof of Perl equivalence. Hand-written fixtures anchor it.
"""
import re


def fields_from_raw(raw):
    # Separate token operations from the adapter's regular-expression parser.
    line = raw.rstrip(b' \t\r\n\v\f')
    parts = [x.translate(None, b' ') for x in line.split(b'\t') if x.translate(None, b' ')]
    if len(parts) < 3 or parts[0] not in (b'1', b'2', b'3'):
        raise ValueError('REFERENCE_FORMAT')
    return int(parts[0]), parts[1], parts[2:]


def find_words_reference(text, member, maxlen, tick=lambda: None, trace=None):
    tick()
    if len(text) > 87 or not 1 <= maxlen <= 46:
        raise ValueError('SEGMENTATION_BOUND')
    if text in (b'', b'0'):
        return text
    def ask(word):
        result = member(word)
        if trace is not None:
            trace.append([word.decode('ascii'), bool(result)])
            if len(trace) > 100000:
                raise ValueError('TRACE_BOUND')
        return result
    if ask(text):
        return text
    if not text.strip(b' \t\r\n\v\f'):
        return text
    for length in range(maxlen, 0, -1):
        for offset in range(len(text) - length + 1):
            tick()
            word = text[offset:offset + length]
            if not ask(word):
                continue
            if offset == 0:
                result = word + b' ' + find_words_reference(text[length:], member, maxlen, tick, trace)
            elif offset + length == len(text):
                result = find_words_reference(text[:offset], member, maxlen, tick, trace) + b' ' + word
            else:
                result = (find_words_reference(text[:offset], member, maxlen, tick, trace) + b' ' + word
                          + b' ' + find_words_reference(text[offset + length:], member, maxlen, tick, trace))
            return re.sub(rb'\s+', b' ', result)
    return text
