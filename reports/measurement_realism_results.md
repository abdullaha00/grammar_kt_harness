# Measurement-realism results

Status: final quantitative/qualitative synthesis for the measurement extension.
The frozen baseline remains unchanged; no new dataset release is justified.

## Executive result

Known latent truth is necessary for the project's counterfactual analyses, but
it is not sufficient for a valid language-learning measurement environment.
The programme establishes four complementary results:

1. full-v1 is reproducible and structurally useful, but its learner-facing bank
   and platform process have material unvalidated/implausible regions;
2. repeated outcome-blind KC induction does not yield a unique ontology, and
   Q rank is not psychological or generic statistical identifiability;
3. in a content-free structural control, planted format nuisance can make a
   false format-specific KC split predict better, while explicit format
   adjustment recovers the shared representation; a deliberately aligned
   seen-item adjustment recovers planted item nuisance;
4. structured errors add strong diagnostic localisation information but only
   small next-response gains, and greater dialogue openness increases visible
   naturalness at a steep cost to answer determinacy and KC attribution.

The attempted matched learner-facing bank passed only 5/38 families. Therefore
the strongest coherent contribution is a controlled analysis of measurement
assumptions and failure modes, not a claim that the project has produced a
human-realistic platform log.

## 1. Full-v1 learner/platform audit

The strict 113-item census classified 70 as usable under an explicit minimal
response-slot UI, 15 as minor repair, 15 as technically valid but artificial,
10 as material answer-space failures, and three as rewrite/withhold. A second
four-role model audit produced 452 retained judgments. After an explicit label
mapping:

- exact cross-audit agreement: 70/113;
- usable in both audits: 60/113;
- union requiring some action: 53/113;
- union of critical answer-space/withhold concerns: 18/113;
- live learner/teacher/product/measurement role disagreement: 56/113.

All 113 stored items are one broad controlled-production format; descriptively
they include 91 cloze-like slots, 18 whole responses, and four prose chunk
reorders. All four imperative rescue items were called artificial by the
strict audit. The explicit-construction campaign produced no as-stored usable
item under that audit. Three of eight `may` opportunities were underdetermined,
and one one-KC reported-speech row visibly required unmodelled grammar.

These are automated stress-test judgments, not human deployability estimates.
They nevertheless reject equating validator acceptance and a rank-18 Q with
platform-valid measurement. Exact item panels and IDs are in
`reports/platform_plausibility_audit.md`.

## 2. KC construction and non-uniqueness

The declared K* is retained as an interpretable experimental coordinate system,
not human truth. Its 18 columns are linearly independent in full-v1, but only
16/113 items isolate one KC and six KCs have no isolating row. Support and
pedagogical interpretation vary sharply.

Three independent, outcome-blind KC inductions yielded 17/18/18 activation
signatures with ranks 17/18/17. Only nine signatures appeared in every run;
the union contained 30; pairwise activation Jaccard was .400, .440, and .458;
and 5/4/7 proposals exactly matched a K* activation. K* is therefore one
declared plausible world among alternatives. The result is consistent with the
existing full-v1 discovery finding: observable responses identify bank-induced
activation equivalence classes, not unique competence semantics.

## 3. Matched-format construction is a negative result

The rank calculation forced a minimum confirmatory design of 18 distinct seen
cell-Q rows, not the initially considered 12. The frozen target crossed 18
seen cells with four formats and two semantic variants, plus two four-format
held-out cells: 152 slots.

The complete corrected campaign made 178 technically successful calls, 106
family candidates, 712 solver attempts, and 90 role judgments. Its funnel was:

```text
round 1: 38 families → 31 deterministic → 12 solver → 3 critic-pass
round 2: 35 families → 32 deterministic → 12 solver → 2 critic-pass
round 3: 33 families → 26 deterministic →  6 solver → 0 critic-pass
```

Only 5/38 whole families and 20/152 slots passed. They covered 4/20 cells,
6/18 KCs, seen-Q rank 3, and all-regime rank 4. The measurement critic accepted
9/30 critic-reached candidates, versus 29/30 linguistic and 24/30 product
decisions; 23/30 decisions were mixed across roles. Dialogue completion was
the weakest solver format (38/89 item gates; 50 solver responses failed to
match a key, with 59 responses flagged as reasonable but unkeyed).

This failure is not hidden by releasing a partial bank. It demonstrates that
linguistic target fidelity, solver answerability, measurement purity, and
platform surface plausibility are separate gates.

## 4. Controlled format and item nuisance

