# Research state

Last updated: 2026-08-28, Phases 2--7 and the backend-effort audit complete. This file is the compact programme
handoff; experiment detail belongs in `reports/experiment_log.md` and the phase
reports.

## 1. Current active pipeline

```text
typed EGP source rows
→ descriptor-only Phase-1 normalisation
→ explicitly eligible, branch-preserving Phase-2 refinement
→ exact six-dimensional English GrammarCells
→ three independent model-selected item candidates/cell
→ deterministic answer-span check + independent all-criteria judgment
→ separately labelled rescue/explicit-construction fallback only for persistent
  zero-coverage determinacy failures
→ deterministic slot/reference audit + frozen correction/revalidation
→ at most two valid, token-diverse items/cell
→ outcome-free semantic development/compositional/novel-value fold
→ development acquisition + non-updating frozen probes
→ development-only schema/operation/pair/full-cell KC candidates
→ support and activation-equivalence filtering
→ observable-logistic predictive/parsimony selection
→ frozen automatically selected KC policy and Q-matrix
→ empirical/BKT/no-oracle logistic KT
→ regime metrics and learner-paired policy comparisons
```

`scripts/run.py` is the paper-facing linear implementation. It executes the
candidate-generation and selection stages rather than loading a manually
written final ontology. Generation and simulation receive no KC policy;
candidate construction receives only development cells/items; selection
receives only development events. The normal fixture overrides item generation
to one candidate/cell only to keep software tests offline and fast.
The retained-dataset sequence is explicit in `run_full_dataset.py`,
`curate_item_packaging.py`, `finalize_full_dataset.py`,
`run_phase6_selection_stability.py`, and `analyze_full_dataset.py`.

Live model settings are now an explicit per-stage scientific declaration in
`modules/model_backends.yaml`: Sol/high normalisation, Sol/medium generation,
and Terra/medium validation. The retained final dataset is unchanged and
continues to document the all-medium calls from which it was constructed.

The retained medium dataset contains 139 source descriptors, 24 exact cells,
44 selected model-validated and packaging-curated items, 1,000 synthetic
learners, and 204,000 fixed events. The four-world audit uses all 24 cells, 240
learners/world, and three seeds; Phase 5 adds nested 30/60/120/240 learner
selection and a five-point λ grid. The final-bank stability study uses five
1,000-learner seeds plus nested 60/120/240/500/1,000 conditions.

## 2. Current recommended methodology

- **Normalisation:** require `phase2_eligible` to name only uncertain
  dimensions; allow Phase 2 only to narrow those domains while preserving every
  Phase-1 branch and every ineligible exact field. Retain partial/unresolved
  rows rather than guessing.
- **Canonical representation:** keep the declared six English dimensions as an
  interpretable structural representation, not a claim that they are cognitive
  atoms. Use feature tuples, not ordinal IDs, for semantic decisions.
- **Items:** generate three independent candidates with common model-selected
  language; apply the conservative answer-span check, then one independent
  per-criterion model judgment; select the earliest valid item and, when
  available, the most token-diverse valid second item. If N=3 has zero coverage,
  allow one unchanged-method two-draw rescue; after repeated determinacy-only
  failure, allow one separately declared two-draw prompt that names the target
  construction. The bank is model-validated, not human-validated.
  Reconstruct the response slot deterministically, freeze any packaging-only
  correction before revalidation, preserve raw candidates/judgments, and
  archive downstream evidence made from a superseded bank.
- **Fold:** use the deterministic semantic 18/5/1 split on the current 24-cell
  inventory: development/compositional/novel `modal=would`. Report constituent
  and pair coverage explicitly.
- **Transfer protocol:** make five passes of development-only acquisition
  (four selection-train, one selection-validation) followed by one non-updating
  all-bank probe. Mixed history is a contamination sensitivity only.
- **Latent worlds:** audit factorized, interaction-heavy, cell-specific, and
  mixed readable worlds; never infer human cognitive truth from a simulator.
