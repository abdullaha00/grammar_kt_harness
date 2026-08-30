# Historical full dataset investigation — curated medium-v1

Date: 2026-08-27
Status: complete for the retained English sample and declared synthetic learner
world; human item quality and human KC validity remain untested.

## Evidence boundary and supersession

The authoritative Phase-6 dataset is `data/grammar_kt_medium_v1/` after the
frozen F36 packaging correction and downstream rerun. It contains 139 source
descriptors, 24 canonical GrammarCells, 44 selected items, 1,000 synthetic
learners, and 204,000 events. The final analysis is
`reports/phase6/artifacts/full_dataset_analysis/summary.json`; its paper-facing
tables are in the same directory. The selection-stability result is
`reports/phase6/artifacts/selection_stability_v1/results.json`.

The earlier 45-item finalization and selection-stability run are superseded.
Their dataset derivatives were moved to
`data/grammar_kt_medium_v1/superseded_pre_curation/2026-08-27_f36_packaging_correction/`,
and the old selection-stability study was moved to
`reports/phase6/artifacts/superseded_pre_curation_selection_stability_v1/`.
They are provenance, not final evidence. Raw generation candidates and original
validator judgments remain unchanged; the curated layer records six exact
edits and six replacement judgments separately.

All item-quality judgments are model judgments or an agent-based qualitative
audit. No teacher, learner, linguist, or other human annotator evaluated the
bank. All learner responses are synthetic under declared latent worlds. Thus
the investigation establishes an executable methodology and controlled
recovery/prediction evidence, not human pedagogical effectiveness or cognitive
truth.

## Final experiment in one view

```text
139 retained EGP descriptors
→ retained constrained normalization
→ 24 exact six-feature GrammarCells
→ 78 generation attempts / 77 valid candidate payloads
→ independent all-criteria validation
→ frozen six-record packaging correction and revalidation
→ 54 validator-accepted candidates / 44 selected items / 24 covered cells
→ semantic 18 development / 5 compositional / 1 novel-value cell fold
→ 1,000 mixed-world synthetic learners / 204,000 events
→ 55 structural KC candidates / 28 selection-eligible representatives
→ 9 protected feature KCs + 1 selected interaction
→ frozen Q-matrices → empirical, BKT, and observable-logistic KT
→ 44,000 frozen probes and learner-cluster paired uncertainty
```

The fixed-bank boundary was maintained: item generation and validation did not
receive the grammar fold, learner evidence, candidate KCs, latent world, KT
predictions, or evaluation results. KC selection received 160,000 development
acquisition events (128,000 train; 32,000 chronological validation), and no
holdout or reserved test event.

## Source, normalization, and canonical inventory

| Result | Count | Proportion of 139 |
|---|---:|---:|
| complete | 44 | 31.65% |
| partial | 77 | 55.40% |
| unresolved | 2 | 1.44% |
| out of scope | 16 | 11.51% |

The 44 contributing descriptors produce 48 source-to-cell edges and 24 unique
GrammarCells: 1.83 contributing descriptors and 2.00 edges per cell on average.
This is genuine editorial compression, but it should not be summarized as
139-to-24 because 95 partial, unresolved, or out-of-scope rows do not contribute
an exact cell. Current canonicalization exactly reproduces the retained legacy
24-cell feature inventory and source memberships.

The inventory is uneven. Present and past occur in 11 and 10 cells (22 and 17
selected items); three cells have `tense=NA`. Active voice dominates (19 cells,
35 items) over passive (5, 9). Declaratives dominate (20 cells, 37 items), with
two polar-question and two imperative cells; no WH-question cell is present.
Twenty-three cells use `modal=none`; the sole modal cell has `would`, and every
other schema-declared modal has zero support. Thirteen of 24 exact cells have
only one source edge, while positive imperative has seven. Sparse schema values
therefore remain a source-coverage limitation, not evidence that they are
unimportant KCs.

