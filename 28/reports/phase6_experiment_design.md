# Phase 6 experiment design — medium grammar-KT dataset

Date frozen: 2026-08-27  
Status: source/canonical preparation complete; live missing-cell generation has
not started; KC penalty awaits the Phase-5 checkpoint.

## Scientific scope

The final empirical language domain is the retained English Grammar Profile
(EGP) sample. The dataset is medium scale rather than a claim of exhaustive
English grammar coverage. It combines a real grammar-resource sample and live
model-generated/model-validated exercise text with controlled synthetic learner
evidence. Synthetic correctness is appropriate for evaluating whether the KC
method can recover declared latent structure; it is not evidence that the
latent worlds describe human learners.

The expensive language-model stage stops at a fixed item-bank boundary:

```text
139 frozen source descriptors
→ retained normalisation evidence
→ 24 exact GrammarCells
→ N=3 independent item candidates/cell
→ independent validation
→ at most two selected items/cell
──────────────────────── fixed item bank ────────────────────────
→ fold, simulation, KC candidates, KC selection, projection, KT
```

No fold, KC, learner outcome, simulation parameter, or KT result may influence
generation or validation. The first three model-selected candidates from the
Phase-4 pilot are reused by exact feature-tuple identity for eight cells; no
language-model call is repeated when its evidence is already frozen.

## Research questions

The programme RQ-F1--F30 are retained. Operational questions and additional
failure-driven questions are grouped here to make the analysis executable.

### Source and canonicalisation

- **F1/F2:** What proportions are complete/partial/unresolved/out of scope, and
  how many exact cells result?
- **F3:** How much source-descriptor compression occurs, distinguishing
  contributing descriptors, source-cell edges, and unique cells?
- **F4/F5:** Which values and combinations are sparse or dominant?
- **F6/F7:** How many semantic compositional and novel-value cells/items can be
  retained after item acceptance?
- **F29:** Which decisions are English-schema-specific and which KC operations
  consume only a declared schema?
- **F30:** What stability evidence exists for source-to-canonical mappings, and
  what remains unavailable because the retained model snapshot is unpinned?

### Item bank

- **F8/F9:** How many generation attempts per cell are needed, and does the
  pilot N=1/3/5 result remain descriptively compatible with full-bank coverage?
- **F10--F14:** What are acceptance, structural failure, criterion failure,
  lexical/contextual diversity, and non-target-language rejection rates; which
  cells/structures are hardest?
- **F26:** Which stages dominate recorded concurrent call time? Provider price
  is reported only if available.
- **F27/F28:** What new failures appear at 24 cells, and do qualitative examples
  resemble usable focused practice rather than uniform templates?
- **F31 (added):** Does the deterministic answer-span check reject malformed
  response contracts without reducing cell coverage?
- **F32 (added):** How much does selecting at most two candidates reduce the
  validator-accepted pool, and does token-distance selection preserve lexical
  diversity and complete cell coverage?
- **F33 (conditional):** If any cell has no accepted N=3 candidate, what failure
  caused it and does one predeclared rescue batch resolve it? Rescue results are
  reported separately and never relabelled as N=3 evidence.

### KC and learner evidence

- **F15--F17:** What is the raw feature/operation/pair/full-cell candidate
  space, how much do support/equivalence filters remove, and which operations
  remain nonredundant?
- **F18--F21:** Which additions are selected, how stable are they, how many KCs
  result versus factorized/full-cell extremes, and what is support/Q density?
- **F22--F24:** What fixed-logistic prediction/parsimony and frozen
  development/compositional/novel-value performance results, and how do Phase-4
  world sensitivities constrain the conclusion?
- **F25:** Is 1,000-learner selection consistent with the Phase-5 nested support
  curve, and how stable is selection across smaller repeated streams?
- **F34 (added):** Does using one versus up-to-two accepted variants per cell
  alter pair eligibility or the selected inventory through item-support counts?

## Frozen design choices

