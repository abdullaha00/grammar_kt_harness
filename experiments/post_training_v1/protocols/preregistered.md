# Preregistered active-architecture protocol

Frozen before the first pilot candidate was generated. Date: 2026-08-25.
Repository commit before experiment files: `c3e6508d39b3a3e5fa0a42a1f5079697f4fb37e1`.

## Scope and research questions

**RQ1.** Can active Grammar-KT measurement opportunities plus blind validation
produce non-trivial generation-verifier and preference supervision?

**RQ2.** Does a lightweight verifier trained on development-cell attempts
improve best-of-3 selection on frozen held-out canonical cells?

Feedback preference generation is not part of this pilot. The active pipeline
has no authentic learner response/error text or human-grounded pedagogical
feedback labels. This is a readiness decision, not a negative result selected
after seeing generation outcomes.

## Experiment 1: candidate-pool feasibility

**Research question.** Does ordinary repeated sampling from the active LLM
generator naturally create accepted candidates and plausible structural near
misses for the same measurement opportunity?

**Hypothesis.** At least 20 non-trivial accepted-vs-near-miss pairs will be
available, spanning at least three structural rejection dimensions.

**Motivation.** Preferences are useful only when the rejected response is a
plausible educational output, not an API, JSON, empty-output, or obvious-garbage
failure.

**Inputs.** Active canonical cells from `runs/base/canonical/canonical_cells.jsonl`;
active measurement builder; frozen `modules/folds/reference_v0.json`; active
standalone/dialogue prompts and output schemas; active blind structural and
quality validation.

**Sampling.** Select at most two opportunities per canonical cell, prioritising
the lexical-transitive, third-person-singular baseline and then stable
opportunity ID. Generate three independent candidates per selected opportunity.
Assign format by the deterministic SHA-256 rule in `configs/pilot_v1.json`,
targeting approximately two standalone opportunities per dialogue opportunity.

**Independent variable.** Candidate generation attempt under a fixed
measurement opportunity.

**Dependent variables.** Generation success, blind structural acceptance,
recovered-vs-intended dimensions, separate quality diagnostics, duplication,
lexical diversity, and pair eligibility.

**Controls.** Fixed prompts/schemas/configuration; target grammar chosen before
generation; validator receives no intended target; three attempts per
opportunity; all raw outputs and failures retained.

**Split.** Frozen canonical-cell fold. Development cells are training only.
Compositional and novel-feature holdout cells are evaluation only. All attempts
and all pairs for one opportunity inherit its cell split. No random record-level
split is permitted.

**Metrics.** Opportunity/candidate counts; accepted/rejected and rates; reason
taxonomy; mixed-validity opportunities; possible and eligible pairs;
duplicates; distinct-n/total-n lexical diversity; format and grammar-feature
coverage.

**Pair inclusion.** Chosen is structurally accepted. Rejected must be
schema-valid and fluent/plausible, have a completed blind reconstruction, and
fail target preservation through `cell_mismatch`, `operations_mismatch`,
`predicate_class_mismatch`, or `agreement_site_mismatch`. Category C
(ambiguous measurement) is eligible only if the quality evaluator marks answer
ambiguity. Hard schema/reference, generation/API/JSON, empty, and diagnostic
exhaustion failures are excluded. Quality-only differences are not preference
labels in v1.

**Decision criterion.** Dataset-level preference readiness requires at least 20
eligible pairs, at least three structural error dimensions, at least 10 mixed
opportunities overall, and at least 80% correctness/plausibility in an
author audit of a stratified sample of up to 30 pairs. If not met, retain only
pointwise verifier records and classify preferences as not ready.

**Exact planned commands.**

```bash
PYTHONPATH=src .venv/bin/python experiments/post_training_v1/scripts/run_pilot.py prepare
PYTHONPATH=src .venv/bin/python experiments/post_training_v1/scripts/run_pilot.py collect
PYTHONPATH=src .venv/bin/python experiments/post_training_v1/scripts/run_pilot.py analyse
```

## Experiment 2: held-out verifier-guided best-of-3

**Research question.** Does Grammar-KT validation supervision improve candidate
selection on unseen canonical grammar cells?

**Hypothesis.** A verifier trained only on development-cell candidates will
improve held-out accepted-item rate over first-candidate selection and random
selection, and will exceed a candidate-only verifier on held-out pairwise
accuracy.

**Motivation.** This is the smallest direct test of whether the additional
supervision has operational value; it does not require LM fine-tuning.

