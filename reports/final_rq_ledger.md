# Final research-question ledger

Statuses are `supported`, `rejected`, or `inconclusive with reason`. Every
answer is conditional on its declared evidence source. The measurement-realism
programme does not convert automated audits, planted content-free worlds, or
synthetic error labels into human/platform evidence. Exact protocols, commands,
seeds, intervals, and hashes are in `reports/experiment_log.md`.

## Current paper-level ledger

| RQ | Status | Evidence-backed answer | Confidence and remaining caveat | Paper location |
|---|---|---|---|---|
| **RQ1 — What must be declared and audited to construct a grammar-learning measurement environment with known latent structure, and where does a clean Q-driven benchmark fall short?** | **Auditable clean construction supported; platform-valid extension rejected** | Full-v1 supplies immutable GrammarCells, K*, Q*, state, and responses. The broader audit found 60/113 items usable under both mappings, 53/113 in the action-required union, and 18/113 in the critical-answer-space/withhold union. The matched four-format bank passed only 5/38 families, so **no new dataset release** is made. | High for artifact integrity and the frozen automated negative result; inconclusive for actual learner comprehension and expert deployability because there is no human/expert gold. | Construction and Audit; Limitations |
| **RQ2 — How do KC/Q assumptions and item/format nuisance affect prediction and recovery of planted state?** | **Supported for declared controls; external format claim rejected** | The full-v1 clean-control misspecification result remains. In the content-free extension, planted format nuisance shifts the false-split-versus-shared contrast by mean DiD `-.031551`; explicit format C beats false split B in every strong-format seed (mean `-.005317`). Aligned model D recovers item nuisance planted in its seen-item residual span. | This is a controlled scenario, not validated task-format evidence. Item-only B-A is mixed/null; combined-heterogeneous C-B is mixed with every interval crossing zero; D is an exactly aligned positive control and cannot recover new-item nuisance. | Measurement Nuisance; Results; Discussion |
| **RQ3 — Which measurement contrasts, histories, and response information make structure or state distinguishable?** | **Equivalence limits supported; policy and richer-response effects bounded** | Outcome-blind KC inductions are non-unique; existing Q-equivalence results persist. Linked structured errors raise planted failed-KC top-1 from `.421` for binary evidence to `1.000` linked and `.884` at 80%, but predictive gains are small. Schedules change observable histories and exploratory fit. More open dialogue increases automated naturalness while weakening determinacy and KC attribution. | Failed KC is post-outcome attribution, policy fits are post-response exploratory, and the dialogue pilot covers four families with automated critics only. None establishes human error causality, policy value, or deployability. | Identifiability; Structured Errors; Platform Policy; Dialogue Boundary |

## Retained full-v1 ledger

| RQ | Status | Evidence-backed answer | Confidence and remaining caveat | Paper location |
|---|---|---|---|---|
| **RQ1 — Can a grammar resource be transformed into an auditable fixed language-learning dataset with explicit KCs, items, Q, and interactions?** | **Supported within declared scope** | All 1,222 EGP rows receive a disposition. The complete in-scope subset yields 75 GrammarCells, an outcome-free 18-KC K*, 113 fixed items, a deterministic full-rank 113-by-18 Q*, and 283,000 replay-verifiable events from 1,000 learners with oracle truth stored separately. | High for software/artifact integrity; moderate for automatic linguistic/item judgments; no human learner or expert-validation claim. | Methods; Dataset Construction; Limitations |
| **RQ2 — How does KT behave when the supplied KC representation differs from K*?** | **Supported for the frozen perturbations** | K* has the lowest primary all-probe log loss (.670627). Split-2, split-4, family merge, all-merge, and exact-cell cost +.003165, +.005868, +.008132, +.010225, and +.015039; every learner-paired interval excludes zero. All nine 10% Q-noise instances harm prediction. Oracle item-state recovery also favors K* overall. | High for learner sampling in the baseline stream. Representation ordering outside the compact robustness worlds remains simulator-dependent; coarse mastery recovery reverses on the six unseen-value cells. | Misspecification; Robustness; Mastery Recovery |
| **RQ3 — Can observable response evidence recover an appropriate KC representation when K*/Q* are hidden?** | **Unique recovery rejected; high-overlap equivalence-class recovery supported** | The observable-only selector reaches an atomic/compositional seen-Q equivalence class. Its atomic projection recovers 16/18 KCs exactly (activation Jaccard .970854; aligned Q-edge F1 .965385); a declared compositional ceiling is 18/18 but is not blindly selected. Hash distractors recover 0/18. | High that seen response prediction cannot distinguish exact-Q-equivalent rules in this benchmark. The result does not rule out recovery with new measurement contrasts or priors; the N=120 pilot selects coarse. | KC Discovery; Identifiability; Discussion |
| **RQ4 — How do representations generalise to seen structures, unseen combinations, and unseen values?** | **Supported for recombination; unseen-value ontology choice inconclusive** | K* log loss is .669161 seen, .672036 on 15 pairwise-seen/full-tuple-unseen cells, and .681181 on six unseen-value cells. Exact-cell costs +.008209, +.037609, and +.028627. Merges and split-2 also have supported combination costs. Atomic and compositional rules are indistinguishable on seen/combination rows. | High for the full-tuple recombination result under learner bootstrap. The six unseen-value cells all test perfect-progressive composition; atomic-vs-compositional CI crosses zero and cannot break the RQ3 equivalence class. | Linguistic Generalisation; Limitations |

