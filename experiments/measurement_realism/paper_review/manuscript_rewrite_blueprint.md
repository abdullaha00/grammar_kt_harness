# Adversarial ACL manuscript review and rewriting blueprint

Status: isolated review artifact; no ACL file or shared report was edited  
Review date: 2026-08-30  
Manuscript snapshot: `f1a5eb29414dd03d173dbd9d0c4cb20762f2b259`  
Protected benchmark: `data/grammar_kt_full_v1/`

## Evidence boundary

This review assesses the current ACL manuscript against:

- the retained full-v1 construction and experiment evidence in
  `ACL/evidence.md`, `ACL/results_summary.md`, and the frozen release;
- the completed 113-item census in
  `experiments/measurement_realism/audits/item_audit/` and
  `reports/platform_plausibility_audit_draft.md`;
- the completed generator-KC structural/pedagogical audit in
  `experiments/measurement_realism/audits/kc_audit/`; and
- the 37-source review in
  `experiments/measurement_realism/literature/`.

The item and KC audits combine deterministic calculations with one explicitly
non-human Codex review. They are evidence of documented concerns, not human
learner, teacher, product, or expert agreement. The literature constrains
plausible mechanisms and claim boundaries; it does not calibrate a human
language-learner simulator. No measurement-extension results are presumed in
this blueprint unless they already exist as retained artifacts.

## Executive verdict

The current paper is unusually strong on causal ordering, artifact integrity,
oracle separation, and the distinction
`GrammarCell != generator KC != discovered KC`. Its best retained scientific
result is not that it discovered the right grammar KCs. It is that, even in a
world with declared latent truth, predictive evidence identifies only what the
bank and response process make distinguishable. The exact-Q equivalence result,
the A+B-only control, and the item-difficulty reversal jointly support this
lesson.

The current paper's organizing claim is nevertheless too dataset-centric for
the revised programme. It treats construction of a fixed item bank as the
successful first RQ, then places the fact that prompts never cause responses in
methods, discussion, and limitations. The completed census makes that
boundary more consequential:

- 70/113 items (61.9%) were judged plausibly usable as stored under an assumed
  minimal UI/scoring policy;
- 15/113 (13.3%) were judged locally repairable;
- 15/113 (13.3%) were technically answerable but pedagogically/artificially
  specified;
- 10/113 (8.8%) had a material response-space problem; and
- 3/113 (2.7%) required rewrite or withholding.

These are non-human audit categories, not estimates of real deployability.
They still falsify any unqualified implication that linguistic validator
acceptance plus Q rank yields a platform-ready measurement bank. Full-v1 is a
clean Q-driven control environment with an auditable intended item surface,
not yet a synthetic approximation of actual platform interaction.

Likewise, the KC audit supports the 18 columns as a defensible declared control
world, but not as 18 validated independently learnable competencies. The
columns are most accurately described as **feature-linked latent factors with
operation-motivated names**. Rank 18 establishes linear independence in this
bank. It does not establish psychological independence, response-model
identifiability, pedagogical transfer, or measurement purity.

The manuscript should therefore be rewritten around a stricter thesis:

> Perfect latent annotation is useful because it permits counterfactual tests
> that real learner logs cannot support, but known truth is not sufficient for
> valid KT inference. What is recoverable depends jointly on the declared KC
> world, the measurement instrument, the assignment policy, and the response
> information retained.

The dataset is the experimental instrument supporting that analysis. It should
not remain the paper's intellectual endpoint.

## Strongest coherent thesis

### Thesis supportable now

With only currently retained evidence, the strongest coherent claim is:

> We construct a replayable clean-control grammar-KT environment with known
> latent structure and use it to expose limits that cannot be measured against
> real logs: KC misspecification degrades inference in the planted world,
> activation-equivalent ontologies remain observationally indistinguishable,
> response volume cannot repair missing measurement contrasts, and omitted
> item difficulty can make a false refinement appear preferable. A separate
> non-human census shows why this internally controlled benchmark must not be
> conflated with a platform-validated measurement environment.

This is already a defensible methodological paper. It is less ambitious than
the requested final programme, but every clause maps to retained evidence.

### Thesis supportable after the core measurement extension

If the matched-bank and nuisance experiments produce the planned retained
evidence, the stronger final thesis should be:

> We use a controlled synthetic language-learning environment to separate
> learner knowledge from the instruments and policies through which it is
> observed. Across clean and platform-oriented scenarios, we test when
> KC/Q misspecification is recoverable, when item and format nuisance
> masquerades as skill granularity, and whether explicit nuisance variables and
> richer error information restore shared-skill and mastery recovery. This
> reveals which conclusions depend on clean laboratory measurement and which
> survive plausible observable-data perturbations.

This thesis requires results, not only a plausible architecture. In
particular, it requires the zero-format control, planted format/item worlds,
false format splits, explicit nuisance models, and oracle recovery evaluation.

### Thesis that would remain unsupported

Do not claim any of the following without new human or external evidence:

- that the simulator is realistic or human-like;
- that the 18 KCs are the cognitive or pedagogically correct decomposition of
  English grammar;
- that the 113 frozen prompts constitute a deployable platform item bank;
- that item audit percentages estimate prevalence on EGP or real platforms;
- that planted scenario parameters estimate language-learner populations;
- that matching broad synthetic marginals validates the causal learner model;
- that dialogue completion or generated error text is learner-realistic; or
- that full Q rank guarantees KC identifiability.

Use `clean-control`, `platform-oriented`, `plausibility scenario`, and
`plausible synthetic error` unless stronger validation is actually retained.

## Recommended title direction

The current title, *Operationalising Grammar Knowledge Components for
Knowledge Tracing*, foregrounds KC construction and can be read as claiming a
resolved operational definition. A stronger title should foreground the
measurement problem.

Preferred after successful nuisance experiments:

> **When Measurement Looks Like Knowledge: Controlled Grammar Knowledge
> Tracing with Known Latent Truth**

Conservative title supportable now:

> **Known Truth, Ambiguous Measurement: A Controlled Benchmark for Grammar
> Knowledge Tracing**

Alternative framing title:

