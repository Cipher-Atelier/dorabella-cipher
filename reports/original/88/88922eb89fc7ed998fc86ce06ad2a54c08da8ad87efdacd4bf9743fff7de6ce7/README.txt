Dorabella R6 §7 — implementation-readback-1 — BLOCKED / NOT_STARTED

Start with STATIC_REVIEW_RU.md, then freeze_manifest.json and SHA256SUMS.txt.
Scientific protocol: protocol/review-v1.md, unchanged byte-for-byte.

code/reference.py        Independent scalar encoder / decoder / verifier.
code/driver.py           G0/G1 procedure definitions, never executed here.
code/winner_original.py  Literal original lines100–109, dormant; no G2 stage.
code/guard.py            Hash checks and persistence primitives.
code/supervisor.py       Fail-closed read-only admission; NO launch backend.
code/static_review.py    AST/byte audit only, executed once in preparation.
original/               Unchanged local source closure, model, dictionary,
                        input/provenance and selected original result records.
inputs/                 Frozen positive text candidates, not encryptions.
evidence/               Actual environment observations, static machine audit,
                        source provenance and preparation journal.

This is NOT a runnable calibration package. A functioning isolated launcher,
watchdog, durable run context and pinned original runtime remain unavailable.
Supervisor --run always raises; manifest has no authorized stages.
No T0, G0/G1 results, bank generation, encoding, representability, score or
solver computation was produced. Future readback must not be treated as
resolution of the documented blockers or permission to silently weaken caps.

All archive member bytes were copied and hashed, never imported/executed.
The source-only audit script imports only Python standard-library modules.
Rerunning it would refuse overwriting its existing evidence output.

Manifest is JSON consumed by supervisor's read-only entry. Pin its SHA from
MANIFEST.sha256, independently checked against the supplied ZIP identity.
Do not run original/fraction_v6.py or any archived main().
