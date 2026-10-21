DORABELLA ROUND 14
Independent within-triplet arc order with cyclic triplet group order

This package records an exploratory, finite cryptanalytic experiment, not a
claimed decipherment. See Dorabella_round14_report_ru.docx for the short report
and checks/results_verified.json for the full numeric summary.

The family has 16 * 6^8 = 26,873,856 unique complete keys per input. It is not a
superset of round13. See protocol.json for the exact formula, canonical IDs,
pruning proof, score, tie rules, sensitivity gate, and limitations. The original
protocol was frozen before Dorabella scoring. Later auditing, packaging, and
reproduction helpers are separate files; BUNDLE_MANIFEST.sha256 covers them.

Contents
- protocol.json and protocol.sha256: original frozen definition and input/code hashes
- data/search_inputs.json: 94 inputs used by the search, without positive answers
- data/positive_truth.json: 14 previously seen regression plaintexts and fresh keys
- data/scoring.npz: unchanged round13 character and word model
- code/engine.py and run.py: frozen numerical search
- checkpoints/: all 1,504 block JSON records
- results/: all 94 complete search records, including every maximum-tied full key
- checks/results_verified.json: independent scoring and inverse-cipher checks
- checks/review_integrity.json: independent positive-gate and frozen-code audit
- checks/final_integrity.json: full protocol/checkpoint/result consistency audit
- checks/unpruned_*.json: four complete no-pruning reruns and comparisons
- checks/clean_replay_verified.json: fresh-directory reproduction check
- code/reproduce.py: safer clean-directory replay wrapper
- requirements.txt and environment.json: tested numeric dependencies and runtime

Reproduction
Use Python with versions from requirements.txt. Install them in a virtual
environment, then run from the extracted package directory:

  python code/audit_integrity.py --require-complete
  python code/reproduce.py --output /absolute/path/to/new-output-directory

The output directory must not already exist and must be outside the source
package. The wrapper copies frozen inputs/code into a fresh directory, verifies
the protocol, reruns all 14 regression cases, verifies the fixed sensitivity
gate, and then reruns the real cases and 78 controls. It compares score, key ID,
all exact ties, decoded87, and evaluation counts against the archived results.
Success is saved as reproduction_verified.json with status=passed.

For a bounded replay:
  python code/reproduce.py --case hauer_real --output /absolute/path/to/new-output-directory

This still reruns the14 sensitivity cases before the requested real input.
The original low-level run.py resumes/skips existing output and has weaker
cache provenance checks than audit_integrity.py. Do not use it with untrusted
or mixed old results; use the fresh-directory wrapper. At most two disjoint
case workers are started. Do not concurrently launch the same target case.

Optional full no-pruning audit, after results exist in the selected directory:
  python code/audit_unpruned.py --case hauer_real

Only NumPy, Numba and llvmlite are needed for the numerical experiment. The
optional document-building script additionally requires python-docx. Source
paper downloads are not needed for numerical replay. New historical documents,
new cribs and fresh blind annotations were not part of this experiment.

Interpretation
All 87 glyphs are optimized; none is held out. The14 plaintexts were already
used before this round. The78 controls are also reused and preserve directed
bigrams and endpoints. Separate plus-one tails are descriptive conditional
ranks, not solution probabilities or globally corrected significance. Both
transcriptions come from related prior readings, not independent manuscripts.
There are exactly two equivalent complete keys for each observable decoding of
each real/control input because some glyphs never occur. Re-encryption confirms
algebraic consistency, not historical correctness.

Sources
https://aclanthology.org/2021.smp-1.5.pdf
https://www.benzedrine.ch/dorabella.html
Archived round13 reproducibility bundle SHA256 is recorded in protocol.json.
All final report values come from the completed outputs in this package.