| Component | Choice | Evidence/justification |
|---|---|---|
| Source | all 139 retained typed rows | Entire available audited sample; avoids outcome-driven source selection. |
| Normalisation | retained `gpt-5.6-sol`, medium outputs; active eligibility/transition validation on reload | Phase 4 established 2.5% Phase-2 yield and safer explicit routing. Regeneration would add cost and change the source inventory without an identified intervention. |
| Canonicalisation | exact cells only under the active six-dimension English schema | Preserves conservative uncertainty boundary; reproduces the 24-cell inventory exactly. |
| Generation | `gpt-5.6-sol`, medium; three independent candidates/cell; four concurrent workers | Phase-4 N=3 covers all eight sentinels; N=5 adds no coverage. |
| Item language | common model-selected lexical/contextual material | Controlled six-entry lexicon has lower coverage. |
| Validation | `gpt-5.6-terra`, medium; conservative answer-span precheck then one all-required-criteria judgment | Phase-4 reliability does not justify an ensemble or criterion deletion. |
| Bank | earliest valid + most token-distant second valid; maximum two/cell | Supplies repeated measurement/support while controlling bank size; inspect F32/F34. |
| Fold | semantic 0.20 compositional fraction, minimum two development cells/value, explicit novel `modal=would` | Phase-4 yields 18/5/1 cells and is ID/order invariant. Fold is computed only after bank freezing. |
| Primary transfer | five development acquisition passes (four train, one validation), then one non-updating all-bank probe | Gives zero holdout acquisition exposure. |
| Primary dataset world | declared mixed world, 1,000 learners, seed 20260827 | Includes marginals and interactions without implying it is the human truth; large enough to exceed the Phase-5 240-learner support ceiling. |
| Robustness | retain four-world × three-seed Phase-4 study; add full-bank selector stability only where needed | Avoids blindly repeating a full Cartesian KT grid. |
| KC candidates | feature, declared deterministic operation, supported pair, development full-cell; pair guard ≥2 cells and ≥3 items | Active Phase-2/4 structural method. |
| Selector | protected marginals + observable-logistic forward additions/backward prune; final λ frozen by Phase 5 | Active automated method; no holdout grammar/outcomes. |
| Representations | factorized, all-supported interactions, automated, labelled oracle-all-cell | Small set spanning reusable to memorized extremes. Manual interaction inventory is not a final main method. |
| KT | empirical, fixed BKT sensitivity, standardized observable logistic primary | Phase-4 audit rejects oracle difficulty/KC count and BKT selection. |
| Metrics | log loss/Brier primary; AUC/ECE diagnostic; development/compositional/novel regimes | Proper scores plus transparent regime analysis. |
| Uncertainty | 5,000 learner-cluster paired bootstrap repeats, seed 20260827 | Fixed learner/event comparison and Phase-5 method. |

### Conditional item rescue

The default bank is exactly N=3. If any of the 24 cells has zero accepted items
after those calls, first inspect and report its structural/model rejection
reasons. Then make one separate rescue batch of two independent candidates for
only uncovered cells, with the same generator and validator. The manifest must
retain `default_n3` and `rescue` provenance separately. A cell still uncovered
after rescue remains an explicit dataset gap; no prompt tuning based on its
validation result is allowed inside this experiment.

## Planned scale and retained artifacts

- source rows: 139;
- expected exact cells: 24;
- default attempts: 72 total, of which 24 are frozen Phase-4 calls and 48 are
  new;
- selected bank: at most 48 items, target at least one per cell;
- semantic cell fold: expected 18/5/1, subject to accepted-item support;
- primary synthetic learners: 1,000;
- acquisition opportunities/learner: five times the number of development
  items;
- frozen probes/learner: every selected item once;
- primary seed: 20260827;
- stability seeds where run: 20260827--20260831;
- bootstrap: 5,000 learner resamples, seed 20260827.

