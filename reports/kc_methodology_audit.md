# Generator-KC methodology after the GrammarCell stage

Status: completed structural, pedagogical, and outcome-blind induction audit  
Protected reference: `data/grammar_kt_full_v1/` (unchanged)  
Evidence boundary: deterministic artifact analysis plus explicitly non-human
Codex judgments and proposals; no learner/expert validation

## Decision

Retain the 18-column full-v1 K* as the **declared clean-control generator
world**. Describe its columns as *feature-linked latent factors with
operation-motivated names*, not as recovered human cognitive atoms. Do not
replace K* using the automated proposals, Q rank, or downstream predictive
performance.

For the measurement extension, improve the methodology in three ways:

1. freeze GrammarCells, K*, and deterministic Q rows before item construction;
2. give the already-frozen active KCs and a measurement objective to the item
   constructor, so anchors, crossings, transfer contexts, and nuisance controls
   are intentional rather than inherited after wording is selected;
3. report conclusions across declared alternative structural worlds where the
   available representation supports them.

This preserves the causal hygiene of full-v1 while no longer treating
algebraic convenience as educational validity.

## What full-v1 establishes

The independent replay in
`experiments/measurement_realism/audits/kc_audit/structural_metrics.json`
confirms:

| Diagnostic | Result |
|---|---:|
| Q* shape | 113 × 18 |
| Q* edges | 269 |
| Q* rank | 18 |
| Distinct cell-level Q rows | 75 |
| One-KC items | 16/113 (14.2%) |
| Multi-KC items | 97/113 (85.8%) |
| KCs with a one-column Q isolate | 12/18 |
| Crossed KC pairs | 46/153 (30.1%) |
| Nested KC pairs | 2/153 (1.3%) |

These facts establish an explicit, deterministic, linearly distinguishable
synthetic world. They do not establish completeness, cognitive independence,
transfer, measurement purity, or model-specific identifiability. The
literature synthesis records the stronger assumptions needed by particular
cognitive-diagnosis identifiability results; full numerical rank alone is not
a general guarantee.

## Pedagogical and representation limitations

The 18-row judgment ledger and full report are retained under
`experiments/measurement_realism/audits/kc_audit/`. The main limitations are:

- Support is highly unequal: 2–49 items and 1–32 GrammarCells per KC; seven
  KCs have fewer than six frozen items.
- Perfect, progressive, passive, negation, polar-question, and non-subject-WH
  columns have no one-KC item.
- The only non-subject-WH GrammarCell is present, negative, and non-modal, so
  the proposed WH competence is narrow and nested in present and negation.
- Nine mutually exclusive modal-lemma columns are easy to separate
  algebraically but provide no evidence about a shared modal competence or
  transfer between modal functions.
- KC descriptions sometimes promise narrower operations than their executable
  predicates encode. For example, finite-present spans lexical verbs, BE,
  perfect HAVE, and DO-support without person/number in GrammarCell; negation
  spans DO, BE, HAVE, and modals.
- The full-v1 item generator deliberately did not read K*. This prevented
  outcome leakage, but it optimized linguistic cell fidelity rather than
  evidence for a declared KC measurement claim.

The final interpretation is therefore world-relative: a learner in the
simulator has these 18 states by construction. A real learner need not.

## Systematic candidate worlds

`candidate_world_metrics.json` deterministically projects seven hypotheses
without reading outcomes. They include:

- the frozen K* reference;
- a clause-compositional world that replaces separate polar/WH columns with
  shared operator inversion plus WH fronting;
- K* plus perfect-progressive-chain or DO-support interactions;
- a shared-modal world;
- a flat shared-modal parent plus lemma children, intentionally rank-deficient
  because a plausible hierarchy need not be representable as independent flat
  Q columns;
- a non-reference feature/value world.

The clause-compositional and feature/value worlds remain rank 18 on the chosen
18-cell matched-format basis. The shared-modal world has 10 columns and rank
10. These are structural sensitivity worlds, not rival claims about human
truth. Modal-function, lexical-morphology, argument-structure, person/number,
and genuine prerequisite-transfer worlds cannot be projected faithfully from
current GrammarCell fields and are not fabricated.

