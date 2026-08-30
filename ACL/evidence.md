# ACL manuscript evidence ledger — full-v1 and measurement realism

This ledger maps the manuscript's central claims to retained evidence. The
immutable full-v1 benchmark is the clean known-truth reference. Measurement
realism artifacts are separate audits, failed construction evidence, or a
content-free controlled scenario; none is silently folded into full-v1.
Historical medium-v1 artifacts are pilot evidence only. A software fixture is
never promoted to a scientific result.

| ID | Manuscript statement | Retained evidence | Claim boundary |
|---|---|---|---|
| F01 | The causal order is source → GrammarCells → generator K* → items → Q* audit → simulation → frozen dataset; K-hat/Q-hat are downstream. | reports/final_methodology.md; data/grammar_kt_full_v1/manifest.json; scientific-contract tests | Implemented method boundary |
| F02 | All 1,222 EGP rows yield 211 complete, 327 partial, 9 unresolved, and 675 out-of-scope mappings; complete rows yield 228 relations and 75 cells. | data/grammar_kt_full_v1/provenance/normalisation/full_audit.json; grammar/inventory_audit.json | Automatic annotation within the declared six-dimensional scope |
| F03 | A balanced 120-row repeat gives 93.3% status, 95.8% eligibility, 38/38 jointly complete cell-set, and 79.0% partial-branch agreement. | provenance/normalisation/stability/run_summary.json | Stability, not expert correctness |
| F04 | Outcome-free K* contains 18 reusable operations; feature-only, nested-chain, and exact-cell alternatives were audited before learner outcomes. | modules/kcs/generator/; provenance/kcs/construction.json; reports/full_v1_artifacts/kc/ | Declared synthetic truth, not human ontology |
| F05 | Default N=3 yields 225 valid candidates, 102 accepts, and 57/75-cell coverage; determinacy dominates rejection. | provenance/items/generation_audit.json; validation_audit.json; immutable call evidence | Independent automatic validation |
| F06 | Separately declared rescue/intervention/correction/cue campaigns achieve 75/75 coverage; open imperative production remains a negative result. | provenance/items/campaigns/; packaging_corrections/; reports/experiment_log.md FULL-ITEM-002--004 | Interventions are not relabelled as default generation |
| F07 | The accepted pool has 126 candidates; max-two curation selects 113 unique prompts, with 37 one-item and 38 two-item cells. | provenance/items/curation.json; curation_scale_comparison.json; items/items.jsonl | Surface variants are not new grammar structures |
| F08 | The 113×18 Q* has 269 edges, density .1323, rank 18, 75 activation rows, and no identical or Jaccard≥.90 columns. | provenance/measurement/audit.json; q_matrix.csv | Bank-specific structural identifiability |
| F09 | The semantic regimes contain 54/15/6 cells and 84/20/9 items; every unseen combination is pairwise-seen/full-tuple-unseen. | grammar/regime_assignments.jsonl; provenance/grammar_regimes/audit.json | Unseen value is perfect-progressive only |
| F10 | The frozen release has 1,000 learners, 170,000 acquisition rows, 113,000 probes, and separate public/private archives that exactly replay; stored prompt/answer text is neither rendered nor scored by the simulator. | data/grammar_kt_full_v1/manifest.json; data/grammar_kt_full_v1/provenance/simulation/; data/grammar_kt_full_v1/items/items.jsonl; data/grammar_kt_full_v1/interactions.jsonl.gz; data/grammar_kt_full_v1/oracle/learner_truth.jsonl.gz | Synthetic baseline; public rows contain no oracle state or textual learner answer |
| F11 | RQ2 K* loss is .670627; all-merged, family-coarse, split-2, split-4, and exact-cell costs are +.010225, +.008132, +.003165, +.005868, and +.015039 with paired intervals above zero. | reports/full_v1_artifacts/rq2_misspecification_v1/results.json | Same frozen baseline events; learner-sampling uncertainty |
| F12 | All nine 10% Q corruptions harm prediction; mean false-positive/false-negative/mixed costs are .001685/.002644/.002294. | Same RQ2 result and preregistered projections | Three structural seeds do not establish universal ordering |
| F13 | Observable-only discovery freezes before truth/probes/oracle; 181 candidates and 22 eligible additions are evaluated. | experiments/full_v1/rq3_kc_discovery_v1/plan.json; final_selection.json | Selection reads seen item structure and acquisition outcomes only |
| F14 | The compositional ceiling recovers 18/18; the selected atomic class recovers 16/18 with Jaccard .970854 and edge F1 .965385; hash distractors recover 0/18. | rq3_kc_discovery_v1/final_evaluation.json | Ceiling is reachability evidence, not blind selection |
| F15 | Atomic and compositional hypotheses are exactly seen-Q-equivalent; atomic costs .000374 [.000228,.000517] on all probes. | Same final selection/evaluation | Unique predictive recovery is rejected |
| F16 | K* loss is .669161/.672036/.681181 on seen/combination/unseen-value; exact-cell costs are +.008209/+.037609/+.028627. | experiments/full_v1/rq4_generalisation_v1/results.json | Six unseen-value cells; learner bootstrap only |
| F17 | The 30-cell exact-item control preserves K* opportunities and yields 30,000 outcomes identical to paired baseline probes. | RQ4 item_novelty artifacts and result | Consequence of no item memory/difficulty |
| F18 | Overall prerequisite-state RMSE is .123738 K*, .146300 coarse, .132752 split-2, .140428 split-4, and .163828 exact; coarse reverses on unseen value. | reports/full_v1_artifacts/mastery_recovery_v1/results.json; paired bootstrap | Item minimum prerequisite state, not human or individual-KC mastery |
| F19 | Fixed BKT unique learner-KC RMSE is .300804 and correlation .434973 under deliberate update/aggregation mismatch. | mastery_recovery_v1/secondary_bkt_state_recovery.json | Secondary semantic-mismatch diagnostic |
| F20 | Across 13 conditions × 3 seeds × 500 learners, K* ranks first in 38/39 primary worlds; item difficulty is the sole primary reversal. | experiments/full_v1/simulator_robustness_v1/results.json; seed_comparisons.csv | Three seeds; perturbations are mostly one at a time apart from combined guess/slip |
| F21 | A mood/person toy schema executes cells → K* → Q* → simulation → observable events. | Alternate-schema scientific-contract tests | Software abstraction, not cross-lingual validity |
| F22 | Raw prediction selects K* in 21/21 nested cohorts while a fixed KC penalty selects union in 18/21; max-two adds support but no Q row/rank; A+B-only stays exactly tied through N=1,000; anchors restore rank but the planted-interaction omission costs only .000506 at balanced N=1,000. | experiments/full_v1/collection_design_v1/results.json; study_plan.json | Synthetic design evidence, not human sample thresholds; full rank is not sufficient for practically unique recovery |