Retain source, mapping, cells, source-cell relations, every generation attempt,
every valid candidate, every model judgment, accepted pool, selected bank,
fold, events, private oracle, candidate inventory, selection trace, frozen
policies, projections/Q-matrices, predictions, metrics, paired effects, and
qualitative examples under `data/grammar_kt_medium_v1/` and
`reports/phase6/`.

## Exact staged commands

Static preparation already executed without model calls:

```bash
.venv/bin/python scripts/run_full_dataset.py --prepare-only \
  --output-dir data/grammar_kt_medium_v1
```

After the Phase-5 selector checkpoint, run missing-cell generation/validation:

```bash
.venv/bin/python scripts/run_full_dataset.py --generate-missing --workers 4 \
  --generation-model gpt-5.6-sol --validation-model gpt-5.6-terra \
  --reasoning-effort medium --output-dir data/grammar_kt_medium_v1
```

The downstream integration command will be recorded after the Phase-5 choice
is frozen and before it is executed. No paper claim may use prepared-only or
partially covered bank statistics as final-dataset evidence.

## Default N=3 checkpoint and conditional failure study

The missing-cell command was executed after Phase 5 froze λ=.0005. Across the
full 24-cell bank, default N=1/2/3 prefixes yield respectively 18/21/22 covered
cells and 18/35/53 accepts from 24/48/72 attempts. N=3 contains 71 structurally
valid candidates, 53 accepted candidates, and 43 selected items; 21 cells have
two selected variants, one has one, and two have none. Thus the eight-cell
pilot correctly predicted a large N=3 coverage improvement but overestimated
complete-bank coverage.

The uncovered cells are:

- `cell_017`: past perfect progressive, active, negative, declarative;
- `cell_022`: past perfect, passive, positive, declarative.

All six outputs are structurally valid but fail determinacy. The negative past
perfect progressive prompts allow a perfect-simple/simple-past alternative,
and one candidate contradicts its negative answer. The passive past-perfect
contexts also allow a simple-past passive/stative reading. This is a coherent
hard-structure failure rather than random API loss.

**F33 hypothesis frozen before rescue calls.** Two further independent draws
with the unchanged prompt, rulebook, generator, validator, and criteria may
produce temporally explicit contexts that determine the target without tuning
against individual judgments. Generate indices 4 and 5 only for these two
cells and label them `conditional_rescue`; report default N=3 and rescue
coverage separately. If either remains uncovered, do not make another blind
batch: leave the gap or run a separately motivated prompt intervention.

## Determinacy prompt intervention preregistration (2026-08-27)

**Frozen before any determinacy-intervention live call.** The unchanged-prompt
rescue is complete. It yields one accepted item for `cell_022`, while
`cell_017` remains uncovered: all five of its structurally valid default-plus-
rescue candidates fail the independently judged determinacy criterion. This
repeated, construction-specific ambiguity motivates a separate intervention,
not another blind best-of-N batch.

**F35 hypothesis.** For a grammatical contrast that short semantic contexts do
not uniquely determine, allowing the learner-facing instruction to explicitly
name the complete target construction (for example, “use the negative past
perfect continuous”) will improve determinacy without disclosing the inflected
answer. This tests an instructional-design choice; it does not retroactively
alter the default N=3 or unchanged-prompt rescue conditions.

Freeze the still-uncovered post-rescue cohort before the first call. For every
frozen cell, generate exactly candidate positions 6 and 7 and independently
validate both even if position 6 is accepted. Change only the researcher-facing
generation prompt to
`modules/items/generation/ablations/determinacy_explicit_construction_prompt.txt`.
Keep the rulebook, controlled-production format, lexical design, generator
(`gpt-5.6-sol`, medium), validator (`gpt-5.6-terra`, medium), and all validation
criteria fixed. Retain a separate plan, provenance status, evidence directories,
and manifest counts. Report acceptance, criterion-level outcomes, and coverage
separately from default N=3 and unchanged-prompt rescue. Make no additional
generation calls if both preregistered positions fail.

Exact command frozen before execution:

