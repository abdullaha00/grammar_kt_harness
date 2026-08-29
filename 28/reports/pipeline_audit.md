# Phase 1 repository and methodology audit

Date: 2026-08-27  
Audited snapshot: branch `phase-c-ontology-independent-simulation`, HEAD
`6e52823`, plus the pre-existing uncommitted working-tree changes visible on
2026-08-27.

## Scope and claim boundary

This audit starts from `scripts/run.py`, `README.md`, and
`notebooks/pipeline_walkthrough.ipynb`, then follows every active declaration,
stage function, relevant test, and retained result artifact. It does not treat
fixture responses as scientific evidence and it does not conduct KC selection.

The working tree was already dirty when Phase 1 began. In particular, the
current working tree removes the active controlled lexicon and replaces the old
A2/CEFR validation criterion with `non_target_language_simplicity`. This audit
describes that current working tree while noting where tracked artifacts and
the ACL paper still describe older code.

## Executive assessment

The active implementation has a valuable simple shape: stages receive explicit
scientific objects, candidate KCs do not enter generation or simulation, and
projection happens only after the item bank and learner events exist. Tests
protect these architectural boundaries.

It is not yet an experiment that can answer which KC representation is best.
The active runner uses six fixture descriptors, one item per cell, a manual
factorized policy, a predominantly factorized latent learner world, and a
schedule that puts holdout grammar into learner training history. The retained
fixture schedule contains no compositional-holdout test events. Logistic KT
also receives the exact structural difficulty term used by the simulator, and
the only bootstrap compares KT models rather than KC representations.

The highest-value next step is therefore Phase 2 structural candidate
generation, not outcome-based selection. It should replace fixture-specific KC
lists with development-derived feature values, explicit operation hypotheses,
supported pairwise interactions, full-cell baselines, and transparent support
and duplicate filtering.

## Priority weaknesses and research loop

| Priority | Verified weakness | Why it matters | RQ / hypothesis | Smallest meaningful later test |
|---|---|---|---|---|
| P0 | The active runner freezes a manual factorized policy; the automated selector is only demonstrated in the notebook/tests. | There is no active learner-evidence-based KC method to evaluate. | RQ1–RQ4: development-derived candidates plus predictive/parsimony selection will outperform fixture declarations. | Phase 2 builds the structural space; Phase 3 evaluates selection on development-only outcomes. |
| P0 | The selector lets one interaction discharge two marginal obligations. | In the fixture it removes `kc_past` and leaves the past-passive cell without a past KC. | Existing obligation coverage is not a coherent definition of preserved distinctions. | Replace global set coverage with item/cell-level semantics, or reject this selector as a main baseline. |
| P0 | Holdout items enter acquisition history; the compositional cell has zero test events. | Current grammar-split scores are not a clean compositional-transfer test. | RQ9: a development-acquisition then frozen-probe protocol is the scientifically primary transfer test. | Phase 4B compares mixed history with frozen probes on the same fixed bank/outcomes. |
| P0 | The only latent world is feature-factorized. | KC conclusions may merely recover the simulator's construction. | RQ6: rankings will change across factorized, interaction-heavy, cell-specific, and mixed worlds. | Phase 4C introduces four readable worlds and repeats a small controlled comparison. |
| P1 | Candidate values/interactions and fold IDs are hard-coded to the six-cell fixture. | Candidate growth and generalisation cannot scale or survive cell reordering. | RQ8/RQ14: schema-derived candidates and semantic folds will remain interpretable at 16–24 development cells. | Phase 2 structural inventory; Phase 4A deterministic fold builder. |
| P1 | `operation_tags` are generated but neither validated nor consumed. | They are currently dead metadata and cannot safely support operation KCs. | RQ13: deterministic operations may add nonduplicate information beyond canonical features. | Compare explicit rule-derived operation columns with fixed item tags and feature columns. |
| P1 | Logistic KT uses simulator-derived `item_difficulty`. | It gives one KT model privileged access to the response-generating function. | RQ7: KC conclusions should be robust without oracle difficulty. | Phase 4D makes no-difficulty logistic primary and retains oracle difficulty only as a labeled control. |
| P1 | The paired bootstrap compares KT techniques and resamples events independently. | It does not quantify the KC-policy effect and ignores learner clustering. | RQ19: learner-level paired KC deltas will give valid comparative uncertainty. | Phase 3/5 resample learners and compare policies within each KT model. |
| P1 | Phase-2 eligibility is encoded inside `note`; transition checks preserve only marginal field sets. | The implementation can miss illegal branch recombination or changes to exact eligible values. | RQ12/RQ17: explicit eligibility plus cell-wise descent will be clearer and safer. | Phase 4H replays partial mappings through both transition checks. |
| P2 | `source_support` exposes only opaque IDs. | It supplies no readable support and may be redundant or a target hint when IDs are descriptive. | RQ16: source evidence may add no value beyond a fixed GrammarCell. | Phase 4E compares cell-only generation with concise human-readable source evidence. |
| P2 | Current model-selected lexical material and grammar-only validation are uncommitted and untested scientifically. | The conceptual fix may change naturalness, diversity, and target fidelity. | RQ10/RQ11: model-selected vocabulary and best-of-N improve quality without target drift. | Phase 4E/F controlled live-model item study. |