**Inputs.** Schema-valid candidates with completed blind validation. The main
training label is structural acceptance. Generation/format failures are
excluded because they create trivial shortcuts. Quality diagnostics are not
features of the main model because they require a validator at inference time.

**Independent variable.** Selection rule: first candidate; random candidate
(seeded Monte Carlo expectation); naturalness-only diagnostic oracle baseline;
candidate-only TF-IDF logistic verifier; context-plus-candidate TF-IDF logistic
verifier trained on Grammar-KT records.

**Dependent variables.** Candidate-level accuracy, balanced accuracy, AUROC,
Brier score, pairwise accepted-vs-near-miss accuracy, and opportunity-level
best-of-3 accepted-item rate. Rejection-type confusion is reported.

**Controls.** Same training rows, regularisation search fixed to
`C ∈ {0.1, 1, 10}` using development-cell GroupKFold only; class-weight
`balanced`; word `(1,2)` plus character `(3,5)` TF-IDF; fixed random seed. The
candidate-only ablation omits the measurement context but otherwise uses the
same pipeline.

**Split.** Train and model selection use only the 16 development canonical
cells. Final evaluation uses only the seven compositional and one novel-feature
holdout cells. Confidence intervals use 10,000 cluster bootstrap resamples over
held-out measurement opportunities. No attempt from a held-out cell enters
vocabulary fitting, hyperparameter selection, or training.

**Metrics and decision criterion.** The supervision is considered to show a
small downstream gain only if (i) context-plus-candidate pairwise accuracy is
above 0.50, (ii) best-of-3 accepted rate exceeds both first-candidate and seeded
random-choice rate, and (iii) the opportunity-cluster 95% bootstrap interval
for improvement over first candidate excludes zero. Otherwise report no
demonstrated gain. Candidate-only comparison is diagnostic, not a mandatory
gate, because surface cues may legitimately generalize.

**Exact planned command.**

```bash
PYTHONPATH=src .venv/bin/python experiments/post_training_v1/scripts/run_pilot.py evaluate
```

No DPO, RLHF, feedback generation, or pedagogical/learner-gain claim is planned.

## Infrastructure amendment 1 (before any candidate output)

The first collection invocation returned HTTP 400 for every completed unit
because the Codex structured-output API rejects the JSON Schema keyword
`uniqueItems`. No candidate text was produced. The run was stopped, and all 59
completed infrastructure-failure records and invocation logs were retained.
Before retrying, `uniqueItems` was removed from the three active transport
schemas; the existing Python boundary validation still enforces unique accepted
answers, and duplicate-operation rejection was added to `_parse_structure` so
scientific semantics are unchanged. Collection revision 2 creates new attempt
IDs and evidence directories. The hypotheses, split, models, metrics, and
decision criteria above were not changed.

## Infrastructure amendment 2 (before model training/evaluation)

The first author audit of the completed pool showed that the blind structural
prompt did not define the measurement module's closed operation vocabulary.
The evaluator therefore returned correct but free-form aliases such as
`do-support`, `past_perfect`, or `perfect_auxiliary_had`; exact comparison to
`do_support` or `perfect` falsely rejected valid items. The original candidate
outputs and faulty judgments are retained. The structural prompt and schema now
declare the closed active operation ontology, and the parser rejects unknown
operation labels. The same frozen candidates will be blindly revalidated under
revision 2; no target cell or expected-operation list is exposed to the
evaluator. Candidate sampling, split, hypotheses, and downstream decision
criteria remain unchanged. Exact amendment command:

```bash
PYTHONPATH=src .venv/bin/python experiments/post_training_v1/scripts/run_pilot.py revalidate
```

## Infrastructure amendment 3 (before model training/evaluation)

Revision-2 audit found that the prompt also omitted two canonical conventions:
modal and imperative cells use `tense: NA`, and imperatives use
`agreement_site: none`. These omissions caused otherwise correct blind outputs
to fail cross-field validation or mismatch. The active measurement derivation
also incorrectly attached `do_support` to the `lets_not` subtype. The derivation
is corrected and regression-tested. Because candidates for
`OPP_3B82359745F83047` were generated under the erroneous old target, that
opportunity and its three attempts are retained as raw evidence but excluded
from verifier/preference export and utility evaluation. Validation revision 3
reruns the same frozen pool with explicit label conventions. No outcome-based
example selection, split change, model change, or decision-criterion change was
made.
