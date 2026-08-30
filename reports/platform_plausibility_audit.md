# Platform plausibility audit of the frozen full-v1 item bank

Status: final deterministic cross-audit synthesis  
Dataset: `data/grammar_kt_full_v1/`  
Scope: all 113 fixed items, all 75 GrammarCells, all 18 generator KCs  
Mutation policy: full-v1 was read only and remains unchanged

## Finding in one paragraph

Two separately constructed automated audits agree that full-v1 is a useful clean Q-driven control bank but do not establish a platform-validated measurement bank. After an explicit five-category mapping, they assign the same category to 70/113 items (61.9%). Both call 60 items usable under their stated UI/scoring assumptions; the stricter census alone requests action on 19, the four-role live audit alone requests action on 10, and both request action on 24. The cross-audit differences and substantial role disagreement are evidence against one opaque realism score: every non-usable item and every disputed item should remain visible during extension design.

These counts are automated stress-test results, not estimates of how real learners, teachers, or platform teams would judge the items.

## What the two audits are

The **strict census** is the all-item ledger in `experiments/measurement_realism/audits/item_audit/`. One Codex review applied separate learner and platform perspectives under an explicit rubric. Its 19 perspective disagreements are useful, but they are not independent inter-rater disagreements.

The **live four-role audit** is the preregistered evidence in `experiments/measurement_realism/audits/full_v1_items_v2/`. Four independent critic roles—learner, teacher, platform-product, and measurement—judged each item without seeing one another's outputs across 16 audited batch calls. Its aggregate uses plurality plus the frozen tie-break rule. The 452 role judgments, rendered prompts, raw outputs, parsed outputs, settings, and hashes are retained.

Neither audit read learner outcomes or private learner trajectories. The learner-role critic did not see GrammarCell/KC oracle annotations. The other live roles did, because their task included measurement critique. Neither audit is human or expert gold.

## Explicit five-category mapping

The source labels differ, so agreement is computed only after this declared mapping. The operational rank reproduces the live audit's least-to-most-severe tie-break order; it is not a psychometric scale.

| Canonical category | Strict census label | Live four-role label | Rank | Meaning |
|---|---|---|---:|---|
| `usable` | `usable_as_stored` | `usable_as_is` | 0 | No material stored-task problem was identified under the audit's stated UI/scoring assumptions. |
| `local_change` | `minor_ui_or_context_change` | `minor_ui_or_answer_set_change` | 1 | A local UI, wording, context, or accepted-answer change may suffice. |
| `artificial` | `technically_valid_but_artificial` | `pedagogically_artificial` | 2 | The form is answerable but the interaction is pedagogically or platform-wise artificial as stored. |
| `answer_space` | `answer_space_problem` | `problematic_answer_space` | 3 | A salient reasonable response or construction is not fairly excluded or credited. |
| `withhold` | `rewrite_or_withhold` | `probably_not_deployable` | 4 | The task requires substantive redesign or withholding, not ordinary copy-editing. |

`artificial` and `answer_space` name different failure mechanisms even though the declared tie-break places one before the other. Exact-category agreement and the usable/action threshold are therefore more interpretable than treating the five categories as equal numerical intervals.

## Marginal results

| Canonical category | Strict census | Live four-role aggregate |
|---|---:|---:|
| `usable` | 70 (61.9%) | 79 (69.9%) |
| `local_change` | 15 (13.3%) | 23 (20.4%) |
| `artificial` | 15 (13.3%) | 2 (1.8%) |
| `answer_space` | 10 (8.8%) | 8 (7.1%) |
| `withhold` | 3 (2.7%) | 1 (0.9%) |

The strict census is more intervention-sensitive in aggregate: it marks 70 usable, versus 79 in the live plurality. That does not make it ground truth. The live plurality can also hide a minority critic's material concern.

## Exact cross-audit confusion

Rows are strict-census categories and columns are live-aggregate categories.

| Strict \ Live | usable | local change | artificial | answer space | withhold | Row total |
|---|---:|---:|---:|---:|---:|---:|
| usable | 60 | 5 | 0 | 4 | 1 | 70 |
| local change | 9 | 5 | 1 | 0 | 0 | 15 |
| artificial | 2 | 12 | 1 | 0 | 0 | 15 |
| answer space | 6 | 0 | 0 | 4 | 0 | 10 |
| withhold | 2 | 1 | 0 | 0 | 0 | 3 |
| Column total | 79 | 23 | 2 | 8 | 1 | 113 |

