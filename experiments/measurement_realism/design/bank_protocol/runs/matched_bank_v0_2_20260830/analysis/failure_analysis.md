# Matched-format bank v0: deterministic negative-result audit

## Result

The preregistered v0 construction **did not freeze**: 5/38 whole semantic families (20/152 item slots) passed all gates. The remaining 33 families exhausted three no-feedback generation rounds. This is a successful execution with a negative construction result, not a technical failure.

No realism score is computed. Linguistic, solver, measurement, product, coverage, and Q-geometry evidence remain separate.

## Run integrity and preflights

The scientific run retained 178 complete audited calls, 106 generated candidates, 712 solver attempts, and 90 family-role critic records, with zero technical failures.

Two earlier preflights are excluded from scientific counts:

- `matched_bank_v0_20260830`: three byte-identical calls were rejected by the provider because a dynamic `const` property lacked an explicit JSON-schema `type`; no inference output or scientific judgment exists.
- `matched_bank_v0_1_20260830`: one complete generation exposed an orchestrator reconstruction bug: a visible `Speaker:` label was treated as part of the target utterance. It stopped before solvers/critics. The v0_2 prompt and gate explicitly froze the speaker-label exclusion.

## Candidate pass funnel

| Round | Evaluated | Deterministic | Solver-family | All critics | Accepted |
|---:|---:|---:|---:|---:|---:|
| 1 | 38 | 31 | 12 | 3 | 3 |
| 2 | 35 | 32 | 12 | 2 | 2 |
| 3 | 33 | 26 | 6 | 0 | 0 |
| **All** | **106** | **89** | **30** | **5** | **5** |

A family reaches critics only after every one of its four items passes the deterministic and two-replicate solver gates. Formats were never cherry-picked across rounds.

## Solver evidence by format

| Format | Items attempted | Item gate pass | No keyed match | Major ambiguity | Task/UI unclear | Reasonable unkeyed pending |
|---|---:|---:|---:|---:|---:|---:|
| constrained_cloze | 89 | 66 | 11 | 18 | 2 | 30 |
| dialogue_completion | 89 | 38 | 50 | 14 | 0 | 59 |
| multiple_choice | 89 | 84 | 0 | 5 | 0 | 11 |
| sentence_transformation | 89 | 81 | 8 | 0 | 0 | 6 |

Across 712 attempts, 562 matched a keyed answer, 51 flagged major ambiguity, and 176 proposed at least one reasonable unkeyed response. These are automated stress tests, not learner success rates.

## Independent critic evidence

| Role | Families judged | Overall accept | Overall reject | Any major concern | Any blocking judgment |
|---|---:|---:|---:|---:|---:|
| linguistic | 30 | 29 | 1 | 1 | 1 |
| measurement | 30 | 9 | 21 | 21 | 21 |
| platform_product | 30 | 24 | 6 | 6 | 0 |

Role decisions were unanimous accepts for 7/30 critic-reached candidates, unanimous rejects for 0/30, and mixed for 23/30. Disagreements and criterion evidence are retained by exact candidate/item ID in the JSON.
Of the 7 unanimous overall accepts, 2 still failed the preregistered critic gate because a must-pass criterion was rated `minor_concern` rather than `pass`; overall labels never overrode criterion gates.

The most frequent non-pass criterion/format records were:

| Role | Scope | Criterion | Format | Minor | Major | Concern candidates |
|---|---|---|---|---:|---:|---:|
| measurement | family | construct_equivalence_across_formats | all formats | 4 | 18 | 22 |
| measurement | item | accepted_response_coverage | dialogue_completion | 2 | 16 | 18 |
| measurement | item | answer_determinacy | dialogue_completion | 4 | 12 | 16 |
| measurement | item | accepted_response_coverage | sentence_transformation | 6 | 9 | 15 |
| measurement | item | accepted_response_coverage | constrained_cloze | 3 | 9 | 12 |
| measurement | family | no_format_specific_kc_redefinition | all formats | 2 | 9 | 11 |
| measurement | item | answer_determinacy | constrained_cloze | 2 | 7 | 9 |
| measurement | item | no_target_avoiding_shortcut | dialogue_completion | 1 | 7 | 8 |
| platform_product | family | non_repetitive_learner_experience | all formats | 25 | 5 | 30 |
| measurement | item | no_target_avoiding_shortcut | constrained_cloze | 0 | 4 | 4 |
| measurement | item | no_target_avoiding_shortcut | multiple_choice | 22 | 3 | 25 |
| measurement | item | no_target_avoiding_shortcut | sentence_transformation | 3 | 3 | 6 |
| measurement | item | active_kc_evidence | dialogue_completion | 0 | 3 | 3 |
| measurement | item | answer_determinacy | multiple_choice | 0 | 3 | 3 |
| measurement | item | answer_determinacy | sentence_transformation | 7 | 2 | 9 |