The Phase-4 replay gives the relevant normalization audit boundary. Historical
Phase 2 made 80 calls but resolved only 2 (2.5%); explicit eligibility identifies
only 9/80 rows, all uncertain in tense, and would have avoided 71 calls. All 80
retained transitions pass the stronger branch-preserving checks. Eight selected
repeat annotations agree exactly, but that is too small and selected to estimate
general annotation reliability. The retained `gpt-5.6-sol`/medium snapshot is
not a repeated-run or cross-model stability study.

## Item construction, validation, and curation

### Generation and coverage

The final curated reconstruction is:

| Stage | Attempts | Candidate payloads | Accepted | Covered cells | Would select |
|---|---:|---:|---:|---:|---:|
| default prefix N=1 | 24 | 24 | 16 | 16 | 16 |
| default prefix N=2 | 48 | 48 | 33 | 19 | 33 |
| default prefix N=3 | 72 | 71 | 51 | 22 | 41 |
| rescue only | 4 | 4 | 1 | 1 | 1 |
| cumulative through rescue | 76 | 75 | 52 | 23 | 42 |
| explicit-construction intervention only | 2 | 2 | 2 | 1 | 2 |
| **final cumulative** | **78** | **77** | **54** | **24** | **44** |

The counts differ from the preregistration's pre-curation checkpoint because
fresh F36 judgments rejected two formerly accepted default candidates and
accepted one formerly rejected intervention candidate. The 44-item table above
is final; the old 53-default/45-selected counts are superseded. Twenty-two
cells required the default three attempts, `cell_022` required five, and
`cell_017` required seven. The single structural failure was a missing required
legacy output field for `candidate_cell_001_03`, not an API loss or a linguistic
failure.

N=3 materially improves coverage over N=1 (22/24 versus 16/24), but does not
complete the bank. The separate eight-cell Phase-4 prefix experiment found that
N=5 added accepted candidates but no coverage beyond N=3 (8/8 at both) and
reduced acceptance from .750 to .675. This supports N=3 as a cost/coverage
default, not a claim that N=3 is universally optimal. The full bank never ran
N=5 for all cells.

### Validation behavior

Final acceptance is 54/77 valid candidates (70.13%), or 54/78 attempts (69.23%).
The all-required criterion pass rates are:

| Criterion | Passed / 77 | Pass rate |
|---|---:|---:|
| target fidelity | 77 | 100% |
| grammaticality | 77 | 100% |
| naturalness | 75 | 97.40% |
| pedagogical suitability | 74 | 96.10% |
| determinacy | 55 | 71.43% |
| non-target-language simplicity | 77 | 100% |
| no answer leakage | 77 | 100% |
| no extraneous grammar | 77 | 100% |
| no world knowledge | 77 | 100% |

Determinacy fails on 22 candidates and is by far the active bottleneck;
naturalness fails twice and pedagogical suitability three times, sometimes
alongside determinacy. Always-passing criteria are not proven redundant: this
is one model, one snapshot, and one English sample. In particular, zero failures for
non-target-language simplicity means that the validator detected none, not that
lexical nuisance difficulty is absent.

Phase-4 repeated-judgment evidence quantifies this boundary. Original versus
same-model acceptance agrees on 19/23 valid rejudgments (82.6%, Wilson 95%
interval [62.9%, 93.0%], kappa .652); original Terra versus Sol agrees on
19/24 (79.2%, [59.5%, 90.8%], kappa .583). One repeat output is malformed.
This is material judgment/model uncertainty and gives no basis for treating
the validator as gold or using an ensemble without human adjudication.

The hardest cells are structurally marked and temporally difficult to elicit:
past perfect passive `cell_022` accepts 1/5, negative past perfect progressive
`cell_017` accepts 2/7 after intervention and correction, and positive past
perfect progressive `cell_018`, positive past perfect `cell_015`, and positive
imperative `cell_005` each accept 1/3. Five of the first two cells' failures are
explicitly about determinacy. This is a realistic-scale failure of semantic
elicitation, not random call loss.

### Rescue and explicit-construction intervention

Default N=3 left `cell_017` and `cell_022` uncovered. The unchanged-prompt
rescue generated exactly two further candidates for each; one of four passed,
covering `cell_022`, while all five accumulated `cell_017` candidates still
failed determinacy. The rescue therefore resolved one of two cells, not the
whole failure.

