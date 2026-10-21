# Dorabella round 13 preflight

Status: not executed as a cryptanalytic run.

Verified:
- Python environment available.
- round11 update archive available at /mnt/data/dorabella_round11_update.zip.
- Archive contains round11 code, checkpoints, and data.
- Inspected round11 engine/run code.

Important finding:
- round11 engine is prefix-only: run.py asserts len(g)==43 and selects keys on prefix.
- The requested round13 experiment would be a new full-87 optimization, not a rerun of round11.

Not executed:
- No 30,965,760-key full-87 search.
- No controls.
- No positive-control reruns.

Reason:
- The extracted code is not immediately runnable in the inspected location because imports/dependency layout are incomplete (engine.py imports model_v5 from the laboratory root, not present in the extracted round11-only tree).
- Full benchmark and reproducibility setup require restoring the complete laboratory tree.

Next required step:
- restore full round10/round11 laboratory tree without modifying frozen files;
- verify hashes;
- run a small synthetic performance benchmark;
- only then decide whether the full-87 search fits available resources.