- **KC candidates:** enumerate schema-observed non-background feature values,
  declared cell-deterministic English operations, supported cross-dimension
  feature pairs, and exact development cells. Require two cells and three
  items for pair eligibility; retain support and bank-specific activation
  aliases in the artifact.
- **KC selection:** protect supported feature marginals; greedily add eligible
  operation/pair candidates that reduce development-validation observable-PFA
  logistic loss enough to offset `0.0005 × #KCs`; backward-prune additions;
  freeze before grammar-holdout evaluation. Exact cells remain an oracle
  comparison rather than active additions. Use at least 240 learners/selection
  seed at the current bank size and report addition frequencies across seeds.
- **KT:** primary logistic uses only prior observable history, standardized on
  train, with neither simulator difficulty nor KC count. Empirical and
  fixed-parameter mean-credit BKT are sensitivities.
- **Statistics:** compare representations with fixed events and fixed KT,
  resampling whole learners; use 5,000 repeats for final intervals.
- **Model backends:** use `gpt-5.6-sol`/high for future normalisation and retain
  `gpt-5.6-sol`/medium generation plus `gpt-5.6-terra`/medium validation. The
  strict zero-critical backend rule was inconclusive for every stage; these are
  operational risk/quality/efficiency choices from matched challenge cohorts,
  not superiority claims and not a rewrite of the retained dataset provenance.
- **Paper:** make the narrower evidence-supported claim: automatic selection
  detects supported strong interactions and otherwise falls back to marginals;
  no representation is universally best and compositional benefit is not yet
  established.

## 3. Active RQs and status

| RQ | Status | Current answer / remaining work |
|---|---|---|
| RQ1 granularity/prediction/parsimony | partially answered | λ=.0005 selected interactions give the best controlled prediction/parsimony point in the strong interaction world; exact cells help only in a cell world and no representation universally wins. |
| RQ2 feature-value sufficiency | partially answered | Sufficient in factorized and current mixed/null runs, not interaction-heavy or cell-specific worlds. |
| RQ3 useful interactions | partially answered | Perfect×negative and present×negative are recovered when planted strongly; perfect×negative is selected in the final mixed seed. Natural/human interactions remain unknown. |
| RQ4 automated recovery | answered for synthetic controls | Recovery is 3/3 for both eligible strong planted interactions and 0/3 additions in two null worlds; weak mixed recovery is 1/3. |
| RQ5 compositional generalisation | partially answered | Protocol is repaired, but interaction-world automated–factorized compositional CI crosses zero. |
| RQ6 latent-world robustness | answered within declared worlds | Rankings are world-dependent; no universal winner. Human-world relevance is unresolved. |
| RQ7 selector-model sensitivity | answered at medium structural scale | BKT/logistic inventories differ materially; BKT overselects under shared full-credit updates, so logistic is primary. |
| RQ8 scalable grammar folds | answered for current schema | Semantic tuple split gives 18/5/1 cells and is ID/order invariant. |
| RQ9 genuine transfer protocol | answered | Old mixed history did not test transfer; frozen probes now give zero holdout acquisition exposure. |
| RQ10 lexical material | answered at eight-cell model-validated pilot | Model-selected language covers 8/8 at N=3 versus controlled 5/8; no human realism claim. |
| RQ11 best-of-N | answered conditionally | In the final curated evidence, N=1/2/3 prefixes cover 16/19/22 of 24 cells; N=3 remains the default but needs separately labelled fallbacks for complete coverage. Pilot N=5 added no eight-cell coverage. |
| RQ12 Phase-2 usefulness | partially answered | Legacy yield is 2/80=2.5%; broader fresh annotation stability is unknown. |
| RQ13 operation KCs | answered structurally | Cell-deterministic tags reproduce declarations but are aliases/redundant as item metadata; only non-alias declared operations remain candidates. |
| RQ14 candidate-space size | answered structurally | The final development bank yields 55 raw candidates, 38 activation classes, and 28 selection-eligible candidates. |
| RQ15 background/reference values | partially answered | Explicit references control explosion; cognitive treatment of present/past remains an assumption. |
| RQ16 source evidence | partially answered | Three matched cells show no N=3 benefit; opaque IDs are removed. Sample too small for a general negative claim. |
| RQ17 eligibility/transition safety | answered structurally | Avoids 71/80 legacy Phase-2 calls and rejects six adversarial unsafe cases. |
| RQ18 validation reliability | partially answered | Acceptance agreement .826 same-model/.792 alternate-model; no human gold and ceiling criteria prevent deletion/ensemble claims. |
| RQ19 paired comparison | answered methodologically | Learner-cluster paired bootstrap with fixed event identities is implemented/tested. |
| RQ20 support for stable selection | answered within the declared synthetic studies | At least 240 learners are needed for 3/3 strong-control recovery and both clean nulls. All five final-bank 1,000-learner seeds select the same inventory; one 120-learner prefix swaps interactions. Structural support for perfect×negative is still only two cells/four items. |
| RQ21 backend reasoning effort | answered operationally; confirmatory rule inconclusive | A fresh 905-call audit supports high normalisation and retaining medium generation/validation. Strict zero-critical gates select no winner; aliases, unseeded sampling, and research-agent rather than human review bound the result. |