## Accepted coverage and Q geometry

The five passing families cover 4/20 selected cells, 3/18 seen cells, and 6/18 generator KCs. Only 1/18 seen cells has both required semantic variants. The accepted seen Q rows have exact rank 3, not 18; adding the accepted unseen-combination probe raises all-regime rank to 4.

| Family | Round | Regime | Cell | KCs | Target |
|---|---:|---|---|---|---|
| `mb0_8f8fa56e7109_seen_gc_90b9229122fa55d6_sv01` | 1 | seen | `gc_90b9229122fa55d6` | gkc_modal_might | The delivery might arrive this afternoon. |
| `mb0_8f8fa56e7109_seen_gc_90b9229122fa55d6_sv02` | 1 | seen | `gc_90b9229122fa55d6` | gkc_modal_might | I might miss the train this morning. |
| `mb0_8f8fa56e7109_seen_gc_44ff4acdb263024b_sv01` | 1 | seen | `gc_44ff4acdb263024b` | gkc_aspect_progressive, gkc_finite_past | At 8:00 yesterday, Maya was carrying the boxes. |
| `mb0_8f8fa56e7109_seen_gc_4634bf1b005f7724_sv01` | 2 | seen | `gc_4634bf1b005f7724` | gkc_finite_present, gkc_negation, gkc_non_subject_wh_question | Which ingredient does the soup not contain? |
| `mb0_8f8fa56e7109_ucomb_gc_e730dbce7b036961_sv01` | 2 | unseen_combination | `gc_e730dbce7b036961` | gkc_aspect_progressive, gkc_finite_present | Maya is carrying the boxes into the office. |

The full JSON includes every cell and KC funnel, all accepted learner-facing item IDs/examples, every solver-failure item ID, deterministic examples, critic disagreements, and criterion-level evidence. Counts that activate multiple KCs are deliberately non-exclusive.

## Why the release gate failed

- `all_preregistered_families_pass`: 5/38.
- `exact_152_item_complete_crossing`: 20/152 accepted slots.
- `both_seen_variants_for_every_seen_cell`: 1/18 cells.
- `every_selected_cell_covered`: 4/20 cells.
- `seen_q_basis_retains_rank_18`: rank 3/18.
- `both_held_out_probe_regimes_covered`: unseen_combination.

Consequently, no `bank/` release was frozen. Treating the 20 accepted slots as a partial release would violate the preregistered family, coverage, held-out, and full-rank design.

## Smallest defensible successor method

Create a separately versioned declared-correction layer for the 33 exhausted whole families. Link every edit to its raw candidate and an explicit failure; prohibit silent repair and cross-round format cherry-picking; then rerun deterministic reconstruction, both solver replicates, and all three role critics. Do not spend another blind no-feedback generation round under the exhausted v0 protocol.

Before calling a successor bank deployable or platform-validated, render the learner interaction and obtain independent language-teacher/measurement and product review, followed by a small learner answerability pilot. Automated passing is stress-test evidence only.

A corrected fully crossed bank may be used as a **controlled measurement scenario** for planted format/item-effect experiments once all structural and automated gates replay. That is distinct from **release validity**: human/expert rendered-item review and a learner answerability pilot remain necessary before platform-deployability claims.

## Reproduction

```bash
.venv/bin/python scripts/experiments/analyze_measurement_realism_bank_failure.py analyze
.venv/bin/python scripts/experiments/analyze_measurement_realism_bank_failure.py verify
```