For the still-uncovered `cell_017`, the preregistered intervention changed only
the generation prompt so it could name the target construction. Both generated
items are accepted in the final curated evidence: one passed originally and the
second passed after its complete-target packaging error was corrected and
independently rejudged. This restores coverage but is only two candidates from
one cell. The surviving prompts are metalinguistic and one is contrived; the
result shows an operational escape hatch, not a general causal estimate of
prompt effectiveness or realism.

### Frozen packaging correction (F36)

An agent audit identified five selected packaging defects and a likely
slot-versus-complete-target error on rejected `candidate_cell_017_06`. The
correction plan froze six exact before/after values and preserved item IDs,
prompts, cells, raw candidates, and original judgments. Independent
`gpt-5.6-terra`/medium revalidation accepted four corrections:
`candidate_cell_003_01`, `_017_06`, `_018_03`, and `_019_03`. It rejected
`_005_01` because “Turn the light on” remained an unlisted alternative and
`_018_01` because a `since eight` completion remained possible. The selected
bank therefore changed from 45 to 44: two formerly selected items were removed,
one formerly rejected item entered, and all 24 cells remained covered.
The frozen plan hash is
`bbed7be77c2d326bd7133308ea22d637bed5de8d44cd4bb470a2421c4ebe0dc5`.

This partly supports F36. The frozen edits repaired serialization defects and
the pipeline responded correctly to fresh evidence, but correction did not make
all six packages valid. The raw candidate and judgment hashes are preserved;
all stale downstream artifacts were archived and recomputed.

### Bank size, diversity, and realism

At most two variants per cell reduces 54 accepted candidates to 44 selected
items (18.52% reduction) while retaining all 24 cells. Twenty cells have two
items and four have one. All 44 prompts are distinct. They contain 795 prompt
word tokens and 242 types (TTR .304), with median prompt length 17 tokens. The
20 rank-2 items have median token-set distance .739 from their cell's first
item. These are lexical surface statistics, not evidence of instructional
diversity.

The pre-curation independent agent audit inspected every then-selected item and
all 22 rejections. It found no clearly ungrammatical or wrong-cell selected
target, but flagged judgment-sensitive perfect/simple-past, past-progressive,
and passive decisions. It also found heavy worksheet-template reuse, repeated
names, domestic contexts, and predicates. That audit's 45-item category counts
are superseded by F36; its qualitative failure modes remain traceable in
`reports/phase6/artifacts/qualitative_item_audit.md`. A direct count over the
final 44 prompts still finds 33 containing “complete,” 18 explicitly mentioning
a cue, 13 mentioning Mia, and 7 mentioning Maya. The resulting material is
plausible focused controlled-production practice, but is more worksheet-like
than communicatively diverse. Human usability remains unresolved.

## Grammar fold and learner evidence

| Regime | Cells | Items | Unseen development values | Value pairs unseen in development |
|---|---:|---:|---:|---:|
| development | 18 | 32 | 0 | 0 |
| compositional holdout | 5 | 10 | 0 | 1 |
| novel-value holdout | 1 | 2 | 1 (`modal=would`) | 6 |

Every compositional cell is an unseen exact tuple whose individual feature
values occur in development. However, one of its 37 value pairs is also unseen,
so the fold is clean at the constituent level but not a pure all-pairs-seen
test. The novel regime is only one cell and cannot support a broad novel-value
claim.

Each learner receives five passes over 32 development items (160 acquisition
events) followed by one non-updating probe for each of 44 items. Across 1,000
learners this gives 204,000 events: 160,000 acquisition and 44,000 probes. The
probe set contains 32,000 development, 10,000 compositional, and 2,000 novel
events. No holdout item occurs in acquisition. Events and outcomes are identical
across KC policies, and logistic KT uses no simulator-derived item difficulty or
KC count.

## KC hypothesis space and automated selection

### Structural candidates