> **What Perfect-Information Synthetic Data Can Reveal about Grammar
> Knowledge Tracing**

Avoid `realistic`, `platform-realistic`, `human-like`, or `validated language
learning dataset` in the title unless human/expert response-process evidence is
added.

## Compact research questions

Three RQs are enough. They should name the inferential problem rather than the
historical project phases.

### RQ1 — Construction and measurement validity

> What must be declared and audited to construct a grammar-learning
> measurement environment with known latent structure, and where does a clean
> Q-driven benchmark fall short of a plausible platform interaction?

Current evidence answers the construction and audit-boundary parts. A claim of
platform plausibility remains pending independent critics and, for a strong
claim, human/expert review.

### RQ2 — Representation versus measurement nuisance

> How do KC/Q misspecification and item- or format-specific nuisance affect
> response prediction and recovery of the planted learner state?

Current evidence answers the clean misspecification part and provides one
item-difficulty reversal. The central matched-format comparison remains
required.

### RQ3 — Identifiability and information design

> Which item-bank contrasts, assignment policies, and response information
> make latent structure and mastery distinguishable from observable histories?

Current evidence supports activation equivalence and anchor/volume limits.
Policy comparisons and structured-error information remain required if they
are to appear in the RQ answer. Linguistic recombination belongs here as one
test of reuse rather than as a separate broad generalisation RQ.

If page pressure requires an even narrower paper, omit policy and structured
errors from RQ3 and state it as:

> Under what Q geometry can observable responses distinguish competing KC
> representations?

Then treat policy and richer responses as follow-up work rather than a rushed
multi-part claim.

## Claim-by-claim triage

| Current manuscript claim or implication | Decision | Required wording or action | Evidence status |
|---|---|---|---|
| The work presents an “auditable pipeline” separating cells, K*, Q*, items, events, and K-hat. | Retain. | Define auditability as provenance, deterministic projection/replay, and explicit uncertainty—not substantive validity. | Retained in full-v1 manifests, tests, and evidence ledger. |
| The 18-KC set is a “reusable-operation ontology.” | Narrow. | Use “declared 18-factor marked-operation/modal-identity control world” or “feature-linked latent factors with operation-motivated names.” Some columns are construction families or modal lemmas, not narrow operations. | KC audit retained; no human transfer evidence. |
| The bank contains 113 “validated items.” | Narrow materially. | Use “113 linguistically/model-screened frozen prompts” for full-v1. Reserve “measurement-validated” or “platform-deployable” for an extension passing separate gates. | Original validator and new census retained; human evidence absent. |
| The item bank is a learner-facing measurement surface. | Qualify. | It is an intended/stored surface. The simulator does not render it, execute a response component, normalize answers, or score text. | Retained and already acknowledged in methods/limitations. |
| The “measurement gate passes.” | Rename. | Call it a “Q-geometry/structural gate.” Report rank, support, equality, anchors, crossings, nesting, and their limits separately. | Rank 18 retained; only 12/18 KCs have a one-KC row; 46/153 pairs are fully crossed. |
| Full rank supports identifiability. | Narrow sharply. | Say “linear column independence for this bank.” Do not imply generic statistical or psychological identifiability. Cite Q-identifiability theory with its model assumptions. | Deterministic metrics retained; KT05 constrains the claim. |
| Every KC has meaningful measurement support because every column has at least two items. | Reject as an inference. | Report 2–49 items, 1–32 cells, seven KCs below six items, 16/113 single-KC rows, and rare/campaign-confounded columns. Item count is not independent measurement evidence. | KC audit retained. |
| The K* winner indicates an appropriate KC representation. | Narrow. | It shows sensitivity to declared misspecification in a world generated from K*. It does not validate K* as human or pedagogical truth. | RQ2 retained. |
| Both coarsening and refinement hurt. | Retain only world-qualified. | “Both hurt the primary observable model in frozen full-v1.” Immediately report the item-difficulty reversal and model/regime boundaries. | Retained with paired intervals and 13-world robustness. |
| Ten-percent Q corruption is harmful. | Retain only for the nine frozen perturbations. | Avoid universal ordering of false positives versus false negatives. | Retained; three structural seeds. |
| Observable discovery recovers an appropriate KC representation. | Replace. | “Observable selection recovers a high-overlap activation-equivalence class; unique ontology recovery is rejected.” Names/competence semantics are not recovered from Q activation. | Retained and one of the paper's strongest results. |
| Reusable KCs “transfer” to unseen grammar. | Narrow. | Say the declared shared-history projection outperforms exact-cell history on 15 pairwise-seen/full-tuple-unseen cells. This is compositional extrapolation under a generator with all KCs seen, not evidence of human grammatical transfer. | Retained; six unseen-value cells are narrow. |
| The exact-item negative control shows transfer across surface variants. | Do not imply. | Keep the current caveat: identical outcomes are forced by no item memory/difficulty and same keyed draws. Consider moving this control to appendix once real item effects become central. | Retained. |
| The baseline learner stream resembles learner interactions. | Narrow materially. | Call it a Q-balanced laboratory stream of binary events. It lacks rendered prompts, text responses, item effects, time, session structure, dropout, and platform selection. | Retained schema and simulator. |
| The 170-event acquisition schedule is a reasonable platform process. | Unsupported. | Present it as an internal-validity schedule. Any curriculum/adaptive relevance requires a separate policy experiment. | No platform-policy evidence retained. |
| Item difficulty is a simulator robustness detail. | Promote. | Treat it as the first direct warning that omitted measurement nuisance can change apparent KC granularity. It motivates—not completes—the new core experiment. | One three-seed perturbation retained; matched format/item models pending. |
| Pedagogical suitability passed independent validation. | Reconcile with the audit. | State what the original validator tested, then report the broader audit found platform, answer-space, and purity concerns. Do not silently choose one judgment. | Both evidence sets retained; no independent human adjudication. |
| The release offers design guidance for real collection. | Keep conditional. | Derive principles (cross KCs/formats, retain raw responses, log policy/item exposure, separate nuisance) rather than numeric prescriptions. | Structural and literature support retained; human effect sizes absent. |
| The methodology is language-independent. | Narrow. | “Schema-driven software components generalize to a toy non-English-named schema.” No cross-lingual empirical validity. | Already correctly bounded in discussion. |

