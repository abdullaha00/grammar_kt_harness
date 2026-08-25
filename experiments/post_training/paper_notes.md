# Research-ready paper notes

## Working title

**One Grammar Opportunity, Multiple Learning Signals: Evaluating Structured
Grammar and Knowledge-Tracing Supervision for Language-Tutoring LMs**

## Motivation

Synthetic tutoring corpora often begin with unconstrained model-generated
dialogue and then use another model to judge it. This makes it difficult to know
which pedagogical distinction was learned and whether train/test examples share
the same latent content. Grammar-KT offers a complementary starting point: a
typed grammar opportunity produces deterministic realizations, exercise items,
KC/Q-matrix projections, and observable learner histories with traceable source
provenance. The research question is whether those representations add a
learnable signal beyond prose instructions—not whether a more complicated
alignment algorithm can be attached to the pipeline.

## Related-work position

- FEAT shows that synthetic preference feedback plus a small human-ranked
  component can train economical **feedback rankers**, but its task is MCTest
  multiple-choice reading feedback and its main evaluation is ranking agreement.
- Educational DPO work on Socratic questions and answer-adaptive feedback shows
  that targeted invalid outputs can be useful; it does not eliminate the need
  for SFT and filtered-generation baselines.
- EXPECT and GEE support separating grammar-error diagnosis/evidence from
  explanation generation.
- KT-conditioned exercise generation and Dialogue-KT connect learner state to
  generation or dialogue inference, but neither makes a synthetic Grammar-KT
  trajectory an optimal tutor policy.
- LongTutor and recent student-simulation audits motivate explicit state-use
  evaluation and warn against circular simulator-only evidence.
- General post-training results motivate the order SFT → verified sampling →
  small preference ablation; RL requires a credible sequential environment.

Candidate contribution: a single provenance graph yields several independently
evaluable post-training signals—exact positives, feature-level counterfactuals,
KC projections, and learner-state contexts—while preserving the separation
between latent grammar, interaction format, KT representation, and tutor policy.
This is an integration claim to verify against a fuller systematic review, not
a claim that no prior work has combined any pair of these elements.

## Methodology

### Latent unit

