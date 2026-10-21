# Reproduce round6

Read `README_ROUND6_RU.md` before interpreting any scores or candidate strings.
No candidate in this archive is an established decipherment of Dorabella.

## Requirements

Python 3.13.5 was used. A virtual environment is recommended.

```bash
pip install -r requirements_round6.txt
export OPENBLAS_NUM_THREADS=1
export OMP_NUM_THREADS=1
```

`export` is shell-specific; set equivalent environment variables on Windows.
The language models and prior input fixtures are included. The TextBlob dictionary
and Lee Corpus are taken from the pinned installed packages when needed.
No whole new historical books were added or used to train the model in round6.

## Verify preserved results without repeating the entire search

```bash
python checks_v6.py --complete --exhaustive
python summarize_v6.py
python make_report_v6.py
```

These commands verify frozen algorithm/model/dictionary hashes, transformations,
keys, candidate scores, global consistency and completeness of the actual trial
sets. The optional old-archive byte comparison runs when the old ZIP is present.
It is not necessary to have the old ZIP to inspect the included old files.
The report is written beside the scripts by default. To change its location,
use `python make_report_v6.py --journal-output /path/to/report.md`.

## Re-run the actual trial sets

The scripts skip completed records. Preserve the supplied results before
removing files. To recalculate a branch from scratch, rename its directory
under `results/v6`, then run that script. Some later branches depend on earlier
branch manifests; use the order below. Do not mix altered code or models with
results marked as belonging to a frozen protocol.

```bash
python whole24_v6.py --mode all --workers 4
python routes_v6.py --mode all --workers 4
python localrules_v6.py --mode all --workers 2
python relax_v6.py --mode real --workers 2
python fraction_v6.py --workers 2
python homophonic_v6.py --mode all --workers 2
python homophonic_emission_v6.py --mode all --workers 2
python periodic_v6.py --mode all --workers 2
python header_v6.py
python merged_masc_v6.py
python keyword_tables_v6.py
python routes_wordall_v6.py --workers 4
python checks_v6.py --complete --exhaustive
python summarize_v6.py
python make_report_v6.py
```

**Do not replace `relax --mode real` with `--mode all` when reproducing the
reported trial count.** Its 38 null inputs were constructed but not executed;
there is no null calibration for that branch in this report.

The every-route word-aware extension includes only two real transcriptions and
one deliberately selected old failed regression case. It has no negative null
calibration. The earlier route-search null results do not apply to it.

## Scope of the artifact

The original round1–5 files are preserved. Round6 source names end in `_v6.py`;
all new experimental results are in `results/v6`. The consolidated table is
`results/v6/results.csv`, with machine-readable interpretation in `summary.json`.

Some errors in auxiliary serialization/validation were fixed; initial error
logs and the superseded pre-serialization-fix manifest were retained. No failed
run is counted as a completed trial. Each experimental score is tied to its
specific protocol; different alphabet normalizations and objectives must not
be pooled onto one scale. Existence of an inverse does not authenticate a
historical plaintext.
