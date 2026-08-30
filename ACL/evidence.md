# ACL manuscript evidence ledger — full-v1

This ledger maps the manuscript's central claims to retained full-v1 evidence.
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

## Explicitly unavailable evidence

- Human expert adjudication of normalisation or items.
- Real learner responses, classroom efficacy, or human simulator parameters.
- Empirical validation in another language.
- Grammar-cell/world uncertainty represented by learner bootstrap intervals.
- Provider-pinned model snapshots or sampling seeds.
- Human sample-size thresholds inferred from synthetic collection controls.