## Stage audit

### A. Resource boundary

**Object flow.** `data/fixtures/egp_pilot.jsonl` plus
`modules/grammar/resource/egp/schema.yaml` becomes a list of unchanged resource
rows after key validation (`scripts/run.py:38-39,89`;
`src/grammar_kt/io.py:57-74`).

**Scientific decisions.** EGP is the only resource. The required evidence is
the ID, category/subcategory, guideword, can-do statement, and examples; CEFR is
optional source metadata. Examples are withheld from Phase 1 and CEFR is not a
canonical dimension.

**Assumptions and limitations.** The active input is always the six-row fixture,
including in live-model mode. There is no active source sampling declaration,
digest check, source manifest, or CLI source override. The loader checks only
missing/unknown keys, not field types, empty content, duplicate IDs, list shape,
or the declared `id_field`. Active run artifacts do not retain the typed source
or source identity. `data/external/README.md` describes an obsolete external
source CLI and missing files.

**Research questions.** How representative should the source subset be? How
sensitive are cell and candidate inventories to source sampling? Which source
fields materially improve normalisation?

### B. Normalisation

**Object flow.** Typed rows, Phase-1/Phase-2 prompts, the rulebook, schema, and
model settings produce one final mapping with `source_id`, `result`, `cells`,
and `note`; per-call inputs/prompts/raw outputs can be retained
(`scripts/run.py:91-103`; `src/grammar_kt/normalise.py:85-172`).

**Scientific decisions.** Phase 1 uses five descriptor fields and withholds
examples/CEFR. Mappings distinguish exact scalars, bounded unresolved lists,
nulls, and separately supported OR cells. Phase 2 is restricted to partial
mappings with nonempty examples and declared eligible dimensions. Only
`complete` mappings can proceed to canonicalisation.

**Verified weaknesses.** Eligibility is machine-parsed from the beginning of a
free-text note (`normalise.py:47-65`). Names are not checked against the schema
or against uncertain dimensions. Transition validation compares marginal value
sets for ineligible fields (`normalise.py:72-82`), so it does not enforce
cell-wise descent, branch correlations, branch counts, or immutability of exact
fields declared eligible. The fixture has six Phase-1-complete responses and
never exercises Phase 2. Only final mappings are consolidated; paired Phase-1
and Phase-2 results remain buried in call evidence.

**Scale limits.** One or two fresh model calls per descriptor scale linearly,
with no active repeat/adjudication or retry policy. The hard-coded
`PHASE1_FIELDS` tuple duplicates the resource declaration.

**Research questions.** RQ12 asks whether Phase 2 is useful. RQ17 asks whether
explicit eligibility and cell-wise transition validation improve safety and
readability. Repeated-model stability and exact-only coverage bias remain open.

### C. Canonicalisation

**Object flow.** Complete mappings and the canonical schema become deduplicated
exact cells with `cell_id`, six features, and `source_ids`
(`src/grammar_kt/canonicalise.py:33-60`).

**Scientific decisions.** The canonical hypothesis is tense, aspect, voice,
polarity, clause type, and modal identity. Agreement, transitivity, operation
labels, and item wording are explicitly excluded. Equal feature tuples collapse
while source IDs are accumulated.

