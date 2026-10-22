# Unknown-key Trifid: universal period/axis equivalence

Analytic planning only, 21 October2026. Fixed NORMAL87, continuous blocks, actual shorter final block, p=1…87, all six ordered axes; input compass mapping unchanged. No row resets, rotations/reflections, opposite-transform addition, actual input projection, arrays, RNG, model/reference import, new token-map enumeration, solver or score. No new experiment elected. This strengthens the earlier design note's deliberately unresolved alias question for this EXACT family; it changes no frozen artifact.

## Formula and general output-key criterion

Let x[i,a] be input trit a∈{0,1,2} at cell i. In a block beginning b with actual m=min(p,87−b), output coordinate σ(j), j0…2, copies

`D[p,σ](b+i,σ(j)) = (b+floor((j*m+i)/3), σ((j*m+i) mod3))`, i0…m−1.

This is the exact reviewed `full27(...,inverse=False)` convention. The inverse groups ordered plaintext-coordinate streams back into interleaved ciphertext triples. All formulas here use decryption; no padding or replacement by a nominal full-period tail.

For two such token permutations F,G, there exists ONE position-independent output cell bijection h∈S27 with G(x)[i]=h(F(x)[i]) for EVERY full27 input x iff there is ONE coordinate permutation τ∈S3 such that

`D_G(i,a) = D_F(i,τ(a))` for every i,a.

Proof: write y=F(x); y ranges freely over27^87. G∘F⁻¹ copies coordinate variables. If an output trit uses another y-cell, vary that variable while holding y[i] fixed: no fixed h(y[i]) can explain it. All three source addresses therefore belong to the same y-cell and, by bijectivity, constitute a coordinate permutation τ_i. A single h at every position forces τ_i identical. Conversely a uniform τ is plainly absorbable into any unknown output alphabet π. Thus arbitrary27! output relabeling creates no extra nonlinear universal equivalences between these coordinate-copy transforms.

The same necessity holds on ALL physical24 input strings, not merely on full27 strings: every individual source trit can vary0→1/2 around the all-zero input while remaining off the missing(r=c=1) line, forcing the same source-address-set condition. Every selected output triple can attain all eight {0,2}³ corners with physical inputs; the coordinate-permutation action on these corners is faithful, forcing a uniform τ. This concerns the entire physical24 domain, not a particular observed20-type text. A relabeling may remain arbitrary on codes unreachable everywhere, but cannot create additional transform equivalences.

## Applying the criterion without enumerating maps

**Different periods cannot be output-key aliases.** For p≥2, inspect only INPUT CELL addresses of the three output coordinates at the first two positions. The first multiset is `{0,floor(p/3),floor(2p/3)}`. It distinguishes all periods except p=3k versus3k+1, k≥1. For that pair, the second multisets are `{0,k,2k}` and `{0,k,2k+1}`, so they differ. p1 has first multiset `{0,0,0}`, distinct from every p≥2. A cell relabel may reorder three coordinates, not substitute a different source-cell address. Later block boundaries/tails therefore cannot restore a lost equivalence.

**At fixed p≥3, different axes cannot be output-key aliases.** Within the first block, the source-cell addresses floor((j*p+i)/3), j0,1,2, are strictly increasing. Address matching forces the same stream j in both transforms, independently of the physical coordinate order. In the criterion above this means τ(σ′(j))=σ(j). Matching the actual input-axis labels also requires σ′(r)=σ(r); positions i0,1,2 expose all three residues r via j0. Hence σ′=σ and then τ is identity. This first-block obstruction cannot be undone by a shorter last block; when the axes agree, both transforms also apply the identical actual-m tail formula. Removing an output-axis permutation does not remove the input-axis conjugation.

**At p2, the last block has m1 because87 is odd.** Every axis choice is identity on that singleton, so any universal output relabel must be identity on its possible cell values (and on all eight corners for physical24). Distinct axis choices give distinct exact token maps already on a two-cell block: source-address sets require equal middle axis and, at most, swapping the other two; that reversal induces different output rotations in the two positions, not identity. Thus no distinct p2 axes are aliases. This argument explicitly includes the real last partial block; it is not a padded-period argument.

**At p1, all six axes are exactly identity**, not just equivalent after a new output key. Conclusion for continuous87:522 nominal labels reduce to **517 universally distinct families even with a free27 output permutation**: one identity family plus86×6. There are no further universal output-cell-relabel aliases among these labels. This analytic count agrees with existing preparation metadata's exact-token count, but was derived here without generating or comparing its stored261-index arrays. Finite-input coincidences or score ties may be more numerous; none were inspected.

## What an input relabel does, and why it is different

With Pσ denoting coordinate-order permutation, F[p,σ]=Pσ⁻¹ F[p,012] Pσ. The left output permutation is absorbable; the right INPUT permutation generally remains. Therefore one cannot keep only axes012 at each p merely because π is unknown.

An EXTRA global input-axis relabel Q adds no family when all six σ are already present: F[p,σ]Q=Q F[p,σ′] for the corresponding σ′, then absorb the output Q into π. This relates a CHANGED input embedding to another axis member; it does not identify the two members on the SAME fixed input embedding. A common trit bijection applied to all three coordinate fields also commutes with token copying and is absorbable. Independent field reflections/count reversal generally require additional position-dependent relabeling and are not covered by that argument. They are not added or evaluated here.

## Distinct-type constraint and calibration limit

For a given transformed sequence with d distinct cube codes and one bijective cube→A–Z+SPACE key, the raw87 plaintext has EXACTLY d distinct output symbols. If SPACE occurs, the number of distinct letters is EXACTLY d−1; if it does not, it is d≤26. SPACE cannot absorb several cube types, and no letter fold/merge/deletion is allowed in this family.

Using ONLY root's already reported period7 metadata d=25…27 (not recomputed here): with SPACE present this requires24…26 distinct letters. At d27 all26 letters and SPACE must appear; at d26 the possibilities are25 letters+SPACE or26 letters/noSPACE; at d25 they are24 letters+SPACE or25 letters/noSPACE. Any fixed eligibility requiring SPACE removes the noSPACE alternatives, not the diversity requirement.

This is a necessary inventory condition, not a language impossibility, plaintext, letter assignment or p-value. An87-symbol English pangram is possible; unusual diversity alone does not exclude English or establish fractionation. Generic controls may have different planted output inventories/source style and full27 ciphertexts rather than physical24 inputs. Old strict24 negatives, fixed-table/published-table controls and atomicSPACE27 or period7 generic controls do not establish sensitivity for every period, high-d observed equality pattern or a full outer-period selector. No matched inventory corpus counts, controls, rejection rules or new language test were constructed here.

Primary1893 documentation establishes one three-coordinate period7 example with a fixed published table, not an unknown alphabet, compass embedding, period sweep or Elgar use. All exact source/code/metadata hashes read for this proof are in the sibling provenance JSON; no frozen files or live root reports were edited.