| Family | Raw | Support eligible | Activation duplicates | Selection eligible | Median item support |
|---|---:|---:|---:|---:|---:|
| feature value | 9 | 9 | 0 | 9 | 6.0 |
| declared operation | 10 | 7 | 6 | 3 | 4.5 |
| pairwise interaction | 18 | 8 | 2 | 7 | 2.0 |
| development full cell | 18 | 18 | 9 | 9 | 2.0 |
| **total** | **55** | **42** | **17** | **28** | — |

Support filtering removes 13 candidates and activation-equivalence plus family
eligibility reduces the usable inventory to 28 representatives across 38
activation classes. These are equivalences on the 32 development items, not
universal linguistic identities.

Of ten English operation declarations, only `finite_tense_form` (16 cells/29
items), `perfect_dependency` (8/13), and `progressive_dependency` (6/11) remain
selection eligible. Imperative, negation, inversion, and passive-dependency are
activation aliases of canonical feature KCs. Central modal and the two WH
operations have zero development support. No operation is selected in the
final policy.

### Selected policy and trace

The selector starts with nine protected non-background feature KCs, scores
supported nonredundant operations/interactions using chronological development
evidence, minimizes validation log loss plus `.0005 × KC count`, and
backward-prunes before freezing. From ten eligible additions it selects only:

`kc_interaction__aspect_perfect__and__polarity_negative`

The interaction has two-cell/four-item structural support. It reduces selector
validation log loss from .647160 to .646354. After paying the extra .0005
complexity penalty, objective improves by .000307; the best second addition
would worsen objective by .000137. No holdout grammar or outcome enters this
trace.

| Policy | KCs | Interactions | KCs/item | Q density | Median item support |
|---|---:|---:|---:|---:|---:|
| factorized | 9 | 0 | 2.091 | .232 | 8 |
| **automated** | **10** | **1** | **2.182** | **.218** | **8** |
| all supported interactions | 16 | 7 | 2.886 | .180 | 6 |
| oracle exact-all-cell | 24 | 0 | 1.000 | .042 | 2 |

The lower Q density of larger policies reflects a larger denominator; KCs/item
is the more direct edge-load comparison. Reusable policies cover every
compositional item but do not activate on the two novel-`would` items. The
oracle covers all items by construction and is not development-admissible.

### Selection stability and support

The final 44-item bank was replayed at nested 60/120/240/500/1,000 learner
prefixes for seed 20260827 and at 1,000 learners for five seeds
20260827–20260831. All five 1,000-learner seeds select exactly the same ten KCs
(all-KC and addition Jaccard 1.0). Eight of nine total conditions reproduce the
final inventory. The 120-learner prefix replaces perfect×negative with
present×passive; 60, 240, 500, and 1,000 select perfect×negative. Thus the nine
protected features are invariant and the full-support result is stable, but
one small-sample anomaly shows that the interaction is not an ontology fact.
No holdout or reserved test event enters any stability selection.

Phase 5 supplies the complementary four-world support result. At 240 learners,
the selector recovered both eligible planted interactions in all three
interaction-heavy seeds and made no addition in any factorized-null seed; at
smaller samples false or swapped additions were more common. More learners
reduce sampling noise, but they do not increase the final interaction's two-cell
structural support. Broader grammar/item support remains needed.

Selecting two variants materially changes the candidate measurement space.
Using only the rank-1 development variant gives 37 support-eligible and 23
selection-eligible candidates, including two eligible interactions; up to two
variants gives 42, 28, and seven. Five interactions become eligible only with
the larger bank. This is a structural sensitivity analysis: learner outcomes
were not read and the selector was not rerun on the one-variant bank, so an
inventory-change claim remains unresolved.

## KT prediction and generalization

### Absolute primary-logistic results

All rows use the same 44,000 frozen probes.

| Policy | Log loss | Brier | AUC | ECE |
|---|---:|---:|---:|---:|
| factorized | .643731 | .225775 | .5604 | .0034 |
| all supported interactions | **.643334** | **.225596** | **.5650** | **.0027** |
| automated | .643356 | .225610 | .5641 | .0044 |
| oracle exact-all-cell | .657507 | .232565 | .5459 | .0413 |

All-supported interactions have the best point estimate by only .000022 log
loss over automated while using six more KCs. The automated method is therefore
a prediction/parsimony choice, not the absolute predictive winner. The labelled
all-cell oracle performs worst overall because its evaluation-cell KCs lack
acquisition history.