## RQ1 supporting questions

| Question | Evidence | Result | Status / caveat |
|---|---|---|---|
| What is the final source scope? | FULL-LING-001 | 211 complete, 327 partial, 9 unresolved, 675 out of scope from all 1,222 rows. | Supported; bounded six-dimensional verbal-morphosyntax scope. |
| Is normalisation stable? | 120-row balanced repeat | 93.3% status, 95.8% eligibility, 100% exact cell-set agreement among 38 jointly complete rows; 79.0% partial-branch agreement. | Exact-cell stability supported; uncertain branching remains model-sensitive. |
| Why this K*? | FULL-KC-001 pilots/full audit | 18 reusable operation KCs, full rank, 75 activation rows; nested chain rejected; exact cells lack reuse. | Supported as declared generator design, never as human truth. |
| Does the bank cover grammar and K*? | FULL-ITEM-001--004; FULL-REGIME-Q-001 | 75/75 cells, 113 items, every KC measured, Q* rank 18, no equal/near-equal columns. | Supported; seven KCs are rare and one WH construction is nested. |
| How reliable is item validation? | Independent full-bank validator; retained medium reliability audit | Full default acceptance 45.3%; determinacy dominates failure. Historical 24-item repeat/alternate agreement is .826/.792. | Inconclusive as human validity; future human expert sample required. |
| Is the learner stream reproducible and nonleaking? | FULL-DATASET-FREEZE-001 | Exact 283,000-row replay; public/private link and 88 artifact hashes pass; probes do not update. | Supported. |

## RQ2 supporting questions

| Question | Evidence | Result | Status / caveat |
|---|---|---|---|
| Is the granularity curve U-shaped? | FULL-RQ2-001 | Descriptively yes on the six-point frozen grid: K* is the minimum and loss rises on both the coarser and finer sides; within each side it increases away from K*. | Supported only for this discrete, asymmetric grid; not a smooth or universal law. |
| Are merge/union and interaction/intersection equivalent? | FULL-RQ4-001; planted two-KC control | No. Family union and added conjunctions have distinct activation and predictive effects. | Supported structurally and empirically. |
| Are false negatives worse than false positives? | Three seeds at 10% Q noise | Mean costs .002644 vs .001685; ranges overlap in the limited structural sample. | Inconclusive; every corruption is harmful, but ordering is not established. |
| Does predictive ranking agree with state recovery? | FULL-MASTERY-001 | Yes overall: K* prerequisite-state RMSE .123738 versus .132752--.163828 alternatives. | Supported overall; coarse unseen-value reversal retained. |
| Does a plausible KT state necessarily match simulator mastery? | Secondary fixed BKT | No: unique learner-KC RMSE .300804, correlation .434973 under deliberate update/aggregation mismatch. | Negative result; targets differ from inverse-linked item state. |

## RQ3 supporting questions