```bash
.venv/bin/python scripts/run_full_dataset.py --determinacy-intervention \
  --workers 4 --generation-model gpt-5.6-sol \
  --validation-model gpt-5.6-terra --reasoning-effort medium \
  --output-dir data/grammar_kt_medium_v1
```

No determinacy-intervention result is recorded in this preregistration section.

## Final-bank selection-stability plan (frozen before execution)

The primary `20260827` downstream run has been materialized, so its selected
inventory and test metrics are known. The following stability design is frozen
before any additional event stream is generated and is not tuned to make that
inventory recur.

- Reuse the final 24 cells, 45 fixed items, 18/5/1 fold, candidate inventory,
  mixed-world declaration, simulation protocol, selector, and `lambda=.0005`.
- Generate complete 1,000-learner frozen-probe streams for exactly seeds
  `20260827`--`20260831`. Verify deterministic equality with the retained
  primary stream/policy at `20260827`; retain compressed streams, hashes, and
  every selected policy.
- On the reference seed only, select from deterministic nested learner prefixes
  of 60, 120, 240, 500, and 1,000 learners. At 1,000 learners only, compare all
  five seeds. This gives nine unique selections rather than a blind Cartesian
  grid.
- Report all-KC and addition-only Jaccard, exact-inventory recurrence, selected
  addition frequency, KC count, and validation loss/objective. Never use a
  grammar-holdout item or outcome in selection.

**F19/F25 hypothesis.** The nine protected marginals should be invariant. The
low-support selected interaction may remain seed-sensitive even with 1,000
learners because repeated learner events do not increase its two-cell/four-item
structural support; larger learner samples should reduce, but cannot eliminate,
sampling-driven additions.

Exact command frozen before execution:

```bash
.venv/bin/python scripts/run_phase6_selection_stability.py
```

No stability outcome is recorded in this preregistration section.

## Item packaging-correction preregistration (F36; 2026-08-27)

**Frozen before any correction revalidation call.** A complete manual audit of
all 45 selected items, plus the rejected intervention candidate
`candidate_cell_017_06`, identified six data-packaging inconsistencies. These
are answer-key serialization defects: the target GrammarCell, prompt, lexical
content, and intended grammatical response do not change. Four accepted-answer
spans repeat punctuation that is already printed after the response slot; two
full-sentence `target_answer` fields omit visible sentence context or preserve
only the slot-local clause. The rejected intervention item has the same
slot-versus-full-sentence mismatch in `target_answer` that the original judge
explicitly cited.

**F36 hypothesis.** Applying only the six frozen, exact before/after field
edits will remove these packaging inconsistencies without changing item IDs,
prompts, target GrammarCells, generation evidence, or original judgments. A
fresh independent judgment of all six corrected records under the unchanged
`gpt-5.6-terra` medium validator and unchanged all-required criteria will test
whether each corrected package is valid; the corrected judgment overrides the
original only in the curated bank. This is a disclosed post-generation data
curation stage, not additional generation and not evidence for best-of-N.

The frozen plan is `items/packaging_correction_plan.json`. The curation script
must verify the plan hash and every exact pre-correction value, preserve
`items/candidates.jsonl` and `items/validation.jsonl` byte-for-byte, write all
77 rows to `items/curated_candidates.jsonl` with correction provenance, and
retain the six new judgments and call evidence separately. It must then rebuild
the accepted pool and at-most-two-per-cell selected bank deterministically,
using corrected judgments only for the six planned IDs. Because item content
feeds the fold, simulation, KC projection, KT, and evaluation, all existing
downstream artifacts must be moved to an explicit
`superseded_pre_curation/` archive before those stages are rerun.

Exact command frozen before execution:

```bash
.venv/bin/python scripts/curate_item_packaging.py \
  --dataset-dir data/grammar_kt_medium_v1 --workers 4 \
  --validation-model gpt-5.6-terra --reasoning-effort medium
```

No packaging-correction result is recorded in this preregistration section.