Empirical and BKT results are retained as sensitivities, not as the primary KC
comparison. Their all-test log losses are .665–.693 and .817–.828 for reusable
policies, respectively, versus about .643 for logistic. Phase 4 also found that
BKT's full-credit updates over multiple active KCs change inventories and
confound representation size; the observable logistic remains the selector and
primary evaluator.

### Paired representation effects

Effects below are candidate minus factorized; negative favors the candidate.
Intervals are 5,000 whole-learner bootstrap resamples, seed 20260827.

| Regime | Candidate | Δ log loss [95% interval] | Δ Brier [95% interval] |
|---|---|---:|---:|
| all probes | automated | **−.000375 [−.000631, −.000109]** | **−.000166 [−.000281, −.000046]** |
| all probes | all interactions | **−.000397 [−.000782, −.000026]** | **−.000180 [−.000356, −.000008]** |
| all probes | exact-cell oracle | **+.013777 [+.012288, +.015235]** | **+.006789 [+.006070, +.007491]** |
| development | automated | **−.000450 [−.000758, −.000141]** | **−.000203 [−.000339, −.000065]** |
| compositional | automated | −.000234 [−.000836, +.000375] | −.000091 [−.000372, +.000192] |
| compositional | all interactions | **−.001168 [−.002042, −.000246]** | **−.000532 [−.000935, −.000109]** |
| novel value | automated | +.000119 [−.000099, +.000352] | +.000057 [−.000047, +.000169] |

The automated policy's all-probe and development gains are small but
learner-cluster-robust under the declared mixed world. Its compositional interval
crosses zero, so the main selector has no established compositional advantage.
The richer all-interaction policy does improve compositional probes in this
world, at a six-KC complexity cost. Novel-value evidence is inconclusive and
only 2,000 probes from one cell; factorized/automated policies have no KC for
`would`, so these metrics cannot establish novel-KC generalization.

### Latent-world robustness

The final 44-item experiment uses one mixed world. The retained Phase-5
four-world, three-seed study constrains interpretation but used the immediately
preceding structural bank. Mean all-probe fixed-logistic losses were:

| World | Factorized | All interactions | Automated | Exact cell |
|---|---:|---:|---:|---:|
| factorized | .578311 | .578334 | .578311 | .603004 |
| interaction-heavy | .609353 | .607225 | **.607097** | .621903 |
| cell-specific | .686715 | .686379 | .686715 | **.679439** |
| mixed | .641559 | **.641273** | .641575 | .652886 |

Automation recovers predictive interactions in the positive-control world and
collapses to factorized KCs in clean controls, but no representation dominates
all plausible worlds. Exact cells win only when the latent world is itself
cell-specific. These are synthetic stress tests; they do not identify the
latent structure of human grammar learning.

## Cost evidence

Across 78 generation calls, recorded per-call durations sum to 784.2 seconds
(median 9.30 s). Across 77 validation records, 57 have duration metadata and
sum to 626.3 seconds (median 10.93 s); 20 reused pilot judgments lack retained
duration. Calls ran with four workers, so sums are workload totals, not elapsed
wall time. Generation has the larger recorded workload total, while validation
has the larger median per recorded call. Provider prices were unavailable, and
the retained normalization snapshot has no comparable cost accounting.

## RQ-F1–F36 ledger

Statuses refer only to the evidence retained in this repository.