**Weaknesses.** IDs are ordinal and insertion-order-derived, so adding or
reordering a source can renumber the inventory and invalidate an ID-based fold.
Provenance loses source-cell position, mapping notes, evidence, and relation
rationale. Partial mappings are silently excluded downstream. Schema
constraints cover modal/tense and imperative compatibility but do not fully
characterise all valid single-main-clause combinations.

**Research questions.** Are the six dimensions sufficient for generation and
KCs? Which operation distinctions add information? How should stable semantic
fold identities be represented? How much coverage bias follows from exact-only
inclusion?

### D. Item generation

**Object flow.** Every cell plus generation prompt/rulebook/design/format and
model settings produces `CandidateItem` records with learner-facing text,
answers, self-reported operation tags, and metadata
(`scripts/run.py:109-121`; `src/grammar_kt/generate.py:13-78`).

**Scientific decisions.** The GrammarCell is fixed. In the current working tree
the model chooses common, transparent vocabulary and context; vocabulary is
background knowledge, not a KC. The only format is controlled production and
the design asks for one item per cell. Generation is explicitly denied KC,
fold, learner, simulation, and KT information.

**Verified status of the controlled lexicon.** No active runner or generator
loads one. The old six-row lexicon is retained only at
`modules/items/generation/ablations/controlled_lexicon.jsonl`, and tests protect
the absence of an active dependency. This is a current uncommitted
implementation change, not evidence that model-selected vocabulary is better.

**Weaknesses.** `source_support` contains only source IDs. `operation_tags` are
not checked against the rulebook, judged independently, or consumed downstream.
Candidate types, nonempty answers, answer inclusion/equivalence, and required
format fields are not validated at the record boundary. With N greater than
one, calls receive no variant number, previous candidates, or bank context, so
diversity instructions are prompt-only. There is no retry or best-of-N
selection. Fixture outputs reproduce the old lexical examples and are not
quality evidence.

**Research questions.** RQ10, RQ11, RQ13, and RQ16 cover lexical choice,
best-of-N, operations, and source support. Item variants per cell are also a KC
support-design question.

### E. Independent item validation

**Object flow.** The visible item, intended cell, criteria, validation prompt,
and separate model produce criterion judgments; all required passes retain a
copy of the candidate (`src/grammar_kt/validate_items.py:15-84`). Bank summaries
report acceptance, coverage, simple lexical TTR, prompt duplicates, formats,
and criterion pass rates (`validate_items.py:87-119`).

**Scientific decisions.** Generator reasoning, generation metadata, and
operation tags are hidden. The live defaults use a different model label for
generation and validation. Current criteria use
`non_target_language_simplicity`, matching the grammar-only learner assumption.

**Weaknesses.** `acceptance_rule` is ignored; all-required-pass behavior is
hard-coded. Criterion names are checked but Boolean/note types are not. One
automated judgment is used with no repeated judging, calibration, adjudication,
or human comparison. The nine criteria may be redundant. A rejected sole item
can remove all item support for a cell or grammar regime. Fixture judgments are
canned passes. Prompt-only TTR is bank-size-sensitive and not a realism measure.

**Research questions.** Which validation criteria are necessary and reliable?
What agreement is achieved across models, repeats, and humans? How many accepted
items per cell must exist before the bank is frozen?

### F. Grammar fold

**Object flow.** Cells plus a manual manifest become development,
compositional-holdout, or novel-feature-holdout assignments with copied
features (`src/grammar_kt/fold.py:10-32`).

**Scientific decisions.** Compositional cells may use only feature values seen
in development. Novel-feature cells must contain at least one unseen value.
The fold is not supplied to generation, validation, or simulation outcome
construction as a KC hypothesis.

**Weaknesses.** The declaration assigns exactly `cell_001` through `cell_006`
and tests lock the 4/1/1 split. Ordinal cell IDs make it order-fragile. There is
no deterministic fold builder, interaction-coverage analysis, minimum split
size, accepted-item support requirement, or requirement that novelty isolate a
single unseen feature. The sole novel cell introduces multiple unseen values.

**Research questions.** RQ8 covers scalable fold construction. RQ9 covers the
learner protocol needed to turn a structural fold into a transfer test.

### G. Learner simulation