Because the curated bank failed, the quantitative experiment uses a separate
content-free instrument with the same full-rank slot geometry and categorical
format labels. It cannot validate actual task-format effects. It tests whether
the planted response process can make nuisance resemble KC granularity.

Models are A shared K*, B false format-split KCs, C shared K* plus format, and D
shared K* plus format and an aligned seen-item residual basis. Negative values
below favour the candidate named first. Intervals are learner-bootstrap
intervals conditional on one frozen fit/seed; the mean/range over three seeds
is descriptive.

| Controlled contrast | Mean (seed range) | Per-seed conditional intervals |
|---|---:|---|
| Format DiD: `(B-A)_strong - (B-A)_zero` | -.031551 [-.033431, -.029013] | all three exclude 0 |
| Explicit format: `C-B` in strong format | -.005317 [-.006034, -.004652] | all three exclude 0 |
| Aligned item positive control: `D-C`, item-only | -.013099 [-.013313, -.012698] | all three exclude 0 |
| Aligned item positive control: `D-C`, item+format | -.012609 [-.013506, -.011947] | all three exclude 0 |

The corrected DiD interpretation is important: negative means planted format
nuisance increases B's relative predictive advantage over A. It does not mean
B is psychologically correct. The frozen aggregate retained a generic sign
gloss that is wrong for this one contrast; the verified synthesis records this
append-only correction without changing the aggregate.

The zero-format control behaves as required: mean log loss is .657219 for A
and .664138 for B, so unnecessary splitting harms prediction. In the strong
format world, A/B/C means are .663597/.638965/.633648. Thus a false split can
absorb nuisance, but the explicit observed format model does better.

Important negative/boundary results:

- in the item-only world, B-A is +.001195, +.000847, and -.001328; every
  interval crosses zero. This extension does **not** support the claim that a
  false format split generally absorbs item difficulty;
- under combined learner/noise/learning heterogeneity, C-B is mixed across
  seeds and every interval crosses zero; the explicit format remedy is not
  uniformly demonstrated there;
- D-C remains negative in all combined-world seeds, but D is a positive
  control whose planted seen-item nuisance is constructed in exactly its
  representable span. It is not a general remedy and does not extrapolate to
  unseen item IDs;
- item-prerequisite state RMSE is an item-level nuisance-removed diagnostic,
  not per-KC mastery recovery. Full-v1 supplies the separate mastery-recovery
  study.

The quantitative result therefore supports a narrow but important statement:
**measurement nuisance can masquerade as learner-skill granularity in a
controlled world, and an observed nuisance variable can recover the shared
representation when the model is correctly specified.**

## 5. Structured errors versus binary correctness

All streams hold outcomes and non-error fields fixed and fit condition D using
only prior error history. Values are three-seed means with seed ranges.

| Observable stream | Log loss | Failed-KC top-1 | Secondary terminal-KC RMSE |
|---|---:|---:|---:|
| binary | .636359 [.634562,.637321] | .420781 [.419372,.421840] | .228727 [.225387,.230607] |
| linked positive control | .635493 [.633665,.636827] | 1.000 | .144357 [.141253,.146503] |
| linked on 80%, otherwise unresolved | .635833 [.634093,.636986] | .883728 [.883395,.883992] | .158804 [.155085,.160681] |
| within-item shuffled control | .636987 [.635169,.638011] | .462525 [.456719,.469783] | .165519 [.160795,.168737] |

Linked-vs-binary next-response improvements are small: the positive-control
deltas are -.001336, -.000897, and -.000368, and the third seed's interval
crosses zero. The 80% stream excludes zero in one of three seeds. The shuffled
control does not improve prediction and has poor learner-specific localisation.

The localisation result quantifies information destroyed by correctness for
multi-KC errors. It is also deliberately synthetic: `failed_kc` is a
post-outcome deficit-proportional attribution, not proof of a single causal
human failure. Shuffling still improves the secondary evidence-count RMSE over
binary because it distributes multi-KC failures instead of charging all active
KCs; therefore that RMSE alone cannot establish useful learner-specific error
information.

Surface error strings were not generated at scale. Without a release-valid
instrument and independent learner-corpus/expert validation, they would add
realism theatre rather than stronger evidence.

## 6. Assignment policy changes the observed history

The original confirmatory policy comparison was descriptive. The subsequent
A-D fits were frozen after response generation and after descriptive schedules
had been inspected; they are explicitly exploratory.

