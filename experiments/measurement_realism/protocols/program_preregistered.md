# Measurement-realism methodology programme: staged protocol

Date frozen: 2026-08-30

Source revision: `f1a5eb29414dd03d173dbd9d0c4cb20762f2b259`

Protected reference: `data/grammar_kt_full_v1/`

## Scientific boundary

The frozen full-v1 benchmark remains the clean control world. No file below
`data/grammar_kt_full_v1/` may be changed. Extensions are downstream studies
until a separate release decision is made. GrammarCell, generator K*/Q*, the
measurement instrument, platform policy, observable behaviour, and model
hypotheses remain separate objects.

The programme asks two questions simultaneously:

1. Does a design preserve controlled latent truth and isolate its intended
   comparison?
2. Could its visible opportunity and event history plausibly be produced by a
   language-learning platform?

Plausibility scenarios constrain and stress-test the synthetic world. They are
not estimates of human parameters, and automated critics are not human or
expert validation.

## Stage 0: immutable reference replay

Before extension work, require:

- no Git diff under `data/grammar_kt_full_v1/`;
- exact Q* verification;
- exact observable/oracle event replay;
- release-manifest verification;
- the full scientific-contract test suite;
- independent RQ2, RQ3, and RQ4 headline replays.

Record the source commit and core hashes. Repeat the immutable-directory check
after every material experimental stage and at release.

## Stage 1: observable-bank audit

Audit every one of the 113 frozen items. Use four independent, explicitly
prompted non-human critic roles: learner perspective, language teacher,
platform product, and measurement. Retain each role's input, rendered prompt,
model/settings, raw output, parsed output, stderr, and hashes. Do not merge the
roles into one opaque score.

The shared dimensions are task comprehensibility, answer determinacy,
pedagogical plausibility, format plausibility, lexical simplicity, context
naturalness, difficulty plausibility, response-space plausibility, KC
measurement purity, and platform deployability. Judgments use categorical
`pass`, `minor_concern`, `major_concern`, or `not_applicable`; aggregate counts
are diagnostics rather than validated prevalence estimates. Report item-level
disagreement and inspect examples from every final disposition, campaign,
GrammarCell complexity, and rare/common KC stratum.

The mutually exclusive deployment disposition is:

- `usable_as_is`;
- `minor_ui_or_answer_set_change`;
- `pedagogically_artificial`;
- `problematic_answer_space`;
- `probably_not_deployable`.

## Stage 2: KC audit and alternative worlds

Evaluate the 18 declared KCs against linguistic coherence, reuse, independent
mastery interpretation, measurement support, distinguishability, parsimony,
compositionality, and pedagogical relevance. Structural facts (support,
co-occurrence, rank, activation equivalence) are deterministic. Pedagogical
interpretations remain explicit non-human judgments.

Retain operation-based K* as the clean reference unless a critical construction
error is found. Compare, as downstream generator-world sensitivity rather than
claims of psychological truth, an outcome-free feature-value world and a
preregistered interaction-rich world. Canonicalise candidates by activation on
the 75 cells before comparing names.

## Stage 3: matched measurement bank

Select GrammarCells without learner outcomes. The selected cells must jointly:

- cover all 18 KCs;
- retain full K* column rank;
- include rare KCs, one- and multi-KC rows, active/passive, positive/negative,
  declarative/question/imperative, modal/non-modal, and simple/stacked aspect;
- include seen and held-out grammar for audit, while acquisition uses seen
  cells only;
- avoid selecting solely because a downstream model performs well.

Generate matched families in a compact declared set of formats:

- constrained cloze;
- multiple choice with one keyed option and plausible distractors;
- sentence transformation;
- short dialogue completion.

Within a family, GrammarCell and Q row are identical across formats. Each item
must explicitly store instruction, context, stimulus, response mechanism,
target, accepted answers or options, format, cell, family, and provenance.
Generation uses audited `gpt-5.6-sol` calls at medium reasoning. Independent
validation uses audited `gpt-5.6-terra` calls at medium reasoning. Deterministic
schema, option, answer-containment, Q-projection, coverage, and rank gates run
separately from model judgment. Raw generations are immutable; rejected items
are retained; no silent repair is permitted.

Hard release gates are linguistic validity, answer determinacy, learner
usability, and a defined response mechanism. Pedagogical/platform plausibility
is reported separately and cannot be rescued by Q rank. A matched family is
eligible only when every retained format passes the hard gates.

## Stage 4: controlled response worlds

Use separate worlds, common keyed latent draws, and at least three seeds:

- `clean_zero_format`: no item or format effects;
- `item_difficulty`: stable centred item logit offsets;
- `format_effect`: centred format offsets with format-specific guess/slip;
- `learner_heterogeneity`: bounded learner ability, learning-rate, and
  guess/slip variation;
- `combined_plausibility`: item, format, and learner variation together;
- `structured_error`: the combined world plus observable error categories.

Parameter magnitudes are literature-constrained scenarios, not human
estimates. The response probability, learning rule, and every latent draw are
declared. Observable rows contain only fields a platform could ordinarily log;
mastery, item/format effects, response probability, draw, and failed KC remain
private oracle fields.

## Stage 5: format-confounding experiment

Primary hypothesis: planted measurement nuisance can make a false
format-specific skill split predict better than a shared K* model, while an
explicit nuisance model can recover the shared representation's predictive
performance without redefining learner knowledge.

Compare on identical rows:

- A: shared K*, no format covariate;
- B: false format-specific split KCs;
- C: shared K* plus observable format covariates;
- D: shared K* plus item and format effects.

The zero-format world is the negative control. A deliberately strong planted
format effect is the positive control. Use held-out learners, event-weighted
log loss, Brier score, ECE, AUC, accuracy, learner-paired intervals, and oracle
mastery recovery. A predictive gain for B never establishes a truer ontology.

## Stage 6: platform policy

Keep a Q-balanced laboratory schedule. Compare it with transparent curriculum,
mixed-practice, and recent-error adaptive schedules. All policies use the same
bank and learner world. Report exposure/support, repetition/spacing, selection
dependence, accuracy trajectories, and downstream recovery. Do not build a
general recommender.

## Stage 7: structured errors

On incorrect responses, sample a failed active KC with probability proportional
to `1 - mastery`, with a deterministic weakest-KC alternative as sensitivity.
Map failed KCs to declared linguistic error families. Compare binary-only
history, informative observed error categories, and within-item shuffled error
labels. Evaluate next-response prediction, calibration, oracle mastery RMSE,
and failed-KC localisation. The shuffled-label condition is the negative
control. Surface error text is only a qualitative pilot unless independently
validated; it is not required for a release.

## Stage 8: dialogue continuum

For matched structures, compare cloze, transformation, contextual completion,
dialogue completion, and a small open-dialogue pilot. Audit determinacy,
incidental grammar, lexical nuisance, plausible-response coverage, and KC
attribution. Treat any loss of measurement precision as a result, not as an
item-generation failure to conceal.

## Dataset-release decision

Freeze a separate versioned dataset only if the crossed bank passes hard gates,
observable/oracle schemas remain cleanly separated, all KCs retain meaningful
support and rank, event histories pass qualitative inspection, and deterministic
reconstruction succeeds. Otherwise retain the work as controlled experiments.

## Paper decision rule

The dataset is an experimental instrument. The main claim may shift from
dataset construction to controlled analysis only if the retained results show
which clean-control findings survive measurement nuisance and what information
real platform logs should preserve. Every claim must name its world and its
external-validity boundary.