| RQ | Status | Evidence-based answer and implication |
|---|---|---|
| F1 | answered for sample | Of 139 descriptors, 44 complete, 77 partial, 2 unresolved, and 16 out of scope (31.65%, 55.40%, 1.44%, 11.51%). Most source rows do not safely yield an exact cell. |
| F2 | answered | The 44 complete mappings yield 24 unique GrammarCells. |
| F3 | answered | Forty-four contributors create 48 source-cell edges compressed to 24 unique cells (1.83 contributors and 2.00 edges/cell). Noncontributors are not counted as compressed cells. |
| F4 | answered for sample | Modal, WH, passive, question, imperative, and several aspect values are sparse; only `would` is observed among non-`none` modals and WH support is zero. |
| F5 | answered for sample | Active declaratives and `modal=none` dominate. Thirteen cells have one source edge; positive imperative has seven. The inventory is not balanced English grammar coverage. |
| F6 | answered | Five cells/ten items form constituent-compositional holdout; all values are seen, but one of 37 value pairs is unseen. |
| F7 | answered narrowly | One `modal=would` cell/two items form novel-value holdout. This is too small for a general novel-feature conclusion. |
| F8 | answered | N=1/2/3 covers 16/19/22 cells. Twenty-two cells stop at three attempts, one needs five, and one needs seven including the separate intervention. |
| F9 | partially answered | N=3 gives large full-bank coverage gains. An eight-cell pilot found no N=5 coverage gain, but full-bank N=5 was not run; universal optimality is unresolved. |
| F10 | answered under model judge | Final acceptance is 54/77 valid payloads (70.13%) and coverage is 24/24 after rescue/intervention/curation. |
| F11 | answered | `cell_017` and `cell_022` are hardest to generate determinately; their marked tense/aspect contexts require 7 and 5 attempts. The only structural payload failure is a missing legacy field. |
| F12 | answered under one judge | Determinacy passes only 55/77 and dominates model-judged rejection; two records also fail the deterministic slot-contract precheck. Every target-fidelity and grammaticality judgment passes. Always-passing criteria are not proven redundant. |
| F13 | quantitatively answered; pedagogically unresolved | Final prompts are unique, with 242 types/795 tokens and TTR .304, but template/name/context repetition is substantial and no human diversity judgment exists. |
| F14 | answered within validator boundary | Non-target-language simplicity fails 0/77. The proper conclusion is “not detected by this validator,” not “lexical difficulty absent.” |
| F15 | answered | Development grammar/items produce 55 raw candidates: 9 feature, 10 operation, 18 pair, and 18 full-cell. |
| F16 | answered | Support leaves 42; activation/family filtering leaves 28 representatives and marks 17 duplicates across 38 activation classes. |
| F17 | answered structurally | Three operations are nonredundant and supported; four are canonical-feature aliases; three have zero support. No operation survives learner-evidence selection. |
| F18 | answered for mixed synthetic world | The selector adds only perfect×negative (2 cells/4 items) to nine protected features. This is not evidence of a human English dependency. |
| F19 | answered at tested scale | All five 1,000-learner seeds select the same inventory; 8/9 nested/seed conditions match. One 120-learner swap shows finite-sample instability. |
| F20 | answered | Automated uses 10 KCs versus 9 factorized, 16 all-interaction, and 24 oracle exact-cell KCs; it is close to the reusable extreme. |
| F21 | answered | Automated median selected-KC item support is 8 (range 3–22), 2.182 KCs/item, Q density .218; its interaction has four-item support. |
| F22 | answered for synthetic mixed world | Automated improves all-probe log loss over factorized by .000375 with a paired interval excluding zero, while using six fewer KCs than all-interaction. All-interaction has a .000022 better point estimate, so automation is a parsimony trade-off. |
| F23 | partially answered | Automated compositional Δ log loss is −.000234 with an interval crossing zero; all-interaction improves by −.001168 with an interval below zero. A compositional benefit of the selected policy is unresolved. |
| F24 | partially answered | Four synthetic worlds show strong method×world dependence and no universal winner. Human-world robustness is unknown, and final-bank KT is run only in the mixed world. |
| F25 | partially answered | Full-support selection is identical across five 1,000-learner seeds; 120 learners swaps the interaction while 60/240/500/1,000 match on one seed. Learner volume cannot replace broader cell/item support. |
| F26 | partially answered | Recorded generation workload is 784.2 call-seconds and validation 626.3; concurrency prevents wall-time interpretation and provider price is unavailable. |
| F27 | answered | Scale exposes incomplete N=3 coverage, systematic tense/aspect determinacy failure, judge inconsistency, packaging defects, and variant-dependent KC eligibility. These failures changed the active method. |
| F28 | partially answered | Items are recognizable controlled grammar practice and no audited final target is clearly wrong-cell, but the bank is worksheet-like and model/agent judged. Human realism and pedagogical efficacy are unresolved. |
| F29 | partially answered | Candidate enumeration, activation, support, equivalence, selection, and freezing consume declared dimensions generically; EGP normalization, the six-feature schema, operation declarations, prompts, and empirical results are English-specific. A toy alternate-schema contract is structural, not cross-lingual validation. |
| F30 | partially answered | Current conversion exactly reproduces the retained 24 cells/source memberships and eight selected repeats agree, but the unpinned retained model snapshot supplies no general repeat- or cross-model-stability estimate. |
| F31 | answered | The deterministic prefix check rejects two malformed slot contracts (`cell_010_02`, `cell_021_02`) before judging; both cells retain other selected items, so coverage is unchanged. The active suffix guard now protects the punctuation-defect class exposed by F36. |
| F32 | answered | Selection reduces 54 accepted items to 44, preserves 24/24 coverage and unique prompts, and gives median rank-2 token distance .739. Surface diversity does not establish contextual diversity. |
| F33 | answered | The frozen two-per-cell rescue covers one of two N=3 gaps (1/4 accepts); `cell_017` remains uncovered and requires the separately declared F35 intervention. |
| F34 | partially answered | Two variants raise eligible interactions from 2 to 7 and total selection-eligible candidates from 23 to 28. Because outcomes were not read and selection was not rerun on the one-variant bank, the policy effect is unresolved. |
| F35 | partially answered | Explicitly naming the construction yields 2/2 final accepts for the one hard cell after correction, versus 0/5 prior semantic prompts, and restores coverage. The one-cell, two-item, metalinguistic comparison cannot establish general effectiveness or realism. |
| F36 | answered operationally; hypothesis partly supported | Six frozen corrections are independently rejudged: four pass, two remain indeterminate. The selected bank changes 45→44, retains 24-cell coverage, preserves raw evidence, and all downstream results are recomputed. |

