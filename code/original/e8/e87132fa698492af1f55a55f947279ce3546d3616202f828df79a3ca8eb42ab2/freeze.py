from pathlib import Path
import json,hashlib,datetime
H=Path(__file__).resolve().parents[1]
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
paths=['data/scoring.npz','data/search_inputs.json','data/positive_truth.json','code/engine.py','code/run.py','code/prepare.py','code/verify.py','code/benchmark.py','code/freeze.py','checks/preflight.json','checks/benchmark.json']
protocol={
'id':'round14-cyclic-triplet-independent-arcs-full87-exact-v1',
'frozen_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),
'hypothesis':'Fixed alphabetic triplets retain cyclic geometric group order up to rotation/reflection, but arc-letter order is independently arbitrary in every direction.',
'prior_scope':'Not a superset of round13. Intersection 12288 full keys; 26861568 keys newly outside round13. No claim this is an authenticated 1897 key.',
'alphabet':'ABCDEFGHIKLMNOPQRSTUWXYZ; merge I/J and U/V; scoring indices ASCII 0..25',
'group_order':'P[o]=(s*o+h)%8; s in [1,-1], then h in range(8)',
'arc_order':'Q lexicographic permutations of [0,1,2]; each direction independent',
'key_id':'pidx*6^8 + sum(q_o*6^o,o=0..7), q_0 least significant',
'key_formula':'key[3*o+c] = A24[3*P[o]+Q[q_o,c]]',
'full_keys_per_input':26873856,
'positions':'All87 in existing forward order; no insertion/deletion/transposition/reversal/state changes/spelling repairs',
'score':'unchanged archived S87=C87+0.5W87; all84 character4grams, same word segmentation',
'pruning':'Every C evaluated. W skipped only when C+.5*upperW < incumbent-1e-9. upperW is exact DP over independent allowed letters at each occurrence: q5,q6,q7 fixed within a 6^5-key block; q0..q4 unconstrained to their three group letters. This is a superset, permitting inconsistent assignments per occurrence.',
'selection':'strict float64 maximum; retain every exact equal best key; choose smallest canonical ID. Tolerance1e-11 only verification,1e-10 descriptive comparison. No true-key tie selection.',
'inputs':'14 fresh encryptions of old 12 Bailey/Brewer +2 Elgar regression plaintexts;2real Hauer/Hartmeier;78archived directed-bigram-preserving controls (39each). No heldout data.',
'synthetic_seed':202610051340,
'sensitivity_gate':'Before any real/null scoring: verify all14; require >=12 exact87/87 and >=1194/1218 letters correct. If fail, stop and report lack of sensitivity; no parameter changes within run.',
'controls':'Same full search on each. Verify counts,directed pairs,endpoints. Separate ranks and (k+1)/40 for each version; no pooled pair p or version cherry-pick. Adaptive exploration and reused controls: descriptive conditional tails, not confirmatory significance.',
'identifiability':'Each real/null87 output represented by2fullkeys due unobserved11,12,13,23 and only1observed member in orientation4; exact tie count must be even>=2. Fullkeys distinct, observed-string count13436928.',
'stop':'Complete frozen94inputs only after sensitivity gate and source/code checks; stop on verification failure or resource interruption, retain checkpoints. No model expansion, new cribs, score retuning, manuscript edits or external outreach. At completion report only this model result.',
'audit':'132 independent key/score/inverse and bound checks;12x1000synthetic pruned/unpruned checks before freeze. Recheck every final key/tie with independent implementation; independent roundtrip. Postrun complete unpruned audit for bailey_01,hauer_real,hart_real and hauer_real_pair_00.',
'benchmark':'synthetic random87:1,679,616keys in0.717seconds optimized; actual workload timing may vary. At most2case workers.',
'sources':['https://www.benzedrine.ch/dorabella.html','https://aclanthology.org/2021.smp-1.5.pdf'],
'prior_bundle_sha256':sha(H/'input/dorabella_round13_reproducible_bundle.zip'),
'prior_protocol_sha256':sha(H/'source/dorabella_round13/frozen_protocol.json'),
'sha256':{p:sha(H/p) for p in paths}}
p=H/'protocol.json';assert not p.exists();p.write_text(json.dumps(protocol,indent=2));(H/'protocol.sha256').write_text(sha(p)+'  protocol.json\n');print('FROZEN',protocol['frozen_utc'],sha(p))
