# Dorabella cipher

Status as of 5 October 2026: **not deciphered (не расшифровано)**. The completed computational experiments have produced no accepted plaintext or letter assignments.

## Research question

Can the 87-sign note be explained by a constrained substitution derived from its eight orientations and three arc counts? A separate musical-source investigation asks whether an appropriately dated musical witness can justify a testable crib.

## Sources and earlier work

- Bradley Hauer, Colin Choi, Abram Hindle, Scott Smallwood and Grzegorz Kondrak, [*Dorabella Cipher as Musical Inspiration* (2021)](https://aclanthology.org/2021.smp-1.5/), especially Figure 2 for a transcription. Their musical output is explicitly framed as creative composition rather than a uniquely established historical solution.
- Daniel Hartmeier, [*Clues (or red herrings) to the Dorabella Cipher*](https://www.benzedrine.ch/dorabella.html), for source discussion and the alternative transcription tradition.
- British Library, [Add MS 57992 catalogue record](https://searcharchives.bl.uk/catalog/040-002000199), identifying *Lullaby* at ff. 28–37 in a score catalogued [1896]. This is a source lead, not an inspected score or an established crib. A 1901 score and later recollections are insufficient to establish a crib for the 1897 note.

## Completed tests

The latest completed experiment, round 14, fixed the cyclic triplet sequence ABC, DEF, GHI, KLM, NOP, QRS, TUW, XYZ. It allowed eight rotations, two traversal directions and an independent six-way arc-count permutation within each triplet. I/J and U/V were folded. All 87 signs remained in source order.

This gives 16 × 6⁸ = **26,873,856 keys per input**. It is a neighboring family, not a superset of round 13: the internal permutations are freer, while triplet order is more restricted. The families intersect in 12,288 keys.

The fixed S87 = C87 + 0.5 W87 criterion was applied to two source transcriptions, 78 control sequences and 14 regression messages: **94 searches**. This involved 2,526,142,464 character-score evaluations and 9,813,214 full word-score evaluations; safe upper bounds avoided unnecessary word-score work. Four full unpruned repeats agreed on maxima and exact ties.

## Results and their limits

Both real transcriptions selected canonical key 19301530, with one equivalent full key, 19305418. Their difference concerns absent signs and leaves the output unchanged. Isolated English-looking fragments did not form a connected message. No key or letter value is accepted.

All 14 previously used messages, re-encrypted under the round-14 family, were recovered: 1,218/1,218 letters. These are **old regression controls**, not new independent validation. The real-note scoring has no held-out section.

Control comparisons preserve symbol counts, directed neighboring-pair counts and endpoint signs. The plus-one tail fractions are descriptive, conditional comparisons. The controls had already been used, and the family was selected after earlier experiments; no new significance or plaintext-correctness claim follows.

The research package records the frozen protocol, all 94 outputs, 1,504 checkpoints, inverse checks and implementation checks. This page summarizes that completed experiment; it does not publish the package or make the whole study reproducible from this page alone.

## Unresolved questions

Other substitution families, different triplet orders, positional transpositions, stateful ciphers and language-model limitations remain open. The musical branch has not passed its early-source gate. Neither completed negative tests nor an unavailable early witness establish that the note is meaningless.

All transcription, computational and editorial checks described here were AI-assisted. There is no external human validation of a decipherment.

[Research catalogue](../README.md)

