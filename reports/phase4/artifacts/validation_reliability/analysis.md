# Phase 4 validation reliability audit

## Scope and boundary

This is a live-model audit of the independent item validator, not an ensemble
acceptance procedure. Rejudgments did not change the frozen item-audit bank.
The enriched sample is intentionally not prevalence representative: it contains
12 originally accepted and 12 originally rejected candidates, all three
generation conditions, all eight pilot GrammarCells, and every criterion that
failed in the original pilot.

The original pilot produced 86 structurally valid candidates and valid
validator outputs; 56 were accepted and 30 rejected. The reliability sample was
judged again from neutral visible content and intended GrammarCell, without
generation metadata, by:

- a fresh `gpt-5.6-terra` call at medium reasoning effort (same-model repeat);
- `gpt-5.6-sol` at medium reasoning effort (model sensitivity).

The exact command is retained in `manifest.json`. One Terra repeat returned
malformed JSON and is retained as an invalid validator output rather than
silently retried; 23 Terra and all 24 Sol rejudgments were structurally valid.

## Reliability results

| Comparison | Joint valid n | Accept agreement | Wilson 95% interval | Cohen's kappa |
|---|---:|---:|---:|---:|
| Original Terra vs Terra repeat | 23 | 82.6% | [62.9%, 93.0%] | 0.652 |
| Original Terra vs Sol | 24 | 79.2% | [59.5%, 90.8%] | 0.583 |
| Terra repeat vs Sol | 23 | 78.3% | [58.1%, 90.3%] | 0.569 |

Same-model repeat agreement was 82.6% for determinacy and 91.3% for
pedagogical suitability. Cross-model agreement with the original was 79.2% for
both determinacy and pedagogical suitability, 87.5% for naturalness, and 95.8%
for no-extraneous-grammar. Target fidelity, grammaticality, non-target-language
simplicity, no-answer-leakage, and no-world-knowledge were unanimously passed
by all judges on the sample. Their nominal 100% agreement is a ceiling effect:
the audit supplied no negative cases with which to establish rejection
reliability.

The primary conclusion is therefore criterion-specific. The validator is not
arbitrarily unstable: agreement is substantial at the overall decision level,
and the two model families agreed perfectly on several observable properties.
However, item acceptance is meaningfully sensitive to repeated/model judgment
because determinacy is both common and interpreted inconsistently.

## Criterion activity and redundancy

Across all 86 original live judgments, failures were:

| Criterion | Failures |
|---|---:|
| target fidelity | 0 |
| grammaticality | 0 |
| naturalness | 7 |
| pedagogical suitability | 8 |
| determinacy | 29 |
| non-target-language simplicity | 0 |
| no-answer-leakage | 0 |
| no-extraneous-grammar | 3 |
| no-world-knowledge | 0 |

Determinacy accounts for 29 of the 30 rejected candidates. Naturalness and
pedagogical suitability overlap strongly: all seven naturalness failures also
failed pedagogical suitability, and seven of eight pedagogical failures also
failed naturalness (failure-set Jaccard 0.875). The criteria are nevertheless
not activation-identical on the full bank. Their behaviour also diverged under
model sensitivity: Sol failed naturalness twice but pedagogical suitability
seven times on the enriched sample. This is evidence of overlap, not sufficient
evidence to remove either criterion.

No-extraneous-grammar was nested inside naturalness in its three original
failures, but the very small failure count prevents a redundancy conclusion.
The five always-passing criteria are untested on negative cases, not validated
as redundant or reliable. A deliberately constructed challenge set would be
needed to audit them.

## Qualitative agent inspection

The six-item subset was declared automatically by disagreement and diversity
before inspection. The detailed review is in
`agent_qualitative_review.md` and is explicitly a research-agent assessment,
not human validation.

The disagreements are substantively interpretable. Three candidates omit or
weakly communicate the intended form (`would`, passive, or past-perfect
progressive); one has a visible blank/target-answer span mismatch. Other
disagreements concern whether optional contractions, discourse markers,
politeness, or adverbs make the accepted-answer set non-exhaustive even when the
target grammatical contrast is clear. The current criterion does not state how
strictly to distinguish target-form determinacy from exhaustive surface-form
determinacy. Different calls resolved that ambiguity differently.

## Methodological implication

Keep independent per-criterion validation, but do not claim that one judgment
is a gold item-quality label. Do not add an ensemble solely from this small
study: without human adjudication there is no basis for deciding which model is
correct. Before realistic-scale generation, operationalise determinacy more
precisely by separating (a) whether the learner-facing prompt fixes the target
grammar from (b) whether harmless surface variants are represented in the
accepted-answer set, and add structural checking for answer-span consistency.

Naturalness/pedagogical-suitability overlap should be monitored rather than
silently merged. Criteria with zero failures require targeted negative controls
before reliability or redundancy claims.

## Retained evidence

- `manifest.json`: exact command, models, settings, seed, and input hashes.
- `sample_mapping.jsonl`: stratification and original-to-blind mapping.
- `blinded_items.jsonl`: exact neutral rejudgment inputs.
- `original_judgments.jsonl`: frozen original sample decisions.
- `terra_repeat_judgments.jsonl` and `sol_sensitivity_judgments.jsonl`.
- `terra_repeat/` and `sol_sensitivity/`: per-call prompts, inputs, raw outputs,
  parsed results, settings, and resumable result records.
- `summary.json`: full per-criterion agreement and failure-overlap diagnostics.
- `qualitative_sample.jsonl`: mechanically declared six-item review subset.
- `agent_qualitative_review.md`: labelled non-human qualitative inspection.

