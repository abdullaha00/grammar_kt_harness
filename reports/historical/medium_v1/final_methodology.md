# Historical medium-v1 executable methodology

This report describes the active method after Phases 2--7.  The compact state
and experiment ledger remain authoritative for conclusions and exact runs:
`reports/research_state.md` and `reports/experiment_log.md`.  Quantitative
dataset claims come from `reports/phase6/artifacts/full_dataset_analysis/`.

## Pipeline

```text
typed EGP descriptors
→ constrained two-phase normalisation
→ exact English GrammarCells
→ N=3 contextual controlled-production candidates
→ deterministic packaging checks + independent validation
→ frozen, curated item bank
→ outcome-free semantic grammar fold
→ development acquisition + non-updating frozen probes
→ development-derived structural KC candidates
→ support / activation-equivalence filtering
→ development-validation predictive-parsimony selection
→ frozen KC policy + item–KC projection
→ empirical, BKT, and observable-logistic KT
→ regime metrics + learner-paired representation comparisons
```

The central causal boundary is simple: item generation and learner simulation
cannot receive a KC policy; candidate discovery receives development cells and
fixed development items but no outcomes; selection receives development
train/validation evidence but no grammar holdout or reserved test event.  The
selected policy is frozen before any grammar-holdout projection or evaluation.

## Stage-by-stage method

| Stage | Input | Active method / researcher declaration | Retained output | Evidence and alternatives |
|---|---|---|---|---|
| Source | 139 typed English Grammar Profile descriptors | EGP field contract in `modules/grammar/resource/egp/schema.yaml` | `source/descriptors.jsonl`, manifest | Phase-1 audit retained the existing structural inventory; other resources are not studied. |
| Normalisation | descriptor and, only when eligible, examples | Descriptor-only Phase 1; Phase 2 may narrow explicitly uncertain dimensions while preserving branches. Prompts/rulebook live under `modules/grammar/resource/egp/normalisation/`; new live runs use declared `gpt-5.6-sol`/high. | 44 complete, 77 partial, 2 unresolved, 16 out-of-scope mappings | Phase-4 replay: only 2/80 legacy Phase-2 calls resolved; explicit eligibility avoids 71 unnecessary calls and rejects six unsafe transitions. BACKEND-THINKING-001 operationally prefers high, but its strict gate is inconclusive and the retained mappings used medium. |
| Canonicalisation | complete mappings | Exact tuple over declared English dimensions `tense, aspect, voice, polarity, clause, modal` in `modules/grammar/canonical/schema.yaml` | 24 cells and 48 source→cell edges | Interpretable hypothesis, not cognitive ground truth; 44 complete descriptors compress to 24 cells. |
| Item generation | one fixed GrammarCell | Three independent `gpt-5.6-sol`/medium candidates using common model-selected language, English rules, bank design, and controlled-production format under `modules/items/generation/` | 78 attempts, 77 payloads | N=1/2/3 curated prefixes cover 16/19/22 cells. Controlled lexicon under-covered the eight-cell pilot; N=5 added no pilot coverage. |
| Coverage fallback | frozen zero-coverage cohort | Two unchanged-method draws; after repeated determinacy-only failure, two separately labelled draws whose instruction names the construction | Rescue and intervention evidence with distinct provenance | Rescue accepted 1/4; corrected explicit-cue evidence accepted 2/2 for the final hard cell. The cue trades contextual realism for determinacy. |
| Validation/curation | generated payload and intended cell | Deterministic slot check followed by one independent `gpt-5.6-terra`/medium all-required-criteria judgment. Freeze packaging-only fixes and independently revalidate them. | 54 accepts, 44 selected items, immutable raw and curated layers | Repeat/alternate-model agreement is .826/.792 without human gold. Six corrections caused three acceptance flips; model judgment is a limitation. |
| Grammar fold | fixed cells/items only | Deterministic semantic coverage rule in `modules/simulation/folds/semantic.yaml` | 18 development, 5 compositional, 1 novel-value (`modal=would`) cells | ID/order invariant. All compositional feature values occur in development, though 1/37 value pairs does not; novel regime has one value and two items. |
| Learner evidence | fixed bank/fold | Five passes of development-only acquisition, then one non-updating all-bank probe, declared in `modules/simulation/protocol.yaml`; factorized, interaction-heavy, cell-specific, and mixed worlds are sensitivity data-generating processes | 1,000 learners and 204,000 events in the final mixed world | Frozen probes remove holdout practice. Mixed-history comparison showed direct holdout exposure and is not primary. Synthetic worlds do not model human cognition. |
| KC candidates | declared schema, English operation declarations, development cells/items | Generic enumeration of non-background observed feature values, declared cell-deterministic operations, cross-dimension observed pairs, and exact development cells; support and activation equivalence computed on development items | 55 raw candidates, 38 activation classes, 42 support-eligible, 28 selection-eligible | Config: `modules/kcs/candidate_design.yaml`; require ≥2 cells and ≥3 items for pair eligibility. Full cells are a structural extreme, not active additions. |
| KC selection | candidate inventory + development train/validation events | Protect supported feature marginals; greedily add the candidate with best validation log-loss improvement after `0.0005 × #KCs`, stop at no objective gain, then backward-prune additions | 10-KC frozen policy and selection trace | Config: `modules/kcs/selection.yaml`. λ=.0005 uniquely gave 0/3 additions in both clean null controls and 3/3 joint recovery of eligible strong interactions at 240 learners among tested penalties. Obligation and BKT selectors were rejected. |
| Projection | all fixed items/cells + frozen policy | Deterministic activation of frozen definitions | projections and Q-matrices for four policies | The automated policy contains nine marginals plus perfect×negative. Candidate aliases are explicitly bank-specific. |
| KT | identical event stream + one projection | Empirical baseline, fixed mean-credit BKT, and standardized observable PFA-style logistic; primary logistic uses prior observable history only | predictions by policy/model | Simulator difficulty and KC count were removed from primary logistic; BKT's shared full-credit multi-KC update is a documented confound. |
| Evaluation | predictions, fold, fixed learners/events | Log loss, Brier, AUC, ECE by regime; primary policy differences use 5,000 whole-learner paired bootstrap resamples | metrics and 12 paired comparisons | Automated−factorized Δ log loss is −.000375 [−.000631,−.000109] overall, but compositional and novel-value intervals cross zero. No universal representation wins across worlds. |