**Object flow.** The fixed accepted bank, fold rows, and world declaration
produce chronological response events plus optional private oracle diagnostics
(`src/grammar_kt/simulate.py:45-132`).

**Scientific decisions.** The fixture uses 24 learners, four exhaustive passes,
rotating order, Beta initial mastery, fixed feature-specific learning rates, an
arithmetic mean over active mastery, logistic response noise, and a 60/20/20
temporal split. Mastery moves toward one after every opportunity regardless of
correctness.

**Verified strengths.** Simulation accepts no KC policy or candidate space.
Tests protect that boundary, and seeded runs are deterministic.

**Verified weaknesses.** Hidden mastery is factorized into past, progressive,
passive, negative, question, and modal dimensions. There are no latent
interactions or cell-specific skills. All accepted items, including grammar
holdouts, enter every learner history. The retained schedule gives the
compositional item three training exposures and one validation exposure but no
test exposure; the novel item is seen twice in training and once in validation
before its test exposure. `item_order` and `learning_update` declarations are
not read; rotation and the background learning rate `0.08` are hard-coded.
There is no item-specific lexical/contextual noise, and exhaustive presentation
does not scale realistically.

**Research questions.** RQ6 asks for robustness across latent worlds. RQ9 is
answered narrowly for the current protocol: it does not genuinely test pure
compositional transfer. Scheduling, learning-update, correlation, and
compensatory mastery assumptions need later sensitivity checks.

### H. KC representation and selection

**Object flow.** The active baseline directly freezes
`modules/kcs/policies/factorized.yaml` (`scripts/run.py:154-156`). A separate
`select_kcs` function consumes cells/items/fold plus candidates, obligations,
and selector declarations, but is called only by the notebook and tests
(`src/grammar_kt/kc.py:138-185`).

**Scientific decisions.** Three predefined extremes exist: marked factorized
features, factorized plus two manual interactions, and one KC per exact cell.
The demonstration selector greedily covers declared marginal obligations and
optionally backward-prunes.

**Verified weaknesses.** Candidate feature values and interactions are a
fixture list, and seven pilot KC names are hard-coded in `_kc_id`
(`kc.py:34-44`). Selector ranking strings are ignored; the tuple ranking is
hard-coded. `background_conditions` is unused. Items affect only IDs recorded in
metadata, not candidate support, and learner outcomes are absent. An interaction
lists both constituent features in `represents`, so it can satisfy both global
marginal obligations. The fixture test explicitly expects `kc_past_negative` to
replace `kc_past` and `kc_negation`; this leaves other past or negative cells
without those distinctions. The full-cell policy dynamically invents KCs for
holdout cells during projection rather than freezing a finite development
inventory.

**Research questions.** RQ1–RQ4 are entirely open. RQ13 asks whether operations
add nonredundant signal. Phase 2 must first establish the allowed structural
hypothesis space.

### I. Projection and Q-matrix

**Object flow.** Fixed items, exact cells, and a frozen policy become one list
of KC IDs per item and a dense CSV Q-matrix (`src/grammar_kt/kc.py:188-225`).

**Scientific decisions.** Projection is mechanical and normally depends only
on canonical cell features through a deliberately small `cell`/`all`/`any`
activation language. Background feature values are omitted by manual policies.

**Strengths.** Policy changes occur after items/events and do not mutate them.
The invariant is protected by tests.

**Weaknesses.** Items with the same cell cannot differ by validated operation.
Empty projections are allowed and silently fall back to overall learner history
in KT. Unsupported declared KCs disappear from both Q-matrix columns and
reported inventory. Full-cell projection uses unstable ordinal IDs. Dense
output scales as items by KCs; later redundancy checking is quadratic in KCs.

**Research questions.** RQ5 must distinguish structural ID reuse from actual
predictive transfer. Phase 2 should create an explicit candidate support table
before projection.

### J. Knowledge tracing

**Object flow.** Events, projection, and KT protocol produce per-event
probabilities for empirical, BKT, and logistic techniques
(`src/grammar_kt/kt.py:109-159`).

**Scientific decisions.** Empirical histories use Beta smoothing. BKT has fixed
initial/learn/guess/slip parameters. Logistic regression uses prior learner and
active-KC rates, prior opportunities, item difficulty, KC count, and KC
indicators. History features are computed before the current response is used;
a test protects this contract.