## Methodological decisions and negative results

1. **Retain constrained exact canonicalization.** Partial evidence is not forced
   into exact cells. Phase 2 is explicitly eligible and branch preserving; its
   2.5% historical yield rejects routine example-based resolution.
2. **Retain model-selected common language and N=3 as defaults.** The controlled
   six-entry lexicon had worse pilot coverage, source evidence showed no gain in
   only three cells, and pilot N=5 added no coverage. These remain scale-limited
   ablations.
3. **Keep independent all-criteria validation and deterministic slot checks.**
   Determinacy filters substantial output, but one validator is inconsistent.
   The final bank therefore includes an explicit, hashed curation overlay rather
   than silent edits.
4. **Keep semantic folds and frozen probes.** Mixed-history probes have prior
   holdout exposure and do not estimate clean acquisition transfer. The final
   holdouts have zero acquisition exposure.
5. **Keep the forward/prune selector at `lambda=.0005`.** It is interpretable,
   stable at 1,000 learners, and parsimonious. Residual shortlisting, top-down
   merging, the old obligation selector, and unpenalized selection remain
   rejected baselines/negative results.
6. **Do not claim a universal KC ontology.** The final policy's gain is tiny,
   compositional evidence is mixed, and world rankings change with latent
   structure. Exact cells are useful only in the matching synthetic world and
   generalize poorly elsewhere.
7. **Do not claim human dataset validity.** Model acceptance, lexical TTR, and
   agent audit are insufficient substitutes for expert or learner evaluation.

## Remaining unresolved questions

- Will human teachers and learners judge the 44 items grammatical, natural,
  determinate, appropriately difficult, and pedagogically useful?
- Do real learner responses select perfect×negative, another interaction, or a
  different representation entirely?
- Does the selected policy improve compositional transfer with more cells,
  especially when every held-out value pair is observed in development?
- How should truly novel values such as `would` receive a KC without leaking
  holdout grammar into development-only selection?
- Are normalization mappings stable across representative repeats, pinned model
  snapshots, and human annotation?
- Does one-versus-two item selection change the learned KC policy, rather than
  only structural eligibility?
