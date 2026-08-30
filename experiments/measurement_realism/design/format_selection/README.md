# Outcome-free GrammarCell selection for the matched-format study

Status: **selected and replayable**  
Frozen input: `data/grammar_kt_full_v1/`  
Selection scope: seen/acquisition-eligible GrammarCells only  
Learner outcomes or oracle trajectories read: **no**

## Decision

Use the 18-cell `full_rank_18` cohort for the matched-format measurement
study. It is the smallest possible cohort whose distinct cell-level Q rows can
have rank 18, and its exact rank is 18. Its determinant is -1, so the selected
integer matrix is an exact unimodular basis rather than a floating-point rank
accident.

Use the nested 12-cell `coverage_pilot_12` cohort only to test generation,
parsing, independent validation, and UI-schema feasibility. It is the exact
minimum number of seen cells that can activate all 18 KCs, but its rank is only
12 and four KC-column pairs are activation-equivalent. Marginal KC coverage is
therefore not sufficient for an inferential matched-format study.

The canonical bank input is `selected_cells.json`. It contains the 18 seen
acquisition cells plus one `unseen_combination` and one `unseen_value` probe.
Both probes have `acquisition_updates=false` and are excluded from every seen-Q
rank, determinant, acquisition, and support claim.

The selection is an instrument-design decision, not a claim that these 18
cells are representative of all 75 canonical cells or that full rank proves
psychological separability.

## Evidence boundary

The selector reads only:

- frozen GrammarCells and grammar-regime assignments;
- frozen K* and deterministic Q*;
- frozen learner-facing item records; and
- the explicit, outcome-free full-v1 item audit.

It does not open interactions, private learner truth, response probabilities,
or downstream experiment results. The item audit consists of structured Codex
rubric judgments, not learner, teacher, product, or expert validation. A
representative item is a starting stem for matched-format construction, not an
automatically approved successor item.

CEFR/intended-proficiency is not present in the frozen item schema, so it was
not manufactured for selection. EGP source-record support is retained
explicitly.

## Deterministic rule

The selection has three blocks.

1. Each of the nine mutually exclusive modal KCs receives one seen cell. The
   deterministic priority is: audited usable representative; a Q-isolating
   modal anchor when one exists; greatest source support; narrower Q row;
   stable ID tie-break.
2. Imperative and non-subject-WH receive mandatory rare-clause rows. The
   positive imperative is chosen because it is the only Q-isolating imperative
   cell. Its frozen item is explicitly marked for redesign. The WH cell is the
   only available canonical WH cell.
3. Seven exact feature templates construct interpretable common-operation
   contrasts: past and present anchors; past-perfect; past-progressive;
   past-progressive passive; past-perfect passive negative; and
   present-perfect polar question.
4. The two probe cells are selected independently within their required
   regimes using: audited usable representative; greatest EGP source support;
   narrower Q row; representative-item quality; stable ID. They do not alter
   or optimize the acquisition basis.

The common-operation block gives transparent exact contrasts. In Q-row
notation:

```text
perfect     = past-perfect - past-anchor
progressive = past-progressive - past-anchor
passive     = past-progressive-passive - past-progressive
negation    = complex-negative - past-perfect - passive
polar       = present-perfect-polar - present-anchor - perfect
WH          = WH-row - present-anchor - negation
```

Once those common operations are resolved, each selected modal row supplies
its unique modal pivot. `identification_contrasts.json` contains an exact
machine-checked unit-vector reconstruction for every KC.

## Full 18-cell cohort

All 18 cells are `seen`. “Usable” below reproduces the outcome-free audit
disposition for the chosen frozen reference item.