**Weaknesses.** Logistic directly consumes `event["item_difficulty"]`
(`kt.py:51`), the exact structural term used in simulation (`simulate.py:26-33,
84-106`). Empirical and BKT do not receive it. BKT averages active KC mastery and
updates every active KC from the same response; empirical KT similarly credits
every active KC, so adding interactions changes model dynamics as well as the
ontology. Training includes holdout-grammar events because the simulator labels
them temporal train. `history` and `evaluation_split` declarations are
documentary; split behavior is hard-coded. Fixed regularization is compared
across representations of different dimensionality.

**Research questions.** RQ7 asks which KT model should drive selection and how
stable selected KCs are across models. Phase 4D must remove oracle difficulty
from the primary model and audit multi-KC semantics.

### K. Evaluation

**Object flow.** Dataset, fold, event, policy, projection, and prediction records
produce dataset, representation, KT, grammar-split, and bootstrap metrics
(`src/grammar_kt/evaluate.py:110-156`).

**Scientific decisions.** Metrics include log loss, Brier, AUC, ECE, accuracy,
item/event coverage, Q density, KCs/item, KC support, identical activation
columns, and a structural compositional-coverage measure.

**Weaknesses.** `primary_metrics` and `diagnostic_metrics` declarations are not
read; only ECE bins and bootstrap settings affect code. Structural
`compositional_coverage` means that assigned KC IDs appeared on some development
item, not that outcomes generalise. The bootstrap compares KT techniques within
one representation, not KC representations, and resamples events rather than
learners. The retained factorized result reports structural compositional
coverage 1.0 while every compositional test metric has `n=0`. No current result
supports a KC ranking.

**Research questions.** RQ1 and RQ5 need representation-level predictive and
generalisation comparisons. RQ19 asks for learner-level paired uncertainty
within each KT model.

## Disposition of the specifically flagged issues

| Potential issue | Audit verdict |
|---|---|
| Normalisation machine state in `note` | Verified. Replace experimentally with an explicit field in Phase 4H. |
| Controlled lexicon active despite grammar-only vocabulary | Not active in the current working tree; historical ablation only. Scientific comparison remains unanswered. |
| `operation_tags` retained but unused | Verified. Do not trust as KC evidence without deterministic/independent validation. |
| `source_support` contains opaque IDs only | Verified. It is not meaningful support content. |
| Validation CEFR wording mismatches grammar-only model | Resolved in the current uncommitted working tree; not yet live-tested. |
| Fold hard-coded to six cells | Verified in the declaration and tests. |
| Simulation resembles factorized KCs | Verified directly; comparative bias is a strong inference to test across worlds. |
| Holdout items enter learner history | Verified; the current protocol is mixed history, not frozen probe. |
| Oracle difficulty enters logistic KT | Verified. |
| Selector declarations unused/partly hard-coded | Verified; selector is inactive in the runner, ranking/background declarations are ignored. |
| Interaction KCs satisfy marginal obligations questionably | Verified and protected by a test; unsuitable as the main selector semantics. |
| Statistics emphasize KT models rather than KC representations | Verified. |
| Paper methodology is stale | Verified throughout `ACL/`; defer comprehensive rewrite until Phase 7. |

## Test and evidence audit

The current tests protect several important contracts:

- generation has no KC, fold, simulation, learner, or controlled-lexicon input;
- simulation has no candidate-KC/Q-matrix input;
- predefined policy changes do not mutate accepted items or events;
- selected-policy discovery ignores holdout cell content;
- KT history features use prior events only;
- the notebook calls active functions and defaults to fixture mode without live
  model calls.

Important missing contracts correspond to methods not yet implemented:

- development-derived candidate generation and duplicate collapse;
- selection invariance to holdout outcomes;
- controlled toy recovery of interactions and complexity-penalty sensitivity;
- accepted items/events invariant across automated KC methods;
- frozen-probe acquisition excludes holdout items;
- grammar-regime coverage in each scored split;
- no oracle difficulty in the primary KT model;
- operation-tag/rule agreement.

Phase 1 verification command:

```bash
.venv/bin/python -m pytest -q
```

Final Phase 1 verification result: `25 passed in 3.27s`.

## Retained artifact audit

