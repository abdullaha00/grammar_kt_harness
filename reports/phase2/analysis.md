# Phase 2 — development-only KC candidate generation

Date: 2026-08-27  
Experiment: `P2-CANDIDATES-001`

## Claim boundary

This phase constructs and audits the structural hypothesis space. It uses no
learner event, correctness value, simulated mastery, KT prediction, or final
evaluation metric. The active function receives only the canonical schema,
already-partitioned development GrammarCells, fixed development item identifiers
and cell identifiers, and the researcher-facing candidate design.

The four-cell fixture is software-contract evidence only. The 24-cell legacy
artifact is used only as a structural measurement-opportunity inventory; its
learner outcomes, KCs, simulation, and predictive results are not imported.

## Hypotheses

- **H2.1 / RQ14:** schema-derived enumeration plus support/equivalence marking
  will be more principled than fixture-specific declarations while remaining
  manageable at the 16-cell development scale.
- **H2.2 / RQ13:** many GrammarCell-deterministic operation KCs will be aliases
  of canonical feature KCs; only some cross-value dependency operations will
  add distinct activation.
- **H2.3 / RQ15:** background/reference values should be explicit scientific
  declarations rather than Python conventions.
- **H2.4 / RQ20:** one item per fixture cell cannot support reusable
  interactions; cell support must be distinguished from repeated-item support.
- **Negative control:** changing every holdout feature and source identifier
  must leave the development-derived inventory unchanged.

## Active implementation

The active declaration is `modules/kcs/candidate_design.yaml`; English-specific
cell-deterministic operation rules are in
`modules/grammar/canonical/english_operations.yaml`. Generic construction is
the direct function `make_kc_candidates(...)` in
`src/grammar_kt/kc_candidates.py`.

The stage performs, in order:

1. enumerate observed, schema-valid, non-background feature values;
2. compile declared cell-deterministic operations;
3. enumerate cross-dimension feature pairs that actually co-occur;
4. create exact candidates for development cells only;
5. attach supporting development cell/item IDs and binary item activations;
6. mark support eligibility;
7. mark development-bank activation-equivalence classes and deterministic
   representatives.

All candidates remain inspectable. Low- and zero-support candidates are marked,
not silently discarded. Pairwise hypotheses require at least two supporting
cells and three structural items in the active Phase 2 design. Feature-value
candidates are preferred as representatives, followed by operations,
interactions, and exact cells.

`scripts/run.py` now executes this stage after development partitioning and
writes `kc/candidate_inventory.json`. It still uses the predefined factorized
policy downstream; Phase 3 replaces that provisional choice with evidence-based
selection.

## Fixture contract run

The four development cells and four accepted fixture items produced:

| Family | Raw candidates |
|---|---:|
| Feature values | 5 |
| Operations | 10 |
| Supported pairwise co-occurrences | 3 |
| Development full cells | 4 |
| **Total** | **22** |

There were eight distinct activation vectors and 14 duplicate candidates.
Thirteen candidates had item support, but only seven were both supported and
equivalence representatives. Every pair occurred on one cell/one item, so none
met the active 2-cell/3-item interaction threshold. This supports H2.4 only as
a measurement limitation: it is not evidence that the interactions are
cognitively absent.

The complete inspectable inventory is
`reports/phase2/artifacts/fixture_candidate_inventory.json`.

## Legacy structural compatibility

Input SHA-256:
`5635b69de038fa3d0532265c78695b8c7360d92a84df932791ab7446b3e9768e`.

The artifact contains 42 measurement opportunities over 24 exact cells:

| Grammar split | Opportunities | Cells |
|---|---:|---:|
| Development | 30 | 16 |
| Compositional holdout | 11 | 7 |
| Novel-feature holdout | 1 | 1 |

All feature tuples satisfy the current canonical schema and constraints; each
canonical ID maps to one tuple. Development extraction uses only
`canonical_split == "development"`. All compositional values are observed in
development, and the sole novel value is `modal=would`; neither fact was used
for development candidate construction. The 30 item-support units are
preselected structural opportunities, not accepted learner items, and this
limits the support interpretation.

Compatibility evidence is retained in
`reports/phase2/artifacts/legacy_compatibility.json`.

## Medium structural candidate space

The active design yielded:

| Family | Raw | Meets support | Selection-eligible after equivalence |
|---|---:|---:|---:|
| Feature values | 9 | 9 | 9 |
| Operations | 10 | 7 | 3 |
| Pairwise interactions | 13 | 6 | 6 |
| Development full cells | 16 | 16 | 8 |
| **Total** | **48** | **38** | **26** |

The 48 hypotheses occupy 33 development-item activation classes, leaving 15
duplicate excess candidates. Thus H2.1 is supported at this scale: automatic
enumeration is broader than the fixture declarations but remains inspectable
after support/equivalence analysis.

The six active-threshold interactions are:

- `aspect=perfect × polarity=negative`;
- `aspect=perfect × tense=past`;
- `aspect=perfect × tense=present`;
- `aspect=progressive × tense=present`;
- `polarity=negative × tense=past`;
- `polarity=negative × tense=present`.

Eligibility is structural, not evidence that any interaction improves learner
prediction. The complete inventory is
`reports/phase2/artifacts/legacy_development_candidate_inventory.json`.

## Support sensitivity (RQ20 structural portion)

With cell support fixed at one, minimum item support 1/2/3/5 retained
13/11/6/1 interactions. With item support fixed at one, minimum cell support
1/2/3/5 retained 13/6/1/0. Repeated opportunities therefore inflate item
support: an item-only threshold of two retains interactions observed in just
one GrammarCell. Requiring two cells is the important reusability guard; the
active three-item threshold adds a minimal amount of measurement evidence.