Per-stage model and reasoning settings are the compact scientific declaration
`modules/model_backends.yaml`. A fresh matched audit retains Sol/high for new
normalisation and Sol/medium plus Terra/medium for generation and validation.
These operational settings do not retroactively alter the final dataset: its
source, item, and judgment artifacts retain their original all-medium
provenance. Full evidence and strict inconclusive outcomes are in
`reports/backend_thinking/analysis.md`.

## Active KC methodology

### Candidate construction

`make_kc_candidates(schema, development_cells, development_items, design)` is
outcome-free and language-agnostic.  It follows the declared dimension order,
observes only development values, and excludes explicit background/reference
values.  Readable IDs are derived deterministically from dimension/value
pairs.  Pair candidates join compatible unary candidates from different
dimensions only when they co-occur; arbitrary higher-order conjunctions are
not generated.  Exact-cell candidates cover development tuples only.

English operations are data declarations, not branches in the generic KC
code.  Each operation has a tuple predicate over declared features.  Operations
whose activation duplicates another candidate on the measured bank remain
inspectable but are ineligible as duplicate additions.  Equivalence therefore
means identical binary activation over this development item bank, not
universal linguistic identity.

Every candidate records supporting development cell IDs, item IDs, support
counts, activation vector, eligibility, any representative alias, and rejection
reason.  This turns rare candidates into reported evidence instead of silently
dropping them.

### Evidence-based selection

`select_kcs(candidate_inventory, development_events, selection_design)` uses a
chronological development split already marked on the frozen event stream.  Its
selector model is observable logistic KT: each response is predicted only from
prior attempts and successes on active KCs.  The score is

```text
development-validation log loss + 0.0005 × number of KCs.
```

Supported feature-value marginals form the protected initial representation.
At each forward step, every eligible non-initial candidate is evaluated; the
best objective reduction is retained if positive.  A backward pass removes an
added KC if its deletion improves the same objective.  Deterministic tie rules
make the trace reproducible.  The result is serialized as a `FrozenKCPolicy`
and thereafter projection is mechanical.

At final scale, all five 1,000-learner mixed-world seeds select the same nine
marginals plus `aspect=perfect × polarity=negative`.  A 120-learner prefix
selects a different interaction, whereas 60/240/500/1,000 prefixes match the
reference; the study supports the current ≥240-learner working rule but does
not establish human-data sample complexity.

