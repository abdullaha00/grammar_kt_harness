# Historical medium-v1 research-question ledger

Statuses use `answered`, `partially answered`, `unanswered`, or
`rejected/superseded`.  “Answered” is always bounded by the experiment named in
the caveat; it does not imply human cognitive or cross-lingual validity.  Exact
commands, seeds, and artifacts are in `reports/experiment_log.md`.

## Programme RQs

| RQ | Status | Experiment / retained evidence | Answer | Caveat |
|---|---|---|---|---|
| RQ1. Predictive and parsimonious KC granularity | partially answered | P3 selector studies; P4 four-world audit; P5 integrated validation; P6 curated final evaluation | Protected feature marginals plus evidence-supported interactions give the retained trade-off. Exact cells are too sparse for transfer; all-supported interactions predict slightly better in the final composition regime but use 16 vs 10 KCs. | No human learner evidence and no universal winner across latent worlds. |
| RQ2. Are feature-value KCs sufficient? | partially answered | P4/P5 world×representation results | Yes in the factorized/null controls; no in the interaction-heavy world; they cannot express cell-specific structure. | These are declared simulator controls. |
| RQ3. Which interactions add value? | partially answered | P3/P5 planted controls; P6 final selection | Perfect×negative and present×negative are recovered when strongly planted; perfect×negative is selected in the final mixed world. | Natural human interaction structure is unknown; final support is two cells/four items. |
| RQ4. Can automation recover interactions? | answered for synthetic controls | P5-LAMBDA-SUPPORT; P6-SELECTION-STABILITY | At λ=.0005 and ≥240 learners it jointly recovers both eligible strong interactions in 3/3 seeds with 0/3 additions in each clean null; the final interaction is stable in 5/5 1,000-learner streams. | Does not establish recovery from real learner data. |
| RQ5. Compositional generalisation | partially answered | P4 frozen-probe repair; P5 and P6 paired results | The protocol now measures transfer without holdout practice. Automated−factorized composition effects cross zero; all-supported interactions improve the final mixed-world compositional interval. | Five cells/10 items, one unseen pair, synthetic outcomes. |
| RQ6. Robustness across latent worlds | answered within declared worlds | P4-WORLD-KT-001; P5 integrated validation | Rankings depend on the world. Factorized, interaction-heavy, and cell-specific structures favour matching representations; no universal winner. | The worlds are controls, not estimates of human cognition. |
| RQ7. Selector-model sensitivity | answered at medium scale | P3 selector audit; P4 KT audit | BKT and logistic select materially different inventories. Shared full-credit multi-KC updates make BKT overselect, so observable logistic is primary. | Other KT families are not studied. |
| RQ8. Scalable grammar folds | answered for the current inventory | P4-FOLD-001; final fold artifact | Semantic tuple/coverage rules yield an ID- and order-invariant 18/5/1 split. | Only 24 English cells; exact balance is inventory-dependent. |
| RQ9. Does simulation test composition? | answered | P4 mixed-history vs frozen-probe audit | The former mixed history did not. Development-only acquisition plus non-updating probes is now primary. | Still simulated transfer. |
| RQ10. Model-selected vs controlled lexical/context material | answered at an eight-cell pilot | P4-ITEM-AUDIT | Model-selected N=3 covered 8/8 cells versus 5/8 controlled; common-language checks passed. | No human realism study; final bank remains template-heavy. |
| RQ11. Best-of-N | answered conditionally | P4 pilot and P6-ITEM-N3/curated analysis | Final curated N=1/2/3 prefixes cover 16/19/22 cells. N=3 is retained; N=5 added no pilot coverage. | Complete coverage needs separately labelled fallbacks. |
| RQ12. Phase-2 normalisation usefulness | partially answered | P4-NORM-001 | Only 2/80 legacy Phase-2 calls resolve; explicit eligibility avoids most calls. | Fresh large repeated annotation was not run. |
| RQ13. Operation KCs | answered structurally | P2 operation audit; final operation table | Imperative, negation, inversion, and passive declarations are aliases of feature KCs on this bank; finite/perfect/progressive can be distinct; generator tags add no independent evidence. | Bank-specific activation equivalence is not linguistic equivalence. |
| RQ14. Candidate-space size | answered structurally | P2 medium structural run; final candidate inventory | Final development data produce 55 raw candidates, 38 activation classes, 42 support-eligible, and 28 selection-eligible. | Candidate size depends on schema, fold, and bank. |
| RQ15. Background/reference values | partially answered | P2 support sensitivity; active candidate design | Explicit background declarations prevent hidden conventions and candidate explosion. | Whether present/active/positive/declarative/none are cognitively “background” is assumed. |
| RQ16. Source evidence in item generation | partially answered | P4 source-evidence matched pilot | Three matched cells show no N=3 coverage benefit; opaque source IDs were removed. | Too small for a general negative claim. |
| RQ17. Eligibility and transition safety | answered structurally | P4-NORM-001 | Explicit eligible dimensions plus branch-preserving validation avoid 71/80 calls and reject six unsafe adversarial transitions. | Annotation correctness beyond structural safety remains model-dependent. |
| RQ18. Validation criteria reliability/redundancy | partially answered | P4-VALID-001; P6 qualitative/correction audit | Same-model/alternate-model acceptance agreement is .826/.792; determinacy dominates rejection; ceiling criteria cannot be justified for deletion. | No human gold; six corrected cases produced unrelated decision flips. |
| RQ19. Paired KC-policy comparison | answered methodologically | policy-statistics tests; P5/P6 5,000-repeat comparisons | Resample whole learners and compute within-learner fixed-event loss differences. | Intervals quantify synthetic learner sampling only. |
| RQ20. Structural/event support for selection | answered within controls | P5 support curve; P6 stability | Require ≥2 cells/≥3 items for pair eligibility and use ≥240 learners at current scale. Five full 1,000-learner seeds agree; one 120-learner prefix swaps interactions. | Repeated learners do not increase structural diversity. |
| RQ21. Backend reasoning effort by module | answered operationally; strict rule inconclusive | BACKEND-THINKING-001 | Use Sol/high for future normalisation and retain Sol/medium generation plus Terra/medium validation. Higher effort is not monotonically better: high and xhigh tie on normalisation quality, while medium leads validation; generation's coverage/safety evidence is mixed. | 905 fresh model calls use mutable aliases without provider seeds; challenge cohorts and research-agent reviews are not human/expert gold, and the zero-critical confirmatory gate selected no winner. |