Exact mapped agreement is 70/113 (61.9%); 43 items move category. All cell-level item-ID lists are stored in `platform_audit_synthesis.json`, so no confusion cell is represented only by an aggregate count.

At the simpler action threshold:

| Cross-audit action status | Items | Percent |
|---|---:|---:|
| both usable | 60 | 53.1% |
| strict only requires action | 19 | 16.8% |
| live only requires action | 10 | 8.8% |
| both require action | 24 | 21.2% |

The intersection of 60 usable judgments is a conservative positive-control pool, not a validated deployable subset. The union of concerns contains 53 items and is the appropriate review queue for a wording-dependent extension.

## Stricter-versus-live differences

Using only the declared operational tie-break order, the strict census is more severe for 32 items (28.3%), the mapped category is the same for 70 (61.9%), and the live aggregate is more severe for 11 (9.7%). This is audit-process sensitivity, not accuracy against gold.

Important asymmetries include:

- twelve strict `artificial` items become live `local_change`; these are mostly intervention prompts whose constraints could plausibly move into UI;
- six strict `answer_space` items become live `usable`, showing that plurality can miss an alternative-response concern;
- two strict `withhold` items become live `usable`, including the reported-speech/Q-purity example below; and
- four strict `usable` items become live `answer_space`, so the stricter census is not uniformly more severe item by item.

Exact IDs and every rank delta from -4 through +4 are retained in the JSON artifact. Because category mechanisms differ, extension curation should read the rationales, not sort mechanically by delta.

## Role disagreement is evidence, not noise to average away

The strict census records 19/113 (16.8%) learner/platform-perspective differences within one review. The live audit records 56/113 (49.6%) items with at least two different role dispositions. These disagreement notions are deliberately not treated as interchangeable reliability coefficients.

| Live role | usable | local change | artificial | answer space | withhold |
|---|---:|---:|---:|---:|---:|
| `learner` | 74 | 23 | 1 | 14 | 1 |
| `teacher` | 91 | 10 | 2 | 8 | 2 |
| `platform_product` | 84 | 26 | 2 | 1 | 0 |
| `measurement` | 76 | 22 | 2 | 10 | 3 |

The two disagreement flags overlap on 11 items; 8 are strict-only, 45 live-only, and 49 show neither form. The live aggregate calls 24 items usable even though at least one independent role chose another disposition. Aggregate usability must therefore never erase role records.

## Representative exact learner-facing items

These examples quote the frozen prompt, target, accepted spans, and audit records. They are not reconstructed paraphrases.

### `shared_clear_pass` — `candidate_gc_0397fa37f2228649_02`

> The workers finished painting the room before lunch. Complete the sentence using the verb in brackets: By lunchtime, the room _____. (paint)

Target: `By lunchtime, the room had been painted.`  
Accepted response span(s): `had been painted`  
Active generator KCs: `gkc_aspect_perfect`, `gkc_be_passive`, `gkc_finite_past`

Strict census: `usable_as_stored`. The before-lunch/by-lunchtime contrast and verb cue make the expected span clear. This is a recognizable platform cloze with a focused passive-perfect dependency.

Live aggregate: `usable_as_is`. Role dispositions: learner=`usable_as_is`; teacher=`usable_as_is`; platform_product=`usable_as_is`; measurement=`usable_as_is`.

### `shared_answer_space_failure` — `candidate_gc_0397fa37f2228649_01`

> When we arrived at the park, the workers were gone and the gate was open. Complete the sentence using the cue “open”: The gate ____.

Target: `The gate had been opened.`  
Accepted response span(s): `had been opened`  
Active generator KCs: `gkc_aspect_perfect`, `gkc_be_passive`, `gkc_finite_past`

Strict census: `answer_space_problem`. “The gate was open” supports an adjectival state or simple-past completion as readily as past-perfect passive “had been opened.” The item cannot cleanly attribute failure to perfect + passive + past because the visible context does not select that analysis.

Live aggregate: `problematic_answer_space`. Role dispositions: learner=`problematic_answer_space`; teacher=`problematic_answer_space`; platform_product=`usable_as_is`; measurement=`usable_as_is`.

Live role concerns: learner: “The gate was open” is a natural, unaccepted completion; no time relation requires the keyed past perfect passive. | teacher: “Had been open” is a plausible completion, so the context does not securely require the passive verb form.

### `shared_artificial_interface` — `cue_bounded_imperative_gc_04a854582c08aa84_01`