The threshold is provisional because the legacy design deliberately supplies
only one or two opportunities per cell. Learner-event support and selection
stability remain Phase 3/5 questions. Full sensitivity is retained in
`reports/phase2/artifacts/support_sensitivity.json`.

## Background/reference values (RQ15)

The active background declaration treats `tense=NA`, `aspect=none`,
`voice=active`, `polarity=positive`, `clause=declarative`, and `modal=none` as
reference conditions. Present and past remain explicit finite-morphology
hypotheses.

At legacy-development scale:

| Design | Feature | Pair | Raw total | Distinct vectors | Duplicate excess | Eligible |
|---|---:|---:|---:|---:|---:|---:|
| Active | 9 | 13 | 48 | 33 | 15 | 26 |
| Present also reference | 8 | 7 | 41 | 29 | 12 | 24 |
| Every observed value explicit | 15 | 66 | 107 | 54 | 53 | 47 |

Making constant `modal=none` explicit alone expands the raw pair space from 13
to 22 and creates additional aliases. Promoting the other frequent reference
values similarly expands the space without outcome-free evidence of cognitive
benefit. The active declaration is therefore a parsimonious, interpretable
starting hypothesis, not an empirical claim that reference values require no
knowledge. Present remains explicit because it is a realised finite
morphological alternative to past; treating it as reference remains a Phase 3
ablation. RQ15 is only partially answered.

Full interventions and supports are retained in
`reports/phase2/artifacts/background_sensitivity.json`.

## Operation audit (RQ13)

Only operations derivable from the cell are declared. Agreement, DO-support,
emphatic DO, and LET-imperative are excluded because their activation depends
on realisation information absent from the canonical cell.

Legacy development gives the following result:

- `negation`, `passive_dependency`, `imperative`, and
  `operator_inversion` are activation aliases of feature-value candidates;
- `perfect_dependency` and `progressive_dependency` combine two aspect values
  and add distinct reusable columns;
- `finite_tense_form` adds a broad distinct column over morphological
  present/past cells;
- `central_modal`, `subject_wh`, and `wh_fronting` have zero development
  support and are selection-ineligible.

The fixture's four development items agree 4/4 with the declared deterministic
tags, but responses are canned. Legacy expected-operation tags agree 30/30,
but those tags were generated by the same deterministic rules and are not
independent validation. The older post-training study separately showed that
blind operation reconstruction became feasible after its ontology repair; it
does not validate the active generator's self-tags. Generator `operation_tags`
therefore do not activate Phase 2 candidates.

RQ13 is answered for the current development banks: some dependency operations
are structurally nonredundant, while direct one-value operations are aliases and
realisation-dependent operations require independent item analysis. Evidence is
retained in `reports/phase2/artifacts/operation_audit.json`.

## Leakage negative control

Every holdout feature and source ID in the fixture was replaced with
`UNREAD_HOLDOUT`/`mutated_holdout` after preserving only fold IDs for the
partition. Candidate SHA-256 remained
`486614ecc9a1e3f8e044946923ffefe4e896ad6eecfd6d93df9227c9d80aafa3`
before and after. The active API has no fold, event, outcome, KT, or evaluation
parameter; it reads only `item_id`/`cell_id` from development items.

## Decisions

1. Retain schema-observed feature-value enumeration with explicit background
   values.
2. Retain English cell-deterministic operation declarations, but prefer feature
   representatives for equivalent columns and never use generator self-tags.
3. Generate only cross-dimension feature-feature pairs with actual development
   co-occurrence; do not expand operation interactions.
4. Retain the 2-cell/3-item interaction threshold for Phase 3, with sensitivity
   required later.
5. Retain exact development-cell candidates as the fine-grained extreme; do not
   invent exact holdout KCs.
6. Mark measurement-bank equivalence rather than claim universal linguistic
   equivalence.
7. Carry all supported evidence forward, while the automated selector may use
   only `selection_eligible` hypotheses.

## RQ answers

- **RQ13 — answered for current English structural evidence.** Direct
  feature-corresponding operations are redundant; perfect/progressive
  dependencies and finite-tense form are distinct; realisation-dependent
  operations remain excluded.
- **RQ14 — answered at 16-cell/30-opportunity scale.** The active inventory is
  48 raw hypotheses, 33 activation classes, and 26 support/equivalence-eligible
  candidates.
- **RQ15 — partially answered.** Explicit reference declarations sharply reduce
  aliases/candidate growth. Their cognitive status and present/reference choice
  still require learner evidence.
- **RQ20 — partially answered structurally.** At least two supporting cells are
  needed to avoid repeated-item inflation; stable learner-event support remains
  unresolved.

## Reproduction and verification

Exact experiment command:

```bash
.venv/bin/python scripts/run_candidate_analysis.py
```

No live model was called; fixture model responses were used only for the
four-cell contract. No random seed applies to structural enumeration.

Verification:

```bash
.venv/bin/python -m pytest -q
# 34 passed in 2.79s
```

The notebook executes the active candidate function with `LIVE_MODE = False`.
`git diff --check` reports only pre-existing trailing spaces in the user's
modified `pipeline.txt`; the Phase 2 paths pass targeted whitespace checking.

## Limitations and next step

The medium input is a structurally selected legacy opportunity bank rather than
accepted items, and it contains at most two opportunities per cell. Activation
equivalence is therefore conditional on this measurement bank. No learner
outcome supports any KC ranking yet.

Phase 3 should use fixed development learner evidence to compare a factorized
starting representation with eligible interactions under a simple validation
loss plus KC-count penalty, retain a trace, and freeze the selected policy
before holdout evaluation.