## What the current manuscript gets right and should preserve

1. **Scientific ordering.** K* and Q* precede learner outcomes, and discovery
   is downstream. This prevents response-selected generator truth.
2. **Object separation.** GrammarCell, generator state, observable event, and
   model hypothesis are explicitly distinct.
3. **Frozen reference benchmark.** Full-v1 is versioned, replayable, and keeps
   private state out of ordinary observable rows.
4. **Negative identification result.** Exact seen-Q equivalence defeats unique
   discovery even when a truth-like policy exists in the candidate space.
5. **Counterfactual design.** The same events are reused for representation
   comparisons, and oracle truth is opened only after selection when required.
6. **Honest limitations.** The current paper already says prompts are not
   rendered or scored, K* is not human truth, and synthetic thresholds are not
   recruitment prescriptions.

The rewrite should build on these strengths. It should not rewrite history or
pretend full-v1 was designed as a platform simulator.

## Central conceptual change

The current figure is described as a two-layer construction/experiment
programme. The new paper needs a causal measurement view:

```text
grammar resource
    ↓
GrammarCell ───────────────┐
    ↓                      │
declared K* + Q*           │
    ↓                      ↓
latent learner state + measurement instrument + platform policy
                         ↓
             observable response history
                         ↓
                 K-hat/Q-hat/KT state
```

The visible outcome is jointly caused by learner knowledge, item/format
burden, selection policy, and response/scoring noise. Oracle annotations let
the paper separate these causes in controlled counterfactuals. That is the
reason synthetic data is scientifically necessary.

The validity argument should follow this chain:

```text
visible task and response mechanism
→ interpretable learner response
→ evidence about declared K*
→ fitted KT state or recovered ontology
→ bounded data-collection implication
```

Each arrow needs different evidence. Grammaticality, Q rank, predictive fit,
and platform plausibility are not interchangeable validation scores.

## Section-level rewriting blueprint

### Title and abstract

Lead with the hidden-truth problem and the measurement confound, not the EGP
record count. The abstract should contain five moves:

1. Real language-learning logs lack trustworthy opportunity/KC/Q/mastery
   truth, preventing counterfactual evaluation.
2. A synthetic environment supplies that truth, but its observable layer is
   useful only if measurement and platform mechanisms are explicit.
3. Briefly describe full-v1 as the immutable clean control and the separate
   measurement extension/audit.
4. State at most three central findings, including one negative or boundary
   result.
5. End with the collection/interpretation lesson and a bounded realism claim.

Do not spend half the abstract listing all census counts. Keep one compact
construction sentence. Do not add matched-format or error-aware findings until
the result files and intervals exist.

A safe abstract skeleton is:

> Language-learning logs reveal responses but not the true grammatical
> opportunity, KC decomposition, Q-matrix, or learner state needed to evaluate
> KT representations. We construct [an auditable clean-control environment]
> in which these quantities are declared and replayable, then separate learner
> knowledge from the item, format, and assignment processes through which it
> is observed. [One sentence of construction scope.] In the clean world,
> [retained misspecification/equivalence result]. A census of the stored
> opportunities identifies [qualified audit boundary], and controlled
> [item/format] scenarios show [insert only retained core result]. [Optional
> structured-error result.] These findings show [bounded conclusion about
> measurement nuisance and data collection], not that the simulator or KC
> ontology is human truth.

### Introduction

Replace the current progression “KT needs a Q-matrix → EGP is complex → here
is our dataset” with:

1. **Perfect-data thought experiment.** What analyses would become possible if
   opportunity boundaries, K*, Q*, and mastery were known?
2. **Why real logs cannot answer them.** Use TSCC/SLAM/EdNet-style examples to
   distinguish ambiguous language interactions, platform-selected histories,
   and opaque skills.
3. **Why synthetic truth is not sufficient.** State the joint observation
   process: learner + instrument + policy + noise.
4. **Controlled response.** Introduce GrammarCell, K*/Q*, measurement
   instrument, platform policy, observable behavior, and K-hat/Q-hat.
5. **Three compact RQs.** Use the RQs above.
6. **Contributions.** List methodological separations and retained findings,
   not merely artifact counts.

Suggested contribution order:

- a versioned clean-control environment with complete provenance and oracle
  separation;
- a layered measurement-validity and KC audit exposing gaps hidden by Q
  coverage/rank;
- controlled evidence about representation misspecification, structural
  equivalence, and measurement nuisance; and
- data-collection implications and a reproducible platform-oriented extension
  if it passes the release gates.

The current “Why didn't he went?” example contains an ungrammatical auxiliary
construction that may distract readers from the ontology point. Either explain
that it is an illustrative learner error or use a grammatical target plus a
plausible incorrect response.

### Related work

The present related-work section is too narrow for the new thesis. Reorganize
it into four contrasts:

1. **KT domain models and Q misspecification.** Retain BKT/PFA/LFA and Q
   validation; add model-specific identifiability and misspecification work
   (literature ledger KT02–KT09). Explicitly distinguish linear rank,
   restricted-latent-class identifiability, predictive selection, and
   educational interpretation.
2. **Educational measurement and task format.** Add validity arguments and
   construct underrepresentation/irrelevant variance (ME02–ME04), then matched
   format/task-sampling evidence (ME05–ME10). This is the conceptual basis for
   separate linguistic, response-process, internal-structure, and use claims.
3. **Platform logs, policy, and learner simulation.** Use SLAM/EdNet, spacing,
   adaptation/off-policy selection, IRT/item effects, and simulator-validity
   reviews (PL01–PL07, SI01–SI03). Literature motivates mechanisms but does
   not supply universal parameters.
4. **Language responses and dialogue.** Use learner-corpus error annotation,
   alternative valid corrections, partial-credit/open-response modelling, and
   TSCC/tutorial dialogue (ER01–ER05, DL01–DL03). Rich responses can be more
   informative while weakening opportunity boundaries.

Do not turn this into a citation inventory. Every paragraph should identify a
specific gap the controlled design isolates.

### Scientific objects and source data

