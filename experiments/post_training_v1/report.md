# Active-architecture post-training investigation

Date: 2026-08-25. Base commit: `c3e6508d39b3a3e5fa0a42a1f5079697f4fb37e1`.

## Executive conclusion

The active pipeline can expose a well-provenanced **pointwise generation
verifier view**, and the proposed JSONL schema is workable. This pilot does
**not** support releasing generation preferences or claiming downstream
post-training utility.

After repairing two validator-ontology defects and excluding one opportunity
generated under an erroneous `lets_not` measurement rule, all 102
release-eligible, schema-valid candidates were structurally valid. The remaining
21 failures were generation/output-contract failures, which the protocol
correctly forbids as training negatives. There were therefore zero educational
near-miss pairs and only one verifier class: 74/74 development records and
28/28 held-out records were positive. The preregistered ranker/reranker could
not be trained, so no downstream gain was demonstrated.

The restrained finding is:

> Grammar-KT can serialize structurally grounded verifier records, but this
> active-architecture pilot did not naturally produce trustworthy negative
> supervision and therefore did not demonstrate downstream post-training value.

## A. Literature conclusion

### FEAT

[FEAT](https://aclanthology.org/2025.acl-short.45/) ranks short teacher feedback
for an incorrect multiple-choice response in an MCTest reading-comprehension
dialogue. It contains three related datasets:

- DIRECT-Manual (DM): five feedback candidates from human and model sources,
  ranked by humans on Correctness and Revealingness; higher/lower ranked
  candidates yield chosen/rejected pairs. The reported split is 5,025 train and
  475 test pairs.
- DIRECT-Generated (DG): feedback from GPT-4o, Claude 3.5 Sonnet, and
  Llama-3.1-70B generated with and without five criteria—Correct, Revealing,
  Guidance, Diagnostic, Encouragement. “With criteria” is designated chosen
  and “without criteria” rejected by construction, not by an independent
  per-pair human comparison. The reported split is 3,996/444.
- DIRECT-Augmented (DA): DG plus 5–100% of DM.

FEAT trains binary pair classifiers, scalar reward models, DPO rankers,
RankNet, and an ensemble using 1B/3B Llama and Qwen backbones. Evaluation is
rank-biased overlap with held-out human DM rankings, over five seeds. Several
Llama-3B-IT approaches using DG plus 5–10% DM exceed the corresponding
DM-only ranking result. This is evidence that synthetic preference-shaped data
plus a small human-ranked set can improve a **feedback ranking task**. It is not
evidence of better generated feedback, learner gains, grammar control, KT, or
the superiority of DPO over simpler supervision.

The official FEAT release was previously pinned and audited at commit
`c598a7b6f52e5b3b22fa31fd5c40024d93f37e3f`; its DG internal split has heavy
context overlap, although FEAT's central DG/DA claims evaluate on independently
human-ranked DM, so that overlap does not invalidate the main comparison. See
[`literature/feat_release_audit.json`](../post_training/literature/feat_release_audit.json).

### Closest methodological precedents

- [More Insightful Feedback for Tutoring](https://aclanthology.org/2024.emnlp-main.605/)
  adds preference optimization for answer-adaptive feedback and evaluates
  faithfulness/revealingness proxies plus a human subset. It reinforces that
  diagnostic correctness and answer revealingness must be separated.
- [Improving Socratic Question Generation](https://aclanthology.org/2024.bea-1.10/)
  uses targeted invalid-question types and DPO to avoid specific pedagogical
  failures. This is the closest precedent for typed, plausible negatives.
- [SMART](https://aclanthology.org/2024.emnlp-main.786/) collects both expressed
  and observed preferences from learners and finds that they disagree. It is a
  warning against treating plausible automated pedagogy scores as learning
  outcomes.
- Verifier/best-of-N work supports learned candidate selection, but only when
  labels are trustworthy and both classes exist. It does not make arbitrary
  failures useful negatives.

The transferable FEAT lesson is narrow: additional educational ranking
supervision earns a dataset claim only after a downstream ranking improvement
against independently meaningful labels. This pilot does not clear that bar.

## B. Active-pipeline supervision map

The active path is:

```text
GrammarCell
  -> MeasurementOpportunity
  -> constrained LLM generation attempt
  -> hard schema/reference checks
  -> blind structural reconstruction
  -> separate quality diagnostics
  -> accepted item or retained rejection
```

Information available **before validation**:

- the stable opportunity and canonical cell IDs;
- exact six-field cell, structural conditions, expected operations, source
  descriptor IDs, and coverage reasons;
- generator ID/family/config, fully rendered prompt, backend/model, attempt
  number/history, raw response, parsed response, events, stderr, and invocation
  metadata;
- for schema-valid output, content, target answer, accepted answers, surface
  item ID, and empty validation fields;
- for generation failure, opportunity/generator/attempt history plus all raw
  evidence on disk.

Information available **after validation**:

- hard-check outcome;
- blind recovered cell, operations, predicate class, and agreement site;
- exact mismatch reasons against the pre-existing opportunity;
- independent quality fields (naturalness, ambiguity, suitability,
  world-knowledge/lexical flags, and dialogue diagnostics);
- evaluator identity, repetitions, raw judge outputs, attempt logs, and a flag
  confirming that the intended target was hidden;
- accepted/rejected disposition and accepted-item-bank fingerprint.

Quality is deliberately diagnostic and does not gate structural acceptance.
Standalone and dialogue generators share the same opportunity interface and
produce different item IDs over the same latent target. Folds and simulation
are keyed by canonical cell/opportunity, so format transfer does not change the
measurement or KC logic. No archived deterministic realiser was used.

Conceptually, the derived view remains downstream:

```text
MeasurementOpportunity
  +-- accepted item --------------------> KT dataset
  +-- attempts + blind validation ------> possible post-training view
```

## C. Dataset proposal

The minimal pointwise schema is defensible:

```json
{
  "record_type": "generation_verifier",
  "context": {"measurement_opportunity": {}},
  "candidate": {
    "attempt_id": "...",
    "item_id": "...",
    "item_family": "standalone_completion",
    "content": {},
    "target_answer": "...",
    "accepted_answers": []
  },
  "labels": {
    "structurally_valid": true,
    "taxonomy": "A_valid_target_realization",
    "mismatch_dimensions": [],
    "reasons": [],
    "blind_reconstruction": {},
    "quality_diagnostics": {}
  },
  "provenance": {}
}
```

The corresponding preference schema is implemented in the exporter but v1
emits no records:

```json
{
  "record_type": "generation_preference",
  "context": {"measurement_opportunity": {}},
  "chosen": {},
  "rejected": {},
  "preference": {
    "reason": "chosen preserves the fixed target; rejected is a plausible structural near miss",
    "rejected_taxonomy": "B_fluent_wrong_target",
    "structural_dimensions": {"aspect": "mismatch"},
    "label_source": "active blind structural reconstruction"
  },
  "validation": {"chosen": {}, "rejected": {}},
  "provenance": {"split_unit": "CELL_...", "post_training_split": "train"}
}
```

Inclusion requires an accepted, quality-adequate chosen item and a fluent,
schema-valid rejected item with completed blind reconstruction and an actual
target-preservation mismatch. API, JSON, empty, contract, hard-reference, and
diagnostic-exhaustion failures are excluded.

## D. Candidate-pool analysis

The frozen pilot sampled three candidates for 42 opportunities (at most two
per each of 24 cells). The frozen reference fold yielded 30 development and 12
held-out opportunities; 25 were standalone and 17 dialogue.

| Quantity | Result |
| --- | ---: |
| Raw attempts | 126 |
| Schema-valid candidates | 105 |
| Generation/output-contract failures | 21 |
| Scientifically excluded attempts | 3 (one stale `lets_not` opportunity) |
| Release-eligible candidates with completed validation | 102 |
| Structurally valid among those 102 | 102 (100%) |
| Valid including all release-eligible raw attempts | 102/123 (82.9%) |
| Standalone raw acceptance | 57/75 (76.0%) |
| Dialogue raw acceptance | 45/51 (88.2%) |
| Opportunities with valid + any raw failure | 7 |
| Opportunities with valid + educational structural negative | 0 |
| Possible eligible pairs | 0 |
| Released preference pairs | 0 |
| Exact duplicate instances | 1; 104 unique surfaces among 105 candidates |

Coverage spans all 24 cells: present/past/NA; all four aspect values; active
and passive; both polarities; declarative, polar-question, and imperative;
and the `would` modal. Surface vocabulary has 2,444 tokens, 247 types
(type/token 0.101), and distinct-bigram ratio 0.354. These descriptive measures
do not establish educational diversity.

Final release-eligible taxonomy:

| Type | Count | Training use |
| --- | ---: | --- |
| A valid target realization, quality pass | 81 | positive verifier record |
| E structurally valid, quality concern | 21 | positive structural label; keep quality vector separate |
| F generation/output-contract failure | 21 | retained raw evidence; excluded from supervision |
| B/C/D educational structural near miss | 0 | none available |

### Leakage policy

Splitting occurs at `canonical_cell_id`, before pairs. The existing frozen fold
assigns 16 cells to development, seven to compositional holdout, and one modal
cell to novel-feature holdout. All attempts/pairs inherit the cell split; train
and evaluation cell overlap is empty. The chosen and rejected sides of any
future pair must have the same opportunity and therefore the same split.

### Audit and discovered validity defects

The first 22 apparent pairs were all invalid. Every rejected candidate was
plausible, but the blind evaluator had reconstructed the correct cell and used
free-form aliases (`do-support`, `past_perfect`,
`perfect_auxiliary_had`) instead of the measurement ontology. Thus 0/22 was a
true structural preference. One candidate was answer-ambiguous, but v1 did not
define quality-only preferences. The audit invalidated the pairs before
training.

Three active defects were repaired:

1. transport schemas used unsupported `uniqueItems`; uniqueness remains
   enforced at Python boundaries, including a new duplicate-operation check;
2. blind validation did not define its closed operation or canonical
   tense/agreement ontology;
3. measurement incorrectly assigned `do_support` to `let's not`; the rule is
   fixed and regression-tested, while candidates generated under the old
   target are excluded.

Pre-repair data, logs, and amendment chronology remain in `data/pilot_v1/` and
the preregistration. These are methodological findings, not usable negatives.

## E. Utility experiment

**Frozen hypothesis.** A context-plus-candidate TF-IDF logistic verifier trained
on development cells would improve held-out best-of-3 accepted-item rate over
first/random selection and beat a candidate-only ablation on pairwise accuracy.

**Planned model.** Word (1,2) and character (3,5) TF-IDF; balanced logistic
regression; `C` selected from `{0.1, 1, 10}` by canonical-cell GroupKFold;
context-feature/token interaction terms; CPU-only scikit-learn.

**Planned metrics.** Accuracy, balanced accuracy, AUROC, Brier score, pairwise
accuracy, best-of-3 accepted rate, and a 10,000-resample opportunity-cluster
bootstrap CI against first-candidate selection.

**Result.** Not run: the development export contains 74 positives and zero
negatives; held-out contains 28 positives and zero negatives; preference count
is zero. A classifier, AUROC, pairwise accuracy, reranking comparison, and
confidence interval are undefined. All preregistered gain gates are false.
Treating the 21 contract failures as negatives would manufacture a trivial task
and violate the protocol.

Therefore the model-level result is **no demonstrated downstream gain**. This
is lack of testable supervision, not evidence that a verifier would never work
with a better candidate pool.

## F. Example records and exclusions

### Valid pointwise verifier record

For `OPP_09F87B8452792126` (present, simple, active, negative declarative;
third-person plural; `do_support + negation`):

```text
Prompt: The children ___ TV after dinner. (not / watch)
Answer: The children do not watch TV after dinner.
Blind recovery: exact cell; [do_support, negation]; lexical_transitive; site=do
Quality: naturalness 5, ambiguity false, suitability 5
Label: structurally_valid=true
```

Full record: `ATTEMPT_23C48A20E67138F7` in
`data/pilot_v1/generation_verifier.jsonl`.

### Apparent difficult pair that was correctly excluded

The original validator preferred one past-perfect-progressive item over:

```text
By the time I got home, Anna ___ the kitchen for an hour. (clean)
Answer: had been cleaning
```

The evaluator recovered the exact intended cell but returned `operations: []`
in one early run, while another returned free-form operation descriptions.
After the closed ontology was supplied, this candidate passed. It is a useful
validator-reliability example, not a preference pair.

### Trivial failure excluded from training

One raw generator output set `target_answer` to `have not sent` but listed only
`haven't sent` under `accepted_answers`. The active record boundary requires the
target answer itself to occur in the accepted list. The full raw output and
contract rejection are retained; this is not an educational near miss.

### Measurement defect excluded

The pre-fix `lets_not` opportunity requested `do_support`, leading to the
unnatural answer “Don't let's leave the door open at night,” while natural
“Let's not open…” candidates conflicted with the erroneous target. All three
attempts for `OPP_3B82359745F83047` are retained and excluded.

There are no representative good or difficult *true* preference pairs because
none survived audit. Inventing examples would misrepresent the result.

## G. Decision

### Ready for dataset release

- Existing accepted items, raw attempt evidence, and validation provenance.
- The experimental `generation_verifier` **schema** and 102 positive records,
  clearly described as a positive-only view, not a trainable verifier dataset.
- The closed structural-validation ontology and corrected `lets_not` rule.

### Promising but not ready

- Generation verifier/preference supervision. A next pilot should deliberately
  increase informative error yield without scripting the answer: use a weaker
  or less constrained generator, higher sampling diversity, more samples per
  opportunity, and/or a target-blind corruption/contrast generator. Any
  targeted negative must still undergo independent blind reconstruction and
  human audit.
- Quality-based preferences. The 21 quality-flagged but structurally valid
  items show a possible second axis, but model-only naturalness/ambiguity scores
  are not sufficiently grounded for release as gold pedagogy.
- Format-transfer ranking. There are both formats, but no negative class and no
  cross-format utility test.

### Not justified

- A claim that Grammar-KT currently provides useful preference training data.
- A claim of ranker, verifier, best-of-N, DPO, or post-training gain.
- FEAT-style feedback preferences: the active dataset has no authentic learner
  error text and no human-grounded correctness/guidance/revealingness labels.
- Pedagogical-quality or learner-gain claims.
- RLHF/RLAIF, DPO, or any larger training stack on this pool.

## Reproducibility

Preregistered commands:

```bash
PYTHONPATH=src .venv/bin/python experiments/post_training_v1/scripts/run_pilot.py prepare
PYTHONPATH=src .venv/bin/python experiments/post_training_v1/scripts/run_pilot.py collect
PYTHONPATH=src .venv/bin/python experiments/post_training_v1/scripts/run_pilot.py revalidate
PYTHONPATH=src .venv/bin/python experiments/post_training_v1/scripts/run_pilot.py analyse
PYTHONPATH=src .venv/bin/python experiments/post_training_v1/scripts/run_pilot.py evaluate
```

Generation used `gpt-5.6-luna` at low reasoning; blind validation used
`gpt-5.6-terra` at low reasoning. Snapshot and decoding parameters were not
pinned, which is recorded as a reproducibility limitation. The final selected
evidence comprises 330 model invocations, 4,580,821 reported input tokens
(2,903,552 cached), 49,475 output tokens, 25,521 reasoning tokens, and 2,955.3
summed invocation-seconds. The backend exposes no monetary cost schedule.

Primary artifacts:

- `protocols/preregistered.md`: frozen protocol and timestamped amendments;
- `data/pilot_v1/manifest.json`: split/selection fingerprints;
- `data/pilot_v1/candidate_attempts.jsonl`: every final attempt disposition;
- `data/pilot_v1/evidence/`: prompts, raw outputs, events, stderr, and invocations;
- `data/pilot_v1/generation_verifier.jsonl`: positive-only pointwise view;
- `data/pilot_v1/generation_preference.jsonl`: empty by design after audit;
- `results/pilot_v1/candidate_pool_summary.json`: final analysis;
- `results/pilot_v1/manual_audit_result.json`: audit decision;
- `results/pilot_v1/utility_experiment.json`: preregistered non-run result.