| Role | Cell ID | Active KCs | Reference item ID | Frozen stem status |
|---|---|---|---|---|
| CAN crossing | `gc_edcc8d38860ff41d` | CAN + polar | `candidate_gc_edcc8d38860ff41d_02` | usable |
| COULD crossing | `gc_9b8833161ce61d83` | perfect + COULD | `unchanged_rescue_gc_9b8833161ce61d83_01` | usable |
| MAY crossing | `gc_325e05b06bb38886` | MAY + polar | `candidate_gc_325e05b06bb38886_01` | usable |
| MIGHT anchor | `gc_90b9229122fa55d6` | MIGHT | `candidate_gc_90b9229122fa55d6_01` | usable |
| MUST crossing | `gc_4a4c9d34c1b5bce4` | perfect + MUST | `unchanged_rescue_gc_4a4c9d34c1b5bce4_02` | usable |
| SHALL crossing | `gc_f86ecd83135f0b52` | SHALL + polar | `candidate_gc_f86ecd83135f0b52_02` | usable |
| SHOULD anchor | `gc_809d40d141731b61` | SHOULD | `candidate_gc_809d40d141731b61_02` | usable |
| WILL anchor | `gc_16d9f6e33f0517ec` | WILL | `unchanged_rescue_gc_16d9f6e33f0517ec_01` | usable |
| WOULD crossing | `gc_e7fef77abc10b5ba` | perfect + WOULD + negation | `candidate_gc_e7fef77abc10b5ba_01` | usable |
| Imperative anchor | `gc_bb4f472f992ab76b` | imperative | `cue_bounded_imperative_gc_bb4f472f992ab76b_02` | artificial; redesign required |
| WH rare cell | `gc_4634bf1b005f7724` | present + negation + non-subject-WH | `candidate_gc_4634bf1b005f7724_03` | usable |
| Past anchor | `gc_4601bed02c004e37` | finite past | `candidate_gc_4601bed02c004e37_01` | usable |
| Present anchor | `gc_d15de8b5658bd6a5` | finite present | `candidate_gc_d15de8b5658bd6a5_01` | usable |
| Perfect contrast | `gc_2d6eb4f93cba4c6b` | perfect + past | `candidate_gc_2d6eb4f93cba4c6b_03` | usable |
| Progressive contrast | `gc_44ff4acdb263024b` | progressive + past | `candidate_gc_44ff4acdb263024b_01` | usable |
| Passive contrast / pilot compressor | `gc_fcb801c76c95c7bf` | progressive + passive + past | `candidate_gc_fcb801c76c95c7bf_03` | usable |
| Complex negative | `gc_9d70af80c0843115` | perfect + passive + past + negation | `candidate_gc_9d70af80c0843115_01` | usable |
| Polar contrast | `gc_08d90a35b669ed28` | perfect + present + polar | `candidate_gc_08d90a35b669ed28_02` | usable |

## Quantitative audit

| Diagnostic | Full tier | Pilot tier |
|---|---:|---:|
| Cells | 18 | 12 |
| Exact Q rank | 18 | 12 |
| All 18 KCs marginally covered | yes | yes |
| Exact determinant | -1 | not square |
| Q widths 1 / 2 / 3 / 4 | 6 / 7 / 4 / 1 | 4 / 5 / 3 / 0 |
| KCs with a Q-isolating selected cell | 6 | 4 |
| Equal activation-column pairs | 0 | 4 |
| Crossed / nested / disjoint KC pairs | 10 / 11 / 132 | 1 / 9 / 139 |
| Audited usable reference stems | 17 | 11 |
| Artificial reference stems requiring redesign | 1 | 1 |
| Raw 2-norm condition number | 14.756 | 2.175* |
| Column-normalised condition number | 10.929 | 1.732* |

`*` The pilot condition numbers describe its 12 non-zero singular values and
must not be mistaken for 18-column identifiability; it has four equal column
pairs and a six-dimensional null space.

The full cohort crosses every declared in-scope value available to acquisition:

- tense: NA, past, present;
- aspect: none, perfect, progressive;
- voice: active, passive;
- polarity: positive, negative;
- clause: declarative, imperative, polar question, non-subject-WH question;
- modal: none and all nine declared modal values.

The six Q-isolating cells anchor finite past, finite present, imperative,
MIGHT, SHOULD, and WILL. “Q-isolating” means only that the declared Q row has
one active column; it does not establish lexical or format purity.

### Selected-cell support by KC

| KC | Full cells | Pilot cells | Full-v1 items | Full selected anchor? |
|---|---:|---:|---:|---|
| perfect | 6 | 3 | 42 | no |
| progressive | 2 | 1 | 29 | no |
| BE-passive | 2 | 1 | 22 | no |
| finite past | 5 | 1 | 20 | yes |
| finite present | 3 | 1 | 30 | yes |
| imperative | 1 | 1 | 4 | yes |
| CAN | 1 | 1 | 7 | no |
| COULD | 1 | 1 | 5 | no |
| MAY | 1 | 1 | 8 | no |
| MIGHT | 1 | 1 | 5 | yes |
| MUST | 1 | 1 | 7 | no |
| SHALL | 1 | 1 | 4 | no |
| SHOULD | 1 | 1 | 4 | yes |
| WILL | 1 | 1 | 14 | yes |
| WOULD | 1 | 1 | 5 | no |
| negation | 3 | 2 | 49 | no |
| non-subject-WH | 1 | 1 | 2 | no |
| polar question | 4 | 3 | 12 | no |

