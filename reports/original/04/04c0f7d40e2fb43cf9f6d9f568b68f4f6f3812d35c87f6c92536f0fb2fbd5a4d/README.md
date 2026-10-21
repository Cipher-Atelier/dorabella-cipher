# Round 13: fixed synthetic87 scan_block microbenchmark

This package records only the benchmark requested in this conversation.
No full-family search, Dorabella evaluation or 94-input experiment was run.

## Executed procedure

- Input: NumPy default_rng(1301).integers(0,24,size=87,dtype=int64).
- Input raw-byte SHA-256: 10abe79f71717da2c8e1fa71e5b82b82fd72a17a721aaff37f909c37ab8c227a
- P8 half-open ranges: [0,4), [10000,10004), [20000,20004), [30000,30004).
- Each range: one excluded warmup, then three fresh measurements (-1e100, -1),
  then three conditional measurements starting from that same block's measured optimum.
- Compilation/signature-cache-load wall time, separate: 2.063390208 seconds.
- Timings cover scan_block only, including its allocations and returned-array construction.
  Generation, serialization, validation and compilation are excluded.
- 3072 C evaluations and 12 dictionary-upper-bound evaluations per call.
- Complete W = sum(stats[:,4]); pruned W = sum(stats[:,5]).
  The former is checked against all three sparse-output lengths.
- 24 timed calls, 4 excluded warmups; 12288 distinct keys across the four blocks.
- Model and engine remain unchanged. All 16 frozen dependency hashes match before and after.
- Repetitions within each mode have identical output-array hashes. All inputs are unchanged.

## Files and evidence

`benchmark_scan_block.py` is the exact executed benchmark code.
`benchmark_protocol.json` was written before compilation and measurements.
`benchmark_report.json` contains every individual duration, complete-W/pruning counts,
best score/ID, input metadata, module paths/hashes and output hashes.
`P8_*.npz` contains the actual arrays returned by each of 28 calls.
`scan_block_source.txt` records the unchanged function whose counter semantics were inspected.
`restoration.json` records archive paths/hashes, restore verification and the initial process snapshot.

The `stats[:,7:9]` local values are NOT assumed to be exact maxima for pruned
(P8,m) subgroups; they concern only evaluated candidates. The returned block
maximum is exact for fresh searches under the unchanged engine's bound,
and is carried unchanged into the conditional measurements.

No fresh independent mathematical audit of C/W/bounds was performed here.
This package does not promote historical or user-reported audit results to new runs.

## Reproduction

Requires the unchanged laboratory restored from:
- dorabella_lab_round10.zip
- dorabella_round11_update.zip

Run from any directory with an unused output directory:
```bash
python benchmark_scan_block.py --lab /path/to/dorabella_lab --out /path/to/new_benchmark
```
The script refuses to overwrite an existing report. It creates new cache files only under --out.

## Extrapolation limits

The report's arithmetic scaling uses the mean of four fresh-block median times.
It is not a measured full-family runtime, a confidence interval, or an established
94-input budget. A full search carries its incumbent between blocks; W pruning
depends on the input and reached incumbent. Only one uniform-random synthetic
input was timed. Compilation, checkpoint I/O and preparation are excluded.