## 4. Established findings

1. Fixed-item/fixed-outcome and development-only discovery/selection boundaries
   are implemented and tested.
2. Phase 2 produced 48 raw/33 activation-class/26 eligible candidates on the
   16-development-cell legacy structure. Phase 4 produces 55/38/27 on the
   semantic 18-cell development bank.
3. English operation declarations are outside generic KC code. Direct
   negation/passive/imperative/inversion are activation aliases on the measured
   bank; finite/perfect/progressive operations can be distinct. Generator tags
   add no independent evidence and have been removed from active items.
4. An alternate `mood`/`person` schema passes candidate generation, active
   learner-evidence selection, policy freezing, and projection. None of this
   constitutes cross-lingual empirical evidence.
5. The semantic fold yields 18 development, five constituent-compositional, and
   one novel-value cell; final selected-item counts are 32/10/2. Of 37
   compositional value pairs, 36 occur in development.
6. Frozen probes have zero prior same-cell holdout exposure. Mixed histories
   average 8.843 compositional and 4.836 novel same-cell exposures, changing
   the estimand.
7. In four worlds × three seeds × 240 learners, automated selection chooses
   9/9/9 KCs in factorized, 11/12/11 in interaction-heavy, 9/9/9 in
   cell-specific, and 9/9/10 in mixed worlds.
8. Mean automated-minus-factorized frozen all-probe log loss is 0, -.002256, 0,
   and +.000016 in factorized, interaction-heavy, cell-specific, and mixed
   worlds. On the reference interaction seed it is -.002666 with learner 95%
   interval [-.004244,-.001103]. Compositional-only is -.001438
   [-.005268,.002646].
9. Oracle exact-all-cell KCs win only in the matching cell-specific world; the
   active selector cannot discover cell KCs by design and this remains a stated
   limitation.
10. Oracle simulator difficulty, KC count, and logistic C=.1/1/10 do not alter
    the Phase-4 ordering materially. Duplicate activation columns affect
    regularized logistic slightly but not BKT; BKT has a substantive multi-KC
    full-credit update confound.
11. The live item pilot made 89 generation attempts, produced 86 structurally
    valid candidates and 56 all-criteria accepts. Model-selected N=1/3/5 covers
    6/8, 8/8, 8/8 cells; controlled lexicon covers 5/8, 5/8, 7/8.
12. Determinacy participates in 29/30 live rejections. Validator repeat/model
    agreement is moderate/substantial, not gold-label reliability.
13. The 139-row legacy normalisation replay yields 44 complete, 77 partial, 16
    out-of-scope, and two unresolved rows; only two of 80 Phase-2 calls resolve.
