# Measurement-realism extension methodology

Status: completed controlled methodology programme; **no new dataset release**.
The immutable reference remains `data/grammar_kt_full_v1/`. The controlled
scenario supplies structural sensitivity evidence only. Human/expert review is
still required for learner-facing release validity.

## Scientific purpose

Real language-learning logs expose responses but rarely expose trustworthy true
grammatical opportunity boundaries, a true KC ontology, a true Q-matrix,
counterfactual learner states, or latent mastery. Synthetic data make those
objects available, which permits experiments that cannot be scored against real
logs. Known truth alone does not make the observable measurement valid. This
programme therefore treats the dataset as an experimental instrument and asks
two questions simultaneously:

1. **Internal validity:** is the generator world fixed, outcome-independent,
   replayable, and suitable for the intended counterfactual?
2. **Measurement/ecological plausibility:** could a learner understand and
   answer the visible task, and could the item and history plausibly occur on a
   language-learning platform?

The programme deliberately does not collapse these layers:

```text
GrammarCell
→ declared generator K* and Q*
→ visible instrument (prompt, context, format, response mechanism)
→ assignment policy and learner process
→ observable response/error
→ fitted K-hat, Q-hat, and KT state
```

`GrammarCell`, generator KC, observable error label, and discovered KC remain
different scientific objects.

## Immutable clean-control anchor

Before any extension work, the full-v1 manifest, Q projection, learner stream,
and headline results were replayed. The anchor is recorded in
`experiments/measurement_realism/baseline_anchor.json`.

- protected Git tree: `a3d77782cd1d4a5b297cc6d63eba2551d8d71ce4`;
- 75 GrammarCells, 18 declared generator KCs, 113 items;
- 113-by-18 Q*, rank 18, 269 active edges;
- 1,000 learners and 283,000 observable events;
- private oracle state remains separate;
- no worktree change under `data/grammar_kt_full_v1/`.

Full-v1 is retained as **R0: clean Q-driven control**. Its prompt surface is
stored and auditable, but prompt wording does not cause simulated responses
after Q* is fixed. It is not retrospectively called platform-valid.

## Platform and learner-facing audit

### Dimensions and evidence sources

The complete 113-item census kept separate judgments for:

- task comprehension;
- answer determinacy and accepted-answer coverage;
- pedagogical plausibility;
- format/UI plausibility;
- lexical and contextual burden;
- difficulty plausibility;
- response-space fairness;
- KC measurement purity and shortcuts;
- platform deployability.

The strict item-level ledger is
`experiments/measurement_realism/audits/item_audit/item_level_audit.jsonl`.
A second fixed-call audit used learner, teacher, platform-product, and
measurement roles and retained all 452 role judgments. The deterministic
cross-audit synthesis is
`experiments/measurement_realism/audits/platform_audit_synthesis.json`; the
authoritative interpretation is `reports/platform_plausibility_audit.md`.

These are automated/non-human stress tests. They identify likely defects and
disagreement; they are not evidence of actual learner comprehension or expert
deployability.

### Audit decision rule

No realism composite was optimized. Critical answer insufficiency or an
undefined response mechanism is a hard concern even if prose is natural.
Disagreements remain visible by role and item. The two audits agreed exactly on
70/113 labels. Sixty items were usable under both mappings, 53 appeared in the
union of action-required items, and 18 appeared in the union of critical
answer-space/withhold concerns. The live four-role audit disagreed internally
on 56/113 items. Those numbers constrain claims about this bank; they are not
population prevalence estimates.

## Generator-KC methodology audit and induction stress test

The 18 full-v1 columns remain a declared generator world because they are
explicit, deterministic before learner outcomes, reusable across cells, and
structurally full rank. The pedagogical audit in
`reports/kc_methodology_audit.md` changes their description: they are
**feature-linked latent factors with operation-motivated names**, not validated
human cognitive atoms.

The audit measured support, isolates, nesting/co-occurrence, pedagogical
interpretability, transfer interpretation, and possible lexical/format
confounds. Only 16/113 rows are single-KC opportunities and six KCs lack an
isolating row. Full numerical rank establishes linear column independence for
this bank; it does not establish psychological independence or generic
response-model identifiability.