| Question | Evidence | Result | Status / caveat |
|---|---|---|---|
| Does the candidate space contain K*? | Compositional ceiling after selection freeze | Exact 18/18 recovery, Jaccard/F1 1.0. | Positive control passes; reachability is not selection. |
| Does selection reject irrelevant structure? | Hash and interaction controls | Hash: 0 exact KCs and +.013238 probe loss. Added interactions do not improve over compositional; CI crosses zero in RQ3. | Negative control passes; one interaction contrast is inconclusive. |
| Can predictive fit uniquely identify K*? | Seen-Q signatures and paired predictions | Atomic and compositional policies have exactly identical seen Q and numerical-equivalent predictions. | Rejected by construction/evidence. |
| Is recovery stable at small N? | Pilot selector; FULL-COLLECTION-001 | The older N=120 discovery pilot selects coarse, but frozen unpenalized K*/coarse/split/exact comparison selects K* in all 21 nested cohorts from N=60 upward. A fixed KC penalty selects union in 18/21. | Criterion- and candidate-space-dependent; no universal sample threshold. |

## RQ4 supporting questions

| Question | Evidence | Result | Status / caveat |
|---|---|---|---|
| Does exact-cell memorisation transfer to new tuples? | 15 combination cells | Exact-cell costs +.037609 log loss, CI [.033761,.041513]. | Strongly rejected as a transfer representation in this world. |
| Is unseen-value performance cell-sensitive? | Per-cell and leave-one-cell-out | K* per-cell loss .666512--.691208; LOO macro .680016--.684955. | Yes; report cells, not only pooled events. |
| Does holdout item identity cause the grammar gap? | Exact-item novelty negative control | 30,000 paired outcomes are exactly identical after same-cell schedule replacement; K* loss remains below grammar holdouts. | Negative control passes only because baseline has no item memory/difficulty. |
| Can unseen outcomes choose between equivalent hypotheses? | Frozen-policy protocol | They expose differing extrapolations but are prohibited from selection. | No; using them would leak the evaluation target. |

## Robustness and collection-design ledger

| Question | Evidence-backed result | Status / caveat |
|---|---|---|
| Does K* remain predictively preferred under plausible simulator perturbations? | K* wins 38/39 primary worlds and every seed in 12/13 conditions. Split-2 reverses once under unmodelled item difficulty. | Broadly supported in the compact design, which varies assumptions mostly one at a time apart from combined guess/slip; not invariant to item nuisance. |
| Does more response volume repair an activation-equivalent Q? | With A+B-only items, all representations tie exactly through N=1,000. | Rejected: structural equivalence persists at any tested volume. |
| What do second within-cell variants add? | Max-one to max-two raises minimum KC support 1 to 2 but adds zero Q rows or rank. | Replication/support, not structural diversity; lexical benefit is not represented by this simulator. |
| Do anchor items guarantee recovery? | Anchors restore full rank and expose union merging; omitting a planted interaction costs only +.000506 at N=1,000 balanced. | Rank is necessary but insufficient for practically unique predictive recovery. |
| Does a KC-count penalty reveal truth? | Raw prediction selects K* 21/21; fixed penalty selects family union 18/21. | Rejected as a truth criterion; the penalty encodes a different objective. |

These are supporting design results rather than new paper-level RQs. They do
not turn synthetic thresholds into human study requirements.

## Overall answer

Synthetic perfect-information data support analyses that ordinary learner logs
cannot validate directly: controlled KC/Q perturbation, true-state recovery,
counterfactual nuisance mechanisms, and exact equivalence checks. Full-v1
continues to support its clean-world construction, misspecification, and narrow
recombination findings, while rejecting unique KC recovery from seen responses.

The measurement extension changes the external-validity interpretation. A
ranked Q and known state do not establish that a learner can answer the item or
that the platform process is plausible. Format nuisance can masquerade as skill
granularity in a planted control; structured errors can retain diagnostic
information that correctness discards; and schedule and dialogue choices alter
what KT can observe. But the learner-facing bank failed its coverage, rank,
answerability, and measurement gates, so the controlled worlds remain
`release_eligible=false` and there is no new dataset release.

The principal unresolved empirical questions are human linguistic/item
validity, real learner dynamics and format effects, corpus-grounded error
validity, policy-value estimation, generalisation beyond perfect-progressive
unseen values, and cross-lingual replication—not missing execution of a declared
synthetic experiment.