14. The final contract suite passes 112 tests; both executed notebooks and the
    fixture runner traverse the active code/artifact graph. Fixture output is
    six selected items and 624 events.
15. At λ=.0005, the factorized null becomes clean from 60 learners, but the
    cell-specific null becomes clean only at 240. Both eligible interaction-
    heavy dependencies are jointly recovered in 2/3 seeds at 30/60/120
    learners and 3/3 at 240.
16. At 240 learners, λ=0/.00025 produce factorized-null additions in 3/3 and
    2/3 runs; λ=.001 jointly recovers both planted interactions in only 2/3;
    λ=.002 in 0/3. λ=.0005 is the only tested point with 0/3 null additions and
    3/3 joint recovery.
17. The Phase-5 reference interaction-heavy paired effect is Δ log loss
    -.002666 [-.004244,-.001103] and Δ Brier -.001127
    [-.001795,-.000471]. Compositional Δ log loss remains inconclusive at
    -.001438 [-.005286,.002518].
18. Full item construction makes 78 attempts and 77 structurally valid
    payloads. After six frozen packaging corrections and rejudgments, the
    active evidence has 54 model-validator accepts and 44 selected items
    covering 24/24 cells. Final N=3 prefixes cover 22 cells; unchanged rescue
    recovers one; corrected explicit-construction evidence recovers the last.
19. The final development bank has 55 raw candidates (9 feature, 10 operation,
    18 pair, 18 exact-cell), 38 activation classes, and 28 selection-eligible.
    One rather than up-to-two variants would leave only 23 eligible candidates;
    five pairs cross the item-support guard through second variants.
20. The final automated policy contains nine marginals plus perfect×negative.
    Its logistic test delta from factorized is -.000375
    [-.000631,-.000109] overall and -.000234 [-.000836,.000375]
    compositionally; only the overall effect excludes zero. All seven supported
    interactions improve over factorized by -.000397 [-.000782,-.000026]
    overall and -.001168 [-.002042,-.000246] compositionally, at the cost of 16
    vs 10 KCs. Novel-value effects for automation remain inconclusive.
21. All five final 1,000-learner mixed-world seeds select the identical 10-KC
    policy (Jaccard 1.0). Nested 60/240/500/1,000 prefixes agree; the 120-learner
    prefix selects present×passive instead (Jaccard .818). No holdout or
    reserved-test event enters any selection.
22. Independent agent inspection found no clearly wrong-cell or ungrammatical
    selected target, but 9/45 pre-curation items were judgment-sensitive and
    five had packaging/reference defects. Corrected revalidation changed three
    acceptance decisions, including two flips on unrelated determinacy, so
    validator stability and worksheet-like contextual repetition are explicit
    limitations.
23. After the Phase-7 language-generality cleanup, the exact finalizer
    reproduces every 44-item/204,000-event policy and metric. Forced
    regeneration of all five stability streams preserves the identical
    full-support inventories. The final suite passes 112 tests; both executed
    notebooks, the fixture runner, and the 12-page ACL PDF all verify
    successfully.
24. BACKEND-THINKING-001 evaluates 918 stage decisions (905 live model calls,
    3,351,258 CLI tokens) with interleaved medium/high/xhigh conditions and two
    blind reviewers. Normalisation quality is 89.4/92.4/92.4% with repeat
    agreement 78.8/87.9/81.8%; high is the operational choice over xhigh on
    stability/cost. Validation blind-reference agreement is 69.4/58.3/56.9%,
    so medium remains active. Generation blind position-1 quality ties at
    87.5%; high raises fixed-judge coverage 21→23 cells but has more critical
    reviewed defects and no decisive paired interval, so medium remains active.
    The strict zero-critical rule is explicitly retained as inconclusive.

## 5. Current methodological decisions and evidence