All seven KCs with fewer than six frozen items—imperative, COULD, MIGHT,
SHALL, SHOULD, WOULD, and non-subject-WH—are retained.

## Non-updating held-out probes

| Regime | Cell ID | Features | Active KCs | Reference item | Why this probe |
|---|---|---|---|---|---|
| unseen combination | `gc_e730dbce7b036961` | present, progressive, active, positive declarative, no modal | progressive + finite present | `candidate_gc_e730dbce7b036961_01` | Audited usable; five source records; cleanly recombines two acquisition-known values in a compact Q2 cloze. |
| unseen value | `gc_483f3ac117f331a7` | past, perfect-progressive, active, positive declarative, no modal | perfect + progressive + finite past | `candidate_gc_483f3ac117f331a7_02` | Audited usable; greatest source support (two) in its regime; composes known KCs while the exact aspect value is absent from acquisition. |

These choices use no response evidence. They are illustrative regime probes,
not a claim that two cells characterize generalisation across all 23 held-out
GrammarCells. Their new matched-format items must be non-updating evaluation
opportunities under any learner simulation.

## Why the 12-cell pilot is the exact coverage minimum

Nine modal values are mutually exclusive in one GrammarCell, so covering the
nine modal KCs requires at least nine cells. Imperative and the sole
non-subject-WH activation require two different non-modal cells. None of those
eleven cells activates finite past. At least one additional cell is therefore
necessary. `gc_fcb801c76c95c7bf` supplies finite past, progressive, and passive
together, reaching all-KC coverage in 12 cells. An exact bit-mask set-cover
replay independently confirms 12 as the minimum.

This compression creates the pilot's core inferential defect:

```text
progressive column = passive column = finite-past column
finite-present column = non-subject-WH column
```

The six full-tier additions provide explicit contrasts that break every equal
column. The pilot is consequently appropriate for cheaply discovering whether
the matched-format generation and validation protocol works, but not for
format-confounding, KC-recovery, or identifiability conclusions.

## Risks and downstream requirements

1. **Imperative needs new UI-realistic measurement.** Its 50-word frozen
   annotation prompt is the one unavoidable non-usable stem. A tile reordering,
   concise contextual production, or another independently validated format
   must replace it in the new bank; raw v1 remains untouched.
2. **WH support is intrinsically narrow.** The only WH cell is present,
   negative, and non-modal. Exact algebra can subtract present and negation,
   but it cannot show transfer to positive, past, modal, or other WH contexts.
3. **Modal transfer is not tested.** One cell per modal is necessary to keep the
   study compact. Crossing each cell with multiple formats separates format
   nuisance within that cell, but it does not validate each modal KC across
   multiple grammatical contexts.
4. **Rank is not measurement validity.** The determinant certifies Q geometry,
   not learner comprehension, accepted-answer fairness, pedagogical relevance,
   or independent mastery.
5. **The cohort is design-balanced, not prevalence-weighted.** Rare modal and
   clause operations are intentionally over-represented relative to a plausible
   platform log. Later schedules must decide exposure frequencies separately.
6. **Reference prompts are not the new instrument.** Even the 17 usable stems
   must pass format-specific linguistic, measurement, learner-usability, and
   platform-plausibility validation after matched variants are constructed.

## Artifacts and replay

- `select_cells.py`: deterministic selector, frozen-input hash verification,
  exact rank/determinant/inverse, exact set-cover calculation, and artifact
  writer;
- `selected_cells.json`: canonical 20-cell bank input (18 seen acquisition +
  two non-updating held-out probes), with input hashes and full entry metadata;
- `selection_summary.json`: decision, minimality, support, geometry, and risks;
- `full_rank_cells.jsonl` / `pilot_cells.jsonl`: learner-facing reference
  records and selection rationale;
- `full_rank_q.csv` / `pilot_q.csv`: selected cell-level Q rows;
- `identification_contrasts.json`: exact KC unit-vector certificates;
- `input_manifest.json`: exact input hashes and the forbidden-input declaration;
- `output_manifest.json`: hashes of every generated selection artifact.

Replay from the repository root:

```bash
python experiments/measurement_realism/design/format_selection/select_cells.py
```

The script writes only inside this directory and never mutates full-v1.
