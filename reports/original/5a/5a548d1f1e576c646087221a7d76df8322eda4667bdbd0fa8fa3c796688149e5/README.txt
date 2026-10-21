A2-v1 — PROSPECTIVE / NOT EXECUTED
Read A2_PLAN_RU.md, vectors.json, code/*.py, static_review.py and evidence/static_review.json.
No launch is authorized by possession of this package. External readback is required first.
Do not import or execute sources/fraction_v6.py, checks_v6.py or wrapped_grid_gate.py.
They are exact evidence files, not entrypoints. Scientific dependencies are not needed for A2.

Potential future entrypoint, only after acceptance: code/run_a2.py under the pinned Python with -I -S.
It requires --execute-A2-v1 and --manifest-sha256 with the exact MANIFEST.sha256 value.
Do not run it now, including --help. No wrapper, background process, worker or auto-resume is supplied.
The single fixed attempt directory must never be removed to enable a retry.
A2 requires complete22 case receipts, observed exit0 and external hash readback; PASS_CANDIDATE alone is insufficient.

The static reviewer has already run once. It parsed text/AST, never imported the tested modules.
Its retained report is evidence of static checks, not execution of test vectors.
All prior scientific files are unchanged. The separate readable report equals A2_PLAN_RU.md byte for byte.