| Decision | Evidence | Confidence / caveat |
|---|---|---|
| Preserve fixed bank/events across KC policies. | API contracts, event hashes, probe invariance. | high |
| Use explicit Phase-2 eligibility and branch-preserving narrowing. | 80-transition replay + six adversarial cases. | high structurally; annotation quality uncertain |
| Use N=3 model-selected generation, keep ≤2 valid variants; label fallbacks separately. | Curated full bank: 16/19/22 cells at N=1/2/3; rescue and explicit cue reach 24. | medium; no human realism evidence |
| Freeze packaging-only corrections and independently revalidate. | Six-row F36 audit; raw hashes preserved; active bank 44 items after three acceptance flips. | high for artifact integrity; judge instability remains |
| Keep every validation criterion and one independent judge. | 24-item repeat/model sensitivity; no human gold. | medium-low; report uncertainty |
| Use semantic 18/5/1 fold and frozen probes. | Structural coverage, ID invariance, exposure audit. | high for synthetic evaluation |
| Use four latent worlds. | Strong world×representation interaction. | high as robustness controls, not human model |
| Use 2-cell/3-item pair guard. | Full bank has 28 eligible candidates; rank-1-only has 23, exposing item-support sensitivity. | medium; item variants are not independent structures |
| Use protected marginals + λ=.0005 logistic forward/prune selector. | At 240 learners: clean null 3/3 and joint strong recovery 3/3; adjacent λ values trade false positives/negatives. | medium-high for declared worlds; weak/mixed/cell worlds expose limits |
| Require at least 240 learners/seed for current-scale selection. | Nested Phase-5 support curve. | medium; structural support does not grow with repeated learners |
| Use no-oracle/no-count standardized logistic primary. | Control deltas <.00020; removes privileged inputs. | high |
| Use learner-paired representation intervals. | Exact-pair implementation/tests and final 5,000-resample effects. | high |
| Use stage-specific backend effort: high/medium/medium. | BACKEND-THINKING-001 matched calls, blind review/adjudication, paired 10,000-resample contrasts, efficiency evidence. | medium; strict rule inconclusive, mutable aliases/no provider seed/no human gold |

## 6. Rejected alternatives / negative results

- Obligation coverage as main selector: interactions could replace reusable
  marginals and the method used no learner evidence; code/config removed.
- Mean active-KC histories: non-nested predictors confounded additions.
- Double parsimony threshold and λ=.001/.002: planted false negatives.
- λ=.00025: null-world false additions; λ=.0005 is the cautious compromise.
- Mixed-history grammar scores as transfer: direct holdout practice contaminates
  acquisition.
- Simulator-derived difficulty and KC count in primary logistic: privileged or
  representation-dependent inputs with no observed benefit.
- BKT as selector: shared full-credit updates and excess additions.
- Controlled six-entry lexicon: lower cell coverage than model-selected text.
- N=5 default: additional accepted variants but no extra cell coverage.
- Opaque source IDs and generator operation tags: no linguistic information or
  independent activation evidence.
- Validator ensemble or criterion deletion: no human gold and insufficient
  negative cases to justify either.
- Strong compositional-transfer claim: current paired interval includes zero.
- Universal automated-selector winner: contradicted by the cell-specific world.
- One shared medium effort for every live module: high improves normalisation
  quality/stability; xhigh adds no supported stage-level benefit.
- Unpenalized/λ=.00025 selection: overselect in the factorized null; λ=.001 and
  .002: increasingly miss planted interactions.

## 7. Known weaknesses

- The empirical language domain is English only; alternate-schema tests verify
  software structure, not cross-lingual validity.
- Learners and correctness are synthetic; worlds omit vocabulary, forgetting,
  transfer between KCs, multidimensional strategy use, and real classroom
  behavior.
- Items and validation are LLM-based with no human learner or expert study.
- The 44-item bank is model-generated and model-validated; complete structural
  coverage required a post-rescue explicit-construction cue for one cell.
