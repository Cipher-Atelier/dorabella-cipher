The frozen search returned **zero matches in all 56 queries**. It tested 1,223,296 supplied, position-aligned Elgar notes under two projections: all 39 exact token spellings and 36 canonical pitch-class/duration codes. Only the three duration-specific A-flat/G-sharp spelling pairs merge in the canonical projection.

| Projection | Transcription | Full87 matches across 8 masks | Individual-row matches across 6 rules |
|---|---|---:|---:|
| Exact39 | Hauer | 0 | 0 |
| Exact39 | Hartmeier | 0 | 0 |
| Canonical36 | Hauer | 0 | 0 |
| Canonical36 | Hartmeier | 0 | 0 |

Every search required an exact whole-window equality pattern under a bijection of observed glyph labels. The global corpus alphabet having more than 24 types was allowed; the bijection applies to the individual window. The 28 targets were unchanged from the earlier search. No approximate search, language score, crib, insertion, deletion or repair was used.

The measured search, corpus predecessor construction, result assembly and writes took 0.595 seconds in a single process. Synthetic QA passed 588 all-window comparisons against an independent bidirectional mapper, including 80 planted matches, 12 strict invalid-token rejections and accidental/enharmonic/duration checks. Independent postverification reconstructed both complete corpus arrays from all source tokens, reconstructed all 28 targets from source geometry, and checked all 56 unique target/projection records and counts. There were no positive offsets requiring excerpt/inverse checks. No additional actual target queries were made during postverification.

Because every unchanged row has zero matches in both directions, the [proof-only corollary](COROLLARY.md) excludes a full87 exact match after any physical-row permutation/reversal or at most two single-position glyph substitutions in these same two projections and pooled source. At least one complete row would remain unchanged and would have to match a contiguous corpus segment, contradicting the row results.

This is a representation-specific exact negative result. The supplied corpus is already lossy and pooled: octaves, original durations, rests, voices, work boundaries and chronology are not restored. Windows may cross unknown work boundaries. No VariationX, original MIDI or pre1897 attribution follows, and other musical encodings are not excluded. The explicit notation interpretation and primary documentation links are recorded in [PLAN.md](PLAN.md); music21 encoder provenance was not established.

The code, two array hashes, parser/projection tables, targets, source files and archive SHA were frozen before QA and target search. Frozen protocol SHA256: `2b2d3153f217ea06c25276a5f5278afe56a77cbbdb8f380cfb161847ba4a7f01`. Earlier files were read-only.
