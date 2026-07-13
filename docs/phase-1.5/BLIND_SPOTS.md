# Phase 1.5 Blind-Spot Analysis

The Kasparov-style question is not “what feature can we build next?” It is “what future loss becomes unavoidable if we choose the wrong move order now?”

## 1. Attractive UI can conceal a poisoned corpus

A polished drill player creates sunk cost and user exposure before trust is known.

**Countermove:** Phase 2 remains blocked behind a machine-evaluated corpus gate.

## 2. Aggregate pass rates can hide a losing flank

A 98% overall pass rate may coexist with one broken unit or one question format.

**Countermove:** sampling is stratified and quality floors are reported by unit and question type.

## 3. The board can change after the analysis

A corpus audit becomes invalid when revisions are corrected, retired, or remapped.

**Countermove:** each run stores a fingerprint of the exact latest revisions; drift makes the gate fail.

## 4. Random samples can overselect easy direct MCQs

Uniform random selection underrepresents rare passages, tables, assets, and blocked records.

**Countermove:** deterministic round-robin selection across unit × type × tier strata.

## 5. Reviewer agreement can be fake consensus

One reviewer repeating their own label is not agreement. Reviewers who see prior labels are not independent.

**Countermove:** labels are stored per reviewer; kappa uses only overlapping independently labelled items. Sample export does not expose other reviewers' decisions.

## 6. “Rights mostly clear” is not a rights model

A source-level assumption can accidentally publish one blocked question.

**Countermove:** every audit review records rights and provenance separately; the default gate requires 100%.

## 7. Answer-key confidence can be mistaken for evidence

A plausible answer is not an official or independently reviewed answer.

**Countermove:** answer-evidence status is a separate review dimension and golden entries are tied to validator runs.

## 8. Duplicate detection can destroy legitimate recurrence

The same official concept or wording across shifts may be valuable evidence, not waste.

**Countermove:** candidates require an explicit human decision; no automatic deletion or merge occurs.

## 9. A golden set can become a memorized showcase

Teams can optimize validators for 100 known examples while the rest of the corpus degrades.

**Countermove:** the golden set is paired with a separate 250-question representative audit and corpus fingerprint.

## 10. Review cost can kill the business after launch

A technically correct workflow may require more human hours than the subscription economics support.

**Countermove:** review seconds are mandatory evidence; median time and projected hours per 1,000 questions are reported.

## 11. Thresholds can be moved when inconvenient

A gate is meaningless if its owner lowers the bar after seeing results.

**Countermove:** thresholds are versioned input and stored verbatim in every evaluation. Changes require an explicit decision trail.

## 12. Source and validator evidence can silently detach

A copied manifest may point to a revision while carrying an unrelated checksum or old expected findings.

**Countermove:** golden validation checks revision identity, semantic hash, linked import checksum, and latest validator codes.

## 13. “Reviewed” can mean different things

Rights, rendering, mapping, provenance, and answer correctness are independent failure dimensions.

**Countermove:** each dimension is stored and gated separately rather than collapsed into one status.

## 14. Production claims can be built from fixtures

Synthetic tests prove software behavior, not corpus readiness.

**Countermove:** documentation and gate reports distinguish software completion from real evidence. The repository does not mark Phase 1.5 complete until real data passes.