Retain the GrammarCell definition and EGP census, but compress source
normalisation details in the main paper. Move the complete status counts,
repeat-agreement detail, and compatibility examples to one compact construction
table or appendix.

Add a table that distinguishes:

| Layer | Object | Platform observable? | Oracle-only? | Causal role |
|---|---|---:|---:|---|
| Linguistic | GrammarCell | item metadata, possibly | yes for evaluation | describes construction |
| Learner truth | K*, Q*, mastery | no | yes | generates knowledge-dependent response |
| Instrument | wording, format, answer space, item effect | partly | planted effects partly private | elicits/scores response |
| Platform | eligibility, order, time, feedback/policy | yes in logs if retained | policy internals may be private | selects experience |
| Behavior | response, correctness, error label | yes | failed KC is private | observed evidence |
| Model | K-hat, Q-hat, KT state | inferred | no | experimental hypothesis |

This table will prevent later sections from treating an oracle failed KC as an
observable error category or a GrammarCell as a skill.

### Generator-KC methodology

Preserve the outcome-independent declaration. Rewrite its characterization:

- state explicitly that K* is a flat marked-operation/modal-identity control
  world;
- separate **activation semantics**, **competence semantics**, **measurement
  manifestation**, **learning interpretation**, and **nuisance boundary**;
- report the support asymmetry and definition/activation mismatches;
- introduce alternative worlds as sensitivity hypotheses, not candidates from
  which synthetic outcomes identify human truth.

At minimum discuss the deterministic clause-compositional alternative, the
DO-support/interaction alternative, and a feature-value control. A
modal-function/shared-form world cannot honestly be projected until modal
function is added to measurement metadata. A hierarchical modal parent plus
lemma children should not be rejected solely for failing a flat full-rank
criterion.

Move the 18-name inventory to appendix unless individual names are necessary
for a qualitative example. In the main text, explain the methodological issue:
many KCs bundle semantic choice, auxiliary selection, morphology, and word
order while Q encodes only a cell predicate.

### Measurement-bank construction

Split this section into two explicit subsections.

**R0 frozen intended surface.** Describe the original cell-conditioned
generation and validator faithfully, including that K* existed but was not
read by item generation. This is good leakage control but weak instrument
design: the campaign targeted GrammarCell fidelity rather than KC isolation,
format crossing, or diagnostic error manifestations.

**Measurement extension.** If completed, describe:

- a shared semantic/stem specification;
- matched rendering into constrained cloze, multiple choice, transformation,
  and dialogue completion;
- instruction/context/stimulus/response component/scorer fields;
- accepted-answer normalization and option/distractor rules;
- intended proficiency and lexical controls;
- hard gates for linguistic validity, visible sufficiency, determinacy,
  response-space fairness, and executable response mechanism; and
- separate non-gating ratings for pedagogical and platform plausibility.

Do not call items “matched” merely because they share a GrammarCell/Q row.
Lexical content, target meaning, information shown, and intended answer must
come from a common family specification. Format is otherwise confounded with
content.

Report the 113-item audit near this method rather than burying it in
limitations. Include role disagreement and the single-Codex limitation.
Examples should show at least:

- one clean cloze;
- the `today` simple-present/progressive competitor;
- the `may`/`might` ambiguity;
- one over-constrained imperative prompt; and
- the reported-speech item whose Q omits required backshift/reference work.

### Response generator and platform process

Label full-v1 `R0: clean Q-driven laboratory world`. Its response equation and
opportunity update remain useful precisely because they isolate the KC
assumption.

Then define one mechanism per scenario rather than a giant realism simulator:

- stable centered item difficulty;
- centered format offsets and format-specific response noise;
- learner ability and learning-rate heterogeneity;
- curriculum/review assignment; and
- structured error information.

For each world, state the limitation, hypothesis, planted parameter, held-fixed
variables, observable fields, private fields, and falsification control. Use
paired learner/item draws and keyed uniforms where feasible. Call parameter
magnitudes stress-test scenarios, not estimates.

The schedule subsection must make clear that the current 170-event schedule is
Q-balanced laboratory assignment. A platform-policy experiment should log
`policy_id`, order/time/session, eligibility/selection rule, and propensity if
selection is stochastic. Equal event counts alone do not equalize the observed
Q geometry or learner-state distribution.

### Experimental setup

Organize models by explanation, not by historical script:

```text
A  shared K*, no nuisance term
B  false format-specific split KCs
C  shared K* + format term
D  shared K* + item + format terms
```

Add the existing coarse/fine/Q-noise projections as clean-reference controls.
The required comparisons are:

- zero-format negative control;
- planted format positive control;
- centered item effects independent of Q/format;
- shuffled format-label control;
- shared learners, sequence, items, and uniforms within a world;
- held-out learner evaluation;
- an explicit statement whether test items were seen during parameter fitting;
  and
- both prediction and oracle-state recovery.

Control flexibility. A format split has more skill-history features; an item
fixed-effect model has many nuisance parameters. Use held-out responses and
report parameter counts/regularization. Distinguish same-item future-response
prediction from unseen-item generalization. If item effects are oracle-provided
in any upper bound, label it separately from an estimated deployable model.

Primary metrics should remain log loss and Brier, with calibration and
learner-paired intervals. Oracle mastery RMSE is essential because nuisance
models can improve prediction while worsening state semantics. AUC/accuracy
should remain diagnostic.

For structured errors, do not expose private `failed_kc` as if a platform knew
it. Compare:

- binary correctness only;
- an observable noisy/structured error category derived from the response;
- an oracle-linked positive-control category; and
- a frequency-matched within-item/format shuffle.

Evaluate failed-KC localization separately from next-response prediction and
mastery RMSE. Surface text is optional and should not enter the main paper
without independent intended-edit validation.

### Results

The current four-RQ chronological results section cannot simply absorb every
new experiment. Replace it with a result hierarchy.

1. **R0 establishes controlled truth, not platform validity.** Give one compact
   construction table, the item/KC audit, and the observable/oracle boundary.
2. **What clean control reveals.** Retain the coarse–K*–fine curve, Q noise,
   equivalence-class discovery, and the A+B anchor result. Move secondary
   per-regime and BKT detail to appendix.