## Full-dataset RQs

The paper-facing tables referenced below live in
`reports/phase6/artifacts/full_dataset_analysis/`; qualitative evidence is in
`reports/phase6/artifacts/qualitative_item_audit.md` and the complete narrative
is `reports/full_dataset_investigation.md`.

| RQ | Status | Evidence | Answer | Caveat |
|---|---|---|---|---|
| F1. Normalisation outcome proportions | answered | `source_normalisation.csv` | 44/139 complete (31.7%), 77 partial (55.4%), 2 unresolved (1.4%), 16 out-of-scope (11.5%). | Retained one main model run. |
| F2. Unique GrammarCells | answered | `grammar_cells.csv` | 24 exact cells emerge. | Inventory is source/sample bounded. |
| F3. Editorial compression | answered | source summary/relations | 44 contributing complete descriptors form 24 cells and 48 source→cell edges (1.83 contributors/cell). | “Compression” is structural, not information quality. |
| F4. Sparse dimensions/values | answered | `dimension_value_support.csv` | Modal identities except `would` are absent; wh-clause values are absent; `would` occurs in one cell/two items; imperative and polar-question each have two cells. | Zero support reflects this inventory. |
| F5. Dominant combinations | answered | `grammar_cells.csv` | Active/positive/declarative/modal-none dominate; their cell supports are 19/16/20/23 of 24. | Descriptive, not a target-language frequency estimate. |
| F6. Clean compositional holdouts | answered | `fold_summary.csv` | Five cells/10 items have no unseen constituent values. | One of 37 value pairs is unseen in development. |
| F7. Novel-feature holdouts | answered | `fold_summary.csv` | One `modal=would` cell/two items. | Too small for broad novel-value claims. |
| F8. Generations required | answered | `item_generation_stages.csv` | 78 attempts/77 payloads; default 72, rescue 4, explicit cue 2. | Model sampling seed unavailable. |
| F9. Realistic-scale best-of-N | partially answered | stage table plus P4 N=5 | N=3 improves coverage to 22/24; N=5 was only tested at eight-cell pilot scale. | No full-scale N=5 counterfactual. |
| F10. Acceptance rate | answered | stage table | 54/77=.701 after curation; N=3 prefix 51/71=.718. | Model judgment, not human acceptance. |
| F11. Hardest generation structures | answered descriptively | per-cell table; audit | Negative past perfect progressive and past-perfect passive required rescue/intervention; temporal contexts often underdetermined marked aspect. | Few cells per construction. |
| F12. Hardest validation structures | answered descriptively | criterion/per-cell tables | Determinacy fails 22/77; all other criteria fail at most three times. | Validator may be inconsistent at boundaries. |
| F13. Final-bank diversity | answered descriptively | `lexical_diversity.csv`; audit | 44/44 prompts unique, 242 types/795 tokens, TTR .304; median second-item token-set distance .739. | “Complete…” stems, names, predicates, and domestic contexts repeat. |
| F14. Non-target lexical/context rejection | answered by the validator | criterion table | 0/77 fail the simplicity or world-knowledge criteria. | Ceiling result may reflect judge sensitivity, not true absence. |
| F15. Raw KC space | answered | candidate-family table | 55: 9 features, 10 operations, 18 pairs, 18 development cells. | Development-derived only. |
| F16. Structural reduction | answered | candidate inventory/table | 55 raw →38 activation classes; 42 support-eligible and 28 selection-eligible. | Equivalence is bank-specific. |
| F17. Nonredundant operations | answered structurally | `operation_candidates.csv` | Finite tense form, perfect dependency, and progressive dependency are eligible; four common operations alias marginals, three have no support. | Selection retained no operation. |
| F18. Selected interactions | answered | `automated_selected_kcs.csv` | Perfect×negative is the sole final addition. | It matches a declared mixed-world dependency. |
| F19. Inventory stability | answered in one world | `kc/selection_stability.json` | 5/5 1,000-learner seeds identical; reference interaction frequency 8/9 over all supports. | Not generation/model/human stability. |
| F20. KC count vs extremes | answered | `policy_granularity.csv` | Factorized 9, automated 10, all-supported 16, exact-all-cell 24. | Counts alone do not establish cognition. |
| F21. Final support distribution | answered | policy/candidate tables | Automated selected item supports range 3--22, median 8; interaction support is four items/two cells. | Item variants share structure and are not independent cells. |
| F22. Prediction/parsimony trade-off | answered within final world | KT and paired tables | Automated gives a small overall logistic gain with one extra KC; all-supported has the best point log loss with six extra KCs; exact-cell is worse. | One main mixed stream; no human data. |
| F23. Compositional transfer | answered but inconclusive for automation | `paired_logistic.csv` | Automated−factorized −.000234 [−.000836,.000375]; all-supported −.001168 [−.002042,−.000246]. | Five cells/10 items and synthetic outcomes. |
| F24. World robustness | partially answered | Phase-4 four-world artifacts | No universal winner; matching structural assumptions drive gains. | Final large run is mixed-world only. |
| F25. Required learners/opportunities | partially answered | Phase-5 support curve; final stability | 240 is the smallest tested level with 3/3 strong recovery and both clean nulls; 1,000 is 5/5 stable final. | World/bank-specific, no power law estimate. |
| F26. Cost-dominant stages | answered partially | `call_times.csv` | Generation and validation sum to 784.2s and 626.3s of recorded per-call work; deterministic downstream stages need no LM. | Concurrent sums are not wall time; provider price unavailable. |
| F27. Realistic-scale failures | answered | qualitative audit; F36 | Zero-coverage marked aspect, slot packaging defects, validator flips, template repetition, and low novel-value coverage appear. | Agent audit is not expert review. |
| F28. Plausible learner material | partially answered | all-item audit/examples | No selected target is clearly ungrammatical/wrong-cell, but nine are judgment-sensitive and contexts remain worksheet-like. | No human acceptability/pedagogy study. |
| F29. English vs generic dependence | partially answered | language audit/toy-schema test | Candidate/support/selection/projection code is schema-driven; sources, schema, operations, prompts, and empirical conclusions are English-specific. | No second-language experiment. |
| F30. Mapping/item stability across model runs | partially answered | exact legacy replay; validation repeat audit | Legacy mapping feature inventory/source membership reproduces exactly; item validator agreement is moderate/substantial. | Normalisation and generation were not repeated comprehensively across models. |
| F31. Rejection-stage distribution | answered | `rejection_stages.csv` | 54 accepted, 21 model-judgment rejections, two deterministic precheck rejections. | Counts use curated override judgments. |
| F32. Surface vs contextual diversity | answered descriptively | lexical table/audit | Surface strings are unique and lexically varied, while exercise stems and scenarios repeat substantially. | No embedding/human diversity gold. |
| F33. Does unchanged extra sampling rescue coverage? | answered negatively/partially | P6-ITEM-RESCUE | Only 1/4 rescue candidates is accepted; the hardest cell remains 0/5 before intervention. | Two cells only. |
| F34. Do second variants change structural KC support? | answered structurally | `one_vs_two_variant_sensitivity.csv` | Selection eligibility rises 23→28 and eligible pairs 2→7 with up to two variants. | Learner selection is not rerun; variants are not new cells. |
| F35. Does an explicit construction cue repair persistent determinacy? | answered for one cell | P6-ITEM-DETERMINACY + curated revalidation | Corrected active evidence accepts 2/2 intervention candidates and covers the final cell. | One marked cell; cue reduces communicative naturalness. |
| F36. Can frozen packaging correction repair audited defects safely? | answered | P6-ITEM-CURATION | Six preregistered edits preserve raw hashes and yield a 44-item/24-cell bank; three acceptance decisions change. | Reveals, rather than resolves, validator instability. |

## Superseded questions/methods

- The original “does mixed history test compositional transfer?” formulation is
  answered negatively and superseded by the frozen-probe estimand.
- Obligation-based KC selection is rejected as the main method because
  conjunctions could replace reusable marginals without learner evidence.
- A universal-best-representation hypothesis is rejected by the four-world
  results.
- A strong automated compositional-gain claim remains unsupported and is not
  made in the paper.
