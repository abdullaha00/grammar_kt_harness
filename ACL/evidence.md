# ACL manuscript evidence ledger

This ledger maps every central manuscript statement to retained evidence.  A
fixture or software-contract run is never promoted to scientific evidence.

| ID | Manuscript statement | Retained evidence | Claim boundary |
|---|---|---|---|
| E01 | The active order is source → normalization → cells → generation/validation → fixed bank → fold/evidence → candidates → selection → frozen policy/Q → KT. | `scripts/run.py`; `reports/research_state.md`; active modules under `src/grammar_kt/` | Implementation and tests |
| E02 | 139 descriptors yield 44 complete, 77 partial, 16 out-of-scope, and 2 unresolved mappings; 48 edges yield 24 cells. | `reports/phase6/artifacts/full_dataset_analysis/source_normalisation.csv`; dataset source/normalization/canonical trees | Retained model annotation; no expert gold |
| E03 | Explicit Phase-2 eligibility would route 9 rather than 80 partial rows, while 6 adversarial unsafe transitions fail. | `reports/phase4/artifacts/normalisation/`; `reports/phase4/analysis.md` | Structural safety/yield, not mapping correctness |
| E04 | Before curation, default N=1/2/3 covered 18/21/22 cells. After frozen correction/rejudgment, those prefixes contain 16/33/51 accepts and cover 16/19/22; rescue accepts 1/4 and explicit-cue accepts 2/2 to complete coverage. | `reports/phase6/artifacts/full_dataset_analysis/item_generation_stages.csv`; item plans/evidence; superseded pre-curation analysis | Initial and curated values are explicitly distinct |
| E05 | Final construction has 78 attempts, 77 payloads/judgments, 54 model accepts, and 44 selected items covering 24 cells. | Same item-stage table; `data/grammar_kt_medium_v1/items/` | Model-validity only |
| E06 | Determinacy fails 22/77 and dominates curated rejection; naturalness and pedagogy fail 2 and 3. | `criterion_failures.csv`; retained judgments | Criterion participation, not causal error attribution |
| E07 | Model-selected N=3 covers 8/8 pilot cells versus 5/8 controlled; N=5 adds no model-selected coverage. | `reports/phase4/artifacts/item_audit/live_pilot/`; Phase-4 report | Eight-cell pilot |
| E08 | Same-model/alternate-model acceptance agreement is 19/23 and 19/24, kappa .652/.583. | `reports/phase4/artifacts/validation_reliability/` | No human gold |
| E09 | The semantic fold gives 18/5/1 cells and final-bank 32/10/2 items; compositional cells have no unseen values and 36/37 seen pairs. | `fold_summary.csv`; dataset fold | Constituent-compositional, not all-pairs-seen |
| E10 | Final candidate space is 55 raw, 38 activation classes, 42 support-eligible, and 28 selection-eligible. | `kc_candidate_families.csv`; candidate inventory | Development grammar/items only |
| E11 | Direct operations mostly alias features; finite/perfect/progressive dependencies are distinct. | `operation_candidates.csv`; Phase-2 operation audit | Bank-specific activation equivalence |
| E12 | One versus up-to-two variants leaves 2 versus 7 eligible interactions. | `one_vs_two_variant_sensitivity.csv` | Structural-only; selector not rerun |
| E13 | Selector objective is dev-validation log loss + `.0005 × #KCs`, with protected features, forward addition, and backward prune. | `src/grammar_kt/kc_selection.py`; `modules/kcs/selection.yaml`; Phase-3 report | Declared operating point |
| E14 | At 240 learners, `.0005` has 0/3 factorized-null additions and 3/3 joint planted recovery; adjacent penalties trade false positives/negatives. | `reports/phase5/artifacts/integrated_validation_v1/` | Controlled synthetic worlds |
| E15 | Four-world automated-minus-factorized mean log-loss deltas are 0, −.002256, 0, +.000016. | Phase-5 `results.json` and report | Fixed structural bank, three seeds |
| E16 | The final policy has 9 features + perfect×negative; factorized/all-supported/automated/oracle contain 9/16/10/24 KCs. | `automated_selected_kcs.csv`; `policy_granularity.csv`; frozen policies | One final mixed stream |
| E17 | Final logistic all-probe losses are .643731/.643334/.643356/.657507 for factorized/all-supported/automated/oracle. | `kt_metrics.csv`; policy evaluation JSON | Identical 44,000 probes |
| E18 | Automated–factorized all-probe delta is −.000375 [−.000631,−.000109]; compositional −.000234 [−.000836,.000375]; novel +.000119 [−.000099,.000352]. | `paired_logistic.csv`; `paired_logistic.json` | 5,000 whole-learner bootstrap; only all-probe CI excludes zero |
| E19 | All-supported–factorized deltas are −.000397 [−.000782,−.000026] overall and −.001168 [−.002042,−.000246] compositional. | Same paired artifacts | One mixed-world seed; policy not selected by penalized objective |
| E20 | Final dataset has 1,000 learners and 204,000 events; selection receives 160,000 development events. | `finalization_manifest.json`; analysis summary | Synthetic learners |
| E21 | At 1,000 learners, all five mixed-world seeds select the identical ten KCs; nested 60/240/500/1,000 samples match, while 120 learners substitutes one interaction (Jaccard .818). | `reports/phase6/artifacts/selection_stability_v1/results.json` | Synthetic-world selection stability, not response-metric or human-population stability |
| E22 | An alternate mood/person toy schema passes candidate generation, selection, and projection. | KC candidate/selection tests; Phase-2/4 reports | Interface contract, not cross-lingual validity |
| E23 | An exhaustive agent audit found five selected packaging/reference defects and one likely rejected judge error; six frozen corrections were independently rejudged, changing 55/45 accepts/selected to 54/44 while retaining 24-cell coverage. | `reports/phase6/artifacts/qualitative_item_audit.md`; `items/packaging_correction_manifest.json` | Agent audit and model rejudgment, not human expert validation |

## Deferred or unavailable evidence

- Human expert annotation of normalization and generated items.
- Human learner response data or classroom efficacy.
- Empirical evaluation in another language.
- Full-bank repeated normalization, generation, and validator-model stability.
- Provider monetary price and pinned model snapshots.