An outcome-blind induction stress test then supplied only frozen GrammarCells,
support information, and a predicate grammar to three independent
`gpt-5.6-terra` medium calls. Prompts, inputs, settings, raw proposals, parsed
outputs, and hashes are retained under
`experiments/measurement_realism/kc_induction_v1/`. Hypotheses were
canonicalised by cell-activation signature, not wording. The three runs
produced 17/18/18 unique signatures with ranks 17/18/17; only nine signatures
were shared by all runs, the union contained 30, pairwise activation Jaccard
was .400--.458, and only 5/4/7 columns exactly matched K*. This supports
multiple plausible generator worlds and rejects presenting one model proposal
as recovery of uniquely correct psychological KCs.

## Matched-format bank protocol

### Pre-outcome design

A 12-cell design cannot have rank 18 when each lexical/format variant preserves
its cell Q row. The confirmatory target was therefore frozen as:

- 18 seen cells selected without learner outcomes and with cell-Q rank 18;
- one unseen-combination and one unseen-value probe cell;
- four formats: constrained cloze, dialogue completion, multiple choice, and
  sentence transformation;
- two semantic variants per seen cell and one per probe cell;
- 144 seen acquisition slots and eight non-updating probe slots.

The canonical selection is
`experiments/measurement_realism/design/format_selection/selected_cells.json`
(SHA-256
`8f8fa56e710982c92426f154482d062cffebfb32d29f19c7fe96f4208a4b479b`).
Matched families had to preserve GrammarCell and Q while using a shared
semantic specification. Generation, deterministic gates, independent solver
attempts, linguistic/measurement/product critics, curation schemas, retries,
and raw call evidence were frozen under
`experiments/measurement_realism/design/bank_protocol/`.

### Failure is retained as evidence

The scientifically valid run completed 178 model calls with no technical
failure: 106 candidates, 712 independent solver attempts, and 90 role
judgments over three declared rounds. Only 5/38 complete families (20/152
slots) passed all gates. The accepted subset covers 4/20 cells and 6/18 KCs;
seen Q rank is 3 and all-regime rank is 4. The measurement critic accepted
9/30 critic-reached candidates, compared with 29/30 linguistic and 24/30
product decisions; 23/30 had mixed role decisions. Dialogue completion had
the weakest solver evidence.

The two earlier attempts are labelled infrastructure-only: one provider-schema
preflight failed before inference, and one completed generation exposed a
speaker-label reconstruction bug before solvers or critics. The corrected run
is the only scientific bank result. Original outputs were not silently
repaired.

Because exact family crossing, cell/KC coverage, held-out coverage, rank, and
response-space gates failed, no curated bank was frozen and no
`grammar_kt_measurement_v1` dataset is released. The 20 passing slots are not a
partial release.

## Controlled structural sensitivity scenario

The failed learner-facing bank left an important counterfactual question but
removed the basis for a platform-valid dataset. A separate content-free
instrument therefore instantiates only the frozen 38-family/152-slot geometry
and format labels. It deliberately has no prompt, target answer, or accepted
answer set and carries `release_eligible=false`. Its sole permitted use is
controlled structural sensitivity analysis.

The configuration and exact claim boundary are in
`experiments/measurement_realism/design/controlled_instrument_v1/`; the study
plan SHA-256 is
`e3d50e10001b7dff8042b002aba04b595bb8d95e496bd66beebae08e4d678667`.
The append-only execution record does not modify the preregistration.

### Response model and worlds

For active KCs, let `m` be minimum mastery. Responses use

```text
p = g_l + (1 - g_l - s_l) × logistic(
      logit(m) + learner_ability + format_offset - item_difficulty)
```

with keyed common random numbers. Learning updates every active KC by the
declared opportunity rule, without forgetting. The six separate worlds are:

| World | Item SD | Format SD | Ability SD | Learning-rate CV | Noise heterogeneity |
|---|---:|---:|---:|---:|---|
| clean zero | 0 | 0 | 0 | 0 | no |
| format moderate | 0 | .35 | 0 | 0 | no |
| format strong positive control | 0 | .70 | 0 | 0 | no |
| item moderate | .50 | 0 | 0 | 0 | no |
| item + format moderate | .50 | .35 | 0 | 0 | no |
| combined heterogeneous | .50 | .35 | .35 | .25 | yes |

These are planted sensitivity magnitudes, not estimates of humans. Seen-item
effects are orthogonal to intercept, format contrasts, and Q over the 144
equally weighted seen item slots. That is bank-design orthogonality, not exact
orthogonality under the 188-event acquisition multiset.

Five hundred learners and three seeds were used per world. Each run contains
188 acquisition events and 152 non-updating terminal probes (170,000 events).
The response matrix contains 18 Q-balanced world/seed runs plus nine
combined-world alternative-policy runs: 4,590,000 events in total. Observable
events and private oracle rows are separate.

### Competing observable models