3. **Measurement nuisance versus KC granularity.** This must become the central
   quantitative result if supported: zero effect, format effect, item effect,
   false split, explicit nuisance models, prediction plus mastery recovery.
4. **Robustness of the causal lesson.** Add learner heterogeneity and policy
   only if they change or meaningfully bound the core conclusion. Do not list
   dozens of worlds without an organizing contrast.
5. **Information beyond correctness.** Include structured errors only if the
   informative-vs-shuffled contrast is supported and nontrivial.
6. **Ecology–precision boundary.** A small matched cloze/transformation/dialogue
   panel may be a qualitative result. Do not promote an open-dialogue pilot to
   a dataset claim.

Every quantitative subsection should name the generator world and selection
policy. “K* wins” is uninterpretable without saying what nuisance is planted
and what the fitted model observes.

### Discussion

Answer two questions directly:

1. What does known synthetic truth let us learn that real logs cannot?
2. Which conclusions are likely relevant to real collection, and on what
   evidence?

The first answer can be strong: counterfactual Q/KC changes, actual oracle
state error, activation equivalence, and policy/nuisance controls are
unavailable in ordinary logs.

The second answer must remain bounded. Prefer design principles:

- cross KCs with multiple formats and formats with multiple KCs;
- use semantic families, not merely same-cell labels, for format comparisons;
- retain item identity, response mechanism, raw response, scoring outcome,
  timing/exposure, and platform policy metadata;
- keep item/format nuisance separate from learner-skill state;
- collect anchor/diagnostic contrasts where educationally natural;
- retain alternative valid answers and unresolved responses; and
- use non-updating probes when the scientific design permits.

Do not convert synthetic effect magnitudes into literal learner recruitment,
spacing, or item-count prescriptions.

### Limitations and ethics

The current limitations are good but should be restructured around validity
claims rather than implementation components:

- **content evidence:** model-assisted GrammarCell and item judgments, no
  expert adjudication;
- **response process:** no real learner comprehension/production evidence;
- **internal structure:** planted K*/Q* and model-specific recovery;
- **external/ecological validity:** scenario mechanisms and platform-oriented
  formats, not calibrated human behavior;
- **fairness/accessibility:** no subgroup or accessibility evidence;
- **generalization:** one English morphosyntax scope, six narrow unseen-value
  cells, no second language; and
- **uncertainty:** learner bootstrap does not cover ontology, prompt, critic,
  scenario, or human-population uncertainty.

If independent model critics are used, disclose model families, prompts,
settings, lack of provider seed/snapshot pinning, and that critic agreement is
not human agreement. If surface error text is generated, discuss the risk of
stereotyping proficiency and do not attach errors to demographic groups.

### Reproducibility

Retain the strong full-v1 manifest description. Add a separate extension map
with:

- immutable parent hashes;
- matched-family specifications and rendered item schema;
- generator and critic prompts, exact inputs, model/settings, raw and parsed
  outputs, and hashes;
- scenario parameter files and paired seed design;
- observable/oracle schemas;
- policy rules and propensity logging;
- fit splits and prediction artifacts; and
- a claim-to-artifact ledger.

Reproducibility is not itself validation. Keep reconstruction evidence and
measurement evidence in separate columns.

### Conclusion

End on the inferential lesson, not the release inventory:

> Known latent truth makes otherwise impossible evaluations possible, but it
> does not remove the measurement problem. In controlled grammar-learning
> worlds, the KCs that appear recoverable depend on which contrasts a platform
> presents, which nuisance factors a model represents, and which information a
> response retains. Synthetic data are therefore most useful as a
> counterfactual instrument for designing and interpreting real learner logs,
> not as a substitute for evidence about human cognition.

Add specific retained qualifications after this sentence rather than claiming
all planned mechanisms were resolved.

## Main-paper result and display plan

The paper should use fewer, more causally informative displays than the current
inventory of separate RQ tables.

### Figure 1 — Causal layers and observability

Show GrammarCell, K*/Q*/mastery, measurement instrument, platform policy,
observable response, and K-hat/Q-hat/KT. Use color or line style to distinguish
public/loggable from oracle-only variables. This replaces a purely procedural
pipeline.

**Evidence:** conceptual method plus schemas; already supportable.  
**Gap:** extension observable/oracle schemas if a new dataset is shown.

### Table 1 — Clean control versus platform-oriented worlds

Columns should be: world, item surface causal?, item difficulty?, format
effect?, learner heterogeneity?, policy, response information, purpose, claim
boundary. This prevents the phrase “realistic simulator” from hiding multiple
assumptions.

**Evidence:** R0 retained.  
**Gap:** final definitions/manifests for each extension world.

### Table 2 — Measurement and KC audit

Use two compact panels:

- item disposition/dimension counts with the explicit “one non-human audit”
  label; and
- Q/KC geometry: 113×18, rank 18, 16 one-KC items, 12/18 columns with an
  isolating row, 46/153 fully crossed pairs, 2 nested pairs, support 2–49.

Include two short learner-facing examples. Avoid presenting a composite
realism score.

**Evidence:** retained and reproducible.  
**Gap:** independent critic or human agreement if platform validity is claimed.

### Figure 2 — Core measurement-confounding contrast

For zero-format, planted-format, and planted-item+format worlds, plot model
contrasts A–D on:

- held-out log loss/Brier; and
- oracle mastery RMSE.

Show paired uncertainty and the zero-effect falsification result. A connected
point/forest plot is preferable to a dense table.

**Evidence:** not yet retained. This is the main go/no-go figure for the revised
thesis.

### Figure 3 — Identifiability by measurement design

Combine the existing A+B-only/anchor result with matched-bank activation
coverage. Visually separate structural equivalence, full rank, and practical
recovery. If alternative generator worlds are simulated, include their
activation-equivalence classes.

**Evidence:** micro-world and KC audit retained.  
**Gap:** matched-format bank geometry and cross-world recovery.

### Table 3 or Figure 4 — Information beyond correctness

Compare binary, informative error category, shuffled category, and optional
oracle category on localization, mastery RMSE, log loss, and calibration.