Let (g) be a typed grammar cell, (r) a valid realization condition, (R) a
language-specific deterministic realizer, (K(g,r)) the frozen KC projection,
and (p) the complete provenance chain. A positive is (y^+=R(g,r)). A
structural negative is (y^-=R(g',r)), where (g') is valid, shares nuisance
conditions, and differs from (g) on exactly one named feature.

Derived views:

- SFT: `(instruction, g, r, optional K/state) → y+`;
- diagnosis: `(exercise, y-) → feature delta, missing/extraneous KCs`;
- verifier: `(context, candidate) → independent structural dimensions`;
- preference: `(context, y+, y-, named distinction)`;
- state-action: `(observable state/history, candidate actions) → action`, only
  once an external action label or outcome exists.

### Split discipline

Partition the provenance graph before deriving records. Report lexical
transfer, format transfer, compositional cell holdout, novel feature/KC, and
source-descriptor holdout separately. A preference belongs to evaluation if
either target or rejected cell is held out. Do not expose stable IDs or gold
cells/KCs in inference tasks.

### Training comparison

For a small open instruction model with a pinned revision:

1. instruction/base model;
2. natural-language-description SFT;
3. canonical/spec SFT with the same examples/tokens as closely as possible;
4. structured SFT + verifier-filtered best-of-N;
5. optionally structured SFT + IPO (and DPO if budget permits), using only
   validated hard near misses.

Use default/documented training settings, one seed initially, then repeat only
the smallest comparison if the effect passes the predeclared practical
threshold. The question is signal value, not hyperparameter skill.

## Proposed research questions

1. Does structured SFT improve exact target-KC realization and grammar
   judgement on held-out lexicalizations and cells?
2. Does raw canonical/spec conditioning add value beyond semantically
   equivalent prose on a non-ceiling benchmark?
3. Do structural preferences improve hard feature-error rejection beyond SFT
   and verifier-filtered best-of-N?
4. Can exact synthetic feature diagnosis transfer to a small authentic learner
   error set, and does diagnosis improve human-rated feedback targeting?
5. With external action targets/outcomes, does observable KT state improve
   structured pedagogical action selection over history-only and shuffled-state
   controls?

RQ1–RQ3 are the core paper; RQ4 is the strongest bridge to real language
learning; RQ5 should not be claimed from the current simulator.

## Completed pilot setup

The preregistered feasibility run used a historical 24-cell canonical inventory
and regenerated all current downstream artifacts at commit
`f8e810e478d32c782649f5fa575a124e842d465c`, seed 20260825. A model diagnostic
used `gpt-5.6-luna` at low reasoning through Codex CLI 0.149.1. The hosted model
snapshot and decoding were not pinned. Exact prompts, outputs, schemas, events,
timestamps, runtimes, hashes, and commands are retained.

## Pilot results

| Finding | Result | Claim allowed |
| --- | ---: | --- |
| Derived records | 644 SFT, 132 preference, 264 verifier | Current artifacts can express multiple structural training views |
| Pair validity | 132/132 | Pairs satisfy declared Hamming-one/current-realizer invariants |
| Pair coverage | aspect 60, tense 36, polarity 24, clause 12 | Four dimensions observed; voice/modal not covered |
| Surface shortcut | grouped char n-gram accuracy 0.50 | No response-only orientation cue in the symmetric construction; not a quality result |
| Zero-shot generation | 24/24 exact in all three conditions | Benchmark is ceiling-level; no representation advantage established |
| Judge validity/order | 48/48 twice; 0 order inconsistencies | Structural distinction legible to one judge; no human/pedagogical validation |
| SFT/preference training | not run by design | No claim of post-training gain |
| RL | not run by design | Current simulator cannot support a tutoring-policy claim |

## Experimental setup for a compelling follow-up

1. Expand the controlled space to several lexical frames per cell and at least
   five formats: transformation, cloze, minimal pair, correction, judgement.
2. Construct graph-component splits with unseen lexicon, unseen format, and
   compositional cell holdout. Confirm base-model performance is below ceiling.
3. Run the five-condition comparison above. Primary outcomes: exact/parsed
   target-cell match and hard-negative rejection. Secondary: per-feature
   confusion, format compliance, diversity, validator yield, and calibration.
4. Human-audit a stratified structural-pair subset. For feedback experiments,
   separately rate grammatical accuracy, misconception target, usefulness,
   revealingness, and level fit; do not use a global quality score.
5. If authentic learner errors are available, freeze the synthetic-trained
   model before evaluating transfer. Do not tune on the human test subset.

Practical decision criterion: structured supervision earns a pipeline role if
it improves held-out structural accuracy by a predeclared margin (for example
≥5 absolute points with paired confidence intervals) over prose-SFT and the
improvement is not explained by a prompt/template overlap audit. Preference
optimization earns a role only if it improves hard-negative rejection over
both SFT and verified best-of-N without reducing positive validity.

## Limitations to state explicitly

- The archived source/canonical run is historical; the absent external EGP
  snapshot prevents a fresh source-to-KT reproduction.
- Normalisation mappings are model-generated and current pilots use only 24
  cells, 58 items, a fixed English lexicon, and one item format.
- Exact equality measures a controlled sublanguage, not open-ended English
  acceptability or pedagogical usefulness.
- Synthetic alternative-cell errors are not distributions of real learner
  errors; binary simulator failures contain no response text or diagnosis.
- The one hosted judge is unpinned and not independent human evidence.
- KT states depend on a declared KC representation; private synthetic oracle
  state is not observable learner truth.
- No causal learner gain, retention, or counterfactual tutor-action outcome has
  been measured. RL claims would be premature and vulnerable to simulator
  exploitation.
- Cross-lingual generality remains architectural until another typed schema,
  analyzer/realizer, and non-singleton acceptance regime are demonstrated.

## Cautious conclusion paragraph

The pilot establishes feasibility, not post-training efficacy. Grammar-KT can
derive exact positive, diagnostic, verifier, and feature-level preference views
from a common provenance-preserving grammatical representation. The resulting
contrasts are deterministically valid and legible to one instruction-model
judge, but a 24-case generation ablation is at ceiling and provides no evidence
that canonical conditioning or preference learning improves a model. The next
scientifically useful step is a harder, multi-format, provenance-split SFT and
verified-sampling comparison; free-form preference optimization and RL should
remain conditional on that evidence and on human-grounded pedagogical labels.
