"""Own read-only patlst API. Not a Perl facade, numeric LM or solver.

Caller must authenticate index/source against the frozen SHA256 before opening.
Scope: validated ASCII, -n only, original orders folded into order 1.
"""
from collections import OrderedDict
from pathlib import Path
import re
import sqlite3
import sys

WS = b' \t\n\r\v\f'
TABS = re.compile(rb'\t+')
BAD = re.compile(rb'[^\x09\x0a\x0b\x0c\x0d\x20-\x7e]')


class CompactPatList:
    def __init__(self, index, source, tick=lambda: None):
        self.tick = tick
        self.db = sqlite3.connect(Path(index).resolve().as_uri() + '?mode=ro', timeout=0)
        self.db.execute('PRAGMA query_only=ON')
        self.db.execute('PRAGMA cache_size=-4096')
        self.db.execute('PRAGMA mmap_size=0')
        self.db.set_progress_handler(self._progress, 10000)
        self.source = open(source, 'rb')
        self.source_size = self.source.seek(0, 2)
        self.maxlen = int(self.db.execute("SELECT value FROM metadata WHERE key='maxlen'").fetchone()[0])
        if not 1 <= self.maxlen <= 46:
            raise ValueError('MAXLEN_DOMAIN')
        self.cache = OrderedDict()
        self.word_cache = OrderedDict()
        self.cache_bytes = 0
        self.stats = dict(list_calls=0, list_hits=0, list_misses=0, evictions=0,
                          peak_cache_bytes=0, rows_read=0, candidates_read=0,
                          word_calls=0, word_hits=0, word_queries=0)

    def _progress(self):
        self.tick()
        return 0

    @staticmethod
    def _bytes(value, cap):
        if not isinstance(value, bytes) or len(value) > cap or BAD.search(value):
            raise ValueError('BYTE_DOMAIN')

    def candidates(self, pattern, order=1):
        self.tick()
        self._bytes(pattern, 46)
        if type(order) is not int or order not in (1, 2, 3):
            raise ValueError('ORDER_DOMAIN')
        self.stats['list_calls'] += 1
        # -n leaves higher-order hashes empty. Missing is None, not empty list.
        if order != 1:
            return None
        if pattern in self.cache:
            self.stats['list_hits'] += 1
            values, size = self.cache.pop(pattern)
            self.cache[pattern] = (values, size)
            return None if values is None else list(values)
        self.stats['list_misses'] += 1
        result = []
        previous = 0
        for seq, original_order, p, offset, nr, count, longest in self.db.execute(
                'SELECT seq, original_order, pattern, offset, raw_bytes, count, longest '
                'FROM segments WHERE pattern=? ORDER BY seq', (pattern,)):
            self.tick()
            if not (previous < seq <= 7548932 and 0 <= offset and 0 < nr <= 118052
                    and offset + nr <= self.source_size):
                raise ValueError('SEGMENT_DOMAIN')
            previous = seq
            self.source.seek(offset)
            raw = self.source.read(nr)
            if len(raw) != nr or BAD.search(raw):
                raise ValueError('SEGMENT_BYTES')
            fields = TABS.split(raw.rstrip(WS).replace(b' ', b''))
            if len(fields) < 3 or fields[0] not in (b'1', b'2', b'3'):
                raise ValueError('SEGMENT_FIELDS')
            values = fields[2:]
            if (int(fields[0]), fields[1], len(values), max(map(len, values))) != (
                    original_order, p, count, longest) or any(not v for v in values):
                raise ValueError('SEGMENT_METADATA')
            if len(result) + len(values) > 63911:
                raise ValueError('CANDIDATE_BOUND')
            result.extend(values)
            self.stats['rows_read'] += 1
            self.stats['candidates_read'] += len(values)
        stored = tuple(result) if previous else None
        size = sys.getsizeof(pattern) + sys.getsizeof(stored)
        if stored is not None:
            size += sum(sys.getsizeof(x) for x in stored)
        # Deterministic bounded LRU. Never truncates values; copies isolate callers.
        if size <= 8 * 1024**2:
            while self.cache and (len(self.cache) >= 2 or self.cache_bytes + size > 8 * 1024**2):
                _, (_, removed_size) = self.cache.popitem(last=False)
                self.cache_bytes -= removed_size
                self.stats['evictions'] += 1
            self.cache[pattern] = (stored, size)
            self.cache_bytes += size
            self.stats['peak_cache_bytes'] = max(self.stats['peak_cache_bytes'], self.cache_bytes)
        return None if stored is None else list(stored)

    def is_word(self, word):
        self.tick()
        self._bytes(word, 87)
        self.stats['word_calls'] += 1
        if self.stats['word_calls'] > 100000:
            raise ValueError('WORD_CALL_BOUND')
        if word in self.word_cache:
            self.stats['word_hits'] += 1
            value = self.word_cache.pop(word)
            self.word_cache[word] = value
            return value
        self.stats['word_queries'] += 1
        value = self.db.execute('SELECT 1 FROM words WHERE word=?', (word,)).fetchone() is not None
        if len(self.word_cache) == 1024:
            self.word_cache.popitem(last=False)
        self.word_cache[word] = value
        return value

    def close(self):
        self.source.close()
        self.db.close()