**Evidence:** not yet retained. Omit entirely if the shuffled control is null
or if the category is merely an exposed oracle label.

### Qualitative panel — One matched semantic family

Show GrammarCell, active generator factors, common semantic specification,
cloze, transformation, multiple choice, dialogue completion, accepted response
policy, and one plausible error. Mark oracle annotations explicitly.

**Evidence:** not yet retained. One family cannot establish coverage but makes
the measurement object inspectable.

### Appendix material

Move these from main text unless a result becomes central:

- detailed EGP normalization counts and stability breakdown;
- all six granularity/Q-noise projections;
- RQ3 candidate inventory mechanics;
- per-cell unseen-value sensitivity;
- fixed-BKT diagnostic details;
- 13-world legacy robustness table;
- collection cohort counts;
- complete 18-KC and item-audit ledgers; and
- all scenario configurations.

The main paper cannot sustain source construction, KC discovery, grammar
generalization, mastery recovery, 13 simulator variants, collection design,
four formats, platform policies, error-aware KT, and dialogue as co-equal
contributions. The central causal result must determine what remains in the
main body.

## Evidence map

### Retained evidence that can support paper claims now

| ID | Evidence | Defensible use | Boundary |
|---|---|---|---|
| R1 | Full-v1 manifest, Q/event replays, immutable hashes | Artifact integrity and clean causal ordering | Not measurement validity |
| R2 | 1,222-row census, 75 cells, repeat annotation study | Complete processing under declared six-dimensional scope | No expert gold; not all EGP grammar |
| R3 | Frozen 18-factor K*/113×18 Q* | Declared synthetic truth and deterministic activation | Not human competence truth |
| R4 | Rank/support/pair-geometry audit | Linear distinguishability and bank diagnostics | Not general/statistical/psychological identifiability |
| R5 | RQ2 coarse/fine/Q-noise results | Sensitivity to misspecification within R0 | K* is favored by its generating world |
| R6 | RQ3 exact activation equivalence | Unique ontology recovery rejected on seen evidence | Bank/regime-specific equivalence |
| R7 | RQ4 recombination result | Shared-history extrapolation to 15 unseen tuples | Not human transfer; narrow unseen values |
| R8 | Oracle prerequisite-state and BKT diagnostics | Model-state/generator-state semantic mismatch | Not human mastery measurement |
| R9 | Thirteen-world robustness | Many one-factor perturbations preserve ranking | Three seeds; not a realism validation |
| R10 | Item-difficulty reversal | Omitted item nuisance can alter representation ranking | One planted severity; no matched formats |
| R11 | A+B-only/anchor controls | More responses do not repair structural equivalence | Micro-world; no literal sample thresholds |
| R12 | 113-item census | Concrete, quantified non-human critique of full-v1 surface | One Codex review, assumed UI/scorer |
| R13 | KC methodology audit | Support asymmetry, confounds, alternative structural worlds | Pedagogical judgments are non-human |
| R14 | 37-source literature ledger | Mechanism motivation and claim constraints | No universal language-learner parameters |

### Evidence required for the revised core claim

| ID | Required artifact/result | Why it is required | Minimum falsification/control |
|---|---|---|---|
| G1 | Independent role-specific item audit calls or explicitly downgraded claims | The protocol calls for independent learner/teacher/product/measurement critics; current role disagreement is not independent | Frozen prompts, raw outputs, parsed results, agreement/disagreement |
| G2 | Matched semantic-family item bank with executable instrument schema | Format cannot be isolated from unmatched lexical/context content | Shared family specification; all formats pass hard gates |
| G3 | Deterministic bank geometry and crossing audit | Ensure format is not confounded with KC/campaign and K* remains measurable | Per-format/KC support, rank/equivalence, family counts |
| G4 | Zero-format-effect world | Detect false-split flexibility, leakage, or finite-sample advantage | Paired draws; format shuffle |
| G5 | Planted format and stable item-difficulty worlds | Test the central nuisance-as-KC hypothesis | Centered independent effects; small/large scenarios |
| G6 | Shared K*, false split, format, and item+format model comparison | Distinguish knowledge representation from observable nuisance | Held-out learners; parameter/regularization report |
| G7 | Oracle mastery recovery for G6 | Prediction alone cannot establish correct state semantics | Same estimand across models; paired intervals |
| G8 | Learner heterogeneity robustness in the matched world | Ensure the result is not a homogeneous-learner artifact | Ability and speed separately, then combined; paired strata |
| G9 | Final claim/artifact ledger | Prevent planned findings from entering prose early | Hash every table/figure input and state world boundary |

G1–G9 are the minimum evidence for the **stronger measurement-confounding
paper**. The existing item-difficulty reversal is motivation, not a substitute
for G2–G7.

### Evidence required only for additional claims

| ID | Claim | Required evidence | Decision if absent |
|---|---|---|---|
| A1 | Platform-policy affects recovery | Balanced vs curriculum/review/adaptive schedules, logged selection rule/propensity and observed Q geometry | Omit policy result; retain as limitation/future work |
| A2 | Error categories recover information lost by binary labels | Informative-vs-shuffled category experiment with localization and mastery metrics | Do not discuss error-aware KT as a finding |
| A3 | Surface errors are plausible learner language | Independent intended-edit/context validation and alternative-answer audit | Call examples illustrative only or omit |
| A4 | Dialogue reveals an ecology–precision tradeoff | Matched continuum with determinacy, incidental-KC, answer-coverage, and critic disagreement | Keep TSCC motivation only |
| A5 | Conclusions persist across plausible KC worlds | Simulated, outcome-independent alternative worlds with equivalent measurement controls | Describe alternative worlds as hypotheses, not robustness evidence |
| A6 | Observable distributions are platform-plausible | Declared diagnostics and external/pilot ranges; no cherry-picked marginals | Use “scenario” rather than “platform-plausible data” |
| A7 | Items are deployable/learner-answerable | Rendered UI plus teacher/product/learner review or pilot responses | Automated audit cannot support the claim |
| A8 | Intended proficiency/difficulty is appropriate | Explicit level metadata plus expert/learner performance evidence | Do not infer CEFR from source links |