> A child reaches toward a hot pan. Give a warning using an ordinary uncontracted negative imperative. Lexical cue chunks (deliberately out of order): “the hot pan” | “touch”. Rearrange and use all and only these chunks, exactly once each. You may add only the function words needed for ordinary uncontracted negative DO-support. Do not make any other additions, omissions, or substitutions; do not use contractions, politeness markers, vocatives, pronouns, or adverbs. Begin with a capital letter. Response: [________].

Target: `Do not touch the hot pan.`  
Accepted response span(s): `Do not touch the hot pan`  
Active generator KCs: `gkc_imperative`, `gkc_negation`

Strict census: `technically_valid_but_artificial`. The 78-word rule set is answerable but burdens the learner with “all and only,” function-word, punctuation, and exclusion instructions. A platform could implement the same task with draggable tiles, but the prose-as-UI is annotation-like and implausible as stored.

Live aggregate: `pedagogically_artificial`. Role dispositions: learner=`probably_not_deployable`; teacher=`pedagogically_artificial`; platform_product=`pedagogically_artificial`; measurement=`pedagogically_artificial`.

Live role concerns: learner: Technical constraints and dense prohibitions test instruction parsing more than an ordinary learner warning. | teacher: The lengthy specialist constraints overwhelm a simple imperative exercise and are unsuitable for ordinary learners. | platform_product: The unusually restrictive metalinguistic directions dominate a simple safety-warning grammar task. | measurement: Extensive metalanguage and arbitrary lexical restrictions overshadow the negative-imperative learning objective.

### `strict_measurement_purity_escalation` — `unchanged_rescue_gc_fac1ce90011b677c_02`

> Mia said, “I will carry one bag.” Complete the report: Mia said that she _____.

Target: `Mia said that she would carry one bag.`  
Accepted response span(s): `would carry one bag`  
Active generator KCs: `gkc_modal_would`

Strict census: `rewrite_or_withhold`. The report-completion task is understandable and has a clear answer. Success also requires reported-speech backshift and pronoun change, neither represented in the one-KC Q-row; it is not a pure `would` item.

Live aggregate: `usable_as_is`. Role dispositions: learner=`usable_as_is`; teacher=`usable_as_is`; platform_product=`usable_as_is`; measurement=`minor_ui_or_answer_set_change`.

Live role concerns: measurement: A natural contracted response (“she’d carry one bag”) is not visibly accepted.

### `live_temporal_determinacy_escalation` — `candidate_gc_19ed2b72505b3a96_01`

> Maya starts work at 9:00 a.m. Complete the sentence using the verb in brackets: By noon, Maya ___ for three hours. (work)

Target: `By noon, Maya will have been working for three hours.`  
Accepted response span(s): `will have been working`  
Active generator KCs: `gkc_aspect_perfect`, `gkc_aspect_progressive`, `gkc_modal_will`

Strict census: `usable_as_stored`. The start time and future endpoint uniquely motivate the future perfect progressive. An advanced but coherent platform cloze.

Live aggregate: `probably_not_deployable`. Role dispositions: learner=`problematic_answer_space`; teacher=`minor_ui_or_answer_set_change`; platform_product=`usable_as_is`; measurement=`probably_not_deployable`.

Live role concerns: learner: No future reference is given; “has been working” or “will have worked” are reasonable alternatives to the keyed answer. | teacher: The intended future reference point is implied rather than explicitly stated. | measurement: No future reference point establishes “will have been working”; “By noon” alone leaves the intended temporal frame underdetermined.

### `shared_modal_answer_space_failure` — `unchanged_rescue_gc_8a330fc9e496e359_02`

> The sky is dark, so take an umbrella. Complete the sentence using the cue “rain”: It ___ soon.

Target: `It may rain soon.`  
Accepted response span(s): `may rain`  
Active generator KCs: `gkc_modal_may`

Strict census: `answer_space_problem`. A dark sky and umbrella make “might rain” at least as natural as the sole accepted “may rain.” Because the modal is not supplied, correctness does not validly isolate the declared `may` KC.

Live aggregate: `problematic_answer_space`. Role dispositions: learner=`problematic_answer_space`; teacher=`usable_as_is`; platform_product=`minor_ui_or_answer_set_change`; measurement=`problematic_answer_space`.

Live role concerns: learner: The context permits “might rain,” “will rain,” and “is going to rain,” not only “may rain.” | teacher: The context also naturally permits “might rain,” though the instruction likely implies may. | platform_product: The context also naturally supports “might rain,” but the accepted answer permits only may. | measurement: The context licenses several future or possibility forms, but neither the prompt nor scoring establishes may as required.