## Outcome-blind independent induction

The preregistered study at
`experiments/measurement_realism/kc_induction_v1/` supplied three independent
automated proposers with only the 75 GrammarCells, source-support counts, and
an executable predicate grammar. K*, Q*, items, learner streams, private
states, and all downstream results were hidden until the raw proposals were
frozen. Hypotheses were then canonicalized by their exact 75-cell activation
vectors, never by wording.

Results:

| Diagnostic | Replicate 1 | Replicate 2 | Replicate 3 |
|---|---:|---:|---:|
| Raw proposals | 18 | 18 | 18 |
| Unique activation columns | 17 | 18 | 18 |
| Rank after activation canonicalization | 17 | 18 | 17 |
| Exact frozen-K* activation matches | 5 | 4 | 7 |

Across all calls, only 9 activation hypotheses were shared by all three, while
the union contained 30. Pairwise activation-set Jaccard agreement was 0.400,
0.440, and 0.458. Seven of the 18 frozen K* columns were reproduced exactly by
at least one proposer. Proposers often converged on broad negation, passive,
question, imperative, and shared-modal families while differing over tense,
aspect composition, modal groupings, and interaction specificity.

This is evidence of **ontology underdetermination from GrammarCells alone**,
not evidence that the majority proposal is correct. It also demonstrates why
an LLM should not simply be asked to return “the KCs.” Repeated calls,
executable predicates, activation canonicalization, explicit limitations, and
post-freeze evaluation make the judgment visible; they do not turn it into
human validation.

Two infrastructure attempts are retained separately. The first stopped before
any call on a prompt-hash mismatch; the second was rejected before inference
because the provider did not support one JSON-schema keyword. Neither enters
the scientific analysis.

## Desirable KC properties and how they are used

No scalar KC score is used. Candidate worlds are assessed with separate
diagnostics:

| Property | Operational question |
|---|---|
| Linguistic coherence | Do activated cells share a defensible construction or operation? |
| Reuse | Does the hypothesis recur beyond one exact cell where the representation permits? |
| Independent mastery interpretation | Could a learner plausibly improve this factor separately? |
| Measurement support | Are there learner-facing opportunities that require it without obvious shortcuts? |
| Distinguishability | Do the bank and schedule provide contrasts rather than only co-occurrence? |
| Parsimony | Does the hypothesis add an interpretation, not merely another rank column? |
| Compositionality | Can shared operations explain complex cells without exact-cell memorization? |
| Pedagogical relevance | Is this something an educational system could plausibly practice or diagnose? |

Structural support and rank are hard diagnostics, but none overrides a failed
linguistic or measurement interpretation. Conversely, a plausible hierarchy
is not rejected merely because a flat binary Q makes its parent column
dependent on its children.

## Final role of K*

K* remains useful because synthetic truth must be declared somewhere, it was
fixed before outcomes, it makes existing counterfactual results replayable,
and the matched-format design can retain its exact Q rows while changing only
measurement nuisance. The paper must state all four boundaries:

1. K* is generator truth inside one controlled world.
2. Its columns are plausible hypotheses, not human cognitive ground truth.
3. Predictive preference for a split/merge does not validate a psychology when
   item difficulty or format can explain the gain.
4. Conclusions that persist in the clause-compositional, feature-based, or
   interaction sensitivity worlds have stronger ontology robustness than
   conclusions shown only under K*.

## Required external validation

Future validation should sample all rare KCs and all proposed interactions,
then obtain independent judgments of linguistic coherence, learnability,
transfer scope, and platform tracking relevance. The concrete expert and
learner design—including sample sizes and assignment—is frozen in
`experiments/measurement_realism/dialogue_pilot/human_expert_validation_protocol.md`.
Until such evidence exists, all pedagogical judgments in this report remain
structured non-human critique.