The learner-disjoint, causal-history bounded-logistic comparison is:

```text
A  shared K*, no format/item covariates
B  false format-specific split KCs
C  shared K* + observable format contrasts
D  shared K* + format + seen-item residual basis
```

Training uses acquisition rows from training learners; dev seen probes select
regularization; final fitting uses train+dev acquisition; held-out test learners'
terminal probes are evaluated. Standardization is fit on training acquisition
only. Primary scope is seen probes, with grammar-regime results retained
separately. Metrics include log loss, Brier score, fixed-width ECE, AUC, and
item-prerequisite state RMSE. Learner-paired bootstrap intervals condition on
the frozen fit, bank, seed, and simulator world; they do not include refitting,
item/cell sampling, bank construction, simulator uncertainty, or multiplicity.

Model D is an oracle-aligned positive control: the planted seen-item effects are
constructed in the exact residual space represented by D. Its success tests
whether known, fully spanned stable nuisance can be recovered. It is not a
general item-difficulty remedy and says nothing about unseen-item nuisance.

## Assignment-policy analysis

All policies use the same 188-event budget. Q-balanced laboratory assignment is
the internal-validity reference. Curriculum and mixed-practice policies reorder
the same fixed occurrence multiset using grammar/item metadata. The adaptive
policy uses observable cell-level Beta-smoothed correctness, exposure, spacing,
and keyed exploration; it cannot read K*, Q*, latent mastery, future outcomes,
or planted nuisance.

Because learning is unconditional and order-independent, Q-balanced,
curriculum, and mixed schedules have identical terminal oracle mastery by
construction. Their comparison is about history morphology and model fit, not
learning efficacy. Adaptive assignment changes exposure and can change terminal
state. Propensities are logged design diagnostics, not a full off-policy
evaluation guarantee.

The original confirmatory analysis matrix included policy response/exposure
diagnostics but not alternative-policy model fits. The latter are therefore
frozen and reported append-only as a post-response exploratory analysis under
`worlds/controlled_instrument_v1/policy_recovery_v1/`, with its timing
disclosure and already-inspected diagnostics explicit.

## Structured errors

For an incorrect multi-KC event, private `failed_kc` is sampled proportional to
the active mastery deficits. It is a post-outcome diagnostic attribution, not a
claim that a human error has one causal KC. A small operation-grounded taxonomy
maps KCs to categories such as tense/finite form, negation, auxiliary or
participle, question formation, and modal choice/complement.

Four observable streams preserve every non-error field and outcome:

- binary only;
- category linked to the planted attribution (positive control);
- linked category exposed on 80% of incorrect rows and otherwise unresolved;
- within-item/phase shuffled labels (negative information control).

The current row's error is unavailable until after its prediction, preventing
same-row leakage. Error-aware model D uses only prior errors. Evaluation covers
next-response metrics, failed-KC localisation on incorrect multi-KC probes, and
a secondary Beta-smoothed terminal KC evidence diagnostic. That diagnostic is
not fitted KT mastery.

Surface learner-error text was not scaled. Structured categories already answer
the information-loss question under known truth, whereas generated text would
add unvalidated realism and response-scoring ambiguity without human/corpus
validation.

## Dialogue/openness continuum

Four matched families were rendered at five openness levels: cloze, sentence
transformation, contextual production, dialogue completion, and open dialogue.
Four fixed generation calls produced 20 opportunities; 20 independent
family-by-role critic calls produced 100 judgments. Prompts, settings, raw
outputs, schemas, evidence bundle, hashes, and verification are retained under
`experiments/measurement_realism/dialogue_pilot_live_v1/`.

Dimensions remain separate: interaction naturalness, answer determinacy,
response-family lower bound, incidental grammar, shortcut availability, KC
attribution, and platform plausibility. No scalar realism score is reported.
The pilot is automated evidence only. The planned expert/learner protocol is
`experiments/measurement_realism/dialogue_pilot/human_expert_validation_protocol.md`.

## Dataset-release rule and next validation

A versioned measurement dataset would require executable learner-facing
instruments, critical answerability gates, genuine KC-by-format crossing,
observable/oracle separation, documented policy, independent validation, and a
complete reconstruction manifest. The matched-bank run failed those gates, so
the controlled scenario remains an experiment, not a dataset.

The smallest defensible next construction is a separately versioned declared
correction layer linked to the immutable raw candidates, followed by full
deterministic/solver/critic replay. If it passes, measurement/platform claims
still require rendered expert review and a learner response-process pilot. No
human judgments are fabricated in this programme.