## Actionable hard gates for the measurement extension

These are gates, not dimensions to average into a realism score.

| Gate | Requirement | Failure action |
|---|---|---|
| `linguistic_fidelity` | The visible task and keyed answer instantiate the declared GrammarCell; the context must not favor a different cell. | Rewrite or withhold; do not repair by accepting an answer that changes the intended Q row. |
| `task_and_ui_completeness` | Instruction, context/stimulus, response component, and learner action are explicit and executable rather than described through annotation-like prose. | Supply the missing UI/media or redesign the interaction before validation. |
| `answer_determinacy` | The information shown selects the intended response mechanism and construction without requiring the learner to guess author intent. | Add a natural constraint or redesign; an extra answer is insufficient when it changes the measured GrammarCell. |
| `response_space_fairness` | The executable scorer covers licensed contractions, punctuation/whitespace normalization, and salient valid responses appropriate to the displayed slot or options. | Expand the scoring policy or replace the task; retain every change as append-only provenance. |
| `kc_measurement_purity` | Success supplies defensible evidence about the declared active KCs without a major undeclared operation or obvious shortcut. | Redesign the item or explicitly revise the successor measurement/KC declaration before learner simulation. |
| `crossed_measurement_design` | KCs are crossed with formats and semantic families so no KC is wholly confounded with one campaign or interface; report support, anchors, crossings, nesting, and rank separately. | Add diagnostically distinct families or retain the bank as a bounded pilot rather than a release. |
| `independent_revalidation` | Every corrected or newly rendered item passes deterministic checks and independent role-specific validation; critic disagreement remains visible. | Escalate unresolved major concerns and all cross-audit category changes to targeted review. |
| `claim_boundary` | Automated audits may support stress-test and triage claims only; deployability, learner comprehension, and proficiency appropriateness require rendered human/expert evidence. | Use 'platform-oriented' or 'automatically audited', not 'platform-validated' or 'learner-validated'. |

Operationally, the extension should begin with the 60-item shared-usable pool as positive controls and the 53-item union-of-concerns queue as mandatory review—not silently discard one audit. All 18 items flagged at the union of the two audits' critical `answer_space`/`withhold` threshold must be rewritten or explicitly adjudicated before wording-dependent simulation. Artificial prompts should be re-expressed through an actual response component (for example tiles) rather than longer instructions.

For matched-format families, every retained format must independently pass the first five gates. Full Q rank, item count, or aggregate critic plurality cannot rescue a failed task, scorer, or measurement claim.

## What the audit supports

The defensible description of full-v1 remains:

> a frozen clean-control grammar-KT benchmark with an auditable intended
> item surface and automated platform-plausibility stress tests.

It is not yet defensible to call full-v1 a platform-validated item bank, a learner-validated assessment, or a realistic simulation of linguistic production. Prompt strings do not cause full-v1 responses after Q is fixed; the baseline has no rendered UI, executable scorer, intended proficiency field, surface learner response, item difficulty, or platform-like assignment policy.

## Reproduction and integrity

Run:

```bash
.venv/bin/python scripts/experiments/analyze_platform_audits.py
```

The script validates a one-to-one 113-item match across the strict ledger, live aggregates, 452 role judgments, and frozen item bank; validates the stored prompts/targets/accepted spans; reconciles both source summaries; and regenerates:

- `experiments/measurement_realism/audits/platform_audit_synthesis.json`; and
- `reports/platform_plausibility_audit.md`.

The JSON records SHA-256 hashes for every input and exact item IDs for every confusion, threshold, severity-delta, and disagreement cell. It also retains all 113 item-level mapped outcomes. The final report is generated from the same in-memory analysis, so its aggregate values are not hand-copied.

## Limitations

- Both audits are automated Codex judgments, not real learner responses, qualified teacher ratings, platform review, or psychometric validation.
- The strict audit is one role-separated review; its role disagreement is not inter-rater disagreement.
- The live roles are independent calls but use one model family and one frozen prompting design; plurality is not truth.
- The category mapping is declared and plausible but the source rubrics are not identical. Rank differences are triage diagnostics only.
- No intended CEFR/proficiency field, rendered UI, executable scoring normalizer, or learner response corpus exists for full-v1.
- Counts describe this exact 113-item bank and do not estimate prevalence for EGP, English-learning platforms, or human learners.
- Human/expert validation remains required for deployability, response process, accessibility, fairness, and educational-use claims.