### Current evidence-ledger gaps

Before the ACL manuscript is rewritten, the future paper evidence ledger must
add explicit rows for:

- the full item-audit counts, exact disposition IDs, and single-reviewer
  boundary;
- the KC audit's support, isolation, crossing, nesting, and alternative-world
  metrics;
- every literature-derived claim, with citations added to `paper.bib`;
- matched-family validation and bank hashes;
- each response-world parameter file and event hash;
- model degrees of freedom, regularization, fit/evaluation split, and whether
  items repeat across split;
- policy-specific observed exposure geometry;
- error-category observability versus private failed-KC truth; and
- human/expert evidence, if any, without conflating it with model critics.

## Likely ACL reviewer objections and required responses

### 1. “K* wins because the simulator was built from K*.”

This objection is correct if the result is framed as validation. Reframe the
experiment as a controlled sensitivity test, retain counterfactual same-event
comparisons, and test multiple generator/nuisance worlds. The important result
is when an incorrect representation wins and why, not that the planted model
usually wins.

### 2. “The item text is cosmetic; no synthetic learner reads it.”

This is fully true of full-v1. State it in the first methods paragraph, not
only later. The core extension must give format/item properties a causal role
in response generation and store an executable visible instrument. If that
extension is not complete, do not claim platform-like interaction.

### 3. “LLMs generated, validated, and then audited LLM items.”

Independent model configurations reduce direct self-approval but do not create
human validity. Freeze role-specific critics, report disagreement, show hard
deterministic gates, and present a feasible human protocol. Platform
deployability requires real teacher/product/learner evidence.

### 4. “The KC ontology is arbitrary or circular.”

Agree that it is a declared synthetic world, document activation versus
competence semantics, and compare conclusions across predeclared plausible
worlds. Do not select a generator ontology by the same outcomes it generates.
The KC audit's alternative worlds and definition/activation mismatches should
be visible, not hidden in limitations.

### 5. “Full rank is being mistaken for identifiability.”

Use the term `linear column rank`. Report anchors, support, equality, nesting,
and response-model-specific conditions. Cite the limited assumptions of formal
Q-identifiability results. The A+B-only experiment is useful precisely because
it shows why volume and even rank are incomplete criteria.

### 6. “Format effects are guaranteed by construction.”

The question is not whether a planted offset exists; it is which misspecified
KC model absorbs it, whether a visible nuisance model recovers the shared
state, and whether the effect survives held-out evaluation. Include zero,
shuffled, moderate, and strong controls. Do not claim the magnitude is human.

### 7. “The false split wins only because it has more parameters.”

Report feature/parameter counts and regularization. Require a zero-effect
negative control and held-out learners. Compare the split with explicit
nuisance models at appropriate flexibility. Report mastery RMSE so predictive
flexibility is not mistaken for ontological recovery.

### 8. “Item fixed effects merely memorize repeated items.”

Distinguish same-item future prediction from unseen-item generalization.
Report whether item effects are estimated, hierarchical, or oracle. Do not
compare an oracle item-offset model to an estimated KC model without labelling
it an upper bound.

### 9. “The bank is too small and support is uneven.”

Report family, item, cell, and KC-by-format support rather than only total
items. Avoid prevalence or power claims from rare KCs. A release needs
meaningful crossing and replication, not merely 18/18 rank.

### 10. “There is no evidence a learner would understand or answer these.”

The current census only flags likely issues. Render the response components,
make the scoring policy executable, and obtain at least targeted expert and
learner evidence before deployability claims. Until then, say
`platform-oriented synthetic instrument`.

### 11. “Synthetic marginal similarity would be realism theatre.”

Treat impossible distributions as warnings, not matching as validation. Plant
one mechanism per world, cite only broad anchors, and avoid arbitrary response
times, motivation, dropout, or personality variables unless tied to a tested
alternative explanation.

### 12. “The adaptive schedule creates selection bias.”

That is the point, but it must be measured. Log eligibility/propensity, compare
actual exposure/Q geometry, and avoid interpreting selected histories as
random assignment. Equal opportunity budgets are necessary but not sufficient.

### 13. “Error labels leak the true KC.”

Keep failed KC private. Use a noisy observable category, an oracle positive
control, and a within-item/format shuffled negative control. Evaluate
localization separately. Generated surface text cannot be called realistic
without independent edit validation.

### 14. “The paper is a kitchen sink.”

This is the largest presentation risk. Do not append measurement realism to
the existing four RQs. Center the main paper on measurement nuisance and
identifiability. Preserve construction and legacy experiments as a compact R0
reference plus appendix. Policy, errors, and dialogue enter the main paper only
if they supply a second genuinely distinct causal result.

### 15. “This is educational measurement, not an ACL contribution.”

Make the language-specific reason essential: grammar opportunities require
linguistic canonicalization; response ambiguity and structured grammatical
errors are not generic binary tutor phenomena; dialogue weakens linguistic
opportunity boundaries; and learner-corpus/platform metadata motivate the
observable schema. Do not reduce the contribution to a generic matrix
simulator with English labels.

### 16. “The literature motivates mechanisms but does not calibrate them.”

Agree explicitly. Label magnitudes design scenarios, report a grid, and avoid
population claims. External pilot data would improve plausibility but should
not be overfit or treated as latent ground truth.

### 17. “Three seeds and learner bootstraps understate uncertainty.”

Distinguish learner sampling, simulation seed, item-family sampling, critic,
ontology, and world uncertainty. Add seeds where feasible, but more seeds do
not replace alternative items/worlds. Report which sources are not covered by
intervals.

### 18. “The unseen-grammar claim is overstated.”

All generator KCs have seen support; the 15-cell cohort tests new tuples, and
the six unseen-value cells all involve perfect-progressive aspect. Call this
recombination/extrapolation under known factors, not unrestricted unseen
grammar learning.

## Criteria: new dataset contribution or experiment only

A separate dataset release should be a result of the methodology, not a way to
make a pilot appear larger.

### Release as a new dataset only if all hard criteria hold

1. **Independent identity.** It has a versioned name, immutable parent/full-v1
   hashes, explicit reconstruction command, manifest, and observable/oracle
   schemas. Full-v1 remains unchanged.