## Measurement-realism evidence

| ID | Manuscript statement | Retained evidence | Claim boundary |
|---|---|---|---|
| M01 | The strict 113-item census classifies 70 usable, 15 minor repair, 15 artificial, 10 answer-space failure, and 3 rewrite/withhold. | `experiments/measurement_realism/audits/item_audit/item_level_audit.jsonl`; `summary.json` | One rubric-guided automated audit under an explicit response-slot UI assumption |
| M02 | Across two mapped audits, only 60/113 items are jointly usable; 53 lie in the union requiring action and 18 in the critical answer-space/withhold union. Role critics disagree on 56/113. | `experiments/measurement_realism/audits/platform_audit_synthesis.json`; `reports/platform_plausibility_audit.md` | Automated triage, not learner or expert deployability evidence |
| M03 | Only 16/113 items isolate one KC and six generator KCs have no isolating item. Three outcome-blind inductions share 9 signatures, have union 30 and pairwise Jaccard .400/.440/.458, and exactly match 5/4/7 K* columns. | `reports/kc_methodology_audit.md`; `experiments/measurement_realism/kc_induction_v1/results.json` | K* remains a declared synthetic coordinate system, not recovered psychological truth |
| M04 | An 18-cell seen basis is required for rank 18; the selected 18 rows have rank 18 and determinant -1, with two probe-only held-out cells. | `experiments/measurement_realism/design/format_selection/selection_summary.json`; `selected_cells.json` | Cell-Q geometry only; no prompt validity |
| M05 | The matched-bank scientific run completes 178 calls, 106 candidates, 712 solver attempts, and 90 role outputs with no technical failures, but only 5/38 families (20/152 slots) pass; seen rank is 3/18. | `experiments/measurement_realism/design/bank_protocol/runs/matched_bank_v0_2_20260830/analysis/failure_analysis.json`; `negative_result_manifest.json` | Failed preregistered release gate; isolated slots are not a partial release |
| M06 | The controlled non-release scenario contains 27 runs, 500 learners/run, and 4.59M events; 18 Q-balanced A–D analyses and 3 structured-error analyses replay with exact aligned evaluation rows. | `experiments/measurement_realism/worlds/controlled_instrument_v1/study_plan.json`; `aggregate/manifest.json`; `synthesis/manifest.json` | Content-free structural instrument; learner-facing and platform validity not assessed |
| M07 | Format DiD is -.03155149 across seeds, and strong-format C−B is -.00531682; nuisance increases the false split's relative advantage, while explicit format improves the strong control. | `worlds/controlled_instrument_v1/synthesis/results.json` | Planted format scenario; conditional learner intervals; not a real format-effect estimate |
| M08 | Item-only B−A intervals all cross zero; combined-heterogeneity C−B is inconsistent. D−C is negative because D exactly spans planted same-seen-item residuals. | Same synthesis | No general split-absorbs-difficulty or arbitrary/unseen-item remedy claim |
| M09 | Linked error histories improve mean log loss by .000867 and failed-KC top-1 from .421 to 1.000; 80%-linked top-1 is .884. Shuffled labels improve a secondary evidence-count RMSE, invalidating it as sole recovery evidence. | Same synthesis; per-run error analyses | Failed KC is post-outcome oracle attribution, not causal or human error truth |
| M10 | Curriculum and adaptive D loss exceed lab by .003420 and .003118 on average, while mixed is approximately null; interval support varies by seed. | `worlds/controlled_instrument_v1/policy_recovery_v1/results/results.json` | Post-response exploratory recovery; same-multiset schedules do not compare learning efficacy |
| M11 | In 20 matched dialogue opportunities, open dialogue gains naturalness but has 0/20 determinate, 4/20 clear-KC, 13/20 shortcut judgments, and response-family lower bound 4.55 versus cloze 17/20, 17/20, 1/20, and 1.30. | `experiments/measurement_realism/dialogue_pilot_live_v1/analysis.json`; `report.md`; `verification.json` | Automated four-family pilot, not human evidence or a universal openness ordering |
| M12 | The release decision is no new dataset release: the matched bank failed and the controlled scenario has no prompts, answers, or scorers. | `reports/measurement_extension_rq_ledger.md`; programme evidence manifest | Full-v1 remains the only frozen dataset; future human/expert validation is required |

## Explicitly unavailable evidence

- Human expert adjudication of normalisation or items.
- Real learner responses, classroom efficacy, or human simulator parameters.
- Human evidence for item comprehension, answerability, KC plausibility,
  platform deployability, format effects, or error realism.
- Empirical validation in another language.
- Grammar-cell/world uncertainty represented by learner bootstrap intervals.
- Provider-pinned model snapshots or sampling seeds.
- Human sample-size thresholds inferred from synthetic collection controls.
- A validated platform-like measurement bank or a measurement-v1 dataset.
- Fitted learner-by-KC mastery recovery for the A--D nuisance models.