| Policy | Item-exposure Gini | Median repetition gap | D log loss | D item-state RMSE |
|---|---:|---:|---:|---:|
| Q-balanced lab | .162530 | 93.67 | .636359 | .129724 |
| curriculum | .162530 | 31.00 | .639779 | .139472 |
| mixed practice | .162530 | 92.00 | .636341 | .130748 |
| adaptive cell weakness | .080298 | 26.67 | .639477 | .141659 |

Curriculum-minus-lab D loss averages +.003420; two seed-specific conditional
intervals exclude zero and one nearly includes it. Mixed-minus-lab averages
-.000018 and every interval crosses zero. Adaptive-minus-lab averages +.003118;
one interval excludes zero. The transparent terminal-KC evidence diagnostic is
.228727/.229618/.229042/.237280 for lab/curriculum/mixed/adaptive.

Lab, curriculum, and mixed use the same occurrence multiset. With unconditional
order-independent learning they have identical terminal oracle mastery and
probe accuracy by construction, so their differences concern history encoding
and fit, not educational efficacy. Adaptive changes exposure and terminal
state, but the result still mixes selection, practice, outcomes, and model fit.
The policy is cell-history adaptive, not oracle-KC adaptive, and the logged
propensity is a design diagnostic rather than a complete off-policy solution.

## 7. Ecology--precision continuum

The automated dialogue pilot used four matched families, five openness levels,
and five independent role judgments per opportunity (20 opportunities, 100
judgments). Cloze versus open dialogue gives the clearest boundary:

| Dimension | Cloze | Open dialogue |
|---|---:|---:|
| interaction-naturalness pass | 17/20 | 20/20 |
| determinate | 17/20 | 0/20 (16 bounded, 3 materially ambiguous, 1 N/A) |
| KC attribution clear | 17/20 | 4/20 |
| shortcut available | 1/20 | 13/20 |
| plausible-response-family lower-bound mean | 1.30 | 4.55 |

Open-minus-cloze matched deltas were +1.00 determinacy risk, +.70 KC-attribution
risk, +3.25 plausible response families, +1.50 incidental grammar, and +.60
shortcuts, while naturalness risk fell by .15. Dialogue completion was not a
universal sweet spot: 14/20 shortcut judgments and only 3/20 clear KC
attributions. Critics disagreed on KC attribution for 14/20 opportunities and
platform plausibility for 12/20.

This supports a real methodological tradeoff, not a universal ordering of task
types: greater visible conversational naturalness can weaken the opportunity
boundary and scoring interpretation that KT needs. Human/expert validation is
still absent.

## 8. Dataset decision and real-data implications

### Decision

Do **not** release `grammar_kt_measurement_v1`. Retain:

- immutable full-v1 as the clean controlled reference;
- the failed matched-bank campaign as a construction negative result;
- the content-free six-world study as non-release sensitivity evidence;
- structured-error and dialogue pilots as bounded methodological evidence.

### Implications for future real collection

The combined evidence supports principles rather than synthetic numeric
prescriptions:

- render and validate the actual response mechanism, not only prompt text;
- cross KCs with multiple formats and semantic variants;
- separate item and format nuisance from KC identity;
- retain raw responses, accepted alternatives, scorer decisions, and structured
  errors rather than only correctness;
- record item exposure, policy ID/eligibility/propensity, context, and session
  order;
- include diagnostically distinct anchor opportunities rather than only more
  repetitions of one Q row;
- use non-updating probes where ethically/pedagogically appropriate;
- estimate learner/item/format heterogeneity from pilot data rather than calling
  planted simulator values human parameters;
- treat dialogue opportunity boundaries and repair sequences as annotations to
  validate, not one-turn defaults.

## Retained quantitative evidence

- controlled aggregate:
  `experiments/measurement_realism/worlds/controlled_instrument_v1/aggregate/results.json`
  (`06da0a0c2e297124234ad433caa0fd0d6f7924d5b13b707f4fed8ded9a81bfaf`);
- corrected cross-seed synthesis:
  `experiments/measurement_realism/worlds/controlled_instrument_v1/synthesis/`;
- exploratory policy plan/results:
  `experiments/measurement_realism/worlds/controlled_instrument_v1/policy_recovery_v1/`
  (plan `5a47ca244c57001ae353e4cc673754cac3df071631347fb79b1853ce3ad0f3e7`,
  results `29702c895ae9ba34cd0e1313514b23694572d3ca60b9629923b4713c5340a5c6`);
- dialogue report and verification:
  `experiments/measurement_realism/dialogue_pilot_live_v1/`;
- matched-bank negative-result package:
  `experiments/measurement_realism/design/bank_protocol/runs/matched_bank_v0_2_20260830/analysis/`.