2. **Executable measurement instruments.** Every public item specifies
   instruction, visible context/stimulus, response component/options,
   accepted-answer normalization/scoring, format, semantic family, intended
   target, and provenance.
3. **Hard item validity gates.** Every released item passes linguistic
   fidelity, visible answer sufficiency, determinacy/fair scoring, learner task
   comprehensibility, and executable response mechanism. Known answer-space
   failures are repaired with append-only provenance or withheld.
4. **Crossed measurement design.** Formats are crossed with KCs and semantic
   families; no KC is wholly confounded with one format/campaign. Matching is
   based on a shared semantic specification, not cell identity alone.
5. **Meaningful latent measurement.** For the declared flat world, every KC has
   defensible support and the intended Q distinguishability gates. The release
   reports anchors, pair crossings, rare/nested columns, and limitations, not
   rank alone.
6. **Causal utility beyond full-v1.** The extension supports at least one
   analysis impossible in v1—e.g., item/format confounding or diagnostic error
   information—and the retained experiment shows that the new observable
   fields matter.
7. **Coherent platform process.** At least one released history follows a
   transparent platform-oriented policy with inspectable exposure, repetition,
   and order. Laboratory-balanced histories may remain as a control.
8. **Observable/oracle separation.** Public rows contain only plausible log
   fields. Mastery, failed KC, planted effects, response probabilities, and
   random draws stay in separately labelled oracle artifacts.
9. **Scenario honesty.** Difficulty, format, heterogeneity, error, and policy
   parameters are named plausibility scenarios, not human estimates. The
   release does not market one giant world as realistic.
10. **Qualitative and quantitative QA.** Actual easy/hard learners, every
    format, correct/errors, rare KCs, unusual trajectories, and policy exposure
    tails have been inspected and indexed, not only summarized.
11. **Independent validation boundary.** At minimum, independent model critics
    and deterministic gates are retained. A claim of actual deployability or
    learner answerability additionally requires human teacher/product/learner
    review with rendered UI and recorded responses.
12. **Reproducibility.** Item calls, critics, seeds, event generation, models,
    tables, and figures reconstruct; manifests verify; tests and notebooks
    execute; paper claims map to exact artifacts.

Do not invent a numeric minimum item count solely to satisfy a release label.
Justify support through the intended uses, uncertainty, and crossing geometry.

### Keep it as an experiment artifact if any of these conditions applies

- the bank is a small 12-cell/96-item matched pilot optimized for one contrast
  but not useful as a general interaction corpus;
- item/format offsets are arbitrary planted values unrelated to an executable
  item surface;
- format remains confounded with KC, campaign, vocabulary, or target meaning;
- the only new field is an oracle failed-KC label that a platform would not
  observe;
- schedules are only laboratory permutations with no platform-process
  interpretation;
- known ambiguous or artificial items remain in the public bank;
- no stable observable/oracle schema or reconstruction manifest exists;
- the added complexity does not change a conclusion, diagnose a limitation,
  or support a collection recommendation; or
- “platform plausible” relies only on the same agent that built/audited the
  artifacts.

An experiment-only outcome is scientifically acceptable. It may produce a
stronger paper than a premature v2 release.

## Paper decision tree

### Outcome A — only audits are completed

Retain full-v1 as the paper's benchmark and rewrite conservatively. Present the
item/KC audits as an adversarial limitation analysis, elevate activation
equivalence and item-difficulty reversal, and do not claim a plausible platform
dataset. No new release.

### Outcome B — matched bank and nuisance experiment succeed

Adopt the measurement-confounding thesis. Make Figure 2 the central result.
Treat full-v1 as R0 and the crossed matched bank as the causal instrument.
Release the matched bank only if the dataset hard criteria pass; otherwise
publish it as an experiment artifact.

### Outcome C — error-aware result succeeds but matched measurement does not

Do not let error labels rescue a weak item instrument. A failed-KC-derived
category can be informative by construction while the visible task remains
ambiguous. Keep the error study secondary or defer it.

### Outcome D — platform schedule changes recovery

Include the result if exposure geometry explains the change. Do not describe a
simple policy as representative of commercial systems. The conclusion is that
selection policy is a confound under the tested policy, not that one schedule
is educationally superior.

### Outcome E — dialogue loses determinacy

Treat this as evidence for the ecology–precision tradeoff. Do not force broad
coverage by increasingly annotation-like instructions. A well-documented
negative dialogue pilot can strengthen the TSCC motivation without becoming a
release.

## Minimum rewrite order after evidence stabilizes

1. Freeze the final claim/evidence ledger and decide whether Outcome A or B is
   supported.
2. Fix title, thesis, and three RQs.
3. Design the causal-layer figure and core result figure before drafting
   prose.
4. Rewrite results around those displays.
5. Rewrite methods to expose every variable needed to interpret the results.
6. Rewrite introduction/contributions and then the abstract.
7. Rebuild related work around the identified inferential gaps.
8. Rewrite discussion, limitations, and conclusion with world-specific claim
   boundaries.
9. Move historical details to appendices rather than compressing them into
   unexplained result lists.
10. Run an adversarial claim audit: every sentence containing `realistic`,
    `valid`, `recover`, `transfer`, `identifiable`, `learner`, `platform`, or
    `ground truth` must point to the appropriate layer and evidence type.

## Final acceptance test for the paper

A reviewer should be able to answer, without consulting repository history:

- why synthetic truth is necessary;
- why synthetic truth alone does not validate a measurement process;
- what the learner sees and what the simulator actually uses;
- which variables are public, planted oracle truth, or fitted hypotheses;
- what K* means and does not mean;
- whether a result concerns clean-control inference or a plausibility scenario;
- whether item/format effects are observed, estimated, or oracle-provided;
- why a false KC split can predict well;
- which measurement contrasts make KCs distinguishable;
- what richer error information adds beyond correctness;
- which data-collection implications are qualitative versus numerically
  transferable; and
- what human/expert evidence is still absent.

If any answer depends on reading a limitation that contradicts an earlier
contribution claim, the rewrite is not complete.
