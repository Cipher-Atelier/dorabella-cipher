# CH1-v1: static review before the sole attempt

The accepted plan is copied unchanged as CH1-v1_accepted_plan.md. No test has been run during preparation. Source bytes, exact real IDs, lengths and observed-type ceilings were checked read-only. No prior CH1 runner/attempt/result was found in the local inventory or the retained Library title search.

Reviewed code/ch1_runner.py, numbered lines:

- 46–53: length 87, integer glyphs 0…23, at most 24 observed types and 276 pairs; guard runs before each diagnostic.
- 56–96: every observed unordered pair, lexical order; complete natural-order projection, original 1-based positions, first adjacent equality; both-singleton label. No grouping, route, reset, key or score.
- 99–124: positive-control truth from positional parity; inverse dictionary and independent counter encoder; all 87 observations retained.
- 127–155: pinned executable/version/-I/-S, every frozen hash, exact source SHA, exact IDs/order, full input arrays/strings and positions17–22.
- 157–185: exact P2/P3 formulas; N2 exchanges zero-based2/4, hence one-based3/5; expected graphs fixed before results. Save failed control and stop before real diagnostics on any mismatch.
- 188–212: H then M, all pairs; comparison uses their stored pair statuses, without choosing a favorable reading.
- 1–15,26–43,61–66,213–263: cooperative 10-second clock, bounded finite loops, 120060 primary-symbol ceiling, exclusive attempt directory, terminal hashes and explicit failure evidence. No resume/retry, subprocess, thread, network, RNG or scientific dependency.

AST was parsed without importing/executing the runner; only time, datetime, hashlib, itertools, json, pathlib, sys, collections are imported; no while/async/eval/exec. Static AST checks are not test execution.

Manifest SHA256: 9d597b40e47e34b41912d0599e6cbb434e1d1dd3ddae07e05be14e52573891cd

Runner SHA256: 75a303b16d9e442567e0edb2addf06a447e809c4575931c2588c94668523c16d

Runtime: Python3.12.14, exact executable and binary hash in manifest. The runner clock begins after importing time; it includes later imports, validation, computation and output writes. Tool-call observation additionally bounds invocation/startup and normal exit. This is cooperative, not realtime hard-kill or crash durability. Later readback/reporting is outside the diagnostic attempt and does not execute its mathematical functions. Original scientific T0 is untouched.
