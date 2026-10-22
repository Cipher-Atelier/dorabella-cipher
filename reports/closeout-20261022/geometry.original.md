# Compass input geometry: a sufficient 24-representative quotient

21 October 2026. Symbolic planning only. No actual glyph projection, token-map census, arrays, RNG, language scores, controls or solver runs were performed for this note. No larger experiment is elected. Existing frozen experiments remain unchanged.

## The explicitly bounded embedding family

Use orientation order E,SE,S,SW,W,NW,N,NE and COMPASS coordinates
`((1,2),(2,2),(2,1),(2,0),(1,0),(0,0),(0,1),(0,2))`.
For orientation o and zero-based arc count a, define

`Phi[k,s,alpha](o,a) = (COMPASS[(s*o+k) mod8], alpha(a))`,

where k=0..7, s is +1 or -1, and alpha is any permutation of {0,1,2}. These are 16 compass dihedral maps times six arc permutations: 96 embeddings. Extend each to a full27 cell bijection by mapping centerline cells `(1,1,a)` to `(1,1,alpha(a))`. This extension makes the algebra explicit; it does not create physical centerline glyphs.

The cipher class has continuous block decryption, every period1..87, all six axis orders, ordinary actual-length short tails, and ONE unknown full27 output-letter permutation. No row resets, arbitrary eight-direction key, arbitrary input cube key or opposite-transform addition is implicit.

## Two absorbable transformations

Let c(t)=2-t. Common coordinate complement C applies c to all three trits. It commutes with coordinate regrouping, because regrouping only copies trits. Thus its output action is absorbed into the free output table.

Let S exchange row and column coordinates. In this COMPASS convention it sends o to `2-o mod8`. The axis conjugacy identity changes the decryption to another already-included axis order, leaving an output coordinate permutation that the unknown table absorbs. This is a statement about the UNION over all six axes, not equality at a fixed axis.

These identities hold separately for each actual block length, so every period and the real shorter final block are covered. The actions on embeddings are:

| Action | New `(k,s,alpha)` |
|---|---|
| C | `(k+4,s,c composed with alpha)` |
| S | `(2-k,-s,alpha)` |
| CS | `(6-k,-s,c composed with alpha)` |

All k arithmetic is modulo8. C and S are commuting involutions. C changes k by4, while S and CS flip s; none of the three nonidentity actions fixes an embedding. Therefore the96 embeddings have exactly24 orbits under THIS four-element subgroup.

One explicit representative set is `s=+1`, `k=0..3`, with all six alpha. Apply S first when s is negative, then C when the resulting k is at least4. Each subgroup orbit has exactly one such representative.

## Coverage bound and limits

At period1, decryption is identity, so ANY of these full27 embedding bijections is absorbed into the unknown output table. One common period1 family suffices. For the other86 periods, 24 representatives and all six axes give the sufficient mathematical upper bound

`1 + 86*6*24 = 12385`.

This does NOT prove that the remaining representatives are inequivalent under a larger nonlinear or cross-operator relation. It is a coverage upper bound, not a minimal-family census. A180-degree compass turn ALONE lacks C's accompanying arc reversal. A45-degree turn has not been shown absorbable by this subgroup.

Mathematical equality of complete key families does not imply identical finite stochastic searches, initializations, seed trajectories or saved maxima. Current canonical-geometry517-family controls do not establish power for the larger selector. A later experiment would need its own frozen control distribution, operator normalization and identifiers, seed plan, resource contracts, complete pipeline calibration and independent proofs. Generic full27 controls would still not become physical24/20-observed historical controls automatically.

ROOT independently checked the actions, free subgroup action, representative construction and arithmetic against the earlier unknown-output and period-equivalence notes. Independent read-only mathematical review agreed. No plaintext, letter correspondence, historical use of this geometry or exclusion of the remaining cipher class follows.