- `runs/research_pipeline_20260827/` and
  `runs/research_modularity_20260827/` demonstrate fixture wiring and the
  fixed-item/fixed-event boundary, but their schemas predate current working-tree
  lexical/validation changes. They are not current item-quality or KC evidence.
- `runs/base`, `runs/kc_interactions`, and `runs/kc_full_cell` are older
  policy-dependent experiments. Their item banks and event streams differ by KC
  policy, so cross-policy KT numbers violate the present experimental boundary.
  `runs/*` is currently ignored, making new run artifacts nonpersistent unless
  explicitly exempted or copied to a tracked research path.
- `experiments/post_training_v1/data/pilot_v1/opportunities.jsonl` is tracked and
  contains 42 fixed opportunities spanning 24 legacy canonical cells (16
  development, seven compositional, one novel-feature according to the retained
  report). It is useful as a structural-only Phase 2 stress inventory after an
  explicit schema compatibility check. Its old policies, items, and outcomes
  must not be imported into a KC comparison.
- `experiments/post_training_v1/report.md` establishes a separate negative
  result about generation-preference supervision, not KC selection.
- `ACL/sections/` and `ACL/evidence.md` describe the superseded deterministic
  realizer, policy-conditioned item banks, content-derived IDs, five items per
  KC, and the old simulation. They are historical until Phase 7.

## Exact Phase 2 handoff

Phase 2 should remain structural and outcome-free.

The starting hypotheses should be recorded before implementation:

- **H2.1 (RQ14):** enumerating observed schema values will expose more valid
  candidates than the seven fixture declarations, but support and identical
  activation filtering will keep growth modest at the 16-development-cell
  legacy scale.
- **H2.2 (RQ13):** operations determined solely by a GrammarCell will often be
  activation aliases of feature KCs; realization-dependent operations such as
  DO-support may add distinctions, but only if their item activation is
  independently reproducible.
- **H2.3 (RQ15):** explicitly declared background/reference values will avoid
  placeholder/complement candidates without hiding the rule in Python.
- **H2.4 (RQ20):** the one-item-per-cell fixture is too sparse to justify most
  interactions; a medium structural inventory will reveal whether a simple
  minimum item-support rule is usable.
- **Negative control:** mutating or deleting grammar-holdout content must leave
  the complete candidate inventory and support artifact byte-for-byte
  unchanged.

1. Read `reports/research_state.md`, `reports/experiment_log.md`, and this audit;
   verify every referenced input exists.
2. Create one compact active declaration, preferably
   `modules/kcs/candidate_design.yaml`. Include only candidate families, any
   explicit background/reference-value treatment, and item-support threshold.
3. Implement a linear candidate transformation that receives the canonical
   schema, development cells, and fixed development items only. It must not
   accept learner events or inspect grammar-holdout features.
4. Derive every observed feature-value candidate from schema-valid development
   cells. Do not encode the seven fixture values in Python.
5. Treat operations as hypotheses with explicit deterministic activation. Audit
   current item tags against those rules; do not admit unvalidated model tags by
   default. If operations are wholly redundant or unreliable, recommend
   removing the metadata.
6. Generate pairwise interactions only across compatible unary candidates from
   distinct grammatical dimensions/operations and only when supported by a
   development cell/item. Do not generate arbitrary higher-order conjunctions.
7. Retain exact development-cell candidates as the fine-grained baseline, even
   when too sparse for the selectable pool.
8. Produce a simple support artifact with candidate ID/type/rule, supporting
   development cells/items, duplicate target, and retained flag. Collapse
   identical activation columns and report low support rather than hiding it.
9. Run first on the active four development fixture cells as a contract test.
   Then extract only the development portion of the tracked 24-cell legacy
   opportunity artifact, validate its cells against the current schema, and use
   it for the medium structural count experiment. Label this input as legacy
   structural evidence.
10. Add tests for development-only discovery, holdout-content mutation,
    schema-derived values, supported interactions, duplicate columns, item
    support, and absence of events/outcomes from the API.
11. Retain Phase 2 outputs under a tracked path such as `reports/phase2/`; new
    `runs/*` paths are ignored by the current `.gitignore`.
12. Report candidate growth, support, duplicates, feature coverage, rejected
    operation types, and the recommended Phase 3 candidate pool. Stop before
    learner-evidence selection.
