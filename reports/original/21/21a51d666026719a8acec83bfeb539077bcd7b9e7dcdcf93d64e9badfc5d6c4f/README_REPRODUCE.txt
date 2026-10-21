This is a completion calibration of R6 every-route-wordall, NOT a new cipher family.
protocol.json and freeze.json precede the first solver invocation.
Install requirements.txt into dependencies/ with pip --target (or supply the same versions).
python code/run.py runs exactly52case searches; it uses positive00 as an equivalence gate against the included archived checkpoints.
python code/verify_results.py independently checks a completed calibration.
The TextBlob data file is pinned and included; TextBlob itself is not needed.
Do not use generated caches or treat prior archives as new results.
The production runner is not a shortcut read of old outputs; it overwrites per-case solver records on a fresh reproduction.
Do not rerun run.py in the same directory without first moving runs/ and logs/ aside: the archived task functions use checkpoints.