## Researcher-facing scientific configuration

```text
modules/
├── model_backends.yaml
├── grammar/
│   ├── canonical/{schema.yaml,english_operations.yaml,rationale.md}
│   └── resource/egp/{schema.yaml,normalisation/{phase1.txt,phase2.txt,rulebook.md,...}}
├── items/
│   ├── generation/{prompt.txt,rulebook.md,design.yaml,formats/controlled_production.yaml}
│   └── validation/{prompt.txt,criteria.yaml}
├── simulation/
│   ├── folds/semantic.yaml
│   ├── protocol.yaml
│   └── worlds/{phase4_factorized.yaml,phase4_interaction_heavy.yaml,phase4_cell_specific.yaml,phase4_mixed.yaml}
├── kcs/{candidate_design.yaml,selection.yaml}
└── evaluation/{protocol.yaml,kt/protocol.yaml}
```

These files expose interventions that change a scientific assumption.  Fixture
responses, legacy reference folds, comparison policies, and rejected methods
are not active methodology declarations.

## Paper-facing code

The substantive active code is deliberately small:

```text
scripts/run.py                         linear source→evaluation runner
scripts/run_full_dataset.py            frozen full-bank construction procedure
scripts/curate_item_packaging.py       preregistered answer-package correction
scripts/finalize_full_dataset.py       fixed-bank simulation→KC→KT finalizer
scripts/run_phase6_selection_stability.py
scripts/analyze_full_dataset.py
src/grammar_kt/{normalise,canonicalise,generate,validate_items,fold,simulate}.py
src/grammar_kt/{kc_candidates,kc_selection,kc,kt,evaluate}.py
```

Phase-specific experiment scripts remain for exact reproducibility, but the
active method does not route through a registry, strategy framework, or generic
workflow engine.

## Language-generality boundary

Language/resource specific:

- EGP source fields and normalisation prompts/rules;
- the six English canonical dimensions and values;
- English generation/validation prompts and realisation rules;
- English grammatical-operation declarations;
- the empirical cells, items, folds, and results.

Structurally reusable over another declared schema:

- feature/pair/full-cell candidate enumeration and activation;
- support calculation and activation-equivalence filtering;
- predictive/parsimony selection and freezing;
- projection, KT interfaces, and evaluation.

The alternate `mood`/`person` contract exercises candidate construction,
selection, freezing, and projection without English feature names.  It verifies
that the algorithmic interface is schema-driven.  It does not show that the
canonical representation, operations, generated items, selected KCs, or
predictive conclusions transfer to another language.

## Main decisions and negative results

- Preserve fixed items/events across representations: this is a tested
  scientific boundary, not an experiment option.
- Prefer semantic frozen probes to mixed holdout practice.
- Protect reusable marginals; obligation selection could replace them with
  conjunctions and is rejected.
- Use observable logistic for selection; BKT overselects under its shared
  multi-KC update semantics.
- Keep λ=.0005 as the supported compromise; lower penalties add false positives
  in null worlds and higher penalties miss planted interactions.
- Retain all-supported interactions as a predictive sensitivity.  It improves
  the final compositional point/interval but costs six extra KCs; automation is
  not claimed to dominate it.
- Keep exact-all-cell as a labelled oracle extreme.  It wins only in the
  matching cell-specific simulator and transfers badly in the final mixed
  evaluation.
- Use model-selected common language.  The controlled lexicon under-covered
  the pilot and is an archived ablation.
- Keep one judge and all criteria.  No human gold supports criterion deletion
  or a judge ensemble.
- Retain N=3 plus narrow labelled fallbacks.  N=5 did not add pilot coverage;
  blind extra sampling did not solve the hardest aspect cell.

## Claim boundaries

The dataset is realistic in scale for this harness and contains inspectable,
grammar-focused learner-facing material, but it is not a validated measurement
instrument.  Item quality is model-judged; the exhaustive independent agent
audit is not expert or learner review.  Learners, mastery, learning, and errors
are simulated.  The chosen worlds omit forgetting, lexical state, strategy
mixtures, transfer between KCs, and classroom effects.  The empirical study is
English-only, the source inventory is selective, normalisation stability is
limited, the compositional regime has only five cells, and the novel-value
regime has one cell/two items.  Final evidence supports a reproducible method
that detects planted supported interactions and often defaults to marginals;
it does not establish a uniquely true grammar ontology or cognitive validity.
