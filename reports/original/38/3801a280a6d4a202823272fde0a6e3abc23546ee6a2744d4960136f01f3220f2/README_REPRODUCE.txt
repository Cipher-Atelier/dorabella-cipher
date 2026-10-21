DORABELLA COORDINATE LAG TEST
A finite exploratory experiment, 9 October 2026. No decipherment claimed.

The new mechanism independently shifts one of the two original geometric
components, then pairs the components again. Previous whole-glyph routes and
base-5/base-3 fractionation do not do this operation. The frozen protocol gives
exact scope, key numbering, scorer, controls and stopping criteria.

Files
protocol.json and protocol.sha256: original frozen protocol and its checksum
code/experiment.py: frozen bank, transform, inverse, sampler and exact search
code/reproduce.py: fresh-directory replay; will not modify this bundle
code/audit.py: independently implemented verification
results/: complete real, regression and control results
checks/: sensitivity, independent audits, pruning checks and source integrity
report DOCX: readable Russian account of the actual outcome

Reproduction
Install the versions in requirements.txt in a virtual environment. From this
bundle's root, run:
  python code/reproduce.py --output /absolute/path/to/a-new-directory
The target must not exist and must be outside the original bundle. Replay
checks frozen hashes, freshly recovers all 14 regression texts before searching
real/control cases, and compares scores, canonical keys, every exact tie,
plaintext, baseline and evaluation counts for all 414 cases. Three full unpruned
searches verify maxima and baseline again. Timing and paths are not compared.

Do not use 'experiment.py prepare' for replay: it creates a new protocol and
inputs. Do not run its low-level 'run' command inside the archival directory:
it writes results. The wrapper keeps source and new output separate.

Interpretation
Both transcriptions are related readings, not independent manuscripts. All87
symbols are optimized and none is held out. The 14 known texts are old regression
examples with fresh artificial encryption. The 199 controls per transcription
are newly sampled conditional sequences; this does not remove adaptive choice
of a hypothesis after earlier rounds. Separate plus-one tails are descriptive
conditional ranks, not probabilities of a solution. Same integer shifts within
rows are bounded to -43..43; this does not cover arbitrary independent offsets
for all three rows. k=0 repeats static mappings already studied. Parameter
counts include duplicate operators; all exactly tied maxima are retained.

The package contains no British Library image, paid scan, private correspondence
or derivatives of restricted source images. It creates no publication or
external disclosure permission. Original research inputs are left unchanged.