- The normalisation inventory is a retained older model run with unpinned
  sampling; repeat evidence covers only eight selected rows.
- One semantic compositional pair is unseen in development, and the two novel
  `would` items have zero factorized KC coverage.
- Candidate equivalence is bank-specific. Reference/background values and the
  prohibition on exact-cell active additions are explicit assumptions.
- Observable PFA gives full response credit to all active KCs. Regularized
  dimension effects are small here but remain conceptually relevant.
- The Phase-6 dataset declares the audited mixed world as primary while
  retaining four worlds as sensitivities. This is an experimental convention,
  not a claim that mixed is the true human world.
- Item-generation/provider prices were unavailable, and concurrent per-call
  durations are workload totals rather than elapsed wall time.
- Backend-effort calls use mutable aliases and no provider sampling seed;
  research-agent review is not human/expert gold, and every strict critical-
  error gate remained inconclusive.
- Normalisation effort calls ran from the repository root before later audit
  calls gained declaration-only working-directory isolation. Transcript scans
  found no tool/file access, but that stage boundary was procedural.

## 8. Important artifact paths

- Active pipeline: `scripts/run.py`, `notebooks/pipeline_walkthrough.ipynb`
- Active declarations: `modules/grammar/`, `modules/items/`,
  `modules/model_backends.yaml`,
  `modules/simulation/folds/semantic.yaml`, `modules/simulation/protocol.yaml`,
  `modules/kcs/candidate_design.yaml`, `modules/kcs/selection.yaml`,
  `modules/evaluation/kt/protocol.yaml`
- Backend effort audit: `reports/backend_thinking/analysis.md`,
  `reports/backend_thinking/artifacts/live_v1/`,
  `scripts/run_backend_thinking_audit.py`,
  `scripts/analyze_backend_thinking_reviews.py`
- Candidate/selector code: `src/grammar_kt/kc_candidates.py`,
  `src/grammar_kt/kc_selection.py`, `src/grammar_kt/kc.py`
- Phase 2: `reports/phase2/analysis.md`, `reports/phase2/artifacts/`
- Phase 3: `reports/phase3/analysis.md`, `reports/phase3/artifacts/`
- Phase 4 report: `reports/phase4/analysis.md`
- Phase 5 report: `reports/phase5/analysis.md`
- Phase 5 artifacts: `reports/phase5/artifacts/integrated_validation_v1/`
- Fold artifacts: `reports/phase4/artifacts/fold/`
- Normalisation artifacts: `reports/phase4/artifacts/normalisation/`
- Live item audit: `reports/phase4/artifacts/item_audit/live_pilot/`
- Validator reliability: `reports/phase4/artifacts/validation_reliability/`
- Four-world/KT audit: `reports/phase4/artifacts/world_kt/study_v1/`
- Experiment ledger: `reports/experiment_log.md`
- Source inventory: `runs/base/source/source_subset.jsonl`
- Retained mappings: `runs/base/normalisation/final_mappings.jsonl`
- Final ACL manuscript and rendered PDF: `ACL/paper.tex`, `ACL/paper.pdf`
- Final dataset: `data/grammar_kt_medium_v1/`
- Full-dataset tables: `reports/phase6/artifacts/full_dataset_analysis/`
- Full-dataset investigation: `reports/full_dataset_investigation.md`
- Final-bank stability: `reports/phase6/artifacts/selection_stability_v1/`
- Qualitative item audit: `reports/phase6/artifacts/qualitative_item_audit.md`
- Final methodology: `reports/final_methodology.md`
- Final RQ ledger: `reports/final_rq_ledger.md`
- Final verification: `reports/final_verification.md`

## 9. Current recommended next step / phase

The autonomous programme is complete. The scientifically most valuable next
step is external human/expert item validation followed by real learner-response
collection; those require new participants/authority and are outside this run.
Within the current synthetic scope, future work should enlarge compositional
and novel-value cell coverage and repeat normalisation/generation across pinned
models before changing the retained method.