- Does the schema-generic methodology retain interpretability and predictive
  value in another language? The current alternate-schema test verifies only
  software/interface reuse.
- Can item prompts gain communicative/contextual diversity without sacrificing
  determinacy, especially for marked tense/aspect combinations?

## Exact reproducibility

Models and settings:

- retained normalization: `gpt-5.6-sol`, medium, retained 2026-08-20;
- generation: `gpt-5.6-sol`, medium;
- independent validation and correction revalidation: `gpt-5.6-terra`, medium;
- item calls: four workers; calls are independently checkpointed;
- primary learner/selector/logistic/bootstrap seed: `20260827`;
- stability seeds: `20260827`–`20260831`;
- prior four-world robustness seeds: `20260827`–`20260829`;
- learner bootstrap: 5,000 whole-learner resamples.

Commands, in scientific order:

```bash
.venv/bin/python scripts/run_normalisation_audit.py

.venv/bin/python scripts/run_item_audit.py --pilot --select-second --workers 4 \
  --generation-model gpt-5.6-sol --validation-model gpt-5.6-terra \
  --reasoning-effort medium \
  --output-dir reports/phase4/artifacts/item_audit/live_pilot

.venv/bin/python scripts/run_validation_reliability.py \
  --input-dir reports/phase4/artifacts/item_audit/live_pilot \
  --output-dir reports/phase4/artifacts/validation_reliability \
  --sample-size 24 --seed 20260827 --workers 4 \
  --repeat-model gpt-5.6-terra --sensitivity-model gpt-5.6-sol \
  --reasoning-effort medium

.venv/bin/python scripts/run_phase4_world_audit.py

.venv/bin/python scripts/run_phase5_integrated_validation.py

.venv/bin/python scripts/run_full_dataset.py --prepare-only \
  --output-dir data/grammar_kt_medium_v1

.venv/bin/python scripts/run_full_dataset.py --generate-missing --workers 4 \
  --generation-model gpt-5.6-sol --validation-model gpt-5.6-terra \
  --reasoning-effort medium --output-dir data/grammar_kt_medium_v1

.venv/bin/python scripts/run_full_dataset.py --rescue-uncovered --workers 4 \
  --generation-model gpt-5.6-sol --validation-model gpt-5.6-terra \
  --reasoning-effort medium --output-dir data/grammar_kt_medium_v1

.venv/bin/python scripts/run_full_dataset.py --determinacy-intervention \
  --workers 4 --generation-model gpt-5.6-sol \
  --validation-model gpt-5.6-terra --reasoning-effort medium \
  --output-dir data/grammar_kt_medium_v1

.venv/bin/python scripts/curate_item_packaging.py \
  --dataset-dir data/grammar_kt_medium_v1 --workers 4 \
  --validation-model gpt-5.6-terra --reasoning-effort medium

.venv/bin/python scripts/finalize_full_dataset.py \
  --dataset-dir data/grammar_kt_medium_v1 --learners 1000 \
  --seed 20260827 --bootstrap-repeats 5000

.venv/bin/python scripts/run_phase6_selection_stability.py

.venv/bin/python scripts/analyze_full_dataset.py \
  --dataset-dir data/grammar_kt_medium_v1 \
  --output-dir reports/phase6/artifacts/full_dataset_analysis
```

The analysis command makes no model calls and does not recompute learner
outcomes. Primary retained artifacts are:

- `data/grammar_kt_medium_v1/manifest.json` and
  `finalization_manifest.json`;
- `items/curated_candidates.jsonl`, `items/curated_validation.jsonl`,
  `items/selected_bank.jsonl`, and `items/packaging_correction_manifest.json`;
- `fold/assignments.jsonl`, `simulation/events.jsonl.gz`, and private
  `simulation/oracle_debug.json.gz`;
- `kc/candidate_inventory.json`, `kc/selection_trace.json`, frozen policies,
  Q-matrices, and projections;
- `kt/{policy}/predictions.jsonl.gz` and `evaluation/{policy}/results.json`;
- `reports/phase6/artifacts/full_dataset_analysis/` and
  `reports/phase6/artifacts/selection_stability_v1/results.json`.
